import os
import uuid
import json
import logging
import traceback
from datetime import datetime
from flask import jsonify, request, send_file
from werkzeug.utils import secure_filename

# 基础路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
TEMPLATE_UPLOADS_DIR = os.path.join(TEMPLATES_DIR, 'uploads')
TERRAFORM_SCRIPTS_DIR = os.path.join(TEMPLATES_DIR, 'terraform')

# 确保目录存在
os.makedirs(TEMPLATE_UPLOADS_DIR, exist_ok=True)
os.makedirs(TERRAFORM_SCRIPTS_DIR, exist_ok=True)

class TemplateController:
    def __init__(self, config=None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 初始化数据库连接
        if config and hasattr(config, 'db'):
            self.db = config.db
        else:
            from db.database import Database
            self.db = Database()
        
        # 初始化部署执行器
        from controllers.deploy_controller import DeployController
        self.deploy_controller = DeployController(config)
    
    def _get_user_id(self):
        """获取当前用户ID的辅助方法"""
        user_id = None
        
        # 首先尝试从request.current_user中获取用户ID
        if hasattr(request, 'current_user'):
            if isinstance(request.current_user, dict):
                user_id = request.current_user.get('user_id') or request.current_user.get('id')
            else:
                # 如果不是字典，尝试获取属性
                user_id = getattr(request.current_user, 'user_id', None) or getattr(request.current_user, 'id', None)
        
        # 如果上面的方式未获取到用户ID，则从Authorization头中提取
        if not user_id:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                # 使用工具函数解析token
                from utils.auth import decode_token
                payload = decode_token(token)
                if payload:
                    user_id = payload.get('user_id')
        
        return user_id
        
    def _get_username(self):
        """获取当前用户名的辅助方法"""
        username = None
        
        # 首先尝试从request.current_user中获取用户名
        if hasattr(request, 'current_user'):
            if isinstance(request.current_user, dict):
                username = request.current_user.get('username')
            else:
                # 如果不是字典，尝试获取属性
                username = getattr(request.current_user, 'username', None)
        
        # 如果上面的方式未获取到用户名，则从Authorization头中提取
        if not username:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                # 使用工具函数解析token
                from utils.auth import decode_token
                payload = decode_token(token)
                if payload:
                    username = payload.get('username')
        
        return username
    
    def get_all_templates(self):
        """获取当前用户的所有模板"""
        try:
            # 使用辅助方法获取用户ID
            user_id = self._get_user_id()
            
            # 如果无法获取用户ID，返回错误
            if not user_id:
                self.logger.error("无法获取用户ID，request.current_user: " + str(getattr(request, 'current_user', None)))
                return jsonify({"error": "未获取到用户ID", "success": False}), 400
            
            # 记录用户ID，帮助调试
            self.logger.info(f"获取模板列表，用户ID: {user_id}")
            
            # 处理可能的数据库连接错误
            try:
                # 先尝试简单查询验证连接
                test_query = "SELECT 1"
                self.db.query(test_query)
            except Exception as db_error:
                self.logger.error(f"数据库连接测试失败: {str(db_error)}")
                # 如果是部署环境，返回一个友好的错误信息
                # 在测试环境中，可以返回更详细的错误信息以便调试
                return jsonify({
                    "error": "数据库连接失败，请检查数据库配置或联系管理员", 
                    "success": False,
                    "templates": [],  # 返回空列表，避免前端解析错误
                    "debug_info": {
                        "message": str(db_error),
                        "stack_trace": traceback.format_exc()
                    }
                }), 500
            
            # 验证表是否存在
            try:
                # 检查templates表是否存在
                table_query = "SHOW TABLES LIKE 'templates'"
                tables = self.db.query(table_query)
                
                # 如果表不存在，尝试创建
                if not tables:
                    self.logger.warning("templates表不存在，尝试创建...")
                    try:
                        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        templates_sql_path = os.path.join(base_dir, 'sql', 'templates.sql')
                        
                        if os.path.exists(templates_sql_path):
                            self.logger.info(f"执行SQL脚本: {templates_sql_path}")
                            with open(templates_sql_path, 'r') as f:
                                sql_script = f.read()
                            
                            # 按分号分割SQL语句
                            statements = sql_script.split(';')
                            for statement in statements:
                                if statement.strip():
                                    self.db.execute(statement)
                            
                            self.logger.info("templates表创建成功")
                        else:
                            self.logger.error(f"SQL文件不存在: {templates_sql_path}")
                            return jsonify({
                                "error": "templates表不存在且无法创建", 
                                "success": False,
                                "templates": []  # 返回空列表，避免前端解析错误
                            }), 500
                    except Exception as create_error:
                        self.logger.error(f"创建templates表失败: {str(create_error)}")
                        return jsonify({
                            "error": "创建templates表失败", 
                            "success": False,
                            "templates": [],  # 返回空列表，避免前端解析错误
                            "debug_info": {
                                "message": str(create_error),
                                "stack_trace": traceback.format_exc()
                            }
                        }), 500
            except Exception as table_error:
                self.logger.error(f"检查表失败: {str(table_error)}")
                return jsonify({
                    "error": "检查数据库表结构失败", 
                    "success": False,
                    "templates": [],  # 返回空列表，避免前端解析错误
                    "debug_info": {
                        "message": str(table_error),
                        "stack_trace": traceback.format_exc()
                    }
                }), 500
            
            # 从数据库获取当前用户的所有模板
            try:
                query = "SELECT * FROM templates WHERE user_id = %s ORDER BY created_at DESC"
                templates = self.db.query(query, (user_id,))
                
                # 记录找到的模板数量
                self.logger.info(f"查询到的模板数量: {len(templates) if templates else 0}")
                
                # 即使没有找到模板，也返回成功和空列表
                return jsonify({
                    "success": True,
                    "templates": templates or []
                })
            except Exception as query_error:
                self.logger.error(f"查询模板失败: {str(query_error)}")
                return jsonify({
                    "error": "查询模板数据失败", 
                    "success": False,
                    "templates": [],  # 返回空列表，避免前端解析错误
                    "debug_info": {
                        "message": str(query_error),
                        "stack_trace": traceback.format_exc()
                    }
                }), 500
        except Exception as e:
            self.logger.error(f"获取模板列表失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "error": str(e), 
                "success": False,
                "templates": []  # 返回空列表，避免前端解析错误
            }), 500
    
    def get_template_details(self):
        """获取单个模板的详细信息"""
        try:
            template_id = request.args.get('template_id')
            user_id = self._get_user_id()
            
            if not template_id:
                return jsonify({"error": "未提供模板ID", "success": False}), 400
            
            if not user_id:
                return jsonify({"error": "未获取到用户ID", "success": False}), 400
            
            # 查询模板信息
            query = "SELECT * FROM templates WHERE id = %s AND user_id = %s"
            template = self.db.query_one(query, (template_id, user_id))
            
            if not template:
                return jsonify({"error": "未找到模板或无权访问", "success": False}), 404
            
            # 读取terraform脚本
            terraform_path = os.path.join(TERRAFORM_SCRIPTS_DIR, f"{template['id']}.tf")
            terraform_content = ""
            if os.path.exists(terraform_path):
                with open(terraform_path, 'r') as f:
                    terraform_content = f.read()
            
            # 构建返回数据
            template['terraform_content'] = terraform_content
            
            return jsonify({
                "success": True,
                "template": template
            })
        except Exception as e:
            self.logger.error(f"获取模板详情失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": str(e), "success": False}), 500
    
    def add_template(self):
        """添加新模板"""
        try:
            # 获取用户信息
            user_id = self._get_user_id()
            username = self._get_username()
            
            if not user_id:
                return jsonify({"error": "未获取到用户ID", "success": False}), 400
            
            # 获取表单数据
            data = request.form
            template_name = data.get('template_name')
            template_description = data.get('template_description', '')
            
            if not template_name:
                return jsonify({"error": "模板名称不能为空", "success": False}), 400
            
            # 获取上传的文件
            topology_image = request.files.get('topology_image')
            terraform_file = request.files.get('terraform_file')
            
            if not terraform_file:
                return jsonify({"error": "必须上传Terraform脚本文件", "success": False}), 400
            
            # 生成唯一模板ID
            template_id = str(uuid.uuid4())
            
            # 保存拓扑图
            topology_filename = None
            if topology_image:
                # 安全处理文件名
                original_filename = secure_filename(topology_image.filename)
                ext = os.path.splitext(original_filename)[1]
                topology_filename = f"{template_id}{ext}"
                topology_path = os.path.join(TEMPLATE_UPLOADS_DIR, topology_filename)
                topology_image.save(topology_path)
            
            # 保存Terraform脚本
            terraform_content = terraform_file.read().decode('utf-8')
            terraform_path = os.path.join(TERRAFORM_SCRIPTS_DIR, f"{template_id}.tf")
            with open(terraform_path, 'w') as f:
                f.write(terraform_content)
            
            # 将模板信息保存到数据库
            insert_query = """
                INSERT INTO templates (
                    id, user_id, username, template_name, description, 
                    topology_image, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """
            
            self.db.execute(
                insert_query, 
                (template_id, user_id, username, template_name, template_description, topology_filename)
            )
            
            return jsonify({
                "success": True,
                "message": "模板添加成功",
                "template_id": template_id
            })
        except Exception as e:
            self.logger.error(f"添加模板失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": str(e), "success": False}), 500
    
    def delete_template(self):
        """删除模板"""
        try:
            template_id = request.json.get('template_id')
            user_id = self._get_user_id()
            
            if not user_id:
                return jsonify({"error": "未获取到用户ID", "success": False}), 400
            
            # 查询模板信息
            query = "SELECT * FROM templates WHERE id = %s AND user_id = %s"
            template = self.db.query_one(query, (template_id, user_id))
            
            if not template:
                return jsonify({"error": "未找到模板或无权删除", "success": False}), 404
            
            # 删除模板文件
            if template.get('topology_image'):
                topology_path = os.path.join(TEMPLATE_UPLOADS_DIR, template['topology_image'])
                if os.path.exists(topology_path):
                    os.remove(topology_path)
            
            terraform_path = os.path.join(TERRAFORM_SCRIPTS_DIR, f"{template_id}.tf")
            if os.path.exists(terraform_path):
                os.remove(terraform_path)
            
            # 从数据库删除模板
            delete_query = "DELETE FROM templates WHERE id = %s AND user_id = %s"
            self.db.execute(delete_query, (template_id, user_id))
            
            return jsonify({
                "success": True,
                "message": "模板删除成功"
            })
        except Exception as e:
            self.logger.error(f"删除模板失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": str(e), "success": False}), 500
    
    def update_template(self):
        """更新模板"""
        try:
            # 获取用户信息
            user_id = self._get_user_id()
            username = self._get_username()
            
            if not user_id:
                return jsonify({"error": "未获取到用户ID", "success": False}), 400
            
            # 获取表单数据
            data = request.form
            template_id = data.get('template_id')
            template_name = data.get('template_name')
            template_description = data.get('template_description', '')
            
            if not template_id:
                return jsonify({"error": "模板ID不能为空", "success": False}), 400
                
            if not template_name:
                return jsonify({"error": "模板名称不能为空", "success": False}), 400
            
            # 查询模板信息，确保用户有权限更新这个模板
            query = "SELECT * FROM templates WHERE id = %s AND user_id = %s"
            template = self.db.query_one(query, (template_id, user_id))
            
            if not template:
                return jsonify({"error": "未找到模板或无权更新", "success": False}), 404
            
            # 获取上传的文件
            topology_image = request.files.get('topology_image')
            terraform_file = request.files.get('terraform_file')
            
            # 更新拓扑图
            topology_filename = template.get('topology_image')  # 保留原值
            if topology_image:
                # 删除旧图像文件（如果存在）
                if topology_filename:
                    old_path = os.path.join(TEMPLATE_UPLOADS_DIR, topology_filename)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # 保存新图像
                original_filename = secure_filename(topology_image.filename)
                ext = os.path.splitext(original_filename)[1]
                topology_filename = f"{template_id}{ext}"
                topology_path = os.path.join(TEMPLATE_UPLOADS_DIR, topology_filename)
                topology_image.save(topology_path)
            
            # 更新Terraform脚本
            if terraform_file:
                terraform_content = terraform_file.read().decode('utf-8')
                terraform_path = os.path.join(TERRAFORM_SCRIPTS_DIR, f"{template_id}.tf")
                with open(terraform_path, 'w') as f:
                    f.write(terraform_content)
            
            # 更新数据库记录
            update_query = """
                UPDATE templates 
                SET template_name = %s, description = %s, 
                    topology_image = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
            """
            
            self.db.execute(
                update_query, 
                (template_name, template_description, topology_filename, template_id, user_id)
            )
            
            return jsonify({
                "success": True,
                "message": "模板更新成功",
                "template_id": template_id
            })
        except Exception as e:
            self.logger.error(f"更新模板失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": str(e), "success": False}), 500
    
    def get_template_image(self):
        """获取模板拓扑图"""
        try:
            template_id = request.args.get('template_id')
            image_name = request.args.get('image_name')
            
            if not template_id or not image_name:
                return jsonify({"error": "参数不完整", "success": False}), 400
            
            # 构建图片路径
            image_path = os.path.join(TEMPLATE_UPLOADS_DIR, image_name)
            
            # 检查文件是否存在
            if not os.path.exists(image_path):
                self.logger.error(f"图片文件不存在: {image_path}")
                return jsonify({"error": "图片不存在", "success": False}), 404
            
            # 返回图片文件，设置缓存控制
            response = send_file(image_path)
            response.headers['Cache-Control'] = 'max-age=86400'  # 缓存1天
            return response
        except Exception as e:
            self.logger.error(f"获取模板图片失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": str(e), "success": False}), 500
    
    def get_templates_for_chat(self):
        """获取当前用户的模板列表，用于聊天中选择"""
        try:
            user_id = self._get_user_id()
            
            if not user_id:
                return jsonify({"error": "未获取到用户ID", "success": False}), 400
            
            # 查询用户模板
            query = """
                SELECT id, template_name, description, topology_image, created_at
                FROM templates
                WHERE user_id = %s
                ORDER BY created_at DESC
            """
            templates = self.db.query(query, (user_id,))
            
            # 添加图片URL
            for template in templates:
                if template.get('topology_image'):
                    template['image_url'] = f"/api/template/image?template_id={template['id']}&image_name={template['topology_image']}"
                else:
                    template['image_url'] = None
            
            return jsonify({
                "success": True,
                "templates": templates,
                "reply": "请选择要部署的模板:",
                "template_selection": True
            })
        except Exception as e:
            self.logger.error(f"获取模板列表失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": str(e),
                "reply": f"获取模板列表失败: {str(e)}"
            })
    
    def get_template_terraform(self):
        """获取模板的Terraform内容"""
        try:
            template_id = request.json.get('template_id')
            
            if not template_id:
                return jsonify({"error": "未提供模板ID", "success": False}), 400
            
            # 读取terraform脚本
            terraform_path = os.path.join(TERRAFORM_SCRIPTS_DIR, f"{template_id}.tf")
            
            if not os.path.exists(terraform_path):
                return jsonify({"error": "Terraform脚本不存在", "success": False}), 404
            
            with open(terraform_path, 'r') as f:
                terraform_content = f.read()
            
            # 查询模板信息
            query = "SELECT template_name, description FROM templates WHERE id = %s"
            template = self.db.query_one(query, (template_id,))
            
            if not template:
                return jsonify({"error": "未找到模板信息", "success": False}), 404
            
            return jsonify({
                "success": True,
                "template_id": template_id,
                "template_name": template.get('template_name'),
                "description": template.get('description'),
                "terraform_content": terraform_content,
                "show_confirm_deploy": True,
                "reply": f"以下是模板 '{template.get('template_name')}' 的Terraform脚本，请确认是否部署:"
            })
        except Exception as e:
            self.logger.error(f"获取模板Terraform内容失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": str(e),
                "reply": f"获取模板Terraform内容失败: {str(e)}"
            })
    
    def update_template_terraform(self):
        """更新模板的Terraform脚本内容"""
        try:
            data = request.json
            template_id = data.get('template_id')
            terraform_content = data.get('terraform_content')
            
            if not template_id:
                return jsonify({"error": "未提供模板ID", "success": False}), 400
                
            if not terraform_content:
                return jsonify({"error": "未提供Terraform脚本内容", "success": False}), 400
                
            # 查询模板信息确认存在
            query = "SELECT template_name FROM templates WHERE id = %s"
            template = self.db.query_one(query, (template_id,))
            
            if not template:
                return jsonify({"error": "未找到模板信息", "success": False}), 404
                
            # 更新terraform脚本文件
            terraform_path = os.path.join(TERRAFORM_SCRIPTS_DIR, f"{template_id}.tf")
            
            with open(terraform_path, 'w') as f:
                f.write(terraform_content)
                
            return jsonify({
                "success": True,
                "message": "Terraform脚本更新成功",
                "template_id": template_id,
                "template_name": template.get('template_name')
            })
        except Exception as e:
            self.logger.error(f"更新模板Terraform内容失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": str(e),
                "message": f"更新模板Terraform内容失败: {str(e)}"
            })
    
    def deploy_template(self):
        """根据模板部署资源"""
        try:
            # 获取请求数据
            data = request.json
            template_id = data.get('template_id')
            
            if not template_id:
                return jsonify({"error": "未提供模板ID", "success": False}), 400
            
            # 获取用户信息
            user_id = self._get_user_id()
            username = self._get_username()
            
            self.logger.info(f"开始模板部署: 模板ID={template_id}, 用户ID={user_id}")
            
            # 查询模板信息
            query = "SELECT * FROM templates WHERE id = %s"
            template = self.db.query_one(query, (template_id,))
            
            if not template:
                return jsonify({"error": "未找到模板", "success": False}), 404
            
            # 读取terraform脚本
            terraform_path = os.path.join(TERRAFORM_SCRIPTS_DIR, f"{template_id}.tf")
            
            if not os.path.exists(terraform_path):
                return jsonify({"error": "Terraform脚本不存在", "success": False}), 404
            
            with open(terraform_path, 'r') as f:
                terraform_content = f.read()
            
            # 生成部署ID (DP前缀)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            random_suffix = str(uuid.uuid4())[:8].upper()
            deploy_id = f"DP{timestamp}{random_suffix}"[:18]
            
            self.logger.info(f"生成模板部署ID: {deploy_id}")
            
            # 项目和云平台信息
            project = data.get('project', '默认项目')
            cloud = data.get('cloud', 'AWS')
            region = data.get('region', 'cn-north-1')
            
            # 构建部署请求数据
            deploy_request = {
                'deploy_id': deploy_id,
                'user_id': user_id,
                'username': username,
                'template_id': template_id,
                'template_name': template.get('template_name'),
                'terraform_content': terraform_content,
                'cloud': cloud,
                'project': project,
                'region': region,
                'ak': data.get('ak', ''),
                'sk': data.get('sk', '')
            }
            
            # 预先保存部署记录到数据库，明确设置deploy_type为'template'
            self.logger.info(f"保存模板部署记录到数据库: {deploy_id}, 用户: {user_id}, 模板: {template_id}")
            insert_query = """
                INSERT INTO deployments (
                    deployid, deploy_type, cloud, project, region, 
                    user_id, username, status, created_at, updated_at, template_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s)
            """
            
            self.db.execute(
                insert_query, 
                (
                    deploy_id, 'template', cloud, project, 
                    region, user_id, username, 'in_progress', template_id
                )
            )
            
            # 使用自己的方法处理Terraform部署，而不是调用deploy_controller的方法
            self._execute_terraform_deploy(deploy_request)
            
            # 返回初始响应
            return jsonify({
                "success": True,
                "deploy_id": deploy_id,
                "message": "模板部署已开始",
                "status": "in_progress",
                "resources": self._parse_resources_from_terraform(terraform_content),
                "deploy_status": {
                    "progress": 0,
                    "message": "部署已开始，正在初始化..."
                },
                "reply": f"模板 '{template.get('template_name')}' 的部署已开始，部署ID: {deploy_id}"
            })
        except Exception as e:
            self.logger.error(f"模板部署失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": str(e),
                "reply": f"模板部署失败: {str(e)}"
            })
            
    def _execute_terraform_deploy(self, deploy_request):
        """执行Terraform部署，替代DeployController.execute_terraform_deploy方法"""
        try:
            deploy_id = deploy_request['deploy_id']
            terraform_content = deploy_request['terraform_content']
            
            self.logger.info(f"开始执行Terraform部署，部署ID: {deploy_id}")
            
            # 创建部署目录
            deploy_dir = os.path.join(BASE_DIR, 'deployments', deploy_id)
            os.makedirs(deploy_dir, exist_ok=True)
            
            # 写入Terraform配置文件
            tf_file = os.path.join(deploy_dir, 'main.tf')
            with open(tf_file, 'w') as f:
                f.write(terraform_content)
                
            # 创建状态文件，记录初始状态
            status_file = os.path.join(deploy_dir, 'status.json')
            with open(status_file, 'w') as f:
                json.dump({
                    'status': 'in_progress',
                    'deploy_id': deploy_id,
                    'message': 'Terraform部署已开始',
                    'updated_at': datetime.now().isoformat(),
                    'resources': self._parse_resources_from_terraform(terraform_content),
                    'template_id': deploy_request.get('template_id', ''),
                    'user_id': deploy_request.get('user_id', '1'),
                    'username': deploy_request.get('username', 'admin'),
                    'project': deploy_request.get('project', '默认项目'),
                    'cloud': deploy_request.get('cloud', 'AWS'),
                    'region': deploy_request.get('region', '未指定')
                }, f, indent=2)
                
            # 启动异步部署任务
            import threading
            deploy_thread = threading.Thread(
                target=self._run_terraform_deployment,
                args=(deploy_id, deploy_dir, deploy_request)
            )
            deploy_thread.daemon = True
            deploy_thread.start()
            
            self.logger.info(f"Terraform部署任务已启动，部署ID: {deploy_id}")
            return {'success': True, 'deploy_id': deploy_id}
            
        except Exception as e:
            self.logger.error(f"启动Terraform部署任务失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            # 更新部署状态为失败
            self._update_deployment_status(deploy_id, 'failed', str(e))
            return {'success': False, 'error': str(e)}

    # 显式添加execute_terraform_deploy方法，确保DeployController可以调用
    def execute_terraform_deploy(self, deploy_request):
        """提供兼容DeployController的接口"""
        self.logger.info(f"通过兼容接口execute_terraform_deploy执行部署，部署ID: {deploy_request.get('deploy_id', 'unknown')}")
        return self._execute_terraform_deploy(deploy_request)
    
    def _run_terraform_deployment(self, deploy_id, deploy_dir, deploy_request):
        """运行Terraform部署流程（在单独的线程中执行）"""
        try:
            self.logger.info(f"Terraform部署线程开始，部署ID: {deploy_id}")
            
            # 设置详细日志记录
            deployment_log_file = os.path.join(deploy_dir, 'deployment.log')
            
            def log_message(message, level='INFO'):
                """输出消息到日志文件和控制台"""
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_line = f"[{timestamp}] [{level}] {message}"
                
                # 输出到控制台
                print(log_line)
                
                # 输出到日志文件
                with open(deployment_log_file, 'a') as f:
                    f.write(f"{log_line}\n")
                
                # 同时使用标准logger
                if level == 'INFO':
                    self.logger.info(message)
                elif level == 'ERROR':
                    self.logger.error(message)
                elif level == 'WARNING':
                    self.logger.warning(message)
            
            # 确保日志目录存在
            os.makedirs(os.path.dirname(deployment_log_file), exist_ok=True)
            
            # 初始化日志文件
            with open(deployment_log_file, 'w') as f:
                f.write(f"Terraform部署日志 - 部署ID: {deploy_id}\n")
                f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"项目: {deploy_request.get('project', '未指定')}\n")
                f.write(f"云服务商: {deploy_request.get('cloud', '未指定')}\n")
                f.write(f"区域: {deploy_request.get('region', '未指定')}\n")
                f.write(f"模板ID: {deploy_request.get('template_id', '未指定')}\n")
                f.write("="*80 + "\n\n")
            
            log_message(f"开始Terraform部署 - 部署ID: {deploy_id}")
            log_message(f"部署目录: {deploy_dir}")
            
            # 设置部署状态跟踪
            resources = self._parse_resources_from_terraform(deploy_request['terraform_content'])
            resources_status = []
            
            # 记录识别到的资源数量和详情
            log_message(f"识别到 {len(resources)} 个资源需要部署")
            for resource in resources:
                log_message(f"资源: {resource['type']}.{resource['name']}")
                resources_status.append({
                    'type': resource['type'],
                    'name': resource['name'],
                    'full_name': resource['full_name'],
                    'status': 'pending',
                    'message': '等待部署'
                })
            
            # 保存初始状态，包含模板ID和用户信息
            initial_status = {
                'status': 'in_progress',
                'deploy_id': deploy_id,
                'message': 'Terraform部署已开始',
                'updated_at': datetime.now().isoformat(),
                'resources': resources_status,
                'template_id': deploy_request.get('template_id', ''),
                'user_id': deploy_request.get('user_id', '1'),
                'username': deploy_request.get('username', 'admin'),
                'project': deploy_request.get('project', '默认项目'),
                'cloud': deploy_request.get('cloud', 'AWS'),
                'region': deploy_request.get('region', '未指定')
            }
            
            # 更新状态文件
            status_file = os.path.join(deploy_dir, 'status.json')
            with open(status_file, 'w') as f:
                json.dump(initial_status, f, indent=2)
                
            # 写入Terraform脚本内容到日志
            log_message("Terraform脚本内容:")
            log_message("```")
            for line in deploy_request['terraform_content'].split('\n'):
                log_message(line)
            log_message("```")
            
            # 初始化Terraform工作目录
            tf_file = os.path.join(deploy_dir, 'main.tf')
            tf_init_cmd = f'cd {deploy_dir} && terraform init'
            
            # 执行Terraform初始化
            log_message("开始执行Terraform初始化...")
            self._update_deployment_status(deploy_id, 'in_progress', 'Terraform初始化中')
            init_result = self._execute_command(tf_init_cmd)
            
            # 记录初始化结果
            log_message(f"Terraform初始化执行结果: 退出代码 {init_result['exit_code']}")
            if init_result['stdout']:
                log_message("初始化输出:\n" + init_result['stdout'])
            
            if init_result['exit_code'] != 0:
                # 初始化失败，更新状态并返回
                log_message(f"Terraform初始化失败:\n{init_result['stderr']}", "ERROR")
                self._update_deployment_status(deploy_id, 'failed', f"Terraform初始化失败: {init_result['stderr']}")
                return
            
            log_message("Terraform初始化成功")
            
            # 执行Terraform计划
            log_message("开始执行Terraform计划...")
            self._update_deployment_status(deploy_id, 'in_progress', 'Terraform计划中')
            tf_plan_cmd = f'cd {deploy_dir} && terraform plan -out=tfplan'
            plan_result = self._execute_command(tf_plan_cmd)
            
            # 记录计划结果
            log_message(f"Terraform计划执行结果: 退出代码 {plan_result['exit_code']}")
            if plan_result['stdout']:
                log_message("计划输出:\n" + plan_result['stdout'])
            
            if plan_result['exit_code'] != 0:
                # 计划失败，更新状态并返回
                log_message(f"Terraform计划失败:\n{plan_result['stderr']}", "ERROR")
                self._update_deployment_status(deploy_id, 'failed', f"Terraform计划失败: {plan_result['stderr']}")
                return
            
            log_message("Terraform计划成功")
            
            # 解析计划输出，更新资源状态
            plan_output = plan_result['stdout']
            for i, resource in enumerate(resources_status):
                resources_status[i]['status'] = 'planned'
                resources_status[i]['message'] = '资源已规划，准备部署'
                log_message(f"资源 {resource['type']}.{resource['name']} 已规划，准备部署")
            
            # 更新资源状态
            self._update_resources_status(deploy_id, resources_status)
            
            # 执行Terraform应用
            log_message("开始执行Terraform应用...")
            self._update_deployment_status(deploy_id, 'in_progress', 'Terraform应用中')
            tf_apply_cmd = f'cd {deploy_dir} && terraform apply -auto-approve tfplan'
            apply_result = self._execute_command(tf_apply_cmd)
            
            # 记录应用结果
            log_message(f"Terraform应用执行结果: 退出代码 {apply_result['exit_code']}")
            if apply_result['stdout']:
                log_message("应用输出:\n" + apply_result['stdout'])
            
            if apply_result['exit_code'] != 0:
                # 应用失败，更新状态并返回
                log_message(f"Terraform应用失败:\n{apply_result['stderr']}", "ERROR")
                self._update_deployment_status(deploy_id, 'failed', f"Terraform应用失败: {apply_result['stderr']}")
                
                # 尝试解析错误并更新具体资源的状态
                error_text = apply_result['stderr']
                for i, resource in enumerate(resources_status):
                    if resource['full_name'] in error_text:
                        resources_status[i]['status'] = 'failed'
                        resources_status[i]['message'] = '部署失败'
                        log_message(f"资源 {resource['full_name']} 部署失败", "ERROR")
                
                # 更新资源状态
                self._update_resources_status(deploy_id, resources_status)
                return
            
            log_message("Terraform应用成功")
            
            # 获取Terraform输出
            log_message("获取Terraform输出信息...")
            self._update_deployment_status(deploy_id, 'in_progress', '获取输出信息')
            tf_output_cmd = f'cd {deploy_dir} && terraform output -json'
            output_result = self._execute_command(tf_output_cmd)
            
            # 解析输出结果
            output_data = {}
            if output_result['exit_code'] == 0 and output_result['stdout']:
                try:
                    output_data = json.loads(output_result['stdout'])
                    
                    # 提取值而不是包括整个结构
                    parsed_output = {}
                    for key, value in output_data.items():
                        if isinstance(value, dict) and 'value' in value:
                            parsed_output[key] = value['value']
                        else:
                            parsed_output[key] = value
                    
                    output_data = parsed_output
                    
                    # 记录输出详情
                    log_message("Terraform输出详情:")
                    for key, value in output_data.items():
                        log_message(f"  {key}: {json.dumps(value)}")
                except Exception as e:
                    log_message(f"解析Terraform输出失败: {str(e)}", "ERROR")
                    self.logger.error(f"解析Terraform输出失败: {str(e)}")
            
            # 获取每个资源的状态
            tf_state_cmd = f'cd {deploy_dir} && terraform state list'
            state_result = self._execute_command(tf_state_cmd)
            
            if state_result['exit_code'] == 0:
                # 解析状态列表
                deployed_resources = state_result['stdout'].strip().split('\n')
                log_message(f"已部署资源列表:")
                
                # 更新资源状态
                for deployed_resource in deployed_resources:
                    if not deployed_resource.strip():
                        continue
                    
                    log_message(f"  {deployed_resource}")
                    
                    # 获取单个资源的详细状态
                    tf_resource_cmd = f'cd {deploy_dir} && terraform state show {deployed_resource}'
                    resource_result = self._execute_command(tf_resource_cmd)
                    
                    if resource_result['exit_code'] == 0:
                        # 找到匹配的资源并更新状态
                        for i, resource in enumerate(resources_status):
                            if resource['full_name'] == deployed_resource:
                                resources_status[i]['status'] = 'completed'
                                resources_status[i]['message'] = '部署成功'
                                log_message(f"资源 {resource['full_name']} 部署成功")
                                break
            
            # 更新所有未明确标记为失败或成功的资源为成功
            for i, resource in enumerate(resources_status):
                if resource['status'] not in ['completed', 'failed']:
                    resources_status[i]['status'] = 'completed'
                    resources_status[i]['message'] = '部署成功'
                    log_message(f"资源 {resource['full_name']} 设置为部署成功")
            
            # 更新资源状态
            self._update_resources_status(deploy_id, resources_status)
            
            # 保存输出结果到状态文件
            self._update_deployment_status(deploy_id, 'completed', '部署成功完成', output_data)
            
            # 更新数据库中的部署状态
            self._update_deployment_in_db(deploy_id, 'completed')
            
            log_message(f"Terraform部署完成，部署ID: {deploy_id}")
            log_message(f"总计部署资源: {len(resources_status)} 个")
            log_message(f"部署成功资源: {sum(1 for r in resources_status if r['status'] == 'completed')} 个")
            log_message(f"部署失败资源: {sum(1 for r in resources_status if r['status'] == 'failed')} 个")
            
            # 记录部署结束时间
            with open(deployment_log_file, 'a') as f:
                f.write("\n" + "="*80 + "\n")
                f.write(f"部署结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"部署状态: 成功\n")
            
        except Exception as e:
            self.logger.error(f"Terraform部署执行出错，部署ID: {deploy_id}, 错误: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            # 记录错误到专用日志文件
            if 'deployment_log_file' in locals() and 'log_message' in locals():
                log_message(f"Terraform部署执行出错: {str(e)}", "ERROR")
                log_message(traceback.format_exc(), "ERROR")
                
                # 记录部署结束时间
                with open(deployment_log_file, 'a') as f:
                    f.write("\n" + "="*80 + "\n")
                    f.write(f"部署结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"部署状态: 失败\n")
                    f.write(f"错误: {str(e)}\n")
            
            # 更新状态为失败
            self._update_deployment_status(deploy_id, 'failed', f"部署执行出错: {str(e)}")
            
            # 更新数据库中的部署状态
            self._update_deployment_in_db(deploy_id, 'failed')
    
    def _execute_command(self, command):
        """执行系统命令并返回结果"""
        import subprocess
        
        try:
            self.logger.info(f"执行命令: {command}")
            
            # 使用subprocess运行命令
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 获取输出
            stdout, stderr = process.communicate()
            
            # 转换为文本
            stdout_text = stdout.decode('utf-8', errors='replace')
            stderr_text = stderr.decode('utf-8', errors='replace')
            
            exit_code = process.returncode
            
            return {
                'exit_code': exit_code,
                'stdout': stdout_text,
                'stderr': stderr_text
            }
            
        except Exception as e:
            self.logger.error(f"执行命令失败: {str(e)}")
            return {
                'exit_code': -1,
                'stdout': '',
                'stderr': str(e)
            }
    
    def _update_deployment_status(self, deploy_id, status, message, output=None):
        """更新部署状态"""
        try:
            # 获取部署目录
            deploy_dir = os.path.join(BASE_DIR, 'deployments', deploy_id)
            status_file = os.path.join(deploy_dir, 'status.json')
            
            # 读取现有状态
            current_status = {}
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    current_status = json.load(f)
                    
            # 更新状态
            current_status.update({
                'status': status,
                'message': message,
                'updated_at': datetime.now().isoformat()
            })
            
            # 如果有输出，添加到状态中
            if output:
                current_status['output'] = output
                
            # 保存更新后的状态
            with open(status_file, 'w') as f:
                json.dump(current_status, f, indent=2)
                
            self.logger.info(f"部署状态已更新，部署ID: {deploy_id}, 状态: {status}, 消息: {message}")
            
        except Exception as e:
            self.logger.error(f"更新部署状态失败: {str(e)}")
            
    def _update_resources_status(self, deploy_id, resources_status):
        """更新资源部署状态"""
        try:
            # 获取部署目录
            deploy_dir = os.path.join(BASE_DIR, 'deployments', deploy_id)
            status_file = os.path.join(deploy_dir, 'status.json')
            
            # 读取现有状态
            current_status = {}
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    current_status = json.load(f)
                    
            # 更新资源状态
            current_status['resources'] = resources_status
            
            # 计算进度 - 优化算法，考虑不同阶段的权重
            total_resources = len(resources_status)
            if total_resources > 0:
                # 计算每个状态的资源数量
                completed = sum(1 for r in resources_status if r['status'] == 'completed')
                failed = sum(1 for r in resources_status if r['status'] == 'failed')
                planned = sum(1 for r in resources_status if r['status'] == 'planned')
                pending = sum(1 for r in resources_status if r['status'] == 'pending')
                
                # 计算进度，考虑不同状态的权重
                # pending: 0%, planned: 40%, completed/failed: 100%
                progress = int(((completed + failed) * 100 + planned * 40) / total_resources)
                
                # 进度上限100%
                progress = min(progress, 100)
            else:
                progress = 0
            
            # 更新进度信息和状态消息
            current_status['progress'] = progress
            
            # 根据进度更新状态消息
            status_message = '初始化中...'
            if progress == 0:
                status_message = '正在初始化部署环境...'
            elif progress < 40:
                status_message = '正在规划资源部署...'
            elif progress < 80:
                status_message = f'正在部署资源：已完成 {completed}/{total_resources}'
            elif progress < 100:
                status_message = f'即将完成：已部署 {completed}/{total_resources} 资源'
            else:
                if failed > 0:
                    status_message = f'部署完成，但有 {failed} 个资源失败'
                else:
                    status_message = '所有资源已成功部署'
            
            current_status['status_message'] = status_message
            current_status['updated_at'] = datetime.now().isoformat()
            
            # 保存更新后的状态
            with open(status_file, 'w') as f:
                json.dump(current_status, f, indent=2)
                
            self.logger.info(f"资源状态已更新，部署ID: {deploy_id}, 进度: {progress}%")
            
        except Exception as e:
            self.logger.error(f"更新资源状态失败: {str(e)}")
            
    def _update_deployment_in_db(self, deploy_id, status):
        """更新数据库中的部署记录状态"""
        try:
            # 检查是否存在部署记录
            check_query = "SELECT * FROM deployments WHERE deployid = %s"
            deployment = self.db.query_one(check_query, (deploy_id,))
            
            if deployment:
                self.logger.info(f"找到现有部署记录: {deploy_id}, 当前状态: {deployment.get('status')}, 类型: {deployment.get('deploy_type')}")
                # 确保deploy_type是'template'
                if deployment.get('deploy_type') != 'template':
                    correct_type_query = "UPDATE deployments SET deploy_type = %s WHERE deployid = %s"
                    self.db.execute(correct_type_query, ('template', deploy_id))
                    self.logger.info(f"更新部署记录类型为template: {deploy_id}")
                
                # 更新部署状态
                update_query = "UPDATE deployments SET status = %s, updated_at = NOW() WHERE deployid = %s"
                result = self.db.execute(update_query, (status, deploy_id))
                
                self.logger.info(f"数据库部署状态已更新，部署ID: {deploy_id}, 状态: {status}")
            else:
                self.logger.warning(f"未找到部署记录: {deploy_id}，尝试创建新记录")
                
                # 查询部署状态文件获取信息
                deploy_dir = os.path.join(BASE_DIR, 'deployments', deploy_id)
                status_file = os.path.join(deploy_dir, 'status.json')
                deploy_info = {}
                
                if os.path.exists(status_file):
                    try:
                        with open(status_file, 'r') as f:
                            deploy_info = json.load(f)
                    except Exception as e:
                        self.logger.error(f"读取部署状态文件失败: {str(e)}")
                
                # 获取用户ID
                user_id = deploy_info.get('user_id') or '1'
                username = deploy_info.get('username') or 'admin'
                template_id = deploy_info.get('template_id', '')
                project = deploy_info.get('project', '默认项目')
                cloud = deploy_info.get('cloud', 'AWS')
                region = deploy_info.get('region', '未指定')
                
                # 插入新记录，确保deploy_type为'template'
                insert_query = """
                    INSERT INTO deployments (
                        deployid, deploy_type, cloud, project, region, 
                        user_id, username, status, created_at, updated_at, template_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s)
                """
                
                self.db.execute(
                    insert_query, 
                    (
                        deploy_id, 'template', cloud, project, 
                        region, user_id, username, status, template_id
                    )
                )
                
                self.logger.info(f"已创建新的模板部署记录，部署ID: {deploy_id}, 状态: {status}, 用户ID: {user_id}, 模板ID: {template_id}")
            
        except Exception as e:
            self.logger.error(f"更新数据库部署状态失败: {str(e)}")
            self.logger.error(traceback.format_exc())
    
    def get_deploy_status(self):
        """获取模板部署状态"""
        try:
            deploy_id = request.args.get('deploy_id')
            
            if not deploy_id:
                return jsonify({"error": "未提供部署ID", "success": False}), 400
            
            # 查询部署状态
            query = "SELECT * FROM deployments WHERE deployid = %s"
            deployment = self.db.query_one(query, (deploy_id,))
            
            if not deployment:
                return jsonify({"error": "未找到部署记录", "success": False}), 404
            
            # 获取部署目录和状态文件
            deploy_dir = os.path.join(BASE_DIR, 'deployments', deploy_id)
            status_file = os.path.join(deploy_dir, 'status.json')
            
            # 读取状态文件
            status_data = {}
            if os.path.exists(status_file):
                try:
                    with open(status_file, 'r') as f:
                        status_data = json.load(f)
                except json.JSONDecodeError as e:
                    self.logger.error(f"解析状态文件JSON失败: {str(e)}")
                    status_data = {
                        "status": "in_progress", 
                        "message": "状态文件解析错误",
                        "updated_at": datetime.now().isoformat()
                    }
            else:
                # 如果状态文件不存在，创建一个初始状态
                status_data = {
                    "status": "in_progress",
                    "message": "等待部署开始...",
                    "updated_at": datetime.now().isoformat()
                }
                
                # 尝试从部署记录创建初始资源列表
                try:
                    if deployment.get('template_id'):
                        template_id = deployment['template_id']
                        terraform_path = os.path.join(TERRAFORM_SCRIPTS_DIR, f"{template_id}.tf")
                        
                        if os.path.exists(terraform_path):
                            with open(terraform_path, 'r') as f:
                                terraform_content = f.read()
                            
                            status_data['resources'] = self._parse_resources_from_terraform(terraform_content)
                except Exception as resource_err:
                    self.logger.error(f"创建初始资源列表失败: {str(resource_err)}")
            
            # 获取部署日志（如果存在）
            deployment_log_file = os.path.join(deploy_dir, 'deployment.log')
            log_content = ""
            if os.path.exists(deployment_log_file):
                try:
                    with open(deployment_log_file, 'r') as f:
                        # 获取最后50行日志
                        log_lines = f.readlines()
                        log_content = ''.join(log_lines[-50:])
                except Exception as log_err:
                    self.logger.error(f"读取部署日志失败: {str(log_err)}")
                    log_content = f"读取日志失败: {str(log_err)}"
            
            # 构建资源状态信息
            resources_status = status_data.get('resources', [])
            
            # 计算进度
            total_resources = len(resources_status)
            if total_resources > 0:
                # 计算每个状态的资源数量
                completed = sum(1 for r in resources_status if r.get('status') == 'completed')
                failed = sum(1 for r in resources_status if r.get('status') == 'failed')
                planned = sum(1 for r in resources_status if r.get('status') == 'planned')
                
                # 计算进度，考虑不同状态的权重
                progress = int(((completed + failed) * 100 + planned * 40) / total_resources)
                progress = min(progress, 100)  # 确保不超过100%
            else:
                progress = status_data.get('progress', 0)
            
            # 使用状态消息或创建一个
            status_message = status_data.get('status_message', '')
            if not status_message:
                if total_resources > 0:
                    completed = sum(1 for r in resources_status if r.get('status') == 'completed')
                    failed = sum(1 for r in resources_status if r.get('status') == 'failed')
                    status_message = f"已完成: {completed}/{total_resources} 资源"
                    if failed > 0:
                        status_message += f", {failed} 个失败"
                else:
                    status_message = status_data.get('message', "处理中...")
            
            # 确定部署状态
            current_status = status_data.get('status', deployment.get('status', 'in_progress'))
            
            # 如果状态数据中没有明确的状态，但所有资源都已完成或失败，则自动更新状态
            if current_status == 'in_progress' and total_resources > 0:
                completed_count = sum(1 for r in resources_status if r.get('status') in ['completed', 'failed'])
                if completed_count == total_resources:
                    # 如果有失败的资源，状态为失败
                    if failed > 0:
                        current_status = 'failed'
                    else:
                        current_status = 'completed'
            
            # 创建部署状态响应
            response_data = {
                "success": True,
                "deploy_id": deploy_id,
                "status": current_status,
                "resources_status": resources_status,
                "deploy_status": {
                    "progress": progress,
                    "message": status_message
                },
                "updated_at": status_data.get('updated_at', deployment.get('updated_at'))
            }
            
            # 添加输出信息（如果有）
            if status_data.get('output'):
                response_data['output'] = status_data.get('output')
            
            # 添加错误信息（如果有）
            if status_data.get('error'):
                response_data['error'] = status_data.get('error')
            
            # 添加日志信息（如果有）
            if log_content:
                response_data['log'] = log_content
            
            return jsonify(response_data)
        except Exception as e:
            self.logger.error(f"获取部署状态失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": str(e), "success": False}), 500
    
    def _parse_resources_from_terraform(self, terraform_content):
        """从Terraform内容解析资源列表"""
        try:
            # 简单解析，实际应该使用HCL解析器
            resources = []
            lines = terraform_content.split('\n')
            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith('resource '):
                    parts = line.split('"')
                    if len(parts) >= 5:
                        resource_type = parts[1]
                        resource_name = parts[3]
                        resources.append({
                            "type": resource_type,
                            "name": resource_name,
                            "full_name": f"{resource_type}.{resource_name}",
                            "status": "pending"
                        })
            return resources
        except Exception as e:
            self.logger.error(f"解析Terraform资源失败: {str(e)}")
            return []
    
    def _get_resources_deployment_status(self, deploy_id):
        """获取资源部署状态"""
        # 这里应该根据实际情况查询每个资源的部署状态
        # 示例实现，实际应当连接到真实的部署状态跟踪系统
        try:
            # 从日志或状态数据库中获取部署状态
            status_query = """
                SELECT resource_type, resource_name, status, updated_at
                FROM deployment_resources
                WHERE deploy_id = %s
                ORDER BY updated_at
            """
            resources = self.db.query(status_query, (deploy_id,))
            
            if not resources:
                # 如果没有资源状态记录，从部署记录中获取模板并解析资源
                deploy_query = "SELECT template_id FROM deployments WHERE deployid = %s"
                deployment = self.db.query_one(deploy_query, (deploy_id,))
                
                if deployment and deployment.get('template_id'):
                    template_id = deployment['template_id']
                    terraform_path = os.path.join(TERRAFORM_SCRIPTS_DIR, f"{template_id}.tf")
                    
                    if os.path.exists(terraform_path):
                        with open(terraform_path, 'r') as f:
                            terraform_content = f.read()
                        
                        return self._parse_resources_from_terraform(terraform_content)
            
            return resources
        except Exception as e:
            self.logger.error(f"获取资源部署状态失败: {str(e)}")
            return []
            
    def get_template_deployments(self):
        """获取模板部署列表"""
        try:
            # 获取用户ID
            user_id = self._get_user_id()
            
            if not user_id:
                self.logger.error("无法获取用户ID")
                return jsonify({"error": "未获取到用户ID", "success": False}), 400
                
            self.logger.info(f"获取模板部署列表，用户ID: {user_id}")
                
            # 查询模板部署记录
            query = """
                SELECT d.*, t.template_name
                FROM deployments d
                LEFT JOIN templates t ON d.template_id = t.id
                WHERE d.deploy_type = %s AND d.user_id = %s
                ORDER BY d.created_at DESC
                LIMIT 100
            """
            
            self.logger.info(f"执行模板部署查询: {query} 参数: ('template', {user_id})")
            
            try:
                deployments = self.db.query(query, ('template', user_id))
                
                # 如果deployments为None，初始化为空列表
                if deployments is None:
                    self.logger.warning("模板部署查询返回None")
                    deployments = []
                    
                # 记录找到的部署数量
                self.logger.info(f"查询到的模板部署数量: {len(deployments)}")
                
                if len(deployments) > 0:
                    # 记录第一条记录的信息（用于调试）
                    self.logger.info(f"第一条模板部署记录: {deployments[0]}")
                
                # 检查deploy_type字段
                if len(deployments) == 0:
                    # 检查是否有任何模板部署记录存在
                    check_query = "SELECT COUNT(*) as count FROM deployments WHERE deploy_type = %s"
                    count_result = self.db.query_one(check_query, ('template',))
                    
                    if count_result and count_result.get('count', 0) > 0:
                        self.logger.warning(f"存在模板部署记录(共{count_result['count']}条)，但当前用户({user_id})没有记录")
                    else:
                        self.logger.warning("数据库中不存在任何deploy_type='template'的记录")
                
                # 检查用户部署记录
                user_deployments_query = "SELECT COUNT(*) as count FROM deployments WHERE user_id = %s"
                user_count_result = self.db.query_one(user_deployments_query, (user_id,))
                
                if user_count_result:
                    self.logger.info(f"用户({user_id})共有{user_count_result.get('count', 0)}条部署记录")
                
                # 返回结果
                return jsonify({
                    "success": True,
                    "deployments": deployments
                })
            except Exception as db_error:
                self.logger.error(f"数据库查询失败: {str(db_error)}")
                self.logger.error(traceback.format_exc())
                return jsonify({
                    "error": f"数据库查询失败: {str(db_error)}", 
                    "success": False,
                    "deployments": []
                }), 500
                
        except Exception as e:
            self.logger.error(f"获取模板部署列表失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": str(e), "success": False, "deployments": []}), 500
    
    def get_template_files(self):
        """获取模板部署的文件列表"""
        try:
            # 获取部署ID
            deploy_id = None
            if request.method == 'POST':
                data = request.get_json()
                deploy_id = data.get('deploy_id')
            else:  # GET
                deploy_id = request.args.get('deploy_id')
            
            if not deploy_id:
                self.logger.error("未提供部署ID")
                return jsonify({"error": "未提供部署ID", "success": False}), 400
                
            self.logger.info(f"获取模板部署文件列表，部署ID: {deploy_id}")
            
            # 确定目录路径
            deploy_dir = os.path.join(BASE_DIR, 'deployments', deploy_id)
            
            if not os.path.exists(deploy_dir):
                self.logger.warning(f"部署目录不存在: {deploy_dir}")
                return jsonify({"error": "部署目录不存在", "success": False}), 404
                
            # 列出目录下的所有文件
            files = []
            
            # 检查main.tf文件
            main_tf_path = os.path.join(deploy_dir, 'main.tf')
            if os.path.exists(main_tf_path):
                file_size = os.path.getsize(main_tf_path)
                # 格式化文件大小
                if file_size < 1024:
                    size_str = f"{file_size} B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.2f} KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.2f} MB"
                    
                files.append({
                    "name": "main.tf",
                    "path": f"deployments/{deploy_id}/main.tf",
                    "size": size_str,
                    "type": "Terraform"
                })
                
            # 检查terraform.tfstate文件
            tfstate_path = os.path.join(deploy_dir, 'terraform.tfstate')
            if os.path.exists(tfstate_path):
                file_size = os.path.getsize(tfstate_path)
                # 格式化文件大小
                if file_size < 1024:
                    size_str = f"{file_size} B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.2f} KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.2f} MB"
                    
                files.append({
                    "name": "terraform.tfstate",
                    "path": f"deployments/{deploy_id}/terraform.tfstate",
                    "size": size_str,
                    "type": "Terraform"
                })
                
            # 检查状态文件
            status_path = os.path.join(deploy_dir, 'status.json')
            if os.path.exists(status_path):
                file_size = os.path.getsize(status_path)
                # 格式化文件大小
                if file_size < 1024:
                    size_str = f"{file_size} B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.2f} KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.2f} MB"
                    
                files.append({
                    "name": "status.json",
                    "path": f"deployments/{deploy_id}/status.json",
                    "size": size_str,
                    "type": "JSON"
                })
                
            # 检查日志文件
            log_path = os.path.join(deploy_dir, 'deployment.log')
            if os.path.exists(log_path):
                file_size = os.path.getsize(log_path)
                # 格式化文件大小
                if file_size < 1024:
                    size_str = f"{file_size} B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.2f} KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.2f} MB"
                    
                files.append({
                    "name": "deployment.log",
                    "path": f"deployments/{deploy_id}/deployment.log",
                    "size": size_str,
                    "type": "Log"
                })
                
            self.logger.info(f"找到 {len(files)} 个文件")
            
            return jsonify({
                "success": True,
                "files": files,
                "message": f"找到 {len(files)} 个文件"
            })
            
        except Exception as e:
            self.logger.error(f"获取模板部署文件列表失败: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({"error": str(e), "success": False}), 500
    
    def get_deployment_details(self):
        """获取指定模板部署ID的资源详情"""
        try:
            # 获取部署ID
            deploy_id = request.args.get('deploy_id')
            if not deploy_id:
                return jsonify({"error": "缺少模板部署ID参数", "success": False}), 400
            
            self.logger.info(f"获取模板部署ID {deploy_id} 的资源详情")
            
            # 查询模板部署记录
            query = """
                SELECT d.*, t.template_name 
                FROM deployments d
                LEFT JOIN templates t ON d.template_id = t.id
                WHERE d.deployid = %s AND d.deploy_type = 'template'
                LIMIT 1
            """
            deployment = self.db.query_one(query, (deploy_id,))
            
            # 检查是否找到记录
            if not deployment:
                self.logger.warning(f"未找到模板部署ID为 {deploy_id} 的记录")
                return jsonify({"error": f"未找到模板部署ID为 {deploy_id} 的记录", "success": False}), 404
            
            # 获取部署状态文件
            deploy_dir = os.path.join(BASE_DIR, 'deployments', deploy_id)
            status_file = os.path.join(deploy_dir, 'status.json')
            
            resources = []
            # 尝试从状态文件中获取资源信息
            if os.path.exists(status_file):
                try:
                    with open(status_file, 'r') as f:
                        status_data = json.load(f)
                        if 'resources' in status_data:
                            resources = status_data['resources']
                except Exception as e:
                    self.logger.error(f"读取状态文件失败: {str(e)}")
            
            # 如果没有从状态文件获得资源，尝试从模板解析
            if not resources and deployment.get('template_id'):
                try:
                    template_id = deployment['template_id']
                    terraform_path = os.path.join(TERRAFORM_SCRIPTS_DIR, f"{template_id}.tf")
                    
                    if os.path.exists(terraform_path):
                        with open(terraform_path, 'r') as f:
                            terraform_content = f.read()
                        
                        # 解析资源
                        resources = self._parse_resources_from_terraform(terraform_content)
                except Exception as e:
                    self.logger.error(f"从模板解析资源失败: {str(e)}")
            
            # 构建HTML表格
            html = "<div class='deployment-details card shadow-sm'>"
            
            # 基本信息表格
            html += "<div class='card-header bg-primary text-white'><h3 class='mb-0'><i class='fas fa-file-code mr-2'></i>模板部署基本信息</h3></div>"
            html += "<div class='card-body'>"
            html += "<table class='table table-striped table-bordered table-hover'>"
            html += "<tbody>"
            html += f"<tr><th width='30%' class='bg-light'>部署ID</th><td><code>{deployment.get('deployid', '')}</code></td></tr>"
            html += f"<tr><th class='bg-light'>模板名称</th><td><strong>{deployment.get('template_name', '未知模板')}</strong></td></tr>"
            html += f"<tr><th class='bg-light'>项目</th><td>{deployment.get('project', '')}</td></tr>"
            html += f"<tr><th class='bg-light'>云平台</th><td><span class='badge badge-info'>{deployment.get('cloud', '')}</span></td></tr>"
            html += f"<tr><th class='bg-light'>区域</th><td><span class='badge badge-secondary'>{deployment.get('region', '')}</span></td></tr>"
            html += f"<tr><th class='bg-light'>状态</th><td>{self._get_status_badge(deployment.get('status', '未知'))}</td></tr>"
            html += f"<tr><th class='bg-light'>创建时间</th><td>{deployment.get('created_at', '')}</td></tr>"
            html += f"<tr><th class='bg-light'>更新时间</th><td>{deployment.get('updated_at', '')}</td></tr>"
            html += "</tbody>"
            html += "</table>"
            html += "</div>"
            
            # 资源列表表格
            if resources:
                html += "<div class='card-header bg-info text-white'><h3 class='mb-0'><i class='fas fa-cubes mr-2'></i>部署资源</h3></div>"
                html += "<div class='card-body table-responsive'>"
                html += "<table class='table table-striped table-bordered table-hover'>"
                html += "<thead class='thead-light'>"
                html += "<tr><th>资源类型</th><th>资源名称</th><th>状态</th></tr>"
                html += "</thead>"
                html += "<tbody>"
                
                # 根据资源类型不同，显示不同的表格
                for resource in resources:
                    resource_type = resource.get('type', '未知')
                    resource_name = resource.get('name', '')
                    resource_status = resource.get('status', '准备中')
                    
                    # 获取资源图标
                    resource_icon = self._get_resource_icon(resource_type)
                    
                    # 获取状态样式
                    status_badge = self._get_resource_status_badge(resource_status)
                    
                    html += "<tr>"
                    html += f"<td>{resource_icon} {resource_type}</td>"
                    html += f"<td><strong>{resource_name}</strong></td>"
                    html += f"<td>{status_badge}</td>"
                    html += "</tr>"
                
                html += "</tbody>"
                html += "</table>"
                html += "</div>"
            else:
                html += "<div class='card-body'><div class='alert alert-warning'><i class='fas fa-exclamation-triangle mr-2'></i>暂无部署资源信息</div></div>"
            
            # 获取部署日志（如果存在）
            deployment_log_file = os.path.join(deploy_dir, 'deployment.log')
            log_content = ""
            
            if os.path.exists(deployment_log_file):
                try:
                    with open(deployment_log_file, 'r') as f:
                        log_content = f.read()
                    
                    # 添加日志内容（如果存在）
                    if log_content:
                        html += "<div class='card-header bg-secondary text-white'><h3 class='mb-0'><i class='fas fa-terminal mr-2'></i>部署日志</h3></div>"
                        html += "<div class='card-body'>"
                        html += "<div class='log-container bg-dark text-light p-3' style='max-height:300px;overflow-y:auto;border-radius:4px;'>"
                        html += f"<pre style='margin-bottom:0;'>{log_content}</pre>"
                        html += "</div>"
                        html += "</div>"
                except Exception as e:
                    self.logger.error(f"读取部署日志失败: {str(e)}")
            
            html += "</div>"
            
            return jsonify({
                "success": True,
                "deployment": deployment,
                "resources": resources,
                "table": html
            })
            
        except Exception as e:
            self.logger.error(f"获取模板部署详情出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"获取模板部署详情失败: {str(e)}", "success": False}), 500 
    
    def _get_resource_icon(self, resource_type: str) -> str:
        """为不同资源类型提供对应的Font Awesome 图标"""
        type_icons = {
            'aws_vpc': '<i class="fas fa-network-wired"></i>',
            'aws_subnet': '<i class="fas fa-sitemap"></i>',
            'aws_s3_bucket': '<i class="fas fa-database"></i>',
            'aws_iam_user': '<i class="fas fa-user"></i>',
            'aws_iam_group': '<i class="fas fa-users"></i>',
            'aws_iam_policy': '<i class="fas fa-file-contract"></i>',
            'aws_instance': '<i class="fas fa-server"></i>',
            'aws_security_group': '<i class="fas fa-shield-alt"></i>',
            'aws_route_table': '<i class="fas fa-route"></i>',
            'aws_internet_gateway': '<i class="fas fa-exchange-alt"></i>',
        }
        return type_icons.get(resource_type, '<i class="fas fa-cube"></i>')
    
    def _get_status_badge(self, status: str) -> str:
        """生成状态的Bootstrap徽章HTML"""
        status_lower = status.lower()
        
        if status_lower == 'completed' or status_lower == 'success':
            return '<span class="badge badge-success"><i class="fas fa-check mr-1"></i>已完成</span>'
        elif status_lower == 'failed' or status_lower == 'error':
            return '<span class="badge badge-danger"><i class="fas fa-times mr-1"></i>失败</span>'
        elif status_lower == 'in_progress' or status_lower == 'running':
            return '<span class="badge badge-warning"><i class="fas fa-spinner fa-spin mr-1"></i>进行中</span>'
        elif status_lower == 'pending':
            return '<span class="badge badge-info"><i class="fas fa-hourglass-half mr-1"></i>准备中</span>'
        else:
            return f'<span class="badge badge-secondary">{status}</span>'
            
    def _get_resource_status_badge(self, status: str) -> str:
        """生成资源状态的Bootstrap徽章HTML"""
        status_lower = status.lower()
        
        if status_lower == 'completed':
            return '<span class="badge badge-success"><i class="fas fa-check mr-1"></i>已完成</span>'
        elif status_lower == 'failed':
            return '<span class="badge badge-danger"><i class="fas fa-times mr-1"></i>失败</span>'
        elif status_lower == 'in_progress':
            return '<span class="badge badge-warning"><i class="fas fa-spinner fa-spin mr-1"></i>进行中</span>'
        elif status_lower == 'pending' or status_lower == 'planned':
            return '<span class="badge badge-info"><i class="fas fa-hourglass-half mr-1"></i>准备中</span>'
        else:
            return f'<span class="badge badge-secondary">{status}</span>'