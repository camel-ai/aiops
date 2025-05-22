import logging
from flask import request, jsonify
import jwt
import datetime
# 使用相对导入
from db.db import get_db
from config.config import Config

class AuthController:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def register(self):
        """处理用户注册请求"""
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")
        department = data.get("department", "未指定")  # 获取部门信息，默认值为"未指定"

        if not username or not password:
            return jsonify({"error": "用户名和密码不能为空"}), 400

        try:
            db = get_db()
            cursor = db.cursor()
            # 检查用户名是否已存在
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return jsonify({"error": "用户名已存在"}), 409
            
            # 只包含username、password和department字段
            cursor.execute("INSERT INTO users (username, password, department) VALUES (%s, %s, %s)", 
                          (username, password, department))
            db.commit()
            self.logger.info(f"用户 {username} 注册成功，部门: {department}")
            return jsonify({"message": "注册成功"}), 201
        except Exception as e:
            self.logger.error(f"注册失败: {str(e)}")
            return jsonify({"error": "注册失败", "detail": str(e)}), 500
        finally:
            if cursor:
                cursor.close()

    def login(self):
        """处理用户登录请求"""
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "用户名和密码不能为空"}), 400

        try:
            db = get_db()
            cursor = db.cursor()
            # TODO: 密码应该进行哈希比较
            cursor.execute("SELECT id, username FROM users WHERE username = %s AND password = %s", (username, password))
            user = cursor.fetchone()

            if user:
                # 生成JWT令牌
                payload = {
                    "user_id": user["id"],
                    "username": user["username"],
                    "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=self.config.jwt_expires)
                }
                token = jwt.encode(payload, self.config.jwt_secret, algorithm="HS256")
                self.logger.info(f"用户 {username} 登录成功")
                return jsonify({"token": token, "message": "登录成功"})
            else:
                self.logger.warning(f"用户 {username} 登录失败：用户名或密码错误")
                return jsonify({"error": "用户名或密码错误"}), 401
        except Exception as e:
            self.logger.error(f"登录失败: {str(e)}")
            return jsonify({"error": "登录失败", "detail": str(e)}), 500
        finally:
            if cursor:
                cursor.close()

