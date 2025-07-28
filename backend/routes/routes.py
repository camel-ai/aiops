from flask import Blueprint, Flask, request, jsonify
import logging
import traceback
import json
import os
# 使用相对导入
from config.config import Config
from controllers.auth_controller import AuthController
from controllers.project_controller import ProjectController
from controllers.chat_controller import ChatController
from controllers.cloud_controller import CloudController
from controllers.deploy_controller import DeployController
from controllers.apikey_controller import ApiKeyController
from controllers.diagram_controller import DiagramController  # 添加图表控制器导入
from middlewares.middlewares import setup_middlewares
from utils.auth import require_login, token_required, get_current_user
from middlewares.auth import jwt_required
from controllers.topology_controller import TopologyController
from controllers.files_controller import FilesController
# 添加模板控制器导入
from controllers.template_controller import TemplateController
from controllers.terraform_controller import TerraformController  # 添加Terraform控制器导入
# 添加云服务提供商控制器导入
from controllers.clouds_controller import CloudsController
from datetime import datetime

def setup_routes(app: Flask, config: Config):
    """设置路由"""
    # 确保上传目录存在
    upload_base_dir = os.path.join(app.root_path, 'upload')
    if not os.path.exists(upload_base_dir):
        os.makedirs(upload_base_dir)
        
    # 设置中间件
    setup_middlewares(app, config)
    
    # 创建控制器实例
    auth_controller = AuthController(config)
    project_controller = ProjectController()
    chat_controller = ChatController(config)
    cloud_controller = CloudController(config)
    deploy_controller = DeployController(config)
    topology_controller = TopologyController(config)
    files_controller = FilesController(config)
    # 创建模板控制器实例
    template_controller = TemplateController(config)
    # 创建API密钥控制器实例
    apikey_controller = ApiKeyController(config)
    # 创建图表控制器实例
    diagram_controller = DiagramController(config)
    # 创建Terraform控制器实例
    terraform_controller = TerraformController(config)
    # 创建云服务提供商控制器实例
    clouds_controller = CloudsController(config)
    
    # 添加全局错误处理
    @app.errorhandler(401)
    def unauthorized_error(error):
        logging.error(f"认证错误: {error}")
        logging.error(f"请求路径: {request.path}")
        logging.error(f"请求方法: {request.method}")
        logging.error(f"请求头: {request.headers}")
        return jsonify({"error": "认证失败", "detail": "请检查您的登录状态或令牌是否有效"}), 401
    
    # 公共路由
    @app.route("/api/health", methods=["GET"])
    def health_check():
        """健康检查路由"""
        return jsonify({
            "status": "healthy",
            "message": "MCDP Backend Service is running",
            "timestamp": datetime.now().isoformat()
        }), 200
    
    @app.route("/api/register", methods=["POST"])
    def register():
        return auth_controller.register()
    
    @app.route("/api/login", methods=["POST"])
    def login():
        return auth_controller.login()
    
    # 需要认证的路由
    # 项目相关路由
    @app.route("/api/projects", methods=["POST"])
    @app.auth_middleware
    def create_project():
        logging.info("路由: 创建项目")
        try:
            return project_controller.create_project()
        except Exception as e:
            logging.error(f"路由处理异常 - 创建项目: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({"error": "创建项目失败", "detail": str(e)}), 500
    
    @app.route("/api/projects", methods=["GET"])
    @app.auth_middleware
    def get_all_projects():
        logging.info("路由: 获取所有项目")
        try:
            return project_controller.get_all_projects()
        except Exception as e:
            logging.error(f"路由处理异常 - 获取所有项目: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({"error": "获取项目列表失败", "detail": str(e), "projects": []}), 500
    
    @app.route("/api/projects/<int:project_id>", methods=["GET"])
    @app.auth_middleware
    def get_project(project_id):
        logging.info(f"路由: 获取项目详情 ID={project_id}")
        try:
            return project_controller.get_project(project_id)
        except Exception as e:
            logging.error(f"路由处理异常 - 获取项目详情: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({"error": "获取项目详情失败", "detail": str(e)}), 500
    
    # 聊天相关路由
    @app.route("/api/chat", methods=["POST"])
    @token_required
    def send_message():
        logging.info("路由: 发送聊天消息 (/api/chat)")
        
        try:
            # 获取消息内容
            data = request.get_json()
            if not data or 'message' not in data:
                return jsonify({"error": "请提供消息内容"}), 400
                
            message = data.get('message', '')
            
            # 获取前端传递的project和cloud信息
            project = data.get('project', '')
            cloud = data.get('cloud', '')
            
            # 记录日志，确认是否收到了项目和云信息
            logging.info(f"收到消息(/api/chat): {message}, 项目: {project}, 云: {cloud}")
            
            # 检查是否是以"/"开头的命令 - 新增的DeepSeek API处理
            if message.startswith('/'):
                # 导入DeepSeek API工具
                from utils.deepseek_api import query_deepseek
                
                # 移除前导斜杠
                query = message[1:].strip()
                
                # 添加提示词
                system_prompt = "我的需求仅仅以云配置jason格式返回给我"
                
                # 调用DeepSeek API
                logging.info(f"收到'/'命令，调用DeepSeek API: {query}")
                result = query_deepseek(query, system_prompt, is_command=True)
                
                # 处理可能的错误
                if 'error' in result and result['error']:
                    return jsonify({
                        "reply": f"调用DeepSeek API时出错: {result['error']}",
                        "success": False
                    })
                
                # 构建回复
                response = {
                    "reply": result['content'],
                    "success": True,
                    "is_deepseek_response": True
                }
                
                # 如果成功提取到JSON，添加到响应中
                if result.get('json_content'):
                    response["json_content"] = result['json_content']
                    response["has_json"] = True
                    
                return jsonify(response)
                
            # 处理@查询和@部署命令，转发到相应的控制器
            if '@查询' in message:
                # 确保传递项目和云信息到查询控制器
                if not data.get('project') and project:
                    data['project'] = project
                if not data.get('cloud') and cloud:
                    data['cloud'] = cloud
                # 更新请求数据
                request.data = json.dumps(data).encode('utf-8')
                return cloud_controller.handle_query_request()
            elif '@部署' in message:
                # 确保传递项目和云信息到部署控制器
                if not data.get('project') and project:
                    data['project'] = project
                if not data.get('cloud') and cloud:
                    data['cloud'] = cloud
                # 更新请求数据
                request.data = json.dumps(data).encode('utf-8')
                return deploy_controller.handle_deployment_request()
            elif '@模版部署' in message or '@模板部署' in message:
                # 调用模板控制器处理模板部署请求
                return template_controller.get_templates_for_chat()
        
            # 在请求中注入当前用户信息
            request.current_user = get_current_user(request)
            
            # 继续使用原有的聊天控制器处理普通消息
            return chat_controller.send_message()
            
        except Exception as e:
            logging.error(f"处理聊天请求出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"服务器处理请求时出错: {str(e)}"}), 500
    
    # 流式聊天路由
    @app.route("/api/chat/stream", methods=["POST"])
    @token_required
    def send_message_stream():
        logging.info("路由: 发送流式聊天消息 (/api/chat/stream)")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.send_message_stream()

    # 获取聊天历史路由
    @app.route("/api/chat/history", methods=["GET"])
    @token_required
    def get_chat_history():
        logging.info("路由: 获取聊天历史 (/api/chat/history)")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.get_chat_history()

    # 添加一个额外的路由，直接处理/chat路径
    @app.route("/chat", methods=["POST"])
    @token_required
    def send_message_direct():
        logging.info("路由: 发送聊天消息 (/chat)")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.send_message()
    
    # 云资源管理相关路由
    @app.route("/api/cloud/form", methods=["POST"])
    @token_required
    def handle_cloud_form():
        logging.info("路由: 处理云资源配置表单")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.handle_cloud_form_submission()
    
    # 添加一个额外的路由，直接处理/cloud/form路径
    @app.route("/cloud/form", methods=["POST"])
    @token_required
    def handle_cloud_form_direct():
        logging.info("路由: 处理云资源配置表单 (/cloud/form)")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.handle_cloud_form_submission()
    
    @app.route("/api/cloud/option", methods=["POST"])
    @token_required
    def handle_cloud_option():
        logging.info("路由: 处理云资源操作选项")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.handle_cloud_option_selection()
    
    # 添加直接处理选项的路由
    @app.route("/cloud/option", methods=["POST"])
    @token_required
    def handle_cloud_option_direct():
        logging.info("路由: 处理云资源操作选项 (/cloud/option)")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.handle_cloud_option_selection()
        
    # 添加处理区域选择的路由
    @app.route("/api/cloud/region", methods=["POST"])
    @token_required
    def handle_cloud_region():
        logging.info("路由: 处理云资源区域选择")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.handle_region_selection()
        
    # 添加直接处理区域选择的路由
    @app.route("/cloud/region", methods=["POST"])
    @token_required
    def handle_cloud_region_direct():
        logging.info("路由: 处理云资源区域选择 (/cloud/region)")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.handle_region_selection()
        
    # 添加处理确认查询的路由
    @app.route("/api/cloud/query", methods=["POST"])
    @token_required
    def handle_cloud_query():
        logging.info("路由: 处理云资源查询")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.handle_cloud_query()
        
    # 添加直接处理确认查询的路由
    @app.route("/cloud/query", methods=["POST"])
    @token_required
    def handle_cloud_query_direct():
        logging.info("路由: 处理云资源查询 (/cloud/query)")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.handle_cloud_query()
    
    # 添加资源选择路由
    @app.route('/api/cloud/resources', methods=['POST'])
    @token_required
    def select_cloud_resources():
        logging.info("路由: 处理云资源选择")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.handle_resource_selection()
    
    # 添加获取用户部署历史路由
    @app.route('/api/deployments', methods=['GET'])
    @token_required
    def get_user_deployments():
        logging.info("路由: 获取用户部署历史")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.get_user_deployments()
    
    # 添加获取部署详情路由
    @app.route('/api/deployments/details', methods=['GET'])
    @token_required
    def get_deployment_details():
        logging.info("路由: 获取部署详情")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return chat_controller.get_deployment_details()
    
    # 查询历史和详情
    @app.route('/api/cloud/deployments', methods=['GET'])
    @token_required
    def get_cloud_deployments():
        logging.info("路由: 获取用户查询历史")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return cloud_controller.get_user_deployments()
    
    @app.route('/api/cloud/deployment', methods=['GET'])
    @token_required
    def get_cloud_deployment_details():
        logging.info("路由: 获取查询详情")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return cloud_controller.get_deployment_details()
    
    # 云资源部署相关路由 - 新增
    @app.route('/api/deploy/form', methods=['POST'])
    @token_required
    def submit_deploy_form():
        logging.info("路由: 处理部署表单提交")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return deploy_controller.save_cloud_config()
    
    @app.route('/api/deploy/option', methods=['POST'])
    @token_required
    def select_deploy_option():
        logging.info("路由: 处理部署选项选择")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return deploy_controller.handle_cloud_option_selection()
    
    @app.route('/api/deploy/region', methods=['POST'])
    @token_required
    def select_deploy_region():
        logging.info("路由: 处理部署区域选择")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return deploy_controller.handle_region_selection()
    
    @app.route('/api/deploy/resources', methods=['POST'])
    @token_required
    def select_deploy_resources():
        logging.info("路由: 处理部署资源选择")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return deploy_controller.handle_resource_selection()
    
    @app.route('/api/deploy/resource_config', methods=['POST'])
    @token_required
    def handle_resource_config():
        logging.info("路由: 处理资源配置表单")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return deploy_controller.handle_resource_config_form()
    
    @app.route('/api/deploy/deployments', methods=['GET'])
    @token_required
    def get_deploy_deployments():
        logging.info("路由: 获取用户部署历史")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return deploy_controller.get_user_deployments()
    
    @app.route('/api/deploy/deployment', methods=['GET'])
    @token_required
    def get_deploy_deployment_details():
        logging.info("路由: 获取部署详情")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return deploy_controller.get_deployment_details()
    
    # 添加获取部署状态的路由
    @app.route('/api/deploy/status', methods=['GET'])
    @token_required
    def get_deployment_status():
        logging.info("路由: 获取部署状态")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return deploy_controller.get_deployment_status()
    
    @app.route('/api/deploy/execute', methods=['POST'])
    @token_required
    def execute_deploy():
        """同步执行部署请求，避免轮询"""
        logging.info("路由: 执行部署请求")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        # 调用控制器方法
        return deploy_controller.handle_execute_deploy()
    
    # 消息处理路由
    @app.route('/api/message', methods=['POST'])
    @token_required
    def handle_message():
        logging.info("路由: 处理消息")
        """处理不同类型的消息，根据关键词分发到不同的控制器"""
        try:
            # 在请求中注入当前用户信息
            request.current_user = get_current_user(request)
            
            data = request.get_json()
            if not data or 'message' not in data:
                return jsonify({"error": "请提供消息内容"}), 400
            
            message = data.get('message', '')
            
            # 获取前端传递的project和cloud信息
            project = data.get('project', '')
            cloud = data.get('cloud', '')
            
            # 记录日志，确认是否收到了项目和云信息
            logging.info(f"收到消息: {message}, 项目: {project}, 云: {cloud}")
            
            # 检查是否是以"/"开头的命令 - 新增的DeepSeek API处理
            if message.startswith('/'):
                # 导入DeepSeek API工具
                from utils.deepseek_api import query_deepseek
                
                # 移除前导斜杠
                query = message[1:].strip()
                
                # 添加提示词
                system_prompt = "我的需求仅仅以云配置jason格式返回给我"
                
                # 调用DeepSeek API，是命令模式
                logging.info(f"收到'/'命令，调用DeepSeek API: {query}")
                result = query_deepseek(query, system_prompt, is_command=True)
                
                # 处理可能的错误
                if 'error' in result and result['error']:
                    return jsonify({
                        "reply": f"调用DeepSeek API时出错: {result['error']}",
                        "success": False
                    })
                
                # 构建回复
                response = {
                    "reply": result['content'],
                    "success": True,
                    "is_deepseek_response": True
                }
                
                # 如果成功提取到JSON，添加到响应中
                if result.get('json_content'):
                    response["json_content"] = result['json_content']
                    response["has_json"] = True
                    
                return jsonify(response)
            
            # 根据消息关键词分发到不同控制器
            if '@查询' in message:
                # 确保传递项目和云信息到查询控制器
                if not data.get('project') and project:
                    data['project'] = project
                if not data.get('cloud') and cloud:
                    data['cloud'] = cloud
                # 更新请求数据
                request.data = json.dumps(data).encode('utf-8')
                return cloud_controller.handle_query_request()
            elif '@部署' in message:
                # 确保传递项目和云信息到部署控制器
                if not data.get('project') and project:
                    data['project'] = project
                if not data.get('cloud') and cloud:
                    data['cloud'] = cloud
                # 更新请求数据
                request.data = json.dumps(data).encode('utf-8')
                return deploy_controller.handle_deployment_request()
            elif '@模版部署' in message or '@模板部署' in message:
                # 调用模板控制器处理模板部署请求
                return template_controller.get_templates_for_chat()
            elif '@ai' in message:
                # 调用图表控制器生成AI部署图
                logging.info("收到@ai命令，调用图表控制器生成AI部署图")
                return diagram_controller.generate_diagram()
            else:
                # 默认使用聊天控制器处理
                return chat_controller.send_message()
        except Exception as e:
            logging.error(f"处理消息时出错: {str(e)}")
            traceback.print_exc()
            return jsonify({"error": f"处理消息时发生错误: {str(e)}"}), 500

    # 拓扑图相关路由
    @app.route('/api/topology/generate', methods=['POST'])
    @jwt_required
    def generate_topology():
        """生成拓扑图"""
        logging.info('处理生成拓扑图请求')
        # 注入当前用户信息到请求上下文
        request.current_user = getattr(request, 'current_user', None)
        return topology_controller.generate_topology()
    
    # 文件相关路由
    @app.route('/api/files/list', methods=['GET', 'POST'])
    @jwt_required
    def list_files():
        """获取文件列表"""
        logging.info('路由: 列出文件')
        # 注入当前用户信息到请求上下文
        request.current_user = getattr(request, 'current_user', None)
        return files_controller.list_files()
    
    @app.route('/api/files/download', methods=['GET'])
    @jwt_required
    def download_file():
        """下载文件"""
        logging.info('处理下载文件请求')
        # 注入当前用户信息到请求上下文
        request.current_user = getattr(request, 'current_user', None)
        return files_controller.download_file()
    
    @app.route('/api/files/deployments/<string:deploy_id>/<string:filename>', methods=['GET'])
    @jwt_required
    def get_deployment_file(deploy_id, filename):
        """获取部署相关文件，例如拓扑图"""
        logging.info(f'路由: 获取部署文件 ID={deploy_id}, 文件={filename}')
        
        # 尝试从URL获取type参数
        deploy_type = request.args.get('type', '')
        
        # 如果URL中没有明确指定类型，根据其他信息进行判断
        if not deploy_type:
            # 检查部署ID是否包含特定前缀，如QR开头表示query类型
            if deploy_id.startswith('QR'):
                deploy_type = 'query'
            # 检查是否来自模板页面或路径包含模板相关关键词
            elif '/workspace/template' in request.headers.get('Referer', ''):
                deploy_type = 'template'
            else:
                # 默认为普通部署类型
                deploy_type = 'deploy'
        
        logging.info(f'确定的部署类型: {deploy_type}')
        
        # 设置参数到请求对象
        request.args = request.args.copy()
        request.args.update({
            'deploy_id': deploy_id, 
            'filename': filename,
            'type': deploy_type
        })
        
        # 注入当前用户信息到请求上下文
        request.current_user = getattr(request, 'current_user', None)
        # 使用FileController的方法处理请求
        from controllers.file_controller import FileController
        file_controller = FileController(config)
        return file_controller.get_deployment_file()
    
    @app.route('/api/files/image', methods=['GET'])
    @jwt_required
    def get_image():
        """获取图像文件"""
        logging.info('处理获取图像请求')
        # 注入当前用户信息到请求上下文
        request.current_user = getattr(request, 'current_user', None)
        return files_controller.get_image()

    # 添加模板相关路由
    @app.route('/api/templates', methods=['GET'])
    @token_required
    def get_templates():
        """获取所有模板"""
        logging.info("路由: 获取所有模板")
        request.current_user = get_current_user(request)
        return template_controller.get_all_templates()
    
    @app.route('/api/template/details', methods=['GET'])
    @token_required
    def get_template_details():
        """获取模板详情"""
        logging.info("路由: 获取模板详情")
        request.current_user = get_current_user(request)
        return template_controller.get_template_details()
    
    @app.route('/api/template/add', methods=['POST'])
    @token_required
    def add_template():
        """添加新模板"""
        logging.info("路由: 添加新模板")
        request.current_user = get_current_user(request)
        return template_controller.add_template()
    
    @app.route('/api/template/delete', methods=['POST'])
    @token_required
    def delete_template():
        """删除模板"""
        logging.info("路由: 删除模板")
        request.current_user = get_current_user(request)
        return template_controller.delete_template()
    
    @app.route('/api/template/update', methods=['POST'])
    @token_required
    def update_template():
        """更新模板"""
        logging.info("路由: 更新模板")
        request.current_user = get_current_user(request)
        return template_controller.update_template()
    
    @app.route('/api/template/image', methods=['GET'])
    def get_template_image():
        """获取模板图片"""
        logging.info("路由: 获取模板图片")
        return template_controller.get_template_image()
    
    @app.route('/api/template/chat', methods=['POST'])
    @token_required
    def get_templates_for_chat():
        """获取聊天中使用的模板列表"""
        logging.info("路由: 获取聊天中使用的模板列表")
        request.current_user = get_current_user(request)
        return template_controller.get_templates_for_chat()
    
    @app.route('/api/template/terraform', methods=['POST'])
    @token_required
    def get_template_terraform():
        """获取模板Terraform内容"""
        logging.info("路由: 获取模板Terraform内容")
        request.current_user = get_current_user(request)
        return template_controller.get_template_terraform()
    
    @app.route('/api/template/update-terraform', methods=['POST'])
    @token_required
    def update_template_terraform():
        """更新模板Terraform内容"""
        logging.info("路由: 更新模板Terraform内容")
        request.current_user = get_current_user(request)
        return template_controller.update_template_terraform()
    
    @app.route('/api/template/deploy', methods=['POST'])
    @token_required
    def deploy_template():
        """部署模板"""
        logging.info("路由: 部署模板")
        request.current_user = get_current_user(request)
        return template_controller.deploy_template()
    
    @app.route('/api/template/deploy/status', methods=['GET'])
    @token_required
    def get_template_deploy_status():
        """获取模板部署状态"""
        logging.info("路由: 获取模板部署状态")
        request.current_user = get_current_user(request)
        return template_controller.get_deploy_status()
    
    @app.route('/api/template/deployments', methods=['GET'])
    @token_required
    def get_template_deployments():
        """获取模板部署列表"""
        logging.info("路由: 获取模板部署列表")
        request.current_user = get_current_user(request)
        return template_controller.get_template_deployments()
    
    @app.route('/api/template/deployment', methods=['GET'])
    @token_required
    def get_template_deployment_details():
        """获取模板部署详情"""
        logging.info("路由: 获取模板部署详情")
        request.current_user = get_current_user(request)
        return template_controller.get_deployment_details()
    
    @app.route('/api/template/files', methods=['GET', 'POST'])
    @token_required
    def get_template_files():
        """获取模板部署文件列表"""
        logging.info("路由: 获取模板部署文件列表")
        request.current_user = get_current_user(request)
        return template_controller.get_template_files()

    # 添加API密钥相关路由
    @app.route('/api/apikeys', methods=['GET'])
    @token_required
    def get_api_keys():
        """获取当前用户的API密钥列表"""
        logging.info("路由: 获取API密钥列表")
        try:
            return apikey_controller.get_api_keys()
        except Exception as e:
            logging.error(f"路由处理异常 - 获取API密钥列表: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({"error": "获取API密钥列表失败", "detail": str(e)}), 500
    
    @app.route('/api/apikeys', methods=['POST'])
    @token_required
    def add_api_key():
        """添加新的API密钥"""
        logging.info("路由: 添加API密钥")
        try:
            return apikey_controller.add_api_key()
        except Exception as e:
            logging.error(f"路由处理异常 - 添加API密钥: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({"error": "添加API密钥失败", "detail": str(e)}), 500
    
    @app.route('/api/apikeys/<int:key_id>', methods=['PUT'])
    @token_required
    def update_api_key(key_id):
        """更新指定的API密钥"""
        logging.info(f"路由: 更新API密钥 ID={key_id}")
        try:
            return apikey_controller.update_api_key(key_id)
        except Exception as e:
            logging.error(f"路由处理异常 - 更新API密钥: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({"error": "更新API密钥失败", "detail": str(e)}), 500
    
    @app.route('/api/apikeys/<int:key_id>', methods=['DELETE'])
    @token_required
    def delete_api_key(key_id):
        """删除指定的API密钥"""
        logging.info(f"路由: 删除API密钥 ID={key_id}")
        try:
            return apikey_controller.delete_api_key(key_id)
        except Exception as e:
            logging.error(f"路由处理异常 - 删除API密钥: {str(e)}")
            logging.error(traceback.format_exc())
            return jsonify({"error": "删除API密钥失败", "detail": str(e)}), 500

    # 添加图表生成路由
    @app.route('/api/diagram/generate', methods=['POST'])
    @token_required
    def generate_diagram():
        logging.info("路由: 生成拓扑图")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return diagram_controller.generate_diagram()
        
    # AI部署相关路由
    @app.route('/api/terraform/deploy', methods=['POST'])
    @token_required
    def deploy_terraform():
        logging.info("路由: 部署Terraform")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return terraform_controller.deploy_terraform()
    
    # 添加大型Terraform部署的分批上传路由
    @app.route('/api/terraform/deploy/init', methods=['POST'])
    @token_required
    def init_terraform_deploy():
        logging.info("路由: 初始化分批Terraform部署")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return terraform_controller.deploy_terraform_init()
    
    @app.route('/api/terraform/deploy/part', methods=['POST'])
    @token_required
    def upload_terraform_part():
        logging.info("路由: 上传Terraform代码片段")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return terraform_controller.deploy_terraform_part()
    
    @app.route('/api/terraform/deploy/complete', methods=['POST'])
    @token_required
    def complete_terraform_deploy():
        logging.info("路由: 完成Terraform部署上传并开始部署")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return terraform_controller.deploy_terraform_complete()
    
    @app.route('/api/terraform/deployments', methods=['GET'])
    @token_required
    def list_terraform_deployments():
        logging.info("路由: 获取Terraform部署列表")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return terraform_controller.list_deployments()
    
    @app.route('/api/terraform/status', methods=['GET'])
    @token_required
    def get_terraform_status():
        logging.info("路由: 获取Terraform部署状态")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        deploy_id = request.args.get('deploy_id')
        return terraform_controller.get_deployment_status(deploy_id)

    # 添加新的AI部署详情和资源获取路由
    @app.route('/api/terraform/deployment', methods=['GET'])
    @token_required
    def get_ai_deployment_details():
        logging.info("路由: 获取AI部署详情")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        return terraform_controller.get_ai_deployment_details()
    
    @app.route('/api/terraform/file', methods=['GET'])
    def get_ai_deployment_file():
        logging.info("路由: 获取AI部署文件")
        return terraform_controller.get_ai_deployment_file()
    
    @app.route('/api/terraform/topology', methods=['GET'])
    def get_ai_deployment_topology():
        logging.info("路由: 获取AI部署拓扑图")
        return terraform_controller.get_ai_deployment_topology()

    # 添加云服务提供商相关路由
    @app.route('/api/clouds', methods=['GET'])
    def get_all_clouds():
        """获取所有云服务提供商列表"""
        logging.info("路由: 获取所有云服务提供商列表")
        return clouds_controller.get_all_clouds()
    
    @app.route('/api/clouds/id', methods=['GET'])
    def get_cloud_by_id():
        """根据ID获取云服务提供商信息"""
        logging.info("路由: 根据ID获取云服务提供商信息")
        return clouds_controller.get_cloud_by_id()
    
    @app.route('/api/clouds/name', methods=['GET'])
    def get_cloud_by_name():
        """根据名称获取云服务提供商信息"""
        logging.info("路由: 根据名称获取云服务提供商信息")
        return clouds_controller.get_cloud_by_name()
    
    @app.route('/api/clouds', methods=['POST'])
    @token_required
    def add_cloud():
        """添加新的云服务提供商"""
        logging.info("路由: 添加新的云服务提供商")
        request.current_user = get_current_user(request)
        return clouds_controller.add_cloud()
    
    @app.route('/api/clouds', methods=['PUT'])
    @token_required
    def update_cloud():
        """更新云服务提供商信息"""
        logging.info("路由: 更新云服务提供商信息")
        request.current_user = get_current_user(request)
        return clouds_controller.update_cloud()
    
    @app.route('/api/clouds', methods=['DELETE'])
    @token_required
    def delete_cloud():
        """删除云服务提供商"""
        logging.info("路由: 删除云服务提供商")
        request.current_user = get_current_user(request)
        return clouds_controller.delete_cloud()

    # 聊天文件上传与获取路由
    @app.route('/api/chat/upload', methods=['POST'])
    @token_required
    def upload_chat_file():
        """处理聊天窗口的文件上传"""
        logging.info('路由: 处理聊天文件上传')
        # 注入当前用户信息到请求上下文
        request.current_user = get_current_user(request)
        return files_controller.upload_chat_file()
    
    @app.route('/api/chat/files/<string:username>/<string:filename>', methods=['GET'])
    def get_chat_file(username, filename):
        """获取聊天上传的文件"""
        logging.info(f'路由: 获取聊天文件 user={username}, file={filename}')
        return files_controller.get_chat_file(username, filename)

    # 停止部署路由
    @app.route('/api/terraform/deploy/stop', methods=['POST'])
    @token_required
    def stop_terraform_deployment():
        """停止指定的Terraform部署任务"""
        logging.info("路由: 停止Terraform部署")
        # 在请求中注入当前用户信息
        request.current_user = get_current_user(request)
        data = request.get_json()
        if not data or 'deploy_id' not in data:
            return jsonify({"success": False, "message": "缺少deploy_id参数"}), 400
        
        deploy_id = data.get('deploy_id')
        result = terraform_controller.stop_deployment(deploy_id)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
