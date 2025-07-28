import os
import sys
import logging
import traceback
from flask import request, jsonify, current_app

# 获取当前脚本所在目录的父目录（backend）
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from db.database import Database

class ApiKeyController:
    def __init__(self, config=None):
        """初始化API密钥控制器"""
        self.db = Database(config)
        self.logger = logging.getLogger(__name__)
    
    def add_api_key(self):
        """添加新的API密钥"""
        try:
            # 获取请求数据
            data = request.get_json()
            if not data:
                return jsonify({"error": "请提供API密钥信息"}), 400
            
            # 获取当前用户信息
            current_user = request.current_user
            if not current_user:
                return jsonify({"error": "未获取到用户信息"}), 401
            
            # 验证必需字段
            required_fields = ['apikey_name', 'cloud', 'ak', 'sk']
            for field in required_fields:
                if field not in data or not data[field]:
                    return jsonify({"error": f"请提供 {field} 字段"}), 400
            
            # 准备插入数据
            # 在JWT验证中，用户ID字段名为user_id而不是id
            user_id = current_user.get('user_id')
            username = current_user.get('username')
            
            # 确保获取到用户ID
            if not user_id:
                self.logger.error(f"未获取到用户ID，current_user: {current_user}")
                return jsonify({"error": "未获取到有效的用户ID"}), 401
            
            apikey_name = data.get('apikey_name')
            cloud = data.get('cloud')
            ak = data.get('ak')
            sk = data.get('sk')
            remark = data.get('remark', '')
            
            # 检查是否已存在同名API密钥
            check_sql = """
                SELECT * FROM api_keys 
                WHERE userid = %s AND apikey_name = %s AND cloud = %s
            """
            existing_key = self.db.query_one(check_sql, (user_id, apikey_name, cloud))
            
            if existing_key:
                return jsonify({"error": f"同名API密钥已存在: {apikey_name}"}), 409
            
            # 插入数据
            insert_sql = """
                INSERT INTO api_keys (userid, username, apikey_name, cloud, ak, sk, remark)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            self.db.execute(insert_sql, (user_id, username, apikey_name, cloud, ak, sk, remark))
            
            return jsonify({"message": "API密钥添加成功", "success": True}), 201
            
        except Exception as e:
            self.logger.error(f"添加API密钥失败: {e}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": "添加API密钥失败", "detail": str(e)}), 500
    
    def get_api_keys(self):
        """获取当前用户的所有API密钥"""
        try:
            # 获取当前用户信息
            current_user = request.current_user
            if not current_user:
                return jsonify({"error": "未获取到用户信息"}), 401
            
            # 在JWT验证中，用户ID字段名为user_id而不是id
            user_id = current_user.get('user_id')
            
            # 确保获取到用户ID
            if not user_id:
                self.logger.error(f"未获取到用户ID，current_user: {current_user}")
                return jsonify({"error": "未获取到有效的用户ID"}), 401
            
            # 查询用户的API密钥
            query_sql = """
                SELECT id, apikey_name, cloud, ak, sk, remark, createtime
                FROM api_keys
                WHERE userid = %s
                ORDER BY createtime DESC
            """
            api_keys = self.db.query(query_sql, (user_id,))
            
            # 格式化日期时间
            for key in api_keys:
                if 'createtime' in key and key['createtime']:
                    key['createtime'] = key['createtime'].strftime('%Y-%m-%d %H:%M:%S')
            
            return jsonify({"keys": api_keys, "success": True}), 200
            
        except Exception as e:
            self.logger.error(f"获取API密钥列表失败: {e}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": "获取API密钥列表失败", "detail": str(e)}), 500
    
    def update_api_key(self, key_id):
        """更新指定的API密钥"""
        try:
            # 获取请求数据
            data = request.get_json()
            if not data:
                return jsonify({"error": "请提供API密钥更新信息"}), 400
            
            # 获取当前用户信息
            current_user = request.current_user
            if not current_user:
                return jsonify({"error": "未获取到用户信息"}), 401
            
            # 在JWT验证中，用户ID字段名为user_id而不是id
            user_id = current_user.get('user_id')
            
            # 确保获取到用户ID
            if not user_id:
                self.logger.error(f"未获取到用户ID，current_user: {current_user}")
                return jsonify({"error": "未获取到有效的用户ID"}), 401
            
            # 检查API密钥是否存在且属于当前用户
            check_sql = "SELECT * FROM api_keys WHERE id = %s AND userid = %s"
            existing_key = self.db.query_one(check_sql, (key_id, user_id))
            
            if not existing_key:
                return jsonify({"error": "API密钥不存在或无权限操作"}), 404
            
            # 准备更新数据
            update_fields = []
            update_values = []
            
            if 'apikey_name' in data and data['apikey_name']:
                update_fields.append("apikey_name = %s")
                update_values.append(data['apikey_name'])
            
            if 'cloud' in data and data['cloud']:
                update_fields.append("cloud = %s")
                update_values.append(data['cloud'])
            
            if 'ak' in data and data['ak']:
                update_fields.append("ak = %s")
                update_values.append(data['ak'])
            
            if 'sk' in data and data['sk']:
                update_fields.append("sk = %s")
                update_values.append(data['sk'])
            
            if 'remark' in data:
                update_fields.append("remark = %s")
                update_values.append(data['remark'])
            
            if not update_fields:
                return jsonify({"error": "未提供任何要更新的字段"}), 400
            
            # 构建更新SQL
            update_sql = f"UPDATE api_keys SET {', '.join(update_fields)} WHERE id = %s AND userid = %s"
            update_values.extend([key_id, user_id])
            
            # 执行更新
            self.db.execute(update_sql, update_values)
            
            return jsonify({"message": "API密钥更新成功", "success": True}), 200
            
        except Exception as e:
            self.logger.error(f"更新API密钥失败: {e}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": "更新API密钥失败", "detail": str(e)}), 500
    
    def delete_api_key(self, key_id):
        """删除指定的API密钥"""
        try:
            # 获取当前用户信息
            current_user = request.current_user
            if not current_user:
                return jsonify({"error": "未获取到用户信息"}), 401
            
            # 在JWT验证中，用户ID字段名为user_id而不是id
            user_id = current_user.get('user_id')
            
            # 确保获取到用户ID
            if not user_id:
                self.logger.error(f"未获取到用户ID，current_user: {current_user}")
                return jsonify({"error": "未获取到有效的用户ID"}), 401
            
            # 检查API密钥是否存在且属于当前用户
            check_sql = "SELECT * FROM api_keys WHERE id = %s AND userid = %s"
            existing_key = self.db.query_one(check_sql, (key_id, user_id))
            
            if not existing_key:
                return jsonify({"error": "API密钥不存在或无权限操作"}), 404
            
            # 删除API密钥
            delete_sql = "DELETE FROM api_keys WHERE id = %s AND userid = %s"
            self.db.execute(delete_sql, (key_id, user_id))
            
            return jsonify({"message": "API密钥删除成功", "success": True}), 200
            
        except Exception as e:
            self.logger.error(f"删除API密钥失败: {e}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": "删除API密钥失败", "detail": str(e)}), 500
    
    def get_api_key_by_id(self, key_id):
        """根据ID获取API密钥详情
        
        Args:
            key_id: API密钥ID
            
        Returns:
            dict: API密钥信息，如果不存在则返回None
        """
        try:
            # 查询API密钥
            query_sql = """
                SELECT id, apikey_name, cloud, ak, sk, remark, createtime
                FROM api_keys
                WHERE id = %s
            """
            api_key = self.db.query_one(query_sql, (key_id,))
            
            # 格式化日期时间
            if api_key and 'createtime' in api_key and api_key['createtime']:
                api_key['createtime'] = api_key['createtime'].strftime('%Y-%m-%d %H:%M:%S')
            
            return api_key
            
        except Exception as e:
            self.logger.error(f"获取API密钥详情失败: {e}")
            self.logger.error(traceback.format_exc())
            return None 