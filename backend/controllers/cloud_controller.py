import logging
from typing import Dict, Any, Optional
from flask import request, jsonify, session
from models.cloud_model import CloudModel
from config.config import Config
import json
import re
import random
import string
import time
import os

class CloudController:
    """云资源管理控制器类，处理与云资源管理相关的请求"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 初始化云资源模型
        self.cloud_model = CloudModel({
            'host': config.db_host,
            'user': config.db_user,
            'password': config.db_password,
            'database': config.db_name
        })
        
        # 确保cloud表存在
        self.cloud_model.init_table()
        
    def generate_deploy_id(self) -> str:
        """生成18位查询ID
        
        格式: 前缀 + 时间戳 + 随机字符
        
        Returns:
            18位查询ID
        """
        prefix = "QR"  # 查询前缀
        timestamp = int(time.time())  # 当前时间戳
        timestamp_str = str(timestamp)[-10:]  # 取时间戳后10位
        
        # 计算需要的随机字符数量(18 - 前缀长度 - 时间戳长度)
        random_length = 18 - len(prefix) - len(timestamp_str)
        
        # 生成随机字符串(包含字母数字)
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=random_length))
        
        # 组合查询ID
        deploy_id = f"{prefix}{timestamp_str}{random_chars}"
        
        return deploy_id
        
    def handle_query_request(self):
        """处理查询请求，用户发送包含"@查询"的消息时，返回一个表单，让用户填写AK/SK等信息"""
        try:
            # 获取请求数据
            data = request.get_json()
            if not data or 'message' not in data:
                return jsonify({"error": "请提供消息内容"}), 400
                
            message = data.get('message', '')
            project = data.get('project', '未指定项目')
            cloud = data.get('cloud', '未指定云')
            user_id = data.get('user_id', 0)
            username = data.get('username', '未知用户')
            
            # 从请求头中获取用户信息，确保用户ID和用户名正确
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
                try:
                    from utils.auth import decode_token
                    payload = decode_token(token)
                    if payload:
                        user_id = payload.get('user_id', user_id)
                        username = payload.get('username', username)
                        self.logger.info(f"从JWT token获取到用户信息: ID={user_id}, 用户名={username}")
                except Exception as e:
                    self.logger.error(f"解析JWT token出错: {str(e)}")
                    
            # 检查消息是否包含@查询
            if '@查询' not in message:
                return jsonify({"error": "无效的查询请求"}), 400
            
            # 生成查询ID
            query_id = self.generate_deploy_id()
                
            # 构建响应
            response = {
                "deployment_request": True,
                "reply": f"您本次查询ID：{query_id} ； 您本次查询项目：{project} ； 您本次查询云：{cloud} ； 请输入AKSK：",
                "form": {
                    "title": "云平台访问凭证",
                    "fields": [
                        {"name": "ak", "label": "Access Key", "type": "text", "required": True},
                        {"name": "sk", "label": "Secret Key", "type": "password", "required": True}
                    ],
                    "metadata": {
                        "user_id": user_id,
                        "username": username,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": query_id
                    }
                }
            }
            
            # 记录日志
            self.logger.info(f"生成查询表单: ID={query_id}, 用户={username}({user_id}), 项目={project}, 云={cloud}")
            
            return jsonify(response)
        except Exception as e:
            self.logger.error(f"处理查询请求时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理请求时发生错误: {str(e)}"}), 500
    
    def handle_deployment_request(self):
        """处理查询请求的别名，与handle_query_request功能相同
        
        当用户发送包含"@查询"的消息时，返回一个表单，让用户填写AK/SK等信息
        """
        # 直接调用handle_query_request
        return self.handle_query_request()
    
    def save_cloud_config(self):
        """保存云配置信息
        
        当用户提交AK/SK表单时，保存到数据库中，始终创建新记录
        """
        try:
            # 获取请求数据
            data = request.get_json()
            self.logger.info(f"接收到原始请求数据: {data}")
            
            if not data:
                return jsonify({"error": "请提供配置数据"}), 400
            
            # 获取当前登录用户的ID和用户名
            current_user_id = session.get('user_id', 0)
            current_username = session.get('username', '')
            
            # 如果会话中没有用户信息，尝试从JWT token获取
            if current_user_id == 0 or not current_username:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                    try:
                        from utils.auth import decode_token
                        payload = decode_token(token)
                        if payload:
                            current_user_id = payload.get('user_id', 0)
                            current_username = payload.get('username', '')
                            self.logger.info(f"从JWT token获取到用户信息: ID={current_user_id}, 用户名={current_username}")
                    except Exception as e:
                        self.logger.error(f"解析JWT token出错: {str(e)}")
            
            # 如果仍然无法获取用户信息，则尝试从请求数据中获取（作为备用）
            if current_user_id == 0:
                current_user_id = data.get('user_id', 0)
            if not current_username:
                current_username = data.get('username', '未知用户')
            
            self.logger.info(f"使用的用户信息: ID={current_user_id}, 用户名={current_username}")
                
            project = data.get('project', '未指定项目')
            cloud = data.get('cloud', '未指定云')
            ak = data.get('ak', '')
            sk = data.get('sk', '')
            deploy_id = data.get('deploy_id', '')
            
            # 记录关键参数
            self.logger.info(f"接收到的表单数据: 用户={current_username}, 项目={project}, 云={cloud}, 查询ID={deploy_id}")
            
            if not all([current_user_id, current_username, project, cloud, ak, sk]):
                return jsonify({"error": "请提供完整的配置信息"}), 400
            
            # 检查查询ID
            if not deploy_id:
                # 如果没有查询ID，生成一个
                deploy_id = self.generate_deploy_id()
                self.logger.warning(f"表单中缺少查询ID，已生成新ID: {deploy_id}")
            
            # 调试查询ID
            self.logger.info(f"即将保存的查询ID: {deploy_id}")
            
            # 显式声明查询ID作为单独变量，避免引用问题
            deployid_to_save = str(deploy_id).strip()
            self.logger.info(f"最终使用的查询ID: {deployid_to_save}, 类型: {type(deployid_to_save)}")
            
            # 进行额外检查，确保不会传递空的查询ID
            if not deployid_to_save:
                deployid_to_save = self.generate_deploy_id()
                self.logger.warning(f"生成的查询ID为空，重新生成: {deployid_to_save}")
            
            # 保存云配置信息，显式设置force_insert=True确保始终创建新记录
            # 包装在try-except中，以便捕获并记录数据库错误
            try:
                success = self.cloud_model.save_cloud_config(
                    user_id=current_user_id,
                    username=current_username,
                    project=project,
                    cloud=cloud,
                    ak=ak,
                    sk=sk,
                    deployid=deployid_to_save,  # 使用明确的变量
                    force_insert=True  # 关键参数: 强制插入新记录
                )
            except Exception as db_error:
                self.logger.error(f"数据库操作失败: {str(db_error)}", exc_info=True)
                return jsonify({"error": f"数据库操作失败: {str(db_error)}"}), 500
            
            if success:
                self.logger.info(f"成功保存云配置: 项目={project}, 云={cloud}, 查询ID={deployid_to_save}")
                
                # 验证保存结果
                try:
                    configs = self.cloud_model.get_cloud_config(
                        user_id=current_user_id,
                        project=project,
                        cloud=cloud
                    )
                    
                    # 检查最新保存的记录
                    if configs:
                        found_deployid = False
                        for config in configs:
                            saved_deployid = config.get('deployid')
                            if saved_deployid == deployid_to_save:
                                self.logger.info(f"找到匹配的查询ID记录: {saved_deployid}")
                                found_deployid = True
                        
                        if not found_deployid:
                            self.logger.warning(f"未找到匹配查询ID的记录: {deployid_to_save}")
                            if configs:
                                self.logger.info(f"找到的第一条配置: {configs[0]}")
                except Exception as verify_error:
                    self.logger.error(f"验证保存结果时出错: {str(verify_error)}")
                
                # 构建响应
                response = {
                    "type": "deployment_options",
                    "message": f"AK/SK 已成功保存。请选择您要执行的操作：",
                    "options": [
                        {"id": "query", "text": "查询当前云资源", "action": "query_resources"}
                    ],
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deployid_to_save
                    }
                }
                self.logger.info(f"返回响应: {response}")
                return jsonify(response)
            else:
                self.logger.error(f"保存云配置失败: 项目={project}, 云={cloud}, 查询ID={deployid_to_save}")
                return jsonify({"error": "保存配置信息失败"}), 500
        except Exception as e:
            self.logger.error(f"处理表单提交时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理表单时发生错误: {str(e)}"}), 500
            
    def handle_cloud_option_selection(self):
        """处理云资源操作选项选择"""
        try:
            data = request.get_json()
            self.logger.info(f"接收到选项选择数据: {data}")
            
            if not data:
                return jsonify({"error": "请提供选项数据"}), 400
            
            # 获取当前登录用户的ID和用户名
            current_user_id = session.get('user_id', 0)
            current_username = session.get('username', '')
            
            # 如果会话中没有用户信息，尝试从JWT token获取
            if current_user_id == 0 or not current_username:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                    try:
                        from utils.auth import decode_token
                        payload = decode_token(token)
                        if payload:
                            current_user_id = payload.get('user_id', 0)
                            current_username = payload.get('username', '')
                            self.logger.info(f"从JWT token获取到用户信息: ID={current_user_id}, 用户名={current_username}")
                    except Exception as e:
                        self.logger.error(f"解析JWT token出错: {str(e)}")
            
            # 如果仍然无法获取用户信息，则尝试从请求数据中获取（作为备用）
            if current_user_id == 0:
                current_user_id = data.get('user_id', 0)
            
            self.logger.info(f"使用的用户信息: ID={current_user_id}, 用户名={current_username}")
                
            option_id = data.get('option_id', '')
            project = data.get('project', '')
            cloud = data.get('cloud', '')
            deploy_id = data.get('deploy_id', '')
            
            self.logger.info(f"处理选项: {option_id}, 用户: {current_user_id}, 项目: {project}, 云: {cloud}, 查询ID: {deploy_id}")
            
            if option_id == 'query':
                # 查询云资源前，先让用户选择区域
                # 检查云配置是否存在
                configs = self.cloud_model.get_cloud_config(
                    user_id=current_user_id,
                    project=project,
                    cloud=cloud
                )
                
                if not configs:
                    return jsonify({
                        "reply": "未找到云配置信息，请先配置AK/SK"
                    })
                
                # 获取该云的所有可用区域
                regions = self.cloud_model.get_regions_by_cloud(cloud)
                self.logger.info(f"为云{cloud}获取到区域列表: {regions}")
                
                # 返回区域选择下拉菜单
                return jsonify({
                    "reply": f"请选择{cloud}的区域：",
                    "region_selection": True,
                    "regions": regions,
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id or configs[0].get('deployid', '')
                    }
                })
                
            elif option_id == 'deploy':
                # 查询云资源
                # 返回资源选择界面
                response_data = {
                    "reply": f"请选择要查询的云资源类型：",
                    "resource_selection": True,
                    "resource_options": [
                        {"id": "vpc", "text": "VPC", "disabled": False},
                        {"id": "subnet", "text": "子网", "disabled": False},
                        {"id": "s3", "text": "S3存储桶", "disabled": False},
                        {"id": "iam_user", "text": "IAM用户", "disabled": False},
                        {"id": "iam_group", "text": "IAM用户组", "disabled": False},
                        {"id": "iam_policy", "text": "IAM策略", "disabled": False}
                    ],
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id or configs[0].get('deployid', '')
                    }
                }
                self.logger.info(f"返回资源选择界面数据: {response_data}")
                return jsonify(response_data)
            else:
                return jsonify({"error": "未知的选项"}), 400
        except Exception as e:
            self.logger.error(f"处理选项选择时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理选项时发生错误: {str(e)}"}), 500
    
    def handle_region_selection(self):
        """处理区域选择"""
        try:
            data = request.get_json()
            self.logger.info(f"接收到区域选择数据: {data}")
            
            if not data:
                return jsonify({"error": "请提供区域数据"}), 400
            
            # 获取当前登录用户的ID和用户名
            current_user_id = session.get('user_id', 0)
            current_username = session.get('username', '')
            
            # 如果会话中没有用户信息，尝试从JWT token获取
            if current_user_id == 0 or not current_username:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                    try:
                        from utils.auth import decode_token
                        payload = decode_token(token)
                        if payload:
                            current_user_id = payload.get('user_id', 0)
                            current_username = payload.get('username', '')
                            self.logger.info(f"从JWT token获取到用户信息: ID={current_user_id}, 用户名={current_username}")
                    except Exception as e:
                        self.logger.error(f"解析JWT token出错: {str(e)}")
            
            # 如果仍然无法获取用户信息，则尝试从请求数据中获取（作为备用）
            if current_user_id == 0:
                current_user_id = data.get('user_id', 0)
            
            self.logger.info(f"使用的用户信息: ID={current_user_id}, 用户名={current_username}")
                
            project = data.get('project', '')
            cloud = data.get('cloud', '')
            region = data.get('region', '')
            deploy_id = data.get('deploy_id', '')
            
            self.logger.info(f"处理区域选择: 用户={current_user_id}, 项目={project}, 云={cloud}, 区域={region}, 查询ID={deploy_id}")
            
            if not all([current_user_id, project, cloud, region]):
                return jsonify({"error": "请提供完整的区域信息"}), 400
            
            # 获取云配置信息
            configs = self.cloud_model.get_cloud_config(
                user_id=current_user_id,
                project=project,
                cloud=cloud
            )
            
            if not configs:
                return jsonify({
                    "reply": "未找到云配置信息，请先配置AK/SK"
                })
            
            # 在保存区域前确保有查询ID
            if not deploy_id and configs:
                deploy_id = configs[0].get('deployid', '')
                if not deploy_id:
                    deploy_id = self.generate_deploy_id()
                    self.logger.warning(f"区域选择中缺少查询ID，已生成新ID: {deploy_id}")
            
            self.logger.info(f"保存区域信息，查询ID: {deploy_id}, 区域: {region}")
            
            # 获取要更新的配置（使用最新的一条记录）
            config = configs[0]
            
            # 保存区域信息到数据库
            success = self.cloud_model.save_cloud_config(
                user_id=current_user_id,
                username=current_username,
                project=project,
                cloud=cloud,
                ak=config.get('ak', ''),
                sk=config.get('sk', ''),
                region=region,
                deployid=deploy_id,
                force_insert=False  # 不强制插入，允许更新现有记录
            )
            
            if success:
                self.logger.info(f"成功保存区域信息: 项目={project}, 云={cloud}, 区域={region}, 查询ID={deploy_id}")
                
                # 构建查询信息文本，而不是显示资源
                query_text = f"**本次查询信息如下：**\n\n"
                query_text += f"- 项目：{project}\n"
                query_text += f"- 云: {cloud}\n"
                query_text += f"- AK: {config.get('ak', '')}\n"  # 完整显示AK
                query_text += f"- SK: {config.get('sk', '')}\n"  # 完整显示SK
                query_text += f"- 查询区域：{region}\n"
                query_text += f"- 查询ID：{deploy_id}\n"
                
                return jsonify({
                    "reply": query_text,
                    "region": region,
                    "deploy_id": deploy_id,
                    "show_query_button": True,  # 添加标志以显示查询按钮
                    "query_info": {
                        "user_id": current_user_id,  # 使用当前用户ID
                        "project": project,
                        "cloud": cloud,
                        "region": region,
                        "deploy_id": deploy_id
                    }
                })
            else:
                return jsonify({"error": "更新区域信息失败"}), 500
        except Exception as e:
            self.logger.error(f"处理区域选择时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理区域选择时发生错误: {str(e)}"}), 500
    
    def handle_cloud_query(self):
        """处理确认查询按钮的点击，执行Terraform查询操作"""
        try:
            # 获取请求数据
            data = request.get_json()
            self.logger.info(f"接收到查询请求数据: {data}")
            
            if not data:
                return jsonify({"error": "请提供查询数据"}), 400
                
            project = data.get('project', '')
            cloud = data.get('cloud', '')
            region = data.get('region', '')
            deploy_id = data.get('deploy_id', '')
            action = data.get('action', '')
            user_id = data.get('user_id', 0)
            
            self.logger.info(f"处理查询请求: 项目={project}, 云={cloud}, 区域={region}, 查询ID={deploy_id}, 动作={action}")
            
            if not deploy_id:
                return jsonify({"error": "缺少查询ID"}), 400
            
            # 导入工具类
            from toolkits.terraform_generator import TerraformGenerator
            from toolkits.terraform_executor import TerraformExecutor
            
            # 数据库配置
            db_config = {
                'host': self.config.db_host,
                'user': self.config.db_user,
                'password': self.config.db_password,
                'database': self.config.db_name
            }
            
            # 生成Terraform配置文件
            self.logger.info(f"正在为查询ID {deploy_id} 生成Terraform配置文件")
            generator = TerraformGenerator(db_config)
            tf_file_path = generator.generate_terraform_file(deploy_id)
            
            if not tf_file_path:
                self.logger.error(f"生成Terraform配置文件失败")
                return jsonify({"error": "生成Terraform配置文件失败"}), 500
            
            # 获取terraform_content
            with open(tf_file_path, 'r') as f:
                terraform_content = f.read()
            
            # 创建执行器并执行Terraform
            self.logger.info(f"正在为查询ID {deploy_id} 执行Terraform查询")
            executor = TerraformExecutor(db_config)
            
            # 获取当前登录用户的ID
            current_user_id = session.get('user_id', 0)
            if current_user_id == 0:
                # 尝试从请求头的JWT token获取用户ID
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                    try:
                        from utils.auth import decode_token
                        payload = decode_token(token)
                        if payload and 'user_id' in payload:
                            current_user_id = payload['user_id']
                            self.logger.info(f"从JWT token获取到用户ID: {current_user_id}")
                    except Exception as e:
                        self.logger.error(f"解析JWT token出错: {str(e)}")
            
            self.logger.info(f"当前用户ID: {current_user_id}")
            
            # 调用run_terraform
            terraform_config = generator.get_terraform_config(deploy_id)
            if not terraform_config:
                self.logger.error(f"获取Terraform配置失败")
                return jsonify({"error": "获取Terraform配置失败"}), 500
                
            # 使用当前登录用户的ID，而不是terraform_config中的user_id
            ak = terraform_config.get('ak', '')
            sk = terraform_config.get('sk', '')
            
            # 将ak/sk传递给run_terraform方法
            result = executor.run_terraform(current_user_id, project, cloud, region, terraform_content, deploy_id, ak, sk)
            
            if not result.get('success', False):
                self.logger.error(f"执行Terraform失败: {result.get('error', '未知错误')}")
                return jsonify({
                    "reply": f"查询失败: {result.get('error', '未知错误')}",
                    "success": False,
                    "error": result.get('error', '未知错误')
                }), 500
            
            # 处理结果
            if result and result.get('success'):
                # 使用公共接口format_results_as_table，避免出现错误
                result_table = executor.format_results_as_table(result.get('results', {}))
                
                # 记录Terraform查询结果，特别是IAM用户信息
                results = result.get('results', {})
                self.logger.info(f"Terraform查询结果: {results}")
                
                # 检查IAM用户信息是否被正确获取
                if 'iamid' in results and results['iamid']:
                    self.logger.info(f"成功获取IAM用户ID: {results['iamid']}")
                if 'iamarn' in results and results['iamarn']:
                    self.logger.info(f"成功获取IAM用户ARN: {results['iamarn']}")
                
                # 返回格式化的响应，包含完整的HTML表格
                return jsonify({
                    "success": True, 
                    "message": f"查询执行成功，已获取{cloud}资源列表", 
                    "reply": f"<div class='query-result'>查询执行成功，已获取{cloud}资源列表：<br/><br/>{result_table}</div>",
                    "data": {
                        "table": result_table,
                        "results": results
                    }
                })
            
        except Exception as e:
            self.logger.error(f"处理查询请求时出错: {str(e)}", exc_info=True)
            return jsonify({
                "error": f"处理查询请求时发生错误: {str(e)}",
                "reply": f"查询失败: 处理查询请求时发生错误",
                "success": False
            }), 500
            
    def _get_cloud_resources(self, cloud, region, project):
        """获取指定云服务商和区域的资源信息（模拟）"""
        # 基于云服务商和区域的资源信息
        resources = {
            "计算资源": [],
            "存储资源": [],
            "网络资源": [],
            "安全资源": []
        }
        
        # 生成资源ID前缀
        id_prefix = f"{cloud[:2].upper()}-{region[:2].upper()}"
        
        # AWS资源
        if cloud.upper() == "AWS":
            # 计算资源
            if region == "us-east-1":
                resources["计算资源"] = [
                    {"id": f"{id_prefix}-EC2-001", "name": f"{project}-web-server", "status": "运行中", 
                     "details": {"类型": "t3.medium", "CPU": "2 vCPU", "内存": "4 GiB"}},
                    {"id": f"{id_prefix}-EC2-002", "name": f"{project}-app-server", "status": "运行中", 
                     "details": {"类型": "t3.large", "CPU": "2 vCPU", "内存": "8 GiB"}}
                ]
            elif region in ["cn-north-1", "cn-northwest-1"]:
                resources["计算资源"] = [
                    {"id": f"{id_prefix}-EC2-001", "name": f"{project}-web-server-cn", "status": "运行中", 
                     "details": {"类型": "t3.medium", "CPU": "2 vCPU", "内存": "4 GiB"}},
                    {"id": f"{id_prefix}-EC2-002", "name": f"{project}-app-server-cn", "status": "已停止", 
                     "details": {"类型": "t3.large", "CPU": "2 vCPU", "内存": "8 GiB"}}
                ]
            else:
                resources["计算资源"] = [
                    {"id": f"{id_prefix}-EC2-001", "name": f"{project}-web-server", "status": "运行中", 
                     "details": {"类型": "t3.medium", "CPU": "2 vCPU", "内存": "4 GiB"}}
                ]
            
            # 存储资源
            resources["存储资源"] = [
                {"id": f"{id_prefix}-S3-001", "name": f"{project}-data-bucket", "status": "可用", 
                 "details": {"容量": "500 GB", "类型": "标准存储", "访问策略": "私有"}},
                {"id": f"{id_prefix}-EBS-001", "name": f"{project}-data-volume", "status": "已挂载", 
                 "details": {"容量": "100 GB", "类型": "gp2", "IOPS": "3000"}}
            ]
            
            # 网络资源
            resources["网络资源"] = [
                {"id": f"{id_prefix}-VPC-001", "name": f"{project}-vpc", "status": "可用", 
                 "details": {"CIDR": "10.0.0.0/16", "子网数": "3"}},
                {"id": f"{id_prefix}-SUBNET-001", "name": f"{project}-public-subnet", "status": "可用", 
                 "details": {"CIDR": "10.0.1.0/24", "可用区": f"{region}a", "类型": "公有"}}
            ]
            
            # 安全资源
            resources["安全资源"] = [
                {"id": f"{id_prefix}-IAM-001", "name": f"{project}-app-role", "status": "活跃", 
                 "details": {"权限数": "3", "信任实体": "EC2"}},
                {"id": f"{id_prefix}-SG-001", "name": f"{project}-web-sg", "status": "已应用", 
                 "details": {"入站规则": "2", "出站规则": "1"}}
            ]
        
        # 阿里云资源
        elif "阿里" in cloud:
            # 计算资源
            resources["计算资源"] = [
                {"id": f"{id_prefix}-ECS-001", "name": f"{project}-web-server", "status": "运行中", 
                 "details": {"规格": "ecs.g6.large", "CPU": "2 vCPU", "内存": "8 GB"}},
                {"id": f"{id_prefix}-ECS-002", "name": f"{project}-db-server", "status": "运行中", 
                 "details": {"规格": "ecs.g6.xlarge", "CPU": "4 vCPU", "内存": "16 GB"}}
            ]
            
            # 存储资源
            resources["存储资源"] = [
                {"id": f"{id_prefix}-OSS-001", "name": f"{project}-bucket", "status": "已创建", 
                 "details": {"存储类型": "标准", "读写权限": "私有", "访问域名": f"{project}.oss-{region}.aliyuncs.com"}},
                {"id": f"{id_prefix}-DISK-001", "name": f"{project}-data-disk", "status": "使用中", 
                 "details": {"容量": "200 GB", "类型": "ESSD PL1"}}
            ]
            
            # 网络资源
            resources["网络资源"] = [
                {"id": f"{id_prefix}-VPC-001", "name": f"{project}-vpc", "status": "可用", 
                 "details": {"CIDR": "172.16.0.0/12"}},
                {"id": f"{id_prefix}-VSWITCH-001", "name": f"{project}-vswitch", "status": "可用", 
                 "details": {"CIDR": "172.16.0.0/24", "可用区": f"{region}-a"}}
            ]
            
            # 安全资源
            resources["安全资源"] = [
                {"id": f"{id_prefix}-RAM-001", "name": f"{project}-role", "status": "启用", 
                 "details": {"策略数": "2", "类型": "服务角色"}},
                {"id": f"{id_prefix}-SG-001", "name": f"{project}-security-group", "status": "已应用", 
                 "details": {"规则数": "5"}}
            ]
        
        # 其他云服务商的资源
        else:
            # 通用资源模板
            resources["计算资源"] = [
                {"id": f"{id_prefix}-VM-001", "name": f"{project}-server", "status": "运行中", 
                 "details": {"CPU": "2 vCPU", "内存": "4 GB"}}
            ]
            
            resources["存储资源"] = [
                {"id": f"{id_prefix}-STORAGE-001", "name": f"{project}-storage", "status": "可用", 
                 "details": {"容量": "100 GB"}}
            ]
            
            resources["网络资源"] = [
                {"id": f"{id_prefix}-NET-001", "name": f"{project}-network", "status": "可用", 
                 "details": {"CIDR": "192.168.0.0/16"}}
            ]
            
            resources["安全资源"] = [
                {"id": f"{id_prefix}-SEC-001", "name": f"{project}-security", "status": "已部署", 
                 "details": {"规则数": "3"}}
            ]
        
        return resources 

    def handle_resource_selection(self):
        """处理资源选择提交"""
        try:
            data = request.get_json()
            self.logger.info(f"接收到资源选择数据: {data}")
            
            if not data:
                return jsonify({"error": "请提供资源选择数据"}), 400
            
            # 获取当前登录用户的ID和用户名
            current_user_id = session.get('user_id', 0)
            current_username = session.get('username', '')
            
            # 如果会话中没有用户信息，尝试从JWT token获取
            if current_user_id == 0 or not current_username:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    token = auth_header.split(' ')[1]
                    try:
                        from utils.auth import decode_token
                        payload = decode_token(token)
                        if payload:
                            current_user_id = payload.get('user_id', 0)
                            current_username = payload.get('username', '')
                            self.logger.info(f"从JWT token获取到用户信息: ID={current_user_id}, 用户名={current_username}")
                    except Exception as e:
                        self.logger.error(f"解析JWT token出错: {str(e)}")
            
            # 如果仍然无法获取用户信息，则尝试从请求数据中获取（作为备用）
            if current_user_id == 0:
                current_user_id = data.get('user_id', 0)
            
            self.logger.info(f"使用的用户信息: ID={current_user_id}, 用户名={current_username}")
                
            project = data.get('project', '')
            cloud = data.get('cloud', '')
            selected_resources = data.get('selected_resources', [])
            deploy_id = data.get('deploy_id', '')
            
            self.logger.info(f"处理资源选择: 用户={current_user_id}, 项目={project}, 云={cloud}, 资源={selected_resources}, 查询ID={deploy_id}")
            
            if not all([current_user_id, project, cloud]) or not selected_resources:
                return jsonify({"error": "请提供完整的资源选择信息"}), 400
            
            # 获取云配置信息
            configs = self.cloud_model.get_cloud_config(
                user_id=current_user_id,
                project=project,
                cloud=cloud
            )
            
            if not configs:
                return jsonify({
                    "reply": "未找到云配置信息，请先配置AK/SK"
                })
            
            # 在保存资源选择前确保有查询ID
            if not deploy_id and configs:
                deploy_id = configs[0].get('deployid', '')
                if not deploy_id:
                    deploy_id = self.generate_deploy_id()
                    self.logger.warning(f"资源选择中缺少查询ID，已生成新ID: {deploy_id}")
            
            # 获取要更新的配置（使用最新的一条记录）
            config = configs[0]
            
            # 特殊处理独占选项 - 着陆区和AIOPS
            if 'landing_zone' in selected_resources:
                # 处理一键查询合规着陆区
                self.logger.info(f"处理一键查询合规着陆区: 查询ID={deploy_id}")
                
                # 返回查询开始的消息
                return jsonify({
                    "reply": f"<div class='deployment-message'>已开始查询合规着陆区，这将包含VPC、子网、IAM用户和策略等所有必要资源。<br><br>查询ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{config.get('region', '未指定')}</strong><br><br>查询预计需要5-10分钟完成，完成后可在历史查询中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id,
                        "resources": ["vpc", "subnet", "iam_user", "iam_policy", "iam_group"]
                    }
                })
            elif 'aiops' in selected_resources:
                # 处理AIOPS查询
                self.logger.info(f"处理AIOPS查询: 查询ID={deploy_id}")
                
                # 返回AIOPS查询开始的消息
                return jsonify({
                    "reply": f"<div class='deployment-message'>已开始查询AIOPS资源，这将包含云监控、日志分析、告警系统和AI运维资源。<br><br>查询ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{config.get('region', '未指定')}</strong><br><br>AIOPS查询预计需要8-15分钟完成，完成后可在历史查询中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id,
                        "resources": ["monitoring", "logging", "alerting", "ai_ops"]
                    }
                })
            else:
                # 处理普通资源选择
                self.logger.info(f"处理普通资源选择: 资源={selected_resources}, 查询ID={deploy_id}")
                
                # 构建资源列表文本
                resource_list = "<ul>"
                for resource in selected_resources:
                    if resource == "vpc":
                        resource_list += "<li>VPC</li>"
                    elif resource == "subnet":
                        resource_list += "<li>子网</li>"
                    elif resource == "s3":
                        resource_list += "<li>S3存储桶</li>"
                    elif resource == "iam_user":
                        resource_list += "<li>IAM用户</li>"
                    elif resource == "iam_group":
                        resource_list += "<li>IAM用户组</li>"
                    elif resource == "iam_policy":
                        resource_list += "<li>IAM策略</li>"
                resource_list += "</ul>"
                
                # 返回资源选择确认消息
                return jsonify({
                    "reply": f"<div class='deployment-message'>已开始查询以下资源：<br>{resource_list}<br>查询ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{config.get('region', '未指定')}</strong><br><br>查询预计需要3-5分钟完成，完成后可在历史查询中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id,
                        "resources": selected_resources
                    }
                })
                
        except Exception as e:
            self.logger.error(f"处理资源选择时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理资源选择时发生错误: {str(e)}"}), 500

    def get_user_deployments(self):
        """获取当前用户的所有查询历史"""
        try:
            # 从请求中获取用户ID
            current_user_id = request.current_user.get('user_id', 0)
            self.logger.info(f"获取用户 {current_user_id} 的查询历史")
            
            # 获取用户查询历史
            deployments = self.cloud_model.get_user_deployments(current_user_id)
            
            # 添加日志记录找到的查询历史记录数
            self.logger.info(f"找到用户ID={current_user_id}的查询历史记录数: {len(deployments)}")
            if deployments:
                self.logger.info(f"用户查询历史示例: {deployments[0]}")
            
            # 返回查询历史列表
            return jsonify({
                "success": True,
                "deployments": deployments
            })
            
        except Exception as e:
            self.logger.error(f"获取用户查询历史出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"获取查询历史失败: {str(e)}"}), 500
            
    def get_deployment_details(self):
        """获取指定查询ID的资源详情"""
        try:
            # 获取查询ID
            deploy_id = request.args.get('deploy_id')
            if not deploy_id:
                return jsonify({"error": "缺少查询ID参数"}), 400
                
            self.logger.info(f"获取查询ID {deploy_id} 的资源详情")
            
            # 获取查询资源详情
            details = self.cloud_model.get_deployment_details(deploy_id)
            
            # 检查是否找到资源
            if not details['deployment_info']:
                return jsonify({"error": f"未找到查询ID为 {deploy_id} 的资源"}), 404
                
            # 格式化结果为表格展示
            from toolkits.terraform_executor import TerraformExecutor
            # 从self.config获取数据库配置而不是使用不存在的self.db_config
            db_config = {
                'host': self.config.db_host,
                'user': self.config.db_user,
                'password': self.config.db_password,
                'database': self.config.db_name
            }
            executor = TerraformExecutor(db_config)
            
            # 构建一个更友好的HTML表格
            html = "<div class='deployment-details card shadow-sm'>"
            
            # 添加基本信息表格
            if details['deployment_info']:
                deployment_info = details['deployment_info']
                html += "<div class='card-header bg-primary text-white'><h3 class='mb-0'><i class='fas fa-info-circle mr-2'></i>查询基本信息</h3></div>"
                html += "<div class='card-body'>"
                html += "<table class='table table-striped table-bordered table-hover'>"
                html += "<tbody>"
                html += f"<tr><th width='30%' class='bg-light'>查询ID</th><td><code>{deploy_id}</code></td></tr>"
                html += f"<tr><th class='bg-light'>项目</th><td>{deployment_info.get('project', '未知')}</td></tr>"
                html += f"<tr><th class='bg-light'>云平台</th><td><span class='badge badge-info'>{deployment_info.get('cloud', '未知')}</span></td></tr>"
                html += f"<tr><th class='bg-light'>区域</th><td><span class='badge badge-secondary'>{deployment_info.get('region', '未知')}</span></td></tr>"
                html += f"<tr><th class='bg-light'>创建时间</th><td>{deployment_info.get('created_at', '未知')}</td></tr>"
                html += "</tbody>"
                html += "</table>"
                html += "</div>"
            
            # 添加VPC资源表格
            vpc_resources = details.get('vpc_resources', [])
            if vpc_resources:
                html += f"<div class='card-header bg-info text-white'><h3 class='mb-0'><i class='fas fa-network-wired mr-2'></i>VPC资源 ({len(vpc_resources)}个)</h3></div>"
                html += "<div class='card-body table-responsive'>"
                html += "<table class='table table-striped table-bordered table-hover'>"
                html += "<thead class='thead-light'>"
                html += "<tr><th>VPC名称</th><th>VPC ID</th><th>CIDR</th></tr>"
                html += "</thead>"
                html += "<tbody>"
                for vpc in vpc_resources:
                    html += "<tr>"
                    html += f"<td><strong>{vpc.get('vpc', '未命名')}</strong></td>"
                    html += f"<td><code>{vpc.get('vpcid', '')}</code></td>"
                    html += f"<td><span class='badge badge-light'>{vpc.get('vpccidr', '')}</span></td>"
                    html += "</tr>"
                html += "</tbody>"
                html += "</table>"
                html += "</div>"
            
            # 添加子网资源表格
            subnet_resources = details.get('subnet_resources', [])
            if subnet_resources:
                html += f"<div class='card-header bg-info text-white'><h3 class='mb-0'><i class='fas fa-sitemap mr-2'></i>子网资源 ({len(subnet_resources)}个)</h3></div>"
                html += "<div class='card-body table-responsive'>"
                html += "<table class='table table-striped table-bordered table-hover'>"
                html += "<thead class='thead-light'>"
                html += "<tr><th>子网名称</th><th>子网ID</th><th>所属VPC</th><th>CIDR</th></tr>"
                html += "</thead>"
                html += "<tbody>"
                for subnet in subnet_resources:
                    html += "<tr>"
                    html += f"<td><strong>{subnet.get('subnet', '未命名')}</strong></td>"
                    html += f"<td><code>{subnet.get('subnetid', '')}</code></td>"
                    html += f"<td><code>{subnet.get('subnetvpc', '')}</code></td>"
                    html += f"<td><span class='badge badge-light'>{subnet.get('subnetcidr', '')}</span></td>"
                    html += "</tr>"
                html += "</tbody>"
                html += "</table>"
                html += "</div>"
            
            # 添加IAM资源表格
            iam_resources = details.get('iam_resources', [])
            if iam_resources:
                html += f"<div class='card-header bg-info text-white'><h3 class='mb-0'><i class='fas fa-users-cog mr-2'></i>IAM用户资源 ({len(iam_resources)}个)</h3></div>"
                html += "<div class='card-body table-responsive'>"
                html += "<table class='table table-striped table-bordered table-hover'>"
                html += "<thead class='thead-light'>"
                html += "<tr><th>用户名</th><th>用户ID</th><th>ARN</th></tr>"
                html += "</thead>"
                html += "<tbody>"
                for iam in iam_resources:
                    html += "<tr>"
                    html += f"<td><strong>{iam.get('iam_user', '未命名')}</strong></td>"
                    html += f"<td><code>{iam.get('iamid', '')}</code></td>"
                    html += f"<td><small class='text-muted'>{iam.get('iamarn', '')}</small></td>"
                    html += "</tr>"
                html += "</tbody>"
                html += "</table>"
                html += "</div>"
            
            if not vpc_resources and not subnet_resources and not iam_resources:
                html += "<div class='card-body'><div class='alert alert-warning'><i class='fas fa-exclamation-triangle mr-2'></i>暂无资源信息</div></div>"
            
            html += "</div>"
            
            # 返回资源详情
            return jsonify({
                "success": True,
                "details": details,
                "table": html
            })
            
        except Exception as e:
            self.logger.error(f"获取查询详情出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"获取查询详情失败: {str(e)}"}), 500

    def update_deployid_prefix(self):
        """更新所有deployid记录的前缀从DP改为QR"""
        try:
            self.logger.info("开始更新deployid前缀从DP到QR")
            
            # 调用模型方法更新前缀
            success = self.cloud_model.update_deploy_id_prefix()
            
            if success:
                return jsonify({
                    "success": True,
                    "message": "成功更新所有deployid的前缀从DP到QR"
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "更新deployid前缀失败"
                }), 500
        except Exception as e:
            self.logger.error(f"更新deployid前缀时出错: {str(e)}", exc_info=True)
            return jsonify({
                "success": False,
                "error": f"更新deployid前缀时发生错误: {str(e)}"
            }), 500 