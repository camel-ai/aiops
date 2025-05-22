import mysql.connector
from datetime import datetime
from typing import Dict, Any, List, Optional
import time
import logging
import random
import string

class DeployModel:
    """数据库模型类，用于处理clouddeploy表的操作"""
    
    def __init__(self, db_config: Dict[str, Any]):
        """初始化数据库连接配置
        
        Args:
            db_config: 数据库连接配置，包含host, user, password, database等参数
        """
        self.db_config = db_config
        self.db = None
        self.logger = logging.getLogger('deploy_model')
        
    def _get_connection(self):
        """获取数据库连接"""
        if self.db is None or not self.db.is_connected():
            self.db = mysql.connector.connect(**self.db_config)
        return self.db
    
    def init_table(self):
        """初始化clouddeploy表，如果不存在则创建"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 读取SQL文件
            with open("sql/create_clouddeploy_table.sql", "r") as f:
                sql = f.read()
                
            # 执行SQL语句
            for statement in sql.split(';'):
                if statement.strip():
                    cursor.execute(statement)
                    
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            self.logger.error(f"Error initializing clouddeploy table: {str(e)}")
            if conn:
                conn.rollback()
            return False
    
    def save_cloud_config(self, user_id, username, project, cloud, ak, sk, region=None, deployid=None, force_insert=False):
        """保存云配置信息
        
        Args:
            user_id: 用户ID
            username: 用户名
            project: 项目名称
            cloud: 云服务商
            ak: Access Key
            sk: Secret Key
            region: 区域（可选）
            deployid: 部署ID（可选），如果没有提供则生成一个
            force_insert: 是否强制插入新记录，默认为False

        Returns:
            保存是否成功
        """
        # 记录参数
        self.logger.info(f"==== 保存云部署配置 ====")
        self.logger.info(f"用户ID: {user_id}")
        self.logger.info(f"用户名: {username}")
        self.logger.info(f"项目: {project}")
        self.logger.info(f"云: {cloud}")
        self.logger.info(f"部署ID原始值: {deployid}")
        self.logger.info(f"区域: {region}")
        self.logger.info(f"强制插入: {force_insert}")
        
        # 确保deployid不为空
        if not deployid:
            deployid = "DP" + str(int(time.time()))[-10:] + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            self.logger.info(f"生成新的部署ID: {deployid}")
        
        deployid_to_save = str(deployid).strip()
        self.logger.info(f"使用处理后的部署ID: {deployid_to_save}")
        
        try:
            with self._get_connection() as connection, connection.cursor() as cursor:
                if force_insert:
                    # 强制插入新记录
                    sql = """
                        INSERT INTO clouddeploy (username, user_id, project, cloud, ak, sk, deployid)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    params = [username, user_id, project, cloud, ak, sk, deployid_to_save]
                    
                    if region:
                        sql = """
                            INSERT INTO clouddeploy (username, user_id, project, cloud, ak, sk, region, deployid)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        params = [username, user_id, project, cloud, ak, sk, region, deployid_to_save]
                    
                    self.logger.info(f"执行插入SQL: {sql}")
                    self.logger.info(f"参数: {params}")
                    cursor.execute(sql, params)
                    insert_id = cursor.lastrowid
                    connection.commit()
                    
                    # 验证插入结果
                    verify_sql = """
                        SELECT id, username, project, cloud, deployid, region
                        FROM clouddeploy
                        WHERE id = %s
                    """
                    cursor.execute(verify_sql, (insert_id,))
                    result = cursor.fetchone()
                    self.logger.info(f"插入成功，ID: {insert_id}")
                    self.logger.info(f"验证插入结果: {result}")
                    
                    # 检查结果类型，安全处理
                    deployid_from_db = None
                    if result:
                        # 如果是元组，按索引访问
                        if isinstance(result, tuple):
                            # 假设deployid是第5个字段 (索引为4)
                            deployid_from_db = result[4] if len(result) > 4 else None
                            self.logger.info(f"从元组中提取部署ID: {deployid_from_db}")
                        # 如果是字典，按键访问
                        elif isinstance(result, dict) and 'deployid' in result:
                            deployid_from_db = result['deployid']
                            self.logger.info(f"从字典中提取部署ID: {deployid_from_db}")
                        else:
                            self.logger.warning(f"无法从验证结果中提取部署ID，结果类型: {type(result)}")
                        
                        if deployid_from_db == deployid_to_save:
                            self.logger.info(f"✅ 部署ID已正确保存: {deployid_to_save}")
                        else:
                            self.logger.warning(f"❌ 部署ID未正确保存: {deployid_from_db} != {deployid_to_save}")
                    else:
                        self.logger.warning(f"❌ 部署ID保存不正确或未找到记录")
                    
                    return True
                else:
                    # 更新现有记录，基于deployid
                    sql = """
                        UPDATE clouddeploy
                        SET username = %s, user_id = %s, project = %s, cloud = %s, ak = %s, sk = %s
                    """
                    params = [username, user_id, project, cloud, ak, sk]
                    
                    if region:
                        sql += ", region = %s"
                        params.append(region)
                    
                    sql += " WHERE deployid = %s"
                    params.append(deployid_to_save)
                    
                    self.logger.info(f"执行更新SQL: {sql}")
                    self.logger.info(f"参数: {params}")
                    cursor.execute(sql, params)
                    affected_rows = cursor.rowcount
                    connection.commit()
                    
                    if affected_rows > 0:
                        self.logger.info(f"✅ 更新成功，影响行数: {affected_rows}")
                        return True
                    else:
                        self.logger.warning(f"❓ 没有记录被更新，尝试插入新记录")
                        # 如果没有找到记录，则插入新记录
                        return self.save_cloud_config(user_id, username, project, cloud, ak, sk, region, deployid, True)
        except Exception as e:
            self.logger.error(f"保存云部署配置时出错: {str(e)}", exc_info=True)
            return False
    
    def get_cloud_config(self, user_id: int, project: str = None, 
                        cloud: str = None) -> List[Dict[str, Any]]:
        """获取用户的云部署配置信息
        
        Args:
            user_id: 用户ID
            project: 项目名称（可选）
            cloud: 云服务提供商（可选）
            
        Returns:
            云部署配置信息列表
        """
        conn = None
        cursor = None
        try:
            # 创建新连接
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor(dictionary=True)
            
            query = "SELECT * FROM clouddeploy WHERE user_id = %s"
            params = [user_id]
            
            if project:
                query += " AND project = %s"
                params.append(project)
            
            if cloud:
                query += " AND cloud = %s"
                params.append(cloud)
            
            # 添加排序，确保最新的记录在前
            query += " ORDER BY id DESC"
            
            self.logger.info(f"执行查询: {query}")
            self.logger.info(f"参数: {params}")
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            self.logger.info(f"查询结果数量: {len(results)}")
            if results:
                self.logger.info(f"第一条结果: {results[0]}")
            
            # 确保完全消费结果集
            cursor.fetchall()  # 清空任何剩余结果
            
            # 安全关闭
            cursor.close()
            conn.close()
            
            return results
        except Exception as e:
            self.logger.error(f"获取云部署配置时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            if conn:
                try:
                    if cursor:
                        cursor.close()
                except:
                    pass
                finally:
                    try:
                        conn.close()
                    except:
                        pass
            return []
    
    def update_cloud_resources(self, user_id: int, project: str, cloud: str,
                              resources: Dict[str, str], deployid: str = None) -> bool:
        """更新云资源部署信息
        
        Args:
            user_id: 用户ID
            project: 项目名称
            cloud: 云服务提供商
            resources: 资源信息，键为资源名称，值为资源值
            deployid: 部署ID（可选），如果提供则优先使用此ID找记录
            
        Returns:
            更新是否成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 先尝试使用部署ID查找记录
            if deployid:
                query = """
                    SELECT id FROM clouddeploy
                    WHERE deployid = %s
                    LIMIT 1
                """
                cursor.execute(query, (deployid,))
                result = cursor.fetchone()
                
                if result:
                    record_id = result[0]
                    self.logger.info(f"通过部署ID={deployid}找到记录ID: {record_id}")
                else:
                    self.logger.warning(f"未找到部署ID={deployid}的记录，尝试使用其他条件查找")
                    # 如果找不到记录，继续使用用户ID、项目和云查找
                    query = """
                        SELECT id, deployid FROM clouddeploy
                        WHERE user_id = %s AND project = %s AND cloud = %s
                        ORDER BY id DESC LIMIT 1
                    """
                    cursor.execute(query, (user_id, project, cloud))
                    result = cursor.fetchone()
            else:
                # 如果没有提供部署ID，使用用户ID、项目和云查找最新记录
                query = """
                    SELECT id, deployid FROM clouddeploy
                    WHERE user_id = %s AND project = %s AND cloud = %s
                    ORDER BY id DESC LIMIT 1
                """
                cursor.execute(query, (user_id, project, cloud))
                result = cursor.fetchone()
            
            if result is None:
                self.logger.error(f"未找到用户ID={user_id}, 项目={project}, 云={cloud}的部署记录")
                return False
            
            # 提取记录ID
            record_id = result[0]
            db_deployid = result[1] if len(result) > 1 else None
            self.logger.info(f"找到记录ID: {record_id}, 部署ID: {db_deployid}")
            
            # 构建更新语句
            update_sql = "UPDATE clouddeploy SET "
            update_fields = []
            params = []
            
            for key, value in resources.items():
                update_fields.append(f"{key} = %s")
                params.append(value)
            
            # 添加更新时间
            update_fields.append("updated_at = NOW()")
            
            update_sql += ", ".join(update_fields)
            update_sql += " WHERE id = %s"
            params.append(record_id)
            
            cursor.execute(update_sql, params)
            conn.commit()
            
            affected_rows = cursor.rowcount
            cursor.close()
            
            if affected_rows > 0:
                self.logger.info(f"成功更新部署资源，影响行数: {affected_rows}")
                return True
            else:
                self.logger.warning(f"资源部署更新操作没有影响任何行")
                return False
        except Exception as e:
            self.logger.error(f"更新云资源部署信息时出错: {str(e)}")
            if conn:
                conn.rollback()
            return False
    
    def get_regions_by_cloud(self, cloud: str) -> List[str]:
        """获取云服务商支持的区域列表
        
        Args:
            cloud: 云服务商名称
            
        Returns:
            区域列表
        """
        # 始终获取默认完整区域列表
        default_regions = self._get_default_regions_for_cloud(cloud)
        
        # 再从数据库中获取已有的区域信息
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT DISTINCT region FROM clouddeploy
                WHERE cloud = %s AND region IS NOT NULL AND region != ''
            """
            cursor.execute(query, (cloud,))
            results = cursor.fetchall()
            
            db_regions = [row[0] for row in results if row[0] is not None]
            
            # 合并默认区域和数据库中的区域，确保不重复
            all_regions = list(set(default_regions + db_regions))
            
            self.logger.info(f"为{cloud}返回区域列表: {all_regions}")
            return all_regions
        except Exception as e:
            self.logger.error(f"获取云区域时出错: {str(e)}")
            self.logger.info(f"使用默认区域列表: {default_regions}")
            return default_regions
    
    def _get_default_regions_for_cloud(self, cloud: str) -> List[str]:
        """获取云服务商的默认区域列表
        
        Args:
            cloud: 云服务商名称
            
        Returns:
            默认区域列表
        """
        # 为不同的云服务商提供默认的区域列表
        cloud_regions = {
            'AWS': ['ap-south-1', 'eu-north-1', 'eu-west-3', 'eu-west-2', 'eu-west-1', 'ap-northeast-3', 'ap-northeast-2', 'ap-northeast-1', 'ca-central-1', 'sa-east-1', 'ap-southeast-1', 'ap-southeast-2', 'eu-central-1', 'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 'cn-north-1', 'cn-northwest-1'],
            'Azure': ['eastus', 'westus', 'northeurope', 'eastasia', 'southeastasia'],
            'GCP': ['us-central1', 'us-east1', 'europe-west1', 'asia-east1', 'asia-southeast1'],
            'Aliyun': ['cn-hangzhou', 'cn-beijing', 'cn-shanghai', 'cn-shenzhen', 'ap-southeast-1'],
            'Tencent': ['ap-guangzhou', 'ap-beijing', 'ap-shanghai', 'ap-nanjing', 'ap-hongkong'],
            'Huawei': ['cn-north-4', 'cn-east-3', 'cn-south-1', 'ap-southeast-1']
        }
        
        return cloud_regions.get(cloud, ['region-1', 'region-2', 'region-3'])
    
    def get_user_deployments(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的所有部署历史
        
        Args:
            user_id: 用户ID
            
        Returns:
            部署历史记录列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = """
                SELECT id, username, user_id, project, cloud, region, deployid, 
                       created_at, updated_at
                FROM clouddeploy
                WHERE user_id = %s
                ORDER BY id DESC
            """
            cursor.execute(query, (user_id,))
            results = cursor.fetchall()
            
            # 处理日期格式
            for row in results:
                if 'created_at' in row and row['created_at']:
                    row['created_at'] = row['created_at'].isoformat()
                if 'updated_at' in row and row['updated_at']:
                    row['updated_at'] = row['updated_at'].isoformat()
            
            self.logger.info(f"找到用户ID={user_id}的部署历史记录数: {len(results)}")
            return results
        except Exception as e:
            self.logger.error(f"获取用户部署历史时出错: {str(e)}")
            return []
    
    def get_deployment_details(self, deploy_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """获取指定部署ID的资源详情
        
        Args:
            deploy_id: 部署ID
            
        Returns:
            包含部署信息和资源列表的字典
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 获取部署基本信息
            query = """
                SELECT * FROM clouddeploy
                WHERE deployid = %s
                LIMIT 1
            """
            cursor.execute(query, (deploy_id,))
            deployment_info = cursor.fetchone()
            
            if not deployment_info:
                self.logger.warning(f"未找到部署ID为{deploy_id}的记录")
                return {"deployment_info": {}, "resources": []}
            
            # 处理日期格式
            if 'created_at' in deployment_info and deployment_info['created_at']:
                deployment_info['created_at'] = deployment_info['created_at'].isoformat()
            if 'updated_at' in deployment_info and deployment_info['updated_at']:
                deployment_info['updated_at'] = deployment_info['updated_at'].isoformat()
            
            # 获取相关资源信息
            resources = []
            resource_fields = ['vpc', 'subnet', 'object', 'iam_user', 'iam_user_group', 'iam_user_policy']
            
            for field in resource_fields:
                if deployment_info.get(field):
                    resources.append({
                        "type": field,
                        "name": deployment_info[field],
                        "id": deployment_info.get(f"{field}id", ""),
                        "details": self._get_resource_details(deployment_info, field)
                    })
            
            self.logger.info(f"找到部署ID={deploy_id}的资源数: {len(resources)}")
            return {
                "deployment_info": deployment_info,
                "resources": resources
            }
        except Exception as e:
            self.logger.error(f"获取部署详情时出错: {str(e)}")
            return {"deployment_info": {}, "resources": []}
    
    def _get_resource_details(self, deployment_info: Dict[str, Any], resource_type: str) -> Dict[str, Any]:
        """获取资源详细信息
        
        Args:
            deployment_info: 部署信息
            resource_type: 资源类型
            
        Returns:
            资源详细信息
        """
        details = {}
        
        if resource_type == 'vpc':
            details = {
                "cidr": deployment_info.get('vpccidr', ''),
                "status": "已部署",
                "cloud": deployment_info.get('cloud', '')
            }
        elif resource_type == 'subnet':
            details = {
                "vpc": deployment_info.get('subnetvpc', ''),
                "cidr": deployment_info.get('subnetcidr', ''),
                "status": "已部署",
                "cloud": deployment_info.get('cloud', '')
            }
        elif resource_type == 'iam_user':
            details = {
                "arn": deployment_info.get('objectarn', ''),
                "access_key_id": deployment_info.get('iam_access_key_id', ''),
                "access_key_secret": deployment_info.get('iam_access_key_secret', ''),
                "console_password": deployment_info.get('iam_console_password', ''),
                "policies": deployment_info.get('iam_user_policies', ''),
                "status": "已部署",
                "cloud": deployment_info.get('cloud', '')
            }
        
        return details

    def generate_deploy_id(self) -> str:
        """生成部署ID，格式为DP+时间戳+随机字符"""
        timestamp = str(int(time.time()))[-10:]  # 取时间戳后10位
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        deploy_id = f"DP{timestamp}{random_str}"
        return deploy_id
        
    def create_deployment(self, deploy_id: str, deploy_type: str, project: str, 
                         cloud: str, region: str, status: str, user_id: int) -> bool:
        """创建部署记录
        
        Args:
            deploy_id: 部署ID
            deploy_type: 部署类型 (vpc, subnet, iam_user 等)
            project: 项目名称
            cloud: 云服务提供商
            region: 区域
            status: 部署状态 (in_progress, completed, failed 等)
            user_id: 用户ID
            
        Returns:
            创建是否成功
        """
        self.logger.info(f"创建部署记录: ID={deploy_id}, 类型={deploy_type}, 项目={project}, 云={cloud}, 区域={region}, 状态={status}, 用户ID={user_id}")
        
        try:
            # 获取用户名（如果有记录）
            username = None
            with self._get_connection() as connection, connection.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT username FROM clouddeploy WHERE user_id = %s LIMIT 1", (user_id,))
                result = cursor.fetchone()
                if result and 'username' in result:
                    username = result['username']
            
            # 如果没有找到用户名，使用默认值
            if not username:
                username = f"user_{user_id}"
            
            # 获取deploytype数值
            deploy_type_value = self._status_to_deploytype(status)
            
            # 创建新的部署记录
            with self._get_connection() as connection, connection.cursor() as cursor:
                sql = """
                    INSERT INTO clouddeploy 
                    (deployid, user_id, username, project, cloud, region, deploytype, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """
                params = [deploy_id, user_id, username, project, cloud, region, deploy_type_value]
                
                # 记录SQL和参数
                self.logger.info(f"执行创建部署SQL: {sql}")
                self.logger.info(f"参数: {params}")
                
                cursor.execute(sql, params)
                connection.commit()
                
                self.logger.info(f"✅ 部署记录创建成功, ID: {deploy_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"创建部署记录时出错: {str(e)}", exc_info=True)
            return False
        
    def update_deployment_status(self, deploy_id: str, status: str, user_id: int = None) -> bool:
        """更新部署状态
        
        Args:
            deploy_id: 部署ID
            status: 部署状态（in_progress, completed, failed等）
            user_id: 用户ID（可选，用于额外验证）
            
        Returns:
            更新是否成功
        """
        self.logger.info(f"更新部署状态: ID={deploy_id}, 状态={status}")
        
        try:
            with self._get_connection() as connection, connection.cursor() as cursor:
                # 构建SQL语句 - 使用deploytype字段
                sql = """
                    UPDATE clouddeploy
                    SET deploytype = %s, updated_at = NOW()
                    WHERE deployid = %s
                """
                params = [self._status_to_deploytype(status), deploy_id]
                
                # 如果提供了用户ID，则添加用户ID条件
                if user_id:
                    sql += " AND user_id = %s"
                    params.append(user_id)
                
                self.logger.info(f"执行更新状态SQL: {sql}")
                self.logger.info(f"参数: {params}")
                
                cursor.execute(sql, params)
                affected_rows = cursor.rowcount
                connection.commit()
                
                if affected_rows > 0:
                    self.logger.info(f"✅ 状态更新成功，影响行数: {affected_rows}")
                    return True
                else:
                    self.logger.warning(f"❓ 没有记录被更新，检查部署ID是否存在: {deploy_id}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"更新部署状态时出错: {str(e)}", exc_info=True)
            return False
            
    def _status_to_deploytype(self, status: str) -> int:
        """将状态字符串转换为数据库中的deploytype值
        
        Args:
            status: 状态字符串（in_progress, completed, failed等）
            
        Returns:
            对应的deploytype整数值
        """
        status_map = {
            'not_started': 0,
            'in_progress': 1,
            'completed': 2,
            'failed': 3,
            'cancelled': 4
        }
        
        return status_map.get(status.lower(), 0)  # 默认为未开始 

    def get_deployment_by_id(self, deploy_id):
        """根据部署ID获取部署信息
        
        Args:
            deploy_id: 部署ID
            
        Returns:
            包含部署信息的字典，若未找到则返回None
        """
        if not deploy_id:
            self.logger.error("获取部署信息失败：部署ID为空")
            return None
            
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            # 查询clouddeploy表中的部署信息
            query = """
                SELECT * FROM clouddeploy 
                WHERE deployid = %s
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            cursor.execute(query, (deploy_id,))
            result = cursor.fetchone()
            
            if result:
                self.logger.info(f"找到部署ID:{deploy_id}的信息")
            else:
                self.logger.warning(f"未找到部署ID:{deploy_id}的信息")
                
            cursor.close()
            conn.close()
            
            return result
        except Exception as e:
            self.logger.error(f"获取部署信息时出错: {str(e)}")
            return None 