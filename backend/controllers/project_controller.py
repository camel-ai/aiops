import logging
from flask import request, jsonify
# 使用相对导入
from db.db import get_db

class ProjectController:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def create_project(self):
        """处理创建项目请求"""
        data = request.get_json()
        name = data.get("name")
        description = data.get("description")
        user_id = request.user_id # 从中间件获取用户ID
        username = request.username # 从中间件获取用户名

        if not name:
            return jsonify({"error": "项目名称不能为空"}), 400

        try:
            db = get_db()
            cursor = db.cursor()
            # 将created_by设置为username，现在该字段存储用户名而非用户ID
            cursor.execute("INSERT INTO projects (name, description, user_id, created_by) VALUES (%s, %s, %s, %s)", 
                           (name, description, user_id, username))
            db.commit()
            project_id = cursor.lastrowid
            self.logger.info(f"项目 {name} (ID: {project_id}) 创建成功，用户 ID: {user_id}，创建人: {username}")
            return jsonify({"message": "项目创建成功", "project_id": project_id}), 201
        except Exception as e:
            self.logger.error(f"创建项目失败: {str(e)}")
            return jsonify({"error": "创建项目失败", "detail": str(e)}), 500
        finally:
            if cursor:
                cursor.close()

    def get_all_projects(self):
        """获取用户的所有项目"""
        user_id = request.user_id # 从中间件获取用户ID
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id, name, description, created_at FROM projects WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
            projects = cursor.fetchall()
            self.logger.info(f"为用户 ID {user_id} 获取了 {len(projects)} 个项目")
            return jsonify({"projects": projects})
        except Exception as e:
            self.logger.error(f"获取项目列表失败: {str(e)}")
            return jsonify({"error": "获取项目列表失败", "detail": str(e), "projects": []}), 500
        finally:
            if cursor:
                cursor.close()

    def get_project(self, project_id):
        """获取单个项目详情"""
        user_id = request.user_id # 从中间件获取用户ID
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id, name, description, created_at FROM projects WHERE id = %s AND user_id = %s", (project_id, user_id))
            project = cursor.fetchone()
            if project:
                self.logger.info(f"获取项目详情成功，项目 ID: {project_id}，用户 ID: {user_id}")
                return jsonify({"project": project})
            else:
                self.logger.warning(f"项目 ID {project_id} 未找到或用户 ID {user_id} 无权访问")
                return jsonify({"error": "项目未找到或无权访问"}), 404
        except Exception as e:
            self.logger.error(f"获取项目详情失败: {str(e)}")
            return jsonify({"error": "获取项目详情失败", "detail": str(e)}), 500
        finally:
            if cursor:
                cursor.close()

