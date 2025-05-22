import pymysql
import logging

# 使用相对导入 (从 backend 包的根目录开始)
from config.config import Config

db_connection = None

def init_db(config: Config):
    """初始化数据库连接"""
    global db_connection
    try:
        db_connection = pymysql.connect(
            host=config.db_host,
            user=config.db_user,
            password=config.db_password,
            database=config.db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        logging.info("数据库连接成功")
        return None
    except pymysql.MySQLError as e:
        logging.error(f"数据库连接失败: {e}")
        db_connection = None
        return str(e)

def get_db():
    """获取数据库连接"""
    global db_connection
    if db_connection is None:
        logging.error("数据库未连接")
        raise Exception("数据库未连接")
    try:
        # 检查连接是否仍然有效
        db_connection.ping(reconnect=True)
    except pymysql.MySQLError:
        logging.warning("数据库连接丢失，尝试重新连接...")
        # 尝试重新加载配置并重新连接（这部分可能需要更健壮的实现）
        # 使用相对导入
        from ..config.config import load_config
        config = load_config()
        init_db(config)
        if db_connection is None:
            logging.error("重新连接数据库失败")
            raise Exception("重新连接数据库失败")
        logging.info("数据库重新连接成功")
        
    return db_connection

def close_db():
    """关闭数据库连接"""
    global db_connection
    if db_connection:
        db_connection.close()
        db_connection = None
        logging.info("数据库连接已关闭")

