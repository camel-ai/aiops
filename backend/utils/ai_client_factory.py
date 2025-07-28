import os
import logging
from typing import Optional, Dict, Any, List
import anthropic
import openai
from prompts.cloud_terraform_prompts import CloudTerraformPrompts

class AIClientFactory:
    """AI客户端工厂类，根据配置创建相应的AI客户端"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.provider = config.ai_model_provider
        
    def create_client(self):
        """根据配置创建相应的AI客户端"""
        if self.provider == 'openai':
            return OpenAIClient(self.config)
        elif self.provider == 'anthropic':
            return AnthropicClient(self.config)
        else:
            raise ValueError(f"不支持的AI模型提供商: {self.provider}")

class BaseAIClient:
    """AI客户端基类"""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def generate_mermaid(self, message: str, image_data: Optional[Dict[str, Any]] = None) -> str:
        """生成Mermaid图表代码"""
        raise NotImplementedError
        
    def generate_terraform(self, user_message: str, mermaid_code: str, cloud_provider: str = None) -> str:
        """生成Terraform代码"""
        raise NotImplementedError

class OpenAIClient(BaseAIClient):
    """OpenAI客户端实现"""
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.openai_api_key or os.environ.get('OPENAI_API_KEY')
        self.api_base_url = config.openai_api_base_url
        self.model = config.openai_api_model
        
        if not self.api_key:
            raise ValueError("未配置OpenAI API密钥")
            
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.api_base_url
        )
        
    def generate_mermaid(self, message: str, image_data: Optional[Dict[str, Any]] = None) -> str:
        """使用OpenAI生成Mermaid图表代码"""
        system_prompt = r"""You are an assistant to help user build diagram with Mermaid.
You only need to return the output Mermaid code block.
Do not include any description, do not include the ```.
Code (no ```):
        """
        
        if image_data:
            # 带图片的请求
            response = self.client.chat.completions.create(
                model=self.model,
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
                                    "url": f"data:{image_data['mime_type']};base64,{image_data['base64']}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096
            )
        else:
            # 无图片的请求
            detailed_message = f"""
            请严格按照以下需求创建Mermaid架构图：
            
            {message}
            
            要求：
            1. 只包含用户明确提到的服务和组件
            2. 不要自动添加用户未提及的额外服务
            3. 使用Mermaid图表语法，确保关系清晰
            4. 但是需要自动补充用户明确提到的服务和组件能正确运行和被访问到所依赖的必须的服务和组件。
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
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
            
        return response.choices[0].message.content
        
    def generate_terraform(self, user_message: str, mermaid_code: str, cloud_provider: str = None) -> str:
        """使用OpenAI生成Terraform代码"""
        # 检测云提供商（如果未明确指定）
        if not cloud_provider:
            cloud_provider = CloudTerraformPrompts.detect_cloud_from_description(user_message)
        
        # 使用云提供商特定的prompt
        system_prompt = CloudTerraformPrompts.get_cloud_specific_prompt(cloud_provider, user_message)
        
        # 使用云提供商特定的用户prompt模板
        user_prompt_template = CloudTerraformPrompts.get_user_prompt_template()
        user_prompt = user_prompt_template.format(
            user_description=user_message,
            mermaid_code=mermaid_code,
            cloud_provider=cloud_provider
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4
        )
        
        return response.choices[0].message.content
        
    def _build_terraform_system_prompt(self, user_message: str) -> str:
        """构建Terraform生成的系统提示"""
        system_prompt = r"""
        You are a DevOps engineer expert in Terraform. 
        Your task is to generate Terraform code based on a user's request and a Mermaid diagram.
        
        CRITICAL REQUIREMENTS:
        1. Include all resources shown in the diagram.
        4. Ensure the code is complete and ready to execute.
        5. Include provider configuration.
        6. Use best practices and meaningful resource names.
        7. Add helpful comments to explain key sections of the code.
        8. Automatically supplement the missing cloud components to meet all the functions described by the user. You must ensure proper resource dependencies and complete all necessary components for the diagram to function correctly. If essential components are missing from the diagram (such as security groups, IAM roles, route tables, internet gateways, etc.), you must add them to ensure the infrastructure works properly.
        
        CLOUD PROVIDER SPECIFIC REQUIREMENTS:
        1. For non-AWS cloud providers (like Azure, GCP, Volcengine, etc.), DO NOT include Internet Gateway (IGW) resources or internet_gateway components, as these are AWS-specific concepts and not required in other cloud platforms.
        2. For non-AWS cloud providers, instances with public IP addresses can access the internet without configuring default routes. No additional routing configuration is needed for internet access when public IPs are assigned.
        
        Only return the complete Terraform code without any additional explanations or markdown formatting.
        """
        
        # 检查用户消息是否同时包含EC2和Linux关键词
        if "ec2" in user_message.lower() and "linux" in user_message.lower():
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
            
            if is_volcengine_ecs:
                system_prompt += r"""
        
        SPECIAL REQUIREMENT FOR VOLCENGINE ECS INSTANCES:
        For ANY Volcengine ECS instances, use these specific settings:
        
        Then in all volcengine_ecs_instance resources, use these settings:

instance_type   = "ecs.c3il.large"
image_id        = "image-aagd56zrw2jtdro3bnrl"
system_volume_type = "ESSD_PL0"   # Recommended system volume type
        """
        
        return system_prompt

