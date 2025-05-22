import os
import logging
import traceback
import json
import requests
import base64
from flask import request, jsonify, current_app
from werkzeug.utils import safe_join
import re

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

class DiagramController:
    def __init__(self, config=None):
        """初始化图表控制器"""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.openai_api_key = os.environ.get('OPENAI_API_KEY', '')
        self.openai_api_base_url = os.environ.get('OPENAI_API_BASE_URL', 'https://api.openai.com/v1')
        self.openai_api_model = os.environ.get('OPENAI_API_MODEL', 'gpt-4o')
        
    def generate_diagram(self):
        """从用户描述生成Mermaid图表"""
        try:
            # 获取请求数据
            data = request.get_json()
            if not data or 'message' not in data:
                return jsonify({"error": "请提供消息内容"}), 400
            
            # 提取消息内容
            message = data.get('message', '').strip()
            
            # 获取并记录当前用户信息
            user = getattr(request, 'current_user', None)
            user_id = user.get('user_id', 0) if user else 0
            username = user.get('username', 'unknown') if user else 'unknown'
                
            self.logger.info(f"用户 {username} (ID: {user_id}) 请求生成图表：")
            
            # 获取上传图片路径
            uploaded_image_path = data.get('uploaded_image_path')
            
            # 记录是否包含图片，方便调试
            if uploaded_image_path:
                self.logger.info(f"检测到上传的图片：{uploaded_image_path}")
            
            # 调用OpenAI API生成Mermaid代码
            api_key = self.openai_api_key or os.environ.get('OPENAI_API_KEY')
            if not api_key:
                return jsonify({"error": "未配置OpenAI API密钥"}), 500
            
            # 构建系统提示
            system_prompt = r"""You are an assistant to help user build diagram with Mermaid.
You only need to return the output Mermaid code block.
Do not include any description, do not include the ```.
Code (no ```):
            """
            
            # 获取API Base URL和模型名称
            api_base_url = self.openai_api_base_url
            if not api_base_url and self.config:
                api_base_url = getattr(self.config, 'openai_api_base_url', 'https://api.openai.com/v1')
            
            model_name = self.openai_api_model
            if not model_name and self.config:
                model_name = getattr(self.config, 'openai_api_model', 'gpt-4o')
                
            # 记录使用的API设置
            self.logger.info(f"使用API Base URL: {api_base_url}")
            self.logger.info(f"使用模型: {model_name}")
            
            # 初始化OpenAI客户端，正确使用自定义base_url
            import openai
            client = openai.OpenAI(
                api_key=api_key,
                base_url=api_base_url
            )
            
            # 构建请求体 - 根据是否有图片采用不同的处理方式
            if uploaded_image_path:
                self.logger.info(f"调用OpenAI API生成图表（带图片）")
                
                # 获取用户名（用于确定用户的上传文件夹）
                username = user.get('username', '10') if user else '10'
                
                # 构建图片路径
                # 图片实际存储在 /root/mcdp/backend/upload/{username}/{filename}
                # 确保upload目录存在
                upload_root = os.path.join(current_app.root_path, 'upload')
                os.makedirs(upload_root, exist_ok=True)
                os.makedirs(os.path.join(upload_root, username), exist_ok=True)
                
                # 检查是否是完整的URL路径
                if uploaded_image_path.startswith('/api/chat/files/'):
                    # 从URL提取文件名
                    path_parts = uploaded_image_path.split('/')
                    if len(path_parts) >= 5:
                        username_in_path = path_parts[-2]
                        filename_in_path = path_parts[-1]
                        self.logger.info(f"从URL中提取用户名和文件名: {username_in_path}, {filename_in_path}")
                        uploaded_image_path = filename_in_path
                
                image_file_path = os.path.join(current_app.root_path, 'upload', username, uploaded_image_path)
                self.logger.info(f"构建图片路径: {image_file_path}")
                
                # 检查文件是否存在
                if not os.path.exists(image_file_path):
                    # 尝试在其他可能的路径查找文件
                    alternative_paths = [
                        # 首先尝试查找原图，而不是缩略图（如果传入的是缩略图路径）
                        os.path.join(current_app.root_path, 'upload', username, uploaded_image_path.replace('thumb_', '')),
                        # 检查原始路径
                        os.path.join(current_app.root_path, 'upload', username, uploaded_image_path),
                        # 如果路径中没有thumb_前缀但实际存储的是缩略图
                        os.path.join(current_app.root_path, 'upload', username, 'thumb_' + uploaded_image_path),
                        # 检查直接在upload根目录的原图
                        os.path.join(current_app.root_path, 'upload', uploaded_image_path.replace('thumb_', '')),
                        # 检查直接在upload根目录的缩略图
                        os.path.join(current_app.root_path, 'upload', uploaded_image_path),
                        # 检查路径中原文件名和缩略图名混用的情况
                        os.path.join(current_app.root_path, 'upload', 'thumb_' + uploaded_image_path)
                    ]
                    
                    self.logger.info(f"图片路径 {image_file_path} 不存在，尝试查找替代路径...")
                    
                    # 检查所有可能的路径
                    for alt_path in alternative_paths:
                        self.logger.info(f"尝试备选路径: {alt_path}")
                        if os.path.exists(alt_path):
                            image_file_path = alt_path
                            self.logger.info(f"在备选路径找到图片: {image_file_path}")
                            break
                            
                    # 如果仍然找不到，尝试更广泛地查找
                    if not os.path.exists(image_file_path):
                        # 首先检查upload目录及其子目录
                        upload_dirs = [
                            os.path.join(current_app.root_path, 'upload', username),  # 用户目录
                            os.path.join(current_app.root_path, 'upload')             # 根上传目录
                        ]
                        
                        # 遍历所有可能的目录
                        for upload_dir in upload_dirs:
                            if os.path.exists(upload_dir) and os.path.isdir(upload_dir):
                                self.logger.info(f"在 {upload_dir} 中查找匹配的文件")
                                try:
                                    # 尝试直接查找文件
                                    files = os.listdir(upload_dir)
                                    
                                    # 先尝试完全匹配
                                    for file in files:
                                        if file == uploaded_image_path:
                                            image_file_path = os.path.join(upload_dir, file)
                                            self.logger.info(f"找到完全匹配的图片文件: {file}")
                                            break
                                            
                                    # 如果没找到，尝试不区分大小写匹配
                                    if not os.path.exists(image_file_path):
                                        for file in files:
                                            if file.lower() == uploaded_image_path.lower():
                                                image_file_path = os.path.join(upload_dir, file)
                                                self.logger.info(f"找到匹配的图片文件(不区分大小写): {file}")
                                                break
                                    
                                    # 如果仍然没找到，尝试查找包含特定UUID部分的文件
                                    if not os.path.exists(image_file_path) and len(uploaded_image_path) > 8:
                                        # 提取可能的UUID部分(假设上传的图片名称包含UUID)
                                        uuid_part = uploaded_image_path[:8]  # 取前8个字符作为UUID前缀
                                        self.logger.info(f"尝试查找包含UUID前缀 {uuid_part} 的文件")
                                        for file in files:
                                            if uuid_part in file:
                                                image_file_path = os.path.join(upload_dir, file)
                                                self.logger.info(f"找到包含UUID前缀的图片文件: {file}")
                                                break
                                    
                                    # 如果找到了匹配的文件，就不需要继续搜索其他目录
                                    if os.path.exists(image_file_path):
                                        break
                                        
                                except Exception as e:
                                    self.logger.error(f"列出目录内容时出错: {str(e)}")
                
                # 再次检查文件是否存在
                if not os.path.exists(image_file_path):
                    self.logger.error(f"上传的图片文件不存在: {image_file_path}")
                    self.logger.error(f"已尝试以下路径:")
                    self.logger.error(f"1. {os.path.join(current_app.root_path, 'upload', username, uploaded_image_path)}")
                    self.logger.error(f"2. {os.path.join(current_app.root_path, 'upload', username, uploaded_image_path.replace('thumb_', ''))}")
                    self.logger.error(f"3. {os.path.join(current_app.root_path, 'upload', username, 'thumb_' + uploaded_image_path)}")
                    self.logger.error(f"4. {os.path.join(current_app.root_path, 'upload', uploaded_image_path)}")
                    return jsonify({"error": f"上传的图片文件不存在: {uploaded_image_path}"}), 404
                
                # 读取图片并转换为base64
                try:
                    with open(image_file_path, "rb") as image_file:
                        image_data = image_file.read()
                        base64_image = base64.b64encode(image_data).decode('utf-8')
                        
                        # 获取MIME类型
                        import imghdr
                        image_type = imghdr.what(None, h=image_data) or 'jpeg'
                        mime_type = f"image/{image_type}"
                        
                        # 记录图片类型和大小信息，帮助诊断问题
                        self.logger.info(f"使用图片类型: {image_type}, 大小: {len(image_data)/1024:.2f} KB, 路径: {image_file_path}")
                        # 检查是否为缩略图路径
                        if 'thumb_' in image_file_path:
                            self.logger.warning(f"当前使用的是缩略图而非原图，这可能影响分析质量!")
                        
                        # 使用OpenAI客户端调用带图片的请求
                        response = client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {
                                    "role": "system",
                                    "content": system_prompt
                                },
                                {
                                    "role": "user",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": message
                                        },
                                        {
                                            "type": "image_url",
                                            "image_url": {
                                                "url": f"data:{mime_type};base64,{base64_image}"
                                            }
                                        }
                                    ]
                                }
                            ],
                            max_tokens=4096
                        )
                        
                        self.logger.info(f"已成功调用OpenAI API（带图片）")
                except Exception as e:
                    self.logger.error(f"处理图片时出错: {str(e)}")
                    return jsonify({"error": f"处理图片时出错: {str(e)}"}), 500
            else:
                self.logger.info(f"调用OpenAI API生成图表（无图片）")
                
                # 构建请求用户消息，添加更多指导
                detailed_message = f"""
                请为以下需求创建一个详细的云架构图：
                
                {message}
                
                请使用Mermaid图表语法，确保关系清晰。
                """
                
                # 使用OpenAI客户端调用无图片的请求
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": detailed_message
                        }
                    ],
                    max_tokens=4096
                )
                
                self.logger.info(f"已成功调用OpenAI API（无图片）")
            
            # 处理响应
            raw_content = response.choices[0].message.content
        
            # 处理Mermaid代码格式
            mermaid_code = self._parse_mermaid_code(raw_content)
        
            # 生成Terraform代码
            terraform_code = self._generate_terraform_code(message, mermaid_code)
        
            # 返回结果
            self.logger.info("图表生成成功")
            return jsonify({
                "success": True,
                "is_diagram": True,
                "mermaid_code": mermaid_code,
                "terraform_code": terraform_code,
                "original_message": message,
                "reply": "已生成拓扑图和Terraform代码"
            })
        
        except Exception as e:
            self.logger.error(f"生成图表时出错: {str(e)}")
            traceback_str = traceback.format_exc()
            self.logger.error(f"详细错误: {traceback_str}")
            return jsonify({"error": f"生成图表时出错: {str(e)}"}), 500
    
    def _parse_mermaid_code(self, content):
        """从OpenAI响应中提取Mermaid代码并做基本处理"""
        self.logger.info(f"OpenAI返回的原始内容长度: {len(content)}")
        
        # 记录完整的原始内容（用于调试）
        formatted_content = content.replace('\n', ' ')
        self.logger.info(f"OpenAI返回的完整原始内容: {formatted_content}")
        
        # 移除可能的Markdown代码块标记
        if '```mermaid' in content:
            self.logger.info("检测到```mermaid标记，正在清理")
            content = content.replace('```mermaid', '')
            content = content.replace('```', '')
        elif '```' in content:
            self.logger.info("检测到```标记，正在清理")
            content = content.replace('```', '')
        
        # 移除开头和结尾的空白字符
        content = content.strip()
        
        # 定义有效的mermaid图表类型（更完整的列表）
        valid_mermaid_types = [
            'flowchart', 'graph', 'sequenceDiagram', 'classDiagram', 
            'stateDiagram', 'entityRelationshipDiagram', 'erDiagram', 
            'gantt', 'pie', 'gitGraph', 'journey', 'mindmap', 
            'timeline', 'quadrantChart'
        ]
        
        # 检查是否以有效的mermaid类型开始
        is_valid_start = any(content.startswith(t) for t in valid_mermaid_types)
        
        if not is_valid_start:
            self.logger.warning(f"Mermaid代码可能格式不正确，不是以标准类型开始: {content[:50]}...")
            
            # 尝试检测代码的第一行是否包含图表类型
            first_line = content.split('\n')[0].strip().lower()
            type_found = False
            
            for mermaid_type in valid_mermaid_types:
                if mermaid_type.lower() in first_line:
                    self.logger.info(f"第一行包含图表类型: {first_line}")
                    type_found = True
                    break
            
            # 如果内容太简短或者没有检测到有效的图表类型，则添加默认的flowchart
            if not type_found or len(content.split('\n')) < 3:
                self.logger.warning("内容过于简单或未检测到图表类型，将生成默认架构图")
                
                # 构建一个基本的AWS架构图作为默认内容
                default_content = """
flowchart TD
    %% AWS 云架构
    subgraph AWS["AWS Cloud"]
        subgraph VPC["VPC (10.0.0.0/16)"]
            subgraph PublicSubnet1["Public Subnet AZ1 (10.0.1.0/24)"]
                EC2["EC2 Instance\\nt2.micro"]
                SG["Security Group"]
                EC2 --- SG
            end
            
            subgraph PrivateSubnet1["Private Subnet AZ1 (10.0.2.0/24)"]
                RDS[(RDS Database\\nMySQL)]
                SGDB["DB Security Group"]
                RDS --- SGDB
            end
            
            PublicSubnet1 --> PrivateSubnet1
        end
        
        IAM[/"IAM Role\\nEC2 Access"/]
        S3[(S3 Bucket\\nData Storage)]
        
        EC2 --> S3
        EC2 --> RDS
        IAM --> EC2
    end
    
    User([User]) --> EC2
"""
                content = default_content.strip()
                self.logger.info("已生成默认架构图内容")
            elif not content.startswith(('flowchart', 'graph')):
                # 如果检测到的图表类型不是flowchart或graph，但内容似乎包含架构信息
                # 则尝试修复格式，将其转换为flowchart
                content = f"flowchart TD\n{content}"
                self.logger.info("已将内容转换为flowchart格式")
        
        # 确保内容不为空
        if not content or len(content.strip()) < 10:
            self.logger.warning("Mermaid代码内容过短或为空，使用默认模板")
            content = """
flowchart TD
    A[AWS账户] --> B[区域: 北京]
    B --> C[VPC: 10.0.0.0/16]
    C --> D[公有子网: 10.0.1.0/24]
    C --> E[私有子网: 10.0.2.0/24]
    D --> F[EC2实例: t2.micro]
    F --> G[安全组]
    E --> H[数据库: RDS]
"""
        
        self.logger.info(f"处理后的Mermaid代码长度: {len(content)}")
        
        return content 

    def _generate_terraform_code(self, user_message, mermaid_code):
        """根据用户需求和Mermaid图表生成对应的Terraform代码"""
        try:
            self.logger.info("开始生成Terraform代码")
            
            # 获取API密钥，优先使用环境变量，否则使用配置
            api_key = self.openai_api_key
            if not api_key and self.config:
                api_key = getattr(self.config, 'openai_api_key', '')
            
            if not api_key:
                self.logger.error("未配置OpenAI API密钥，无法生成Terraform代码")
                return ""
            
            # 获取API Base URL和模型名称
            api_base_url = self.openai_api_base_url
            if not api_base_url and self.config:
                api_base_url = getattr(self.config, 'openai_api_base_url', 'https://api.openai.com/v1')
            
            model_name = self.openai_api_model
            if not model_name and self.config:
                model_name = getattr(self.config, 'openai_api_model', 'gpt-4o')
                
            # 构建完整的API URL
            chat_completions_url = f"{api_base_url.rstrip('/')}/chat/completions"
            self.logger.info(f"使用API URL: {chat_completions_url}")
            self.logger.info(f"使用模型: {model_name}")
            
            # 构建系统提示
            system_prompt = r"""
            You are a DevOps engineer expert in Terraform. 
            Your task is to generate Terraform code based on a user's request and a Mermaid diagram.
            
            CRITICAL REQUIREMENTS:
            1. Include all resources shown in the diagram.
            4. Ensure the code is complete and ready to execute.
            5. Include provider configuration.
            6. Use best practices and meaningful resource names.
            7. Add helpful comments to explain key sections of the code.
            8. You must ensure proper resource dependencies and complete all necessary components for the diagram to function correctly. If essential components are missing from the diagram (such as security groups, IAM roles, etc.), you must add them to ensure the infrastructure works properly.
            
            Remember: EVERY resource must have at least one output block.
            
            CLOUD PROVIDER SPECIFIC REQUIREMENTS:
            1. For non-AWS cloud providers (like Azure, GCP, Volcengine, etc.), DO NOT include Internet Gateway (IGW) resources or internet_gateway components, as these are AWS-specific concepts and not required in other cloud platforms.
            2. For non-AWS cloud providers, instances with public IP addresses can access the internet without configuring default routes. No additional routing configuration is needed for internet access when public IPs are assigned.
            
            Only return the complete Terraform code without any additional explanations or markdown formatting.
            """
            
            # 检查用户消息是否同时包含EC2和Linux关键词
            if "ec2" in user_message.lower() and "linux" in user_message.lower():
                self.logger.info("检测到EC2和Linux关键词，添加Amazon Linux AMI数据源要求")
                system_prompt += r"""
            
            SPECIAL REQUIREMENT FOR EC2 WITH LINUX:
            You MUST include this data source for Amazon Linux AMI:
            
            data "aws_ami" "amazon_linux" {
              most_recent = true
              owners      = ["amazon"]
            
              filter {
                name   = "name"
                values = ["amzn2-ami-hvm-*-x86_64-gp2"]
              }
            }
            
            For ALL EC2 instances, use this data source as the AMI:
            ami = data.aws_ami.amazon_linux.id
            """
                
            # 检查用户消息是否包含火山云相关关键词
            is_volcengine = any(keyword in user_message.lower() for keyword in ["火山云", "火山引擎", "volcengine"])
            is_volcengine_ecs = is_volcengine and "ecs" in user_message.lower()
            
            if is_volcengine:
                self.logger.info("检测到火山云/火山引擎关键词，使用火山引擎provider")
                system_prompt += r"""
            
            SPECIAL REQUIREMENT FOR VOLCENGINE:
            You MUST include BOTH of these provider configuration blocks at the beginning of your code:
            
            terraform {
              required_providers {
                volcengine = {
                  source = "volcengine/volcengine"
                  version = "0.0.167"
                }
              }
            }
            
            provider "volcengine" {
              region = "cn-beijing"
              # access_key and secret_key will be added automatically
            }
            
            NOTE: DO NOT include access_key and secret_key in your code, they will be added automatically.
            DO NOT include any AWS provider configurations - no "provider aws" block should appear in your code.
            Create infrastructure using Volcengine resources that correspond to the requirements.
            """
                
                # 如果同时包含火山云和ECS关键词，添加ECS数据源的特殊要求
                if is_volcengine_ecs:
                    self.logger.info("检测到火山云/火山引擎和ECS关键词，添加ECS数据源")
                    system_prompt += r"""
            
            SPECIAL REQUIREMENT FOR VOLCENGINE ECS INSTANCES:
            For ANY Volcengine ECS instances, use these specific settings:
            
            Then in all volcengine_ecs_instance resources, use these settings:

instance_type   = "ecs.c3il.large"
image_id        = "image-aagd56zrw2jtdro3bnrl"
system_volume_type = "ESSD_PL0"   # Recommended system volume type
            """
            
            # 构建用户消息
            user_prompt = f"""
            User request: {user_message}
            
            Mermaid diagram of the infrastructure:
            ```
            {mermaid_code}
            ```
            
            Based on this request and diagram, generate complete and executable Terraform code.
            
            IMPORTANT: You must add any missing components necessary for the infrastructure to work properly. 
            If the diagram doesn't show essential dependencies (like security groups, IAM roles, etc.), 
            you must include them in your Terraform code. Ensure all resources have proper dependencies configured.
            """
            
            # 调用OpenAI API生成Terraform代码
            # 初始化OpenAI客户端，正确使用自定义base_url
            import openai
            client = openai.OpenAI(
                api_key=api_key,
                base_url=api_base_url
            )
            
            # 使用客户端实例调用API
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )
            
            # 解析响应
            terraform_code = response.choices[0].message.content
            
            # 清理代码，移除可能的Markdown格式
            if '```terraform' in terraform_code:
                terraform_code = terraform_code.replace('```terraform', '').replace('```', '').strip()
            elif '```hcl' in terraform_code:
                terraform_code = terraform_code.replace('```hcl', '').replace('```', '').strip()
            elif '```' in terraform_code:
                terraform_code = terraform_code.replace('```', '').strip()
            
            self.logger.info(f"Terraform代码生成成功，长度: {len(terraform_code)}")
            return terraform_code
            
        except Exception as e:
            self.logger.error(f"生成Terraform代码时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return "# 生成Terraform代码时出错\n# " + str(e)
