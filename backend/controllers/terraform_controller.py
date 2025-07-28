import os
import logging
import traceback
import json
import requests
import base64
import re
import uuid
import threading
import subprocess
import time
from datetime import datetime
from flask import request, jsonify, current_app, send_file, Response
from werkzeug.utils import safe_join
from models.aideployment_model import AIDeploymentModel
from utils.ai_client_factory import AIClientFactory
from utils.auth import get_current_user
from db.db import get_db
import docker
from typing import Optional
from prompts.cloud_terraform_prompts import CloudTerraformPrompts

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 定义部署目录
DEPLOYMENTS_DIR = os.path.join(current_dir, '..', 'aideployments')

# 确保部署目录存在
if not os.path.exists(DEPLOYMENTS_DIR):
    os.makedirs(DEPLOYMENTS_DIR)

# 定义部署状态
DEPLOYMENT_STATUS = {
    'PENDING': 'pending',
    'RUNNING': 'running',
    'SUCCESS': 'success',
    'FAILED': 'failed'
}

class TerraformController:
    def __init__(self, config=None):
        """初始化Terraform控制器"""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.deployments_dir = DEPLOYMENTS_DIR
        self.deployment_model = AIDeploymentModel()  # 移除config参数
        
        # 记录正在运行的部署进程，用于支持停止部署功能
        self.active_deployments = {}  # deploy_id -> {"process": process, "thread": thread}
        
        # 创建AI客户端
        if config:
            self.ai_client_factory = AIClientFactory(config)
            self.ai_client = self.ai_client_factory.create_client()
            self.logger.info(f"TerraformController使用AI模型提供商: {config.ai_model_provider}")
        else:
            # 兼容旧代码，如果没有config，使用环境变量
            self.openai_api_key = os.environ.get('OPENAI_API_KEY', '')
            self.openai_api_base_url = os.environ.get('OPENAI_API_BASE_URL', 'https://api.openai.com/v1')
            self.openai_api_model = os.environ.get('OPENAI_API_MODEL', 'gpt-4o')
            self.ai_client = None
        
        # Initialize MCP server configuration
        self.enable_mcp = os.environ.get('ENABLE_TERRAFORM_MCP', 'false').lower() == 'true'
        self.mcp_server_url = os.environ.get('TERRAFORM_MCP_SERVER_URL', 'http://localhost:8080')
        self.mcp_server_version = os.environ.get('TERRAFORM_MCP_SERVER_VERSION', '0.1.0')
        
        # MCP Docker container configuration
        self.mcp_container_name = "terraform-mcp-server"
        self.mcp_server_path = "/bin/terraform-mcp-server"  # 默认路径
        
        # Initialize Docker client for MCP server if enabled
        if self.enable_mcp:
            try:
                self.docker_client = docker.from_env()
                self._ensure_mcp_server()
                self.logger.info("MCP server with Docker client initialized successfully")
            except Exception as e:
                self.logger.warning(f"MCP功能不可用 - Docker client初始化失败: {str(e)}")
                self.logger.info("MCP功能已禁用，将使用传统Terraform生成模式")
                self.enable_mcp = False
        else:
            self.logger.info("MCP功能已禁用，使用传统Terraform生成模式")

    def _ensure_mcp_server(self):
        """Ensures the Terraform MCP server is running"""
        try:
            self.logger.info("开始检查并启动Terraform MCP server")
            self.logger.info(f"MCP server配置:")
            self.logger.info(f"- 启用MCP: {self.enable_mcp}")
            self.logger.info(f"- MCP server URL: {self.mcp_server_url}")
            self.logger.info(f"- MCP server版本: {self.mcp_server_version}")
            
            if not self.enable_mcp:
                self.logger.info("MCP server已禁用，跳过启动")
                return
            
            # Pull the latest MCP server image
            image_name = f"hashicorp/terraform-mcp-server:{self.mcp_server_version}"
            self.logger.info(f"正在拉取MCP server镜像: {image_name}")
            
            try:
                image = self.docker_client.images.pull(image_name)
                self.logger.info(f"成功拉取MCP server镜像: {image.id}")
            except Exception as pull_error:
                self.logger.error(f"拉取MCP server镜像失败: {str(pull_error)}")
                raise
            
            # Check if container is already running
            self.logger.info("检查是否已有运行中的MCP server容器")
            containers = self.docker_client.containers.list(
                filters={"name": "terraform-mcp-server"}
            )
            
            if containers:
                container = containers[0]
                self.logger.info(f"发现已运行的MCP server容器: {container.id}")
                self.logger.info(f"容器状态: {container.status}")
                self.logger.info(f"容器端口: {container.ports}")
                
                # 检查容器是否健康
                if container.status == 'running':
                    self.logger.info("MCP server容器正在正常运行")
                    
                    # 使用stdio方式进行健康检查（而不是HTTP）
                    health_ok = self._test_mcp_server_connection()
                    if health_ok:
                        self.logger.info("MCP server健康检查通过")
                    else:
                        self.logger.warning("MCP server健康检查失败，但容器仍在运行")
                else:
                    self.logger.warning(f"MCP server容器状态异常: {container.status}，将重启容器")
                    container.stop()
                    container.remove()
                    self._start_new_mcp_container(image_name)
            else:
                self.logger.info("未发现运行中的MCP server容器，将启动新容器")
                self._start_new_mcp_container(image_name)
                
        except Exception as e:
            self.logger.error(f"启动Terraform MCP server失败: {str(e)}")
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            self.enable_mcp = False
            
    def _start_new_mcp_container(self, image_name):
        """启动新的MCP server容器"""
        try:
            self.logger.info(f"正在启动新的MCP server容器: {image_name}")
            
            # 先清理可能存在的同名容器
            try:
                existing_containers = self.docker_client.containers.list(
                    all=True, filters={"name": "terraform-mcp-server"}
                )
                for container in existing_containers:
                    self.logger.info(f"清理现有容器: {container.id}")
                    try:
                        container.stop(timeout=5)
                    except:
                        pass
                    try:
                        container.remove(force=True)
                    except:
                        pass
            except Exception as cleanup_error:
                self.logger.warning(f"清理现有容器时出错: {str(cleanup_error)}")
            
            # 启动新容器
            self.logger.info("启动容器参数:")
            self.logger.info(f"- 镜像: {image_name}")
            self.logger.info(f"- 端口映射: 8080:8080")
            self.logger.info(f"- 环境变量: LOG_LEVEL=DEBUG")
            
            # 首先检查镜像是否有问题，尝试运行一个简单的命令来测试
            try:
                self.logger.info("测试镜像是否能正常运行...")
                test_container = self.docker_client.containers.run(
                    image_name,
                    command="--help",  # 运行help命令看看镜像是否正常
                    remove=True,
                    detach=False
                )
                self.logger.info("镜像测试运行成功")
            except Exception as test_error:
                self.logger.error(f"镜像测试运行失败: {str(test_error)}")
                # 继续尝试正常启动
            
            # MCP server 需要运行在 stdio 模式，但容器本身要运行一个保持活跃的进程
            container = self.docker_client.containers.run(
                image_name,
                name="terraform-mcp-server",
                command=["sh", "-c", "while true; do sleep 3600; done"],  # 保持容器运行
                detach=True,
                stdin_open=True,  # 保持 stdin 开放
                tty=True,         # 分配伪终端
                environment={
                    'LOG_LEVEL': 'DEBUG'  # 启用详细日志
                }
                # 注意：MCP server通过stdio通信，每次查询时动态启动terraform-mcp-server stdio
            )
            
            self.logger.info(f"容器创建成功: {container.id}")
            
            # 等待一小段时间让容器有时间启动
            import time
            self.logger.info("等待容器启动...")
            time.sleep(2)
            
            # 获取容器启动日志（在状态检查之前）
            try:
                logs = container.logs().decode('utf-8')
                if logs:
                    self.logger.info(f"容器启动日志: {logs}")
                else:
                    self.logger.info("容器日志为空")
            except Exception as log_error:
                self.logger.warning(f"获取容器日志失败: {str(log_error)}")
            
            # 检查容器状态 - 使用简单的方式
            try:
                # 直接查询所有容器，避免使用可能有问题的reload
                containers = self.docker_client.containers.list(all=True)
                mcp_container = None
                
                for c in containers:
                    if c.name == "terraform-mcp-server":
                        mcp_container = c
                        break
                
                if mcp_container is None:
                    self.logger.error("找不到MCP server容器")
                    return
                
                self.logger.info(f"容器当前状态: {mcp_container.status}")
                self.logger.info(f"容器端口映射: {mcp_container.ports}")
                
                if mcp_container.status == 'running':
                    self.logger.info("MCP server容器正在运行")
                    # 尝试连接测试
                    self._test_mcp_server_connection()
                elif mcp_container.status == 'exited':
                    self.logger.error("容器已退出")
                    
                    # 获取详细的容器信息
                    try:
                        container_info = self.docker_client.api.inspect_container(mcp_container.id)
                        exit_code = container_info.get('State', {}).get('ExitCode', 'unknown')
                        error_msg = container_info.get('State', {}).get('Error', 'no error message')
                        self.logger.error(f"容器退出代码: {exit_code}")
                        self.logger.error(f"容器错误信息: {error_msg}")
                        
                        # 获取更详细的日志
                        logs = mcp_container.logs().decode('utf-8')
                        if logs:
                            self.logger.error(f"容器完整日志: {logs}")
                    except Exception as info_error:
                        self.logger.error(f"获取容器详细信息失败: {str(info_error)}")
                else:
                    self.logger.warning(f"容器状态异常: {mcp_container.status}")
                    
            except Exception as status_error:
                self.logger.error(f"检查容器状态时出错: {str(status_error)}")
                self.logger.error(f"状态检查错误详情: {traceback.format_exc()}")
                
        except Exception as e:
            self.logger.error(f"启动MCP server容器时出错: {str(e)}")
            self.logger.error(f"启动错误详情: {traceback.format_exc()}")
            raise
            
    def _test_mcp_server_connection(self):
        """测试MCP server连接（通过stdio）"""
        try:
            self.logger.info("正在测试MCP server连接（stdio方式）")
            
            # 找到MCP server容器
            containers = self.docker_client.containers.list()
            mcp_container = None
            for container in containers:
                if container.name == "terraform-mcp-server":
                    mcp_container = container
                    break
            
            if not mcp_container:
                self.logger.error("找不到MCP server容器")
                return False
            
            # 发送一个简单的tools/list请求来测试MCP server是否正确运行在stdio模式
            import json
            import subprocess
            
            # 使用标准的tools/list请求
            test_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            
            for i in range(3):  # 最多重试3次
                try:
                    # 修复：使用正确的MCP server stdio模式测试
                    mcp_command = [
                        "docker", "exec", "-i", self.mcp_container_name,
                        self.mcp_server_path, "stdio"
                    ]
                    
                    # 添加换行符，MCP协议需要
                    request_data = json.dumps(test_request) + "\n"
                    
                    exec_result = subprocess.run(
                        mcp_command,
                        input=request_data,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    self.logger.info(f"MCP server连接测试执行结果退出码: {exec_result.returncode}")
                    
                    if exec_result.returncode == 0:
                        output = exec_result.stdout if exec_result.stdout else ""
                        self.logger.info(f"MCP server连接测试响应: {output[:300]}{'...' if len(output) > 300 else ''}")
                        
                        # 检查响应是否包含有效的JSON-RPC格式
                        if '"jsonrpc"' in output and '"result"' in output:
                            self.logger.info("✅ MCP server连接测试成功 - 返回有效JSON-RPC响应")
                            return True
                        elif "terraform-mcp-server [command]" in output:
                            self.logger.error("❌ MCP server返回帮助信息而非JSON-RPC响应，可能配置错误")
                            return False
                        else:
                            self.logger.warning(f"⚠️ MCP server响应格式异常，重试 {i+1}/3")
                    else:
                        self.logger.warning(f"❌ MCP server连接测试失败，退出码: {exec_result.returncode}，重试 {i+1}/3")
                        if exec_result.stderr:
                            self.logger.warning(f"错误输出: {exec_result.stderr[:200]}")
                            
                except Exception as test_error:
                    self.logger.warning(f"MCP server连接测试出错，重试 {i+1}/3: {str(test_error)}")
                    
                if i < 2:  # 最后一次不等待
                    import time
                    time.sleep(2)
            
            self.logger.error("MCP server连接测试失败，已达到最大重试次数")
            return False
            
        except Exception as e:
            self.logger.error(f"MCP server连接测试出错: {str(e)}")
            return False

    def _diagnose_mcp_server(self):
        """诊断MCP server支持的工具和providers"""
        try:
            self.logger.info("🔍 开始诊断MCP server支持情况")
            
            # 先检查容器内的文件和进程
            self._check_mcp_container_status()
            
            # 修复：MCP server必须运行在stdio模式下
            mcp_command = [
                "docker", "exec", "-i", self.mcp_container_name,
                self.mcp_server_path, "stdio"  # 明确指定stdio模式
            ]
            
            # 查询支持的工具列表
            tools_request = {
                "jsonrpc": "2.0",
                "id": 99,
                "method": "tools/list"
            }
            
            # 添加换行符，MCP协议需要
            request_data = json.dumps(tools_request) + "\n"
            
            result = subprocess.run(
                mcp_command,
                input=request_data,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.logger.info(f"📋 MCP server工具列表响应: {result.stdout}")
                
                # 尝试一个简单的AWS查询作为基准测试
                aws_test = {
                    "jsonrpc": "2.0",
                    "id": 98,
                    "method": "tools/call",
                    "params": {
                        "name": "resolveProviderDocID",
                        "arguments": {
                            "providerName": "aws",
                            "providerNamespace": "hashicorp",
                            "serviceSlug": "vpc",
                            "providerDataType": "resources",
                            "providerVersion": "latest"
                        }
                    }
                }
                
                # AWS测试查询也要使用相同的命令，添加换行符
                aws_request_data = json.dumps(aws_test) + "\n"
                
                aws_result = subprocess.run(
                    mcp_command,  # 使用相同的修复后命令
                    input=aws_request_data,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if aws_result.returncode == 0:
                    self.logger.info(f"✅ AWS测试查询成功: {aws_result.stdout[:300]}...")
                else:
                    self.logger.warning(f"❌ AWS测试查询失败: {aws_result.stderr}")
                    
            else:
                self.logger.error(f"❌ MCP server工具列表查询失败: {result.stderr}")
                
        except Exception as e:
            self.logger.error(f"MCP server诊断失败: {str(e)}")
            
    def _check_mcp_container_status(self):
        """检查MCP容器的详细状态"""
        try:
            self.logger.info("🔍 检查MCP容器内部状态")
            
            # 1. 检查terraform-mcp-server文件是否存在
            check_file_cmd = ["docker", "exec", self.mcp_container_name, "ls", "-la", self.mcp_server_path]
            result = subprocess.run(check_file_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.logger.info(f"✅ MCP server文件存在: {result.stdout.strip()}")
            else:
                self.logger.error(f"❌ MCP server文件不存在: {result.stderr}")
                return
            
            # 2. 检查文件是否可执行
            check_exec_cmd = ["docker", "exec", self.mcp_container_name, "file", self.mcp_server_path]
            result = subprocess.run(check_exec_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.logger.info(f"📋 文件类型: {result.stdout.strip()}")
            
            # 3. 尝试执行help命令
            help_cmd = ["docker", "exec", self.mcp_container_name, self.mcp_server_path, "--help"]
            result = subprocess.run(help_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.logger.info(f"✅ Help命令成功: {result.stdout[:200]}...")
            else:
                self.logger.error(f"❌ Help命令失败: {result.stderr}")
            
            # 4. 检查容器进程
            ps_cmd = ["docker", "exec", self.mcp_container_name, "ps", "aux"]
            result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                self.logger.info(f"📋 容器进程: {result.stdout}")
            
            # 5. 测试简单的JSON-RPC响应
            self._test_simple_jsonrpc()
            
        except Exception as e:
            self.logger.error(f"容器状态检查失败: {str(e)}")
    
    def _test_simple_jsonrpc(self):
        """测试简单的JSON-RPC通信"""
        try:
            self.logger.info("🔍 测试简单JSON-RPC通信")
            
            # 使用标准的MCP初始化请求
            simple_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "capabilities": {},
                    "clientInfo": {
                        "name": "mcdp-terraform-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            mcp_command = [
                "docker", "exec", "-i", self.mcp_container_name,
                self.mcp_server_path, "stdio"
            ]
            
            # 添加换行符，某些JSON-RPC实现需要
            request_data = json.dumps(simple_request) + "\n"
            
            result = subprocess.run(
                mcp_command,
                input=request_data,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            self.logger.info(f"简单JSON-RPC测试退出码: {result.returncode}")
            self.logger.info(f"简单JSON-RPC测试stdout: '{result.stdout}'")
            self.logger.info(f"简单JSON-RPC测试stderr: '{result.stderr}'")
            
            if result.stdout.strip():
                self.logger.info("✅ 有stdout输出，可能表示通信正常")
            else:
                self.logger.warning("⚠️ 没有stdout输出")
                
            if result.stderr.strip():
                self.logger.info(f"📋 stderr内容: {result.stderr}")
            
        except Exception as e:
            self.logger.error(f"简单JSON-RPC测试失败: {str(e)}")

    def _generate_with_mcp(self, user_description, mermaid_code):
        """使用MCP server查询模块信息来辅助代码生成"""
        try:
            self.logger.info("开始使用MCP server查询模块信息")
            
            # 先进行诊断
            self._diagnose_mcp_server()
            
            # 智能检测云平台
            detected_cloud = CloudTerraformPrompts.detect_cloud_from_description(user_description)
            self.logger.info(f"从用户描述中智能检测到云平台: {detected_cloud}")
            
            # 云平台映射到MCP支持的provider名称
            cloud_to_provider_mapping = {
                "AWS": "aws",
                "AWS(CHINA)": "aws", 
                "AZURE": "azurerm",
                "AZURE(CHINA)": "azurerm",
                "阿里云": "alicloud",
                "华为云": "huaweicloud", 
                "腾讯云": "tencentcloud",
                "百度云": "baiducloud",
                "火山云": "volcengine"
            }
            
            mcp_provider = cloud_to_provider_mapping.get(detected_cloud, "aws")
            self.logger.info(f"映射到MCP provider: {mcp_provider}")
            
            # 智能解析用户需求中的资源类型
            resource_types = self._extract_resource_types_from_description(user_description, mcp_provider)
            self.logger.info(f"识别到需要查询的资源类型: {resource_types}")
            
            # 如果没有识别到任何资源，使用默认资源
            if not resource_types:
                self.logger.warning("未识别到具体资源类型，使用默认VPC资源")
                resource_types = ["vpc"]
            
            # 分别查询每个资源类型的文档
            all_docs = []
            for resource_type in resource_types:
                self.logger.info(f"开始查询 {mcp_provider}_{resource_type} 的文档")
                
                try:
                    service_slug = f"{mcp_provider}_{resource_type}"
                    docs = self._query_mcp_resource_docs(mcp_provider, service_slug, resource_type)
                    
                    if docs:
                        all_docs.append({
                            "resource_type": resource_type,
                            "service_slug": service_slug,
                            "docs": docs
                        })
                        self.logger.info(f"成功获取 {service_slug} 的文档，长度: {len(docs)} 字符")
                    else:
                        self.logger.warning(f"未获取到 {service_slug} 的文档")
                        
                except Exception as resource_error:
                    self.logger.error(f"查询 {service_slug} 文档时出错: {str(resource_error)}")
                    continue
            
            # 合并所有文档
            if all_docs:
                combined_docs = self._combine_mcp_docs(all_docs, mcp_provider, user_description)
                self.logger.info(f"成功合并所有文档，总长度: {len(combined_docs)} 字符")
                return combined_docs
            else:
                self.logger.warning("未获取到任何有效的MCP文档")
                return None
                
        except Exception as e:
            self.logger.error(f"MCP server查询失败: {str(e)}")
            return None

    def _extract_resource_types_from_description(self, user_description, provider):
        """从用户描述中提取需要查询的资源类型"""
        resource_types = []
        desc_lower = user_description.lower()
        
        # 基于云平台的资源类型映射
        if provider == "aws":
            resource_mapping = {
                "vpc": ["vpc", "虚拟网络", "私有云"],
                "instance": ["ec2", "实例", "服务器", "虚拟机", "ecs"],
                "subnet": ["subnet", "子网"],
                "security_group": ["安全组", "security group", "sg"],
                "db_instance": ["rds", "数据库", "db", "mysql", "postgres"],
                "s3_bucket": ["s3", "存储桶", "bucket", "存储"],
                "lb": ["elb", "alb", "nlb", "负载均衡", "load balancer"],
                "route_table": ["路由表", "route table", "路由"],
                "internet_gateway": ["网关", "gateway", "igw"]
            }
        elif provider == "huaweicloud":
            resource_mapping = {
                "vpc": ["vpc", "虚拟网络", "私有云"],
                "compute_instance": ["ecs", "实例", "服务器", "虚拟机"],
                "vpc_subnet": ["subnet", "子网"],
                "vpc_security_group": ["安全组", "security group", "sg"],
                "rds_instance": ["rds", "数据库", "db", "mysql", "postgres"],
                "obs_bucket": ["obs", "存储桶", "bucket", "存储"],
                "elb_loadbalancer": ["elb", "负载均衡", "load balancer"]
            }
        elif provider == "alicloud":
            resource_mapping = {
                "vpc": ["vpc", "虚拟网络", "私有云"],
                "instance": ["ecs", "实例", "服务器", "虚拟机"],
                "vswitch": ["vswitch", "交换机", "subnet", "子网"],
                "security_group": ["安全组", "security group", "sg"],
                "db_instance": ["rds", "数据库", "db", "mysql", "postgres"],
                "oss_bucket": ["oss", "存储桶", "bucket", "存储"],
                "slb": ["slb", "负载均衡", "load balancer"]
            }
        elif provider == "tencentcloud":
            resource_mapping = {
                "vpc": ["vpc", "虚拟网络", "私有云"],
                "instance": ["cvm", "实例", "服务器", "虚拟机", "ecs"],
                "subnet": ["subnet", "子网"],
                "security_group": ["安全组", "security group", "sg"],
                "mysql_instance": ["mysql", "数据库", "db"],
                "cos_bucket": ["cos", "存储桶", "bucket", "存储"],
                "clb_instance": ["clb", "负载均衡", "load balancer"]
            }
        elif provider == "volcengine":
            resource_mapping = {
                "vpc": ["vpc", "虚拟网络", "私有云"],
                "ecs_instance": ["ecs", "实例", "服务器", "虚拟机"],
                "subnet": ["subnet", "子网"],
                "security_group": ["安全组", "security group", "sg"],
                "rds_mysql_instance": ["rds", "mysql", "数据库", "db"],
                "tos_bucket": ["tos", "存储桶", "bucket", "存储"]
            }
        elif provider == "azurerm":
            resource_mapping = {
                "virtual_network": ["vnet", "虚拟网络", "vpc"],
                "virtual_machine": ["vm", "实例", "服务器", "虚拟机", "ecs"],
                "subnet": ["subnet", "子网"],
                "network_security_group": ["nsg", "安全组", "security group"],
                "sql_database": ["sql", "数据库", "db", "mysql"],
                "storage_account": ["storage", "存储"],
                "lb": ["负载均衡", "load balancer"]
            }
        else:
            # 默认AWS映射
            resource_mapping = {
                "vpc": ["vpc", "虚拟网络"],
                "instance": ["ec2", "实例", "ecs"],
                "subnet": ["subnet", "子网"]
            }
        
        # 检测用户描述中提到的资源类型
        mentioned_resources = []
        for resource_type, keywords in resource_mapping.items():
            for keyword in keywords:
                if keyword in desc_lower:
                    if resource_type not in mentioned_resources:
                        mentioned_resources.append(resource_type)
                    break
        
        # 如果用户提到了特定资源，根据最佳实践自动添加依赖资源
        if mentioned_resources:
            resource_types = list(mentioned_resources)
            
            # 自动添加依赖资源的逻辑
            if any(r in ["instance", "compute_instance", "virtual_machine", "ecs_instance"] for r in mentioned_resources):
                # 如果提到实例，自动添加VPC和子网
                vpc_resource = "vpc" if provider in ["aws", "alicloud", "huaweicloud", "tencentcloud", "volcengine"] else "virtual_network"
                
                # 华为云使用vpc_subnet，其他云平台的子网命名
                if provider == "huaweicloud":
                    subnet_resource = "vpc_subnet"
                elif provider == "alicloud":
                    subnet_resource = "vswitch"
                else:
                    subnet_resource = "subnet"
                
                if vpc_resource not in resource_types:
                    resource_types.insert(0, vpc_resource)  # VPC放在最前面
                if subnet_resource not in resource_types:
                    resource_types.insert(-1, subnet_resource)  # 子网放在实例前面
                    
                # 添加安全组 - 华为云使用vpc_security_group
                if provider == "huaweicloud":
                    sg_resource = "vpc_security_group"
                elif provider == "azurerm":
                    sg_resource = "network_security_group"
                else:
                    sg_resource = "security_group"
                    
                if sg_resource not in resource_types:
                    resource_types.append(sg_resource)
            
            self.logger.info(f"用户提到资源: {mentioned_resources}, 添加依赖后: {resource_types}")
        else:
            # 如果没有明确提到资源，使用VPC作为默认
            vpc_resource = "vpc" if provider != "azurerm" else "virtual_network"
            resource_types = [vpc_resource]
            self.logger.info(f"未识别到具体资源，使用默认: {resource_types}")
        
        return resource_types

    def _query_mcp_resource_docs(self, provider, service_slug, resource_type):
        """查询指定资源的MCP文档 - 使用混合查询策略"""
        try:
            self.logger.info(f"开始查询 {service_slug} 的文档 (混合策略)")
            
            # 策略1：优先使用模块查询
            module_docs = self._query_mcp_via_modules(provider, resource_type)
            if module_docs:
                self.logger.info(f"✅ 通过模块查询成功获取 {resource_type} 文档")
                return module_docs
            
            # 策略2：fallback到provider查询，尝试不同的namespace
            provider_docs = self._query_mcp_via_providers(provider, service_slug, resource_type)
            if provider_docs:
                self.logger.info(f"✅ 通过provider查询成功获取 {resource_type} 文档")
                return provider_docs
            
            # 策略3：尝试通用模块搜索
            generic_docs = self._query_mcp_generic_modules(provider, resource_type)
            if generic_docs:
                self.logger.info(f"✅ 通过通用模块查询成功获取 {resource_type} 文档")
                return generic_docs
            
            self.logger.warning(f"❌ 所有查询策略都失败，未获取到 {resource_type} 文档")
            return None
            
        except Exception as e:
            self.logger.error(f"查询 {service_slug} 文档时出错: {str(e)}")
            return None

    def _query_mcp_via_modules(self, provider, resource_type):
        """策略1：通过模块查询获取文档"""
        try:
            # 构建模块搜索关键词
            module_queries = self._build_module_search_queries(provider, resource_type)
            
            for query in module_queries:
                self.logger.info(f"🔍 模块搜索: '{query}'")
                
                # 搜索模块
                modules_response = self._search_modules(query)
                if not modules_response:
                    continue
                
                # 解析模块列表，找到最相关的模块
                module_id = self._parse_module_search_results(modules_response, provider, resource_type)
                if not module_id:
                    continue
                
                # 获取模块详情
                module_details = self._get_module_details(module_id)
                if module_details:
                    return module_details
            
            return None
            
        except Exception as e:
            self.logger.error(f"模块查询失败: {str(e)}")
            return None

    def _build_module_search_queries(self, provider, resource_type):
        """构建模块搜索关键词"""
        queries = []
        
        # 云平台特定的搜索词
        if provider == "huaweicloud":
            cloud_terms = ["huawei", "huaweicloud", "华为云"]
        elif provider == "alicloud":
            cloud_terms = ["alicloud", "aliyun", "阿里云"]
        elif provider == "tencentcloud":
            cloud_terms = ["tencent", "tencentcloud", "腾讯云"]
        elif provider == "volcengine":
            cloud_terms = ["volcengine", "bytedance", "火山云"]
        elif provider == "baiducloud":
            cloud_terms = ["baidu", "baiducloud", "百度云"]
        else:
            cloud_terms = [provider]
        
        # 资源类型映射到通用术语
        resource_mapping = {
            "vpc": ["vpc", "network", "virtual-network"],
            "compute_instance": ["ecs", "vm", "instance", "server", "compute"],
            "vpc_subnet": ["subnet", "subnetwork"],
            "subnet": ["subnet", "subnetwork"],
            "vpc_security_group": ["security-group", "sg", "firewall"],
            "security_group": ["security-group", "sg", "firewall"],
            "rds_instance": ["rds", "database", "db"],
            "db_instance": ["rds", "database", "db"],
            "obs_bucket": ["storage", "bucket", "object-storage"],
            "s3_bucket": ["storage", "bucket", "s3"],
            "elb_loadbalancer": ["lb", "load-balancer", "elb"],
            "lb": ["lb", "load-balancer"]
        }
        
        resource_terms = resource_mapping.get(resource_type, [resource_type])
        
        # 组合搜索词
        for cloud_term in cloud_terms:
            for resource_term in resource_terms:
                queries.extend([
                    f"{cloud_term} {resource_term}",
                    f"{cloud_term}-{resource_term}",
                    f"{resource_term} {cloud_term}",
                    resource_term  # 通用搜索
                ])
        
        # 去重并限制数量
        unique_queries = list(dict.fromkeys(queries))[:8]  # 最多8个查询
        self.logger.info(f"构建的模块搜索词: {unique_queries}")
        return unique_queries

    def _search_modules(self, query):
        """执行模块搜索"""
        try:
            # 修复：MCP server必须运行在stdio模式下
            mcp_command = [
                "docker", "exec", "-i", self.mcp_container_name,
                self.mcp_server_path, "stdio"  # 明确指定stdio模式
            ]
            
            search_request = {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "searchModules",
                    "arguments": {
                        "moduleQuery": query,
                        "currentOffset": 0
                    }
                }
            }
            
            # 添加换行符，MCP协议需要
            request_data = json.dumps(search_request) + "\n"
            
            result = subprocess.run(
                mcp_command,
                input=request_data,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # 添加详细的响应日志
                response_preview = result.stdout[:300] + "..." if len(result.stdout) > 300 else result.stdout
                self.logger.info(f"📋 模块搜索'{query}'响应预览: {response_preview}")
                return result.stdout
            else:
                self.logger.warning(f"❌ 模块搜索'{query}'失败: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"执行模块搜索时出错: {str(e)}")
            return None

    def _parse_module_search_results(self, response, provider, resource_type):
        """解析模块搜索结果，找到最相关的模块ID"""
        try:
            self.logger.info(f"🔍 解析模块搜索结果，寻找 {provider} {resource_type}")
            
            lines = response.strip().split('\n')
            best_module_id = None
            best_score = 0
            found_modules = []
            
            for line in lines:
                if line.startswith('{"jsonrpc"'):
                    try:
                        parsed_response = json.loads(line)
                        if "result" in parsed_response and "content" in parsed_response["result"]:
                            content = parsed_response["result"]["content"]
                            if isinstance(content, list):
                                for item in content:
                                    if isinstance(item, dict) and "text" in item:
                                        # 解析模块信息
                                        module_info = self._extract_module_info(item["text"])
                                        if module_info:
                                            score = self._score_module_relevance(module_info, provider, resource_type)
                                            found_modules.append({
                                                "info": module_info,
                                                "score": score
                                            })
                                            if score > best_score:
                                                best_score = score
                                                best_module_id = module_info.get("id")
                                                self.logger.info(f"🎯 发现候选模块: {best_module_id} (评分: {score})")
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"JSON解析失败: {str(e)}")
                        continue
                elif line.strip():  # 非空行但不是JSON
                    # 可能是普通文本响应，尝试直接解析
                    module_info = self._extract_module_info(line)
                    if module_info:
                        score = self._score_module_relevance(module_info, provider, resource_type)
                        found_modules.append({
                            "info": module_info,
                            "score": score
                        })
                        if score > best_score:
                            best_score = score
                            best_module_id = module_info.get("id")
                            self.logger.info(f"🎯 发现候选模块(文本): {best_module_id} (评分: {score})")
            
            # 输出调试信息
            if found_modules:
                self.logger.info(f"✅ 找到 {len(found_modules)} 个候选模块")
                for i, module in enumerate(sorted(found_modules, key=lambda x: x["score"], reverse=True)[:3]):
                    self.logger.info(f"  {i+1}. {module['info'].get('id', 'N/A')} (评分: {module['score']})")
            else:
                self.logger.warning(f"❌ 未找到任何匹配的模块")
                # 输出响应内容用于调试
                response_preview = response[:500] + "..." if len(response) > 500 else response
                self.logger.info(f"📋 原始响应预览: {response_preview}")
            
            if best_module_id and best_score > 30:  # 设置最低分数阈值
                self.logger.info(f"🏆 选择最佳模块: {best_module_id} (评分: {best_score})")
                return best_module_id
            else:
                self.logger.info(f"⚠️ 未找到足够相关的模块 (最高分: {best_score})")
                return None
            
        except Exception as e:
            self.logger.error(f"解析模块搜索结果时出错: {str(e)}")
            return None

    def _extract_module_info(self, text_content):
        """从文本中提取模块信息"""
        try:
            # 解析模块列表文本格式
            import re
            
            # 查找模块ID和相关信息
            patterns = [
                r'moduleID[:\s]+([^\s\n]+)',
                r'id[:\s]+["\']([^"\']+)["\']',
                r'name[:\s]+["\']([^"\']+)["\']'
            ]
            
            module_info = {}
            for pattern in patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    if "id" not in module_info:
                        module_info["id"] = match.group(1)
                    if "name" not in module_info:
                        module_info["name"] = match.group(1)
            
            # 提取描述信息
            desc_match = re.search(r'description[:\s]+["\']([^"\']+)["\']', text_content, re.IGNORECASE)
            if desc_match:
                module_info["description"] = desc_match.group(1)
            
            # 提取下载量和验证状态
            download_match = re.search(r'downloads?[:\s]+(\d+)', text_content, re.IGNORECASE)
            if download_match:
                module_info["downloads"] = int(download_match.group(1))
            
            verified_match = re.search(r'verified[:\s]+(true|false)', text_content, re.IGNORECASE)
            if verified_match:
                module_info["verified"] = verified_match.group(1).lower() == "true"
            
            return module_info if "id" in module_info else None
            
        except Exception as e:
            self.logger.error(f"提取模块信息时出错: {str(e)}")
            return None

    def _score_module_relevance(self, module_info, provider, resource_type):
        """给模块相关性打分"""
        score = 0
        
        text_to_check = " ".join([
            module_info.get("id", ""),
            module_info.get("name", ""),
            module_info.get("description", "")
        ]).lower()
        
        # 云平台匹配
        provider_keywords = {
            "huaweicloud": ["huawei", "huaweicloud", "华为"],
            "alicloud": ["ali", "aliyun", "alicloud", "阿里"],
            "tencentcloud": ["tencent", "tencentcloud", "腾讯"],
            "volcengine": ["volcengine", "bytedance", "火山"],
            "baiducloud": ["baidu", "baiducloud", "百度"],
            "aws": ["aws", "amazon"],
            "azurerm": ["azure", "microsoft"]
        }
        
        if provider in provider_keywords:
            for keyword in provider_keywords[provider]:
                if keyword in text_to_check:
                    score += 50
                    break
        
        # 资源类型匹配
        resource_keywords = {
            "vpc": ["vpc", "network", "virtual"],
            "compute_instance": ["ecs", "compute", "instance", "vm", "server"],
            "subnet": ["subnet", "subnetwork"],
            "security_group": ["security", "firewall", "sg"],
            "rds_instance": ["rds", "database", "db"],
            "obs_bucket": ["storage", "bucket", "object"],
            "elb_loadbalancer": ["lb", "balancer", "elb"]
        }
        
        if resource_type in resource_keywords:
            for keyword in resource_keywords[resource_type]:
                if keyword in text_to_check:
                    score += 30
        
        # 验证状态加分
        if module_info.get("verified", False):
            score += 20
        
        # 下载量加分
        downloads = module_info.get("downloads", 0)
        if downloads > 1000:
            score += 10
        elif downloads > 100:
            score += 5
        
        return score

    def _get_module_details(self, module_id):
        """获取模块详细信息"""
        try:
            # 修复：MCP server必须运行在stdio模式下
            mcp_command = [
                "docker", "exec", "-i", self.mcp_container_name,
                self.mcp_server_path, "stdio"  # 明确指定stdio模式
            ]
            
            detail_request = {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "moduleDetails",
                    "arguments": {
                        "moduleID": module_id
                    }
                }
            }
            
            # 添加换行符，MCP协议需要
            request_data = json.dumps(detail_request) + "\n"
            
            result = subprocess.run(
                mcp_command,
                input=request_data,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # 解析模块详情响应
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('{"jsonrpc"'):
                        try:
                            parsed_response = json.loads(line)
                            if "result" in parsed_response and "content" in parsed_response["result"]:
                                content = parsed_response["result"]["content"]
                                if isinstance(content, list) and len(content) > 0:
                                    for item in content:
                                        if isinstance(item, dict) and "text" in item:
                                            self.logger.info(f"成功获取模块详情，长度: {len(item['text'])} 字符")
                                            return item["text"]
                        except json.JSONDecodeError:
                            continue
                
                self.logger.warning("模块详情响应中未找到有效内容")
                return None
            else:
                self.logger.error(f"获取模块详情失败: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"获取模块详情时出错: {str(e)}")
            return None

    def _query_mcp_via_providers(self, provider, service_slug, resource_type):
        """策略2：通过provider查询获取文档（尝试不同namespace）"""
        try:
            # 根据官方文档，调整华为云的namespace优先级
            if provider == "huaweicloud":
                namespaces_to_try = [
                    "huaweicloud",        # 华为云官方namespace
                    "hashicorp",          # 可能的官方支持
                    "terraform-providers", # 社区providers
                    "registry.terraform.io" # 完整格式
                ]
            else:
                namespaces_to_try = [
                    "hashicorp",          # 大多数官方provider
                    provider,             # 使用provider名作为namespace
                    "terraform-providers", # 旧格式
                    "registry.terraform.io" # 完整格式
                ]
            
            for namespace in namespaces_to_try:
                self.logger.info(f"🔍 尝试provider查询: {namespace}/{provider}")
                
                # 第一步：查询文档列表
                doc_list_response = self._query_mcp_doc_list_with_namespace(provider, service_slug, namespace)
                if not doc_list_response:
                    continue
                    
                # 解析文档列表，找到最相关的文档ID
                doc_id = self._parse_doc_list_for_resource(doc_list_response, resource_type)
                if not doc_id:
                    continue
                
                # 第二步：查询详细文档
                detailed_docs = self._query_mcp_detailed_docs(doc_id)
                if detailed_docs:
                    return detailed_docs
            
            return None
            
        except Exception as e:
            self.logger.error(f"Provider查询失败: {str(e)}")
            return None

    def _query_mcp_doc_list_with_namespace(self, provider, service_slug, namespace):
        """使用指定namespace查询MCP文档列表"""
        try:
            # 根据官方文档，serviceSlug应该是简单的资源名，不包含provider前缀
            simple_service_slug = service_slug.replace(f"{provider}_", "") if service_slug.startswith(f"{provider}_") else service_slug
            
            # 修复：MCP server必须运行在stdio模式下
            mcp_command = [
                "docker", "exec", "-i", self.mcp_container_name,
                self.mcp_server_path, "stdio"  # 明确指定stdio模式
            ]
            
            query_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "resolveProviderDocID",
                    "arguments": {
                        "providerName": provider,
                        "providerNamespace": namespace,
                        "serviceSlug": simple_service_slug,  # 使用简化的serviceSlug
                        "providerDataType": "resources",
                        "providerVersion": "latest"
                    }
                }
            }
            
            self.logger.info(f"🔍 Provider查询详情: {namespace}/{provider}, serviceSlug='{simple_service_slug}'")
            
            # 添加换行符，MCP协议需要
            request_data = json.dumps(query_request) + "\n"
            
            result = subprocess.run(
                mcp_command,
                input=request_data,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # 添加详细的响应日志
                response_preview = result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout
                self.logger.info(f"📋 MCP响应预览: {response_preview}")
                return result.stdout
            else:
                self.logger.warning(f"❌ Provider查询失败: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"查询MCP文档列表时出错: {str(e)}")
            return None

    def _query_mcp_generic_modules(self, provider, resource_type):
        """策略3：通用模块搜索（不限定云平台）"""
        try:
            # 使用通用资源术语搜索
            generic_terms = {
                "vpc": ["vpc", "virtual network", "network"],
                "compute_instance": ["compute", "virtual machine", "instance"],
                "subnet": ["subnet"],
                "security_group": ["security group", "firewall"],
                "rds_instance": ["database", "rds"],
                "obs_bucket": ["object storage", "storage"],
                "elb_loadbalancer": ["load balancer"]
            }
            
            terms = generic_terms.get(resource_type, [resource_type])
            
            for term in terms:
                self.logger.info(f"🔍 通用模块搜索: '{term}'")
                
                modules_response = self._search_modules(term)
                if not modules_response:
                    continue
                
                # 查找包含云平台关键词的模块
                module_id = self._parse_module_search_results(modules_response, provider, resource_type)
                if not module_id:
                    continue
                
                module_details = self._get_module_details(module_id)
                if module_details:
                    return module_details
            
            return None
            
        except Exception as e:
            self.logger.error(f"通用模块搜索失败: {str(e)}")
            return None

    def _parse_doc_list_for_resource(self, response, resource_type):
        """从文档列表响应中解析出相关的文档ID（用于provider查询）"""
        try:
            # 添加详细的解析日志
            self.logger.info(f"🔍 解析文档列表，寻找资源类型: {resource_type}")
            
            # 解析响应，找到包含目标资源类型的文档
            lines = response.strip().split('\n')
            found_docs = []
            
            for line in lines:
                if line.startswith('{"jsonrpc"'):
                    try:
                        parsed_response = json.loads(line)
                        if "result" in parsed_response and "content" in parsed_response["result"]:
                            content = parsed_response["result"]["content"]
                            if isinstance(content, list) and len(content) > 0:
                                # 解析内容，查找匹配的资源
                                for item in content:
                                    if isinstance(item, dict) and "text" in item:
                                        text_content = item["text"]
                                        
                                        # 更宽松的匹配策略
                                        resource_variants = [
                                            resource_type.lower(),
                                            resource_type.replace("_", " "),
                                            resource_type.replace("vpc_", ""),  # 华为云特殊处理
                                            resource_type.split("_")[-1]  # 取最后一部分
                                        ]
                                        
                                        for variant in resource_variants:
                                            if variant in text_content.lower():
                                                # 使用正则表达式提取文档ID
                                                import re
                                                id_patterns = [
                                                    r'"providerDocID":\s*"([^"]+)"',
                                                    r'"id":\s*"([^"]+)"',
                                                    r'providerDocID:\s*([^\s,\}]+)'
                                                ]
                                                
                                                for pattern in id_patterns:
                                                    id_match = re.search(pattern, text_content)
                                                    if id_match:
                                                        doc_id = id_match.group(1)
                                                        found_docs.append({
                                                            "id": doc_id,
                                                            "variant": variant,
                                                            "text": text_content[:200]
                                                        })
                                                        self.logger.info(f"✅ 找到匹配文档: ID={doc_id}, 匹配词='{variant}'")
                                                        break
                                                
                                                if found_docs:
                                                    break
                                        
                                        if found_docs:
                                            break
                    except json.JSONDecodeError:
                        continue
            
            if found_docs:
                # 返回第一个找到的文档ID
                best_doc = found_docs[0]
                self.logger.info(f"🎯 选择文档ID: {best_doc['id']} (匹配: {best_doc['variant']})")
                return best_doc["id"]
            else:
                self.logger.warning(f"❌ 在响应中未找到 {resource_type} 相关的文档ID")
                # 输出响应内容的前300字符用于调试
                response_preview = response[:300] + "..." if len(response) > 300 else response
                self.logger.info(f"📋 响应内容预览: {response_preview}")
                return None
            
        except Exception as e:
            self.logger.error(f"解析文档列表响应时出错: {str(e)}")
            return None

    def _query_mcp_detailed_docs(self, doc_id):
        """查询指定文档ID的详细文档（用于provider查询）"""
        try:
            # 修复：MCP server必须运行在stdio模式下
            mcp_command = [
                "docker", "exec", "-i", self.mcp_container_name,
                self.mcp_server_path, "stdio"  # 明确指定stdio模式
            ]
            
            # 构建详细文档查询请求
            detail_request = {
                "jsonrpc": "2.0", 
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "getProviderDocs",
                    "arguments": {
                        "providerDocID": doc_id
                    }
                }
            }
            
            self.logger.info(f"查询providerDocID '{doc_id}' 的详细文档")
            
            # 添加换行符，MCP协议需要
            request_data = json.dumps(detail_request) + "\n"
            
            # 执行详细文档查询
            result = subprocess.run(
                mcp_command,
                input=request_data,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.logger.info(f"MCP server详细文档响应长度: {len(result.stdout)} 字符")
                
                # 解析详细文档响应
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.startswith('{"jsonrpc"'):
                        try:
                            parsed_response = json.loads(line)
                            if "result" in parsed_response and "content" in parsed_response["result"]:
                                content = parsed_response["result"]["content"]
                                if isinstance(content, list) and len(content) > 0:
                                    for item in content:
                                        if isinstance(item, dict) and "text" in item:
                                            doc_text = item["text"]
                                            self.logger.info(f"成功获取详细文档，长度: {len(doc_text)} 字符")
                                            return doc_text
                        except json.JSONDecodeError:
                            continue
                
                self.logger.warning("详细文档响应中未找到有效内容")
                return None
            else:
                self.logger.error(f"MCP server详细文档查询失败: {result.stderr}")
                return None
                
        except Exception as e:
            self.logger.error(f"查询详细文档时出错: {str(e)}")
            return None

    def _combine_mcp_docs(self, all_docs, provider, user_description):
        """合并所有查询到的文档"""
        combined_content = f"""
# {provider.upper()} Provider Documentation

Based on your request: "{user_description}"

Here are the relevant Terraform resource documentations:

"""
        
        for doc_info in all_docs:
            resource_type = doc_info["resource_type"]
            service_slug = doc_info["service_slug"] 
            docs = doc_info["docs"]
            
            combined_content += f"""
## {service_slug} Resource Documentation

Resource Type: {resource_type}
Service Slug: {service_slug}

{docs}

---

"""
        
        combined_content += """
Please use these documentations as reference to generate accurate and complete Terraform code that includes all necessary resources and their proper configurations.
"""
        
        return combined_content

    def _enhance_terraform_code_legacy(self, user_description, mermaid_code, mcp_code, cloud_provider=None):
        """使用AI增强MCP生成的Terraform代码（legacy方法）"""
        try:
            self.logger.info("使用AI增强MCP生成的Terraform代码（legacy方法）")
            
            # 构建增强提示
            system_prompt = r"""
            You are a DevOps engineer expert in Terraform. 
            Your task is to review and enhance Terraform code generated by MCP server.
            
            CRITICAL REQUIREMENTS:
            1. Review the MCP-generated code for correctness and completeness
            2. Add any missing resources or configurations
            3. Ensure the code is complete and ready to execute
            4. Include provider configuration if missing
            5. Use best practices and meaningful resource names
            6. Add helpful comments to explain key sections of the code
            7. Ensure proper resource dependencies and complete all necessary components
            8. If essential components are missing, add them to ensure the infrastructure works properly
            
            Remember: EVERY resource must have at least one output block.
            
            Only return the complete enhanced Terraform code without any additional explanations or markdown formatting.
            """
            
            user_prompt = f"""
            User request: {user_description}
            
            Mermaid diagram of the infrastructure:
            ```
            {mermaid_code}
            ```
            
            MCP Server Generated Code:
            ```
            {mcp_code}
            ```
            
            Please review and enhance the above MCP-generated Terraform code.
            Ensure it meets all requirements and is production-ready.
            """
            
            # 确定AI提供商并调用相应API
            ai_provider = 'openai'  # 默认值
            if self.config:
                ai_provider = getattr(self.config, 'ai_model_provider', 'openai').lower()
            else:
                ai_provider = os.environ.get('AI_MODEL_PROVIDER', 'openai').lower()
            
            self.logger.info(f"使用AI提供商增强MCP代码: {ai_provider}")
            
            # 根据AI提供商进行调用
            if ai_provider == 'anthropic':
                # Anthropic配置
                api_key = None
                if self.config:
                    api_key = getattr(self.config, 'anthropic_api_key', '')
                if not api_key:
                    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
                
                api_base_url = None
                if self.config:
                    api_base_url = getattr(self.config, 'anthropic_api_base_url', 'https://api.anthropic.com/v1')
                if not api_base_url:
                    api_base_url = os.environ.get('ANTHROPIC_API_BASE_URL', 'https://api.anthropic.com/v1')
                
                model_name = None
                if self.config:
                    model_name = getattr(self.config, 'anthropic_api_model', 'claude-3-5-sonnet-20241022')
                if not model_name:
                    model_name = os.environ.get('ANTHROPIC_API_MODEL', 'claude-3-5-sonnet-20241022')
                
                if not api_key:
                    self.logger.error("未配置Anthropic API密钥，无法增强Terraform代码")
                    return jsonify({
                        "success": False,
                        "error": "未配置Anthropic API密钥"
                    }), 500
                
                # 使用Anthropic API
                import anthropic
                client = anthropic.Anthropic(
                    api_key=api_key,
                    base_url=api_base_url
                )
                
                self.logger.info(f"使用Anthropic API增强代码，模型: {model_name}")
                
                response = client.messages.create(
                    model=model_name,
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
                
                enhanced_code = response.content[0].text
                
            else:
                # OpenAI配置（包括其他兼容的提供商）
                api_key = None
                if self.config:
                    api_key = getattr(self.config, 'openai_api_key', '')
                if not api_key:
                    api_key = os.environ.get('OPENAI_API_KEY', '')
                
                api_base_url = None
                if self.config:
                    api_base_url = getattr(self.config, 'openai_api_base_url', 'https://api.openai.com/v1')
                if not api_base_url:
                    api_base_url = os.environ.get('OPENAI_API_BASE_URL', 'https://api.openai.com/v1')
                
                model_name = None
                if self.config:
                    model_name = getattr(self.config, 'openai_api_model', 'gpt-4o')
                if not model_name:
                    model_name = os.environ.get('OPENAI_API_MODEL', 'gpt-4o')
                
                if not api_key:
                    self.logger.error("未配置OpenAI API密钥，无法增强Terraform代码")
                    return jsonify({
                        "success": False,
                        "error": "未配置OpenAI API密钥"
                    }), 500
                
                # 使用OpenAI API
                import openai
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url=api_base_url
                )
                
                self.logger.info(f"使用OpenAI API增强代码，模型: {model_name}")
                
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.4,
                    max_tokens=4000
                )
                
                enhanced_code = response.choices[0].message.content
            
            # 清理和格式化生成的代码
            enhanced_code = self._clean_terraform_code(enhanced_code)
            
            self.logger.info(f"AI成功增强MCP代码，最终代码长度: {len(enhanced_code)} 字符")
            
            return jsonify({
                "success": True,
                "terraform_code": enhanced_code
            }), 200
            
        except Exception as e:
            self.logger.error(f"增强MCP代码时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": f"增强代码失败: {str(e)}"
            }), 500

    def generate_terraform_code(self, user_description, mermaid_code, cloud_provider=None):
        """根据用户描述和Mermaid代码生成Terraform代码"""
        try:
            # 确保部署目录存在
            self.logger.info(f"确保部署目录存在: {self.deployments_dir}")
            os.makedirs(self.deployments_dir, exist_ok=True)
            
            # 记录输入信息
            self.logger.info(f"开始生成Terraform代码，Mermaid代码长度: {len(mermaid_code)}")
            
            # 检测云提供商（如果未明确指定）
            if not cloud_provider:
                cloud_provider = CloudTerraformPrompts.detect_cloud_from_description(user_description)
            
            self.logger.info(f"检测到目标云提供商: {cloud_provider}")
            
            # 首先尝试使用MCP server生成基础代码
            mcp_generated_code = None
            if self.enable_mcp:
                self.logger.info("MCP server已启用，尝试使用MCP server生成基础Terraform代码")
                mcp_generated_code = self._generate_with_mcp(user_description, mermaid_code)
                
                if mcp_generated_code:
                    self.logger.info(f"MCP server成功返回provider信息，长度: {len(mcp_generated_code)} 字符")
                    self.logger.info("现在将MCP返回的provider信息发送给AI参考生成代码")
                else:
                    self.logger.warning("MCP server查询provider失败，将直接使用AI生成")
            else:
                self.logger.info("MCP server未启用，直接使用AI生成代码")
            
            # 检查AI客户端是否已初始化
            if not self.ai_client:
                # 如果没有AI客户端，尝试使用旧的OpenAI API方式（向后兼容）
                if mcp_generated_code:
                    return self._enhance_terraform_code_legacy(user_description, mermaid_code, mcp_generated_code, cloud_provider)
                else:
                    return self._generate_terraform_code_legacy(user_description, mermaid_code, cloud_provider)
            
            # 根据是否有MCP生成的代码来构建不同的提示
            if mcp_generated_code:
                # 有MCP返回的provider信息，让AI参考生成代码
                # 使用云提供商特定的prompt，但添加MCP参考信息
                system_prompt = CloudTerraformPrompts.get_cloud_specific_prompt(cloud_provider, user_description)
                system_prompt += """

ADDITIONAL REQUIREMENTS FOR MCP REFERENCE:
1. Use the provided provider documentation as reference for correct resource syntax and configuration
2. Follow Terraform best practices from the provider documentation
3. Add necessary output variables
4. Maintain consistency with user requirements and Mermaid diagram"""
                
                user_prompt = f"""
                User Description:
                {user_description}
                
                Mermaid Diagram:
                {mermaid_code}
                
                Provider Documentation Reference:
                {mcp_generated_code}
                
                Please generate complete Terraform code for {cloud_provider} using NATIVE CLOUD RESOURCES based on the user requirements and Mermaid diagram.
                
                IMPORTANT REMINDERS:
                - Use the provider documentation as reference for correct syntax and configuration
                - Generate a complete, executable Terraform configuration for {cloud_provider}
                
                Return complete, executable Terraform code.
                """
            else:
                # 没有MCP代码，直接AI生成，使用云提供商特定的prompt
                system_prompt = CloudTerraformPrompts.get_cloud_specific_prompt(cloud_provider, user_description)
                
                user_prompt_template = CloudTerraformPrompts.get_user_prompt_template()
                user_prompt = user_prompt_template.format(
                    user_description=user_description,
                    mermaid_code=mermaid_code,
                    cloud_provider=cloud_provider
                )
            
            # 使用AI客户端生成代码
            try:
                if hasattr(self.ai_client, 'client'):
                    # 获取底层客户端
                    if hasattr(self.ai_client, 'model'):
                        model = self.ai_client.model
                    else:
                        model = 'gpt-4'  # 默认模型
                    
                    if mcp_generated_code:
                        self.logger.info(f"准备使用AI参考MCP provider信息生成代码，提供商: {self.config.ai_model_provider}, 模型: {model}")
                        action_description = "参考MCP provider信息生成代码"
                    else:
                        self.logger.info(f"准备使用AI直接生成Terraform代码，提供商: {self.config.ai_model_provider}, 模型: {model}")
                        action_description = "直接生成Terraform代码"
                    
                    # 根据不同的AI提供商调用不同的API
                    if self.config.ai_model_provider == 'anthropic':
                        # Anthropic API
                        response = self.ai_client.client.messages.create(
                            model=model,
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
                        terraform_code = response.content[0].text
                    else:
                        # OpenAI API
                        response = self.ai_client.client.chat.completions.create(
                            model=model,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.4,
                            max_tokens=4000
                        )
                        terraform_code = response.choices[0].message.content
                else:
                    # 如果没有底层客户端，使用通用方法
                    self.logger.warning("AI客户端没有底层客户端，使用旧方法")
                    return self._generate_terraform_code_legacy(user_description, mermaid_code)
                
                if mcp_generated_code:
                    self.logger.info("AI客户端成功参考MCP provider信息生成Terraform代码")
                else:
                    self.logger.info("AI客户端成功生成Terraform代码")
                
                # 清理和格式化生成的代码
                terraform_code = self._clean_terraform_code(terraform_code)
                
                # 返回结果
                result = {
                    "success": True,
                    "terraform_code": terraform_code
                }
                
                return jsonify(result), 200
                
            except Exception as e:
                self.logger.error(f"AI生成Terraform代码失败: {str(e)}")
                self.logger.error(traceback.format_exc())
                return jsonify({
                    "success": False,
                    "error": f"AI生成失败: {str(e)}"
                }), 500
                
        except Exception as e:
            self.logger.error(f"生成Terraform代码时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def _generate_terraform_code_legacy(self, user_description, mermaid_code, cloud_provider=None):
        """根据配置的AI提供商生成Terraform代码"""
        try:
            # 检测云提供商（如果未明确指定）
            if not cloud_provider:
                cloud_provider = CloudTerraformPrompts.detect_cloud_from_description(user_description)
            
            self.logger.info(f"Legacy模式使用云提供商: {cloud_provider}")
            
            # 使用云提供商特定的prompt
            system_prompt = CloudTerraformPrompts.get_cloud_specific_prompt(cloud_provider, user_description)
            
            # 检查用户描述是否同时包含EC2和Linux关键词
            needs_amazon_linux_ami = "ec2" in user_description.lower() and "linux" in user_description.lower()
            
            if needs_amazon_linux_ami:
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
                
            # 检查用户描述是否包含火山云相关关键词
            is_volcengine = any(keyword in user_description.lower() for keyword in ["火山云", "火山引擎", "volcengine"])
            is_volcengine_ecs = is_volcengine and "ecs" in user_description.lower()
            
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
            
            # 构建用户提示，使用云提供商特定的模板
            user_prompt_template = CloudTerraformPrompts.get_user_prompt_template()
            user_prompt = user_prompt_template.format(
                user_description=user_description,
                mermaid_code=mermaid_code,
                cloud_provider=cloud_provider
            )
            
            # 确定AI提供商
            ai_provider = 'openai'  # 默认值
            if self.config:
                ai_provider = getattr(self.config, 'ai_model_provider', 'openai').lower()
            else:
                ai_provider = os.environ.get('AI_MODEL_PROVIDER', 'openai').lower()
            
            self.logger.info(f"使用AI提供商生成Terraform代码: {ai_provider}")
            
            # 根据AI提供商获取相应的配置
            if ai_provider == 'anthropic':
                # Anthropic配置
                api_key = None
                if self.config:
                    api_key = getattr(self.config, 'anthropic_api_key', '')
                if not api_key:
                    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
                
                api_base_url = None
                if self.config:
                    api_base_url = getattr(self.config, 'anthropic_api_base_url', 'https://api.anthropic.com/v1')
                if not api_base_url:
                    api_base_url = os.environ.get('ANTHROPIC_API_BASE_URL', 'https://api.anthropic.com/v1')
                
                model_name = None
                if self.config:
                    model_name = getattr(self.config, 'anthropic_api_model', 'claude-3-5-sonnet-20241022')
                if not model_name:
                    model_name = os.environ.get('ANTHROPIC_API_MODEL', 'claude-3-5-sonnet-20241022')
                
                if not api_key:
                    self.logger.error("未配置Anthropic API密钥，无法生成Terraform代码")
                    return jsonify({
                        "success": False,
                        "error": "未配置Anthropic API密钥"
                    }), 500
            else:
                # OpenAI配置（默认）
                api_key = None
                if hasattr(self, 'openai_api_key'):
                    api_key = self.openai_api_key
                elif self.config:
                    api_key = getattr(self.config, 'openai_api_key', '')
                
                if not api_key:
                    api_key = os.environ.get('OPENAI_API_KEY', '')
                
                api_base_url = None
                if hasattr(self, 'openai_api_base_url'):
                    api_base_url = self.openai_api_base_url
                elif self.config:
                    api_base_url = getattr(self.config, 'openai_api_base_url', 'https://api.openai.com/v1')
                
                if not api_base_url:
                    api_base_url = os.environ.get('OPENAI_API_BASE_URL', 'https://api.openai.com/v1')
                
                model_name = None
                if hasattr(self, 'openai_api_model'):
                    model_name = self.openai_api_model
                elif self.config:
                    model_name = getattr(self.config, 'openai_api_model', 'gpt-4o')
                
                if not model_name:
                    model_name = os.environ.get('OPENAI_API_MODEL', 'gpt-4o')
                
                if not api_key:
                    self.logger.error("未配置OpenAI API密钥，无法生成Terraform代码")
                    return jsonify({
                        "success": False,
                        "error": "未配置OpenAI API密钥"
                    }), 500
                
            # 记录使用的API设置
            self.logger.info(f"使用API Base URL: {api_base_url}")
            self.logger.info(f"使用模型: {model_name}")
            
            # 根据AI提供商初始化客户端
            client = None
            if ai_provider == 'anthropic':
                import anthropic
                client = anthropic.Anthropic(
                    api_key=api_key,
                    base_url=api_base_url
                )
            else:
                import openai
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url=api_base_url
                )
            
            # 根据AI提供商调用相应的API
            self.logger.info(f"调用{ai_provider}生成Terraform代码")
            if ai_provider == 'anthropic':
                # 调用Anthropic API
                response = client.messages.create(
                    model=model_name,
                    max_tokens=4000,
                    temperature=0.4,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )
                # 解析响应
                content = response.content[0].text
            else:
                # 调用OpenAI API
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.4  # 适中的温度以确保一致性
                )
                # 解析响应
                content = response.choices[0].message.content
            
            # 提取Terraform代码（移除可能的代码块标记）
            terraform_code = self._clean_terraform_code(content)
            
            # ... existing code ...
            
        except Exception as e:
            self.logger.error(f"生成Terraform代码时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": "生成Terraform代码时出错",
                "message": str(e)
            }), 500
    
    def _clean_terraform_code(self, content):
        """清理从OpenAI获得的Terraform代码，移除可能的Markdown代码块标记"""
        # 移除可能的Markdown代码块标记
        if '```terraform' in content or '```hcl' in content:
            # 使用正则表达式提取代码块内容
            pattern = r'```(?:terraform|hcl)\s*([\s\S]*?)```'
            matches = re.findall(pattern, content)
            if matches:
                return matches[0].strip()
            
        # 如果没有找到特定的代码块标记，尝试匹配任何代码块
        if '```' in content:
            pattern = r'```\s*([\s\S]*?)```'
            matches = re.findall(pattern, content)
            if matches:
                return matches[0].strip()
        
        # 如果没有代码块标记，直接返回整个内容
        return content.strip()
    
    def deploy_terraform(self):
        """处理Terraform部署请求"""
        try:
            # 获取请求数据
            data = request.get_json()
            if not data:
                return jsonify({"error": "请求数据无效"}), 400
            
            # 验证必需参数
            if 'code' not in data:
                return jsonify({"error": "缺少Terraform代码"}), 400
            
            # 获取用户ID
            user = getattr(request, 'current_user', None)
            user_id = user.get('user_id', 0) if user else 0
            
            # 获取项目ID和云平台ID
            project_id = data.get('project_id', 0)
            project_name = data.get('project_name', '未命名项目')
            cloud_id = data.get('cloud_id', 0)
            cloud_name = data.get('cloud_name', '未知云平台')
            
            # 记录接收到的项目和云平台信息
            self.logger.info(f"部署请求接收到的项目和云平台信息: project_id={project_id}, project_name='{project_name}', cloud_id={cloud_id}, cloud_name='{cloud_name}'")
            
            # 获取API密钥ID或直接的凭证
            api_key_id = data.get('api_key_id')
            ak = data.get('ak', '')
            sk = data.get('sk', '')
            
            # 如果提供了API密钥ID，尝试查找对应的凭证
            if api_key_id and (not ak or not sk):
                try:
                    from controllers.apikey_controller import ApiKeyController
                    apikey_controller = ApiKeyController(self.config)
                    api_key = apikey_controller.get_api_key_by_id(api_key_id)
                    
                    if not api_key:
                        self.logger.error(f"找不到指定的API密钥: {api_key_id}")
                        return jsonify({"error": "找不到指定的API密钥"}), 404
                    
                    # 获取AK和SK
                    ak = api_key.get('ak', '')
                    sk = api_key.get('sk', '')
                    
                    self.logger.info(f"成功通过ID获取API密钥: {api_key.get('apikey_name')}")
                except Exception as apikey_error:
                    self.logger.error(f"获取API密钥时出错: {str(apikey_error)}")
                    return jsonify({"error": f"获取API密钥时出错: {str(apikey_error)}"}), 500
            
            # 检查是否提供了凭证
            if not ak or not sk:
                return jsonify({"error": "请提供有效的访问凭证"}), 400
            
            # 获取原始Terraform代码
            original_code = data.get('code', '')
            
            # 检查代码是否为空
            if not original_code.strip():
                return jsonify({"error": "不能部署空的Terraform代码"}), 400
            
            # 使用智能凭证添加方法，根据代码中的云平台类型自动添加相应凭证
            terraform_code = self._add_cloud_credentials_to_code(original_code, ak, sk)
            
            # 生成部署ID (AIDP前缀+23位随机数)
            deploy_id = f"AIDP{uuid.uuid4().hex[:19]}".upper()
            
            # 创建部署目录
            deploy_dir = os.path.join(self.deployments_dir, deploy_id)
            os.makedirs(deploy_dir, exist_ok=True)
            
            # 创建main.tf文件
            tf_file_path = os.path.join(deploy_dir, 'main.tf')
            with open(tf_file_path, 'w') as f:
                f.write(terraform_code)
            
            # 保存原始代码，用于对比和恢复（使用.bak扩展名避免Terraform读取）
            original_code_path = os.path.join(deploy_dir, 'original.tf.bak')
            with open(original_code_path, 'w') as f:
                f.write(original_code)
            
            # 创建部署记录
            deploy_data = {
                'id': deploy_id,
                'user_id': user_id,
                'username': user.get('username', 'unknown'),
                'name': project_name,
                'description': f"云平台: {cloud_name}, 项目ID: {project_id}",
                'project': project_name,
                'cloud': cloud_name,
                'status': 'pending',
                'terraform_code': terraform_code,
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 保存部署记录
            self.logger.info(f"正在创建部署记录: deploy_id={deploy_id}, project='{project_name}', cloud='{cloud_name}'")
            self.deployment_model.create_deployment(deploy_data)
            self.logger.info(f"部署记录已创建并写入数据库: {deploy_id}")
            
            # 启动后台任务
            deployment_thread = threading.Thread(
                target=self._run_terraform_deployment,
                args=(deploy_id, deploy_dir, user_id)
            )
            deployment_thread.start()
            
            # 记录活跃的部署信息
            self.active_deployments[deploy_id] = {
                'thread': deployment_thread,
                'process': None,  # 稍后在_run_terraform_deployment中设置
                'deploy_dir': deploy_dir,
                'user_id': user_id
            }
            
            return jsonify({
                "success": True,
                "deploy_id": deploy_id,
                "message": "部署任务已提交，正在后台执行"
            })
            
        except Exception as e:
            self.logger.error(f"部署Terraform时出错: {str(e)}")
            traceback_str = traceback.format_exc()
            self.logger.error(f"详细错误: {traceback_str}")
            return jsonify({"error": f"部署Terraform时出错: {str(e)}"}), 500
    
    def _add_aws_credentials_to_code(self, terraform_code, ak, sk):
        """向Terraform代码中添加AWS凭证"""
        # 检查代码中的AWS provider
        providers = []
        lines = terraform_code.split('\n')
        
        # 寻找已有的AWS provider并记录
        for i, line in enumerate(lines):
            if re.match(r'\s*provider\s+"aws"\s+{', line):
                provider_start = i
                provider_end = -1
                
                # 找到provider块的结束
                for j in range(provider_start + 1, len(lines)):
                    if re.match(r'\s*}', lines[j]):
                        provider_end = j
                        break
                
                if provider_end > 0:
                    provider_lines = lines[provider_start:provider_end+1]
                    # 获取provider别名（如果有）
                    alias = None
                    for provider_line in provider_lines:
                        alias_match = re.search(r'alias\s+=\s+"([^"]+)"', provider_line)
                        if alias_match:
                            alias = alias_match.group(1)
                            break
                    
                    providers.append({
                        'start': provider_start,
                        'end': provider_end,
                        'alias': alias
                    })
        
        # 为每个provider添加凭证
        offset = 0  # 行偏移量（添加行会改变后续行号）
        
        for provider in providers:
            # 获取provider内容
            start = provider['start'] + offset
            end = provider['end'] + offset
            
            # 检查provider中是否已有access_key和secret_key
            has_credentials = False
            has_access_key = False
            has_secret_key = False
            
            for i in range(start, end):
                # 检查是否有非空的access_key设置（不包括注释和空值）
                if re.search(r'access_key\s*=\s*".+?"', lines[i]) or re.search(r"access_key\s*=\s*'.+?'", lines[i]):
                    if not re.search(r'access_key\s*=\s*["\']\s*["\']', lines[i]):  # 跳过空值
                        has_access_key = True
                        
                # 检查是否有非空的secret_key设置（不包括注释和空值）
                if re.search(r'secret_key\s*=\s*".+?"', lines[i]) or re.search(r"secret_key\s*=\s*'.+?'", lines[i]):
                    if not re.search(r'secret_key\s*=\s*["\']\s*["\']', lines[i]):  # 跳过空值
                        has_secret_key = True
                        
                # 只有两者都存在才视为有效凭证
                if has_access_key and has_secret_key:
                    has_credentials = True
                    self.logger.info("检测到火山引擎provider已包含有效的AK/SK")
                    break
            
            # 如果没有凭证，则添加
            if not has_credentials:
                # 在provider块结束前添加凭证
                credentials = [
                    f"  access_key = \"{ak}\"",
                    f"  secret_key = \"{sk}\""
                ]
                
                # 插入凭证到provider块结束前
                lines.insert(end, credentials[1])
                lines.insert(end, credentials[0])
                
                # 更新偏移量
                offset += 2
        
        # 如果没有找到provider，则添加一个默认provider
        if not providers:
            default_provider = [
                "provider \"aws\" {",
                f"  access_key = \"{ak}\"",
                f"  secret_key = \"{sk}\"",
                "  region = \"us-east-1\"",
                "}"
            ]
            
            # 在代码开头添加默认provider
            lines = default_provider + [''] + lines
        
        return '\n'.join(lines)
    
    def _add_volcengine_credentials_to_code(self, terraform_code, ak, sk):
        """向Terraform代码中添加火山引擎凭证"""
        self.logger.info("添加火山引擎凭证到Terraform代码")
        
        # 检查代码中是否有火山引擎provider
        providers = []
        lines = terraform_code.split('\n')
        
        # 寻找已有的火山引擎provider并记录
        for i, line in enumerate(lines):
            if re.match(r'\s*provider\s+"volcengine"\s+{', line):
                provider_start = i
                provider_end = -1
                
                # 找到provider块的结束
                for j in range(provider_start + 1, len(lines)):
                    if re.match(r'\s*}', lines[j]):
                        provider_end = j
                        break
                
                if provider_end > 0:
                    providers.append({
                        'start': provider_start,
                        'end': provider_end
                    })
        
        # 为每个provider添加凭证
        offset = 0  # 行偏移量（添加行会改变后续行号）
        
        for provider in providers:
            # 获取provider内容
            start = provider['start'] + offset
            end = provider['end'] + offset
            
            # 检查provider中是否已有access_key和secret_key
            has_credentials = False
            has_access_key = False
            has_secret_key = False
            
            for i in range(start, end):
                # 检查是否有非空的access_key设置（不包括注释和空值）
                if re.search(r'access_key\s*=\s*".+?"', lines[i]) or re.search(r"access_key\s*=\s*'.+?'", lines[i]):
                    if not re.search(r'access_key\s*=\s*["\']\s*["\']', lines[i]):  # 跳过空值
                        has_access_key = True
                        
                # 检查是否有非空的secret_key设置（不包括注释和空值）
                if re.search(r'secret_key\s*=\s*".+?"', lines[i]) or re.search(r"secret_key\s*=\s*'.+?'", lines[i]):
                    if not re.search(r'secret_key\s*=\s*["\']\s*["\']', lines[i]):  # 跳过空值
                        has_secret_key = True
                        
                # 只有两者都存在才视为有效凭证
                if has_access_key and has_secret_key:
                    has_credentials = True
                    self.logger.info("检测到火山引擎provider已包含有效的AK/SK")
                    break
            
            # 如果没有凭证，则添加
            if not has_credentials:
                if has_access_key and not has_secret_key:
                    self.logger.info("火山引擎provider中只有access_key但缺少secret_key，添加凭证")
                elif has_secret_key and not has_access_key:
                    self.logger.info("火山引擎provider中只有secret_key但缺少access_key，添加凭证")
                else:
                    self.logger.info("火山引擎provider中缺少完整的AK/SK凭证，添加凭证")
                
                # 在provider块结束前添加凭证
                credentials = [
                    f"  access_key = \"{ak}\"",
                    f"  secret_key = \"{sk}\""
                ]
                
                # 插入凭证到provider块结束前
                lines.insert(end, credentials[1])
                lines.insert(end, credentials[0])
                
                # 更新偏移量
                offset += 2
        
        # 如果没有找到provider，则添加一个默认provider
        if not providers:
            # 检查代码中是否已经包含了required_providers块
            has_required_providers = False
            for line in lines:
                if "required_providers" in line:
                    has_required_providers = True
                    break
            
            # 准备添加的代码块
            provider_blocks = []
            
            # 如果没有required_providers块，添加一个
            if not has_required_providers:
                provider_blocks.extend([
                    "terraform {",
                    "  required_providers {",
                    "    volcengine = {",
                    "      source = \"volcengine/volcengine\"",
                    "      version = \"0.0.167\"",
                    "    }",
                    "  }",
                    "}",
                    ""
                ])
            
            # 添加provider块
            provider_blocks.extend([
                "provider \"volcengine\" {",
                "  region = \"cn-beijing\"",
                f"  access_key = \"{ak}\"",
                f"  secret_key = \"{sk}\"",
                "}",
                ""
            ])
            
            # 在代码开头添加provider块
            lines = provider_blocks + lines
            
            self.logger.info("找不到火山引擎provider，已添加默认provider配置")
        
        return '\n'.join(lines)
    
    def _run_terraform_deployment(self, deploy_id, deploy_dir, user_id):
        """在后台运行Terraform部署过程"""
        
        # 定义检查停止信号的辅助函数
        def should_stop_deployment():
            """检查是否应该停止部署"""
            stop_file = os.path.join(deploy_dir, '.stop_deployment')
            return os.path.exists(stop_file) or deploy_id not in self.active_deployments
        
        # 记录执行过程中的所有重要信息，用于创建摘要日志
        deployment_logs = {
            'deploy_id': deploy_id,
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'pending',
            'init_output': '',
            'plan_output': '',
            'apply_output': '',
            'init_error': '',
            'plan_error': '',
            'apply_error': '',
            'retry_count': 0,
            'error_message': '',
            'outputs': {}
        }
        
        # 创建或更新部署摘要日志的辅助函数
        def create_deployment_summary(is_success=True):
            deploy_summary_log = os.path.join(deploy_dir, 'deployment_summary.log')
            with open(deploy_summary_log, 'w') as summary_file:
                summary_file.write(f"部署ID: {deploy_id}\n")
                summary_file.write(f"开始时间: {deployment_logs['start_time']}\n")
                summary_file.write(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                summary_file.write(f"总重试次数: {deployment_logs['retry_count']}\n")
                summary_file.write(f"部署状态: {'成功' if is_success else '失败'}\n")
                if not is_success:
                    summary_file.write(f"失败原因: {deployment_logs['error_message']}\n")
                summary_file.write("\n")
                
                # 添加初始化信息
                if deployment_logs['init_output']:
                    summary_file.write("Terraform初始化输出:\n")
                    summary_file.write("-" * 80 + "\n")
                    summary_file.write(f"{deployment_logs['init_output']}\n\n")
                if deployment_logs['init_error']:
                    summary_file.write("Terraform初始化错误:\n")
                    summary_file.write("-" * 80 + "\n")
                    summary_file.write(f"{deployment_logs['init_error']}\n\n")
                
                # 添加规划信息
                if deployment_logs['plan_output']:
                    summary_file.write("Terraform规划输出:\n")
                    summary_file.write("-" * 80 + "\n")
                    summary_file.write(f"{deployment_logs['plan_output']}\n\n")
                if deployment_logs['plan_error']:
                    summary_file.write("Terraform规划错误:\n")
                    summary_file.write("-" * 80 + "\n")
                    summary_file.write(f"{deployment_logs['plan_error']}\n\n")
                
                # 添加应用信息
                if deployment_logs['apply_output']:
                    summary_file.write("Terraform应用输出:\n")
                    summary_file.write("-" * 80 + "\n")
                    summary_file.write(f"{deployment_logs['apply_output']}\n\n")
                if deployment_logs['apply_error']:
                    summary_file.write("Terraform应用错误:\n")
                    summary_file.write("-" * 80 + "\n")
                    summary_file.write(f"{deployment_logs['apply_error']}\n\n")
                
                # 添加修复历史
                if deployment_logs['retry_count'] > 0:
                    summary_file.write("修复历史:\n")
                    summary_file.write("-" * 80 + "\n")
                    fix_log_path = os.path.join(deploy_dir, 'fix_attempts.log')
                    if os.path.exists(fix_log_path):
                        with open(fix_log_path, 'r') as fix_log:
                            summary_file.write(fix_log.read())
                    summary_file.write("\n")
                
                # 添加输出变量
                if is_success and deployment_logs['outputs']:
                    summary_file.write("输出变量:\n")
                    summary_file.write("-" * 80 + "\n")
                    summary_file.write(f"{json.dumps(deployment_logs['outputs'], indent=2)}\n\n")
        
        try:
            self.logger.info(f"开始执行Terraform部署: {deploy_id}, 目录: {deploy_dir}")
            
            # 检查terraform命令是否存在
            try:
                terraform_version = subprocess.run(
                    ['terraform', '--version'],
                    capture_output=True,
                    text=True
                )
                self.logger.info(f"Terraform版本: {terraform_version.stdout.strip()}")
            except FileNotFoundError:
                error_msg = "未找到Terraform命令，请确保已安装Terraform并添加到PATH"
                self.logger.error(error_msg)
                deployment_logs['error_message'] = error_msg
                deployment_logs['status'] = 'failed'
                create_deployment_summary(is_success=False)
                self.deployment_model.update_deployment_status(
                    deploy_id, 
                    'failed', 
                    error_message=error_msg
                )
                return
            
            # 检查部署目录是否存在
            if not os.path.exists(deploy_dir):
                error_msg = f"部署目录不存在: {deploy_dir}"
                self.logger.error(error_msg)
                deployment_logs['error_message'] = error_msg
                deployment_logs['status'] = 'failed'
                create_deployment_summary(is_success=False)
                self.deployment_model.update_deployment_status(
                    deploy_id, 
                    'failed', 
                    error_message=error_msg
                )
                return
            
            # 检查main.tf文件是否存在
            tf_file_path = os.path.join(deploy_dir, 'main.tf')
            if not os.path.exists(tf_file_path):
                error_msg = f"Terraform配置文件不存在: {tf_file_path}"
                self.logger.error(error_msg)
                deployment_logs['error_message'] = error_msg
                deployment_logs['status'] = 'failed'
                create_deployment_summary(is_success=False)
                self.deployment_model.update_deployment_status(
                    deploy_id, 
                    'failed', 
                    error_message=error_msg
                )
                return
            
            # 最大重试次数
            max_retries = 20
            retry_count = 0
            
            # 开始部署循环，带重试和自动修复机制
            while retry_count <= max_retries:
                # 检查是否应该停止部署
                if should_stop_deployment():
                    self.logger.info(f"检测到停止信号，终止部署: {deploy_id}")
                    deployment_logs['error_message'] = '用户手动停止部署'
                    deployment_logs['status'] = 'stopped'
                    create_deployment_summary(is_success=False)
                    self.deployment_model.update_deployment_status(
                        deploy_id, 
                        'failed', 
                        error_message='用户手动停止部署'
                    )
                    return
                
                # 如果不是第一次尝试，更新状态为重试中
                if retry_count > 0:
                    self.logger.info(f"第{retry_count}次重试部署: {deploy_id}")
                    self.deployment_model.update_deployment_status(
                        deploy_id, 
                        'planning', 
                        error_message=f"第{retry_count}次重试，正在重新生成Terraform代码"
                    )
                    deployment_logs['retry_count'] = retry_count
                
                # 更新部署状态为"initializing"
                self.logger.info(f"更新部署状态为initializing: {deploy_id}")
                self.deployment_model.update_deployment_status(deploy_id, 'initializing')
                
                # 运行terraform init
                self.logger.info(f"开始初始化Terraform: {deploy_id}")
                try:
                    init_result = subprocess.run(
                        ['terraform', 'init'],
                        cwd=deploy_dir,
                        capture_output=True,
                        text=True
                    )
                    
                    # 记录输出
                    deployment_logs['init_output'] = init_result.stdout
                    
                    if init_result.returncode != 0:
                        deployment_logs['init_error'] = init_result.stderr
                        if retry_count < max_retries:
                            self.logger.error(f"Terraform初始化失败，尝试修复: {init_result.stderr}")
                            
                            # 如果存在之前的部署，先执行terraform destroy清理
                            if os.path.exists(os.path.join(deploy_dir, '.terraform')):
                                self.logger.info(f"执行terraform destroy清理之前可能存在的资源: {deploy_id}")
                                try:
                                    # 更新部署状态
                                    self.deployment_model.update_deployment_status(
                                        deploy_id, 
                                        'cleaning', 
                                        error_message=f"清理之前可能部署的资源，准备重新部署"
                                    )
                                    
                                    # 执行terraform destroy
                                    destroy_result = subprocess.run(
                                        ['terraform', 'destroy', '-auto-approve'],
                                        cwd=deploy_dir,
                                        capture_output=True,
                                        text=True
                                    )
                                    
                                    # 记录清理结果
                                    cleanup_log_path = os.path.join(deploy_dir, 'cleanup_attempts.log')
                                    with open(cleanup_log_path, 'a') as cleanup_file:
                                        cleanup_file.write(f"\n\n{'='*80}\n")
                                        cleanup_file.write(f"初始化错误清理 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                        cleanup_file.write(f"{'='*80}\n\n")
                                        cleanup_file.write("清理输出:\n```\n")
                                        cleanup_file.write(destroy_result.stdout)
                                        cleanup_file.write("\n```\n\n")
                                except Exception as destroy_error:
                                    self.logger.error(f"执行terraform destroy时出错: {str(destroy_error)}")
                            
                            # 读取原始Terraform代码
                            with open(tf_file_path, 'r') as f:
                                original_tf = f.read()
                            
                            # 尝试修复代码
                            fixed_tf = self._fix_terraform_code(original_tf, init_result.stderr, tf_file_path)
                            if fixed_tf:
                                self.logger.info("成功修复Terraform代码，准备重新部署")
                                # 保存修复后的代码
                                with open(tf_file_path, 'w') as f:
                                    f.write(fixed_tf)
                                
                                # 创建对比日志，记录修改前后的差异
                                diff_log_path = os.path.join(deploy_dir, 'code_diff.log')
                                with open(diff_log_path, 'a') as diff_file:
                                    diff_file.write(f"\n\n{'='*80}\n")
                                    diff_file.write(f"第{retry_count+1}次修复 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                    diff_file.write(f"{'='*80}\n\n")
                                    diff_file.write("修复前:\n```terraform\n")
                                    diff_file.write(original_tf)
                                    diff_file.write("\n```\n\n修复后:\n```terraform\n")
                                    diff_file.write(fixed_tf)
                                    diff_file.write("\n```\n")
                                
                                retry_count += 1
                                # 更新部署状态，告知用户正在修复
                                self.deployment_model.update_deployment_status(
                                    deploy_id, 
                                    'planning', 
                                    error_message=f"检测到Terraform初始化错误，已自动修复并重试 ({retry_count}/{max_retries})"
                                )
                                deployment_logs['retry_count'] = retry_count
                                self.logger.info(f"开始第{retry_count}次重试部署")
                                continue
                            else:
                                self.logger.warning("无法自动修复Terraform代码")
                        
                        self.logger.error(f"Terraform初始化失败: {init_result.stderr}")
                        
                        # 清理可能已部署的资源(达到最大重试次数时)
                        if retry_count >= max_retries and os.path.exists(os.path.join(deploy_dir, '.terraform')):
                            self.logger.info(f"达到最大重试次数({max_retries})，尝试清理可能存在的资源")
                            try:
                                # 更新状态为清理中
                                self.deployment_model.update_deployment_status(
                                    deploy_id, 
                                    'cleaning', 
                                    error_message=f"达到最大重试次数，正在清理已部署资源"
                                )
                                
                                # 执行terraform destroy
                                destroy_result = subprocess.run(
                                    ['terraform', 'destroy', '-auto-approve'],
                                    cwd=deploy_dir,
                                    capture_output=True,
                                    text=True
                                )
                                
                                if destroy_result.returncode != 0:
                                    self.logger.warning(f"资源清理失败: {destroy_result.stderr}")
                                else:
                                    self.logger.info(f"资源清理成功: {destroy_result.stdout}")
                                
                                # 记录清理结果
                                cleanup_log_path = os.path.join(deploy_dir, 'cleanup_attempts.log')
                                with open(cleanup_log_path, 'a') as cleanup_file:
                                    cleanup_file.write(f"\n\n{'='*80}\n")
                                    cleanup_file.write(f"达到最大重试次数清理 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                    cleanup_file.write(f"{'='*80}\n\n")
                                    cleanup_file.write("清理输出:\n```\n")
                                    cleanup_file.write(destroy_result.stdout)
                                    cleanup_file.write("\n```\n\n")
                                    if destroy_result.stderr:
                                        cleanup_file.write("清理错误:\n```\n")
                                        cleanup_file.write(destroy_result.stderr)
                                        cleanup_file.write("\n```\n\n")
                            except Exception as destroy_error:
                                self.logger.error(f"执行terraform destroy时出错: {str(destroy_error)}")
                        
                        error_msg = f"初始化失败: {init_result.stderr}"
                        deployment_logs['error_message'] = error_msg
                        deployment_logs['status'] = 'failed'
                        create_deployment_summary(is_success=False)
                        self.deployment_model.update_deployment_status(
                            deploy_id, 
                            'failed', 
                            error_message=error_msg
                        )
                        return
                        
                    self.logger.info(f"Terraform初始化成功: {init_result.stdout}")
                except Exception as init_error:
                    error_msg = f"执行terraform init时出错: {str(init_error)}"
                    self.logger.error(error_msg)
                    deployment_logs['error_message'] = error_msg
                    deployment_logs['status'] = 'failed'
                    create_deployment_summary(is_success=False)
                    self.deployment_model.update_deployment_status(
                        deploy_id, 
                        'failed', 
                        error_message=error_msg
                    )
                    return
                
                # 更新部署状态为"planning"
                self.logger.info(f"更新部署状态为planning: {deploy_id}")
                self.deployment_model.update_deployment_status(deploy_id, 'planning')
                
                # 运行terraform plan
                self.logger.info(f"开始Terraform规划: {deploy_id}")
                try:
                    plan_result = subprocess.run(
                        ['terraform', 'plan', '-out=tfplan'],
                        cwd=deploy_dir,
                        capture_output=True,
                        text=True
                    )
                    
                    # 记录输出
                    deployment_logs['plan_output'] = plan_result.stdout
                    
                    if plan_result.returncode != 0:
                        deployment_logs['plan_error'] = plan_result.stderr
                        if retry_count < max_retries:
                            self.logger.error(f"Terraform规划失败，尝试修复: {plan_result.stderr}")
                            
                            # 如果存在之前的部署，先执行terraform destroy清理
                            if os.path.exists(os.path.join(deploy_dir, '.terraform')):
                                self.logger.info(f"执行terraform destroy清理之前可能存在的资源: {deploy_id}")
                                try:
                                    # 更新部署状态
                                    self.deployment_model.update_deployment_status(
                                        deploy_id, 
                                        'cleaning', 
                                        error_message=f"清理之前可能部署的资源，准备重新部署"
                                    )
                                    
                                    # 执行terraform destroy
                                    destroy_result = subprocess.run(
                                        ['terraform', 'destroy', '-auto-approve'],
                                        cwd=deploy_dir,
                                        capture_output=True,
                                        text=True
                                    )
                                    
                                    # 记录清理结果
                                    cleanup_log_path = os.path.join(deploy_dir, 'cleanup_attempts.log')
                                    with open(cleanup_log_path, 'a') as cleanup_file:
                                        cleanup_file.write(f"\n\n{'='*80}\n")
                                        cleanup_file.write(f"规划错误清理 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                        cleanup_file.write(f"{'='*80}\n\n")
                                        cleanup_file.write("清理输出:\n```\n")
                                        cleanup_file.write(destroy_result.stdout)
                                        cleanup_file.write("\n```\n\n")
                                except Exception as destroy_error:
                                    self.logger.error(f"执行terraform destroy时出错: {str(destroy_error)}")
                            
                            # 读取原始Terraform代码
                            with open(tf_file_path, 'r') as f:
                                original_tf = f.read()
                            
                            # 尝试修复代码
                            fixed_tf = self._fix_terraform_code(original_tf, plan_result.stderr, tf_file_path)
                            if fixed_tf:
                                self.logger.info("成功修复Terraform代码，准备重新部署")
                                # 保存修复后的代码
                                with open(tf_file_path, 'w') as f:
                                    f.write(fixed_tf)
                                
                                # 创建对比日志，记录修改前后的差异
                                diff_log_path = os.path.join(deploy_dir, 'code_diff.log')
                                with open(diff_log_path, 'a') as diff_file:
                                    diff_file.write(f"\n\n{'='*80}\n")
                                    diff_file.write(f"第{retry_count+1}次修复 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                    diff_file.write(f"{'='*80}\n\n")
                                    diff_file.write("修复前:\n```terraform\n")
                                    diff_file.write(original_tf)
                                    diff_file.write("\n```\n\n修复后:\n```terraform\n")
                                    diff_file.write(fixed_tf)
                                    diff_file.write("\n```\n")
                                
                                retry_count += 1
                                # 更新部署状态，告知用户正在修复
                                self.deployment_model.update_deployment_status(
                                    deploy_id, 
                                    'planning', 
                                    error_message=f"检测到Terraform规划错误，已自动修复并重试 ({retry_count}/{max_retries})"
                                )
                                deployment_logs['retry_count'] = retry_count
                                self.logger.info(f"开始第{retry_count}次重试部署")
                                continue
                            else:
                                self.logger.warning("无法自动修复Terraform代码")
                        
                        self.logger.error(f"Terraform规划失败: {plan_result.stderr}")
                        
                        # 清理可能已部署的资源(达到最大重试次数时)
                        if retry_count >= max_retries and os.path.exists(os.path.join(deploy_dir, '.terraform')):
                            self.logger.info(f"达到最大重试次数({max_retries})，尝试清理可能存在的资源")
                            try:
                                # 更新状态为清理中
                                self.deployment_model.update_deployment_status(
                                    deploy_id, 
                                    'cleaning', 
                                    error_message=f"达到最大重试次数，正在清理已部署资源"
                                )
                                
                                # 执行terraform destroy
                                destroy_result = subprocess.run(
                                    ['terraform', 'destroy', '-auto-approve'],
                                    cwd=deploy_dir,
                                    capture_output=True,
                                    text=True
                                )
                                
                                if destroy_result.returncode != 0:
                                    self.logger.warning(f"资源清理失败: {destroy_result.stderr}")
                                else:
                                    self.logger.info(f"资源清理成功: {destroy_result.stdout}")
                                
                                # 记录清理结果
                                cleanup_log_path = os.path.join(deploy_dir, 'cleanup_attempts.log')
                                with open(cleanup_log_path, 'a') as cleanup_file:
                                    cleanup_file.write(f"\n\n{'='*80}\n")
                                    cleanup_file.write(f"达到最大重试次数清理 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                    cleanup_file.write(f"{'='*80}\n\n")
                                    cleanup_file.write("清理输出:\n```\n")
                                    cleanup_file.write(destroy_result.stdout)
                                    cleanup_file.write("\n```\n\n")
                                    if destroy_result.stderr:
                                        cleanup_file.write("清理错误:\n```\n")
                                        cleanup_file.write(destroy_result.stderr)
                                        cleanup_file.write("\n```\n\n")
                            except Exception as destroy_error:
                                self.logger.error(f"执行terraform destroy时出错: {str(destroy_error)}")
                                
                        error_msg = f"规划失败: {plan_result.stderr}"
                        deployment_logs['error_message'] = error_msg
                        deployment_logs['status'] = 'failed'
                        create_deployment_summary(is_success=False)
                        self.deployment_model.update_deployment_status(
                            deploy_id, 
                            'failed', 
                            error_message=error_msg
                        )
                        return
                        
                    self.logger.info(f"Terraform规划成功: {plan_result.stdout}")
                except Exception as plan_error:
                    error_msg = f"执行terraform plan时出错: {str(plan_error)}"
                    self.logger.error(error_msg)
                    deployment_logs['error_message'] = error_msg
                    deployment_logs['status'] = 'failed'
                    create_deployment_summary(is_success=False)
                    self.deployment_model.update_deployment_status(
                        deploy_id, 
                        'failed', 
                        error_message=error_msg
                    )
                    return
                
                # 更新部署状态为"applying"
                self.logger.info(f"更新部署状态为applying: {deploy_id}")
                self.deployment_model.update_deployment_status(deploy_id, 'applying')
                
                # 运行terraform apply
                self.logger.info(f"开始应用Terraform配置: {deploy_id}")
                try:
                    apply_result = subprocess.run(
                        ['terraform', 'apply', '-auto-approve', 'tfplan'],
                        cwd=deploy_dir,
                        capture_output=True,
                        text=True
                    )
                    
                    # 记录输出
                    deployment_logs['apply_output'] = apply_result.stdout
                    
                    if apply_result.returncode != 0:
                        deployment_logs['apply_error'] = apply_result.stderr
                        # 记录完整的错误消息到日志，便于诊断
                        self.logger.error(f"Terraform应用失败，完整错误: {apply_result.stderr}")
                        
                        if retry_count < max_retries:
                            self.logger.info(f"尝试修复Terraform应用错误，第{retry_count+1}次尝试")
                            
                            # 先执行terraform destroy清理之前部署的资源
                            self.logger.info(f"执行terraform destroy清理之前的部署资源: {deploy_id}")
                            try:
                                # 更新部署状态，告知用户正在清理资源
                                self.deployment_model.update_deployment_status(
                                    deploy_id, 
                                    'cleaning', 
                                    error_message=f"清理之前部署的资源，准备重新部署"
                                )
                                
                                # 执行terraform destroy
                                destroy_result = subprocess.run(
                                    ['terraform', 'destroy', '-auto-approve'],
                                    cwd=deploy_dir,
                                    capture_output=True,
                                    text=True
                                )
                                
                                if destroy_result.returncode != 0:
                                    self.logger.warning(f"Terraform资源清理失败，可能存在残留资源: {destroy_result.stderr}")
                                else:
                                    self.logger.info(f"Terraform资源清理成功: {destroy_result.stdout}")
                                    
                                # 记录清理结果到日志
                                cleanup_log_path = os.path.join(deploy_dir, 'cleanup_attempts.log')
                                with open(cleanup_log_path, 'a') as cleanup_file:
                                    cleanup_file.write(f"\n\n{'='*80}\n")
                                    cleanup_file.write(f"第{retry_count+1}次清理 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                    cleanup_file.write(f"{'='*80}\n\n")
                                    cleanup_file.write("清理输出:\n```\n")
                                    cleanup_file.write(destroy_result.stdout)
                                    cleanup_file.write("\n```\n\n")
                                    if destroy_result.stderr:
                                        cleanup_file.write("清理错误:\n```\n")
                                        cleanup_file.write(destroy_result.stderr)
                                        cleanup_file.write("\n```\n\n")
                            except Exception as destroy_error:
                                self.logger.error(f"执行terraform destroy时出错: {str(destroy_error)}")
                            
                            # 读取原始Terraform代码
                            with open(tf_file_path, 'r') as f:
                                original_tf = f.read()
                            
                            # 尝试修复代码 - 直接传递完整错误消息
                            fixed_tf = self._fix_terraform_code(original_tf, apply_result.stderr, tf_file_path)
                            if fixed_tf:
                                self.logger.info("成功修复Terraform代码，准备重新部署")
                                # 保存修复后的代码
                                with open(tf_file_path, 'w') as f:
                                    f.write(fixed_tf)
                                
                                # 创建对比日志，记录修改前后的差异
                                diff_log_path = os.path.join(deploy_dir, 'code_diff.log')
                                with open(diff_log_path, 'a') as diff_file:
                                    diff_file.write(f"\n\n{'='*80}\n")
                                    diff_file.write(f"第{retry_count+1}次修复 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                    diff_file.write(f"{'='*80}\n\n")
                                    diff_file.write("修复前:\n```terraform\n")
                                    diff_file.write(original_tf)
                                    diff_file.write("\n```\n\n修复后:\n```terraform\n")
                                    diff_file.write(fixed_tf)
                                    diff_file.write("\n```\n")
                                
                                retry_count += 1
                                # 更新部署状态，告知用户正在修复
                                self.deployment_model.update_deployment_status(
                                    deploy_id, 
                                    'planning', 
                                    error_message=f"检测到Terraform应用错误，已自动修复并重试 ({retry_count}/{max_retries})"
                                )
                                deployment_logs['retry_count'] = retry_count
                                self.logger.info(f"开始第{retry_count}次重试部署")
                                continue
                            else:
                                self.logger.warning("无法自动修复Terraform代码")
                        
                        self.logger.error(f"Terraform应用失败: {apply_result.stderr}")
                        
                        # 清理已部署的资源(达到最大重试次数时)
                        if retry_count >= max_retries and os.path.exists(os.path.join(deploy_dir, '.terraform')):
                            self.logger.info(f"达到最大重试次数({max_retries})，清理已部署资源")
                            try:
                                # 更新状态为清理中
                                self.deployment_model.update_deployment_status(
                                    deploy_id, 
                                    'cleaning', 
                                    error_message=f"达到最大重试次数，正在清理已部署资源"
                                )
                                
                                # 执行terraform destroy
                                destroy_result = subprocess.run(
                                    ['terraform', 'destroy', '-auto-approve'],
                                    cwd=deploy_dir,
                                    capture_output=True,
                                    text=True
                                )
                                
                                if destroy_result.returncode != 0:
                                    self.logger.warning(f"资源清理失败: {destroy_result.stderr}")
                                else:
                                    self.logger.info(f"资源清理成功: {destroy_result.stdout}")
                                
                                # 记录清理结果
                                cleanup_log_path = os.path.join(deploy_dir, 'cleanup_attempts.log')
                                with open(cleanup_log_path, 'a') as cleanup_file:
                                    cleanup_file.write(f"\n\n{'='*80}\n")
                                    cleanup_file.write(f"达到最大重试次数清理 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                                    cleanup_file.write(f"{'='*80}\n\n")
                                    cleanup_file.write("清理输出:\n```\n")
                                    cleanup_file.write(destroy_result.stdout)
                                    cleanup_file.write("\n```\n\n")
                                    if destroy_result.stderr:
                                        cleanup_file.write("清理错误:\n```\n")
                                        cleanup_file.write(destroy_result.stderr)
                                        cleanup_file.write("\n```\n\n")
                            except Exception as destroy_error:
                                self.logger.error(f"执行terraform destroy时出错: {str(destroy_error)}")
                                
                        error_msg = f"应用失败: {apply_result.stderr}"
                        deployment_logs['error_message'] = error_msg
                        deployment_logs['status'] = 'failed'
                        create_deployment_summary(is_success=False)
                        self.deployment_model.update_deployment_status(
                            deploy_id, 
                            'failed', 
                            error_message=error_msg
                        )
                        return
                        
                    self.logger.info(f"Terraform应用成功: {apply_result.stdout}")
                    
                    # 部署成功，跳出重试循环
                    break
                except Exception as apply_error:
                    error_msg = f"执行terraform apply时出错: {str(apply_error)}"
                    self.logger.error(error_msg)
                    deployment_logs['error_message'] = error_msg
                    deployment_logs['status'] = 'failed'
                    create_deployment_summary(is_success=False)
                    self.deployment_model.update_deployment_status(
                        deploy_id, 
                        'failed', 
                        error_message=error_msg
                    )
                    return
            
            # 部署成功，获取输出信息
            try:
                output_result = subprocess.run(
                    ['terraform', 'output', '-json'],
                    cwd=deploy_dir,
                    capture_output=True,
                    text=True
                )
                
                outputs = {}
                if output_result.returncode == 0 and output_result.stdout:
                    try:
                        outputs = json.loads(output_result.stdout)
                        self.logger.info(f"Terraform输出: {outputs}")
                        deployment_logs['outputs'] = outputs
                    except json.JSONDecodeError:
                        self.logger.warning(f"无法解析Terraform输出: {output_result.stdout}")
                
                # 设置最终状态和创建成功摘要
                deployment_logs['status'] = 'completed'
                create_deployment_summary(is_success=True)
                
                # 更新部署状态为"completed"
                deployment_summary = {
                    'outputs': outputs,
                    'apply_output': apply_result.stdout,
                    'completed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'retry_count': retry_count,
                    'auto_fixed': retry_count > 0
                }
                self.logger.info(f"更新部署状态为completed: {deploy_id}")
                self.deployment_model.update_deployment_status(
                    deploy_id, 
                    'completed',
                    deployment_summary=json.dumps(deployment_summary)
                )
                
                self.logger.info(f"Terraform部署成功完成: {deploy_id}")
                if retry_count > 0:
                    self.logger.info(f"部署经过 {retry_count} 次自动修复后成功完成")
            except Exception as output_error:
                error_msg = f"获取Terraform输出时出错: {str(output_error)}"
                self.logger.error(error_msg)
                deployment_logs['error_message'] = error_msg
                deployment_logs['status'] = 'failed'
                create_deployment_summary(is_success=False)
                self.deployment_model.update_deployment_status(
                    deploy_id, 
                    'failed', 
                    error_message=error_msg
                )
                return
            
        except Exception as e:
            self.logger.error(f"Terraform部署过程中出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            # 更新部署状态为"failed"并创建失败摘要
            error_msg = str(e)
            deployment_logs['error_message'] = error_msg
            deployment_logs['status'] = 'failed'
            create_deployment_summary(is_success=False)
            
            self.deployment_model.update_deployment_status(
                deploy_id, 
                'failed', 
                error_message=error_msg
            )
        
        finally:
            # 清理活跃部署记录
            if deploy_id in self.active_deployments:
                del self.active_deployments[deploy_id]
                self.logger.info(f"已清理活跃部署记录: {deploy_id}")
            
            # 清理停止信号文件
            stop_file = os.path.join(deploy_dir, '.stop_deployment')
            if os.path.exists(stop_file):
                try:
                    os.remove(stop_file)
                    self.logger.info(f"已清理停止信号文件: {stop_file}")
                except Exception as e:
                    self.logger.warning(f"清理停止信号文件失败: {str(e)}")
    
    def _fix_terraform_code(self, original_code, error_message, tf_file_path):
        """Fix Terraform code using AI assistance"""
        try:
            self.logger.info("开始修复Terraform代码")
            self.logger.info(f"MCP server状态: {'启用' if self.enable_mcp else '禁用'}")
            
            if self.enable_mcp:
                self.logger.info("优先尝试使用MCP server修复Terraform代码")
                # Try using MCP server first
                fixed_code = self._fix_with_mcp(original_code, error_message)
                if fixed_code:
                    self.logger.info("MCP server成功修复代码，返回修复结果")
                    return fixed_code
                else:
                    self.logger.info("MCP server修复失败，切换到传统AI修复方法")
            else:
                self.logger.info("MCP server已禁用，直接使用传统AI修复方法")
            
            # Fall back to regular AI fix if MCP fails or is disabled
            self.logger.info("开始使用传统AI方法修复Terraform代码")
            return self._fix_terraform_code_legacy(original_code, error_message, tf_file_path)
            
        except Exception as e:
            self.logger.error(f"修复Terraform代码时出错: {str(e)}")
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            return None

    def _fix_with_mcp(self, original_code: str, error_message: str) -> Optional[str]:
        """Attempt to fix Terraform code using MCP server via stdio"""
        try:
            self.logger.info(f"开始使用MCP server修复Terraform代码")
            
            # 检查MCP server容器是否在运行
            try:
                containers = self.docker_client.containers.list()
                mcp_container = None
                for container in containers:
                    if container.name == "terraform-mcp-server":
                        mcp_container = container
                        break
                
                if not mcp_container:
                    self.logger.error("MCP server容器未运行")
                    return None
                
                self.logger.info(f"找到运行中的MCP server容器: {mcp_container.id}")
                
                # 记录发送到MCP server的请求内容
                self.logger.info(f"发送到MCP server的请求数据:")
                self.logger.info(f"- 原始代码长度: {len(original_code)} 字符")
                self.logger.info(f"- 错误信息: {error_message[:200]}{'...' if len(error_message) > 200 else ''}")
                
                # 构建MCP请求（JSON-RPC格式）
                import json
                mcp_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "fix_terraform",
                        "arguments": {
                            "code": original_code,
                            "error": error_message
                        }
                    }
                }
                
                # 通过容器的 stdin 发送请求
                request_str = json.dumps(mcp_request) + "\n"
                self.logger.info(f"向MCP server发送JSON-RPC请求")
                
                # 执行命令与MCP server交互
                exec_result = mcp_container.exec_run(
                    cmd=["sh", "-c", f"echo '{request_str}' | cat"],
                    stdin=True,
                    stdout=True,
                    stderr=True
                )
                
                self.logger.info(f"MCP server执行结果退出码: {exec_result.exit_code}")
                
                if exec_result.exit_code == 0:
                    output = exec_result.output.decode('utf-8') if exec_result.output else ""
                    self.logger.info(f"MCP server响应: {output[:500]}{'...' if len(output) > 500 else ''}")
                    
                    # 尝试解析JSON响应
                    try:
                        response_data = json.loads(output.strip())
                        if response_data.get("result"):
                            fixed_code = response_data["result"].get("fixed_code", "")
                            if fixed_code:
                                self.logger.info(f"MCP server成功修复代码，修复后代码长度: {len(fixed_code)} 字符")
                                return fixed_code
                    except json.JSONDecodeError as json_error:
                        self.logger.error(f"解析MCP server响应JSON失败: {str(json_error)}")
                else:
                    self.logger.error(f"MCP server执行失败，退出码: {exec_result.exit_code}")
                    if exec_result.output:
                        self.logger.error(f"错误输出: {exec_result.output.decode('utf-8')}")
                
            except Exception as container_error:
                self.logger.error(f"与MCP server容器交互时出错: {str(container_error)}")
            
            self.logger.warning("MCP server无法修复代码，回退到传统AI修复方法")
            return None
            
        except Exception as e:
            self.logger.error(f"使用MCP server时发生未预期错误: {str(e)}")
            self.logger.error(f"错误详情: {traceback.format_exc()}")
            return None
    
    def _fix_terraform_code_legacy(self, original_code, error_message, tf_file_path):
        """根据配置的AI提供商修复Terraform代码"""
        try:
            # 创建修复日志文件路径
            deploy_id = os.path.basename(os.path.dirname(tf_file_path))
            fix_log_path = os.path.join(os.path.dirname(tf_file_path), 'fix.log')
            
            # 确定AI提供商
            ai_provider = 'openai'  # 默认值
            if self.config:
                ai_provider = getattr(self.config, 'ai_model_provider', 'openai').lower()
            else:
                ai_provider = os.environ.get('AI_MODEL_PROVIDER', 'openai').lower()
            
            self.logger.info(f"使用AI提供商修复Terraform代码: {ai_provider}")
            
            # 根据AI提供商获取相应的配置
            if ai_provider == 'anthropic':
                # Anthropic配置
                api_key = None
                if self.config:
                    api_key = getattr(self.config, 'anthropic_api_key', '')
                if not api_key:
                    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
                
                api_base_url = None
                if self.config:
                    api_base_url = getattr(self.config, 'anthropic_api_base_url', 'https://api.anthropic.com/v1')
                if not api_base_url:
                    api_base_url = os.environ.get('ANTHROPIC_API_BASE_URL', 'https://api.anthropic.com/v1')
                
                model_name = None
                if self.config:
                    model_name = getattr(self.config, 'anthropic_api_model', 'claude-3-5-sonnet-20241022')
                if not model_name:
                    model_name = os.environ.get('ANTHROPIC_API_MODEL', 'claude-3-5-sonnet-20241022')
                
                if not api_key:
                    self.logger.error("未配置Anthropic API密钥，无法修复Terraform代码")
                    with open(fix_log_path, 'a') as log_file:
                        log_file.write("未配置Anthropic API密钥，无法修复Terraform代码\n")
                    return None
            else:
                # OpenAI配置（默认）
                api_key = None
                if hasattr(self, 'openai_api_key'):
                    api_key = self.openai_api_key
                elif self.config:
                    api_key = getattr(self.config, 'openai_api_key', '')
                
                if not api_key:
                    api_key = os.environ.get('OPENAI_API_KEY', '')
                    
                api_base_url = None
                if hasattr(self, 'openai_api_base_url'):
                    api_base_url = self.openai_api_base_url
                elif self.config:
                    api_base_url = getattr(self.config, 'openai_api_base_url', 'https://api.openai.com/v1')
                
                if not api_base_url:
                    api_base_url = os.environ.get('OPENAI_API_BASE_URL', 'https://api.openai.com/v1')
                
                model_name = None
                if hasattr(self, 'openai_api_model'):
                    model_name = self.openai_api_model
                elif self.config:
                    model_name = getattr(self.config, 'openai_api_model', 'gpt-4o')
                
                if not model_name:
                    model_name = os.environ.get('OPENAI_API_MODEL', 'gpt-4o')
                
                if not api_key:
                    self.logger.error("未配置OpenAI API密钥，无法修复Terraform代码")
                    with open(fix_log_path, 'a') as log_file:
                        log_file.write("未配置OpenAI API密钥，无法修复Terraform代码\n")
                    return None
                
            # 记录使用的API设置
            self.logger.info(f"使用API Base URL: {api_base_url}")
            self.logger.info(f"使用模型: {model_name}")
            
            # 根据AI提供商初始化客户端
            client = None
            if ai_provider == 'anthropic':
                import anthropic
                client = anthropic.Anthropic(
                    api_key=api_key,
                    base_url=api_base_url
                )
            else:
                import openai
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url=api_base_url
                )
            
            # 提取所有包含"Error:"的错误信息
            error_lines = []
            lines = error_message.split('\n')
            for i, line in enumerate(lines):
                if 'Error:' in line:
                    # 收集这一行以及后面的6行作为上下文
                    error_block = [line.strip()]
                    for j in range(1, 7):
                        if i + j < len(lines) and lines[i + j].strip():
                            error_block.append(lines[i + j].strip())
                    
                    error_lines.append('\n'.join(error_block))
            
            if not error_lines:
                self.logger.warning("未找到包含Error:的错误信息，无法修复")
                with open(fix_log_path, 'a') as log_file:
                    log_file.write("未找到Error:开头的错误信息，尝试使用完整错误消息\n")
                # 如果没有找到特定格式的错误，使用完整的错误消息
                error_lines = [error_message]
            
            # 检查是否为火山引擎代码
            is_volcengine = "volcengine" in original_code.lower() or "火山" in original_code
            
            # 构建修复提示
            fix_prompt = self._build_fix_prompt(original_code, error_lines, is_volcengine)
            
            # 记录提示到日志
            with open(fix_log_path, 'a') as log_file:
                log_file.write("提交给AI的错误信息:\n")
                log_file.write('\n\n'.join(error_lines))
                log_file.write("\n\n")
            
            # 根据AI提供商调用相应的API
            if ai_provider == 'anthropic':
                # 调用Anthropic API
                response = client.messages.create(
                    model=model_name,
                    max_tokens=4000,
                    temperature=0.7,
                    system=fix_prompt['system'],
                    messages=[
                        {"role": "user", "content": fix_prompt['user']}
                    ]
                )
                # 提取修复后的代码
                fixed_code = response.content[0].text
            else:
                # 调用OpenAI API
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": fix_prompt['system']},
                        {"role": "user", "content": fix_prompt['user']}
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                # 提取修复后的代码
                fixed_code = response.choices[0].message.content
            
            # 提取修复后的代码（移除可能的代码块标记）
            fixed_code = self._clean_terraform_code(fixed_code)
            
            # 记录修复后的代码到日志
            with open(fix_log_path, 'a') as log_file:
                log_file.write("AI修复后的代码:\n")
                log_file.write(fixed_code)
                log_file.write("\n\n")
                
            # 保留原始凭证
            fixed_code = self._preserve_credentials(original_code, fixed_code, is_volcengine, fix_log_path)
            
            return fixed_code
            
        except Exception as e:
            self.logger.error(f"修复Terraform代码时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            with open(fix_log_path, 'a') as log_file:
                log_file.write(f"修复过程中发生错误: {str(e)}\n")
                log_file.write(traceback.format_exc())
                log_file.write("\n")
            return None
    
    def get_deployment_status(self, deploy_id):
        """获取部署状态"""
        try:
            if not deploy_id:
                return jsonify({"success": False, "message": "部署ID为空"}), 400
                
            deployment = self.deployment_model.get_deployment(deploy_id)
            if not deployment:
                return jsonify({"success": False, "message": "未找到部署信息"}), 404
                
            return jsonify({
                "success": True,
                "deployment": deployment
            })
            
        except Exception as e:
            self.logger.error(f"获取部署状态时出错: {str(e)}")
            return jsonify({
                "success": False,
                "error": "获取部署状态时出错",
                "message": str(e)
            }), 500
    
    def deploy_terraform_init(self):
        """初始化大型Terraform部署（分批上传代码）"""
        try:
            # 获取请求数据
            self.logger.info("开始处理分批Terraform部署初始化请求")
            data = request.get_json()
            if not data:
                self.logger.error("请求数据为空")
                return jsonify({"success": False, "message": "请求数据为空"}), 400
            
            terraform_code_part = data.get('terraform_code_part', '')
            if not terraform_code_part:
                self.logger.error("Terraform代码片段为空")
                return jsonify({"success": False, "message": "Terraform代码片段为空"}), 400
                
            # 获取必要参数
            is_multipart = data.get('is_multipart', False)
            total_parts = data.get('total_parts', 1)
            part_index = data.get('part_index', 0)
            
            # 验证这是第一个片段
            if part_index != 0:
                self.logger.error("初始化请求必须是第一个片段")
                return jsonify({"success": False, "message": "初始化请求必须是第一个片段"}), 400
                
            # 获取API密钥ID
            api_key_id = data.get('api_key_id')
            if not api_key_id:
                self.logger.error("未提供API密钥ID")
                return jsonify({"success": False, "message": "请选择API密钥"}), 400
                
            # 获取描述和部署名称
            description = data.get('description', '通过AI生成的部署')
            deploy_name = data.get('deploy_name', '')
            
            # 获取项目和云平台信息
            project_id = data.get('project_id', 0)
            project_name = data.get('project_name', '未命名项目')
            cloud_id = data.get('cloud_id', 0)
            cloud_name = data.get('cloud_name', '未知云平台')
            
            self.logger.info(f"分批部署初始化: 部署名称: {deploy_name}, 描述长度: {len(description)}, 总分片: {total_parts}")
            self.logger.info(f"分批部署接收到的项目和云平台信息: project_id={project_id}, project_name='{project_name}', cloud_id={cloud_id}, cloud_name='{cloud_name}'")
            
            # 获取当前用户信息
            try:
                current_user = get_current_user(request)
                if not current_user:
                    self.logger.error("未找到用户信息")
                    return jsonify({"success": False, "message": "未找到用户信息"}), 401
                    
                user_id = current_user.get('user_id')
                username = current_user.get('username')
                self.logger.info(f"用户ID: {user_id}, 用户名: {username}")
            except Exception as user_error:
                self.logger.error(f"获取用户信息出错: {str(user_error)}")
                return jsonify({"success": False, "message": f"获取用户信息出错: {str(user_error)}"}), 500
            
            # 生成唯一的部署ID
            deploy_id = f"AIDP{uuid.uuid4().hex[:19]}".upper()
            self.logger.info(f"生成部署ID: {deploy_id}")
            
            # 创建部署目录
            try:
                deploy_dir = os.path.join(self.deployments_dir, deploy_id)
                self.logger.info(f"创建部署目录: {deploy_dir}")
                os.makedirs(deploy_dir, exist_ok=True)
                
                # 创建临时代码片段存储目录
                parts_dir = os.path.join(deploy_dir, 'parts')
                os.makedirs(parts_dir, exist_ok=True)
                
                # 保存第一个代码片段
                part_file_path = os.path.join(parts_dir, f"part_{part_index:03d}.tf")
                with open(part_file_path, 'w') as f:
                    f.write(terraform_code_part)
            except Exception as dir_error:
                self.logger.error(f"创建部署目录时出错: {str(dir_error)}")
                return jsonify({"success": False, "message": f"创建部署目录时出错: {str(dir_error)}"}), 500
            
            # 创建部署记录，但标记为draft状态
            try:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                deployment_data = {
                    'id': deploy_id,
                    'user_id': user_id,
                    'username': username,
                    'name': deploy_name or description[:50],
                    'description': description,
                    'project': project_name,
                    'cloud': cloud_name,
                    'status': 'draft',  # 使用draft状态表示正在上传中
                    'created_at': current_time,
                    'updated_at': current_time,
                    'terraform_code': terraform_code_part  # 暂时只保存第一部分
                }
                
                # 保存部署记录到数据库
                self.logger.info(f"保存部署草稿记录到数据库: deploy_id={deploy_id}, project='{project_name}', cloud='{cloud_name}'")
                success = self.deployment_model.create_deployment(deployment_data)
                if not success:
                    self.logger.error("保存部署记录失败")
                    return jsonify({"success": False, "message": "保存部署记录失败"}), 500
                    
                # 创建部署信息文件，记录总分片数和当前进度
                info_file_path = os.path.join(deploy_dir, 'deploy_info.json')
                info_data = {
                    'deploy_id': deploy_id,
                    'total_parts': total_parts,
                    'received_parts': 1,
                    'api_key_id': api_key_id,
                    'status': 'uploading'
                }
                with open(info_file_path, 'w') as f:
                    json.dump(info_data, f)
                
                return jsonify({
                    "success": True,
                    "message": "部署初始化成功",
                    "deploy_id": deploy_id
                })
            except Exception as db_error:
                self.logger.error(f"保存部署记录到数据库时出错: {str(db_error)}")
                return jsonify({"success": False, "message": f"保存部署记录到数据库时出错: {str(db_error)}"}), 500
            
        except Exception as e:
            self.logger.error(f"初始化Terraform部署时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": "初始化部署时出错",
                "message": str(e)
            }), 500
    
    def deploy_terraform_part(self):
        """接收Terraform部署代码片段"""
        try:
            # 获取请求数据
            self.logger.info("开始处理Terraform代码片段上传请求")
            data = request.get_json()
            if not data:
                self.logger.error("请求数据为空")
                return jsonify({"success": False, "message": "请求数据为空"}), 400
            
            # 获取必要参数
            deploy_id = data.get('deploy_id')
            if not deploy_id:
                self.logger.error("未提供部署ID")
                return jsonify({"success": False, "message": "未提供部署ID"}), 400
                
            terraform_code_part = data.get('terraform_code_part', '')
            if not terraform_code_part:
                self.logger.error("Terraform代码片段为空")
                return jsonify({"success": False, "message": "Terraform代码片段为空"}), 400
                
            part_index = data.get('part_index', 0)
            
            # 验证部署存在
            deploy_dir = os.path.join(self.deployments_dir, deploy_id)
            if not os.path.exists(deploy_dir):
                self.logger.error(f"部署目录不存在: {deploy_dir}")
                return jsonify({"success": False, "message": f"部署不存在: {deploy_id}"}), 404
                
            # 检查部署信息文件
            info_file_path = os.path.join(deploy_dir, 'deploy_info.json')
            if not os.path.exists(info_file_path):
                self.logger.error(f"部署信息文件不存在: {info_file_path}")
                return jsonify({"success": False, "message": f"部署信息不存在: {deploy_id}"}), 404
                
            # 读取部署信息
            with open(info_file_path, 'r') as f:
                info_data = json.load(f)
                
            # 验证部署状态
            if info_data.get('status') != 'uploading':
                self.logger.error(f"部署状态不正确: {info_data.get('status')}")
                return jsonify({"success": False, "message": f"部署状态不正确: {info_data.get('status')}"}), 400
                
            # 保存代码片段
            parts_dir = os.path.join(deploy_dir, 'parts')
            part_file_path = os.path.join(parts_dir, f"part_{part_index:03d}.tf")
            with open(part_file_path, 'w') as f:
                f.write(terraform_code_part)
                
            # 更新部署信息
            info_data['received_parts'] += 1
            with open(info_file_path, 'w') as f:
                json.dump(info_data, f)
                
            self.logger.info(f"成功接收代码片段: {deploy_id}, 片段索引: {part_index}, 已接收: {info_data['received_parts']}/{info_data['total_parts']}")
                
            return jsonify({
                "success": True,
                "message": f"成功接收代码片段: {part_index}",
                "deploy_id": deploy_id,
                "received_parts": info_data['received_parts'],
                "total_parts": info_data['total_parts']
            })
            
        except Exception as e:
            self.logger.error(f"接收Terraform代码片段时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": "接收代码片段时出错",
                "message": str(e)
            }), 500
    
    def deploy_terraform_complete(self):
        """完成Terraform部署代码上传并开始部署"""
        try:
            # 获取请求数据
            self.logger.info("开始处理Terraform部署完成请求")
            data = request.get_json()
            if not data:
                self.logger.error("请求数据为空")
                return jsonify({"success": False, "message": "请求数据为空"}), 400
            
            # 获取部署ID
            deploy_id = data.get('deploy_id')
            if not deploy_id:
                self.logger.error("未提供部署ID")
                return jsonify({"success": False, "message": "未提供部署ID"}), 400
                
            # 验证部署存在
            deploy_dir = os.path.join(self.deployments_dir, deploy_id)
            if not os.path.exists(deploy_dir):
                self.logger.error(f"部署目录不存在: {deploy_dir}")
                return jsonify({"success": False, "message": f"部署不存在: {deploy_id}"}), 404
                
            # 检查部署信息文件
            info_file_path = os.path.join(deploy_dir, 'deploy_info.json')
            if not os.path.exists(info_file_path):
                self.logger.error(f"部署信息文件不存在: {info_file_path}")
                return jsonify({"success": False, "message": f"部署信息不存在: {deploy_id}"}), 404
                
            # 读取部署信息
            with open(info_file_path, 'r') as f:
                info_data = json.load(f)
                
            # 验证部署状态
            if info_data.get('status') != 'uploading':
                self.logger.error(f"部署状态不正确: {info_data.get('status')}")
                return jsonify({"success": False, "message": f"部署状态不正确: {info_data.get('status')}"}), 400
                
            # 验证所有片段是否都已接收
            if info_data.get('received_parts', 0) < info_data.get('total_parts', 0):
                self.logger.error(f"尚未接收所有代码片段: {info_data.get('received_parts')}/{info_data.get('total_parts')}")
                return jsonify({
                    "success": False, 
                    "message": f"尚未接收所有代码片段: {info_data.get('received_parts')}/{info_data.get('total_parts')}"
                }), 400
                
            # 合并所有代码片段
            parts_dir = os.path.join(deploy_dir, 'parts')
            terraform_code = ""
            for i in range(info_data.get('total_parts', 0)):
                part_file_path = os.path.join(parts_dir, f"part_{i:03d}.tf")
                if not os.path.exists(part_file_path):
                    self.logger.error(f"找不到代码片段文件: {part_file_path}")
                    return jsonify({"success": False, "message": f"找不到代码片段: {i}"}), 404
                    
                with open(part_file_path, 'r') as f:
                    terraform_code += f.read()
            
            # 获取API密钥ID
            api_key_id = info_data.get('api_key_id')
            if not api_key_id:
                self.logger.error("未找到API密钥ID")
                return jsonify({"success": False, "message": "未找到API密钥ID"}), 400
                
            # 获取API密钥详情
            try:
                from controllers.apikey_controller import ApiKeyController
                apikey_controller = ApiKeyController(self.config)
                api_key = apikey_controller.get_api_key_by_id(api_key_id)
                
                if not api_key:
                    self.logger.error(f"找不到指定的API密钥: {api_key_id}")
                    return jsonify({"success": False, "message": "找不到指定的API密钥"}), 404
                    
                # 获取AK和SK
                ak = api_key.get('ak', '')
                sk = api_key.get('sk', '')
                
                if not ak or not sk:
                    self.logger.error("API密钥缺少AK或SK")
                    return jsonify({"success": False, "message": "API密钥缺少AK或SK"}), 400
                    
                self.logger.info(f"成功获取API密钥 {api_key.get('apikey_name')}")
            except Exception as apikey_error:
                self.logger.error(f"获取API密钥时出错: {str(apikey_error)}")
                return jsonify({"success": False, "message": f"获取API密钥时出错: {str(apikey_error)}"}), 500
            
            # 修改Terraform代码，智能添加云平台凭证
            try:
                # 根据代码中的云平台类型智能添加凭证
                terraform_code = self._add_cloud_credentials_to_code(terraform_code, ak, sk)
            except Exception as code_error:
                self.logger.error(f"添加云平台凭证到Terraform代码时出错: {str(code_error)}")
                return jsonify({"success": False, "message": f"添加云平台凭证到Terraform代码时出错: {str(code_error)}"}), 500
            
            # 写入完整的Terraform代码到main.tf文件
            tf_file_path = os.path.join(deploy_dir, 'main.tf')
            with open(tf_file_path, 'w') as f:
                f.write(terraform_code)
                
            # 更新部署信息
            info_data['status'] = 'ready'
            with open(info_file_path, 'w') as f:
                json.dump(info_data, f)
                
            # 更新部署记录
            try:
                self.deployment_model.update_deployment_status(
                    deploy_id, 
                    'pending',
                    error_message=None,
                    deployment_summary=None
                )
                
                # 更新Terraform代码
                self.logger.info(f"更新部署记录的Terraform代码: {deploy_id}")
                deployment = self.deployment_model.get_deployment(deploy_id)
                if deployment:
                    conn = get_db()
                    cursor = conn.cursor()
                    cursor.execute(
                        f"UPDATE aideployments SET terraform_code = %s WHERE id = %s",
                        (terraform_code, deploy_id)
                    )
                    conn.commit()
                    cursor.close()
                    conn.close()
            except Exception as update_error:
                self.logger.error(f"更新部署记录时出错: {str(update_error)}")
                return jsonify({"success": False, "message": f"更新部署记录时出错: {str(update_error)}"}), 500
            
            # 启动异步部署任务
            try:
                # 获取当前用户信息
                current_user = get_current_user(request)
                user_id = current_user.get('user_id') if current_user else None
                
                # 启动后台部署任务
                self.logger.info(f"启动后台部署任务: {deploy_id}")
                import threading
                deploy_thread = threading.Thread(
                    target=self._run_terraform_deployment,
                    args=(deploy_id, deploy_dir, user_id)
                )
                deploy_thread.daemon = True
                deploy_thread.start()
                
                return jsonify({
                    "success": True,
                    "message": "部署任务已启动",
                    "deploy_id": deploy_id
                })
            except Exception as thread_error:
                self.logger.error(f"启动后台部署任务时出错: {str(thread_error)}")
                return jsonify({"success": False, "message": f"启动后台部署任务时出错: {str(thread_error)}"}), 500
            
        except Exception as e:
            self.logger.error(f"完成Terraform部署时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": "完成部署时出错",
                "message": str(e)
            }), 500
    
    def list_deployments(self):
        """列出用户的AI部署"""
        try:
            # 获取当前用户信息
            current_user = get_current_user(request)
            if not current_user:
                return jsonify({"success": False, "message": "未找到用户信息"}), 401
                
            user_id = current_user.get('user_id')
            
            # 获取分页参数
            page = request.args.get('page', 1, type=int)
            page_size = request.args.get('page_size', 10, type=int)
            
            # 获取部署列表
            deployments, total = self.deployment_model.list_deployments(
                user_id=user_id,
                page=page,
                page_size=page_size
            )
            
            return jsonify({
                "success": True,
                "deployments": deployments,
                "total": total,
                "page": page,
                "page_size": page_size
            })
            
        except Exception as e:
            self.logger.error(f"获取部署列表时出错: {str(e)}")
            return jsonify({
                "success": False,
                "error": "获取部署列表时出错",
                "message": str(e)
            }), 500 
    
    def get_ai_deployment_details(self, deploy_id=None):
        """获取AI部署的详情，包括拓扑图信息"""
        try:
            # 如果未提供deploy_id，则从请求参数中获取
            if not deploy_id:
                deploy_id = request.args.get('deploy_id')
            
            if not deploy_id:
                return jsonify({"success": False, "message": "未提供部署ID"}), 400
            
            # 获取部署详情
            deployment = self.deployment_model.get_deployment(deploy_id)
            if not deployment:
                return jsonify({"success": False, "message": "未找到部署信息"}), 404
            
            # 获取拓扑图路径（只用于检查是否存在）
            deploy_dir = os.path.join(self.deployments_dir, deploy_id)
            topology_image_path = os.path.join(deploy_dir, 'graph.png')
            topology_exists = os.path.exists(topology_image_path)
            
            # 如果拓扑图不存在且部署已完成，尝试生成拓扑图
            if not topology_exists and deployment.get('status') == 'completed':
                try:
                    # 确保在部署目录中执行命令
                    if os.path.exists(deploy_dir):
                        # 尝试生成拓扑图
                        result = subprocess.run(
                            'terraform graph -type=plan | dot -Tpng > graph.png',
                            shell=True,
                            cwd=deploy_dir,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            text=True
                        )
                        
                        if result.returncode == 0:
                            topology_exists = os.path.exists(topology_image_path)
                            self.logger.info(f"已为部署 {deploy_id} 生成拓扑图")
                        else:
                            self.logger.warning(f"无法生成拓扑图: {result.stderr}")
                except Exception as gen_error:
                    self.logger.error(f"生成拓扑图时出错: {str(gen_error)}")
            
            # 构建资源文件列表 - 这里仍需要构建用于返回API，但不会在HTML中显示
            files = []
            if os.path.exists(deploy_dir):
                # 仅列出重要的文件类型
                for file in os.listdir(deploy_dir):
                    if file.endswith(".tf") or file.endswith(".log") or file == "graph.png":
                        file_path = os.path.join(deploy_dir, file)
                        if os.path.isfile(file_path):
                            file_size = os.path.getsize(file_path)
                            files.append({
                                "name": file,
                                "path": f"/api/terraform/file?deploy_id={deploy_id}&file={file}",
                                "size": file_size,
                                "type": file.split('.')[-1]
                            })
            
            # 生成部署摘要HTML表格
            table_html = "<div class='deployment-summary card shadow-sm'>\n"
            table_html += f"<div class='card-header bg-primary text-white'><h3 class='mb-0'><i class='fas fa-brain mr-2'></i>AI部署详情: {deploy_id}</h3></div>\n"
            
            # 基本信息
            table_html += "<div class='card-body'>\n"
            table_html += "<table class='table table-striped table-bordered table-hover'>\n"
            table_html += "<tbody>\n"
            table_html += "<tr><th colspan='2' class='bg-light'>基本信息</th></tr>\n"
            table_html += f"<tr><th width='30%'>部署ID</th><td><code>{deployment.get('id', '')}</code></td></tr>\n"
            table_html += f"<tr><th>名称</th><td><strong>{deployment.get('name', '')}</strong></td></tr>\n"
            table_html += f"<tr><th>创建时间</th><td>{deployment.get('created_at', '')}</td></tr>\n"
            table_html += f"<tr><th>更新时间</th><td>{deployment.get('updated_at', '')}</td></tr>\n"
            
            # 显示状态并根据状态添加不同的样式
            status = deployment.get('status', '')
            status_badge = self._get_status_badge(status)
            table_html += f"<tr><th>状态</th><td>{status_badge}</td></tr>\n"
            
            # 如果有错误信息
            if deployment.get('error_message'):
                table_html += f"<tr><th>错误信息</th><td class='text-danger'><i class='fas fa-exclamation-circle mr-1'></i>{deployment.get('error_message', '')}</td></tr>\n"
            
            table_html += "</tbody>\n"
            table_html += "</table>\n"
            
            # 如果有部署摘要
            if deployment.get('deployment_summary'):
                table_html += "<h4 class='mt-4 mb-2'><i class='fas fa-list-alt mr-2'></i>部署摘要</h4>\n"
                
                summary = deployment.get('deployment_summary')
                if isinstance(summary, dict):
                    # 使用可折叠面板显示复杂的JSON输出
                    formatted_summary = self._format_json_output(summary)
                    table_html += formatted_summary
                else:
                    # 如果是字符串，尝试解析为JSON
                    try:
                        summary_dict = json.loads(summary)
                        formatted_summary = self._format_json_output(summary_dict)
                        table_html += formatted_summary
                    except:
                        # 如果解析失败，作为普通文本显示
                        table_html += "<div class='alert alert-info'>\n"
                        table_html += f"<p>{summary}</p>\n"
                        table_html += "</div>\n"
            
            # 移除文件列表和拓扑图显示部分
            
            table_html += "</div>\n"
            table_html += "</div>"
            
            return jsonify({
                "success": True,
                "deployment": deployment,
                "topology_exists": topology_exists,
                "topology_url": f"/api/terraform/topology?deploy_id={deploy_id}" if topology_exists else None,
                "files": files,
                "table": table_html
            })
            
        except Exception as e:
            self.logger.error(f"获取AI部署详情时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "error": "获取部署详情时出错",
                "message": str(e)
            }), 500
    
    def get_ai_deployment_file(self):
        """获取AI部署相关的文件内容"""
        try:
            # 从请求参数中获取部署ID和文件名
            deploy_id = request.args.get('deploy_id')
            file_name = request.args.get('file')
            
            if not deploy_id or not file_name:
                return jsonify({"success": False, "message": "未提供部署ID或文件名"}), 400
            
            # 构建文件路径
            deploy_dir = os.path.join(self.deployments_dir, deploy_id)
            file_path = os.path.join(deploy_dir, file_name)
            
            # 检查文件是否存在
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                return jsonify({"success": False, "message": "文件不存在"}), 404
            
            # 确定MIME类型
            mime_type = self._get_mime_type(file_path)
            
            # 直接返回文件，不管是什么类型
            return send_file(
                file_path,
                mimetype=mime_type,
                as_attachment=True,
                download_name=file_name
            )
                
        except Exception as e:
            self.logger.error(f"获取AI部署文件时出错: {str(e)}")
            return jsonify({
                "success": False,
                "error": "获取文件内容时出错",
                "message": str(e)
            }), 500
    
    def get_ai_deployment_topology(self):
        """获取AI部署的拓扑图"""
        try:
            # 从请求参数中获取部署ID
            deploy_id = request.args.get('deploy_id')
            
            if not deploy_id:
                return jsonify({"success": False, "message": "未提供部署ID"}), 400
            
            # 构建拓扑图文件路径
            deploy_dir = os.path.join(self.deployments_dir, deploy_id)
            topology_path = os.path.join(deploy_dir, 'graph.png')
            
            # 检查拓扑图是否存在
            if not os.path.exists(topology_path):
                # 尝试生成拓扑图
                try:
                    # 确保在部署目录中执行命令
                    if os.path.exists(deploy_dir):
                        # 尝试生成拓扑图
                        result = subprocess.run(
                            'terraform graph -type=plan | dot -Tpng > graph.png',
                            shell=True,
                            cwd=deploy_dir,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            text=True
                        )
                        
                        if result.returncode == 0 and os.path.exists(topology_path):
                            self.logger.info(f"已为部署 {deploy_id} 生成拓扑图")
                        else:
                            return jsonify({"success": False, "message": f"无法生成拓扑图: {result.stderr}"}), 404
                except Exception as gen_error:
                    return jsonify({"success": False, "message": f"生成拓扑图时出错: {str(gen_error)}"}), 500
            
            # 返回拓扑图文件
            return send_file(
                topology_path,
                mimetype='image/png',
                as_attachment=False,
                download_name=f"topology_{deploy_id}.png"
            )
                
        except Exception as e:
            self.logger.error(f"获取AI部署拓扑图时出错: {str(e)}")
            return jsonify({
                "success": False,
                "error": "获取拓扑图时出错",
                "message": str(e)
            }), 500
    
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
            
    def _format_json_output(self, json_data):
        """将JSON数据格式化为表格形式而不是代码块"""
        html = ""
        
        # 如果是字典类型的输出
        if isinstance(json_data, dict):
            # 检查是否有outputs字段，这需要特殊处理
            if 'outputs' in json_data and isinstance(json_data['outputs'], dict):
                html += "<div class='card mb-3'>\n"
                html += "<div class='card-header bg-light font-weight-bold'>资源输出变量</div>\n"
                html += "<div class='card-body p-0'>\n"
                html += "<table class='table table-sm table-striped mb-0'>\n"
                html += "<thead class='thead-light'>\n"
                html += "<tr><th>输出名称</th><th>值</th></tr>\n"
                html += "</thead>\n"
                html += "<tbody>\n"
                
                for key, value in json_data['outputs'].items():
                    output_value = value.get('value', '') if isinstance(value, dict) else value
                    # 如果输出值是复杂对象，转换为表格而非JSON代码
                    if isinstance(output_value, dict):
                        output_formatted = self._format_dict_as_table(output_value)
                    elif isinstance(output_value, list):
                        output_formatted = self._format_list_as_table(output_value)
                    else:
                        output_formatted = f"<code>{output_value}</code>"
                    
                    html += f"<tr><td><strong>{key}</strong></td><td>{output_formatted}</td></tr>\n"
                
                html += "</tbody>\n"
                html += "</table>\n"
                html += "</div>\n"
                html += "</div>\n"
                
                # 从字典中移除已处理的outputs
                json_data = {k: v for k, v in json_data.items() if k != 'outputs'}
            
            # 处理其他字段，排除过长的apply_output
            other_fields = {k: v for k, v in json_data.items() if k not in ['apply_output']}
            
            if other_fields:
                # 创建表格显示其他简单字段
                for key, value in other_fields.items():
                    # 排除空值和复杂对象
                    if value is None:
                        continue
                        
                    html += f"<div class='card mb-3'>\n"
                    html += f"<div class='card-header bg-light font-weight-bold'>{key}</div>\n"
                    html += f"<div class='card-body p-0'>\n"
                    
                    if isinstance(value, dict):
                        html += self._format_dict_as_table(value)
                    elif isinstance(value, list):
                        html += self._format_list_as_table(value)
                    else:
                        html += f"<div class='p-3'>{value}</div>\n"
                    
                    html += f"</div>\n"
                    html += f"</div>\n"
        
        # 如果是列表类型的输出
        elif isinstance(json_data, list):
            html += "<div class='card mb-3'>\n"
            html += "<div class='card-header bg-light font-weight-bold'>数据列表</div>\n"
            html += "<div class='card-body p-0'>\n"
            html += self._format_list_as_table(json_data)
            html += "</div>\n"
            html += "</div>\n"
        
        # 如果是其他类型（字符串、数字等）
        else:
            html += "<div class='card mb-3'>\n"
            html += "<div class='card-header bg-light font-weight-bold'>值</div>\n"
            html += "<div class='card-body'>\n"
            html += f"<div>{json_data}</div>\n"
            html += "</div>\n"
            html += "</div>\n"
        
        return html
    
    def _format_dict_as_table(self, data):
        """将字典格式化为HTML表格"""
        html = "<table class='table table-sm table-striped mb-0'>\n"
        html += "<tbody>\n"
        
        for key, value in data.items():
            if isinstance(value, dict):
                # 简化嵌套字典显示
                nested_table = "<table class='table table-sm table-bordered mb-0'>\n<tbody>\n"
                for k, v in value.items():
                    if isinstance(v, (dict, list)):
                        v_text = "复杂对象" 
                    else:
                        v_text = str(v)
                    nested_table += f"<tr><td><small>{k}</small></td><td><small>{v_text}</small></td></tr>\n"
                nested_table += "</tbody>\n</table>"
                html += f"<tr><td width='30%'><strong>{key}</strong></td><td>{nested_table}</td></tr>\n"
            elif isinstance(value, list):
                if len(value) > 0 and isinstance(value[0], dict):
                    # 简化列表显示
                    html += f"<tr><td width='30%'><strong>{key}</strong></td><td>列表包含 {len(value)} 项</td></tr>\n"
                else:
                    # 简单列表值显示
                    list_text = ", ".join([str(item) for item in value[:5]])
                    if len(value) > 5:
                        list_text += "..."
                    html += f"<tr><td width='30%'><strong>{key}</strong></td><td>{list_text}</td></tr>\n"
            else:
                # 简单值直接显示
                html += f"<tr><td width='30%'><strong>{key}</strong></td><td>{value}</td></tr>\n"
                
        html += "</tbody>\n"
        html += "</table>\n"
        return html
    
    def _format_list_as_table(self, data):
        """将列表格式化为HTML表格"""
        if not data:
            return "<div class='p-3'>空列表</div>"
            
        # 检查列表项是否为字典
        if all(isinstance(item, dict) for item in data):
            # 使用字典的键作为列头
            all_keys = set()
            for item in data:
                all_keys.update(item.keys())
            all_keys = sorted(list(all_keys))
            
            html = "<table class='table table-sm table-striped mb-0'>\n"
            html += "<thead class='thead-light'>\n<tr>\n"
            
            for key in all_keys:
                html += f"<th>{key}</th>\n"
            
            html += "</tr>\n</thead>\n<tbody>\n"
            
            for item in data:
                html += "<tr>\n"
                for key in all_keys:
                    value = item.get(key, "")
                    if isinstance(value, (dict, list)):
                        html += "<td>复杂对象</td>\n"
                    else:
                        html += f"<td>{value}</td>\n"
                html += "</tr>\n"
                
            html += "</tbody>\n</table>\n"
        else:
            # 简单列表使用序号显示
            html = "<table class='table table-sm table-striped mb-0'>\n"
            html += "<thead class='thead-light'>\n<tr>\n"
            html += "<th>#</th><th>值</th>\n"
            html += "</tr>\n</thead>\n<tbody>\n"
            
            for i, item in enumerate(data):
                html += f"<tr><td>{i+1}</td><td>"
                if isinstance(item, dict):
                    html += "字典对象"
                elif isinstance(item, list):
                    html += f"列表 ({len(item)} 项)"
                else:
                    html += f"{item}"
                html += "</td></tr>\n"
                
            html += "</tbody>\n</table>\n"
            
        return html
    
    def _get_mime_type(self, file_path: str) -> str:
        """根据文件扩展名确定MIME类型
        
        Args:
            file_path (str): 文件路径
            
        Returns:
            str: MIME类型
        """
        # 根据文件扩展名确定MIME类型
        extension = os.path.splitext(file_path)[1].lower()
        
        mime_types = {
            '.txt': 'text/plain',
            '.log': 'text/plain',
            '.tf': 'text/plain',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.svg': 'image/svg+xml',
            '.pdf': 'application/pdf',
            '.zip': 'application/zip',
            '.tfstate': 'application/json',
        }
        
        return mime_types.get(extension, 'application/octet-stream')
    
    def _build_fix_prompt(self, original_code, error_lines, is_volcengine=False):
        """构建修复Terraform代码的提示"""
        system_prompt = """
        You are a Terraform expert specializing in fixing infrastructure-as-code errors.
        Your task is to analyze the error message and fix the Terraform code.
        
        CRITICAL REQUIREMENTS:
        1. Only return the complete, corrected Terraform code
        2. Do NOT include any explanations, markdown formatting, or code blocks
        3. Fix the specific errors mentioned in the error message
        4. Preserve all existing resource configurations and credentials
        5. Ensure the code follows Terraform best practices
        6. Keep all comments and structure intact
        
        Common fixes:
        - Fix resource type typos (e.g., aws_vpcaaa -> aws_vpc)
        - Correct argument names and syntax
        - Add missing required arguments
        - Fix provider configuration issues
        """
        
        user_prompt = f"""
        Original Terraform code:
        {original_code}
        
        Error messages:
        {chr(10).join(error_lines)}
        
        Please fix the errors and return the corrected Terraform code.
        """
        
        if is_volcengine:
            system_prompt += """
            
            VOLCENGINE SPECIFIC:
            - Use volcengine provider resources
            - Ensure proper volcengine resource naming
            - Maintain volcengine-specific configurations
            """
        
        return {
            'system': system_prompt,
            'user': user_prompt
        }
    
    def _preserve_credentials(self, original_code, fixed_code, is_volcengine=False, fix_log_path=None):
        """保留原始代码中的凭证信息"""
        try:
            import re
            
            # 提取原始代码中的凭证
            if is_volcengine:
                # 火山引擎凭证
                ak_match = re.search(r'access_key\s*=\s*"([^"]*)"', original_code)
                sk_match = re.search(r'secret_key\s*=\s*"([^"]*)"', original_code)
                region_match = re.search(r'region\s*=\s*"([^"]*)"', original_code)
                
                if ak_match and sk_match:
                    ak = ak_match.group(1)
                    sk = sk_match.group(1)
                    region = region_match.group(1) if region_match else "cn-beijing"
                    
                    # 在修复后的代码中替换凭证
                    fixed_code = re.sub(r'access_key\s*=\s*"[^"]*"', f'access_key = "{ak}"', fixed_code)
                    fixed_code = re.sub(r'secret_key\s*=\s*"[^"]*"', f'secret_key = "{sk}"', fixed_code)
                    fixed_code = re.sub(r'region\s*=\s*"[^"]*"', f'region = "{region}"', fixed_code)
            else:
                # AWS凭证
                ak_match = re.search(r'access_key\s*=\s*"([^"]*)"', original_code)
                sk_match = re.search(r'secret_key\s*=\s*"([^"]*)"', original_code)
                region_match = re.search(r'region\s*=\s*"([^"]*)"', original_code)
                
                if ak_match and sk_match:
                    ak = ak_match.group(1)
                    sk = sk_match.group(1)
                    region = region_match.group(1) if region_match else "us-east-1"
                    
                    # 在修复后的代码中替换凭证
                    fixed_code = re.sub(r'access_key\s*=\s*"[^"]*"', f'access_key = "{ak}"', fixed_code)
                    fixed_code = re.sub(r'secret_key\s*=\s*"[^"]*"', f'secret_key = "{sk}"', fixed_code)
                    fixed_code = re.sub(r'region\s*=\s*"[^"]*"', f'region = "{region}"', fixed_code)
            
            if fix_log_path:
                with open(fix_log_path, 'a') as log_file:
                    log_file.write("凭证信息已保留在修复后的代码中\n")
            
            return fixed_code
            
        except Exception as e:
            if fix_log_path:
                with open(fix_log_path, 'a') as log_file:
                    log_file.write(f"保留凭证时出错: {str(e)}\n")
            return fixed_code

    def stop_deployment(self, deploy_id):
        """停止指定的部署任务"""
        try:
            self.logger.info(f"收到停止部署请求: {deploy_id}")
            
            # 检查是否有正在运行的部署
            if deploy_id not in self.active_deployments:
                self.logger.warning(f"没有找到正在运行的部署: {deploy_id}")
                return {
                    'success': False,
                    'message': '没有找到正在运行的部署任务'
                }
            
            deployment_info = self.active_deployments[deploy_id]
            deploy_dir = deployment_info.get('deploy_dir')
            
            # 创建停止信号文件
            if deploy_dir and os.path.exists(deploy_dir):
                stop_file = os.path.join(deploy_dir, '.stop_deployment')
                with open(stop_file, 'w') as f:
                    f.write(f"停止时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("原因: 用户手动停止部署\n")
                self.logger.info(f"已创建停止信号文件: {stop_file}")
            
            # 清理活跃部署记录
            if deploy_id in self.active_deployments:
                del self.active_deployments[deploy_id]
            
            self.logger.info(f"部署停止请求已发送: {deploy_id}")
            return {
                'success': True,
                'message': '部署停止信号已发送，部署将在下个检查点停止'
            }
            
        except Exception as e:
            self.logger.error(f"停止部署时出错: {str(e)}")
            return {
                'success': False,
                'message': f'停止部署时出错: {str(e)}'
            }

    def _add_cloud_credentials_to_code(self, terraform_code, ak, sk):
        """智能检测云平台并添加相应凭证"""
        # 检测Terraform代码中的云平台类型
        detected_cloud = self._detect_cloud_provider_from_code(terraform_code)
        
        self.logger.info(f"从Terraform代码中检测到云平台: {detected_cloud}")
        
        # 根据检测到的云平台添加相应凭证
        if detected_cloud == "volcengine":
            return self._add_volcengine_credentials_to_code(terraform_code, ak, sk)
        elif detected_cloud == "aws":
            return self._add_aws_credentials_to_code(terraform_code, ak, sk)
        elif detected_cloud == "huaweicloud":
            return self._add_huaweicloud_credentials_to_code(terraform_code, ak, sk)
        elif detected_cloud == "alicloud":
            return self._add_alicloud_credentials_to_code(terraform_code, ak, sk)
        elif detected_cloud == "tencentcloud":
            return self._add_tencentcloud_credentials_to_code(terraform_code, ak, sk)
        elif detected_cloud == "baiducloud":
            return self._add_baiducloud_credentials_to_code(terraform_code, ak, sk)
        elif detected_cloud == "azurerm":
            return self._add_azure_credentials_to_code(terraform_code, ak, sk)
        else:
            self.logger.warning(f"未识别的云平台: {detected_cloud}，跳过凭证添加")
            return terraform_code

    def _detect_cloud_provider_from_code(self, terraform_code):
        """从Terraform代码中检测云平台类型"""
        code_lower = terraform_code.lower()
        
        # 定义云平台检测规则（按优先级排序）
        cloud_patterns = [
            ("volcengine", ["provider \"volcengine\"", "volcengine_", "volcengine/"]),
            ("huaweicloud", ["provider \"huaweicloud\"", "huaweicloud_", "huaweicloud/"]),
            ("alicloud", ["provider \"alicloud\"", "alicloud_", "aliyun/alicloud"]),
            ("tencentcloud", ["provider \"tencentcloud\"", "tencentcloud_", "tencentcloudstack/"]),
            ("baiducloud", ["provider \"baiducloud\"", "baiducloud_", "baidubce/"]),
            ("azurerm", ["provider \"azurerm\"", "azurerm_", "hashicorp/azurerm"]),
            ("aws", ["provider \"aws\"", "aws_", "hashicorp/aws"])
        ]
        
        # 检测云平台
        for cloud_name, patterns in cloud_patterns:
            for pattern in patterns:
                if pattern in code_lower:
                    return cloud_name
        
        # 如果没有检测到任何云平台，返回unknown
        return "unknown"

    def _add_huaweicloud_credentials_to_code(self, terraform_code, ak, sk):
        """向Terraform代码中添加华为云凭证"""
        self.logger.info("添加华为云凭证到Terraform代码")
        
        lines = terraform_code.split('\n')
        providers = []
        
        # 寻找华为云provider
        for i, line in enumerate(lines):
            if re.match(r'\s*provider\s+"huaweicloud"\s+{', line):
                provider_start = i
                provider_end = -1
                
                # 找到provider块的结束
                for j in range(provider_start + 1, len(lines)):
                    if re.match(r'\s*}', lines[j]):
                        provider_end = j
                        break
                
                if provider_end > 0:
                    providers.append({
                        'start': provider_start,
                        'end': provider_end
                    })
        
        # 为每个华为云provider添加凭证
        offset = 0
        for provider in providers:
            start = provider['start'] + offset
            end = provider['end'] + offset
            
            # 检查是否已有凭证
            has_credentials = False
            for i in range(start, end):
                if re.search(r'access_key\s*=\s*".+?"', lines[i]) and re.search(r'secret_key\s*=\s*".+?"', lines[i]):
                    has_credentials = True
                    break
            
            # 如果没有凭证，添加凭证
            if not has_credentials:
                credentials = [
                    f"  access_key = \"{ak}\"",
                    f"  secret_key = \"{sk}\""
                ]
                
                lines.insert(end, credentials[1])
                lines.insert(end, credentials[0])
                offset += 2
        
        return '\n'.join(lines)

    def _add_alicloud_credentials_to_code(self, terraform_code, ak, sk):
        """向Terraform代码中添加阿里云凭证"""
        self.logger.info("添加阿里云凭证到Terraform代码")
        
        lines = terraform_code.split('\n')
        providers = []
        
        # 寻找阿里云provider
        for i, line in enumerate(lines):
            if re.match(r'\s*provider\s+"alicloud"\s+{', line):
                provider_start = i
                provider_end = -1
                
                for j in range(provider_start + 1, len(lines)):
                    if re.match(r'\s*}', lines[j]):
                        provider_end = j
                        break
                
                if provider_end > 0:
                    providers.append({
                        'start': provider_start,
                        'end': provider_end
                    })
        
        # 为每个阿里云provider添加凭证
        offset = 0
        for provider in providers:
            start = provider['start'] + offset
            end = provider['end'] + offset
            
            # 检查是否已有凭证
            has_credentials = False
            for i in range(start, end):
                if re.search(r'access_key\s*=\s*".+?"', lines[i]) and re.search(r'secret_key\s*=\s*".+?"', lines[i]):
                    has_credentials = True
                    break
            
            if not has_credentials:
                credentials = [
                    f"  access_key = \"{ak}\"",
                    f"  secret_key = \"{sk}\""
                ]
                
                lines.insert(end, credentials[1])
                lines.insert(end, credentials[0])
                offset += 2
        
        return '\n'.join(lines)

    def _add_tencentcloud_credentials_to_code(self, terraform_code, ak, sk):
        """向Terraform代码中添加腾讯云凭证"""
        self.logger.info("添加腾讯云凭证到Terraform代码")
        
        lines = terraform_code.split('\n')
        providers = []
        
        # 寻找腾讯云provider
        for i, line in enumerate(lines):
            if re.match(r'\s*provider\s+"tencentcloud"\s+{', line):
                provider_start = i
                provider_end = -1
                
                for j in range(provider_start + 1, len(lines)):
                    if re.match(r'\s*}', lines[j]):
                        provider_end = j
                        break
                
                if provider_end > 0:
                    providers.append({
                        'start': provider_start,
                        'end': provider_end
                    })
        
        # 为每个腾讯云provider添加凭证
        offset = 0
        for provider in providers:
            start = provider['start'] + offset
            end = provider['end'] + offset
            
            # 检查是否已有凭证
            has_credentials = False
            for i in range(start, end):
                if re.search(r'secret_id\s*=\s*".+?"', lines[i]) and re.search(r'secret_key\s*=\s*".+?"', lines[i]):
                    has_credentials = True
                    break
            
            if not has_credentials:
                credentials = [
                    f"  secret_id = \"{ak}\"",  # 腾讯云使用secret_id
                    f"  secret_key = \"{sk}\""
                ]
                
                lines.insert(end, credentials[1])
                lines.insert(end, credentials[0])
                offset += 2
        
        return '\n'.join(lines)

    def _add_baiducloud_credentials_to_code(self, terraform_code, ak, sk):
        """向Terraform代码中添加百度云凭证"""
        self.logger.info("添加百度云凭证到Terraform代码")
        
        lines = terraform_code.split('\n')
        providers = []
        
        # 寻找百度云provider
        for i, line in enumerate(lines):
            if re.match(r'\s*provider\s+"baiducloud"\s+{', line):
                provider_start = i
                provider_end = -1
                
                for j in range(provider_start + 1, len(lines)):
                    if re.match(r'\s*}', lines[j]):
                        provider_end = j
                        break
                
                if provider_end > 0:
                    providers.append({
                        'start': provider_start,
                        'end': provider_end
                    })
        
        # 为每个百度云provider添加凭证
        offset = 0
        for provider in providers:
            start = provider['start'] + offset
            end = provider['end'] + offset
            
            # 检查是否已有凭证
            has_credentials = False
            for i in range(start, end):
                if re.search(r'access_key\s*=\s*".+?"', lines[i]) and re.search(r'secret_key\s*=\s*".+?"', lines[i]):
                    has_credentials = True
                    break
            
            if not has_credentials:
                credentials = [
                    f"  access_key = \"{ak}\"",
                    f"  secret_key = \"{sk}\""
                ]
                
                lines.insert(end, credentials[1])
                lines.insert(end, credentials[0])
                offset += 2
        
        return '\n'.join(lines)

    def _add_azure_credentials_to_code(self, terraform_code, ak, sk):
        """向Terraform代码中添加Azure凭证"""
        self.logger.info("添加Azure凭证到Terraform代码")
        
        lines = terraform_code.split('\n')
        providers = []
        
        # 寻找Azure provider
        for i, line in enumerate(lines):
            if re.match(r'\s*provider\s+"azurerm"\s+{', line):
                provider_start = i
                provider_end = -1
                
                for j in range(provider_start + 1, len(lines)):
                    if re.match(r'\s*}', lines[j]):
                        provider_end = j
                        break
                
                if provider_end > 0:
                    providers.append({
                        'start': provider_start,
                        'end': provider_end
                    })
        
        # 为每个Azure provider添加凭证
        offset = 0
        for provider in providers:
            start = provider['start'] + offset
            end = provider['end'] + offset
            
            # 检查provider块中已有的配置
            has_client_id = False
            has_client_secret = False
            has_tenant_id = False
            has_subscription_id = False
            has_use_cli = False
            
            for i in range(start, end):
                line = lines[i]
                if re.search(r'client_id\s*=', line):
                    has_client_id = True
                elif re.search(r'client_secret\s*=', line):
                    has_client_secret = True
                elif re.search(r'tenant_id\s*=', line):
                    has_tenant_id = True
                elif re.search(r'subscription_id\s*=', line):
                    has_subscription_id = True
                elif re.search(r'use_cli\s*=', line):
                    has_use_cli = True
            
            # 构建需要添加的凭证列表
            credentials_to_add = []
            
            if not has_client_id:
                credentials_to_add.append(f"  client_id = \"{ak}\"")  # AK对应client_id
            if not has_client_secret:
                credentials_to_add.append(f"  client_secret = \"{sk}\"")  # SK对应client_secret
            if not has_tenant_id:
                credentials_to_add.append(f"  tenant_id = var.tenant_id")
            if not has_subscription_id:
                credentials_to_add.append(f"  subscription_id = var.subscription_id")
            if not has_use_cli:
                credentials_to_add.append(f"  use_cli = false")
            
            # 只添加缺失的配置
            if credentials_to_add:
                self.logger.info(f"添加缺失的Azure凭证配置: {credentials_to_add}")
                for cred in reversed(credentials_to_add):
                    lines.insert(end, cred)
                offset += len(credentials_to_add)
            else:
                self.logger.info("Azure provider配置已完整，无需添加凭证")
        
        return '\n'.join(lines)