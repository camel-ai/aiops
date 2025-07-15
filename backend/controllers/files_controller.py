#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import traceback
from config.config import Config
from flask import request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename, safe_join
import glob
import hashlib
import time
from typing import Dict, Any, Optional, List
from PIL import Image
import io
import uuid
import mimetypes


class FilesController:
    """文件控制器，处理文件列表获取和下载"""

    def __init__(self, config: Config):
        """初始化文件控制器
        
        Args:
            config (Config): 配置对象
        """
        self.config = config
        self.logger = logging.getLogger("file_controller")
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def list_files(self):
        """获取文件列表
        
        根据部署ID和类型获取相关目录下的文件列表
        
        Returns:
            JSON响应，包含文件列表或错误信息
        """
        try:
            # 获取请求参数（支持GET和POST请求）
            if request.method == 'GET':
                deploy_id = request.args.get('id')
                deploy_type = request.args.get('type', 'deploy')  # 默认为deploy类型
            else:  # POST
                data = request.get_json()
                deploy_id = data.get('id')
                deploy_type = data.get('type', 'deploy')
            
            if not deploy_id:
                return jsonify({"success": False, "message": "缺少部署ID"})
            
            self.logger.info(f"获取文件列表: ID={deploy_id}, 类型={deploy_type}")
            
            # 确定基础目录
            if deploy_type == 'deploy':
                base_dir = os.path.join(self.base_dir, 'deploy', deploy_id)
            else:
                base_dir = os.path.join(self.base_dir, 'query', deploy_id)
            
            self.logger.info(f"查找目录: {base_dir}")
            
            # 检查目录是否存在
            if not os.path.exists(base_dir) or not os.path.isdir(base_dir):
                self.logger.warning(f"目录不存在: {base_dir}")
                return jsonify({"success": False, "message": "目录不存在"})
            
            # 搜索所有.tf文件
            tf_files = glob.glob(os.path.join(base_dir, "*.tf"))
            
            # 构建文件列表
            files = []
            for file_path in tf_files:
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                # 格式化文件大小
                if file_size < 1024:
                    size_str = f"{file_size} B"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.2f} KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.2f} MB"
                
                files.append({
                    "name": file_name,
                    "path": f"{deploy_type}/{deploy_id}/{file_name}",
                    "size": size_str,
                    "type": "Terraform"
                })
            
            # 按名称排序
            files.sort(key=lambda x: x["name"])
            
            return jsonify({
                "success": True,
                "files": files,
                "message": f"找到 {len(files)} 个文件"
            })
            
        except Exception as e:
            self.logger.error(f"获取文件列表时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "message": f"获取文件列表失败: {str(e)}"
            })
    
    def download_file(self):
        """下载文件
        
        根据文件路径下载文件
        
        Returns:
            文件内容或错误信息
        """
        try:
            # 获取请求参数
            file_path = request.args.get('path')
            
            if not file_path:
                return jsonify({"success": False, "message": "缺少文件路径"})
            
            # 去除可能存在的额外查询参数
            if '?' in file_path:
                file_path = file_path.split('?')[0]
                
            self.logger.info(f"下载文件: {file_path}")
            
            # 构建完整路径（安全地）
            parts = file_path.split('/')
            if len(parts) < 3:
                return jsonify({"success": False, "message": "无效的文件路径"}), 400
            
            # 安全地构建路径并防止路径遍历
            # 确保每个部分都不包含可疑字符
            for part in parts:
                if ".." in part or part.startswith("/") or part.startswith("\\"):
                    self.logger.warning(f"检测到可疑的路径部分: {part}")
                    return jsonify({"success": False, "message": "无效的文件路径"}), 400
            
            # 构建绝对路径
            full_path = os.path.join(self.base_dir, *parts)
            
            # 规范化路径并确保它在基础目录下
            norm_path = os.path.normpath(full_path)
            norm_base = os.path.normpath(self.base_dir)
            if not norm_path.startswith(norm_base):
                self.logger.warning(f"检测到路径遍历尝试: {full_path}")
                return jsonify({"success": False, "message": "无效的文件路径"}), 400
            
            # 检查文件是否存在
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                self.logger.warning(f"文件不存在: {full_path}")
                return jsonify({"success": False, "message": "文件不存在"}), 404
            
            # 检查文件扩展名，只允许特定类型
            allowed_extensions = ['.tf', '.tfstate', '.png', '.txt', '.json']
            if not any(full_path.endswith(ext) for ext in allowed_extensions):
                self.logger.warning(f"不支持的文件类型: {full_path}")
                return jsonify({"success": False, "message": "不支持的文件类型"}), 400
            
            # 返回文件
            return send_file(
                full_path,
                as_attachment=True,
                download_name=os.path.basename(full_path)
            )
            
        except Exception as e:
            self.logger.error(f"下载文件时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "message": f"下载文件失败: {str(e)}"
            }), 500
    
    def get_image(self):
        """获取图像文件
        
        Returns:
            图像文件或错误信息
        """
        try:
            # 获取请求参数
            image_path = request.args.get('path')
            
            if not image_path:
                return jsonify({"success": False, "message": "缺少图像路径"})
            
            # 去除可能存在的额外查询参数 - 修复处理路径中可能包含的查询参数
            if '?' in image_path:
                self.logger.info(f"图像路径包含查询参数，进行清理: {image_path}")
                image_path = image_path.split('?')[0]
                self.logger.info(f"清理后的图像路径: {image_path}")
                
            self.logger.info(f"获取图像: {image_path}")
            
            # 构建完整路径（安全地）
            parts = image_path.split('/')
            if len(parts) < 3:
                return jsonify({"success": False, "message": "无效的图像路径"}), 400
            
            # 安全地构建路径并防止路径遍历
            # 确保每个部分都不包含可疑字符
            for part in parts:
                if ".." in part or part.startswith("/") or part.startswith("\\"):
                    self.logger.warning(f"检测到可疑的路径部分: {part}")
                    return jsonify({"success": False, "message": "无效的图像路径"}), 400
            
            # 构建绝对路径
            full_path = os.path.join(self.base_dir, *parts)
            
            # 规范化路径并确保它在基础目录下
            norm_path = os.path.normpath(full_path)
            norm_base = os.path.normpath(self.base_dir)
            if not norm_path.startswith(norm_base):
                self.logger.warning(f"检测到路径遍历尝试: {full_path}")
                return jsonify({"success": False, "message": "无效的图像路径"}), 400
            
            # 检查文件是否存在
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                self.logger.warning(f"图像不存在: {full_path}")
                return jsonify({"success": False, "message": "图像不存在"}), 404
            
            # 检查文件扩展名，只允许图像类型
            allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif']
            if not any(full_path.endswith(ext) for ext in allowed_extensions):
                self.logger.warning(f"不支持的图像类型: {full_path}")
                return jsonify({"success": False, "message": "不支持的图像类型"}), 400
            
            # 添加缓存控制头
            return send_file(
                full_path,
                mimetype=f"image/{os.path.splitext(full_path)[1][1:]}"
            )
            
        except Exception as e:
            self.logger.error(f"获取图像时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "message": f"获取图像失败: {str(e)}"
            }), 500

    def upload_chat_file(self):
        """处理聊天中的文件上传请求"""
        try:
            # 获取当前用户信息
            current_user = request.current_user
            if not current_user:
                return jsonify({"error": "未授权，请先登录"}), 401
            
            username = current_user.get('username', 'anonymous')
            user_id = current_user.get('user_id', 'unknown')
            
            # 确保上传目录存在
            upload_dir = os.path.join(current_app.root_path, 'upload', username)
            os.makedirs(upload_dir, exist_ok=True)
            
            # 检查是否有文件上传
            if 'files' not in request.files:
                return jsonify({"error": "没有上传文件"}), 400
            
            uploaded_files = request.files.getlist('files')
            if not uploaded_files or uploaded_files[0].filename == '':
                return jsonify({"error": "文件为空"}), 400
            
            # 允许的图片格式
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
            
            # 处理上传的文件
            file_info_list = []
            for file in uploaded_files:
                # 验证文件类型
                original_filename = file.filename
                file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
                
                if file_ext not in allowed_extensions:
                    continue  # 跳过不允许的文件类型
                
                # 生成安全的文件名
                filename = secure_filename(f"{uuid.uuid4().hex}.{file_ext}")
                file_path = os.path.join(upload_dir, filename)
                
                # 保存文件
                file.save(file_path)
                
                # 生成缩略图路径
                thumbnail_filename = f"thumb_{filename}"
                thumbnail_path = os.path.join(upload_dir, thumbnail_filename)
                
                # 生成缩略图
                try:
                    with Image.open(file_path) as img:
                        img.thumbnail((100, 100))  # 调整为100x100的缩略图
                        img.save(thumbnail_path)
                except Exception as e:
                    self.logger.error(f"生成缩略图失败: {str(e)}")
                    # 如果缩略图生成失败，使用原图作为缩略图
                    thumbnail_filename = filename
                
                # 构建文件信息
                file_info = {
                    "original_name": original_filename,
                    "saved_name": filename,
                    "thumbnail_name": thumbnail_filename,
                    "file_type": file_ext,
                    "file_url": f"/api/chat/files/{username}/{filename}",
                    "thumbnail_url": f"/api/chat/files/{username}/{thumbnail_filename}",
                    "is_image": True
                }
                
                file_info_list.append(file_info)
            
            if not file_info_list:
                return jsonify({"error": "没有有效的图片文件上传"}), 400
            
            # 返回成功结果和文件信息
            return jsonify({
                "success": True,
                "message": f"成功上传 {len(file_info_list)} 个文件",
                "files": file_info_list
            })
            
        except Exception as e:
            self.logger.error(f"文件上传处理失败: {str(e)}")
            return jsonify({"error": f"文件上传失败: {str(e)}"}), 500

    def get_chat_file(self, username, filename):
        """获取上传的聊天文件"""
        try:
            # 验证路径安全性
            file_path = safe_join(current_app.root_path, 'upload', username, filename)
            if not os.path.exists(file_path):
                return jsonify({"error": "文件不存在"}), 404
            
            # 返回文件
            return send_file(file_path)
        except Exception as e:
            self.logger.error(f"获取文件失败: {str(e)}")
            return jsonify({"error": f"获取文件失败: {str(e)}"}), 500 