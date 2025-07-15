#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试数据库连接和查询功能
"""

import os
import sys
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 获取当前脚本所在目录的父目录（backend）的父目录（项目根目录）
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_dir = os.path.dirname(backend_dir)
sys.path.append(project_dir)

# 导入数据库类
from db.database import Database
from config.config import Config

def test_connection():
    """测试数据库连接"""
    logger.info("开始测试数据库连接...")
    db = Database()
    
    try:
        # 测试简单查询
        result = db.query("SELECT 1 as test")
        logger.info(f"查询结果: {result}")
        
        # 测试表是否存在
        tables = db.query("SHOW TABLES")
        logger.info(f"数据库中的表: {tables}")
        
        # 检查templates表是否存在
        templates_exists = False
        for table in tables:
            table_name = list(table.values())[0]
            if table_name == 'templates':
                templates_exists = True
                break
        
        if templates_exists:
            logger.info("templates表存在")
            # 查询templates表结构
            columns = db.query("DESCRIBE templates")
            logger.info(f"templates表结构: {columns}")
            
            # 查询templates表数据
            templates = db.query("SELECT * FROM templates LIMIT 5")
            logger.info(f"templates表中的记录数: {len(templates)}")
            logger.info(f"示例记录: {templates[:2]}")
        else:
            logger.warning("templates表不存在，尝试创建")
            # 创建templates表
            with open(os.path.join(backend_dir, 'sql', 'templates.sql'), 'r') as f:
                sql_script = f.read()
            
            # 按分号分割SQL语句
            statements = sql_script.split(';')
            for statement in statements:
                if statement.strip():
                    logger.info(f"执行SQL: {statement.strip()}")
                    db.execute(statement)
            
            logger.info("templates表创建成功")
        
        return True
    except Exception as e:
        logger.error(f"测试失败: {e}")
        return False

if __name__ == "__main__":
    if test_connection():
        logger.info("数据库连接测试成功!")
    else:
        logger.error("数据库连接测试失败!") 