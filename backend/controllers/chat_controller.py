import logging
from flask import request, jsonify
# 使用相对导入
from config.config import Config
# 移除 MCPClient 和 ResponseFormatter 的导入
# from utils.mcp_client import MCPClient
# from utils.response_formatter import ResponseFormatter

# 导入新的模块 (使用相对导入)
from agents.chat_agent import ChatAgent
from memories.chat_history_memory import ChatHistoryMemory
from messages.base import BaseMessage # 用于类型检查
from retrievers.rag_retriever import RAGRetriever
from controllers.cloud_controller import CloudController  # 新增导入
from utils.auth import get_current_user  # 添加 get_current_user 导入

class ChatController:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 定义系统消息和模型名称
        system_message = "You are a helpful assistant for the Multi-Cloud Deployment Platform (MCDP)."
        # 使用 ModelManager 的默认模型 "gpt-4"，确保 API 密钥在环境中配置
        model_name = "ollama/deepseek-r1:32b" # 使用用户指定的本地 Ollama 模型
        
        # 定义要搜索的数据集列表
        dataset_ids = [
            "b4d3be0c16a411f09945d220a28f9367",  # 原始数据集
            "e8e85b2e1b6011f0be3d2ec89ce5a211",
            "49eef02a1aaa11f0b8b2722aebe90565",
            "4013d7f01aaa11f08a18722aebe90565",
            "def571221aa911f08f9f722aebe90565",
            "227a634a1aa911f0a042722aebe90565"
        ]
        
        # 初始化 RAGRetriever 使用多个数据集
        self.retriever = RAGRetriever(
            endpoint="http://rag.cloudet.cn:9382/sse",
            dataset_ids=dataset_ids
        )
        self.logger.info(f"RAGRetriever initialized with {len(dataset_ids)} datasets")
        
        # 初始化 ChatAgent (使用单例模式简化，后续可改为会话管理)
        # TODO: 考虑内存管理策略（例如，基于用户会话）
        self.memory = ChatHistoryMemory()
        try:
            self.chat_agent = ChatAgent(
                system_message=system_message,
                model_name=model_name, 
                memory=self.memory,
                retriever=self.retriever
            )
            self.logger.info(f"ChatAgent initialized successfully with model: {model_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize ChatAgent with model {model_name}: {str(e)}", exc_info=True)
            # 如果ChatAgent初始化失败，设置一个标志或抛出异常，以便在send_message中处理
            self.chat_agent = None
            
        # 初始化云控制器
        self.cloud_controller = CloudController(config)

    def send_message(self):
        """处理聊天消息发送请求，使用 DeepSeek API 处理所有消息"""
        try:
            # 获取请求数据
            data = request.get_json()
            if not data or 'message' not in data:
                self.logger.warning("Received chat request with missing message field.")
                return jsonify({"error": "请提供消息内容"}), 400
            
            message = data['message']
            self.logger.info(f"Received chat request: {message}")
            
            # 检查是否是AI图表生成触发词 @ai
            if message.startswith('@ai'):
                self.logger.info("检测到 @ai 前缀，调用拓扑图生成")
                
                # 在请求中注入当前用户信息
                request.current_user = get_current_user(request)
                
                # 获取上传的图片路径（如果有）
                uploaded_image_path = data.get('uploaded_image_path')
                if uploaded_image_path:
                    self.logger.info(f"检测到上传的图片路径: {uploaded_image_path}")
                
                # 调用图表控制器生成图表
                try:
                    from controllers.diagram_controller import DiagramController
                    diagram_controller = DiagramController(self.config)
                    
                    # 打印完整请求数据用于调试
                    self.logger.info(f"传递给diagram_controller的完整数据: {data}")
                    
                    # 将完整的请求数据传递给diagram_controller
                    # 这里不要直接调用generate_diagram，而是通过flask的request对象传递数据
                    # 使用Flask的request_context来创建一个新的请求上下文
                    from flask import request as flask_request
                    
                    # 保存当前请求对象的引用
                    original_request = flask_request
                    
                    # 使用原始request对象的上下文，但更新json数据
                    # 注意：这里直接使用request.get_json()._cached_json
                    # 因为Flask的request.get_json()会缓存解析后的JSON数据
                    try:
                        # 确保请求中包含了uploaded_image_path
                        if uploaded_image_path and not data.get('uploaded_image_path'):
                            data['uploaded_image_path'] = uploaded_image_path
                            
                        # 更新请求的json数据（如果_cached_json存在）
                        if hasattr(request, 'get_json') and callable(request.get_json):
                            json_data = request.get_json(silent=True)
                            if json_data is not None and hasattr(json_data, '_cached_json'):
                                json_data._cached_json = data
                    except Exception as context_error:
                        self.logger.error(f"尝试更新请求数据时出错: {str(context_error)}")
                    
                    # 调用图表生成方法
                    result = diagram_controller.generate_diagram()
                    
                    # 如果返回的是元组 (response, status_code)，则取出实际的响应
                    if isinstance(result, tuple) and len(result) > 0:
                        result = result[0]
                    
                    # 从返回的JSON中获取数据
                    result_data = result.get_json() if hasattr(result, 'get_json') else result
                    
                    # 构建包含图表的响应
                    if result_data.get('success', False):
                        mermaid_code = result_data.get('mermaid_code', '')
                        
                        # 获取Terraform部署代码
                        terraform_code = ""
                        try:
                            from controllers.terraform_controller import TerraformController
                            tf_controller = TerraformController(self.config)
                            tf_result = tf_controller.generate_terraform_code(message, mermaid_code)
                            
                            if isinstance(tf_result, tuple) and len(tf_result) > 0:
                                tf_result = tf_result[0]
                                
                            tf_result_data = tf_result.get_json() if hasattr(tf_result, 'get_json') else tf_result
                            
                            if tf_result_data.get('success', False):
                                terraform_code = tf_result_data.get('terraform_code', '')
                        except Exception as tf_error:
                            self.logger.error(f"获取Terraform代码时出错: {str(tf_error)}", exc_info=True)
                            terraform_code = ""  # 确保失败时也有默认值
                        
                        response_data = {
                            "reply": "根据您的描述，生成的拓扑图如下：",
                            "is_diagram": True,
                            "mermaid_code": mermaid_code,
                            "terraform_code": terraform_code, # 添加Terraform代码
                            "can_deploy": len(terraform_code) > 0, # 添加部署标志
                            "original_message": message
                        }
                        return jsonify(response_data)
                    else:
                        # 如果生成失败，返回错误消息
                        error_msg = result_data.get('message', '拓扑图生成失败')
                        return jsonify({
                            "reply": f"生成拓扑图时出错: {error_msg}",
                            "error": result_data.get('error', 'Unknown error')
                        })
                except Exception as e:
                    self.logger.error(f"处理拓扑图生成请求时出错: {str(e)}", exc_info=True)
                    return jsonify({
                        "reply": f"处理拓扑图请求时出错: {str(e)}",
                        "error": str(e)
                    }), 500
            
            # 检查是否是部署触发词
            if '@查询' in message:
                self.logger.info("Detected query trigger in message")
                
                # 获取当前用户信息
                user_id = data.get('user_id', 1)  # 默认用户ID为1
                username = data.get('username', 'admin')  # 默认用户名为admin
                project = data.get('project', '默认项目')  # 获取项目名称
                cloud = data.get('cloud', '默认云')  # 获取云提供商
                
                # 构建部署表单响应
                response_data = {
                    "reply": f"您本次查询项目：{project} ； 您本次查询云：{cloud} ； 请输入AKSK：",
                    "deployment_request": True,
                    "form": {
                        "fields": [
                            {"name": "ak", "label": "AK", "type": "text"},
                            {"name": "sk", "label": "SK", "type": "password"}
                        ],
                        "submit_text": "确定",
                        "metadata": {
                            "user_id": user_id,
                            "username": username,
                            "project": project,
                            "cloud": cloud
                        }
                    }
                }
                
                return jsonify(response_data)
            
            # 使用DeepSeek API处理所有消息
            from utils.deepseek_api import query_deepseek
            
            # 构建系统提示词（可根据需要自定义）
            system_prompt = "你是多云部署平台(MCDP)的助手，可以帮助用户进行云资源的部署、查询和管理。"
            
            # 获取用户信息和环境信息
            project = data.get('project', '')
            cloud = data.get('cloud', '')
            
            # 如果有项目和云信息，添加到系统提示中
            if project and cloud:
                system_prompt += f" 用户当前选择的项目是 {project}，云服务商是 {cloud}。"
            
            # 检查是否是以"/"开头的命令，决定是否需要提取JSON
            is_command_message = message.startswith('/')
            if is_command_message:
                # 对于"/开头"的命令，使用原有逻辑，强调需要JSON格式的返回
                system_prompt = "我的需求仅仅以云配置jason格式返回给我"
                self.logger.info(f"检测到'/'命令，使用JSON提取模式: {message}")
                
            # 调用DeepSeek API，传入正确的is_command参数
            self.logger.info(f"通过DeepSeek API处理消息: {message}, 命令模式: {is_command_message}")
            result = query_deepseek(message, system_prompt, is_command=is_command_message)
            
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
            
            # 如果成功提取到JSON（仅在命令模式下可能发生），添加到响应中
            if result.get('json_content'):
                response["json_content"] = result['json_content']
                response["has_json"] = True
            
            return jsonify(response)

        except Exception as e:
            self.logger.error(f"处理聊天请求时出错: {str(e)}", exc_info=True) # 添加 exc_info=True 记录完整堆栈
            return jsonify({
                "reply": "抱歉，处理您的请求时发生错误。请稍后再试。",
                "error": str(e)
            }), 500

    def handle_cloud_form_submission(self):
        """处理云表单提交
        """
        try:
            # 获取表单数据并记录
            form_data = request.get_json()
            self.logger.info(f"接收到表单数据: {form_data}")
            if not form_data:
                return jsonify({"error": "表单数据为空"}), 400
            
            form_type = form_data.get("form_type", "")
            
            # 首先获取当前登录用户信息（从JWT）
            current_user_id = None
            current_username = None
            
            # 从请求头中获取JWT token
            auth_header = request.headers.get('Authorization', '')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    from utils.auth import decode_token
                    payload = decode_token(token)
                    if payload and 'user_id' in payload and 'username' in payload:
                        current_user_id = payload['user_id']
                        current_username = payload['username']
                        self.logger.info(f"从JWT成功解析用户信息: ID={current_user_id}, 用户名={current_username}")
                    else:
                        self.logger.error("JWT解析成功但缺少用户信息")
                        return jsonify({"error": "身份验证错误：令牌无效"}), 401
                except Exception as e:
                    self.logger.error(f"JWT解析失败: {str(e)}")
                    return jsonify({"error": f"身份验证错误：{str(e)}"}), 401
            else:
                self.logger.error("请求缺少Authorization头或格式不正确")
                return jsonify({"error": "请提供有效的身份验证令牌"}), 401
            
            # 获取其他表单数据
            project = form_data.get("project", "")
            cloud = form_data.get("cloud", "")
            deploy_id = form_data.get("deploy_id", "")
            
            # 处理AK/SK表单
            if form_type == "aksk":
                # 获取AK/SK
                ak = form_data.get("ak", "")
                sk = form_data.get("sk", "")
                
                # 日志记录（减少输出的敏感信息）
                self.logger.info(f"处理AK/SK表单: 用户={current_username}, 项目={project}, 云={cloud}, 部署ID={deploy_id}")
                
                # 保存到数据库
                success = self.cloud_controller.cloud_model.save_cloud_config(
                    user_id=current_user_id,
                    username=current_username,
                    project=project,
                    cloud=cloud,
                    ak=ak,
                    sk=sk,
                    deployid=deploy_id,
                    force_insert=True  # 强制插入新记录
                )
                
                if not success:
                    return jsonify({"error": "保存AK/SK失败"}), 500
                
                # 获取当前配置的选项
                configs = self.cloud_controller.cloud_model.get_cloud_config(
                    user_id=current_user_id,
                    project=project,
                    cloud=cloud
                )
                
                # 构建响应文本
                response_text = "AK/SK 已保存成功。请选择您要执行的操作："
                
                # 定义选项
                options = [
                    {"id": "query", "text": "查询当前云资源"}
                ]
                
                return jsonify({
                    "reply": response_text,
                    "options": options,
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                })
            else:
                return jsonify({"error": "未知的表单类型"}), 400
        except Exception as e:
            self.logger.error(f"处理表单提交时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理表单时发生错误: {str(e)}"}), 500
            
    def handle_cloud_option_selection(self):
        """处理云资源操作选项选择"""
        try:
            data = request.get_json()
            self.cloud_controller.logger.info(f"接收到选项选择请求: {data}")
            return self.cloud_controller.handle_cloud_option_selection()
        except Exception as e:
            self.cloud_controller.logger.error(f"处理选项选择请求时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理选项选择请求时发生错误: {str(e)}"}), 500

    def handle_region_selection(self):
        """处理区域选择请求"""
        try:
            data = request.get_json()
            self.cloud_controller.logger.info(f"接收到区域选择请求: {data}")
            return self.cloud_controller.handle_region_selection()
        except Exception as e:
            self.cloud_controller.logger.error(f"处理区域选择请求时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理区域选择请求时发生错误: {str(e)}"}), 500
            
    def handle_resource_selection(self):
        """处理资源选择请求"""
        try:
            data = request.get_json()
            self.cloud_controller.logger.info(f"接收到资源选择请求: {data}")
            return self.cloud_controller.handle_resource_selection()
        except Exception as e:
            self.cloud_controller.logger.error(f"处理资源选择请求时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理资源选择请求时发生错误: {str(e)}"}), 500
            
    def handle_cloud_query(self):
        """处理云资源查询请求"""
        try:
            data = request.get_json()
            self.cloud_controller.logger.info(f"接收到云资源查询请求: {data}")
            return self.cloud_controller.handle_cloud_query()
        except Exception as e:
            self.cloud_controller.logger.error(f"处理云资源查询请求时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理云资源查询请求时发生错误: {str(e)}"}), 500
            
    def get_user_deployments(self):
        """获取用户部署历史"""
        try:
            self.cloud_controller.logger.info(f"接收到获取用户部署历史请求")
            return self.cloud_controller.get_user_deployments()
        except Exception as e:
            self.cloud_controller.logger.error(f"处理获取用户部署历史请求时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理获取用户部署历史请求时发生错误: {str(e)}"}), 500
            
    def get_deployment_details(self):
        """获取部署详情"""
        try:
            deploy_id = request.args.get('deploy_id')
            self.cloud_controller.logger.info(f"接收到获取部署详情请求: {deploy_id}")
            return self.cloud_controller.get_deployment_details()
        except Exception as e:
            self.cloud_controller.logger.error(f"处理获取部署详情请求时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理获取部署详情请求时发生错误: {str(e)}"}), 500

