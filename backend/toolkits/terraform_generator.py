import os
import logging
import mysql.connector
from typing import Dict, Any, Optional, List

class TerraformGenerator:
    """工具类，用于生成Terraform配置文件"""
    
    def __init__(self, db_config: Dict[str, Any]):
        """初始化TerraformGenerator
        
        Args:
            db_config: 数据库配置信息
        """
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)
    
    def _get_connection(self):
        """创建并返回数据库连接"""
        return mysql.connector.connect(**self.db_config)
    
    def get_deployment_info(self, deploy_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取指定部署ID的信息
        
        Args:
            deploy_id: 部署ID
            
        Returns:
            包含部署信息的字典，如果未找到则返回None
        """
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 查询指定部署ID的配置
            cursor.execute(
                "SELECT * FROM cloud WHERE deployid = %s ORDER BY id DESC LIMIT 1",
                (deploy_id,)
            )
            result = cursor.fetchone()
            
            if not result:
                self.logger.warning(f"未找到部署ID为{deploy_id}的配置")
                return None
                
            self.logger.info(f"找到部署ID为{deploy_id}的配置: {result}")
            return result
        except Exception as e:
            self.logger.error(f"获取部署信息时出错: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def generate_terraform_file(self, deploy_id: str, selected_products: list = None) -> str:
        """为指定部署ID生成Terraform配置文件
        
        Args:
            deploy_id: 部署ID
            selected_products: 用户选择的产品列表
            
        Returns:
            生成的文件路径，如果生成失败则返回空字符串
        """
        # 获取部署信息
        deploy_info = self.get_deployment_info(deploy_id)
        if not deploy_info:
            self.logger.error(f"无法为部署ID {deploy_id} 生成Terraform配置文件: 未找到部署信息")
            return ""
        
        # 确保必要的字段存在
        ak = deploy_info.get('ak', '')
        sk = deploy_info.get('sk', '')
        region = deploy_info.get('region', '')
        cloud = deploy_info.get('cloud', '')
        project = deploy_info.get('project', 'default')
        
        if not all([ak, sk, region, cloud]):
            self.logger.error(f"部署ID {deploy_id} 的配置缺少必要信息: AK={bool(ak)}, SK={bool(sk)}, region={bool(region)}, cloud={bool(cloud)}")
            return ""
        
        # 创建query目录（如果不存在）
        # 获取backend目录路径
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        query_dir = os.path.join(backend_dir, "query")
        os.makedirs(query_dir, exist_ok=True)
        
        # 创建以deploy_id命名的子目录
        deploy_dir = os.path.join(query_dir, deploy_id)
        os.makedirs(deploy_dir, exist_ok=True)
        
        # 设置文件路径
        file_path = os.path.join(deploy_dir, "main.tf")
        
        try:
            # 生成Terraform配置内容
            if cloud.upper() == "AWS":
                config_content = self._generate_aws_terraform_content(deploy_info, selected_products)
            elif "AZURE" in cloud.upper():
                config_content = self._generate_azure_config(project, ak, sk, region)
            elif "ALI" in cloud.upper():
                config_content = self._generate_aliyun_config(project, ak, sk, region)
            else:
                config_content = self._generate_default_config(project, ak, sk, region, cloud)
            
            # 写入文件
            with open(file_path, 'w') as f:
                f.write(config_content)
            
            # 验证文件是否正确生成并包含正确的版本
            if cloud.upper() == "AWS":
                with open(file_path, 'r') as f:
                    content = f.read()
                    if "version = \"~> 5.84.0\"" not in content:
                        self.logger.error(f"警告：生成的AWS配置文件不包含正确的版本号(5.84.0)")
                    else:
                        self.logger.info(f"AWS配置文件验证成功，包含正确的版本号(5.84.0)")
                
            self.logger.info(f"成功生成Terraform配置文件: {file_path}")
            return file_path
        except Exception as e:
            self.logger.error(f"生成Terraform配置文件时出错: {str(e)}")
            return ""
    
    def _generate_aws_terraform_content(self, config, selected_products=None):
        """生成AWS Terraform配置内容"""
        ak = config.get('ak', '')
        sk = config.get('sk', '')
        region = config.get('region', 'us-east-1')
        
        if selected_products is None:
            selected_products = []
        
        content = f'''terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
    external = {{
      source  = "hashicorp/external"
      version = "~> 2.3.5"
    }}
  }}
}}

provider "aws" {{
  region     = "{region}"
  access_key = "{ak}"
  secret_key = "{sk}"
}}

'''
        
        # 如果没有指定产品或者选择了ALL，则查询所有默认产品
        if not selected_products or 'all' in selected_products:
            selected_products = ['vpc', 'subnet', 'iam', 'ec2', 'elb', 's3', 'rds']
        
        # 判断是否为全局查询区域（us-east-1代表全局查询）
        is_global_region = (region == 'us-east-1')
        
        self.logger.info(f"生成AWS Terraform代码，区域: {region}, 是否全局查询: {is_global_region}, 选择的产品: {selected_products}")
        
        # 根据选择的产品生成相应的数据源
        if 'vpc' in selected_products:
            content += '''
# 获取所有 VPC 的 ID 列表
data "aws_vpcs" "all" {
}

# 遍历每个 VPC ID 并获取详细信息
data "aws_vpc" "selected" {
  for_each = toset(data.aws_vpcs.all.ids)
  id       = each.value
}

output "vpc_details" {
  value = [for vpc in data.aws_vpc.selected : {
    name   = lookup(vpc.tags, "Name", "No Name")
    cidr   = vpc.cidr_block
    vpc_id = vpc.id
  }]
}
'''

        if 'subnet' in selected_products:
            # 如果没有选择VPC，需要单独定义VPC数据源
            if 'vpc' not in selected_products:
                content += '''
# 获取所有VPC列表（为子网查询）
data "aws_vpcs" "all" {
}
'''
            
            content += '''
# 查询每个VPC的所有子网
data "aws_subnets" "all" {
  for_each = toset(data.aws_vpcs.all.ids)
  filter {
    name   = "vpc-id"
    values = [each.value]
  }
}

# 遍历每个子网并获取详细信息
data "aws_subnet" "details" {
  for_each = toset(flatten([
    for vpc_id, subnet_ids in data.aws_subnets.all : subnet_ids.ids
  ]))
  id = each.value
}

output "subnet_details" {
  value = [for subnet in data.aws_subnet.details : {
    name      = lookup(subnet.tags, "Name", "No Name")
    subnet_id = subnet.id
    vpc_id    = subnet.vpc_id
    cidr      = subnet.cidr_block
  }]
}
'''

        # IAM用户：只在全局查询区域（us-east-1）中查询
        if 'iam' in selected_products and is_global_region:
            self.logger.info("添加IAM用户查询（全局资源）")
            content += '''
# IAM用户查询（全局资源，仅在us-east-1区域执行）
data "aws_iam_users" "all" {
}

# 获取每个IAM用户的详细信息
data "aws_iam_user" "details" {
  for_each = toset(data.aws_iam_users.all.names)
  user_name = each.value
}

output "iam_user_details" {
  value = [for user in data.aws_iam_user.details : {
    name = user.user_name
    id   = user.user_id
    arn  = user.arn
    region = "global"
  }]
}
'''

        if 'ec2' in selected_products:
            content += '''
# 列出所有EC2实例
data "aws_instances" "all" {
}

# 获取每个EC2实例的详细信息
data "aws_instance" "details" {
  for_each = toset(data.aws_instances.all.ids)
  instance_id = each.value
}

output "ec2_details" {
  value = [for instance in data.aws_instance.details : {
    name        = lookup(instance.tags, "Name", "No Name")
    instance_id = instance.id
    instance_type = instance.instance_type
    state       = instance.instance_state
    public_ip   = instance.public_ip
    private_ip  = instance.private_ip
    subnet_id   = instance.subnet_id
  }]
}
'''

        if 'elb' in selected_products:
            content += '''
# 列出所有负载均衡器
data "aws_lbs" "all" {
}

# 直接输出负载均衡器信息，避免复杂的ARN解析
output "elb_details" {
  value = [for arn in data.aws_lbs.all.arns : {
    arn                = arn
    name               = split("/", arn)[2]
    load_balancer_type = split("/", arn)[1]
  }]
}
'''

        # S3存储桶：只在全局查询区域（us-east-1）中查询
        if 's3' in selected_products and is_global_region:
            self.logger.info("添加S3存储桶查询（全局资源）")
            ak = config.get('ak', '')
            sk = config.get('sk', '')
            region = config.get('region', 'us-east-1')
            
            content += f'''
# S3存储桶查询（全局资源，仅在us-east-1区域执行）
data "external" "s3_buckets" {{
  program = ["bash", "-c", <<-EOF
#!/bin/bash
set -e

# 设置AWS凭证环境变量
export AWS_ACCESS_KEY_ID="{ak}"
export AWS_SECRET_ACCESS_KEY="{sk}"
export AWS_DEFAULT_REGION="{region}"

# 使用aws s3 ls查询存储桶
if result=$(aws s3 ls 2>/dev/null); then
    # 解析aws s3 ls的输出格式
    bucket_count=$(echo "$result" | wc -l)
    
    # 构建输出JSON
    output='{{"status": "success", "bucket_count": "'$bucket_count'"'
    
    # 获取前3个存储桶并查询其区域
    counter=0
    while IFS= read -r line && [ $counter -lt 3 ]; do
        if [ ! -z "$line" ]; then
            # aws s3 ls输出格式: 2024-01-01 00:00:00 bucket-name
            bucket_date=$(echo "$line" | awk '{{print $1}}')
            bucket_name=$(echo "$line" | awk '{{print $3}}')
            
            if [ ! -z "$bucket_name" ]; then
                # 查询存储桶的区域
                bucket_region=$(aws s3api get-bucket-location --bucket "$bucket_name" --query 'LocationConstraint' --output text 2>/dev/null || echo "us-east-1")
                # 如果返回None或null，说明是us-east-1区域
                if [ "$bucket_region" = "None" ] || [ "$bucket_region" = "null" ] || [ -z "$bucket_region" ]; then
                    bucket_region="us-east-1"
                fi
                
                output=$output', "bucket_'$counter'_name": "'$bucket_name'", "bucket_'$counter'_date": "'$bucket_date'", "bucket_'$counter'_region": "'$bucket_region'"'
                counter=$((counter + 1))
            fi
        fi
    done <<< "$result"
    
    output=$output'}}'
    echo "$output"
else
    # 查询失败，返回错误信息
    echo '{{"status": "error", "message": "AWS CLI查询失败，请检查凭证和网络", "bucket_count": "0"}}'
fi
EOF
  ]
}}

# 处理S3查询结果
locals {{
  s3_result = data.external.s3_buckets.result
  s3_status = lookup(local.s3_result, "status", "unknown")
  s3_count = tonumber(lookup(local.s3_result, "bucket_count", "0"))
}}

output "s3_details" {{
  value = local.s3_status == "success" ? [
    for i in range(min(local.s3_count, 3)) : {{
      name = lookup(local.s3_result, "bucket_${{i}}_name", "")
      creation_date = lookup(local.s3_result, "bucket_${{i}}_date", "")
      region = lookup(local.s3_result, "bucket_${{i}}_region", "unknown")
      type = "s3_bucket"
    }}
  ] : [{{
    error = lookup(local.s3_result, "message", "S3查询失败")
    message = "请检查AWS凭证和网络连接"
    suggestion = "确保AWS CLI已安装且凭证正确"
  }}]
  description = "S3 buckets retrieved via AWS CLI with provided credentials (global resource)"
}}
'''

        if 'rds' in selected_products:
            content += '''
# 列出所有RDS实例
data "aws_db_instances" "all" {
}

# 获取每个RDS实例的详细信息
data "aws_db_instance" "details" {
  for_each = toset(data.aws_db_instances.all.instance_identifiers)
  db_instance_identifier = each.value
}

output "rds_details" {
  value = [for db in data.aws_db_instance.details : {
    identifier             = db.db_instance_identifier
    engine                 = db.engine
    engine_version         = db.engine_version
    instance_class         = db.db_instance_class
    allocated_storage      = db.allocated_storage
    storage_type           = db.storage_type
    db_name                = db.db_name
    username               = db.master_username
    endpoint               = db.endpoint
    port                   = db.port
    backup_retention       = db.backup_retention_period
    multi_az               = db.multi_az
    publicly_accessible    = db.publicly_accessible
    vpc_security_groups    = db.vpc_security_groups
    subnet_group_name      = db.db_subnet_group
  }]
}
'''

        if 'lambda' in selected_products:
            content += '''
# 列出所有Lambda函数
data "aws_lambda_functions" "all" {
}

output "lambda_details" {
  value = [for func in data.aws_lambda_functions.all.function_names : {
    function_name = func
  }]
}
'''

        if 'cloudfront' in selected_products:
            content += '''
# 列出所有CloudFront分发
data "aws_cloudfront_distributions" "all" {
}

output "cloudfront_details" {
  value = [for dist in data.aws_cloudfront_distributions.all.ids : {
    distribution_id = dist
  }]
}
'''

        if 'route53' in selected_products:
            content += '''
# 列出所有Route53托管区域
data "aws_route53_zones" "all" {
}

output "route53_details" {
  value = [for zone in data.aws_route53_zones.all.zones : {
    zone_id = zone.zone_id
    name    = zone.name
    private_zone = zone.private_zone
  }]
}
'''

        if 'cloudwatch' in selected_products:
            content += '''
# 列出所有CloudWatch日志组
data "aws_cloudwatch_log_groups" "all" {
}

output "cloudwatch_details" {
  value = [for group in data.aws_cloudwatch_log_groups.all.log_group_names : {
    log_group_name = group
  }]
}
'''

        if 'ebs' in selected_products:
            content += '''
# 列出所有EBS卷
data "aws_ebs_volumes" "all" {
}

# 获取每个EBS卷的详细信息
data "aws_ebs_volume" "details" {
  for_each = toset(data.aws_ebs_volumes.all.ids)
  volume_id = each.value
}

output "ebs_details" {
  value = [for volume in data.aws_ebs_volume.details : {
    volume_id       = volume.id
    availability_zone = volume.availability_zone
    size            = volume.size
    volume_type     = volume.type
    state           = volume.state
    encrypted       = volume.encrypted
    snapshot_id     = volume.snapshot_id
    tags            = volume.tags
  }]
}
'''

        return content
    
    def _generate_azure_config(self, project: str, ak: str, sk: str, region: str) -> str:
        """生成Azure Terraform配置
        
        Args:
            project: 项目名称
            ak: Access Key (Client ID)
            sk: Secret Key (Client Secret)
            region: 区域
            
        Returns:
            Terraform配置内容
        """
        config = f'''# Azure Terraform 配置文件 - 仅用于列表资源
# 项目: {project}
# 区域: {region}

terraform {{
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
  subscription_id = "{ak}"
  client_secret   = "{sk}"
  tenant_id       = "tenant-id"  # 需要替换为实际租户ID
  client_id       = "client-id"  # 需要替换为实际客户端ID
}}

# 列出所有资源组
data "azurerm_resource_groups" "all" {{
}}

output "resource_groups" {{
  value = [for rg in data.azurerm_resource_groups.all.resources : {{
    name = rg.name
    location = rg.location
    tags = rg.tags
  }}]
}}

# 列出所有虚拟网络
data "azurerm_virtual_networks" "all" {{
}}

output "virtual_networks" {{
  description = "所有虚拟网络的详细信息"
  value = [for vnet in data.azurerm_virtual_networks.all.virtual_networks : {{
    name = vnet.name
    resource_group_name = vnet.resource_group_name
    address_space = vnet.address_space
    location = vnet.location
  }}]
}}

# 列出所有子网
data "azurerm_subnets" "all" {{
  resource_group_name = azurerm_resource_group.example.name
  virtual_network_name = azurerm_virtual_network.example.name
}}

output "subnets" {{
  value = [for subnet in data.azurerm_subnets.all.subnets : {{
    name = subnet.name
    address_prefixes = subnet.address_prefixes
  }}]
}}

# 列出所有存储账户
data "azurerm_storage_accounts" "all" {{
}}

output "storage_accounts" {{
  value = [for sa in data.azurerm_storage_accounts.all.accounts : {{
    name = sa.name
    resource_group_name = sa.resource_group_name
    location = sa.location
    account_tier = sa.account_tier
    account_replication_type = sa.account_replication_type
  }}]
}}

# 列出所有用户分配的身份
data "azurerm_user_assigned_identities" "all" {{
  resource_group_name = azurerm_resource_group.example.name
}}

output "user_assigned_identities" {{
  value = data.azurerm_user_assigned_identities.all.identities
}}
'''
        return config
    
    def _generate_aliyun_config(self, project: str, ak: str, sk: str, region: str) -> str:
        """生成阿里云Terraform配置
        
        Args:
            project: 项目名称
            ak: Access Key
            sk: Secret Key
            region: 区域
            
        Returns:
            Terraform配置内容
        """
        config = f'''# 阿里云 Terraform 配置文件 - 仅用于列表资源
# 项目: {project}
# 区域: {region}

terraform {{
  required_providers {{
    alicloud = {{
      source  = "aliyun/alicloud"
      version = "~> 1.160.0"
    }}
  }}
}}

provider "alicloud" {{
  access_key = "{ak}"
  secret_key = "{sk}"
  region     = "{region}"
}}

# 列出所有VPC
data "alicloud_vpcs" "all" {{
}}

output "vpc_details" {{
  value = [for vpc in data.alicloud_vpcs.all.vpcs : {{
    name = vpc.name
    cidr = vpc.cidr_block
    id = vpc.id
  }}]
}}

# 列出所有交换机(子网)
data "alicloud_vswitches" "all" {{
}}

output "subnet_details" {{
  value = [for vswitch in data.alicloud_vswitches.all.vswitches : {{
    name = vswitch.name
    cidr = vswitch.cidr_block
    vpc_id = vswitch.vpc_id
    zone_id = vswitch.zone_id
  }}]
}}

# 列出所有OSS存储桶
data "alicloud_oss_buckets" "all" {{
}}

output "bucket_details" {{
  value = [for bucket in data.alicloud_oss_buckets.all.buckets : {{
    name = bucket.name
    location = bucket.location
    storage_class = bucket.storage_class
  }}]
}}

# 列出所有RAM用户
data "alicloud_ram_users" "all" {{
}}

output "ram_users" {{
  value = data.alicloud_ram_users.all.users
}}

# 列出所有RAM组
data "alicloud_ram_groups" "all" {{
}}

output "ram_groups" {{
  value = data.alicloud_ram_groups.all.groups
}}

# 列出所有RAM策略
data "alicloud_ram_policies" "all" {{
}}

output "ram_policies" {{
  value = data.alicloud_ram_policies.all.policies
}}
'''
        return config
    
    def _generate_default_config(self, project: str, ak: str, sk: str, region: str, cloud: str) -> str:
        """生成默认Terraform配置
        
        Args:
            project: 项目名称
            ak: Access Key
            sk: Secret Key
            region: 区域
            cloud: 云提供商
            
        Returns:
            Terraform配置内容
        """
        config = f'''# {cloud} Terraform 配置文件
# 项目: {project}
# 区域: {region}

terraform {{
  required_providers {{
    null = {{
      source = "hashicorp/null"
      version = "~> 3.0"
    }}
  }}
}}

# 环境变量配置
resource "null_resource" "credentials" {{
  provisioner "local-exec" {{
    command = <<-EOT
      echo "Cloud: {cloud}"
      echo "Project: {project}"
      echo "Region: {region}"
      echo "Access Key: {ak}"
      echo "Secret Key: [HIDDEN]"
    EOT
  }}
}}

# 输出
output "project" {{
  value = "{project}"
}}

output "cloud_provider" {{
  value = "{cloud}"
}}

output "region" {{
  value = "{region}"
}}
'''
        return config
    
    def get_terraform_config(self, deploy_id):
        """
        获取Terraform配置信息
        
        Args:
            deploy_id: 部署ID
            
        Returns:
            配置信息字典
        """
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor(dictionary=True)
            
            # 查询配置
            sql = """
                SELECT * FROM cloud 
                WHERE deployid = %s 
                ORDER BY id DESC 
                LIMIT 1
            """
            cursor.execute(sql, (deploy_id,))
            config = cursor.fetchone()
            
            if config:
                self.logger.info(f"找到部署ID为{deploy_id}的配置: {config}")
                return config
            else:
                self.logger.error(f"未找到部署ID为{deploy_id}的配置")
                return None
                
        except Exception as e:
            self.logger.error(f"获取Terraform配置时出错: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close() 