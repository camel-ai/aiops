import os
import json
import logging
import mysql.connector
from typing import Dict, Any, Optional, List
import subprocess
import tempfile
import pymysql
import time

class TerraformExecutor:
    """Terraform执行器，用于在E2B沙箱中执行Terraform命令"""
    
    def __init__(self, db_config: Dict[str, Any]):
        """初始化TerraformExecutor
        
        Args:
            db_config: 数据库配置信息
        """
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)
        
        # 设置工作目录
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.work_dir = os.path.join(backend_dir, "query")
        
        # 运行查询跟踪
        self._running_queries = set()
        
        # 确保工作目录存在
        os.makedirs(self.work_dir, exist_ok=True)
        self.logger.info(f"TerraformExecutor初始化完成，工作目录: {self.work_dir}")
    
    def _get_connection(self):
        """创建并返回数据库连接"""
        return mysql.connector.connect(**self.db_config)
    
    def create_sandbox(self, config_file_path: str, deploy_id: str) -> Dict[str, Any]:
        """创建E2B沙箱并执行Terraform命令
        
        Args:
            config_file_path: Terraform配置文件路径
            deploy_id: 部署ID
            
        Returns:
            执行结果
        """
        self.logger.info(f"为部署ID {deploy_id} 创建沙箱并执行Terraform")
        
        if not os.path.exists(config_file_path):
            self.logger.error(f"Terraform配置文件不存在: {config_file_path}")
            return {
                "success": False,
                "error": f"配置文件不存在: {config_file_path}",
                "results": {}
            }
        
        # 创建临时脚本文件
        with tempfile.NamedTemporaryFile(suffix='.sh', delete=False, mode='w') as script_file:
            script_path = script_file.name
            
            # 写入沙箱初始化和Terraform执行脚本
            script_file.write(f'''#!/bin/bash
# 设置错误处理
set -e

echo "创建并初始化沙箱环境..."
# 安装Terraform
echo "安装Terraform..."
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor > /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" > /etc/apt/sources.list.d/hashicorp.list
apt-get update && apt-get install -y terraform

# 创建工作目录
mkdir -p /tmp/terraform-{deploy_id}
cd /tmp/terraform-{deploy_id}

# 准备配置文件
cat > {deploy_id}.tf << 'EOF'
{open(config_file_path, 'r').read()}
EOF

# 初始化Terraform
echo "初始化Terraform..."
terraform init

# 执行Terraform计划
echo "执行Terraform计划..."
terraform plan -out=tfplan

# 应用Terraform配置
echo "应用Terraform配置..."
# 只输出状态，不实际创建资源
terraform show -json tfplan > output.json

echo "Terraform执行完成"
cat output.json
''')
        
        try:
            # 设置执行权限
            os.chmod(script_path, 0o755)
            
            # 执行沙箱命令（模拟）
            self.logger.info(f"执行沙箱脚本: {script_path}")
            
            # 对于实际场景，应该通过E2B API或其他方式在沙箱中执行
            # 此处为模拟实现
            process = subprocess.run(
                ['/bin/bash', script_path],
                capture_output=True,
                text=True
            )
            
            # 清理临时文件
            os.unlink(script_path)
            
            if process.returncode != 0:
                self.logger.error(f"沙箱执行失败: {process.stderr}")
                return {
                    "success": False,
                    "error": process.stderr,
                    "results": {}
                }
            
            # 解析结果（此处为模拟结果）
            results = self._generate_mock_results(deploy_id)
            
            # 保存结果到数据库
            self._save_results_to_db(deploy_id, results)
            
            return {
                "success": True,
                "output": process.stdout,
                "results": results
            }
            
        except Exception as e:
            self.logger.error(f"执行Terraform时出错: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "results": {}
            }
    
    def _generate_mock_results(self, deploy_id: str) -> Dict[str, Any]:
        """生成模拟的执行结果（用于演示）
        
        Args:
            deploy_id: 部署ID
            
        Returns:
            模拟的执行结果
        """
        # 从数据库获取部署信息
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute(
                "SELECT * FROM cloud WHERE deployid = %s ORDER BY id DESC LIMIT 1",
                (deploy_id,)
            )
            deploy_info = cursor.fetchone()
            
            if not deploy_info:
                return {}
                
            project = deploy_info.get('project', 'unknown')
            cloud = deploy_info.get('cloud', 'unknown')
            region = deploy_info.get('region', 'unknown')
            
            # 根据云提供商生成不同的结果
            if cloud.upper() == "AWS":
                return {
                    "vpc": f"vpc-{project}-{region}-{deploy_id[:6]}",
                    "vpcid": f"vpc-{deploy_id[:8]}",
                    "vpccidr": "10.0.0.0/16",
                    "subnet": f"subnet-{project}-{region}-{deploy_id[:6]}",
                    "subnetid": f"subnet-{deploy_id[:8]}",
                    "subnetvpc": f"vpc-{deploy_id[:8]}",
                    "subnetcidr": "10.0.1.0/24",
                    "object": f"s3://{project}-{region}-bucket-{deploy_id[:6]}",
                    "iam_user": f"{project}-user-{deploy_id[:6]}",
                    "iamid": f"AIDA{deploy_id[:16]}",
                    "iamarn": f"arn:aws:iam::123456789012:user/{project}-user-{deploy_id[:6]}",
                    "iam_user_group": f"{project}-group-{deploy_id[:6]}",
                    "iam_user_policy": f"{project}-policy-{deploy_id[:6]}"
                }
            elif "AZURE" in cloud.upper():
                return {
                    "vpc": f"{project}-vnet-{deploy_id[:6]}",
                    "vpcid": f"/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/{project}-rg/providers/Microsoft.Network/virtualNetworks/{project}-vnet",
                    "vpccidr": "10.0.0.0/16",
                    "subnet": f"{project}-subnet-{deploy_id[:6]}",
                    "subnetid": f"/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/{project}-rg/providers/Microsoft.Network/virtualNetworks/{project}-vnet/subnets/{project}-subnet",
                    "subnetvpc": f"/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/{project}-rg/providers/Microsoft.Network/virtualNetworks/{project}-vnet",
                    "subnetcidr": "10.0.1.0/24",
                    "object": f"{project}storage{deploy_id[:6]}",
                    "iam_user": f"{project}-user-{deploy_id[:6]}",
                    "iamid": f"{deploy_id[:8]}-{deploy_id[8:12]}-{deploy_id[12:16]}-{deploy_id[16:20]}",
                    "iamarn": f"/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/{project}-rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{project}-user-{deploy_id[:6]}",
                    "iam_user_group": f"{project}-group-{deploy_id[:6]}",
                    "iam_user_policy": f"{project}-policy-{deploy_id[:6]}"
                }
            elif "ALI" in cloud.upper():
                return {
                    "vpc": f"{project}-vpc-{deploy_id[:6]}",
                    "vpcid": f"vpc-{region}-{deploy_id[:8]}",
                    "vpccidr": "172.16.0.0/16",
                    "subnet": f"{project}-vswitch-{deploy_id[:6]}",
                    "subnetid": f"vsw-{region}-{deploy_id[:8]}",
                    "subnetvpc": f"vpc-{region}-{deploy_id[:8]}",
                    "subnetcidr": "172.16.0.0/24",
                    "object": f"{project}-{region}-bucket-{deploy_id[:6]}",
                    "iam_user": f"{project}-user-{deploy_id[:6]}",
                    "iamid": f"{deploy_id[:16]}",
                    "iamarn": f"acs:ram::123456789012:user/{project}-user-{deploy_id[:6]}",
                    "iam_user_group": f"{project}-group-{deploy_id[:6]}",
                    "iam_user_policy": f"{project}-policy-{deploy_id[:6]}"
                }
            else:
                return {
                    "vpc": f"{project}-vpc-{deploy_id[:6]}",
                    "vpcid": f"vpc-{deploy_id[:8]}",
                    "vpccidr": "192.168.0.0/16",
                    "subnet": f"{project}-subnet-{deploy_id[:6]}",
                    "subnetid": f"subnet-{deploy_id[:8]}",
                    "subnetvpc": f"vpc-{deploy_id[:8]}",
                    "subnetcidr": "192.168.1.0/24",
                    "object": f"{project}-storage-{deploy_id[:6]}",
                    "iam_user": f"{project}-user-{deploy_id[:6]}",
                    "iamid": f"ID-{deploy_id[:12]}",
                    "iamarn": f"arn:{cloud}:iam::123456789012:user/{project}-user-{deploy_id[:6]}",
                    "iam_user_group": f"{project}-group-{deploy_id[:6]}",
                    "iam_user_policy": f"{project}-policy-{deploy_id[:6]}"
                }
        except Exception as e:
            self.logger.error(f"生成模拟结果时出错: {str(e)}")
            return {}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _save_results_to_db(self, deploy_id: str, results: Dict[str, Any]) -> bool:
        """将结果保存到数据库
        
        Args:
            deploy_id: 部署ID
            results: 执行结果
            
        Returns:
            操作是否成功
        """
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 准备SQL语句（更新已存在的记录）
            sql = """
                UPDATE cloud SET 
                vpc = %s, vpcid = %s, vpccidr = %s, 
                subnet = %s, subnetid = %s, subnetvpc = %s, subnetcidr = %s,
                object = %s, iam_user = %s, iamid = %s, iamarn = %s,
                iam_user_group = %s, iam_user_policy = %s
                WHERE deployid = %s
            """
            
            # 准备参数
            params = (
                results.get('vpc', ''),
                results.get('vpcid', ''),
                results.get('vpccidr', ''),
                results.get('subnet', ''),
                results.get('subnetid', ''),
                results.get('subnetvpc', ''),
                results.get('subnetcidr', ''),
                results.get('object', ''),
                results.get('iam_user', ''),
                results.get('iamid', ''),
                results.get('iamarn', ''),
                results.get('iam_user_group', ''),
                results.get('iam_user_policy', ''),
                deploy_id
            )
            
            # 执行SQL
            self.logger.info(f"执行SQL: {sql}")
            # 记录时隐藏敏感信息
            safe_params = list(params)
            if len(safe_params) > 7 and safe_params[7]:  # SK位置
                safe_params[7] = '********'  # 隐藏SK
            self.logger.info(f"参数: {safe_params}")
            
            cursor.execute(sql, params)
            conn.commit()
            
            self.logger.info(f"成功更新部署ID {deploy_id} 的资源信息")
            return True
        except Exception as e:
            self.logger.error(f"更新资源信息到数据库失败: {str(e)}")
            if conn:
                conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def format_results_as_table(self, results, region_prefix=None):
        """
        将结果格式化为HTML表格（公共方法，提供向后兼容性）
        
        Args:
            results: 结果字典
            region_prefix: 区域前缀，用于多区域查询时标识资源所属区域
            
        Returns:
            HTML表格字符串
        """
        return self._format_results_as_table(results, region_prefix)
    
    def _format_results_as_table(self, results, region_prefix=None):
        """
        将结果格式化为HTML表格
        
        Args:
            results: 结果字典
            region_prefix: 区域前缀，用于多区域查询时标识资源所属区域
        """
        # 检查结果类型并相应处理
        if isinstance(results, dict):
            vpc_resources = results.get('vpc_resources', [])
            subnet_resources = results.get('subnet_resources', [])
            iam_resources = results.get('iam_resources', [])
            elb_resources = results.get('elb_resources', [])
            ec2_resources = results.get('ec2_resources', [])
            s3_resources = results.get('s3_resources', [])
            rds_resources = results.get('rds_resources', [])
            lambda_resources = results.get('lambda_resources', [])
            other_resources = results.get('other_resources', [])
            
            # 构建HTML表格
            table_html = '''
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>Resource</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
            '''
            
            # 添加区域前缀（如果提供）
            region_display = f" ({region_prefix})" if region_prefix else ""
            
            # 添加VPC资源
            if vpc_resources:
                table_html += f'<tr><td colspan=\'2\'><strong>VPC资源{region_display}（共{len(vpc_resources)}个）</strong></td></tr>'
                for i, vpc in enumerate(vpc_resources):
                    idx = i + 1
                    table_html += f'<tr><td>VPC {idx}</td><td>{vpc.get("vpc", "")}</td></tr>'
                    table_html += f'<tr><td>VPC {idx} ID</td><td>{vpc.get("vpcid", "")}</td></tr>'
                    table_html += f'<tr><td>VPC {idx} CIDR</td><td>{vpc.get("vpccidr", "")}</td></tr>'
            
            # 添加子网资源
            if subnet_resources:
                table_html += f'<tr><td colspan=\'2\'><strong>子网资源{region_display}（共{len(subnet_resources)}个）</strong></td></tr>'
                for i, subnet in enumerate(subnet_resources):
                    idx = i + 1
                    table_html += f'<tr><td>子网 {idx}</td><td>{subnet.get("subnet", "")}</td></tr>'
                    table_html += f'<tr><td>子网 {idx} ID</td><td>{subnet.get("subnetid", "")}</td></tr>'
                    table_html += f'<tr><td>子网 {idx} VPC</td><td>{subnet.get("subnetvpc", "")}</td></tr>'
                    table_html += f'<tr><td>子网 {idx} CIDR</td><td>{subnet.get("subnetcidr", "")}</td></tr>'
            
            # 添加IAM用户资源
            if iam_resources:
                # 如果是GLOBAL区域，特别标记
                global_suffix = " (全局资源)" if region_prefix == "GLOBAL" else ""
                table_html += f'<tr><td colspan=\'2\'><strong>IAM用户资源{global_suffix}{region_display}（共{len(iam_resources)}个）</strong></td></tr>'
                for i, user in enumerate(iam_resources):
                    idx = i + 1
                    table_html += f'<tr><td>IAM用户 {idx}</td><td>{user.get("iam_user", "")}</td></tr>'
                    table_html += f'<tr><td>IAM用户 {idx} ID</td><td>{user.get("iamid", "")}</td></tr>'
                    table_html += f'<tr><td>IAM用户 {idx} ARN</td><td>{user.get("iamarn", "")}</td></tr>'
            
            # 添加ELB资源
            if elb_resources:
                table_html += f'<tr><td colspan=\'2\'><strong>负载均衡器资源{region_display}（共{len(elb_resources)}个）</strong></td></tr>'
                for i, elb in enumerate(elb_resources):
                    idx = i + 1
                    table_html += f'<tr><td>ELB {idx} 名称</td><td>{elb.get("elb_name", "")}</td></tr>'
                    table_html += f'<tr><td>ELB {idx} ARN</td><td>{elb.get("elb_arn", "")}</td></tr>'
                    table_html += f'<tr><td>ELB {idx} 类型</td><td>{elb.get("elb_type", "")}</td></tr>'
            
            # 添加EC2资源
            if ec2_resources:
                table_html += f'<tr><td colspan=\'2\'><strong>EC2实例资源{region_display}（共{len(ec2_resources)}个）</strong></td></tr>'
                for i, instance in enumerate(ec2_resources):
                    idx = i + 1
                    table_html += f'<tr><td>EC2 {idx} 名称</td><td>{instance.get("ec2_name", "")}</td></tr>'
                    table_html += f'<tr><td>EC2 {idx} ID</td><td>{instance.get("ec2_id", "")}</td></tr>'
                    table_html += f'<tr><td>EC2 {idx} 类型</td><td>{instance.get("ec2_type", "")}</td></tr>'
                    table_html += f'<tr><td>EC2 {idx} 状态</td><td>{instance.get("ec2_state", "")}</td></tr>'
            
            # 添加S3资源
            if s3_resources:
                # 如果是GLOBAL区域，特别标记
                global_suffix = " (全局资源)" if region_prefix == "GLOBAL" else ""
                table_html += f'<tr><td colspan=\'2\'><strong>S3存储桶资源{global_suffix}{region_display}（共{len(s3_resources)}个）</strong></td></tr>'
                for i, bucket in enumerate(s3_resources):
                    idx = i + 1
                    # 检查是否是错误信息
                    if bucket.get('is_error'):
                        table_html += f'<tr><td colspan="2" style="color: red;"><strong>{bucket.get("s3_name", "")}</strong></td></tr>'
                        table_html += f'<tr><td>建议</td><td>{bucket.get("s3_region", "")}</td></tr>'
                    # 检查是否是说明信息
                    elif 'solutions' in bucket:
                        table_html += f'<tr><td>S3 查询说明</td><td>{bucket.get("s3_name", "")}</td></tr>'
                        table_html += f'<tr><td>推荐命令</td><td><code>{bucket.get("s3_region", "")}</code></td></tr>'
                        if bucket.get('note'):
                            table_html += f'<tr><td>注意事项</td><td>{bucket.get("note", "")}</td></tr>'
                        if bucket.get('solutions'):
                            solutions_html = '<ul>'
                            for solution in bucket.get('solutions', []):
                                solutions_html += f'<li>{solution}</li>'
                            solutions_html += '</ul>'
                            table_html += f'<tr><td>查询方案</td><td>{solutions_html}</td></tr>'
                    else:
                        # 正常的存储桶信息（从AWS CLI返回的真实数据）
                        table_html += f'<tr><td>S3 {idx} 名称</td><td><strong>{bucket.get("s3_name", "")}</strong></td></tr>'
                        table_html += f'<tr><td>S3 {idx} 区域</td><td>{bucket.get("s3_region", "")}</td></tr>'
                        if bucket.get('s3_creation_date'):
                            table_html += f'<tr><td>S3 {idx} 创建日期</td><td>{bucket.get("s3_creation_date", "")}</td></tr>'
            
            # 添加RDS资源
            if rds_resources:
                table_html += f'<tr><td colspan=\'2\'><strong>RDS数据库资源{region_display}（共{len(rds_resources)}个）</strong></td></tr>'
                for i, db in enumerate(rds_resources):
                    idx = i + 1
                    table_html += f'<tr><td>RDS {idx} 标识符</td><td>{db.get("rds_identifier", "")}</td></tr>'
                    table_html += f'<tr><td>RDS {idx} 引擎</td><td>{db.get("rds_engine", "")}</td></tr>'
                    table_html += f'<tr><td>RDS {idx} 引擎版本</td><td>{db.get("rds_engine_version", "")}</td></tr>'
                    table_html += f'<tr><td>RDS {idx} 实例类</td><td>{db.get("rds_instance_class", "")}</td></tr>'
                    table_html += f'<tr><td>RDS {idx} 端点</td><td>{db.get("rds_endpoint", "")}</td></tr>'
                    table_html += f'<tr><td>RDS {idx} 端口</td><td>{db.get("rds_port", "")}</td></tr>'
                    table_html += f'<tr><td>RDS {idx} 多区域</td><td>{db.get("rds_multi_az", "")}</td></tr>'
            
            # 添加Lambda资源
            if lambda_resources:
                table_html += f'<tr><td colspan=\'2\'><strong>Lambda函数资源{region_display}（共{len(lambda_resources)}个）</strong></td></tr>'
                for i, func in enumerate(lambda_resources):
                    idx = i + 1
                    table_html += f'<tr><td>Lambda {idx} 名称</td><td>{func.get("lambda_name", "")}</td></tr>'
            
            # 添加其他资源
            if other_resources:
                table_html += f'<tr><td colspan=\'2\'><strong>其他资源{region_display}（共{len(other_resources)}个）</strong></td></tr>'
                for i, resource in enumerate(other_resources):
                    idx = i + 1
                    resource_type = resource.get("resource_type", "Unknown")
                    resource_name = resource.get("resource_name", "")
                    table_html += f'<tr><td>{resource_type.upper()} {idx}</td><td>{resource_name}</td></tr>'
            
            table_html += '''
            </tbody>
        </table>
            '''
            
            return table_html
        
        # 兼容旧格式
        else:
            table_html = '''
        <table class="table table-bordered">
            <thead>
                <tr>
                    <th>Resource</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
            '''
            
            for key, value in results.items():
                table_html += f'<tr><td>{key}</td><td>{value}</td></tr>'
            
            table_html += '''
            </tbody>
        </table>
            '''
            
            return table_html
            
    def save_terraform_result(self, user_id, project, cloud, region, deploy_id, results):
        """
        保存Terraform结果到数据库，仅更新VPC、子网和IAM用户相关字段
        """
        # 连接数据库
        connection = None
        cursor = None
        try:
            # 使用self.db_config
            connection = pymysql.connect(
                **self.db_config,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = connection.cursor()
            
            # 首先检查记录是否存在
            check_sql = "SELECT id FROM cloud WHERE deployid = %s LIMIT 1"
            cursor.execute(check_sql, (deploy_id,))
            exists = cursor.fetchone()
            
            if not exists:
                self.logger.warning(f"未找到部署ID为 {deploy_id} 的记录，无法更新")
                return False
            
            # 使用UPDATE语法，更新所有资源字段
            sql = """
                UPDATE cloud SET 
                vpc = %s, vpcid = %s, vpccidr = %s, 
                subnet = %s, subnetid = %s, subnetvpc = %s, subnetcidr = %s,
                iam_user = %s, iamid = %s, iamarn = %s,
                elb_name = %s, elb_arn = %s, elb_type = %s,
                ec2_name = %s, ec2_id = %s, ec2_type = %s, ec2_state = %s,
                s3_name = %s, s3_region = %s,
                rds_identifier = %s, rds_engine = %s, rds_status = %s,
                lambda_name = %s,
                updated_at = NOW()
                WHERE deployid = %s
            """
            
            # 从results中获取第一个资源的信息（保持向后兼容）
            vpc_resources = results.get('vpc_resources', [])
            subnet_resources = results.get('subnet_resources', [])
            iam_resources = results.get('iam_resources', [])
            elb_resources = results.get('elb_resources', [])
            ec2_resources = results.get('ec2_resources', [])
            s3_resources = results.get('s3_resources', [])
            rds_resources = results.get('rds_resources', [])
            lambda_resources = results.get('lambda_resources', [])
            
            # 准备参数
            params = (
                # VPC资源
                vpc_resources[0].get('vpc', '') if vpc_resources else results.get('vpc', ''),
                vpc_resources[0].get('vpcid', '') if vpc_resources else results.get('vpcid', ''),
                vpc_resources[0].get('vpccidr', '') if vpc_resources else results.get('vpccidr', ''),
                # 子网资源
                subnet_resources[0].get('subnet', '') if subnet_resources else results.get('subnet', ''),
                subnet_resources[0].get('subnetid', '') if subnet_resources else results.get('subnetid', ''),
                subnet_resources[0].get('subnetvpc', '') if subnet_resources else results.get('subnetvpc', ''),
                subnet_resources[0].get('subnetcidr', '') if subnet_resources else results.get('subnetcidr', ''),
                # IAM资源
                iam_resources[0].get('iam_user', '') if iam_resources else results.get('iam_user', ''),
                iam_resources[0].get('iamid', '') if iam_resources else results.get('iamid', ''),
                iam_resources[0].get('iamarn', '') if iam_resources else results.get('iamarn', ''),
                # ELB资源
                elb_resources[0].get('elb_name', '') if elb_resources else '',
                elb_resources[0].get('elb_arn', '') if elb_resources else '',
                elb_resources[0].get('elb_type', '') if elb_resources else '',
                # EC2资源
                ec2_resources[0].get('ec2_name', '') if ec2_resources else '',
                ec2_resources[0].get('ec2_id', '') if ec2_resources else '',
                ec2_resources[0].get('ec2_type', '') if ec2_resources else '',
                ec2_resources[0].get('ec2_state', '') if ec2_resources else '',
                # S3资源
                s3_resources[0].get('s3_name', '') if s3_resources else '',
                s3_resources[0].get('s3_region', '') if s3_resources else '',
                # RDS资源
                rds_resources[0].get('rds_identifier', '') if rds_resources else '',
                rds_resources[0].get('rds_engine', '') if rds_resources else '',
                rds_resources[0].get('rds_status', '') if rds_resources else '',
                # Lambda资源
                lambda_resources[0].get('lambda_name', '') if lambda_resources else '',
                # WHERE条件
                deploy_id
            )
            
            # 执行SQL
            self.logger.info(f"执行SQL: {sql}")
            self.logger.info(f"参数: {params}")
            
            cursor.execute(sql, params)
            affected_rows = cursor.rowcount
            connection.commit()
            
            if affected_rows > 0:
                self.logger.info(f"成功更新部署ID {deploy_id} 的资源信息")
                return True
            else:
                self.logger.warning(f"未能更新部署ID {deploy_id} 的资源信息，可能部署ID不存在")
                return False
        except Exception as e:
            self.logger.error(f"更新资源信息到数据库失败: {str(e)}")
            if connection:
                connection.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def run_terraform(self, uid, project, cloud, region, terraform_content, deploy_id, ak=None, sk=None, skip_save=False):
        """
        运行Terraform命令
        """
        # 检查是否已经在运行
        if deploy_id in self._running_queries:
            self.logger.warning(f"部署ID {deploy_id} 已在运行中，跳过重复执行")
            return {"success": False, "message": "查询已在运行中"}
            
        # 添加到运行集合
        self._running_queries.add(deploy_id)
        
        try:
            # 创建工作目录
            work_dir = os.path.join(self.work_dir, deploy_id)
            os.makedirs(work_dir, exist_ok=True)
            
            # 生成Terraform配置文件
            config_file = os.path.join(work_dir, 'main.tf')
            
            self.logger.info(f"📁 创建工作目录: {work_dir}")
            self.logger.info(f"📄 生成配置文件: {config_file}")
            self.logger.info(f"📝 配置内容长度: {len(terraform_content)} 字符")
            
            # 写入配置文件
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(terraform_content)
            
            # 记录生成的配置文件的关键信息
            self.logger.info("🔍 检查生成的配置文件关键组件:")
            
            # 检查Provider配置
            if 'provider "aws"' in terraform_content:
                self.logger.info("✅ 找到AWS Provider配置")
            else:
                self.logger.warning("❌ 未找到AWS Provider配置")
                
            # 检查S3配置
            if 'data "external" "s3_buckets"' in terraform_content:
                self.logger.info("✅ 找到S3外部数据源配置")
                # 记录S3配置的program部分
                if 'powershell' in terraform_content:
                    self.logger.info("✅ 使用PowerShell执行S3查询")
                elif 'bash' in terraform_content:
                    self.logger.info("✅ 使用Bash执行S3查询")
            else:
                self.logger.info("ℹ️ 未包含S3配置")
                
            # 检查RDS配置
            if 'data "aws_db_instances"' in terraform_content:
                self.logger.info("✅ 找到RDS配置")
            else:
                self.logger.info("ℹ️ 未包含RDS配置")
            
            # 记录配置文件前几行和后几行
            lines = terraform_content.split('\n')
            self.logger.info(f"📋 配置文件共 {len(lines)} 行")
            self.logger.info("📋 配置文件开头10行:")
            for i, line in enumerate(lines[:10]):
                self.logger.info(f"  {i+1:2d}: {line}")
                
            # 如果有S3配置，显示S3相关行
            if 'data "external" "s3_buckets"' in terraform_content:
                self.logger.info("📋 S3配置相关行:")
                for i, line in enumerate(lines):
                    if 'external' in line or 's3_buckets' in line or 'powershell' in line:
                        self.logger.info(f"  {i+1:3d}: {line}")
            
            # 检查文件是否成功写入
            if os.path.exists(config_file):
                file_size = os.path.getsize(config_file)
                self.logger.info(f"✅ 配置文件写入成功，大小: {file_size} 字节")
                
                # 读取并验证文件内容
                with open(config_file, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                    
                if len(file_content) == len(terraform_content):
                    self.logger.info("✅ 文件内容完整")
                else:
                    self.logger.warning(f"⚠️ 文件内容长度不匹配: 期望{len(terraform_content)}, 实际{len(file_content)}")
            else:
                self.logger.error("❌ 配置文件写入失败")
                return {"success": False, "message": "配置文件写入失败"}
            
            # 设置环境变量
            env = os.environ.copy()
            if ak and sk:
                env['AWS_ACCESS_KEY_ID'] = ak
                env['AWS_SECRET_ACCESS_KEY'] = sk
                env['AWS_DEFAULT_REGION'] = region
                self.logger.info(f"🔑 设置AWS凭证环境变量 (AK: {ak[:8]}...)")
            
            # 执行terraform init
            self.logger.info("🚀 执行terraform init")
            self.logger.info(f"📂 工作目录: {work_dir}")
            
            init_start_time = time.time()
            init_process = subprocess.run(
                ['terraform', 'init'], 
                cwd=work_dir, 
                env=env,
                capture_output=True, 
                text=True, 
                timeout=120
            )
            init_duration = time.time() - init_start_time
            
            self.logger.info(f"⏱️ terraform init 执行时间: {init_duration:.2f}秒")
            self.logger.info(f"🔢 terraform init 退出码: {init_process.returncode}")
            
            # 详细记录init输出
            if init_process.stdout:
                self.logger.info("📤 terraform init 标准输出:")
                for line in init_process.stdout.split('\n'):
                    if line.strip():
                        self.logger.info(f"  STDOUT: {line}")
                        
            if init_process.stderr:
                self.logger.error("📤 terraform init 错误输出:")
                for line in init_process.stderr.split('\n'):
                    if line.strip():
                        self.logger.error(f"  STDERR: {line}")
            
            if init_process.returncode != 0:
                self.logger.error(f"❌ terraform init 失败，退出码: {init_process.returncode}")
                
                # 检查具体错误
                error_output = init_process.stderr or init_process.stdout or "无错误输出"
                
                # 分析常见错误
                if "syntax" in error_output.lower():
                    self.logger.error("🔍 检测到语法错误")
                elif "provider" in error_output.lower():
                    self.logger.error("🔍 检测到Provider相关错误")
                elif "external" in error_output.lower():
                    self.logger.error("🔍 检测到外部数据源相关错误")
                elif "invalid" in error_output.lower():
                    self.logger.error("🔍 检测到无效配置")
                    
                # 检查工作目录中的文件
                self.logger.info("📁 检查工作目录文件:")
                try:
                    for file in os.listdir(work_dir):
                        file_path = os.path.join(work_dir, file)
                        if os.path.isfile(file_path):
                            size = os.path.getsize(file_path)
                            self.logger.info(f"  📄 {file}: {size} 字节")
                except Exception as e:
                    self.logger.error(f"❌ 无法列出工作目录文件: {e}")
                
                return {
                    "success": False, 
                    "message": f"执行Terraform时发生错误: Command '['terraform', 'init']' returned non-zero exit status {init_process.returncode}.",
                    "error_detail": error_output,
                    "stderr": init_process.stderr,
                    "stdout": init_process.stdout
                }
            
            self.logger.info("✅ terraform init 成功完成")
            
            # 执行terraform apply
            self.logger.info("🚀 执行terraform apply")
            
            apply_start_time = time.time()
            apply_process = subprocess.run(
                ['terraform', 'apply', '-auto-approve'], 
                cwd=work_dir, 
                env=env,
                capture_output=True, 
                text=True, 
                timeout=300
            )
            apply_duration = time.time() - apply_start_time
            
            self.logger.info(f"⏱️ terraform apply 执行时间: {apply_duration:.2f}秒")
            self.logger.info(f"🔢 terraform apply 退出码: {apply_process.returncode}")
            
            # 详细记录apply输出
            if apply_process.stdout:
                self.logger.info("📤 terraform apply 标准输出:")
                for line in apply_process.stdout.split('\n'):
                    if line.strip():
                        self.logger.info(f"  STDOUT: {line}")
                        
            if apply_process.stderr:
                self.logger.error("📤 terraform apply 错误输出:")
                for line in apply_process.stderr.split('\n'):
                    if line.strip():
                        self.logger.error(f"  STDERR: {line}")
            
            if apply_process.returncode != 0:
                self.logger.error(f"❌ terraform apply 失败，退出码: {apply_process.returncode}")
                return {
                    "success": False, 
                    "message": f"Terraform apply失败: {apply_process.stderr or apply_process.stdout}",
                    "error_detail": apply_process.stderr or apply_process.stdout,
                    "stderr": apply_process.stderr,
                    "stdout": apply_process.stdout
                }
            
            self.logger.info("✅ terraform apply 成功完成")
            
            # 获取输出
            self.logger.info("🚀 执行terraform output")
            
            output_start_time = time.time()
            output_process = subprocess.run(
                ['terraform', 'output', '-json'], 
                cwd=work_dir, 
                env=env,
                capture_output=True, 
                text=True, 
                timeout=60
            )
            output_duration = time.time() - output_start_time
            
            self.logger.info(f"⏱️ terraform output 执行时间: {output_duration:.2f}秒")
            self.logger.info(f"🔢 terraform output 退出码: {output_process.returncode}")
            
            if output_process.returncode != 0:
                self.logger.error(f"❌ terraform output 失败: {output_process.stderr}")
                return {
                    "success": False, 
                    "message": f"Terraform output失败: {output_process.stderr}",
                    "error_detail": output_process.stderr
                }
            
            # 解析输出结果
            try:
                output_json = json.loads(output_process.stdout)
                self.logger.info("✅ 成功解析terraform output JSON")
                self.logger.info(f"📊 输出结果包含 {len(output_json)} 个输出项")
                
                # 记录每个输出项的基本信息
                for key, value in output_json.items():
                    if isinstance(value, dict) and 'value' in value:
                        value_content = value['value']
                        if isinstance(value_content, list):
                            self.logger.info(f"  📋 {key}: {len(value_content)} 个项目")
                        else:
                            self.logger.info(f"  📋 {key}: {type(value_content).__name__}")
                    else:
                        self.logger.info(f"  📋 {key}: {type(value).__name__}")
                        
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ JSON解析失败: {e}")
                self.logger.error(f"📤 原始输出: {output_process.stdout}")
                return {
                    "success": False, 
                    "message": f"JSON解析失败: {e}",
                    "raw_output": output_process.stdout
                }
            
            # 解析terraform输出为标准格式
            parsed_results = self._parse_terraform_outputs(output_json)
            self.logger.info(f"📋 解析后的结果包含: {list(parsed_results.keys())}")
            
            # 保存结果到数据库（如果不跳过）
            if not skip_save:
                self.logger.info("💾 保存结果到数据库")
                save_success = self.save_terraform_result(uid, project, cloud, region, deploy_id, parsed_results)
                
                if save_success:
                    self.logger.info("✅ 结果保存成功")
                else:
                    self.logger.error("❌ 结果保存失败")
            else:
                self.logger.info("⏭️ 跳过保存到数据库（多区域查询模式）")
            
            total_duration = time.time() - init_start_time
            self.logger.info(f"🎯 总执行时间: {total_duration:.2f}秒")
            
            # 返回原始输出结构供前端使用
            return {
                "success": True, 
                "message": "Terraform执行成功",
                "results": output_json,  # 返回原始输出用于前端显示
                "duration": total_duration
            }
            
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"❌ Terraform执行超时: {e}")
            return {"success": False, "message": f"Terraform执行超时: {e}"}
        except Exception as e:
            self.logger.error(f"❌ 执行Terraform时发生错误: {e}")
            import traceback
            self.logger.error(f"❌ 详细错误信息: {traceback.format_exc()}")
            return {"success": False, "message": f"执行Terraform时发生错误: {e}"}
        finally:
            # 从运行集合中移除
            self._running_queries.discard(deploy_id) 

    def _parse_terraform_outputs(self, output_json):
        """
        解析terraform输出为标准格式
        
        Args:
            output_json: terraform output -json的原始输出
            
        Returns:
            dict: 解析后的结果，包含所有资源类型
        """
        results = {
            'vpc_resources': [],
            'subnet_resources': [],
            'iam_resources': [],
            'elb_resources': [],
            'ec2_resources': [],
            's3_resources': [],
            'rds_resources': [],
            'lambda_resources': []
        }
        
        try:
            # 解析VPC资源
            if 'vpc_details' in output_json:
                vpc_data = output_json['vpc_details'].get('value', [])
                if isinstance(vpc_data, list):
                    for vpc in vpc_data:
                        if isinstance(vpc, dict):
                            results['vpc_resources'].append({
                                'vpc': vpc.get('name', ''),
                                'vpcid': vpc.get('vpc_id', ''),
                                'vpccidr': vpc.get('cidr', '')
                            })
                self.logger.info(f"解析VPC资源: {len(results['vpc_resources'])} 个")
            
            # 解析子网资源
            if 'subnet_details' in output_json:
                subnet_data = output_json['subnet_details'].get('value', [])
                if isinstance(subnet_data, list):
                    for subnet in subnet_data:
                        if isinstance(subnet, dict):
                            results['subnet_resources'].append({
                                'subnet': subnet.get('name', ''),
                                'subnetid': subnet.get('subnet_id', ''),
                                'subnetvpc': subnet.get('vpc_id', ''),
                                'subnetcidr': subnet.get('cidr', '')
                            })
                self.logger.info(f"解析子网资源: {len(results['subnet_resources'])} 个")
            
            # 解析IAM用户资源
            if 'iam_user_details' in output_json:
                iam_data = output_json['iam_user_details'].get('value', [])
                if isinstance(iam_data, list):
                    for user in iam_data:
                        if isinstance(user, dict):
                            results['iam_resources'].append({
                                'iam_user': user.get('name', ''),
                                'iamid': user.get('id', ''),
                                'iamarn': user.get('arn', '')
                            })
                self.logger.info(f"解析IAM用户资源: {len(results['iam_resources'])} 个")
            
            # 解析EC2实例资源
            if 'ec2_details' in output_json:
                ec2_data = output_json['ec2_details'].get('value', [])
                if isinstance(ec2_data, list):
                    for instance in ec2_data:
                        if isinstance(instance, dict):
                            results['ec2_resources'].append({
                                'ec2_name': instance.get('name', ''),
                                'ec2_id': instance.get('instance_id', ''),
                                'ec2_type': instance.get('instance_type', ''),
                                'ec2_state': instance.get('state', '')
                            })
                self.logger.info(f"解析EC2实例资源: {len(results['ec2_resources'])} 个")
            
            # 解析ELB资源
            if 'elb_details' in output_json:
                elb_data = output_json['elb_details'].get('value', [])
                if isinstance(elb_data, list):
                    for elb in elb_data:
                        if isinstance(elb, dict):
                            results['elb_resources'].append({
                                'elb_name': elb.get('name', ''),
                                'elb_arn': elb.get('arn', ''),
                                'elb_type': elb.get('load_balancer_type', '')
                            })
                self.logger.info(f"解析ELB资源: {len(results['elb_resources'])} 个")
            
            # 解析S3存储桶资源
            if 's3_details' in output_json:
                s3_data = output_json['s3_details'].get('value', [])
                if isinstance(s3_data, list):
                    for bucket in s3_data:
                        if isinstance(bucket, dict):
                            # 检查是否是错误信息
                            if bucket.get('error'):
                                results['s3_resources'].append({
                                    's3_name': bucket.get('error', ''),
                                    's3_region': bucket.get('message', ''),
                                    'is_error': True
                                })
                            else:
                                results['s3_resources'].append({
                                    's3_name': bucket.get('name', ''),
                                    's3_region': bucket.get('region', 'unknown'),
                                    's3_creation_date': bucket.get('creation_date', '')
                                })
                self.logger.info(f"解析S3存储桶资源: {len(results['s3_resources'])} 个")
            
            # 解析RDS资源
            if 'rds_details' in output_json:
                rds_data = output_json['rds_details'].get('value', [])
                if isinstance(rds_data, list):
                    for db in rds_data:
                        if isinstance(db, dict):
                            results['rds_resources'].append({
                                'rds_identifier': db.get('identifier', ''),
                                'rds_engine': db.get('engine', ''),
                                'rds_engine_version': db.get('engine_version', ''),
                                'rds_instance_class': db.get('instance_class', ''),
                                'rds_endpoint': db.get('endpoint', ''),
                                'rds_port': db.get('port', ''),
                                'rds_multi_az': str(db.get('multi_az', False))
                            })
                self.logger.info(f"解析RDS资源: {len(results['rds_resources'])} 个")
            
            # 解析Lambda函数资源
            if 'lambda_details' in output_json:
                lambda_data = output_json['lambda_details'].get('value', [])
                if isinstance(lambda_data, list):
                    for func in lambda_data:
                        if isinstance(func, dict):
                            results['lambda_resources'].append({
                                'lambda_name': func.get('name', '')
                            })
                self.logger.info(f"解析Lambda函数资源: {len(results['lambda_resources'])} 个")
            
            # 为了向后兼容，也提供旧格式的字段
            if results['vpc_resources']:
                first_vpc = results['vpc_resources'][0]
                results.update({
                    'vpc': first_vpc.get('vpc', ''),
                    'vpcid': first_vpc.get('vpcid', ''),
                    'vpccidr': first_vpc.get('vpccidr', '')
                })
            
            if results['subnet_resources']:
                first_subnet = results['subnet_resources'][0]
                results.update({
                    'subnet': first_subnet.get('subnet', ''),
                    'subnetid': first_subnet.get('subnetid', ''),
                    'subnetvpc': first_subnet.get('subnetvpc', ''),
                    'subnetcidr': first_subnet.get('subnetcidr', '')
                })
            
            if results['iam_resources']:
                first_iam = results['iam_resources'][0]
                results.update({
                    'iam_user': first_iam.get('iam_user', ''),
                    'iamid': first_iam.get('iamid', ''),
                    'iamarn': first_iam.get('iamarn', '')
                })
                
        except Exception as e:
            self.logger.error(f"解析terraform输出时发生错误: {e}")
        
        return results 