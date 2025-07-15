import pymysql
import sys
import os
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 获取当前脚本所在目录的父目录
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

from config.config import load_config

def execute_sql_file(sql_command, config):
    """执行SQL命令"""
    connection = None
    try:
        # 连接到数据库
        connection = pymysql.connect(
            host=config.db_host,
            user=config.db_user,
            password=config.db_password,
            database=config.db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # 执行SQL命令
            logger.info(f"执行SQL: {sql_command}")
            cursor.execute(sql_command)
            connection.commit()
            logger.info("SQL执行成功")
        
    except Exception as e:
        logger.error(f"执行SQL时出错: {e}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()
    
    return True

def update_projects_table():
    """修改projects表的created_by字段"""
    # 加载配置
    config = load_config()
    
    try:
        # 检查system_logs表是否存在，如果不存在则创建
        create_logs_table_sql = """
        CREATE TABLE IF NOT EXISTS `system_logs` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `message` text NOT NULL,
            `created_at` datetime NOT NULL,
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        execute_sql_file(create_logs_table_sql, config)
        
        # 先删除外键约束
        drop_fk_sql = "ALTER TABLE `projects` DROP FOREIGN KEY `projects_ibfk_1`;"
        execute_sql_file(drop_fk_sql, config)
        
        # 修改created_by字段类型
        modify_column_sql = "ALTER TABLE `projects` MODIFY COLUMN `created_by` VARCHAR(50) COMMENT '创建人用户名';"
        execute_sql_file(modify_column_sql, config)
        
        # 添加日志
        log_sql = "INSERT INTO `system_logs` (`message`, `created_at`) VALUES ('已将projects表的created_by字段从用户ID外键修改为用户名字符串', NOW());"
        execute_sql_file(log_sql, config)
        
        logger.info("成功修改projects表结构")
        return True
    except Exception as e:
        logger.error(f"修改projects表结构时出错: {e}")
        return False

def main():
    # 加载配置
    config = load_config()
    
    # 从users表中删除project字段的SQL命令
    sql_command = "ALTER TABLE `users` DROP COLUMN `project`;"
    
    # 执行SQL命令
    if execute_sql_file(sql_command, config):
        logger.info("成功从users表中删除project字段")
    else:
        logger.error("无法从users表中删除project字段")
    
    # 修改projects表结构
    update_projects_table()

if __name__ == "__main__":
    main() 