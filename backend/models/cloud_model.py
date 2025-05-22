import mysql.connector
from datetime import datetime
from typing import Dict, Any, List, Optional
import time
import logging
import random
import string

class CloudModel:
    """数据库模型类，用于处理cloud表的操作"""
    
    def __init__(self, db_config: Dict[str, Any]):
        """初始化数据库连接配置
        
        Args:
            db_config: 数据库连接配置，包含host, user, password, database等参数
        """
        self.db_config = db_config
        self._conn = None
        
    def _get_connection(self):
        """获取数据库连接"""
        if self._conn is None or not self._conn.is_connected():
            self._conn = mysql.connector.connect(**self.db_config)
        return self._conn
    
    def init_table(self):
        """初始化cloud表，如果不存在则创建"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 读取SQL文件
            with open("sql/create_cloud_table.sql", "r") as f:
                sql = f.read()
                
            # 执行SQL语句
            for statement in sql.split(';'):
                if statement.strip():
                    cursor.execute(statement)
                    
            conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"Error initializing cloud table: {str(e)}")
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
        logging.info(f"==== 保存云配置 ====")
        logging.info(f"用户ID: {user_id}")
        logging.info(f"用户名: {username}")
        logging.info(f"项目: {project}")
        logging.info(f"云: {cloud}")
        logging.info(f"部署ID原始值: {deployid}")
        logging.info(f"区域: {region}")
        logging.info(f"强制插入: {force_insert}")
        
        # 确保deployid不为空
        if not deployid:
            deployid = "DP" + str(int(time.time()))[-10:] + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            logging.info(f"生成新的部署ID: {deployid}")
        
        deployid_to_save = str(deployid).strip()
        logging.info(f"使用处理后的部署ID: {deployid_to_save}")
        
        try:
            with self._get_connection() as connection, connection.cursor() as cursor:
                if force_insert:
                    # 强制插入新记录
                    sql = """
                        INSERT INTO cloud (username, user_id, project, cloud, ak, sk, deployid)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    params = [username, user_id, project, cloud, ak, sk, deployid_to_save]
                    
                    if region:
                        sql = """
                            INSERT INTO cloud (username, user_id, project, cloud, ak, sk, region, deployid)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        params = [username, user_id, project, cloud, ak, sk, region, deployid_to_save]
                    
                    logging.info(f"执行插入SQL: {sql}")
                    logging.info(f"参数: {params}")
                    cursor.execute(sql, params)
                    insert_id = cursor.lastrowid
                    connection.commit()
                    
                    # 验证插入结果
                    verify_sql = """
                        SELECT id, username, project, cloud, deployid, region
                        FROM cloud
                        WHERE id = %s
                    """
                    cursor.execute(verify_sql, (insert_id,))
                    result = cursor.fetchone()
                    logging.info(f"插入成功，ID: {insert_id}")
                    logging.info(f"验证插入结果: {result}")
                    
                    # 检查结果类型，安全处理
                    deployid_from_db = None
                    if result:
                        # 如果是元组，按索引访问
                        if isinstance(result, tuple):
                            # 假设deployid是第5个字段 (索引为4)
                            deployid_from_db = result[4] if len(result) > 4 else None
                            logging.info(f"从元组中提取部署ID: {deployid_from_db}")
                        # 如果是字典，按键访问
                        elif isinstance(result, dict) and 'deployid' in result:
                            deployid_from_db = result['deployid']
                            logging.info(f"从字典中提取部署ID: {deployid_from_db}")
                        else:
                            logging.warning(f"无法从验证结果中提取部署ID，结果类型: {type(result)}")
                        
                        if deployid_from_db == deployid_to_save:
                            logging.info(f"✅ 部署ID已正确保存: {deployid_to_save}")
                        else:
                            logging.warning(f"❌ 部署ID未正确保存: {deployid_from_db} != {deployid_to_save}")
                    else:
                        logging.warning(f"❌ 部署ID保存不正确或未找到记录")
                    
                    return True
                else:
                    # 更新现有记录，基于deployid
                    sql = """
                        UPDATE cloud
                        SET username = %s, user_id = %s, project = %s, cloud = %s, ak = %s, sk = %s
                    """
                    params = [username, user_id, project, cloud, ak, sk]
                    
                    if region:
                        sql += ", region = %s"
                        params.append(region)
                    
                    sql += " WHERE deployid = %s"
                    params.append(deployid_to_save)
                    
                    logging.info(f"执行更新SQL: {sql}")
                    logging.info(f"参数: {params}")
                    cursor.execute(sql, params)
                    affected_rows = cursor.rowcount
                    connection.commit()
                    
                    if affected_rows > 0:
                        logging.info(f"✅ 更新成功，影响行数: {affected_rows}")
                        return True
                    else:
                        logging.warning(f"❓ 没有记录被更新，尝试插入新记录")
                        # 如果没有找到记录，则插入新记录
                        return self.save_cloud_config(user_id, username, project, cloud, ak, sk, region, deployid, True)
        except Exception as e:
            logging.error(f"保存云配置时出错: {str(e)}", exc_info=True)
            return False
    
    def get_cloud_config(self, user_id: int, project: str = None, 
                        cloud: str = None) -> List[Dict[str, Any]]:
        """获取用户的云配置信息
        
        Args:
            user_id: 用户ID
            project: 项目名称（可选）
            cloud: 云服务提供商（可选）
            
        Returns:
            云配置信息列表
        """
        conn = None
        cursor = None
        try:
            # 创建新连接
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor(dictionary=True)
            
            query = "SELECT * FROM cloud WHERE user_id = %s"
            params = [user_id]
            
            if project:
                query += " AND project = %s"
                params.append(project)
            
            if cloud:
                query += " AND cloud = %s"
                params.append(cloud)
            
            # 添加排序，确保最新的记录在前
            query += " ORDER BY id DESC"
            
            print(f"执行查询: {query}")
            print(f"参数: {params}")
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            print(f"查询结果数量: {len(results)}")
            if results:
                print(f"第一条结果: {results[0]}")
            
            # 确保完全消费结果集
            cursor.fetchall()  # 清空任何剩余结果
            
            # 安全关闭
            cursor.close()
            conn.close()
            
            return results
        except Exception as e:
            print(f"获取云配置时出错: {str(e)}")
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
                              resources: Dict[str, str]) -> bool:
        """更新云资源信息
        
        Args:
            user_id: 用户ID
            project: 项目名称
            cloud: 云服务提供商
            resources: 资源信息，包含vpc, subnet, object, iam_user等字段
            
        Returns:
            操作是否成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 构建更新语句
            fields = []
            values = []
            
            for field, value in resources.items():
                if field in ['vpc', 'subnet', 'object', 'iam_user', 
                           'iam_user_group', 'iam_user_policy']:
                    fields.append(f"{field} = %s")
                    values.append(value)
            
            if not fields:
                return False
                
            values.extend([user_id, project, cloud])
            
            query = f"UPDATE cloud SET {', '.join(fields)} WHERE user_id = %s AND project = %s AND cloud = %s"
            cursor.execute(query, values)
                
            conn.commit()
            cursor.close()
            return cursor.rowcount > 0
        except Exception as e:
            print(f"Error updating cloud resources: {str(e)}")
            if conn:
                conn.rollback()
            return False
    
    def get_regions_by_cloud(self, cloud: str) -> List[str]:
        """获取指定云服务商的所有区域列表
        
        Args:
            cloud: 云服务提供商名称
            
        Returns:
            区域列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 查询特定云的所有区域，排除重复和null值
            cursor.execute(
                "SELECT DISTINCT region FROM cloud WHERE cloud = %s AND region IS NOT NULL",
                (cloud,)
            )
            results = cursor.fetchall()
            cursor.close()
            
            # 提取区域列表
            regions = [row[0] for row in results if row[0]]
            
            # 获取为该云服务商预定义的区域列表
            default_regions = self._get_default_regions_for_cloud(cloud)
            
            # 如果数据库中没有区域数据，使用默认区域
            if not regions:
                print(f"未从数据库获取到{cloud}的区域列表，使用默认区域列表")
                return default_regions
            
            # 合并数据库中存在的区域和默认区域（确保无重复）
            unique_regions = list(set(regions + default_regions))
            unique_regions.sort()  # 排序以获得一致的顺序
            
            print(f"为{cloud}返回区域列表: {unique_regions}")
            return unique_regions
        except Exception as e:
            print(f"Error getting regions for cloud {cloud}: {str(e)}")
            # 出错时返回默认区域列表
            return self._get_default_regions_for_cloud(cloud)
    
    def _get_default_regions_for_cloud(self, cloud: str) -> List[str]:
        """获取云服务商的默认区域列表
        
        Args:
            cloud: 云服务提供商名称
            
        Returns:
            默认区域列表
        """
        # 为不同云提供商提供默认区域
        default_regions = {
            'AWS': ['ap-south-1', 'eu-north-1', 'eu-west-3', 'eu-west-2', 'eu-west-1', 'ap-northeast-3', 'ap-northeast-2', 'ap-northeast-1', 'ca-central-1', 'sa-east-1', 'ap-southeast-1', 'ap-southeast-2', 'eu-central-1', 'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2', 'cn-north-1', 'cn-northwest-1'],
            'AZURE': ['eastus', 'westus', 'northeurope', 'eastasia'],
            '阿里云': ['cn-hangzhou', 'cn-shanghai', 'cn-beijing', 'cn-shenzhen'],
            '华为云': ['cn-north-1', 'cn-east-2', 'cn-south-1'],
            '腾讯云': ['ap-guangzhou', 'ap-shanghai', 'ap-beijing', 'ap-chengdu'],
            '百度云': ['bd-beijing-a', 'bd-guangzhou-a'],
            '火山云': ['cn-beijing', 'cn-shanghai'],
            '四维云': ['cn-beijing', 'cn-hangzhou']
        }
        
        # 确保大小写不敏感匹配
        normalized_cloud = cloud.upper()
        for key in default_regions.keys():
            if key.upper() == normalized_cloud:
                return default_regions[key]
        
        # 如果没有匹配，返回一个基本的默认区域列表
        return ['default-region']
    
    def get_user_deployments(self, user_id: int) -> List[Dict[str, Any]]:
        """获取用户的所有部署历史
        
        Args:
            user_id: 用户ID
            
        Returns:
            部署历史列表，包含部署ID、项目、云、区域和时间
        """
        conn = None
        cursor = None
        try:
            # 创建新连接
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor(dictionary=True)
            
            # 查询用户的所有部署，按部署ID分组
            query = """
                SELECT DISTINCT deployid, project, cloud, region, MAX(created_at) as created_at 
                FROM cloud 
                WHERE user_id = %s 
                GROUP BY deployid, project, cloud, region
                ORDER BY MAX(created_at) DESC
            """
            
            cursor.execute(query, (user_id,))
            deployments = cursor.fetchall()
            
            # 安全关闭
            cursor.close()
            conn.close()
            
            return deployments
        except Exception as e:
            print(f"获取用户部署历史出错: {str(e)}")
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            return []
            
    def get_deployment_details(self, deploy_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """获取指定部署ID的资源详情
        
        Args:
            deploy_id: 部署ID
            
        Returns:
            资源详情，按资源类型分组
        """
        conn = None
        cursor = None
        try:
            # 创建新连接
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor(dictionary=True)
            
            # 查询部署ID的所有资源
            query = """
                SELECT * FROM cloud 
                WHERE deployid = %s
                ORDER BY resource_type, resource_index
            """
            
            cursor.execute(query, (deploy_id,))
            resources = cursor.fetchall()
            
            # 安全关闭
            cursor.close()
            conn.close()
            
            # 按资源类型分组
            result = {
                'vpc_resources': [],
                'subnet_resources': [],
                'iam_resources': [],
                'deployment_info': None
            }
            
            # 部署基本信息
            if resources and len(resources) > 0:
                result['deployment_info'] = {
                    'deploy_id': deploy_id,
                    'project': resources[0]['project'],
                    'cloud': resources[0]['cloud'],
                    'region': resources[0]['region'],
                    'created_at': resources[0]['created_at']
                }
            
            # 分组资源
            for resource in resources:
                if resource['resource_type'] == 'vpc':
                    result['vpc_resources'].append({
                        'vpc': resource['vpc'],
                        'vpcid': resource['vpcid'],
                        'vpccidr': resource['vpccidr'],
                        'resource_index': resource['resource_index']
                    })
                elif resource['resource_type'] == 'subnet':
                    result['subnet_resources'].append({
                        'subnet': resource['subnet'],
                        'subnetid': resource['subnetid'],
                        'subnetvpc': resource['subnetvpc'],
                        'subnetcidr': resource['subnetcidr'],
                        'resource_index': resource['resource_index']
                    })
                elif resource['resource_type'] == 'iam':
                    result['iam_resources'].append({
                        'iam_user': resource['iam_user'],
                        'iamid': resource['iamid'],
                        'iamarn': resource['iamarn'],
                        'resource_index': resource['resource_index']
                    })
            
            return result
        except Exception as e:
            print(f"获取部署详情出错: {str(e)}")
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            return {
                'vpc_resources': [],
                'subnet_resources': [],
                'iam_resources': [],
                'deployment_info': None
            } 