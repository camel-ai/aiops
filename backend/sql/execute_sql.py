import mysql.connector
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config

def execute_sql_commands():
    """执行SQL命令添加新字段"""
    
    # SQL命令
    sql_commands = [
        "ALTER TABLE `cloud` ADD COLUMN `iamid` VARCHAR(255) COMMENT 'IAM用户ID' AFTER `iam_user`;",
        "ALTER TABLE `cloud` ADD COLUMN `iamarn` VARCHAR(255) COMMENT 'IAM用户ARN' AFTER `iamid`;"
    ]
    
    # 连接数据库
    connection = None
    cursor = None
    try:
        connection = mysql.connector.connect(
            host=config.DB_HOST,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME
        )
        
        cursor = connection.cursor()
        
        # 执行每个SQL命令
        for cmd in sql_commands:
            try:
                print(f"正在执行: {cmd}")
                cursor.execute(cmd)
                print("执行成功")
            except mysql.connector.Error as err:
                # 如果错误是因为列已存在，则忽略
                if "Duplicate column name" in str(err) or "already exists" in str(err):
                    print(f"列已存在，跳过: {err}")
                else:
                    print(f"执行出错: {err}")
        
        # 提交更改
        connection.commit()
        print("所有SQL命令执行完毕")
        
    except mysql.connector.Error as err:
        print(f"数据库连接出错: {err}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

if __name__ == "__main__":
    execute_sql_commands() 