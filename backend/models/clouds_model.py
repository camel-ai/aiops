import mysql.connector
import json
from typing import Dict, Any, List, Optional
import logging

class CloudsModel:
    """数据库模型类，用于处理clouds表的操作"""
    
    def __init__(self, db_config: Dict[str, Any]):
        """初始化数据库连接配置
        
        Args:
            db_config: 数据库连接配置，包含host, user, password, database等参数
        """
        self.db_config = db_config
        self._conn = None
        self.logger = logging.getLogger(__name__)
        
    def _get_connection(self):
        """获取数据库连接"""
        if self._conn is None or not self._conn.is_connected():
            self._conn = mysql.connector.connect(**self.db_config)
        return self._conn
    
    def init_table(self):
        """初始化clouds表，如果不存在则创建"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 读取SQL文件
            with open("sql/create_clouds_table.sql", "r") as f:
                sql = f.read()
                
            # 执行SQL语句
            for statement in sql.split(';'):
                if statement.strip():
                    cursor.execute(statement)
                    
            conn.commit()
            cursor.close()
            self.logger.info("成功初始化clouds表")
            return True
        except Exception as e:
            self.logger.error(f"初始化clouds表时出错: {str(e)}")
            if conn:
                conn.rollback()
            return False
    
    def get_all_clouds(self) -> List[Dict[str, Any]]:
        """获取所有云服务提供商列表
        
        Returns:
            云服务提供商列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = "SELECT * FROM clouds WHERE is_active = 1 ORDER BY id"
            cursor.execute(query)
            results = cursor.fetchall()
            
            # 处理regions字段，将JSON字符串转换为Python列表
            for cloud in results:
                if 'regions' in cloud and cloud['regions']:
                    try:
                        cloud['regions'] = json.loads(cloud['regions'])
                    except json.JSONDecodeError:
                        cloud['regions'] = []
            
            cursor.close()
            self.logger.info(f"成功获取{len(results)}个云服务提供商")
            return results
        except Exception as e:
            self.logger.error(f"获取云服务提供商列表出错: {str(e)}")
            return []
    
    def get_cloud_by_id(self, cloud_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取云服务提供商信息
        
        Args:
            cloud_id: 云服务提供商ID
            
        Returns:
            云服务提供商信息，如果不存在则返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = "SELECT * FROM clouds WHERE id = %s"
            cursor.execute(query, (cloud_id,))
            result = cursor.fetchone()
            
            cursor.close()
            
            # 处理regions字段
            if result and 'regions' in result and result['regions']:
                try:
                    result['regions'] = json.loads(result['regions'])
                except json.JSONDecodeError:
                    result['regions'] = []
                    
            return result
        except Exception as e:
            self.logger.error(f"根据ID获取云服务提供商出错: {str(e)}")
            return None
    
    def get_cloud_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """根据名称获取云服务提供商信息
        
        Args:
            name: 云服务提供商名称
            
        Returns:
            云服务提供商信息，如果不存在则返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True)
            
            query = "SELECT * FROM clouds WHERE name = %s"
            cursor.execute(query, (name,))
            result = cursor.fetchone()
            
            cursor.close()
            
            # 处理regions字段
            if result and 'regions' in result and result['regions']:
                try:
                    result['regions'] = json.loads(result['regions'])
                except json.JSONDecodeError:
                    result['regions'] = []
                    
            return result
        except Exception as e:
            self.logger.error(f"根据名称获取云服务提供商出错: {str(e)}")
            return None
    
    def add_cloud(self, name: str, logo: str = None, provider: str = None, 
                 regions: List[str] = None, is_active: bool = True) -> bool:
        """添加新的云服务提供商
        
        Args:
            name: 云服务提供商名称
            logo: 云服务提供商Logo URL
            provider: 提供商公司名称
            regions: 支持的区域列表
            is_active: 是否激活
            
        Returns:
            是否添加成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 将区域列表转换为JSON字符串
            regions_json = json.dumps(regions) if regions else None
            
            query = """
                INSERT INTO clouds (name, logo, provider, regions, is_active)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, (name, logo, provider, regions_json, 1 if is_active else 0))
            conn.commit()
            
            cursor.close()
            self.logger.info(f"成功添加云服务提供商: {name}")
            return True
        except Exception as e:
            self.logger.error(f"添加云服务提供商出错: {str(e)}")
            if conn:
                conn.rollback()
            return False
    
    def update_cloud(self, cloud_id: int, data: Dict[str, Any]) -> bool:
        """更新云服务提供商信息
        
        Args:
            cloud_id: 云服务提供商ID
            data: 要更新的数据字典
            
        Returns:
            是否更新成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 构建更新语句
            fields = []
            values = []
            
            for field, value in data.items():
                if field in ['name', 'logo', 'provider', 'is_active']:
                    fields.append(f"{field} = %s")
                    values.append(value)
                elif field == 'regions' and isinstance(value, list):
                    fields.append("regions = %s")
                    values.append(json.dumps(value))
            
            if not fields:
                return False
                
            values.append(cloud_id)
            
            query = f"UPDATE clouds SET {', '.join(fields)} WHERE id = %s"
            cursor.execute(query, values)
                
            conn.commit()
            cursor.close()
            self.logger.info(f"成功更新云服务提供商ID: {cloud_id}")
            return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"更新云服务提供商出错: {str(e)}")
            if conn:
                conn.rollback()
            return False
    
    def delete_cloud(self, cloud_id: int) -> bool:
        """删除云服务提供商
        
        Args:
            cloud_id: 云服务提供商ID
            
        Returns:
            是否删除成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "DELETE FROM clouds WHERE id = %s"
            cursor.execute(query, (cloud_id,))
            
            conn.commit()
            cursor.close()
            self.logger.info(f"成功删除云服务提供商ID: {cloud_id}")
            return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"删除云服务提供商出错: {str(e)}")
            if conn:
                conn.rollback()
            return False 