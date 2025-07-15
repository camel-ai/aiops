import logging
from typing import Dict, Any, Optional
from flask import request, jsonify, session
from models.deploy_model import DeployModel
from config.config import Config
import json
import re
import random
import string
import time
import os
import datetime
import subprocess
import threading
import traceback

class DeployController:
    """云资源部署控制器类，处理与云资源部署相关的请求"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 获取应用根目录的绝对路径
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.logger.info(f"应用根目录的绝对路径: {self.base_dir}")
        
        # 初始化云资源部署模型
        self.deploy_model = DeployModel({
            'host': config.db_host,
            'user': config.db_user,
            'password': config.db_password,
            'database': config.db_name
        })
        
        # 确保clouddeploy表存在
        self.deploy_model.init_table()
        
    def generate_deploy_id(self) -> str:
        """生成18位部署ID
        
        格式: 前缀 + 时间戳 + 随机字符
        
        Returns:
            18位部署ID
        """
        prefix = "DP"  # 部署前缀
        timestamp = int(time.time())  # 当前时间戳
        timestamp_str = str(timestamp)[-10:]  # 取时间戳后10位
        
        # 计算需要的随机字符数量(18 - 前缀长度 - 时间戳长度)
        random_length = 18 - len(prefix) - len(timestamp_str)
        
        # 生成随机字符串(包含字母数字)
        random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=random_length))
        
        # 组合部署ID
        deploy_id = f"{prefix}{timestamp_str}{random_chars}"
        
        return deploy_id
        
    def handle_deployment_request(self):
        """处理部署请求
        
        当用户发送包含"@部署"的消息时，返回一个表单，让用户填写AK/SK等信息
        """
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
            
            # 检查消息是否包含@部署
            if '@部署' not in message:
                return jsonify({"error": "无效的部署请求"}), 400
            
            # 生成部署ID
            deploy_id = self.generate_deploy_id()
                
            # 构建响应
            response = {
                "type": "deployment_form",
                "message": f"您本次部署ID：{deploy_id} ； 您本次部署项目：{project} ； 您本次部署云：{cloud} ； 请输入AKSK：",
                "form": {
                    "fields": [
                        {"name": "ak", "label": "Access Key", "type": "text"},
                        {"name": "sk", "label": "Secret Key", "type": "password"}
                    ],
                    "submit_text": "确定",
                    "cancel_text": "取消",
                    "metadata": {
                        "user_id": user_id,
                        "username": username,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                }
            }
            
            return jsonify(response)
        except Exception as e:
            self.logger.error(f"处理部署请求时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理请求时发生错误: {str(e)}"}), 500

    def save_cloud_config(self):
        """保存云部署配置信息
        
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
            self.logger.info(f"接收到的表单数据: 用户={current_username}, 项目={project}, 云={cloud}, 部署ID={deploy_id}")
            
            if not all([current_user_id, current_username, project, cloud, ak, sk]):
                return jsonify({"error": "请提供完整的配置信息"}), 400
            
            # 检查部署ID
            if not deploy_id:
                # 如果没有部署ID，生成一个
                deploy_id = self.generate_deploy_id()
                self.logger.warning(f"表单中缺少部署ID，已生成新ID: {deploy_id}")
            
            # 调试部署ID
            self.logger.info(f"即将保存的部署ID: {deploy_id}")
            
            # 显式声明部署ID作为单独变量，避免引用问题
            deployid_to_save = str(deploy_id).strip()
            self.logger.info(f"最终使用的部署ID: {deployid_to_save}, 类型: {type(deployid_to_save)}")
            
            # 进行额外检查，确保不会传递空的部署ID
            if not deployid_to_save:
                deployid_to_save = self.generate_deploy_id()
                self.logger.warning(f"生成的部署ID为空，重新生成: {deployid_to_save}")
            
            # 保存云配置信息，显式设置force_insert=True确保始终创建新记录
            # 包装在try-except中，以便捕获并记录数据库错误
            try:
                success = self.deploy_model.save_cloud_config(
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
                self.logger.info(f"成功保存云部署配置: 项目={project}, 云={cloud}, 部署ID={deployid_to_save}")
                
                # 验证保存结果
                try:
                    configs = self.deploy_model.get_cloud_config(
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
                                self.logger.info(f"找到匹配的部署ID记录: {saved_deployid}")
                                found_deployid = True
                        
                        if not found_deployid:
                            self.logger.warning(f"未找到匹配部署ID的记录: {deployid_to_save}")
                            if configs:
                                self.logger.info(f"找到的第一条配置: {configs[0]}")
                except Exception as verify_error:
                    self.logger.error(f"验证保存结果时出错: {str(verify_error)}")
                
                # 构建响应
                response = {
                    "type": "deployment_options",
                    "message": f"AK/SK 已成功保存。请选择您要执行的操作：",
                    "options": [
                        {"id": "deploy", "text": "部署云资源", "action": "deploy_resources"}
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
                self.logger.error(f"保存云部署配置失败: 项目={project}, 云={cloud}, 部署ID={deployid_to_save}")
                return jsonify({"error": "保存配置信息失败"}), 500
        except Exception as e:
            self.logger.error(f"处理表单提交时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理表单时发生错误: {str(e)}"}), 500 

    def handle_cloud_option_selection(self):
        """处理云资源部署操作选项选择"""
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
            
            self.logger.info(f"处理选项: {option_id}, 用户: {current_user_id}, 项目: {project}, 云: {cloud}, 部署ID: {deploy_id}")
            
            if option_id == 'deploy':
                # 部署云资源前，让用户选择区域
                # 检查云配置是否存在
                configs = self.deploy_model.get_cloud_config(
                    user_id=current_user_id,
                    project=project,
                    cloud=cloud
                )
                
                if not configs:
                    return jsonify({
                        "reply": "未找到云配置信息，请先配置AK/SK"
                    })
                
                # 获取该云的所有可用区域
                regions = self.deploy_model.get_regions_by_cloud(cloud)
                self.logger.info(f"为云{cloud}获取到区域列表: {regions}")
                
                # 确保始终返回所有可用区域
                if len(regions) <= 1:
                    # 如果区域列表为空或只有一个元素，使用默认区域列表
                    regions = self.deploy_model._get_default_regions_for_cloud(cloud)
                    self.logger.warning(f"区域列表不完整，使用默认区域列表: {regions}")
                
                # 返回区域选择下拉菜单
                return jsonify({
                    "reply": f"请选择要部署的区域：",
                    "region_selection": True,
                    "regions": regions,
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                })
            else:
                return jsonify({
                    "reply": "未知的操作选项"
                })
        except Exception as e:
            self.logger.error(f"处理选项选择时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理选项选择时发生错误: {str(e)}"}), 500

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
            
            region = data.get('region', '')
            project = data.get('project', '')
            cloud = data.get('cloud', '')
            deploy_id = data.get('deploy_id', '')
            
            self.logger.info(f"处理区域选择: 用户={current_user_id}, 项目={project}, 云={cloud}, 区域={region}, 部署ID={deploy_id}")
            
            if not all([current_user_id, project, cloud, region]):
                return jsonify({
                    "error": "缺少必要的参数"
                }), 400
            
            # 检查云配置是否存在
            configs = self.deploy_model.get_cloud_config(
                user_id=current_user_id,
                project=project,
                cloud=cloud
            )
            
            if not configs:
                return jsonify({
                    "reply": "未找到云配置信息，请先配置AK/SK"
                })
            
            # 在保存区域前确保有部署ID
            if not deploy_id and configs:
                deploy_id = configs[0].get('deployid', '')
                if not deploy_id:
                    deploy_id = self.generate_deploy_id()
                    self.logger.warning(f"区域选择中缺少部署ID，已生成新ID: {deploy_id}")
            
            self.logger.info(f"保存区域信息，部署ID: {deploy_id}, 区域: {region}")
            
            # 获取要更新的配置（使用最新的一条记录）
            config = configs[0]
            
            # 更新区域信息到数据库
            updates = {
                'region': region
            }
            
            success = self.deploy_model.update_cloud_resources(
                user_id=current_user_id,
                project=project,
                cloud=cloud,
                resources=updates,
                deployid=deploy_id
            )
            
            # 构建部署信息文本，而不是显示资源
            deploy_text = f"**本次部署信息如下：**\n\n"
            deploy_text += f"- 项目：{project}\n"
            deploy_text += f"- 云: {cloud}\n"
            deploy_text += f"- AK: {config.get('ak', '')}\n"  # 完整显示AK
            deploy_text += f"- SK: {config.get('sk', '')}\n"  # 完整显示SK
            deploy_text += f"- 部署区域：{region}\n"
            deploy_text += f"- 部署ID：{deploy_id}\n"
            
            return jsonify({
                "reply": deploy_text,
                "region": region,
                "deploy_id": deploy_id,
                "resource_selection": True,  # 添加标志以显示资源选择界面
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
                    "region": region,
                    "deploy_id": deploy_id
                }
            })
        except Exception as e:
            self.logger.error(f"处理区域选择时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理区域选择时发生错误: {str(e)}"}), 500

    def handle_resource_selection(self):
        """处理部署资源选择"""
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
            
            selected_resources = data.get('selected_resources', [])
            project = data.get('project', '')
            cloud = data.get('cloud', '')
            region = data.get('region', '')
            deploy_id = data.get('deploy_id', '')
            
            self.logger.info(f"处理资源选择: 用户={current_user_id}, 项目={project}, 云={cloud}, 资源={selected_resources}, 部署ID={deploy_id}")
            
            if not all([current_user_id, project, cloud]) or not selected_resources:
                return jsonify({
                    "error": "缺少必要的参数"
                }), 400
            
            # 检查云配置是否存在
            configs = self.deploy_model.get_cloud_config(
                user_id=current_user_id,
                project=project,
                cloud=cloud
            )
            
            if not configs:
                return jsonify({
                    "reply": "未找到云配置信息，请先配置AK/SK"
                })
            
            # 在保存资源选择前确保有部署ID
            if not deploy_id and configs:
                deploy_id = configs[0].get('deployid', '')
                if not deploy_id:
                    deploy_id = self.generate_deploy_id()
                    self.logger.warning(f"资源选择中缺少部署ID，已生成新ID: {deploy_id}")
            
            # 获取要更新的配置（使用最新的一条记录）
            config = configs[0]
            
            # 特殊处理独占选项 - 着陆区和AIOPS
            if 'landing_zone' in selected_resources:
                # 处理一键部署合规着陆区
                self.logger.info(f"处理一键部署合规着陆区: 部署ID={deploy_id}")
                
                # 返回部署开始的消息
                return jsonify({
                    "reply": f"<div class='deployment-message'>已开始部署合规着陆区，这将包含VPC、子网、IAM用户和策略等所有必要资源。<br><br>部署ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{config.get('region', '未指定')}</strong><br><br>部署预计需要5-10分钟完成，完成后可在历史部署中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                })
            elif 'aiops' in selected_resources:
                # 处理AIOPS部署
                self.logger.info(f"处理AIOPS部署: 部署ID={deploy_id}")
                
                # 返回AIOPS部署开始的消息
                return jsonify({
                    "reply": f"<div class='deployment-message'>已开始部署AIOPS资源，这将包含云监控、日志分析、告警系统和AI运维资源。<br><br>部署ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{config.get('region', '未指定')}</strong><br><br>AIOPS部署预计需要8-15分钟完成，完成后可在历史部署中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                })
            else:
                # 处理普通资源选择
                self.logger.info(f"处理普通资源选择: 资源={selected_resources}, 部署ID={deploy_id}")
                
                # 检查是否需要显示资源配置表单
                if len(selected_resources) == 1:
                    resource = selected_resources[0]
                    
                    # VPC配置表单
                    if resource == 'vpc':
                        self.logger.info(f"返回VPC配置表单: 部署ID={deploy_id}")
                        return jsonify({
                            "reply": "请配置VPC资源:",
                            "form": {
                                "title": "VPC配置",
                                "fields": [
                                    {"name": "vpc_name", "label": "VPC名称", "type": "text", "value": f"{project}-vpc", "required": True},
                                    {"name": "vpc_cidr", "label": "VPC CIDR", "type": "text", "value": "10.0.0.0/16", "required": True}
                                ],
                                "submit_text": "部署VPC"
                            },
                            "metadata": {
                                "user_id": current_user_id,
                                "project": project,
                                "cloud": cloud,
                                "region": region,
                                "deploy_id": deploy_id,
                                "resource_type": "vpc",
                                "selected_resources": selected_resources
                            }
                        })
                    
                    # 子网配置表单
                    elif resource == 'subnet':
                        self.logger.info(f"返回子网配置表单: 部署ID={deploy_id}")
                        return jsonify({
                            "reply": "请配置子网资源:",
                            "form": {
                                "title": "子网配置",
                                "fields": [
                                    {"name": "subnet_name", "label": "子网名称", "type": "text", "value": f"{project}-subnet", "required": True},
                                    {"name": "subnet_cidr", "label": "子网CIDR", "type": "text", "value": "10.0.1.0/24", "required": True},
                                    {"name": "subnet_vpc", "label": "所属VPC", "type": "text", "value": f"{project}-vpc", "required": True}
                                ],
                                "submit_text": "部署子网"
                            },
                            "metadata": {
                                "user_id": current_user_id,
                                "project": project,
                                "cloud": cloud,
                                "region": region,
                                "deploy_id": deploy_id,
                                "resource_type": "subnet",
                                "selected_resources": selected_resources
                            }
                        })
                    
                    # IAM用户配置表单
                    elif resource == 'iam_user':
                        self.logger.info(f"返回IAM用户配置表单: 部署ID={deploy_id}")
                        return jsonify({
                            "reply": "请配置IAM用户:",
                            "form": {
                                "title": "IAM用户配置",
                                "fields": [
                                    {"name": "iam_user_name", "label": "IAM用户名", "type": "text", "value": f"{project}-user", "required": True}
                                ],
                                "submit_text": "创建IAM用户"
                            },
                            "metadata": {
                                "user_id": current_user_id,
                                "project": project,
                                "cloud": cloud,
                                "region": region,
                                "deploy_id": deploy_id,
                                "resource_type": "iam_user",
                                "selected_resources": selected_resources
                            }
                        })
                    
                    # IAM用户组配置表单
                    elif resource == 'iam_group':
                        self.logger.info(f"返回IAM用户组配置表单: 部署ID={deploy_id}")
                        return jsonify({
                            "reply": "请配置IAM用户组:",
                            "form": {
                                "title": "IAM用户组配置",
                                "fields": [
                                    {"name": "iam_group_name", "label": "IAM用户组名称", "type": "text", "value": f"{project}-group", "required": True}
                                ],
                                "submit_text": "创建IAM用户组"
                            },
                            "metadata": {
                                "user_id": current_user_id,
                                "project": project,
                                "cloud": cloud,
                                "region": region,
                                "deploy_id": deploy_id,
                                "resource_type": "iam_group",
                                "selected_resources": selected_resources
                            }
                        })
                    
                    # IAM策略配置表单
                    elif resource == 'iam_policy':
                        self.logger.info(f"返回IAM策略配置表单: 部署ID={deploy_id}")
                        return jsonify({
                            "reply": "请配置IAM策略:",
                            "form": {
                                "title": "IAM策略配置",
                                "fields": [
                                    {"name": "iam_policy_name", "label": "IAM策略名称", "type": "text", "value": f"{project}-policy", "required": True},
                                    {"name": "iam_policy_description", "label": "策略描述", "type": "text", "value": f"{project}项目的访问策略", "required": False},
                                    {"name": "iam_policy_content", "label": "策略内容", "type": "textarea", "value": '{\n  "Version": "2012-10-17",\n  "Statement": [\n    {\n      "Effect": "Allow",\n      "Action": [\n        "s3:GetObject",\n        "s3:PutObject",\n        "s3:ListBucket"\n      ],\n      "Resource": "*"\n    }\n  ]\n}', "required": True}
                                ],
                                "submit_text": "创建IAM策略"
                            },
                            "metadata": {
                                "user_id": current_user_id,
                                "project": project,
                                "cloud": cloud,
                                "region": region,
                                "deploy_id": deploy_id,
                                "resource_type": "iam_policy",
                                "selected_resources": selected_resources
                            }
                        })
                    
                    # S3存储桶配置表单
                    elif resource == 's3':
                        self.logger.info(f"返回S3存储桶配置表单: 部署ID={deploy_id}")
                        return jsonify({
                            "reply": "请配置S3存储桶:",
                            "form": {
                                "title": "S3存储桶配置",
                                "fields": [
                                    {"name": "s3_bucket_name", "label": "存储桶名称", "type": "text", "value": f"{project.lower()}-bucket-{deploy_id.lower()}", "required": True}
                                ],
                                "submit_text": "创建S3存储桶"
                            },
                            "metadata": {
                                "user_id": current_user_id,
                                "project": project,
                                "cloud": cloud,
                                "region": region,
                                "deploy_id": deploy_id,
                                "resource_type": "s3",
                                "selected_resources": selected_resources
                            }
                        })
                
                # 构建资源列表文本
                resource_list = "<ul>"
                for resource in selected_resources:
                    resource_text = resource
                    if resource == 'vpc':
                        resource_text = 'VPC'
                    elif resource == 'subnet':
                        resource_text = '子网'
                    elif resource == 's3':
                        resource_text = 'S3存储桶'
                    elif resource == 'iam_user':
                        resource_text = 'IAM用户'
                    elif resource == 'iam_group':
                        resource_text = 'IAM用户组'
                    elif resource == 'iam_policy':
                        resource_text = 'IAM策略'
                    
                    resource_list += f"<li>{resource_text}</li>"
                resource_list += "</ul>"
                
                # 返回资源选择确认消息
                return jsonify({
                    "reply": f"<div class='deployment-message'>已开始部署以下资源：<br>{resource_list}<br>部署ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{config.get('region', '未指定')}</strong><br><br>部署预计需要3-5分钟完成，完成后可在历史部署中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                })
        except Exception as e:
            self.logger.error(f"处理资源选择时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理资源选择时发生错误: {str(e)}"}), 500

    def get_user_deployments(self):
        """获取当前用户的所有部署历史"""
        try:
            # 从请求中获取用户ID
            current_user_id = request.current_user.get('user_id', 0)
            self.logger.info(f"获取用户 {current_user_id} 的部署历史")
            
            # 获取用户部署历史
            deployments = self.deploy_model.get_user_deployments(current_user_id)
            
            # 返回部署历史列表
            return jsonify({
                "success": True,
                "deployments": deployments
            })
            
        except Exception as e:
            self.logger.error(f"获取用户部署历史出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"获取部署历史失败: {str(e)}"}), 500

    def get_deployment_details(self):
        """获取指定部署ID的资源详情"""
        try:
            # 获取部署ID
            deploy_id = request.args.get('deploy_id')
            if not deploy_id:
                return jsonify({"error": "缺少部署ID参数"}), 400
            
            self.logger.info(f"获取部署ID {deploy_id} 的资源详情")
            
            # 获取部署资源详情
            details = self.deploy_model.get_deployment_details(deploy_id)
            
            # 检查是否找到资源
            if not details['deployment_info']:
                return jsonify({"error": f"未找到部署ID为 {deploy_id} 的资源"}), 404
            
            # 格式化结果为表格展示
            deployment_info = details['deployment_info']
            resources = details['resources']
            
            # 构建HTML表格
            html = "<div class='deployment-details card shadow-sm'>"
            
            # 基本信息表格
            html += "<div class='card-header bg-primary text-white'><h3 class='mb-0'><i class='fas fa-rocket mr-2'></i>部署基本信息</h3></div>"
            html += "<div class='card-body'>"
            html += "<table class='table table-striped table-bordered table-hover'>"
            html += "<tbody>"
            html += f"<tr><th width='30%' class='bg-light'>部署ID</th><td><code>{deployment_info.get('deployid', '')}</code></td></tr>"
            html += f"<tr><th class='bg-light'>项目</th><td>{deployment_info.get('project', '')}</td></tr>"
            html += f"<tr><th class='bg-light'>云平台</th><td><span class='badge badge-info'>{deployment_info.get('cloud', '')}</span></td></tr>"
            html += f"<tr><th class='bg-light'>区域</th><td><span class='badge badge-secondary'>{deployment_info.get('region', '')}</span></td></tr>"
            html += f"<tr><th class='bg-light'>创建时间</th><td>{deployment_info.get('created_at', '')}</td></tr>"
            html += f"<tr><th class='bg-light'>更新时间</th><td>{deployment_info.get('updated_at', '')}</td></tr>"
            html += "</tbody>"
            html += "</table>"
            html += "</div>"
            
            # 资源列表表格
            if resources:
                html += "<div class='card-header bg-info text-white'><h3 class='mb-0'><i class='fas fa-cubes mr-2'></i>已部署资源</h3></div>"
                html += "<div class='card-body table-responsive'>"
                html += "<table class='table table-striped table-bordered table-hover'>"
                html += "<thead class='thead-light'>"
                html += "<tr><th>资源类型</th><th>资源名称</th><th>资源ID</th><th>状态</th></tr>"
                html += "</thead>"
                html += "<tbody>"
                
                for resource in resources:
                    resource_type = self._get_resource_type_name(resource['type'])
                    resource_icon = self._get_resource_icon(resource['type'])
                    
                    html += "<tr>"
                    html += f"<td>{resource_icon} {resource_type}</td>"
                    html += f"<td><strong>{resource['name']}</strong></td>"
                    html += f"<td><code>{resource['id']}</code></td>"
                    html += f"<td><span class='badge badge-success'><i class='fas fa-check mr-1'></i>已部署</span></td>"
                    html += "</tr>"
                
                html += "</tbody>"
                html += "</table>"
                html += "</div>"
            else:
                html += "<div class='card-body'><div class='alert alert-warning'><i class='fas fa-exclamation-triangle mr-2'></i>暂无部署资源</div></div>"
            
            html += "</div>"
            
            return jsonify({
                "success": True,
                "details": {
                    "deployment_info": deployment_info,
                    "resources": resources
                },
                "table": html
            })
            
        except Exception as e:
            self.logger.error(f"获取部署详情出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"获取部署详情失败: {str(e)}"}), 500

    def _get_resource_type_name(self, resource_type: str) -> str:
        """转换资源类型为友好显示名称"""
        type_names = {
            'vpc': 'VPC',
            'subnet': '子网',
            'object': 'S3存储桶',
            'iam_user': 'IAM用户',
            'iam_user_group': 'IAM用户组',
            'iam_user_policy': 'IAM策略'
        }
        return type_names.get(resource_type, resource_type)
        
    def _get_resource_icon(self, resource_type: str) -> str:
        """为不同资源类型提供对应的Font Awesome 图标"""
        type_icons = {
            'vpc': '<i class="fas fa-network-wired"></i>',
            'subnet': '<i class="fas fa-sitemap"></i>',
            'object': '<i class="fas fa-database"></i>',
            'iam_user': '<i class="fas fa-user"></i>',
            'iam_user_group': '<i class="fas fa-users"></i>',
            'iam_user_policy': '<i class="fas fa-file-contract"></i>',
            's3': '<i class="fas fa-database"></i>'
        }
        return type_icons.get(resource_type, '<i class="fas fa-cube"></i>')
        
    def handle_resource_config_form(self):
        """处理资源配置表单提交"""
        try:
            data = request.get_json()
            self.logger.info(f"接收到资源配置表单数据: {data}")
            
            if not data:
                self.logger.error("表单数据为空")
                return jsonify({"error": "请提供表单数据"}), 400
            
            # 获取当前登录用户信息
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
            
            # 如果仍然无法获取用户信息，则尝试从表单数据中获取
            if current_user_id == 0:
                current_user_id = data.get('user_id', 0)
                if current_user_id > 0:
                    self.logger.info(f"从表单数据获取用户ID: {current_user_id}")
            
            # 提取表单数据
            form_data = data.get('form_data', {})
            metadata = data.get('metadata', {})
            
            self.logger.info(f"解析表单数据: form_data={form_data}, metadata={metadata}")
            
            # 必要的字段检查
            if not form_data:
                self.logger.error("表单数据form_data为空")
                return jsonify({"error": "表单数据form_data不能为空"}), 400
                
            if not metadata:
                self.logger.error("表单元数据metadata为空")
                return jsonify({"error": "表单元数据metadata不能为空"}), 400
            
            # 提取元数据
            project = metadata.get('project', '')
            cloud = metadata.get('cloud', '')
            region = metadata.get('region', '')
            deploy_id = metadata.get('deploy_id', '')
            resource_type = metadata.get('resource_type', '')
            
            self.logger.info(f"处理{resource_type}配置: 用户={current_user_id}, 项目={project}, 云={cloud}, 区域={region}, 部署ID={deploy_id}")
            
            # 资源类型特定处理
            if resource_type == 'vpc':
                vpc_name = form_data.get('vpc_name', '')
                vpc_cidr = form_data.get('vpc_cidr', '')
                
                if not vpc_name or not vpc_cidr:
                    return jsonify({"error": "VPC名称和CIDR不能为空"}), 400
                
                self.logger.info(f"部署VPC: 名称={vpc_name}, CIDR={vpc_cidr}")
                
                # 生成Terraform配置文件
                # 创建部署目录（使用绝对路径）
                tf_dir = os.path.join(self.base_dir, "deploy", deploy_id)
                tf_file = os.path.join(tf_dir, "main.tf")
                
                # 确保目录存在
                os.makedirs(tf_dir, exist_ok=True)
                self.logger.info(f"创建VPC部署目录（绝对路径）: {tf_dir}")
                
                # 根据云平台选择不同的Terraform模板
                if cloud == 'AWS':
                    # 查询配置信息以获取AK/SK
                    configs = self.deploy_model.get_cloud_config(
                        user_id=current_user_id,
                        project=project,
                        cloud=cloud,
                    )
                    
                    if not configs:
                        return jsonify({"error": "无法获取AK/SK信息"}), 500
                    
                    ak = configs[0].get('ak', '')
                    sk = configs[0].get('sk', '')
                    
                    if not ak or not sk:
                        return jsonify({"error": "AK/SK信息不完整"}), 500
                    
                    terraform_template = f"""
provider "aws" {{
  region = "{region}"
  access_key = "{ak}"
  secret_key = "{sk}"
}}

resource "aws_vpc" "{vpc_name}" {{
  cidr_block = "{vpc_cidr}"
  
  tags = {{
    Name = "{vpc_name}"
    Project = "{project}"
    DeployID = "{deploy_id}"
  }}
}}

output "vpc_id" {{
  value = aws_vpc.{vpc_name}.id
}}

output "vpc_name" {{
  value = "{vpc_name}"
}}

output "vpc_cidr" {{
  value = "{vpc_cidr}"
}}
"""
                elif cloud == 'Azure':
                    # 获取AK/SK
                    configs = self.deploy_model.get_cloud_config(
                        user_id=current_user_id,
                        project=project,
                        cloud=cloud,
                    )
                    
                    if not configs:
                        return jsonify({"error": "无法获取AK/SK信息"}), 500
                    
                    ak = configs[0].get('ak', '')
                    sk = configs[0].get('sk', '')
                    
                    terraform_template = f"""
provider "azurerm" {{
  features {{}}
  
  subscription_id = "{ak}"
  client_secret = "{sk}"
}}

resource "azurerm_resource_group" "{project}_group" {{
  name     = "{project}-rg"
  location = "{region}"
}}

resource "azurerm_virtual_network" "{vpc_name}" {{
  name                = "{vpc_name}"
  address_space       = ["{vpc_cidr}"]
  location            = azurerm_resource_group.{project}_group.location
  resource_group_name = azurerm_resource_group.{project}_group.name
  
  tags = {{
    Project = "{project}"
    DeployID = "{deploy_id}"
  }}
}}

output "vnet_id" {{
  value = azurerm_virtual_network.{vpc_name}.id
}}

output "vpc_name" {{
  value = "{vpc_name}"
}}

output "vpc_cidr" {{
  value = "{vpc_cidr}"
}}
"""
                else:
                    # 默认使用AWS模板
                    # 获取AK/SK
                    configs = self.deploy_model.get_cloud_config(
                        user_id=current_user_id,
                        project=project,
                        cloud=cloud,
                    )
                    
                    if not configs:
                        return jsonify({"error": "无法获取AK/SK信息"}), 500
                    
                    ak = configs[0].get('ak', '')
                    sk = configs[0].get('sk', '')
                    
                    terraform_template = f"""
provider "aws" {{
  region = "{region}"
  access_key = "{ak}"
  secret_key = "{sk}"
}}

resource "aws_vpc" "{vpc_name}" {{
  cidr_block = "{vpc_cidr}"
  
  tags = {{
    Name = "{vpc_name}"
    Project = "{project}"
    DeployID = "{deploy_id}"
  }}
}}

output "vpc_id" {{
  value = aws_vpc.{vpc_name}.id
}}

output "vpc_name" {{
  value = "{vpc_name}"
}}

output "vpc_cidr" {{
  value = "{vpc_cidr}"
}}
"""

                # 写入Terraform配置文件
                try:
                    with open(tf_file, 'w') as f:
                        f.write(terraform_template)
                        
                    self.logger.info(f"已生成Terraform配置文件: {tf_file}")
                except Exception as e:
                    self.logger.error(f"生成Terraform配置文件失败: {e}")
                    return jsonify({"error": f"生成Terraform配置文件失败: {str(e)}"}), 500
                
                # 先定义日志文件路径
                log_file = os.path.join(tf_dir, "deploy.log")
                try:
                    with open(log_file, 'w') as f:
                        current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        f.write(f"开始部署VPC: {vpc_name}\n")
                        f.write(f"时间: {current_time}\n")
                        f.write(f"项目: {project}\n")
                        f.write(f"云平台: {cloud}\n")
                        f.write(f"区域: {region}\n")
                        f.write(f"部署ID: {deploy_id}\n")
                        f.write("部署状态: 进行中\n")
                        
                    self.logger.info(f"已创建部署日志文件: {log_file}")
                except Exception as e:
                    self.logger.error(f"创建部署日志文件失败: {e}")
                    
                # 更新部署状态为进行中
                self.deploy_model.update_deployment_status(
                    deploy_id=deploy_id,
                    status="in_progress",
                    user_id=current_user_id
                )
                
                # 启动实际的Terraform部署（异步）
                # 保存self引用，以便在线程中使用
                controller_ref = self
                
                # 创建部署状态文件，用于前端轮询检查状态
                status_file = os.path.join(tf_dir, "status.json")
                try:
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'in_progress',
                            'deploy_id': deploy_id,
                            'message': '部署已开始',
                            'updated_at': datetime.datetime.now().isoformat()
                        }, f)
                except Exception as e:
                    self.logger.error(f"创建状态文件失败: {e}")
                
                def run_terraform_deployment(deploy_dir, log_file, status_file, deploy_id, user_id, project, cloud, region, vpc_name, vpc_cidr):
                    """在新线程中运行Terraform部署"""
                    try:
                        import json  # 确保在函数内部导入json模块
                        import datetime  # 再次导入以确保可访问
                        # 初始化Terraform
                        controller_ref.logger.info(f"开始执行Terraform部署: {deploy_dir}")
                        
                        # 记录操作到日志文件
                        with open(log_file, 'a') as f:
                            f.write(f"开始执行Terraform部署\n")
                            f.write(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                            
                            # 初始化
                            init_cmd = ["terraform", "init"]
                            controller_ref.logger.info(f"执行命令: {' '.join(init_cmd)}")
                            f.write(f"执行: {' '.join(init_cmd)}\n")
                            
                            init_process = subprocess.Popen(
                                init_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = init_process.communicate()
                            f.write(f"--- 初始化输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 初始化错误 ---\n")
                                f.write(stderr)
                            
                            if init_process.returncode != 0:
                                f.write(f"初始化失败，返回代码: {init_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform初始化失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"VPC部署失败: Terraform初始化错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 计划
                            plan_cmd = ["terraform", "plan", "-out=tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(plan_cmd)}")
                            f.write(f"\n执行: {' '.join(plan_cmd)}\n")
                            
                            plan_process = subprocess.Popen(
                                plan_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = plan_process.communicate()
                            f.write(f"--- 计划输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 计划错误 ---\n")
                                f.write(stderr)
                            
                            if plan_process.returncode != 0:
                                f.write(f"计划失败，返回代码: {plan_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform计划失败: {stderr}")
                                # 记录错误信息到日志
                                f.write(f"ERROR: Terraform计划失败: {stderr}\n")
                                
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"VPC部署失败: Terraform计划错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                # 将错误消息写入到一个特殊的错误文件，前端可以查询
                                error_file = f"{deploy_dir}/error.txt"
                                try:
                                    with open(error_file, 'w') as ef:
                                        ef.write(f"ERROR: Terraform计划失败\n{stderr}")
                                except Exception as e:
                                    controller_ref.logger.error(f"写入错误文件失败: {str(e)}")
                                
                                return
                            
                            # 应用
                            apply_cmd = ["terraform", "apply", "-auto-approve", "tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(apply_cmd)}")
                            f.write(f"\n执行: {' '.join(apply_cmd)}\n")
                            
                            apply_process = subprocess.Popen(
                                apply_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = apply_process.communicate()
                            f.write(f"--- 应用输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 应用错误 ---\n")
                                f.write(stderr)
                            
                            if apply_process.returncode != 0:
                                f.write(f"应用失败，返回代码: {apply_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform应用失败: {stderr}")
                                # 记录错误信息到日志
                                f.write(f"ERROR: Terraform应用失败: {stderr}\n")
                                
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"VPC部署失败: Terraform应用错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                # 将错误消息写入到一个特殊的错误文件，前端可以查询
                                error_file = f"{deploy_dir}/error.txt"
                                try:
                                    with open(error_file, 'w') as ef:
                                        ef.write(f"ERROR: Terraform应用失败\n{stderr}")
                                except Exception as e:
                                    controller_ref.logger.error(f"写入错误文件失败: {str(e)}")
                                
                                return
                            
                            # 部署完成，获取输出
                            output_cmd = ["terraform", "output", "-json"]
                            controller_ref.logger.info(f"执行命令: {' '.join(output_cmd)}")
                            f.write(f"\n执行: {' '.join(output_cmd)}\n")
                            
                            output_process = subprocess.Popen(
                                output_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = output_process.communicate()
                            f.write(f"--- 输出结果 ---\n")
                            f.write(stdout)
                            
                            # 解析输出结果
                            try:
                                output_data = json.loads(stdout)
                                vpc_id = output_data.get('vpc_id', {}).get('value', '')
                                vpc_name_output = output_data.get('vpc_name', {}).get('value', vpc_name)
                                vpc_cidr_output = output_data.get('vpc_cidr', {}).get('value', vpc_cidr)
                                
                                # 成功时才更新数据库中的VPC信息
                                updates = {
                                    'vpc': vpc_name_output,
                                    'vpcid': vpc_id,
                                    'vpccidr': vpc_cidr_output
                                }
                                
                                # 更新云配置信息
                                success = controller_ref.deploy_model.update_cloud_resources(
                                    user_id=user_id,
                                    project=project,
                                    cloud=cloud,
                                    resources=updates,
                                    deployid=deploy_id
                                )
                                
                                if success:
                                    controller_ref.logger.info(f"部署成功，已更新数据库: VPC={vpc_name_output}, ID={vpc_id}, CIDR={vpc_cidr_output}")
                                else:
                                    controller_ref.logger.error(f"部署成功但更新数据库失败")
                                
                                # 记录成功结果
                                f.write(f"\nVPC部署成功:\n")
                                f.write(f"  VPC名称: {vpc_name_output}\n")
                                f.write(f"  VPC ID: {vpc_id}\n")
                                f.write(f"  CIDR: {vpc_cidr_output}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'completed',
                                            'deploy_id': deploy_id,
                                            'vpc_id': vpc_id,
                                            'vpc_name': vpc_name_output,
                                            'vpc_cidr': vpc_cidr_output,
                                            'message': f"VPC部署成功 - ID: {vpc_id}",
                                            'output': f"VPC名称: {vpc_name_output}\nVPC ID: {vpc_id}\nCIDR: {vpc_cidr_output}",
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                    controller_ref.logger.info(f"状态文件已更新: {status_file} - VPC信息已写入")
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                            
                            except Exception as e:
                                f.write(f"\n解析输出结果失败: {str(e)}\n")
                                controller_ref.logger.error(f"解析Terraform输出失败: {str(e)}")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"解析输出失败: {str(e)}",
                                            'error': str(e),
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as write_err:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(write_err)}")
                            
                            # 更新部署状态为已完成
                            controller_ref.deploy_model.update_deployment_status(
                                deploy_id=deploy_id,
                                status="completed",
                            )
                            
                            f.write(f"\n部署完成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                            controller_ref.logger.info(f"Terraform部署完成: {deploy_dir}")
                            
                            # 部署成功后更新部署状态
                            controller_ref.deploy_model.update_deployment_status(
                                deploy_id=deploy_id,
                                status="completed",
                            )
                            
                            # 生成拓扑图
                            try:
                                # 确保部署目录存在
                                if os.path.exists(deploy_dir):
                                    # 生成拓扑图
                                    graph_cmd = ["terraform", "graph", "-type=plan"]
                                    dot_cmd = ["dot", "-Tpng", "-o", os.path.join(deploy_dir, "graph.png")]
                                    
                                    # 执行terraform graph并通过管道传递给dot命令
                                    controller_ref.logger.info(f"生成拓扑图: {' '.join(graph_cmd)} | {' '.join(dot_cmd)}")
                                    
                                    graph_process = subprocess.Popen(
                                        graph_cmd, 
                                        cwd=deploy_dir,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE
                                    )
                                    
                                    dot_process = subprocess.Popen(
                                        dot_cmd,
                                        cwd=deploy_dir,
                                        stdin=graph_process.stdout,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE
                                    )
                                    
                                    # 确保第一个进程的输出被第二个进程完全读取
                                    graph_process.stdout.close()
                                    
                                    # 获取dot进程的输出和错误
                                    stdout, stderr = dot_process.communicate()
                                    
                                    # 检查命令是否成功执行
                                    if dot_process.returncode == 0:
                                        controller_ref.logger.info(f"✅ 成功生成拓扑图: {os.path.join(deploy_dir, 'graph.png')}")
                                        
                                        # 将拓扑图信息添加到状态文件中
                                        try:
                                            with open(status_file, 'r') as sf:
                                                status_data = json.load(sf)
                                                
                                            # 添加拓扑图路径
                                            status_data['topology_graph'] = f"/api/files/deployments/{deploy_id}/graph.png"
                                            
                                            with open(status_file, 'w') as sf:
                                                json.dump(status_data, sf)
                                                
                                            controller_ref.logger.info(f"✅ 已更新状态文件: 添加拓扑图路径")
                                        except Exception as e:
                                            controller_ref.logger.error(f"更新拓扑图路径到状态文件失败: {str(e)}")
                                    else:
                                        controller_ref.logger.error(f"生成拓扑图失败: {stderr}")
                            except Exception as e:
                                controller_ref.logger.error(f"生成拓扑图过程中出错: {str(e)}", exc_info=True)
                            
                    except Exception as e:
                        controller_ref.logger.error(f"Terraform部署过程中出错: {str(e)}")
                        # 记录错误到日志文件
                        try:
                            with open(log_file, 'a') as f:
                                f.write(f"\n部署过程中出现错误: {str(e)}\n")
                        except:
                            pass
                        
                        # 更新状态为失败
                        controller_ref.deploy_model.update_deployment_status(
                            deploy_id=deploy_id,
                            status="failed",
                        )
                        
                        # 更新状态文件
                        try:
                            with open(status_file, 'w') as sf:
                                json.dump({
                                    'status': 'failed',
                                    'deploy_id': deploy_id,
                                    'message': f"VPC部署失败: {str(e)}",
                                    'error': str(e),
                                    'updated_at': datetime.datetime.now().isoformat()
                                }, sf)
                        except Exception as write_err:
                            controller_ref.logger.error(f"无法写入状态文件: {str(write_err)}")
                        
                        # 将错误消息写入到一个特殊的错误文件，前端可以查询
                        error_file = f"{deploy_dir}/error.txt"
                        try:
                            with open(error_file, 'w') as ef:
                                ef.write(str(e))
                        except Exception as err:
                            controller_ref.logger.error(f"写入错误文件失败: {str(err)}")
                
                # 启动部署线程
                terraform_thread = threading.Thread(
                    target=run_terraform_deployment,
                    args=(tf_dir, log_file, status_file, deploy_id, current_user_id, project, cloud, region, vpc_name, vpc_cidr),
                    daemon=True  # 作为守护线程运行，当主进程退出时自动终止
                )
                terraform_thread.start()
                self.logger.info(f"已启动Terraform部署线程: {tf_dir}")
                
                # 添加用于获取部署状态的路由信息
                status_route = f"/api/deploy/status?deploy_id={deploy_id}"
                
                # 返回部署成功消息
                return jsonify({
                    "reply": f"<div class='deployment-message'>VPC部署已开始:<br><ul><li>名称: {vpc_name}</li><li>CIDR: {vpc_cidr}</li></ul><br>部署ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{region}</strong><br><br>部署预计需要2-3分钟完成，完成后可在历史部署中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    },
                    "status_api": f"/api/deploy/status?deploy_id={deploy_id}"
                })
            
            elif resource_type == 'subnet':
                subnet_name = form_data.get('subnet_name', '')
                subnet_cidr = form_data.get('subnet_cidr', '')
                subnet_vpc = form_data.get('subnet_vpc', '')
                
                if not subnet_name or not subnet_cidr or not subnet_vpc:
                    return jsonify({"error": "子网名称、CIDR和所属VPC不能为空"}), 400
                
                self.logger.info(f"部署子网: 名称={subnet_name}, CIDR={subnet_cidr}, VPC={subnet_vpc}")
                
                # 创建部署目录
                deploy_dir = os.path.join(self.base_dir, "deploy", deploy_id)
                os.makedirs(deploy_dir, exist_ok=True)
                
                # 设置Terraform文件路径
                tf_file = f"{deploy_dir}/main.tf"
                log_file = f"{deploy_dir}/deploy.log"
                
                # 获取云配置（AK/SK）
                configs = self.deploy_model.get_cloud_config(
                    user_id=current_user_id,
                    project=project,
                    cloud=cloud,
                )
                
                if not configs:
                    return jsonify({"error": "无法获取AK/SK信息"}), 500
                
                ak = configs[0].get('ak', '')
                sk = configs[0].get('sk', '')
                
                # 生成Terraform配置文件 - AWS示例
                if cloud == 'AWS':
                    terraform_template = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 查找VPC
data "aws_vpc" "selected" {{
  filter {{
    name   = "tag:Name"
    values = ["{subnet_vpc}"]
  }}
}}

# 创建子网
resource "aws_subnet" "{subnet_name}" {{
  vpc_id     = data.aws_vpc.selected.id
  cidr_block = "{subnet_cidr}"
  
  tags = {{
    Name    = "{subnet_name}"
    Project = "{project}"
    DeployID = "{deploy_id}"
  }}
}}

output "subnet_id" {{
  value = aws_subnet.{subnet_name}.id
}}

output "subnet_name" {{
  value = "{subnet_name}"
}}

output "subnet_cidr" {{
  value = "{subnet_cidr}"
}}

output "subnet_vpc" {{
  value = data.aws_vpc.selected.id
}}
'''
                elif "AZURE" in cloud.upper():
                    terraform_template = f'''
terraform {{
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
  
  subscription_id = "{ak}"
  client_secret = "{sk}"
}}

# 查找资源组
data "azurerm_resource_group" "{project}_rg" {{
  name = "{project}-rg"
}}

# 查找虚拟网络
data "azurerm_virtual_network" "selected" {{
  name                = "{subnet_vpc}"
  resource_group_name = data.azurerm_resource_group.{project}_rg.name
}}

# 创建子网
resource "azurerm_subnet" "{subnet_name}" {{
  name                 = "{subnet_name}"
  resource_group_name  = data.azurerm_resource_group.{project}_rg.name
  virtual_network_name = data.azurerm_virtual_network.selected.name
  address_prefixes     = ["{subnet_cidr}"]
}}

output "subnet_id" {{
  value = azurerm_subnet.{subnet_name}.id
}}

output "subnet_name" {{
  value = "{subnet_name}"
}}

output "subnet_cidr" {{
  value = "{subnet_cidr}"
}}

output "subnet_vpc" {{
  value = data.azurerm_virtual_network.selected.id
}}
'''
                else:
                    # 默认AWS配置
                    terraform_template = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 查找VPC
data "aws_vpc" "selected" {{
  filter {{
    name   = "tag:Name"
    values = ["{subnet_vpc}"]
  }}
}}

# 创建子网
resource "aws_subnet" "{subnet_name}" {{
  vpc_id     = data.aws_vpc.selected.id
  cidr_block = "{subnet_cidr}"
  
  tags = {{
    Name    = "{subnet_name}"
    Project = "{project}"
    DeployID = "{deploy_id}"
  }}
}}

output "subnet_id" {{
  value = aws_subnet.{subnet_name}.id
}}

output "subnet_name" {{
  value = "{subnet_name}"
}}

output "subnet_cidr" {{
  value = "{subnet_cidr}"
}}

output "subnet_vpc" {{
  value = data.aws_vpc.selected.id
}}
'''
                
                # 写入Terraform配置文件
                with open(tf_file, 'w') as f:
                    f.write(terraform_template)
                
                # 创建状态文件，用于前端轮询检查状态
                status_file = os.path.join(deploy_dir, "status.json")
                try:
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'in_progress',
                            'deploy_id': deploy_id,
                            'message': '子网部署已开始',
                            'updated_at': datetime.datetime.now().isoformat()
                        }, f)
                except Exception as e:
                    self.logger.error(f"创建状态文件失败: {e}")
                
                # 创建部署记录
                self.deploy_model.create_deployment(
                    deploy_id=deploy_id,
                    deploy_type="subnet",
                    project=project,
                    cloud=cloud,
                    region=region,
                    status="in_progress",
                    user_id=current_user_id
                )
                
                # 启动实际的Terraform部署（异步）
                controller_ref = self
                
                # 定义子网部署线程函数
                def run_subnet_deployment(deploy_dir, log_file, status_file, deploy_id, user_id, project, cloud, region, subnet_name, subnet_cidr, subnet_vpc):
                    """在新线程中运行Terraform子网部署"""
                    try:
                        import json
                        import datetime
                        # 初始化Terraform
                        controller_ref.logger.info(f"开始执行子网Terraform部署: {deploy_dir}")
                        
                        # 记录操作到日志文件
                        with open(log_file, 'a') as f:
                            f.write(f"开始执行子网Terraform部署\n")
                            f.write(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                            
                            # 初始化
                            init_cmd = ["terraform", "init"]
                            controller_ref.logger.info(f"执行命令: {' '.join(init_cmd)}")
                            f.write(f"执行: {' '.join(init_cmd)}\n")
                            
                            init_process = subprocess.Popen(
                                init_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = init_process.communicate()
                            f.write(f"--- 初始化输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 初始化错误 ---\n")
                                f.write(stderr)
                            
                            if init_process.returncode != 0:
                                f.write(f"初始化失败，返回代码: {init_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform初始化失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"子网部署失败: Terraform初始化错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 计划
                            plan_cmd = ["terraform", "plan", "-out=tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(plan_cmd)}")
                            f.write(f"\n执行: {' '.join(plan_cmd)}\n")
                            
                            plan_process = subprocess.Popen(
                                plan_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = plan_process.communicate()
                            f.write(f"--- 计划输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 计划错误 ---\n")
                                f.write(stderr)
                            
                            if plan_process.returncode != 0:
                                f.write(f"计划失败，返回代码: {plan_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform计划失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"子网部署失败: Terraform计划错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 应用
                            apply_cmd = ["terraform", "apply", "-auto-approve", "tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(apply_cmd)}")
                            f.write(f"\n执行: {' '.join(apply_cmd)}\n")
                            
                            apply_process = subprocess.Popen(
                                apply_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = apply_process.communicate()
                            f.write(f"--- 应用输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 应用错误 ---\n")
                                f.write(stderr)
                            
                            if apply_process.returncode != 0:
                                f.write(f"应用失败，返回代码: {apply_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform应用失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"子网部署失败: Terraform应用错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 部署完成，获取输出
                            output_cmd = ["terraform", "output", "-json"]
                            controller_ref.logger.info(f"执行命令: {' '.join(output_cmd)}")
                            f.write(f"\n执行: {' '.join(output_cmd)}\n")
                            
                            output_process = subprocess.Popen(
                                output_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = output_process.communicate()
                            f.write(f"--- 输出结果 ---\n")
                            f.write(stdout)
                            
                            # 解析输出结果
                            try:
                                output_data = json.loads(stdout)
                                subnet_id = output_data.get('subnet_id', {}).get('value', '')
                                subnet_name_output = output_data.get('subnet_name', {}).get('value', subnet_name)
                                subnet_cidr_output = output_data.get('subnet_cidr', {}).get('value', subnet_cidr)
                                subnet_vpc_output = output_data.get('subnet_vpc', {}).get('value', '')
                                
                                # 成功时更新数据库中的子网信息
                                updates = {
                                    'subnet': subnet_name_output,
                                    'subnetid': subnet_id,
                                    'subnetcidr': subnet_cidr_output,
                                    'subnetvpc': subnet_vpc_output
                                }
                                
                                # 更新云配置信息
                                success = controller_ref.deploy_model.update_cloud_resources(
                                    user_id=user_id,
                                    project=project,
                                    cloud=cloud,
                                    resources=updates,
                                    deployid=deploy_id
                                )
                                
                                if success:
                                    controller_ref.logger.info(f"子网部署成功，已更新数据库: 子网={subnet_name_output}, ID={subnet_id}, CIDR={subnet_cidr_output}, VPC={subnet_vpc_output}")
                                else:
                                    controller_ref.logger.error(f"子网部署成功但更新数据库失败")
                                
                                # 记录成功结果
                                f.write(f"\n子网部署成功:\n")
                                f.write(f"  子网名称: {subnet_name_output}\n")
                                f.write(f"  子网ID: {subnet_id}\n")
                                f.write(f"  CIDR: {subnet_cidr_output}\n")
                                f.write(f"  VPC ID: {subnet_vpc_output}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'completed',
                                            'deploy_id': deploy_id,
                                            'subnet_id': subnet_id,
                                            'subnet_name': subnet_name_output,
                                            'subnet_cidr': subnet_cidr_output,
                                            'subnet_vpc': subnet_vpc_output,
                                            'message': f"子网部署成功 - ID: {subnet_id}",
                                            'output': f"子网名称: {subnet_name_output}\n子网ID: {subnet_id}\nCIDR: {subnet_cidr_output}\nVPC ID: {subnet_vpc_output}",
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                    
                                # 部署成功后更新部署状态
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="completed",
                                )
                                    
                            except Exception as e:
                                controller_ref.logger.error(f"解析Terraform输出失败: {str(e)}")
                                f.write(f"\nERROR: 解析输出失败: {str(e)}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"子网部署失败: 无法解析输出",
                                            'error': str(e),
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e2:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e2)}")
                                
                                # 更新部署状态
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                    except Exception as e:
                        controller_ref.logger.error(f"子网Terraform部署出错: {str(e)}", exc_info=True)
                        
                        # 记录错误信息到日志
                        try:
                            with open(log_file, 'a') as f:
                                f.write(f"\nERROR: 部署过程发生错误: {str(e)}\n")
                        except Exception:
                            pass
                        
                        # 更新状态文件
                        try:
                            with open(status_file, 'w') as sf:
                                json.dump({
                                    'status': 'failed',
                                    'deploy_id': deploy_id,
                                    'message': f"子网部署失败: {str(e)}",
                                    'error': str(e),
                                    'updated_at': datetime.datetime.now().isoformat()
                                }, sf)
                        except Exception:
                            pass
                        
                        # 更新部署状态
                        controller_ref.deploy_model.update_deployment_status(
                            deploy_id=deploy_id,
                            status="failed",
                        )
                
                # 在新线程中启动部署
                deploy_thread = threading.Thread(
                    target=run_subnet_deployment,
                    args=(
                        deploy_dir, 
                        log_file, 
                        status_file, 
                        deploy_id, 
                        current_user_id, 
                        project, 
                        cloud, 
                        region, 
                        subnet_name, 
                        subnet_cidr, 
                        subnet_vpc
                    )
                )
                # 设置为守护线程，这样主程序退出时不会等待它
                deploy_thread.daemon = True
                deploy_thread.start()
                
                # 返回部署成功消息
                return jsonify({
                    "reply": f"<div class='deployment-message'>子网部署已开始:<br><ul><li>名称: {subnet_name}</li><li>CIDR: {subnet_cidr}</li><li>所属VPC: {subnet_vpc}</li></ul><br>部署ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{region}</strong><br><br>部署预计需要1-2分钟完成，完成后可在历史部署中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "status_api": f"/api/deploy/status?deploy_id={deploy_id}",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                })
            
            elif resource_type == 'iam_user':
                iam_user_name = form_data.get('iam_user_name', '')
                
                if not iam_user_name:
                    return jsonify({"error": "IAM用户名不能为空"}), 400
                
                self.logger.info(f"创建IAM用户: 名称={iam_user_name}")
                
                # 创建部署目录
                deploy_dir = f"deploy/{deploy_id}"
                os.makedirs(deploy_dir, exist_ok=True)
                
                # 设置Terraform文件路径
                tf_file = f"{deploy_dir}/main.tf"
                log_file = f"{deploy_dir}/deploy.log"
                
                # 获取云配置（AK/SK）
                configs = self.deploy_model.get_cloud_config(
                    user_id=current_user_id,
                    project=project,
                    cloud=cloud,
                )
                
                if not configs:
                    return jsonify({"error": "无法获取AK/SK信息"}), 500
                
                ak = configs[0].get('ak', '')
                sk = configs[0].get('sk', '')
                
                # 生成Terraform配置文件 - AWS示例
                if cloud == 'AWS':
                    terraform_template = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 创建IAM用户
resource "aws_iam_user" "{iam_user_name}" {{
  name = "{iam_user_name}"
  
  tags = {{
    Name    = "{iam_user_name}"
    Project = "{project}"
    DeployID = "{deploy_id}"
  }}
}}

# 创建访问密钥
resource "aws_iam_access_key" "{iam_user_name}_key" {{
  user = aws_iam_user.{iam_user_name}.name
}}

# 创建登录配置文件（开启控制台访问）
resource "aws_iam_user_login_profile" "{iam_user_name}_profile" {{
  user                    = aws_iam_user.{iam_user_name}.name
  password_reset_required = true  # 首次登录需要修改密码
}}

# 创建基本策略附加
resource "aws_iam_user_policy_attachment" "{iam_user_name}_readonly_policy" {{
  user       = aws_iam_user.{iam_user_name}.name
  policy_arn = "{'arn:aws-cn:iam::aws:policy/ReadOnlyAccess' if region in ['cn-north-1', 'cn-northwest-1'] else 'arn:aws:iam::aws:policy/ReadOnlyAccess'}"
}}

# 添加IAMUserChangePassword策略，允许用户更改密码
resource "aws_iam_user_policy_attachment" "{iam_user_name}_change_password_policy" {{
  user       = aws_iam_user.{iam_user_name}.name
  policy_arn = "{'arn:aws-cn:iam::aws:policy/IAMUserChangePassword' if region in ['cn-north-1', 'cn-northwest-1'] else 'arn:aws:iam::aws:policy/IAMUserChangePassword'}"
}}

output "iam_user_name" {{
  value = aws_iam_user.{iam_user_name}.name
}}

output "iam_user_id" {{
  value = aws_iam_user.{iam_user_name}.id
}}

output "iam_user_arn" {{
  value = aws_iam_user.{iam_user_name}.arn
}}

output "iam_user_access_key_id" {{
  value = aws_iam_access_key.{iam_user_name}_key.id
}}

output "iam_user_access_key_secret" {{
  value = aws_iam_access_key.{iam_user_name}_key.secret
  sensitive = true
}}

output "iam_user_console_password" {{
  value = aws_iam_user_login_profile.{iam_user_name}_profile.password
  sensitive = true
}}
'''
                elif "AZURE" in cloud.upper():
                    terraform_template = f'''
terraform {{
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
  
  subscription_id = "{ak}"
  client_secret = "{sk}"
}}

# 查找资源组
data "azurerm_resource_group" "{project}_rg" {{
  name = "{project}-rg"
}}

# 创建Azure AD用户（类似于IAM用户）的相关资源
# 注意：Azure创建AD用户需要额外的权限配置

output "iam_user_name" {{
  value = "{iam_user_name}"
}}

output "iam_user_id" {{
  value = "{deploy_id}"
}}

output "iam_user_arn" {{
  value = "azure://{project}/{iam_user_name}"
}}
'''
                else:
                    # 默认AWS配置
                    terraform_template = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 创建IAM用户
resource "aws_iam_user" "{iam_user_name}" {{
  name = "{iam_user_name}"
  
  tags = {{
    Name    = "{iam_user_name}"
    Project = "{project}"
    DeployID = "{deploy_id}"
  }}
}}

# 创建访问密钥
resource "aws_iam_access_key" "{iam_user_name}_key" {{
  user = aws_iam_user.{iam_user_name}.name
}}

# 创建登录配置文件（开启控制台访问）
resource "aws_iam_user_login_profile" "{iam_user_name}_profile" {{
  user                    = aws_iam_user.{iam_user_name}.name
  password_reset_required = true  # 首次登录需要修改密码
}}

# 创建基本策略附加
resource "aws_iam_user_policy_attachment" "{iam_user_name}_readonly_policy" {{
  user       = aws_iam_user.{iam_user_name}.name
  policy_arn = "{'arn:aws-cn:iam::aws:policy/ReadOnlyAccess' if region in ['cn-north-1', 'cn-northwest-1'] else 'arn:aws:iam::aws:policy/ReadOnlyAccess'}"
}}

# 添加IAMUserChangePassword策略，允许用户更改密码
resource "aws_iam_user_policy_attachment" "{iam_user_name}_change_password_policy" {{
  user       = aws_iam_user.{iam_user_name}.name
  policy_arn = "{'arn:aws-cn:iam::aws:policy/IAMUserChangePassword' if region in ['cn-north-1', 'cn-northwest-1'] else 'arn:aws:iam::aws:policy/IAMUserChangePassword'}"
}}

output "iam_user_name" {{
  value = aws_iam_user.{iam_user_name}.name
}}

output "iam_user_id" {{
  value = aws_iam_user.{iam_user_name}.id
}}

output "iam_user_arn" {{
  value = aws_iam_user.{iam_user_name}.arn
}}

output "iam_user_access_key_id" {{
  value = aws_iam_access_key.{iam_user_name}_key.id
}}

output "iam_user_access_key_secret" {{
  value = aws_iam_access_key.{iam_user_name}_key.secret
  sensitive = true
}}

output "iam_user_console_password" {{
  value = aws_iam_user_login_profile.{iam_user_name}_profile.password
  sensitive = true
}}
'''
                
                # 写入Terraform配置文件
                with open(tf_file, 'w') as f:
                    f.write(terraform_template)
                
                # 创建状态文件，用于前端轮询检查状态
                status_file = os.path.join(deploy_dir, "status.json")
                try:
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'in_progress',
                            'deploy_id': deploy_id,
                            'message': 'IAM用户创建已开始',
                            'updated_at': datetime.datetime.now().isoformat()
                        }, f)
                except Exception as e:
                    self.logger.error(f"创建状态文件失败: {e}")
                
                # 创建部署记录
                self.deploy_model.create_deployment(
                    deploy_id=deploy_id,
                    deploy_type="iam_user",
                    project=project,
                    cloud=cloud,
                    region=region,
                    status="in_progress",
                    user_id=current_user_id
                )
                
                # 启动实际的Terraform部署（异步）
                controller_ref = self
                
                # 定义IAM用户部署线程函数
                def run_iam_user_deployment(deploy_dir, log_file, status_file, deploy_id, user_id, project, cloud, region, iam_user_name):
                    """在新线程中运行Terraform IAM用户部署"""
                    try:
                        import json
                        import datetime
                        # 初始化Terraform
                        controller_ref.logger.info(f"开始执行IAM用户Terraform部署: {deploy_dir}")
                        
                        # 记录操作到日志文件
                        with open(log_file, 'a') as f:
                            f.write(f"开始执行IAM用户Terraform部署\n")
                            f.write(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                            
                            # 初始化
                            init_cmd = ["terraform", "init"]
                            controller_ref.logger.info(f"执行命令: {' '.join(init_cmd)}")
                            f.write(f"执行: {' '.join(init_cmd)}\n")
                            
                            init_process = subprocess.Popen(
                                init_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = init_process.communicate()
                            f.write(f"--- 初始化输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 初始化错误 ---\n")
                                f.write(stderr)
                            
                            if init_process.returncode != 0:
                                f.write(f"初始化失败，返回代码: {init_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform初始化失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM用户创建失败: Terraform初始化错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 计划
                            plan_cmd = ["terraform", "plan", "-out=tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(plan_cmd)}")
                            f.write(f"\n执行: {' '.join(plan_cmd)}\n")
                            
                            plan_process = subprocess.Popen(
                                plan_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = plan_process.communicate()
                            f.write(f"--- 计划输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 计划错误 ---\n")
                                f.write(stderr)
                            
                            if plan_process.returncode != 0:
                                f.write(f"计划失败，返回代码: {plan_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform计划失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM用户创建失败: Terraform计划错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 应用
                            apply_cmd = ["terraform", "apply", "-auto-approve", "tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(apply_cmd)}")
                            f.write(f"\n执行: {' '.join(apply_cmd)}\n")
                            
                            apply_process = subprocess.Popen(
                                apply_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = apply_process.communicate()
                            f.write(f"--- 应用输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 应用错误 ---\n")
                                f.write(stderr)
                            
                            if apply_process.returncode != 0:
                                f.write(f"应用失败，返回代码: {apply_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform应用失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM用户创建失败: Terraform应用错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 部署完成，获取输出
                            output_cmd = ["terraform", "output", "-json"]
                            controller_ref.logger.info(f"执行命令: {' '.join(output_cmd)}")
                            f.write(f"\n执行: {' '.join(output_cmd)}\n")
                            
                            output_process = subprocess.Popen(
                                output_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = output_process.communicate()
                            f.write(f"--- 输出结果 ---\n")
                            f.write(stdout)
                            
                            # 解析输出结果
                            try:
                                output_data = json.loads(stdout)
                                iam_user_name_output = output_data.get('iam_user_name', {}).get('value', iam_user_name)
                                iam_user_id = output_data.get('iam_user_id', {}).get('value', '')
                                iam_user_arn = output_data.get('iam_user_arn', {}).get('value', '')
                                iam_access_key_id = output_data.get('iam_user_access_key_id', {}).get('value', '')
                                iam_access_key_secret = output_data.get('iam_user_access_key_secret', {}).get('value', '')
                                iam_console_password = output_data.get('iam_user_console_password', {}).get('value', '')
                                
                                # 添加IAM策略信息
                                iam_policies = ['ReadOnlyAccess', 'IAMUserChangePassword']
                                iam_policies_str = ', '.join(iam_policies)
                                
                                # 成功时更新数据库中的IAM用户信息
                                updates = {
                                    'object': iam_user_name_output,
                                    'objectid': iam_user_id,
                                    'objectarn': iam_user_arn,
                                    'iam_access_key_id': iam_access_key_id,
                                    'iam_access_key_secret': iam_access_key_secret,
                                    'iam_console_password': iam_console_password,
                                    'iam_user_policy': iam_policies_str  # 使用iam_user_policy而不是iam_user_policies
                                }
                                
                                # 更新云配置信息
                                success = controller_ref.deploy_model.update_cloud_resources(
                                    user_id=user_id,
                                    project=project,
                                    cloud=cloud,
                                    resources=updates,
                                    deployid=deploy_id
                                )
                                
                                if success:
                                    controller_ref.logger.info(f"IAM用户创建成功，已更新数据库: 用户名={iam_user_name_output}, ID={iam_user_id}, ARN={iam_user_arn}")
                                else:
                                    controller_ref.logger.error(f"IAM用户创建成功但更新数据库失败")
                                
                                # 记录成功结果
                                f.write(f"\nIAM用户创建成功:\n")
                                f.write(f"  用户名: {iam_user_name_output}\n")
                                f.write(f"  用户ID: {iam_user_id}\n")
                                f.write(f"  用户ARN: {iam_user_arn}\n")
                                f.write(f"  访问密钥ID: {iam_access_key_id}\n")
                                f.write(f"  控制台密码: {iam_console_password}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'completed',
                                            'deploy_id': deploy_id,
                                            'iam_user_id': iam_user_id,
                                            'iam_user_name': iam_user_name_output,
                                            'iam_user_arn': iam_user_arn,
                                            'iam_access_key_id': iam_access_key_id,
                                            'iam_access_key_secret': iam_access_key_secret,
                                            'iam_console_password': iam_console_password,
                                            'iam_user_policy': iam_policies_str,
                                            'message': f"IAM用户创建成功 - ID: {iam_user_id}",
                                            'output': f"用户名: {iam_user_name_output}\n用户ID: {iam_user_id}\n用户ARN: {iam_user_arn}\n访问密钥ID: {iam_access_key_id}\n访问密钥Secret: {iam_access_key_secret}\n控制台密码: {iam_console_password}\n用户策略: {iam_policies_str}",
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                    
                                # 部署成功后更新部署状态
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="completed",
                                )
                                    
                            except Exception as e:
                                controller_ref.logger.error(f"解析Terraform输出失败: {str(e)}")
                                f.write(f"\nERROR: 解析输出失败: {str(e)}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM用户创建失败: 无法解析输出",
                                            'error': str(e),
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e2:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e2)}")
                                
                                # 更新部署状态
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                    except Exception as e:
                        controller_ref.logger.error(f"执行IAM用户部署线程时出错: {str(e)}", exc_info=True)
                        
                        # 更新部署状态
                        try:
                            controller_ref.deploy_model.update_deployment_status(
                                deploy_id=deploy_id,
                                status="failed",
                            )
                        except Exception as db_err:
                            controller_ref.logger.error(f"更新部署状态时出错: {str(db_err)}")
                        
                        # 更新状态文件
                        try:
                            with open(status_file, 'w') as sf:
                                json.dump({
                                    'status': 'failed',
                                    'deploy_id': deploy_id,
                                    'message': f"IAM用户部署失败: {str(e)}",
                                    'error': str(e),
                                    'updated_at': datetime.datetime.now().isoformat()
                                }, sf)
                        except Exception as file_err:
                            controller_ref.logger.error(f"更新状态文件失败: {str(file_err)}")
                
                # 启动部署线程
                deployment_thread = threading.Thread(
                    target=run_iam_user_deployment,
                    args=(
                        deploy_dir, 
                        log_file, 
                        status_file, 
                        deploy_id, 
                        current_user_id, 
                        project, 
                        cloud, 
                        region, 
                        iam_user_name
                    )
                )
                deployment_thread.daemon = True
                deployment_thread.start()
                self.logger.info(f"已启动IAM用户部署线程: {deploy_dir}")
                
                # 返回部署开始消息（添加status_api字段）
                return jsonify({
                    "reply": f"<div class='deployment-message'>IAM用户创建已开始:<br><ul><li>用户名: {iam_user_name}</li></ul><br>部署ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{region}</strong><br><br>创建过程预计需要1分钟完成，完成后可在历史部署中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "status_api": f"/api/deploy/status?deploy_id={deploy_id}",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                })
            
            elif resource_type == 'iam_group':
                iam_group_name = form_data.get('iam_group_name', '')
                
                if not iam_group_name:
                    return jsonify({"error": "IAM用户组名称不能为空"}), 400
                
                self.logger.info(f"创建IAM用户组: 名称={iam_group_name}")
                
                # 创建部署目录
                deploy_dir = f"deploy/{deploy_id}"
                os.makedirs(deploy_dir, exist_ok=True)
                
                # 设置Terraform文件路径
                tf_file = f"{deploy_dir}/main.tf"
                log_file = f"{deploy_dir}/deploy.log"
                
                # 获取云配置（AK/SK）
                configs = self.deploy_model.get_cloud_config(
                    user_id=current_user_id,
                    project=project,
                    cloud=cloud,
                )
                
                if not configs:
                    return jsonify({"error": "无法获取AK/SK信息"}), 500
                
                ak = configs[0].get('ak', '')
                sk = configs[0].get('sk', '')
                
                # 生成Terraform配置文件 - AWS示例
                if cloud == 'AWS':
                    terraform_template = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 创建IAM用户组
resource "aws_iam_group" "{iam_group_name}" {{
  name        = "{iam_group_name}"
  path        = "/"
}}

output "iam_group_name" {{
  value = aws_iam_group.{iam_group_name}.name
}}

output "iam_group_id" {{
  value = aws_iam_group.{iam_group_name}.id
}}

output "iam_group_arn" {{
  value = aws_iam_group.{iam_group_name}.arn
}}
'''
                elif "AZURE" in cloud.upper():
                    terraform_template = f'''
terraform {{
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
  
  subscription_id = "{ak}"
  client_secret = "{sk}"
}}

# 查找资源组
data "azurerm_resource_group" "{project}_rg" {{
  name = "{project}-rg"
}}

# 创建Azure AD用户组（类似于IAM用户组）的相关资源
# 注意：Azure创建AD用户组需要额外的权限配置

output "iam_group_name" {{
  value = "{iam_group_name}"
}}

output "iam_group_id" {{
  value = "{deploy_id}"
}}

output "iam_group_arn" {{
  value = "azure://{project}/{iam_group_name}"
}}
'''
                else:
                    # 默认AWS配置
                    terraform_template = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 创建IAM用户组
resource "aws_iam_group" "{iam_group_name}" {{
  name        = "{iam_group_name}"
  path        = "/"
}}

output "iam_group_name" {{
  value = aws_iam_group.{iam_group_name}.name
}}

output "iam_group_id" {{
  value = aws_iam_group.{iam_group_name}.id
}}

output "iam_group_arn" {{
  value = aws_iam_group.{iam_group_name}.arn
}}
'''
                
                # 写入Terraform配置文件
                with open(tf_file, 'w') as f:
                    f.write(terraform_template)
                
                # 创建状态文件，用于前端轮询检查状态
                status_file = os.path.join(deploy_dir, "status.json")
                try:
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'in_progress',
                            'deploy_id': deploy_id,
                            'message': 'IAM用户组创建已开始',
                            'updated_at': datetime.datetime.now().isoformat()
                        }, f)
                except Exception as e:
                    self.logger.error(f"创建状态文件失败: {e}")
                
                # 创建部署记录
                self.deploy_model.create_deployment(
                    deploy_id=deploy_id,
                    deploy_type="iam_group",
                    project=project,
                    cloud=cloud,
                    region=region,
                    status="in_progress",
                    user_id=current_user_id
                )
                
                # 启动实际的Terraform部署（异步）
                controller_ref = self
                
                # 定义IAM用户组部署线程函数
                def run_iam_group_deployment(deploy_dir, log_file, status_file, deploy_id, user_id, project, cloud, region, iam_group_name):
                    """在新线程中运行Terraform IAM用户组部署"""
                    try:
                        import json
                        import datetime
                        # 初始化Terraform
                        controller_ref.logger.info(f"开始执行IAM用户组Terraform部署: {deploy_dir}")
                        
                        # 记录操作到日志文件
                        with open(log_file, 'a') as f:
                            f.write(f"开始执行IAM用户组Terraform部署\n")
                            f.write(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                            
                            # 初始化
                            init_cmd = ["terraform", "init"]
                            controller_ref.logger.info(f"执行命令: {' '.join(init_cmd)}")
                            f.write(f"执行: {' '.join(init_cmd)}\n")
                            
                            init_process = subprocess.Popen(
                                init_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = init_process.communicate()
                            f.write(f"--- 初始化输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 初始化错误 ---\n")
                                f.write(stderr)
                            
                            if init_process.returncode != 0:
                                f.write(f"初始化失败，返回代码: {init_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform初始化失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM用户组创建失败: Terraform初始化错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 计划
                            plan_cmd = ["terraform", "plan", "-out=tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(plan_cmd)}")
                            f.write(f"\n执行: {' '.join(plan_cmd)}\n")
                            
                            plan_process = subprocess.Popen(
                                plan_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = plan_process.communicate()
                            f.write(f"--- 计划输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 计划错误 ---\n")
                                f.write(stderr)
                            
                            if plan_process.returncode != 0:
                                f.write(f"计划失败，返回代码: {plan_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform计划失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM用户组创建失败: Terraform计划错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 应用
                            apply_cmd = ["terraform", "apply", "-auto-approve", "tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(apply_cmd)}")
                            f.write(f"\n执行: {' '.join(apply_cmd)}\n")
                            
                            apply_process = subprocess.Popen(
                                apply_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = apply_process.communicate()
                            f.write(f"--- 应用输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 应用错误 ---\n")
                                f.write(stderr)
                            
                            if apply_process.returncode != 0:
                                f.write(f"应用失败，返回代码: {apply_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform应用失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM用户组创建失败: Terraform应用错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 部署完成，获取输出
                            output_cmd = ["terraform", "output", "-json"]
                            controller_ref.logger.info(f"执行命令: {' '.join(output_cmd)}")
                            f.write(f"\n执行: {' '.join(output_cmd)}\n")
                            
                            output_process = subprocess.Popen(
                                output_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = output_process.communicate()
                            f.write(f"--- 输出结果 ---\n")
                            f.write(stdout)
                            
                            # 解析输出结果
                            try:
                                output_data = json.loads(stdout)
                                iam_group_name_output = output_data.get('iam_group_name', {}).get('value', iam_group_name)
                                iam_group_id = output_data.get('iam_group_id', {}).get('value', '')
                                iam_group_arn = output_data.get('iam_group_arn', {}).get('value', '')
                                
                                # 添加IAM策略信息
                                iam_policies = ['ReadOnlyAccess']
                                iam_policies_str = ', '.join(iam_policies)
                                
                                # 成功时更新数据库中的IAM用户组信息
                                updates = {
                                    'object': iam_group_name_output,
                                    'objectid': iam_group_id,
                                    'objectarn': iam_group_arn,
                                    'iam_group_policy': iam_policies_str  # 使用iam_group_policy而不是iam_group_policies
                                }
                                
                                # 更新云配置信息
                                success = controller_ref.deploy_model.update_cloud_resources(
                                    user_id=user_id,
                                    project=project,
                                    cloud=cloud,
                                    resources=updates,
                                    deployid=deploy_id
                                )
                                
                                if success:
                                    controller_ref.logger.info(f"IAM用户组创建成功，已更新数据库: 用户组名={iam_group_name_output}, ID={iam_group_id}, ARN={iam_group_arn}")
                                else:
                                    controller_ref.logger.error(f"IAM用户组创建成功但更新数据库失败")
                                
                                # 记录成功结果
                                f.write(f"\nIAM用户组创建成功:\n")
                                f.write(f"  用户组名: {iam_group_name_output}\n")
                                f.write(f"  用户组ID: {iam_group_id}\n")
                                f.write(f"  用户组ARN: {iam_group_arn}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'completed',
                                            'deploy_id': deploy_id,
                                            'iam_group_id': iam_group_id,
                                            'iam_group_name': iam_group_name_output,
                                            'iam_group_arn': iam_group_arn,
                                            'iam_group_policy': iam_policies_str,
                                            'message': f"IAM用户组创建成功 - ID: {iam_group_id}",
                                            'output': f"用户组名: {iam_group_name_output}\n用户组ID: {iam_group_id}\n用户组ARN: {iam_group_arn}\n用户策略: {iam_policies_str}",
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                    
                                # 部署成功后更新部署状态
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="completed",
                                )
                                    
                            except Exception as e:
                                controller_ref.logger.error(f"解析Terraform输出失败: {str(e)}")
                                f.write(f"\nERROR: 解析输出失败: {str(e)}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM用户组创建失败: 无法解析输出",
                                            'error': str(e),
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e2:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e2)}")
                                
                                # 更新部署状态
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                    except Exception as e:
                        controller_ref.logger.error(f"执行IAM用户组部署线程时出错: {str(e)}", exc_info=True)
                        
                        # 更新部署状态
                        try:
                            controller_ref.deploy_model.update_deployment_status(
                                deploy_id=deploy_id,
                                status="failed",
                            )
                        except Exception as db_err:
                            controller_ref.logger.error(f"更新部署状态时出错: {str(db_err)}")
                        
                        # 更新状态文件
                        try:
                            with open(status_file, 'w') as sf:
                                json.dump({
                                    'status': 'failed',
                                    'deploy_id': deploy_id,
                                    'message': f"IAM用户组部署失败: {str(e)}",
                                    'error': str(e),
                                    'updated_at': datetime.datetime.now().isoformat()
                                }, sf)
                        except Exception as file_err:
                            controller_ref.logger.error(f"更新状态文件失败: {str(file_err)}")
                
                # 启动部署线程
                deployment_thread = threading.Thread(
                    target=run_iam_group_deployment,
                    args=(
                        deploy_dir, 
                        log_file, 
                        status_file, 
                        deploy_id, 
                        current_user_id, 
                        project, 
                        cloud, 
                        region, 
                        iam_group_name
                    )
                )
                deployment_thread.daemon = True
                deployment_thread.start()
                self.logger.info(f"已启动IAM用户组部署线程: {deploy_dir}")
                
                # 返回部署开始消息（添加status_api字段）
                return jsonify({
                    "reply": f"<div class='deployment-message'>IAM用户组创建已开始:<br><ul><li>用户组名: {iam_group_name}</li></ul><br>部署ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{region}</strong><br><br>创建过程预计需要1分钟完成，完成后可在历史部署中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "status_api": f"/api/deploy/status?deploy_id={deploy_id}",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                })
            
            elif resource_type == 'iam_policy':
                iam_policy_name = form_data.get('iam_policy_name', '')
                iam_policy_description = form_data.get('iam_policy_description', '')
                iam_policy_content = form_data.get('iam_policy_content', '')
                
                # 确保策略内容是有效的JSON并进行处理
                try:
                    # 如果提交的是JSON字符串，先解析再转回来确保格式正确
                    policy_json = json.loads(iam_policy_content)
                    iam_policy_content = json.dumps(policy_json)
                    self.logger.info(f"已解析并格式化IAM策略内容")
                except json.JSONDecodeError as e:
                    self.logger.error(f"IAM策略内容不是有效的JSON: {e}")
                    return jsonify({"error": f"IAM策略内容必须是有效的JSON: {str(e)}"}), 400
                
                if not iam_policy_name:
                    return jsonify({"error": "IAM策略名称不能为空"}), 400
                
                self.logger.info(f"创建IAM策略: 名称={iam_policy_name}, 描述={iam_policy_description}")
                
                # 创建部署目录
                deploy_dir = os.path.join(self.base_dir, "deploy", deploy_id)
                os.makedirs(deploy_dir, exist_ok=True)
                
                # 设置Terraform文件路径
                tf_file = os.path.join(deploy_dir, "main.tf")
                log_file = os.path.join(deploy_dir, "deploy.log")
                
                # 获取云配置（AK/SK）
                configs = self.deploy_model.get_cloud_config(
                    user_id=current_user_id,
                    project=project,
                    cloud=cloud,
                )
                
                if not configs:
                    return jsonify({"error": "无法获取AK/SK信息"}), 500
                
                ak = configs[0].get('ak', '')
                sk = configs[0].get('sk', '')
                
                # 生成Terraform配置文件 - AWS示例
                if cloud == 'AWS':
                    terraform_template = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 创建IAM策略
resource "aws_iam_policy" "{iam_policy_name}" {{
  name        = "{iam_policy_name}"
  description = "{iam_policy_description}"
  policy      = <<EOF
{iam_policy_content}
EOF
}}

output "iam_policy_name" {{
  value = aws_iam_policy.{iam_policy_name}.name
}}

output "iam_policy_id" {{
  value = aws_iam_policy.{iam_policy_name}.id
}}

output "iam_policy_arn" {{
  value = aws_iam_policy.{iam_policy_name}.arn
}}
'''
                elif "AZURE" in cloud.upper():
                    terraform_template = f'''
terraform {{
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
  
  subscription_id = "{ak}"
  client_secret = "{sk}"
}}

# 查找资源组
data "azurerm_resource_group" "{project}_rg" {{
  name = "{project}-rg"
}}

# 创建Azure AD策略（类似于IAM策略）的相关资源
# 注意：Azure创建AD策略需要额外的权限配置

output "iam_policy_name" {{
  value = "{iam_policy_name}"
}}

output "iam_policy_id" {{
  value = "{deploy_id}"
}}

output "iam_policy_arn" {{
  value = "azure://{project}/{iam_policy_name}"
}}
'''
                else:
                    # 默认AWS配置
                    terraform_template = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 创建IAM策略
resource "aws_iam_policy" "{iam_policy_name}" {{
  name        = "{iam_policy_name}"
  description = "{iam_policy_description}"
  policy      = <<EOF
{iam_policy_content}
EOF
}}

output "iam_policy_name" {{
  value = aws_iam_policy.{iam_policy_name}.name
}}

output "iam_policy_id" {{
  value = aws_iam_policy.{iam_policy_name}.id
}}

output "iam_policy_arn" {{
  value = aws_iam_policy.{iam_policy_name}.arn
}}
'''
                
                # 写入Terraform配置文件
                with open(tf_file, 'w') as f:
                    f.write(terraform_template)
                
                # 创建状态文件，用于前端轮询检查状态
                status_file = os.path.join(deploy_dir, "status.json")
                try:
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'in_progress',
                            'deploy_id': deploy_id,
                            'message': 'IAM策略创建已开始',
                            'updated_at': datetime.datetime.now().isoformat()
                        }, f)
                except Exception as e:
                    self.logger.error(f"创建状态文件失败: {e}")
                
                # 创建部署记录
                self.deploy_model.create_deployment(
                    deploy_id=deploy_id,
                    deploy_type="iam_policy",
                    project=project,
                    cloud=cloud,
                    region=region,
                    status="in_progress",
                    user_id=current_user_id
                )
                
                # 启动实际的Terraform部署（异步）
                controller_ref = self
                
                # 定义IAM策略部署线程函数
                def run_iam_policy_deployment(deploy_dir, log_file, status_file, deploy_id, user_id, project, cloud, region, iam_policy_name, iam_policy_description, iam_policy_content):
                    """在新线程中运行Terraform IAM策略部署"""
                    try:
                        import json
                        import datetime
                        # 初始化Terraform
                        controller_ref.logger.info(f"开始执行IAM策略Terraform部署: {deploy_dir}")
                        
                        # 记录操作到日志文件
                        with open(log_file, 'a') as f:
                            f.write(f"开始执行IAM策略Terraform部署\n")
                            f.write(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                            
                            # 初始化
                            init_cmd = ["terraform", "init"]
                            controller_ref.logger.info(f"执行命令: {' '.join(init_cmd)}")
                            f.write(f"执行: {' '.join(init_cmd)}\n")
                            
                            init_process = subprocess.Popen(
                                init_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = init_process.communicate()
                            f.write(f"--- 初始化输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 初始化错误 ---\n")
                                f.write(stderr)
                            
                            if init_process.returncode != 0:
                                f.write(f"初始化失败，返回代码: {init_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform初始化失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM策略创建失败: Terraform初始化错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 计划
                            plan_cmd = ["terraform", "plan", "-out=tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(plan_cmd)}")
                            f.write(f"\n执行: {' '.join(plan_cmd)}\n")
                            
                            plan_process = subprocess.Popen(
                                plan_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = plan_process.communicate()
                            f.write(f"--- 计划输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 计划错误 ---\n")
                                f.write(stderr)
                            
                            if plan_process.returncode != 0:
                                f.write(f"计划失败，返回代码: {plan_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform计划失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM策略创建失败: Terraform计划错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 应用
                            apply_cmd = ["terraform", "apply", "-auto-approve", "tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(apply_cmd)}")
                            f.write(f"\n执行: {' '.join(apply_cmd)}\n")
                            
                            apply_process = subprocess.Popen(
                                apply_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = apply_process.communicate()
                            f.write(f"--- 应用输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 应用错误 ---\n")
                                f.write(stderr)
                            
                            if apply_process.returncode != 0:
                                f.write(f"应用失败，返回代码: {apply_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform应用失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM策略创建失败: Terraform应用错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 部署完成，获取输出
                            output_cmd = ["terraform", "output", "-json"]
                            controller_ref.logger.info(f"执行命令: {' '.join(output_cmd)}")
                            f.write(f"\n执行: {' '.join(output_cmd)}\n")
                            
                            output_process = subprocess.Popen(
                                output_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = output_process.communicate()
                            f.write(f"--- 输出结果 ---\n")
                            f.write(stdout)
                            
                            # 解析输出结果
                            try:
                                output_data = json.loads(stdout)
                                iam_policy_name_output = output_data.get('iam_policy_name', {}).get('value', iam_policy_name)
                                iam_policy_id = output_data.get('iam_policy_id', {}).get('value', '')
                                iam_policy_arn = output_data.get('iam_policy_arn', {}).get('value', '')
                                
                                # 添加IAM策略信息
                                iam_policies = ['ReadOnlyAccess', 'IAMUserChangePassword']
                                iam_policies_str = ', '.join(iam_policies)
                                
                                # 成功时更新数据库中的IAM策略信息
                                updates = {
                                    'object': iam_policy_name_output,
                                    'objectid': iam_policy_id,
                                    'objectarn': iam_policy_arn,
                                    'iam_policy': iam_policies_str  # 使用iam_policy而不是iam_policies
                                }
                                
                                # 更新云配置信息
                                success = controller_ref.deploy_model.update_cloud_resources(
                                    user_id=user_id,
                                    project=project,
                                    cloud=cloud,
                                    resources=updates,
                                    deployid=deploy_id
                                )
                                
                                if success:
                                    controller_ref.logger.info(f"IAM策略创建成功，已更新数据库: 策略名={iam_policy_name_output}, ID={iam_policy_id}, ARN={iam_policy_arn}")
                                else:
                                    controller_ref.logger.error(f"IAM策略创建成功但更新数据库失败")
                                
                                # 记录成功结果
                                f.write(f"\nIAM策略创建成功:\n")
                                f.write(f"  策略名: {iam_policy_name_output}\n")
                                f.write(f"  策略ID: {iam_policy_id}\n")
                                f.write(f"  策略ARN: {iam_policy_arn}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'completed',
                                            'deploy_id': deploy_id,
                                            'iam_policy_id': iam_policy_id,
                                            'iam_policy_name': iam_policy_name_output,
                                            'iam_policy_arn': iam_policy_arn,
                                            'iam_policy': iam_policies_str,
                                            'message': f"IAM策略创建成功 - ID: {iam_policy_id}",
                                            'output': f"策略名: {iam_policy_name_output}\n策略ID: {iam_policy_id}\n策略ARN: {iam_policy_arn}\n策略内容: {iam_policy_content}\n用户策略: {iam_policies_str}",
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                    
                                # 部署成功后更新部署状态
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="completed",
                                )
                                    
                            except Exception as e:
                                controller_ref.logger.error(f"解析Terraform输出失败: {str(e)}")
                                f.write(f"\nERROR: 解析输出失败: {str(e)}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"IAM策略创建失败: 无法解析输出",
                                            'error': str(e),
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e2:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e2)}")
                                
                                # 更新部署状态
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                    except Exception as e:
                        controller_ref.logger.error(f"执行IAM策略部署线程时出错: {str(e)}", exc_info=True)
                        
                        # 更新部署状态
                        try:
                            controller_ref.deploy_model.update_deployment_status(
                                deploy_id=deploy_id,
                                status="failed",
                            )
                        except Exception as db_err:
                            controller_ref.logger.error(f"更新部署状态时出错: {str(db_err)}")
                        
                        # 更新状态文件
                        try:
                            with open(status_file, 'w') as sf:
                                json.dump({
                                    'status': 'failed',
                                    'deploy_id': deploy_id,
                                    'message': f"IAM策略部署失败: {str(e)}",
                                    'error': str(e),
                                    'updated_at': datetime.datetime.now().isoformat()
                                }, sf)
                        except Exception as file_err:
                            controller_ref.logger.error(f"更新状态文件失败: {str(file_err)}")
                
                # 启动部署线程
                deployment_thread = threading.Thread(
                    target=run_iam_policy_deployment,
                    args=(
                        deploy_dir, 
                        log_file, 
                        status_file, 
                        deploy_id, 
                        current_user_id, 
                        project, 
                        cloud, 
                        region, 
                        iam_policy_name, 
                        iam_policy_description, 
                        iam_policy_content
                    )
                )
                deployment_thread.daemon = True
                deployment_thread.start()
                self.logger.info(f"已启动IAM策略部署线程: {deploy_dir}")
                
                # 返回部署开始消息（添加status_api字段）
                return jsonify({
                    "reply": f"<div class='deployment-message'>IAM策略创建已开始:<br><ul><li>策略名: {iam_policy_name}</li><li>描述: {iam_policy_description}</li></ul><br>部署ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{region}</strong><br><br>创建过程预计需要1分钟完成，完成后可在历史部署中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "status_api": f"/api/deploy/status?deploy_id={deploy_id}",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                })
            
            elif resource_type == 's3':
                s3_bucket_name = form_data.get('s3_bucket_name', '')
                
                if not s3_bucket_name:
                    return jsonify({"error": "S3存储桶名称不能为空"}), 400
                
                self.logger.info(f"创建S3存储桶: 名称={s3_bucket_name}")
                
                # 创建部署目录
                deploy_dir = f"deploy/{deploy_id}"
                os.makedirs(deploy_dir, exist_ok=True)
                
                # 设置Terraform文件路径
                tf_file = f"{deploy_dir}/main.tf"
                log_file = f"{deploy_dir}/deploy.log"
                
                # 获取云配置（AK/SK）
                configs = self.deploy_model.get_cloud_config(
                    user_id=current_user_id,
                    project=project,
                    cloud=cloud,
                )
                
                if not configs:
                    return jsonify({"error": "无法获取AK/SK信息"}), 500
                
                ak = configs[0].get('ak', '')
                sk = configs[0].get('sk', '')
                
                # 生成Terraform配置文件 - AWS示例
                if cloud == 'AWS':
                    terraform_template = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 创建S3存储桶
resource "aws_s3_bucket" "{s3_bucket_name}" {{
  bucket = "{s3_bucket_name}"
  
  tags = {{
    Name    = "{s3_bucket_name}"
    Project = "{project}"
    DeployID = "{deploy_id}"
  }}
}}

# 配置S3存储桶为私有 - 移除ACL配置，避免AccessControlListNotSupported错误
# AWS在新区域不再支持ACL
# resource "aws_s3_bucket_acl" "{s3_bucket_name}_acl" {{
#   bucket = aws_s3_bucket.{s3_bucket_name}.id
#   acl    = "private"
# }}

# 直接在bucket中设置私有访问控制
resource "aws_s3_bucket_ownership_controls" "{s3_bucket_name}_ownership" {{
  bucket = aws_s3_bucket.{s3_bucket_name}.id
  rule {{
    object_ownership = "BucketOwnerEnforced"
  }}
}}

# 配置版本控制
resource "aws_s3_bucket_versioning" "{s3_bucket_name}_versioning" {{
  bucket = aws_s3_bucket.{s3_bucket_name}.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

output "s3_bucket_id" {{
  value = aws_s3_bucket.{s3_bucket_name}.id
}}

output "s3_bucket_name" {{
  value = aws_s3_bucket.{s3_bucket_name}.bucket
}}

output "s3_bucket_arn" {{
  value = aws_s3_bucket.{s3_bucket_name}.arn
}}
'''
                elif "AZURE" in cloud.upper():
                    terraform_template = f'''
terraform {{
  required_providers {{
    azurerm = {{
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }}
  }}
}}

provider "azurerm" {{
  features {{}}
  
  subscription_id = "{ak}"
  client_secret = "{sk}"
}}

# 查找资源组
data "azurerm_resource_group" "{project}_rg" {{
  name = "{project}-rg"
}}

# 创建Azure存储账户（相当于S3存储桶）
resource "azurerm_storage_account" "{s3_bucket_name}" {{
  name                     = "{s3_bucket_name.replace('-', '')}"
  resource_group_name      = data.azurerm_resource_group.{project}_rg.name
  location                 = data.azurerm_resource_group.{project}_rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  
  tags = {{
    Project = "{project}"
    DeployID = "{deploy_id}"
  }}
}}

# 创建存储容器
resource "azurerm_storage_container" "{s3_bucket_name}_container" {{
  name                  = "default"
  storage_account_name  = azurerm_storage_account.{s3_bucket_name}.name
  container_access_type = "private"
}}

output "s3_bucket_id" {{
  value = azurerm_storage_account.{s3_bucket_name}.id
}}

output "s3_bucket_name" {{
  value = azurerm_storage_account.{s3_bucket_name}.name
}}

output "s3_bucket_arn" {{
  value = azurerm_storage_account.{s3_bucket_name}.primary_blob_endpoint
}}
'''
                else:
                    # 默认AWS配置
                    terraform_template = f'''
terraform {{
  required_providers {{
    aws = {{
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }}
  }}
}}

provider "aws" {{
  region      = "{region}"
  access_key  = "{ak}"
  secret_key  = "{sk}"
}}

# 创建S3存储桶
resource "aws_s3_bucket" "{s3_bucket_name}" {{
  bucket = "{s3_bucket_name}"
  
  tags = {{
    Name    = "{s3_bucket_name}"
    Project = "{project}"
    DeployID = "{deploy_id}"
  }}
}}

# 配置S3存储桶为私有 - 移除ACL配置，避免AccessControlListNotSupported错误
# AWS在新区域不再支持ACL
# resource "aws_s3_bucket_acl" "{s3_bucket_name}_acl" {{
#   bucket = aws_s3_bucket.{s3_bucket_name}.id
#   acl    = "private"
# }}

# 直接在bucket中设置私有访问控制
resource "aws_s3_bucket_ownership_controls" "{s3_bucket_name}_ownership" {{
  bucket = aws_s3_bucket.{s3_bucket_name}.id
  rule {{
    object_ownership = "BucketOwnerEnforced"
  }}
}}

# 配置版本控制
resource "aws_s3_bucket_versioning" "{s3_bucket_name}_versioning" {{
  bucket = aws_s3_bucket.{s3_bucket_name}.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

output "s3_bucket_id" {{
  value = aws_s3_bucket.{s3_bucket_name}.id
}}

output "s3_bucket_name" {{
  value = aws_s3_bucket.{s3_bucket_name}.bucket
}}

output "s3_bucket_arn" {{
  value = aws_s3_bucket.{s3_bucket_name}.arn
}}
'''
                
                # 写入Terraform配置文件
                with open(tf_file, 'w') as f:
                    f.write(terraform_template)
                
                # 创建状态文件，用于前端轮询检查状态
                status_file = os.path.join(deploy_dir, "status.json")
                try:
                    with open(status_file, 'w') as f:
                        json.dump({
                            'status': 'in_progress',
                            'deploy_id': deploy_id,
                            'message': 'S3存储桶部署已开始',
                            'updated_at': datetime.datetime.now().isoformat()
                        }, f)
                except Exception as e:
                    self.logger.error(f"创建状态文件失败: {e}")
                
                # 创建部署记录
                self.deploy_model.create_deployment(
                    deploy_id=deploy_id,
                    deploy_type="s3",
                    project=project,
                    cloud=cloud,
                    region=region,
                    status="in_progress",
                    user_id=current_user_id
                )
                
                # 启动实际的Terraform部署（异步）
                controller_ref = self
                
                # 定义S3存储桶部署线程函数
                def run_s3_deployment(deploy_dir, log_file, status_file, deploy_id, user_id, project, cloud, region, s3_bucket_name):
                    """在新线程中运行Terraform S3存储桶部署"""
                    try:
                        import json
                        import datetime
                        # 初始化Terraform
                        controller_ref.logger.info(f"开始执行S3存储桶Terraform部署: {deploy_dir}")
                        
                        # 记录操作到日志文件
                        with open(log_file, 'a') as f:
                            f.write(f"开始执行S3存储桶Terraform部署\n")
                            f.write(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                            
                            # 初始化
                            init_cmd = ["terraform", "init"]
                            controller_ref.logger.info(f"执行命令: {' '.join(init_cmd)}")
                            f.write(f"执行: {' '.join(init_cmd)}\n")
                            
                            init_process = subprocess.Popen(
                                init_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = init_process.communicate()
                            f.write(f"--- 初始化输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 初始化错误 ---\n")
                                f.write(stderr)
                            
                            if init_process.returncode != 0:
                                f.write(f"初始化失败，返回代码: {init_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform初始化失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"S3存储桶部署失败: Terraform初始化错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 计划
                            plan_cmd = ["terraform", "plan", "-out=tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(plan_cmd)}")
                            f.write(f"\n执行: {' '.join(plan_cmd)}\n")
                            
                            plan_process = subprocess.Popen(
                                plan_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = plan_process.communicate()
                            f.write(f"--- 计划输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 计划错误 ---\n")
                                f.write(stderr)
                            
                            if plan_process.returncode != 0:
                                f.write(f"计划失败，返回代码: {plan_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform计划失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"S3存储桶部署失败: Terraform计划错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 应用
                            apply_cmd = ["terraform", "apply", "-auto-approve", "tfplan"]
                            controller_ref.logger.info(f"执行命令: {' '.join(apply_cmd)}")
                            f.write(f"\n执行: {' '.join(apply_cmd)}\n")
                            
                            apply_process = subprocess.Popen(
                                apply_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = apply_process.communicate()
                            f.write(f"--- 应用输出 ---\n")
                            f.write(stdout)
                            if stderr:
                                f.write(f"--- 应用错误 ---\n")
                                f.write(stderr)
                            
                            if apply_process.returncode != 0:
                                f.write(f"应用失败，返回代码: {apply_process.returncode}\n")
                                controller_ref.logger.error(f"Terraform应用失败: {stderr}")
                                # 更新状态为失败
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"S3存储桶部署失败: Terraform应用错误",
                                            'error': stderr,
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                
                                return
                            
                            # 部署完成，获取输出
                            output_cmd = ["terraform", "output", "-json"]
                            controller_ref.logger.info(f"执行命令: {' '.join(output_cmd)}")
                            f.write(f"\n执行: {' '.join(output_cmd)}\n")
                            
                            output_process = subprocess.Popen(
                                output_cmd,
                                cwd=deploy_dir,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True
                            )
                            
                            stdout, stderr = output_process.communicate()
                            f.write(f"--- 输出结果 ---\n")
                            f.write(stdout)
                            
                            # 解析输出结果
                            try:
                                output_data = json.loads(stdout)
                                s3_bucket_id = output_data.get('s3_bucket_id', {}).get('value', '')
                                s3_bucket_name_output = output_data.get('s3_bucket_name', {}).get('value', s3_bucket_name)
                                s3_bucket_arn = output_data.get('s3_bucket_arn', {}).get('value', '')
                                
                                # 成功时更新数据库中的S3存储桶信息
                                updates = {
                                    'object': s3_bucket_name_output,
                                    'objectid': s3_bucket_id,
                                    'objectarn': s3_bucket_arn
                                }
                                
                                # 更新云配置信息
                                success = controller_ref.deploy_model.update_cloud_resources(
                                    user_id=user_id,
                                    project=project,
                                    cloud=cloud,
                                    resources=updates,
                                    deployid=deploy_id
                                )
                                
                                if success:
                                    controller_ref.logger.info(f"S3存储桶部署成功，已更新数据库: 存储桶={s3_bucket_name_output}, ID={s3_bucket_id}, ARN={s3_bucket_arn}")
                                else:
                                    controller_ref.logger.error(f"S3存储桶部署成功但更新数据库失败")
                                
                                # 记录成功结果
                                f.write(f"\nS3存储桶部署成功:\n")
                                f.write(f"  存储桶名称: {s3_bucket_name_output}\n")
                                f.write(f"  存储桶ID: {s3_bucket_id}\n")
                                f.write(f"  存储桶ARN: {s3_bucket_arn}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'completed',
                                            'deploy_id': deploy_id,
                                            's3_bucket_id': s3_bucket_id,
                                            's3_bucket_name': s3_bucket_name_output,
                                            's3_bucket_arn': s3_bucket_arn,
                                            'message': f"S3存储桶部署成功 - ID: {s3_bucket_id}",
                                            'output': f"存储桶名称: {s3_bucket_name_output}\n存储桶ID: {s3_bucket_id}\n存储桶ARN: {s3_bucket_arn}",
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e)}")
                                    
                                # 部署成功后更新部署状态
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="completed",
                                )
                                    
                            except Exception as e:
                                controller_ref.logger.error(f"解析Terraform输出失败: {str(e)}")
                                f.write(f"\nERROR: 解析输出失败: {str(e)}\n")
                                
                                # 更新状态文件
                                try:
                                    with open(status_file, 'w') as sf:
                                        json.dump({
                                            'status': 'failed',
                                            'deploy_id': deploy_id,
                                            'message': f"S3存储桶部署失败: 无法解析输出",
                                            'error': str(e),
                                            'updated_at': datetime.datetime.now().isoformat()
                                        }, sf)
                                except Exception as e2:
                                    controller_ref.logger.error(f"更新状态文件失败: {str(e2)}")
                                
                                # 更新部署状态
                                controller_ref.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="failed",
                                )
                    except Exception as e:
                        controller_ref.logger.error(f"S3存储桶Terraform部署出错: {str(e)}", exc_info=True)
                        
                        # 记录错误信息到日志
                        try:
                            with open(log_file, 'a') as f:
                                f.write(f"\nERROR: 部署过程发生错误: {str(e)}\n")
                        except Exception:
                            pass
                        
                        # 更新状态文件
                        try:
                            with open(status_file, 'w') as sf:
                                json.dump({
                                    'status': 'failed',
                                    'deploy_id': deploy_id,
                                    'message': f"S3存储桶部署失败: {str(e)}",
                                    'error': str(e),
                                    'updated_at': datetime.datetime.now().isoformat()
                                }, sf)
                        except Exception:
                            pass
                        
                        # 更新部署状态
                        controller_ref.deploy_model.update_deployment_status(
                            deploy_id=deploy_id,
                            status="failed",
                        )
                
                # 在新线程中启动部署
                deploy_thread = threading.Thread(
                    target=run_s3_deployment,
                    args=(
                        deploy_dir, 
                        log_file, 
                        status_file, 
                        deploy_id, 
                        current_user_id, 
                        project, 
                        cloud, 
                        region, 
                        s3_bucket_name
                    )
                )
                # 设置为守护线程，这样主程序退出时不会等待它
                deploy_thread.daemon = True
                deploy_thread.start()
                
                # 返回部署成功消息
                return jsonify({
                    "reply": f"<div class='deployment-message'>S3存储桶创建已开始:<br><ul><li>存储桶名称: {s3_bucket_name}</li></ul><br>部署ID: <strong>{deploy_id}</strong><br>项目: <strong>{project}</strong><br>云平台: <strong>{cloud}</strong><br>区域: <strong>{region}</strong><br><br>创建过程预计需要1-2分钟完成，完成后可在历史部署中查看详情。</div>",
                    "deploy_status": "in_progress",
                    "status_api": f"/api/deploy/status?deploy_id={deploy_id}",
                    "metadata": {
                        "user_id": current_user_id,
                        "project": project,
                        "cloud": cloud,
                        "deploy_id": deploy_id
                    }
                })
            
            else:
                return jsonify({"error": f"不支持的资源类型: {resource_type}"}), 400
                
        except Exception as e:
            self.logger.error(f"处理资源配置表单时出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"处理资源配置表单时发生错误: {str(e)}"}), 500

    def get_deployment_status(self):
        """获取指定部署ID的状态"""
        try:
            # 获取部署ID
            deploy_id = request.args.get('deploy_id')
            if not deploy_id:
                return jsonify({"error": "缺少部署ID参数"}), 400
            
            self.logger.info(f"获取部署ID {deploy_id} 的状态")
            
            # 构建状态文件路径(使用绝对路径)
            status_file = os.path.join(self.base_dir, "deploy", deploy_id, "status.json")
            
            # 检查状态文件是否存在
            if not os.path.exists(status_file):
                return jsonify({
                    "status": "unknown",
                    "deploy_id": deploy_id,
                    "message": "找不到部署状态信息"
                })
            
            # 读取状态文件
            try:
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                    return jsonify(status_data)
            except Exception as e:
                self.logger.error(f"读取状态文件出错: {str(e)}")
                return jsonify({
                    "status": "error",
                    "deploy_id": deploy_id,
                    "message": f"读取状态文件出错: {str(e)}"
                })
                
        except Exception as e:
            self.logger.error(f"获取部署状态出错: {str(e)}", exc_info=True)
            return jsonify({"error": f"获取部署状态失败: {str(e)}"}), 500

    def handle_execute_deploy(self) -> Dict[str, Any]:
        """处理同步执行部署的请求，类似于查询但直接返回结果
        
        Returns:
            Dict[str, Any]: 包含部署结果或错误信息的响应
        """
        self.logger.info("处理资源部署执行请求")
        
        try:
            # 获取请求数据
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "请求参数缺失"})
            
            # 解析部署ID和其他必要信息
            deploy_id = data.get('deploy_id')
            resource_type = data.get('resource_type', 'vpc')
            project = data.get('project')
            cloud = data.get('cloud')
            region = data.get('region')
            
            if not deploy_id:
                return jsonify({"success": False, "error": "部署ID缺失"})
                
            # 获取用户信息
            current_user = getattr(request, 'current_user', None)
            user_id = None
            username = None
            
            if current_user:
                user_id = current_user.get('user_id')
                username = current_user.get('username')
            else:
                user_id = data.get('user_id')
                username = data.get('username')
            
            if not user_id:
                self.logger.warning("未能获取到用户信息，将使用默认用户ID=1")
                user_id = 1
            
            self.logger.info(f"部署执行请求: ID={deploy_id}, 类型={resource_type}, 用户={user_id}")
            
            # 先检查状态文件是否存在(使用绝对路径)
            status_file = os.path.join(self.base_dir, "deploy", deploy_id, "status.json")
            status_data = None
            status = "unknown"
            message = ""
            resources = {}
            
            if os.path.exists(status_file):
                try:
                    with open(status_file, 'r') as f:
                        status_data = json.load(f)
                        status = status_data.get('status', 'unknown')
                        message = status_data.get('message', '')
                        
                        # 获取VPC资源信息
                        if status == 'completed' or status == 'success' or 'vpc_id' in status_data:
                            resources = {
                                "vpc_id": status_data.get('vpc_id', ''),
                                "vpc_name": status_data.get('vpc_name', ''),
                                "vpc_cidr": status_data.get('vpc_cidr', '')
                            }
                            
                            # 如果状态文件有VPC信息，但部署状态尚未更新，更新部署状态
                            if resources["vpc_id"] and (status == 'in_progress' or status == 'unknown'):
                                status = 'completed'
                                message = f"VPC部署成功 - ID: {resources['vpc_id']}"
                                
                                # 更新状态文件
                                status_data['status'] = status
                                status_data['message'] = message
                                with open(status_file, 'w') as sf:
                                    json.dump(status_data, sf)
                                
                                # 确保数据库中的状态也更新
                                self.deploy_model.update_deployment_status(
                                    deploy_id=deploy_id,
                                    status="completed"
                                )
                            
                            self.logger.info(f"从状态文件获取VPC信息: {resources}")
                except Exception as e:
                    self.logger.error(f"读取状态文件出错: {str(e)}")
            
            # 如果没有从状态文件获取到资源信息，尝试从数据库获取
            if not resources or not resources.get('vpc_id'):
                try:
                    # 使用模型的方法获取部署信息
                    deployment_info = self.deploy_model.get_deployment_by_id(deploy_id)
                    
                    # 添加日志，记录返回的部署信息内容
                    self.logger.info(f"从数据库获取到部署信息: {deployment_info}")
                    
                    if not deployment_info:
                        # 如果获取不到信息，尝试使用备用方法
                        deployment_info = self._get_deployment_info(deploy_id)
                        self.logger.info(f"使用备用方法获取到部署信息: {deployment_info}")
                        
                        if not deployment_info:
                            # 如果状态文件存在且状态明确，返回相应状态
                            if status_data and status != 'unknown':
                                return jsonify({
                                    "success": True,
                                    "deploy_id": deploy_id,
                                    "status": status,
                                    "message": message,
                                    "reply": f"<div class='deployment-message'>部署状态: {status}</div>{message}"
                                })
                            else:
                                return jsonify({
                                    "success": False, 
                                    "error": f"未找到部署信息: {deploy_id}",
                                    "reply": f"未找到部署ID: {deploy_id} 的相关信息"
                                })
                    
                    # 从数据库中提取VPC信息
                    resources = {
                        "vpc_id": deployment_info.get('vpcid', ''),
                        "vpc_name": deployment_info.get('vpc', ''),
                        "vpc_cidr": deployment_info.get('vpccidr', '')
                    }
                    
                    self.logger.info(f"从数据库获取VPC信息: {resources}")
                    
                    # 部署类型状态: 0=未开始, 1=进行中, 2=成功, 3=失败
                    deploy_status = deployment_info.get('deploytype', 0)
                    # 如果获取不到deploytype字段，尝试获取其他可能的字段名
                    if deploy_status == 0 and 'status' in deployment_info:
                        status_str = deployment_info.get('status', '').lower()
                        if status_str == 'completed' or status_str == 'success':
                            deploy_status = 2
                            status = 'completed'
                        elif status_str == 'in_progress' or status_str == 'running':
                            deploy_status = 1
                            status = 'in_progress'
                        elif status_str == 'failed' or status_str == 'error':
                            deploy_status = 3
                            status = 'failed'
                except Exception as e:
                    self.logger.error(f"获取部署信息时出错: {str(e)}")
                    # 如果数据库查询出错但有状态文件，仍然返回状态文件的信息
                    if status_data and status != 'unknown':
                        return jsonify({
                            "success": True,
                            "deploy_id": deploy_id,
                            "status": status,
                            "message": message,
                            "resources": resources,
                            "reply": f"<div class='deployment-message'>部署状态: {status}</div>{message}"
                        })
                    else:
                        return jsonify({
                            "success": False,
                            "error": f"获取部署信息失败: {str(e)}",
                            "reply": f"<div class='error-message'>获取部署信息失败</div>{str(e)}"
                        })
            
            # 如果状态是已完成且有VPC ID，返回成功结果
            if (status == 'completed' or status == 'success') and resources.get('vpc_id'):
                self.logger.info(f"成功部署: ID={deploy_id}, 资源类型={resource_type}, VPC ID={resources.get('vpc_id')}")
                
                # 确保数据库中的部署状态已更新
                self.deploy_model.update_deployment_status(
                    deploy_id=deploy_id,
                    status="completed"
                )
                
                # 明确记录返回的资源信息
                vpc_response = {
                    "vpc_id": resources.get('vpc_id'),
                    "vpc_name": resources.get('vpc_name'),
                    "vpc_cidr": resources.get('vpc_cidr')
                }
                self.logger.info(f"返回VPC详情: {vpc_response}")
                
                return jsonify({
                    "success": True,
                    "deploy_id": deploy_id,
                    "status": "completed",
                    "message": f"部署成功: {resource_type}",
                    "resources": vpc_response,
                    "reply": f"<div class='success-message'>部署已完成</div>资源 {resource_type} 已成功部署到 {cloud} 云平台，区域: {region}。<br>部署ID: {deploy_id}<br>VPC ID: {resources.get('vpc_id')}<br>VPC名称: {resources.get('vpc_name')}<br>CIDR: {resources.get('vpc_cidr')}"
                })
            elif status == 'failed':
                # 查找错误日志(使用绝对路径)
                log_path = os.path.join(self.base_dir, "deploy", deploy_id, "deploy.log")
                error_path = os.path.join(self.base_dir, "deploy", deploy_id, "error.txt")
                error_msg = "部署过程中发生错误"
                tf_error = ""
                error_lines = []
                
                # 尝试从错误文件中读取详细错误
                if os.path.exists(error_path):
                    try:
                        with open(error_path, 'r') as f:
                            tf_error = f.read()
                            self.logger.info(f"从错误文件中读取错误信息: {tf_error}")
                    except Exception as e:
                        self.logger.error(f"读取错误文件失败: {str(e)}")
                
                # 尝试从日志文件中提取错误
                if os.path.exists(log_path):
                    try:
                        with open(log_path, 'r') as f:
                            log_content = f.read()
                            # 查找ERROR开头的行
                            for line in log_content.splitlines():
                                if line.strip().startswith("ERROR") or "Error:" in line:
                                    error_lines.append(line.strip())
                                    self.logger.info(f"从日志文件中找到错误行: {line.strip()}")
                            
                            # 尝试找出错误信息，特别是Terraform错误
                            error_patterns = [
                                r"Error: (.+)",
                                r"Failed to (.*)",
                                r"InvalidClientTokenId.*",
                                r"The security token.* is invalid"
                            ]
                            for pattern in error_patterns:
                                matches = re.findall(pattern, log_content)
                                if matches:
                                    tf_error = matches[0]
                                    self.logger.info(f"从日志内容提取错误信息: {tf_error}")
                                    break
                    except Exception as e:
                        self.logger.error(f"读取日志文件失败: {str(e)}")
                
                # 组装错误信息
                error_details = ""
                if error_lines:
                    error_details = "\n".join(error_lines)
                    self.logger.info(f"收集到{len(error_lines)}行错误信息")
                
                if not tf_error and not error_details:
                    # 如果没有找到具体错误信息，使用通用消息
                    error_msg = "部署失败，但未能获取具体错误信息"
                
                # 构建错误响应HTML
                error_html = f"<div class='error-message'>部署失败</div><div>资源 {resource_type} 部署到 {cloud} 云平台失败，区域: {region}。<br>部署ID: {deploy_id}</div>"
                
                if tf_error:
                    error_html += f"<div class='error-details'><pre>{tf_error}</pre></div>"
                
                if error_details:
                    error_html += f"<div class='error-details'><pre>{error_details}</pre></div>"
                
                return jsonify({
                    "success": False,
                    "deploy_id": deploy_id,
                    "status": "failed",
                    "error": error_msg,
                    "tf_error": tf_error,
                    "error_details": error_details,
                    "reply": error_html
                })
            else:
                # 对于进行中或未知状态的部署，检查是否有最新日志(使用绝对路径)
                log_path = os.path.join(self.base_dir, "deploy", deploy_id, "deploy.log")
                log_content = ""
                
                if os.path.exists(log_path):
                    try:
                        with open(log_path, 'r') as f:
                            log_content = f.read()
                            # 提取最后几行日志
                            lines = log_content.splitlines()
                            recent_logs = lines[-5:] if len(lines) > 5 else lines
                            recent_log_text = "\n".join(recent_logs)
                    except Exception as e:
                        self.logger.error(f"读取日志文件失败: {str(e)}")
                
                # 更新部署状态为进行中（如果之前是未开始）
                if status == 'unknown':
                    self.deploy_model.update_deployment_status(
                        deploy_id=deploy_id,
                        status="in_progress"
                    )
                    status = 'in_progress'
                
                # 返回部署状态信息
                return jsonify({
                    "success": True,
                    "deploy_id": deploy_id,
                    "status": status,
                    "message": f"部署{'进行中' if status == 'in_progress' else '状态未知'}: {resource_type}",
                    "reply": f"资源 {resource_type} 正在部署到 {cloud} 云平台，区域: {region}。<br>部署ID: {deploy_id}<br>状态: {status}<br>预计完成时间：3-5分钟，请稍后在历史记录中查看结果。"
                })
                
        except Exception as e:
            self.logger.error(f"处理部署执行请求时出错: {str(e)}", exc_info=True)
            
            # 获取详细的异常信息
            error_detail = traceback.format_exc()
            self.logger.error(f"异常详情: {error_detail}")
            
            # 提取并返回更友好的错误信息
            error_msg = str(e)
            if 'get_deployment_by_id' in error_msg:
                error_msg = f"系统无法查找部署ID: {deploy_id}。请确认部署ID是否正确。"
            elif 'json' in error_msg.lower():
                error_msg = "处理部署状态信息时出错，可能是状态文件格式问题。"
            
            return jsonify({
                "success": False,
                "error": f"处理部署请求时出错: {error_msg}",
                "tf_error": error_detail,  # 将详细的错误堆栈也返回
                "reply": f"<div class='error-message'>处理部署请求时出错</div><div>{error_msg}</div>"
            })
