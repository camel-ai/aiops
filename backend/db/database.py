import os
import sys
import pymysql
import logging
import traceback

# 获取当前脚本所在目录的父目录（backend）的父目录（项目根目录）
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(backend_dir)
sys.path.append(project_dir)

from backend.config.config import Config

class Database:
    def __init__(self, config=None):
        """初始化数据库连接"""
        self.config = config or Config()
        self.logger = logging.getLogger(__name__)
        
        # 记录数据库配置信息（不包含密码）以便于调试
        self.logger.info(f"数据库配置: Host={self.config.db_host}, User={self.config.db_user}, DB={self.config.db_name}")
        
        # 测试连接是否可用
        try:
            conn = self._get_connection(test_connection=True)
            if conn:
                self.logger.info("数据库连接成功")
                conn.close()
        except Exception as e:
            self.logger.error(f"数据库初始化连接测试失败: {e}")
            self.logger.error(traceback.format_exc())
            # 我们只记录错误，但不抛出异常，允许应用程序继续运行
            # 这样当数据库暂时不可用时，应用程序可以提供适当的错误信息
    
    def _get_connection(self, test_connection=False):
        """获取数据库连接"""
        try:
            connection = pymysql.connect(
                host=self.config.db_host,
                user=self.config.db_user,
                password=self.config.db_password,
                database=self.config.db_name,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=5  # 设置连接超时时间
            )
            
            # 如果是测试连接，执行一个简单查询
            if test_connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
            
            return connection
        except Exception as e:
            self.logger.error(f"数据库连接失败: {e}")
            self.logger.error(traceback.format_exc())
            # 仅当是测试连接时才抛出异常
            if test_connection:
                raise
            return None
    
    def query(self, sql, params=None):
        """执行查询语句并返回结果集"""
        connection = None
        try:
            connection = self._get_connection()
            if not connection:
                raise Exception("无法建立数据库连接")
            
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchall()
                return result
        except Exception as e:
            self.logger.error(f"查询失败: {e}")
            self.logger.error(f"SQL: {sql}, 参数: {params}")
            self.logger.error(traceback.format_exc())
            raise
        finally:
            if connection:
                connection.close()
    
    def query_one(self, sql, params=None):
        """执行查询语句并返回单条结果"""
        connection = None
        try:
            connection = self._get_connection()
            if not connection:
                raise Exception("无法建立数据库连接")
            
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchone()
                return result
        except Exception as e:
            self.logger.error(f"查询单条记录失败: {e}")
            self.logger.error(f"SQL: {sql}, 参数: {params}")
            self.logger.error(traceback.format_exc())
            raise
        finally:
            if connection:
                connection.close()
    
    def execute(self, sql, params=None):
        """执行更新语句并返回影响行数"""
        connection = None
        try:
            connection = self._get_connection()
            if not connection:
                raise Exception("无法建立数据库连接")
            
            with connection.cursor() as cursor:
                affected_rows = cursor.execute(sql, params)
                connection.commit()
                return affected_rows
        except Exception as e:
            self.logger.error(f"执行SQL失败: {e}")
            self.logger.error(f"SQL: {sql}, 参数: {params}")
            self.logger.error(traceback.format_exc())
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()
    
    def initialize_database(self):
        """初始化数据库，创建必要的表"""
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
            # 执行基础SQL初始化脚本
            sql_files = [
                os.path.join(base_dir, 'sql', 'schema.sql'),
                os.path.join(base_dir, 'sql', 'templates.sql'),  # 添加模板相关SQL脚本
                os.path.join(base_dir, 'sql', 'create_apikeys_table.sql')  # 添加API密钥表SQL脚本
            ]
            
            for sql_file in sql_files:
                if os.path.exists(sql_file):
                    self.logger.info(f"执行SQL脚本: {sql_file}")
                    with open(sql_file, 'r') as f:
                        sql_script = f.read()
                    
                    # 按分号分割SQL语句
                    statements = sql_script.split(';')
                    for statement in statements:
                        if statement.strip():
                            self.execute(statement)
                else:
                    self.logger.warning(f"SQL文件不存在: {sql_file}")
            
            self.logger.info("数据库初始化成功")
        except Exception as e:
            self.logger.error(f"初始化数据库失败: {e}")
            self.logger.error(traceback.format_exc()) 