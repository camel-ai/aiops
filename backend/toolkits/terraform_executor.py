import os
import json
import logging
import mysql.connector
from typing import Dict, Any, Optional, List
import subprocess
import tempfile
import pymysql

class TerraformExecutor:
    """Terraform执行器，用于在E2B沙箱中执行Terraform命令"""
    
    def __init__(self, db_config: Dict[str, Any]):
        """初始化TerraformExecutor
        
        Args:
            db_config: 数据库配置信息
        """
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)
    
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
    
    def _format_results_as_table(self, results):
        """
        将结果格式化为HTML表格
        """
        # 检查结果类型并相应处理
        if isinstance(results, dict):
            vpc_resources = results.get('vpc_resources', [])
            subnet_resources = results.get('subnet_resources', [])
            iam_resources = results.get('iam_resources', [])
            
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
            
            # 添加VPC资源
            if vpc_resources:
                table_html += f'<tr><td colspan=\'2\'><strong>VPC资源（共{len(vpc_resources)}个）</strong></td></tr>'
                for i, vpc in enumerate(vpc_resources):
                    idx = i + 1
                    table_html += f'<tr><td>VPC {idx}</td><td>{vpc.get("vpc", "")}</td></tr>'
                    table_html += f'<tr><td>VPC {idx} ID</td><td>{vpc.get("vpcid", "")}</td></tr>'
                    table_html += f'<tr><td>VPC {idx} CIDR</td><td>{vpc.get("vpccidr", "")}</td></tr>'
            
            # 添加子网资源
            if subnet_resources:
                table_html += f'<tr><td colspan=\'2\'><strong>子网资源（共{len(subnet_resources)}个）</strong></td></tr>'
                for i, subnet in enumerate(subnet_resources):
                    idx = i + 1
                    table_html += f'<tr><td>子网 {idx}</td><td>{subnet.get("subnet", "")}</td></tr>'
                    table_html += f'<tr><td>子网 {idx} ID</td><td>{subnet.get("subnetid", "")}</td></tr>'
                    table_html += f'<tr><td>子网 {idx} VPC</td><td>{subnet.get("subnetvpc", "")}</td></tr>'
                    table_html += f'<tr><td>子网 {idx} CIDR</td><td>{subnet.get("subnetcidr", "")}</td></tr>'
            
            # 添加IAM用户资源
            if iam_resources:
                table_html += f'<tr><td colspan=\'2\'><strong>IAM用户资源（共{len(iam_resources)}个）</strong></td></tr>'
                for i, user in enumerate(iam_resources):
                    idx = i + 1
                    table_html += f'<tr><td>IAM用户 {idx}</td><td>{user.get("iam_user", "")}</td></tr>'
                    table_html += f'<tr><td>IAM用户 {idx} ID</td><td>{user.get("iamid", "")}</td></tr>'
                    table_html += f'<tr><td>IAM用户 {idx} ARN</td><td>{user.get("iamarn", "")}</td></tr>'
            
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
            
    # 提供向后兼容的公共方法
    def format_results_as_table(self, results):
        """
        将结果格式化为HTML表格（公共方法，提供向后兼容性）
        
        Args:
            results: 结果字典
            
        Returns:
            HTML表格字符串
        """
        return self._format_results_as_table(results)

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
            
            # 使用UPDATE语法，仅更新必要字段
            sql = """
                UPDATE cloud SET 
                vpc = %s, vpcid = %s, vpccidr = %s, 
                subnet = %s, subnetid = %s, subnetvpc = %s, subnetcidr = %s,
                iam_user = %s, iamid = %s, iamarn = %s,
                updated_at = NOW()
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
                results.get('iam_user', ''),
                results.get('iamid', ''),
                results.get('iamarn', ''),
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

    def run_terraform(self, uid, project, cloud, region, terraform_content, deploy_id, ak=None, sk=None):
        """
        运行Terraform并将结果保存到数据库
        """
        self.logger.info(f"开始执行Terraform查询操作，部署ID: {deploy_id}")
        
        # 获取backend目录路径
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # 创建query/{deploy_id}目录
        query_dir = os.path.join(backend_dir, "query")
        deploy_dir = os.path.join(query_dir, deploy_id)
        os.makedirs(deploy_dir, exist_ok=True)
        
        # 保存配置文件
        config_file = os.path.join(deploy_dir, 'main.tf')
        with open(config_file, 'w') as f:
            f.write(terraform_content)
        
        # 初始化和应用Terraform
        try:
            # 切换工作目录到查询ID对应的子目录
            original_dir = os.getcwd()
            os.chdir(deploy_dir)
            
            # 执行terraform命令
            self.logger.info(f"执行terraform init")
            subprocess.run(['terraform', 'init'], check=True, capture_output=True)
            
            self.logger.info(f"执行terraform apply")
            apply_result = subprocess.run(['terraform', 'apply', '-auto-approve'], 
                                capture_output=True, text=True)
            
            # 检查是否成功
            if apply_result.returncode != 0:
                self.logger.error(f"Terraform apply失败: {apply_result.stderr}")
                # 恢复工作目录
                os.chdir(original_dir)
                return {
                    'success': False,
                    'error': f"执行Terraform失败: {apply_result.stderr}"
                }
            
            # 输出结果
            self.logger.info(f"执行terraform output -json")
            output_result = subprocess.run(['terraform', 'output', '-json'], 
                                capture_output=True, text=True)
            
            # 恢复工作目录
            os.chdir(original_dir)
            
            if output_result.returncode != 0:
                self.logger.error(f"Terraform output获取失败: {output_result.stderr}")
                return {
                    'success': False,
                    'error': f"获取Terraform输出失败: {output_result.stderr}"
                }
            
            # 解析输出
            output_json = json.loads(output_result.stdout)
            self.logger.debug(f"Terraform原始输出: {json.dumps(output_json, indent=2)}")
            
            # 处理输出数据
            vpc_resources = []
            subnet_resources = []
            iam_resources = []
            
            # 处理VPC信息
            if 'vpc_details' in output_json:
                vpcs = output_json['vpc_details']['value']
                for i, vpc in enumerate(vpcs):
                    vpc_resources.append({
                        'vpc': vpc.get('name', 'Unknown'),
                        'vpcid': vpc.get('vpc_id', ''),
                        'vpccidr': vpc.get('cidr', ''),
                        'resource_type': 'vpc',
                        'resource_index': i
                    })
            
            # 处理子网信息
            if 'subnet_details' in output_json:
                subnets = output_json['subnet_details']['value']
                for i, subnet in enumerate(subnets):
                    subnet_resources.append({
                        'subnet': subnet.get('name', 'Unknown'),
                        'subnetid': subnet.get('subnet_id', ''),
                        'subnetvpc': subnet.get('vpc_id', ''),
                        'subnetcidr': subnet.get('cidr', ''),
                        'resource_type': 'subnet',
                        'resource_index': i
                    })
            
            # 处理IAM用户信息
            if 'iam_user_details' in output_json:
                users = output_json['iam_user_details']['value']
                for i, user in enumerate(users):
                    iam_resources.append({
                        'iam_user': user.get('name', 'Unknown'),
                        'iamid': user.get('id', ''),
                        'iamarn': user.get('arn', ''),
                        'resource_type': 'iam',
                        'resource_index': i
                    })
            
            # 创建一个包含所有资源的列表
            all_resources = []
            all_resources.extend(vpc_resources)
            all_resources.extend(subnet_resources)
            all_resources.extend(iam_resources)
            
            # 记录找到的资源数量
            self.logger.info(f"找到 {len(iam_resources)} 个IAM用户")
            self.logger.info(f"找到 {len(vpc_resources)} 个VPC")
            self.logger.info(f"找到 {len(subnet_resources)} 个子网")
            self.logger.info(f"总共找到 {len(all_resources)} 个资源需要保存")
            
            # 添加或更新这一部署ID的所有资源记录
            connection = None
            cursor = None
            try:
                # 建立数据库连接
                connection = pymysql.connect(
                    **self.db_config,
                    charset='utf8mb4',
                    cursorclass=pymysql.cursors.DictCursor
                )
                cursor = connection.cursor()
                
                # 先从数据库中删除此部署ID的所有现有记录
                delete_sql = "DELETE FROM cloud WHERE deployid = %s"
                cursor.execute(delete_sql, (deploy_id,))
                deleted_count = cursor.rowcount
                self.logger.info(f"已删除部署ID {deploy_id} 的 {deleted_count} 条现有记录")
                
                # 为每个资源创建新记录
                for i, resource in enumerate(all_resources):
                    # 准备插入SQL
                    insert_sql = """
                        INSERT INTO cloud (
                            user_id, username, project, cloud, region, deployid, 
                            ak, sk,
                            vpc, vpcid, vpccidr, 
                            subnet, subnetid, subnetvpc, subnetcidr,
                            iam_user, iamid, iamarn,
                            resource_type, resource_index,
                            created_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, 
                            %s, %s,
                            %s, %s, %s, 
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            NOW(), NOW()
                        )
                    """
                    
                    # 第一步：准备所有可能的参数默认值
                    params = [
                        uid,     # user_id - 使用传入的uid参数
                        '',      # username (将在后面获取)
                        project, # project
                        cloud,   # cloud
                        region,  # region
                        deploy_id, # deployid
                        ak or 'placeholder',  # ak - 使用传入的ak或默认值
                        sk or 'placeholder',  # sk - 使用传入的sk或默认值
                        '',      # vpc
                        '',      # vpcid
                        '',      # vpccidr
                        '',      # subnet
                        '',      # subnetid
                        '',      # subnetvpc
                        '',      # subnetcidr
                        '',      # iam_user
                        '',      # iamid
                        '',      # iamarn
                        resource.get('resource_type', ''), # resource_type
                        resource.get('resource_index', i), # resource_index
                    ]
                    
                    # 第二步：获取用户名
                    try:
                        username_query = "SELECT username FROM users WHERE id = %s"
                        cursor.execute(username_query, (uid,))  # 使用传入的uid参数
                        user_result = cursor.fetchone()
                        if user_result and 'username' in user_result:
                            params[1] = user_result['username']
                            self.logger.info(f"资源 {i+1}/{len(all_resources)}: 找到用户名 {params[1]}")
                        else:
                            self.logger.warning(f"资源 {i+1}/{len(all_resources)}: 未找到用户ID {uid} 的用户名")  # 使用传入的uid参数
                    except Exception as e:
                        self.logger.error(f"资源 {i+1}/{len(all_resources)}: 获取用户名出错: {str(e)}")
                    
                    # 第三步：根据资源类型更新特定字段
                    if resource.get('resource_type') == 'vpc':
                        params[8] = resource.get('vpc', '')  # vpc
                        params[9] = resource.get('vpcid', '')  # vpcid
                        params[10] = resource.get('vpccidr', '')  # vpccidr
                    elif resource.get('resource_type') == 'subnet':
                        params[11] = resource.get('subnet', '')  # subnet
                        params[12] = resource.get('subnetid', '')  # subnetid
                        params[13] = resource.get('subnetvpc', '')  # subnetvpc
                        params[14] = resource.get('subnetcidr', '')  # subnetcidr
                    elif resource.get('resource_type') == 'iam':
                        params[15] = resource.get('iam_user', '')  # iam_user
                        params[16] = resource.get('iamid', '')  # iamid
                        params[17] = resource.get('iamarn', '')  # iamarn
                    
                    # 执行插入
                    self.logger.info(f"插入资源 {i+1}/{len(all_resources)}: {resource.get('resource_type')} #{resource.get('resource_index')}")
                    cursor.execute(insert_sql, params)
                
                # 提交事务
                connection.commit()
                self.logger.info(f"成功保存 {len(all_resources)} 个资源到数据库")
                
                # 关闭游标和连接
                cursor.close()
                connection.close()
            except Exception as e:
                self.logger.error(f"保存资源到数据库失败: {str(e)}")
                if connection:
                    try:
                        connection.rollback()
                    except:
                        pass
                
                if cursor:
                    try:
                        cursor.close()
                    except:
                        pass
                
                if connection:
                    try:
                        connection.close()
                    except:
                        pass
                
                return {
                    'success': False,
                    'error': f"保存资源到数据库失败: {str(e)}"
                }
            
            # 返回结果
            results = {
                'vpc_resources': vpc_resources,
                'subnet_resources': subnet_resources,
                'iam_resources': iam_resources
            }
            
            return {
                'success': True,
                'results': results
            }
            
        except Exception as e:
            self.logger.error(f"执行Terraform时发生错误: {str(e)}")
            # 确保恢复工作目录
            try:
                os.chdir(original_dir)
            except:
                pass
            
            return {
                'success': False,
                'error': f"执行Terraform时发生错误: {str(e)}"
            } 