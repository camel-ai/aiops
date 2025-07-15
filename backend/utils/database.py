import pymysql
import logging
from config.config import Config

def get_db_connection():
    """获取数据库连接"""
    config = Config()
    logger = logging.getLogger(__name__)
    
    try:
        connection = pymysql.connect(
            host=config.db_host,
            user=config.db_user,
            password=config.db_password,
            database=config.db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
        return connection
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        raise 