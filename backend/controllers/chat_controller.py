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
import json
import traceback

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
            
            # 获取当前用户信息
            user_id = request.current_user.get('user_id')
            username = request.current_user.get('username')
            
            # 保存用户消息到数据库
            if user_id and username:
                self.save_chat_message(user_id, username, message, 'user')
            
            # 检查是否是FAQ查询
            faq_result = self.check_faq_query(message)
            if faq_result:
                self.logger.info(f"检测到FAQ查询: {message}")
                
                # 检查是否是第8个问题，直接返回特殊回复
                if faq_result.get('is_question_8'):
                    self.logger.info("检测到第8个FAQ问题，直接返回功能介绍")
                    
                    # 生成带有可点击元素的回复
                    reply_content = """你可以输入如下命令让我干活噢：
<span style="color: #409EFF; cursor: pointer; text-decoration: underline;" onclick="window.triggerCommand('@查询')">@查询</span>:「查询云资源」
<span style="color: #409EFF; cursor: pointer; text-decoration: underline;" onclick="window.triggerCommand('@部署')">@部署</span>:「部署云组件」
<span style="color: #409EFF; cursor: pointer; text-decoration: underline;" onclick="window.triggerCommand('@模版部署')">@模版部署</span>:「通过terraform模版一键部署多个云组件」
<span style="color: #409EFF; cursor: pointer; text-decoration: underline;" onclick="window.triggerAiMode()">@ai</span> '自然语言描述你想部署的云项目'
点+上传你的架构草图或者手稿 + <span style="color: #409EFF; cursor: pointer; text-decoration: underline;" onclick="window.triggerAiMode()">@ai</span> '对于附件的补充说明' ,来根据附件生成架构图及terraform脚本
tips:执行前需要先添加你的云账号的<span style="color: #409EFF; cursor: pointer; text-decoration: underline;" onclick="window.openApiKeyDialog()">「api-key」</span>噢~ ：）"""

                    response = {
                        "reply": reply_content,
                        "success": True,
                        "is_deepseek_response": False,
                        "is_faq_8": True  # 标记这是FAQ第8题的回复
                    }
                    
                    # 保存系统回复到数据库
                    if user_id and username:
                        self.save_chat_message(user_id, username, reply_content, 'system')
                    
                    return jsonify(response)
                
                # 其他FAQ问题继续发送给AI处理
                faq_enhanced_message = f"用户询问FAQ问题。{faq_result['content']}"
                message = faq_enhanced_message
            
            # 检查是否是AI图表生成触发词 @ai
            if message.startswith('@ai'):
                self.logger.info("检测到 @ai 前缀，调用拓扑图生成")
                
                # 在请求中注入当前用户信息
                request.current_user = get_current_user(request)
                
                # 自动检测用户消息中的云平台，更新cloud参数
                try:
                    self.logger.info(f"开始云平台检测，消息内容: {message}")
                    
                    # 检查模块是否可以正常导入
                    try:
                        from prompts.cloud_terraform_prompts import CloudTerraformPrompts
                        self.logger.info("成功导入 CloudTerraformPrompts 模块")
                    except ImportError as import_error:
                        self.logger.error(f"导入 CloudTerraformPrompts 模块失败: {str(import_error)}")
                        raise import_error
                    
                    # 检测云平台
                    detected_cloud = CloudTerraformPrompts.detect_cloud_from_description(message)
                    self.logger.info(f"CloudTerraformPrompts.detect_cloud_from_description 返回: {detected_cloud}")
                    
                    # 将检测到的云平台映射为前端使用的格式
                    cloud_mapping = {
                        "AWS": "AWS",
                        "AWS(CHINA)": "AWS(CHINA)",
                        "AZURE": "AZURE", 
                        "AZURE(CHINA)": "AZURE(CHINA)",
                        "阿里云": "阿里云",
                        "华为云": "华为云", 
                        "腾讯云": "腾讯云",
                        "百度云": "百度云",
                        "火山云": "火山云"
                    }
                    
                    mapped_cloud = cloud_mapping.get(detected_cloud, data.get('cloud', 'AWS'))
                    self.logger.info(f"云平台映射: {detected_cloud} -> {mapped_cloud}")
                    
                    # 更新data中的cloud参数
                    original_cloud = data.get('cloud', 'AWS')
                    data['cloud'] = mapped_cloud
                    self.logger.info(f"云平台参数更新: {original_cloud} -> {mapped_cloud}")
                    self.logger.info(f"检测到云平台: {detected_cloud}, 映射为: {mapped_cloud}")
                    
                except Exception as cloud_detect_error:
                    self.logger.error(f"云平台检测失败: {str(cloud_detect_error)}")
                    self.logger.error(f"异常类型: {type(cloud_detect_error).__name__}")
                    self.logger.error(f"异常详情: {traceback.format_exc()}")
                    self.logger.info(f"使用默认云平台: {data.get('cloud', 'AWS')}")
                
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
                        
                        # 保存系统回复到数据库
                        if user_id and username:
                            self.save_chat_message(user_id, username, "根据您的描述，生成的拓扑图如下：", 'system')
                        
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
                reply_text = f"您本次查询项目：{project} ； 您本次查询云：{cloud} ； 请输入AKSK："
                response_data = {
                    "reply": reply_text,
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
                
                # 保存系统回复到数据库
                if user_id and username:
                    self.save_chat_message(user_id, username, reply_text, 'system')
                
                return jsonify(response_data)
            
            # 使用DeepSeek API处理所有消息
            from utils.deepseek_api import query_deepseek
            
            # 构建系统提示词（可根据需要自定义）
            system_prompt = "你是「aiops」运维小助手，可以帮助用户进行全球8云资源的查询、部署和管理。请用通俗易懂+简洁的风格回复我。"
            
            # 检测是否为功能询问类消息
            function_keywords = ['hi', 'hello', '你能干啥', '你能做啥', '你的功能', '功能有哪些', '能干什么', '可以做什么', '怎么用', '如何使用']
            is_function_inquiry = any(keyword in message.lower() for keyword in function_keywords)
            
            if is_function_inquiry:
                system_prompt += """

你可以尝试使用如下命令让我干活噢：
@查询:「查询云资源」
@部署:「部署云组件」
@模版部署:「通过terraform模版一键部署多个云组件」
@ai '自然语言描述你想部署的云项目'
点+上传你的架构草图或者手稿 + @ai '对于附件的补充说明' ,来根据附件生成架构图及terraform脚本
tips:执行前需要先添加你的云账号的「api-key」噢~ ：）"""
            
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
            
            # 保存系统回复到数据库
            if user_id and username:
                self.save_chat_message(user_id, username, result['content'], 'system')
            
            return jsonify(response)

        except Exception as e:
            self.logger.error(f"处理聊天请求时出错: {str(e)}", exc_info=True) # 添加 exc_info=True 记录完整堆栈
            return jsonify({
                "reply": "抱歉，处理您的请求时发生错误。请稍后再试。",
                "error": str(e)
            }), 500

    def send_message_stream(self):
        """处理聊天消息流式发送请求，使用 DeepSeek API 流式处理"""
        self.logger.info("开始处理流式聊天请求")
        
        # 在请求上下文中获取数据
        data = request.get_json()
        if not data or 'message' not in data:
            self.logger.warning("流式聊天请求缺少消息字段")
            return jsonify({"error": "请提供消息内容"}), 400
        
        message = data['message']
        project = data.get('project', '')
        cloud = data.get('cloud', '')
        
        # 获取当前用户信息
        user_id = request.current_user.get('user_id')
        username = request.current_user.get('username')
        
        # 保存用户消息到数据库
        if user_id and username:
            self.save_chat_message(user_id, username, message, 'user')
        
        def stream_generator():
            try:
                self.logger.info("流式生成器开始执行")
                self.logger.info(f"收到流式聊天请求: {message}")
                
                # 声明一个变量来存储处理后的消息
                processed_message = message
                
                # 检查是否是FAQ查询
                faq_result = self.check_faq_query(message)
                if faq_result:
                    self.logger.info(f"流式聊天检测到FAQ查询: {message}")
                    
                    # 检查是否是第8个问题，直接返回特殊回复
                    if faq_result.get('is_question_8'):
                        self.logger.info("流式聊天检测到第8个FAQ问题，重定向到普通聊天")
                        yield f"data: {json.dumps({'redirect_to_normal': True, 'done': True})}\n\n".encode('utf-8')
                        return
                    
                    # 其他FAQ问题继续发送给AI处理
                    processed_message = f"用户询问FAQ问题。{faq_result['content']}"
                
                # 检查是否是AI图表生成触发词 @ai - 这些不适合流式输出，保持原有逻辑
                if message.startswith('@ai'):
                    self.logger.info("检测到@ai命令，重定向到普通聊天")
                    yield f"data: {json.dumps({'redirect_to_normal': True, 'done': True})}\n\n".encode('utf-8')
                    return
                
                # 检查是否是部署触发词 - 这些也不适合流式输出
                if '@查询' in message or '@部署' in message or '@模版部署' in message:
                    self.logger.info("检测到特殊命令（@查询/@部署/@模版部署），重定向到普通聊天")
                    yield f"data: {json.dumps({'redirect_to_normal': True, 'done': True})}\n\n".encode('utf-8')
                    return
                
                # 使用DeepSeek API流式处理消息
                from utils.deepseek_api import query_deepseek_stream
                
                # 构建系统提示词
                system_prompt = "你是「aiops」运维小助手，可以帮助用户进行全球8云资源的查询、部署和管理。请用通俗易懂+简洁的风格回复我。"
                
                # 检测是否为功能询问类消息
                function_keywords = ['hi', 'hello', '你能干啥', '你能做啥', '你的功能', '功能有哪些', '能干什么', '可以做什么', '怎么用', '如何使用']
                is_function_inquiry = any(keyword in processed_message.lower() for keyword in function_keywords)
                
                if is_function_inquiry:
                    system_prompt += """

你可以尝试使用如下命令让我干活噢：
@查询:「查询云资源」
@部署:「部署云组件」
@模版部署:「通过terraform模版一键部署多个云组件」
@ai '自然语言描述你想部署的云项目'
点+上传你的架构草图或者手稿 + @ai '对于附件的补充说明' ,来根据附件生成架构图及terraform脚本
tips:执行前需要先添加你的云账号的「api-key」噢~ ：）"""
                
                # 如果有项目和云信息，添加到系统提示中
                if project and cloud:
                    system_prompt += f" 用户当前选择的项目是 {project}，云服务商是 {cloud}。"
                
                # 检查是否是以"/"开头的命令
                is_command_message = processed_message.startswith('/')
                if is_command_message:
                    system_prompt = "我的需求仅仅以云配置jason格式返回给我"
                    self.logger.info(f"检测到'/'命令，使用JSON提取模式: {processed_message}")
                
                # 调用DeepSeek流式API
                self.logger.info(f"通过DeepSeek流式API处理消息: {processed_message}, 命令模式: {is_command_message}")
                
                # 发送开始信号
                self.logger.info("发送流式开始信号")
                yield f"data: {json.dumps({'start': True, 'is_deepseek_response': True, 'done': False})}\n\n".encode('utf-8')
                
                # 处理流式响应
                chunk_count = 0
                full_content = ""
                for chunk in query_deepseek_stream(processed_message, system_prompt, is_command_message):
                    chunk_count += 1
                    if chunk_count <= 5 or chunk_count % 50 == 0:  # 前5个和每50个记录一次日志
                        self.logger.info(f"发送数据块 {chunk_count}: {chunk[:100]}...")
                    
                    # 尝试解析chunk以获取完整内容
                    try:
                        if chunk.startswith('data: '):
                            chunk_data = json.loads(chunk[6:])
                            if chunk_data.get('done') and 'full_content' in chunk_data:
                                full_content = chunk_data['full_content']
                    except:
                        pass
                    
                    yield chunk.encode('utf-8')
                    
                    # 强制刷新 - 发送空行来触发立即传输
                    if chunk_count % 5 == 0:  # 每5个块强制刷新一次
                        yield "\n".encode('utf-8')
                
                self.logger.info(f"流式处理完成，共处理 {chunk_count} 个数据块")
                
                # 保存系统回复到数据库
                if user_id and username and full_content:
                    self.save_chat_message(user_id, username, full_content, 'system')
                
            except Exception as e:
                self.logger.error(f"处理流式聊天请求时出错: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'error': f'处理请求时发生错误: {str(e)}', 'done': True})}\n\n".encode('utf-8')
        
        try:
            from flask import Response
            import sys
            self.logger.info("创建流式响应")
            
            def stream_with_flush():
                """包装生成器，每次yield后立即刷新"""
                for data in stream_generator():
                    yield data
                    # 强制刷新标准输出和错误输出
                    sys.stdout.flush()
                    sys.stderr.flush()
            
            response = Response(
                stream_with_flush(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0',
                    'Connection': 'keep-alive',
                    'Content-Type': 'text/event-stream; charset=utf-8',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Cache-Control',
                    'X-Accel-Buffering': 'no'  # 禁用Nginx缓冲
                }
            )
            
            # 设置直接输出模式
            response.direct_passthrough = True
            
            return response
            
        except Exception as e:
            self.logger.error(f"创建流式响应时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"创建流式响应失败: {str(e)}"}), 500

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
        """获取用户的部署历史"""
        try:
            # 获取当前用户信息
            user_id = request.current_user.get('user_id')
            username = request.current_user.get('username')
            
            self.logger.info(f"获取用户部署历史: {username} (ID: {user_id})")
            
            # 调用云控制器获取部署历史
            return self.cloud_controller.get_user_deployments()
        except Exception as e:
            self.logger.error(f"获取用户部署历史失败: {str(e)}", exc_info=True)
            return jsonify({"error": f"获取部署历史失败: {str(e)}"}), 500
            
    def get_deployment_details(self):
        """获取部署详情"""
        try:
            # 调用云控制器获取部署详情
            return self.cloud_controller.get_deployment_details()
        except Exception as e:
            self.logger.error(f"获取部署详情失败: {str(e)}", exc_info=True)
            return jsonify({"error": f"获取部署详情失败: {str(e)}"}), 500

    def save_chat_message(self, user_id, username, message, message_type='user', session_id=None, metadata=None):
        """保存聊天消息到数据库
        
        Args:
            user_id: 用户ID
            username: 用户名
            message: 消息内容
            message_type: 消息类型 ('user' 或 'system')
            session_id: 会话ID（可选）
            metadata: 元数据（可选）
        """
        try:
            from utils.database import get_db_connection
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # 根据消息类型设置question和answer字段
            # 确保question字段不为空（数据库要求NOT NULL）
            if message_type == 'user':
                question = message
                answer = None
            else:
                question = ""  # 系统消息的question设为空字符串
                answer = message
            
            # 插入聊天记录
            self.logger.info(f"准备保存聊天消息: 用户ID={user_id}, 用户名={username}, 消息类型={message_type}")
            self.logger.info(f"消息内容预览: question='{question[:50] if question else 'None'}...', answer='{answer[:50] if answer else 'None'}...'")
            
            cursor.execute("""
                INSERT INTO chat_history 
                (user_id, username, question, answer, message_type, session_id, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (user_id, username, question, answer, message_type, session_id, 
                  json.dumps(metadata) if metadata else None))
            
            connection.commit()
            cursor.close()
            connection.close()
            
            self.logger.info(f"保存聊天消息成功: 用户={username}, 类型={message_type}")
            
        except Exception as e:
            self.logger.error(f"保存聊天消息失败: {str(e)}", exc_info=True)

    def get_chat_history(self):
        """获取用户的聊天历史记录"""
        try:
            # 获取当前用户信息
            user_id = request.current_user.get('user_id')
            username = request.current_user.get('username')
            
            if not user_id or not username:
                return jsonify({"error": "用户信息无效"}), 401
                
            # 获取清屏时间点参数（可选）
            clear_time = request.args.get('clear_time')
            self.logger.info(f"🔍 获取聊天历史请求，用户: {username}, 清屏时间: {clear_time}")
            
            from utils.database import get_db_connection
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # 先检查表中总共有多少条记录
            cursor.execute("SELECT COUNT(*) as total FROM chat_history")
            result = cursor.fetchone()
            total_count = result.get('total', 0) if isinstance(result, dict) else result[0]
            self.logger.info(f"chat_history表中总共有 {total_count} 条记录")
            
            # 查询该用户的所有记录数量
            cursor.execute("SELECT COUNT(*) as user_total FROM chat_history WHERE username = %s", (username,))
            result = cursor.fetchone()
            user_count = result.get('user_total', 0) if isinstance(result, dict) else result[0]
            self.logger.info(f"用户 {username} 在chat_history表中有 {user_count} 条记录")
            
            # 构建查询SQL和参数
            if clear_time:
                # 将UTC时间转换为本地时间进行比较
                from datetime import datetime
                try:
                    # 解析ISO时间字符串并转换为本地时间
                    utc_time = datetime.fromisoformat(clear_time.replace('Z', '+00:00'))
                    # 转换为本地时间字符串用于数据库查询
                    local_time_str = utc_time.strftime('%Y-%m-%d %H:%M:%S')
                    self.logger.info(f"🔍 时间转换：UTC {clear_time} -> 本地 {local_time_str}")
                except Exception as time_error:
                    self.logger.error(f"时间转换失败: {time_error}, 使用原始时间")
                    local_time_str = clear_time
                
                # 如果有清屏时间点，只查询该时间之后的记录
                self.logger.info(f"🔍 使用清屏时间过滤，用户名: {username}，清屏时间: {local_time_str}")
                # 使用MySQL的CONVERT_TZ函数确保时间比较正确
                sql = """
                    SELECT id, question, answer, message_type, session_id, metadata, created_at
                    FROM chat_history 
                    WHERE username = %s AND created_at > CONVERT_TZ(%s, '+00:00', @@session.time_zone)
                    ORDER BY created_at ASC
                """
                params = (username, clear_time)  # 直接使用UTC时间，让MySQL进行转换
            else:
                # 查询用户的聊天历史，按时间顺序排列
                self.logger.info(f"🔍 查询所有历史，用户名: {username}")
                sql = """
                    SELECT id, question, answer, message_type, session_id, metadata, created_at
                    FROM chat_history 
                    WHERE username = %s 
                    ORDER BY created_at ASC
                """
                params = (username,)
            
            cursor.execute(sql, params)
            
            records = cursor.fetchall()
            self.logger.info(f"🔍 数据库查询结果: {len(records)} 条记录")
            if clear_time and len(records) > 0:
                self.logger.info(f"🔍 过滤后的第一条记录时间: {records[0]}")
            elif clear_time and len(records) == 0:
                self.logger.info(f"🔍 清屏时间 {clear_time} 之后没有新的聊天记录")
            if records:
                self.logger.info(f"第一条记录示例: {records[0]}")
            
            cursor.close()
            connection.close()
            
            # 转换为前端需要的格式
            messages = []
            for record in records:
                # 兼容字典和元组两种格式
                if isinstance(record, dict):
                    # 字典格式
                    id_val = record.get('id')
                    question = record.get('question')
                    answer = record.get('answer')
                    message_type = record.get('message_type')
                    session_id = record.get('session_id')
                    metadata = record.get('metadata')
                    created_at = record.get('created_at')
                else:
                    # 元组格式: (id, question, answer, message_type, session_id, metadata, created_at)
                    id_val, question, answer, message_type, session_id, metadata, created_at = record
                
                if message_type == 'user' and question:
                    # 用户消息
                    messages.append({
                        'type': 'user',
                        'content': question,
                        'timestamp': created_at.isoformat() if created_at else None,
                        'id': id_val
                    })
                elif message_type == 'system' and answer:
                    # 系统消息
                    messages.append({
                        'type': 'system', 
                        'content': answer,
                        'timestamp': created_at.isoformat() if created_at else None,
                        'id': id_val
                    })
            
            self.logger.info(f"获取聊天历史成功: 用户={username}, 消息数量={len(messages)}")
            
            return jsonify({
                "success": True,
                "messages": messages,
                "total": len(messages)
            })
            
        except Exception as e:
            self.logger.error(f"获取聊天历史失败: {str(e)}", exc_info=True)
            return jsonify({"error": f"获取聊天历史失败: {str(e)}"}), 500

    def check_faq_query(self, message):
        """检查是否是FAQ查询并返回对应的问题和答案
        
        Args:
            message: 用户输入的消息
            
        Returns:
            dict: 包含FAQ内容和标识信息的字典，如果不是FAQ查询则返回None
        """
        try:
            from utils.database import get_db_connection
            
            # 清理输入消息
            cleaned_message = message.strip()
            
            # 检查数字模式：1, 1., 2, 2., 等
            import re
            number_match = re.match(r'^(\d+)\.?$', cleaned_message)
            if number_match:
                faq_id = int(number_match.group(1))
                return self.get_faq_by_id(faq_id)
            
            # 检查是否是完整问题内容匹配
            return self.get_faq_by_question(cleaned_message)
            
        except Exception as e:
            self.logger.error(f"检查FAQ查询失败: {str(e)}", exc_info=True)
            return None
    
    def get_faq_by_id(self, faq_id):
        """根据FAQ ID获取问题和答案
        
        Args:
            faq_id: FAQ的序号
            
        Returns:
            dict: 包含FAQ内容和标识信息的字典，如果未找到则返回None
        """
        try:
            from utils.database import get_db_connection
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            cursor.execute("SELECT Q, A FROM start WHERE id = %s", (faq_id,))
            result = cursor.fetchone()
            
            cursor.close()
            connection.close()
            
            if result:
                if isinstance(result, dict):
                    question = result.get('Q')
                    answer = result.get('A')
                else:
                    question, answer = result
                
                return {
                    'content': f"问题：{question} 答案：{answer}",
                    'is_question_8': faq_id == 8,
                    'faq_id': faq_id,
                    'question': question,
                    'answer': answer
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"根据ID获取FAQ失败: {str(e)}", exc_info=True)
            return None
    
    def get_faq_by_question(self, question_text):
        """根据问题内容获取FAQ
        
        Args:
            question_text: 问题文本
            
        Returns:
            dict: 包含FAQ内容和标识信息的字典，如果未找到则返回None
        """
        try:
            from utils.database import get_db_connection
            
            connection = get_db_connection()
            cursor = connection.cursor()
            
            # 精确匹配或者模糊匹配，同时获取id
            cursor.execute("SELECT id, Q, A FROM start WHERE Q = %s OR Q LIKE %s", 
                          (question_text, f"%{question_text}%"))
            result = cursor.fetchone()
            
            cursor.close()
            connection.close()
            
            if result:
                if isinstance(result, dict):
                    faq_id = result.get('id')
                    question = result.get('Q')
                    answer = result.get('A')
                else:
                    faq_id, question, answer = result
                
                return {
                    'content': f"问题：{question} 答案：{answer}",
                    'is_question_8': faq_id == 8,
                    'faq_id': faq_id,
                    'question': question,
                    'answer': answer
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"根据问题内容获取FAQ失败: {str(e)}", exc_info=True)
            return None

