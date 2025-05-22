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
    
    def generate_terraform_file(self, deploy_id: str) -> str:
        """为指定部署ID生成Terraform配置文件
        
        Args:
            deploy_id: 部署ID
            
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
                config_content = self._generate_aws_terraform_content(deploy_info)
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
    
    def _generate_aws_terraform_content(self, config):
        """生成AWS Terraform配置内容"""
        region = config.get('region', 'cn-north-1')
        # 确保西北1区域被正确处理
        if region == 'cn-northwest-1':
            self.logger.info(f"使用宁夏区域(cn-northwest-1)生成AWS Terraform配置")

        ak = config.get('ak', '')
        sk = config.get('sk', '')
        
        content = f'''
# AWS Terraform 配置文件
# 项目: {config.get('project', 'default')}
# 区域: {region}

terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 获取所有 VPC 的 ID 列表
data "aws_vpcs" "all" {{
}}

# 遍历每个 VPC ID 并获取详细信息
data "aws_vpc" "selected" {{
  for_each = toset(data.aws_vpcs.all.ids)
  id       = each.value
}}

output "vpc_details" {{
  value = [for vpc in data.aws_vpc.selected : {{
    name   = lookup(vpc.tags, "Name", "No Name")
    cidr   = vpc.cidr_block
    vpc_id = vpc.id
  }}]
}}

# 查询每个VPC的所有子网
data "aws_subnets" "all" {{
  for_each = toset(data.aws_vpcs.all.ids)
  filter {{
    name   = "vpc-id"
    values = [each.value]
  }}
}}

# 遍历每个子网并获取详细信息
data "aws_subnet" "details" {{
  for_each = toset(flatten([
    for vpc_id, subnet_ids in data.aws_subnets.all : subnet_ids.ids
  ]))
  id = each.value
}}

output "subnet_details" {{
  value = [for subnet in data.aws_subnet.details : {{
    name      = lookup(subnet.tags, "Name", "No Name")
    subnet_id = subnet.id
    vpc_id    = subnet.vpc_id
    cidr      = subnet.cidr_block
  }}]
}}

# 列出所有IAM用户
data "aws_iam_users" "all" {{
}}

# 获取每个IAM用户的详细信息
data "aws_iam_user" "details" {{
  for_each = toset(data.aws_iam_users.all.names)
  user_name = each.value
}}

output "iam_user_details" {{
  value = [for user in data.aws_iam_user.details : {{
    name = user.user_name
    id   = user.user_id
    arn  = user.arn
  }}]
}}
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