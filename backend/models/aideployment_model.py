# AIDeployment模型 - 修复导入
import logging
import json
import time
from datetime import datetime
from db.db import get_db

class AIDeploymentModel:
    """AI部署模型，处理AI自动生成的Terraform部署"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.table_name = 'aideployments'
        
        # 确保表存在
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """确保部署表存在"""
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # 检查表是否存在 (使用MySQL语法)
            cursor.execute(f"SHOW TABLES LIKE '{self.table_name}'")
            table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                # 创建部署表 (使用MySQL语法)
                self.logger.info(f"创建{self.table_name}表")
                create_table_sql = f"""
                CREATE TABLE {self.table_name} (
                    id VARCHAR(255) PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    project VARCHAR(255),
                    cloud VARCHAR(255),
                    status VARCHAR(50) NOT NULL,
                    error_message TEXT,
                    terraform_code TEXT NOT NULL,
                    deployment_summary TEXT,
                    created_at VARCHAR(50) NOT NULL,
                    updated_at VARCHAR(50) NOT NULL
                )
                """
                cursor.execute(create_table_sql)
                conn.commit()
                self.logger.info(f"{self.table_name}表创建成功")
            else:
                # 检查并添加缺失的列
                self._add_missing_columns(cursor)
            
            cursor.close()
            conn.close()
        except Exception as e:
            self.logger.error(f"确保{self.table_name}表存在时出错: {str(e)}")
            raise
    
    def _add_missing_columns(self, cursor):
        """添加缺失的列"""
        try:
            # 检查表结构
            cursor.execute(f"DESCRIBE {self.table_name}")
            existing_columns = {row['Field'] for row in cursor.fetchall()}
            
            # 需要的列
            required_columns = {
                'project': 'VARCHAR(255)',
                'cloud': 'VARCHAR(255)'
            }
            
            # 添加缺失的列
            for column_name, column_type in required_columns.items():
                if column_name not in existing_columns:
                    alter_sql = f"ALTER TABLE {self.table_name} ADD COLUMN {column_name} {column_type}"
                    cursor.execute(alter_sql)
                    self.logger.info(f"已添加列 {column_name} 到 {self.table_name} 表")
            
        except Exception as e:
            self.logger.error(f"添加缺失列时出错: {str(e)}")
            # 不抛出异常，以免影响表的正常使用
    
    def create_deployment(self, deployment_data):
        """创建新的部署记录
        
        Args:
            deployment_data (dict): 部署数据
                id: 部署ID
                user_id: 用户ID
                username: 用户名
                name: 部署名称
                description: 部署描述
                status: 部署状态
                terraform_code: Terraform代码
                created_at: 创建时间
                updated_at: 更新时间
        
        Returns:
            bool: 是否成功
        """
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # 构建SQL
            columns = ', '.join(deployment_data.keys())
            # 使用MySQL占位符%s，无需动态生成
            placeholders = ', '.join(['%s' for _ in deployment_data])
            
            insert_sql = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
            
            # 执行插入
            cursor.execute(insert_sql, list(deployment_data.values()))
            conn.commit()
            
            cursor.close()
            conn.close()
            
            self.logger.info(f"成功创建部署记录: {deployment_data['id']}")
            return True
        except Exception as e:
            self.logger.error(f"创建部署记录时出错: {str(e)}")
            return False
    
    def update_deployment_status(self, deploy_id, status, error_message=None, deployment_summary=None):
        """更新部署状态
        
        Args:
            deploy_id (str): 部署ID
            status (str): 新状态
            error_message (str, optional): 错误消息
            deployment_summary (str, optional): 部署摘要
        
        Returns:
            bool: 是否成功
        """
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # 构建更新数据
            update_data = {
                'status': status,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if error_message is not None:
                update_data['error_message'] = error_message
                
            if deployment_summary is not None:
                update_data['deployment_summary'] = deployment_summary
            
            # 构建更新SQL - 修改为使用MySQL占位符%s
            set_clause = ', '.join([f"{k} = %s" for k in update_data.keys()])
            update_sql = f"UPDATE {self.table_name} SET {set_clause} WHERE id = %s"
            
            # 执行更新
            cursor.execute(update_sql, list(update_data.values()) + [deploy_id])
            conn.commit()
            
            cursor.close()
            conn.close()
            
            self.logger.info(f"成功更新部署状态: {deploy_id} -> {status}")
            return True
        except Exception as e:
            self.logger.error(f"更新部署状态时出错: {str(e)}")
            return False
    
    def get_deployment(self, deploy_id):
        """获取部署详情
        
        Args:
            deploy_id (str): 部署ID
        
        Returns:
            dict: 部署详情，如果不存在则返回None
        """
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # 查询部署
            cursor.execute(f"SELECT * FROM {self.table_name} WHERE id = %s", (deploy_id,))
            row = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if not row:
                return None
                
            # MySQL已经返回了字典，不需要获取列名并手动转换
            deployment = row
            
            # 解析JSON字段
            if deployment.get('deployment_summary'):
                try:
                    deployment['deployment_summary'] = json.loads(deployment['deployment_summary'])
                except json.JSONDecodeError:
                    self.logger.warning(f"无法解析部署摘要: {deployment['deployment_summary']}")
            
            return deployment
        except Exception as e:
            self.logger.error(f"获取部署详情时出错: {str(e)}")
            return None
    
    def list_deployments(self, user_id=None, status=None, page=1, page_size=10):
        """列出部署
        
        Args:
            user_id (int, optional): 用户ID，如果提供则只返回该用户的部署
            status (str, optional): 部署状态，如果提供则只返回该状态的部署
            page (int, optional): 页码，默认为1
            page_size (int, optional): 每页大小，默认为10
        
        Returns:
            tuple: (deployments, total) 部署列表和总数
        """
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            # 构建查询条件
            conditions = []
            params = []
            
            if user_id is not None:
                conditions.append("user_id = %s")
                params.append(user_id)
                
            if status is not None:
                conditions.append("status = %s")
                params.append(status)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # 查询总数
            count_sql = f"SELECT COUNT(*) as count FROM {self.table_name} WHERE {where_clause}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()['count']
            
            # 查询分页数据 (排除terraform_code字段)
            offset = (page - 1) * page_size
            query_sql = f"""
            SELECT id, user_id, username, name, description, project, cloud, status, error_message, 
                   deployment_summary, created_at, updated_at
            FROM {self.table_name}
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """
            cursor.execute(query_sql, params + [page_size, offset])
            rows = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            # 构建部署列表 (MySQL已经返回字典，不需要手动转换)
            deployments = []
            for row in rows:
                deployment = row
                
                # 解析JSON字段
                if deployment.get('deployment_summary'):
                    try:
                        deployment['deployment_summary'] = json.loads(deployment['deployment_summary'])
                    except json.JSONDecodeError:
                        self.logger.warning(f"无法解析部署摘要: {deployment['deployment_summary']}")
                
                deployments.append(deployment)
            
            return deployments, total
        except Exception as e:
            self.logger.error(f"列出部署时出错: {str(e)}")
            return [], 0 