class AnthropicClient(BaseAIClient):
    """Anthropic客户端实现"""
    
    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.anthropic_api_key or os.environ.get('ANTHROPIC_API_KEY')
        self.api_base_url = config.anthropic_api_base_url
        self.model = config.anthropic_api_model
        
        if not self.api_key:
            raise ValueError("未配置Anthropic API密钥")
            
        # 如果使用自定义base_url，需要特殊处理
        if self.api_base_url != 'https://api.anthropic.com/v1':
            self.client = anthropic.Anthropic(
                api_key=self.api_key,
                base_url=self.api_base_url
            )
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
        
    def generate_mermaid(self, message: str, image_data: Optional[Dict[str, Any]] = None) -> str:
        """使用Anthropic生成Mermaid图表代码"""
        system_prompt = """You are an assistant to help user build diagram with Mermaid.
You only need to return the output Mermaid code block.
Do not include any description, do not include the ```.
Code (no ```):"""
        
        if image_data:
            # 带图片的请求
            detailed_message = f"""
            请严格按照以下需求创建Mermaid架构图：
            
            {message}
            
            要求：
            1. 只包含用户明确提到的服务和组件
            2. 不要自动添加用户未提及的额外服务
            3. 使用Mermaid图表语法，确保关系清晰
            4. 但是需要自动补充用户明确提到的服务和组件能正确运行和被访问到所依赖的必须的服务和组件。
            
            [用户上传了一张图片作为参考]
            """
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": detailed_message
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": image_data['mime_type'],
                                    "data": image_data['base64']
                                }
                            }
                        ]
                    }
                ]
            )
        else:
            # 无图片的请求
            detailed_message = f"""
            请严格按照以下需求创建Mermaid架构图：
            
            {message}
            
            要求：
            1. 只包含用户明确提到的服务和组件
            2. 不要自动添加用户未提及的额外服务
            3. 使用Mermaid图表语法，确保关系清晰
            4. 但是需要自动补充用户明确提到的服务和组件能正确运行和被访问到所依赖的必须的服务和组件。
            """
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": detailed_message
                    }
                ]
            )
            
        return response.content[0].text
        
    def generate_terraform(self, user_message: str, mermaid_code: str, cloud_provider: str = None) -> str:
        """使用Anthropic生成Terraform代码"""
        # 检测云提供商（如果未明确指定）
        if not cloud_provider:
            cloud_provider = CloudTerraformPrompts.detect_cloud_from_description(user_message)
        
        # 使用云提供商特定的prompt
        system_prompt = CloudTerraformPrompts.get_cloud_specific_prompt(cloud_provider, user_message)
        
        # 使用云提供商特定的用户prompt模板
        user_prompt_template = CloudTerraformPrompts.get_user_prompt_template()
        user_prompt = user_prompt_template.format(
            user_description=user_message,
            mermaid_code=mermaid_code,
            cloud_provider=cloud_provider
        )
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0.4,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )
        
        return response.content[0].text
        
    def _build_terraform_system_prompt(self, user_message: str) -> str:
        """构建Terraform生成的系统提示"""
        system_prompt = r"""
        You are a DevOps engineer expert in Terraform. 
        Your task is to generate Terraform code based on a user's request and a Mermaid diagram.
        
        CRITICAL REQUIREMENTS:
        1. Include all resources shown in the diagram.
        4. Ensure the code is complete and ready to execute.
        5. Include provider configuration.
        6. Use best practices and meaningful resource names.
        7. Add helpful comments to explain key sections of the code.
        8. Automatically supplement the missing cloud components to meet all the functions described by the user. You must ensure proper resource dependencies and complete all necessary components for the diagram to function correctly. If essential components are missing from the diagram (such as security groups, IAM roles, route tables, internet gateways, etc.), you must add them to ensure the infrastructure works properly.
        
        CLOUD PROVIDER SPECIFIC REQUIREMENTS:
        1. For non-AWS cloud providers (like Azure, GCP, Volcengine, etc.), DO NOT include Internet Gateway (IGW) resources or internet_gateway components, as these are AWS-specific concepts and not required in other cloud platforms.
        2. For non-AWS cloud providers, instances with public IP addresses can access the internet without configuring default routes. No additional routing configuration is needed for internet access when public IPs are assigned.
        
        Only return the complete Terraform code without any additional explanations or markdown formatting.
        """
        
        # 检查用户消息是否同时包含EC2和Linux关键词
        if "ec2" in user_message.lower() and "linux" in user_message.lower():
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
            
            if is_volcengine_ecs:
                system_prompt += r"""
        
        SPECIAL REQUIREMENT FOR VOLCENGINE ECS INSTANCES:
        For ANY Volcengine ECS instances, use these specific settings:
        
        Then in all volcengine_ecs_instance resources, use these settings:

instance_type   = "ecs.c3il.large"
image_id        = "image-aagd56zrw2jtdro3bnrl"
system_volume_type = "ESSD_PL0"   # Recommended system volume type
        """
        
        return system_prompt 