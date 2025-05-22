import os
import logging
from typing import Dict, Any, List
from flask import request, jsonify, send_file
from config.config import Config

class FileController:
    """处理文件相关请求的控制器"""
    
    def __init__(self, config: Config):
        """初始化控制器
        
        Args:
            config (Config): 应用配置
        """
        self.config = config
        self.logger = logging.getLogger('file_controller')
    
    def list_files(self) -> Dict[str, Any]:
        """列出文件
        
        Returns:
            Dict[str, Any]: 包含文件列表的响应
        """
        try:
            # 获取请求数据
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "请求参数缺失"}), 400
            
            deploy_id = data.get('id')
            deploy_type = data.get('type', 'deploy')  # 默认为部署类型
            
            if not deploy_id:
                return jsonify({"success": False, "message": "缺少部署ID"}), 400
            
            self.logger.info(f"列出文件: ID={deploy_id}, 类型={deploy_type}")
            
            # 确定目录路径
            if deploy_type == 'query':
                base_dir = 'query'
            elif deploy_type == 'template' or deploy_type == 'deployments':
                # 对于模板部署类型，使用deployments目录
                base_dir = 'deployments'
            else:
                # 默认为deploy类型
                base_dir = 'deploy'

            tf_dir = os.path.join(base_dir, deploy_id)
            
            # 检查目录是否存在
            if not os.path.exists(tf_dir):
                self.logger.warning(f"找不到目录: {tf_dir}")
                return jsonify({
                    "success": False, 
                    "message": f"找不到部署目录: {tf_dir}"
                }), 404
            
            # 列出目录中的所有.tf文件
            tf_files = self._list_tf_files(tf_dir)
            
            # 检查是否有tfstate文件
            tfstate_path = os.path.join(tf_dir, 'terraform.tfstate')
            if os.path.exists(tfstate_path):
                tf_files.append({
                    "name": "terraform.tfstate",
                    "path": tfstate_path,
                    "size": os.path.getsize(tfstate_path),
                    "lastModified": os.path.getmtime(tfstate_path)
                })
            
            # 检查是否有日志文件 - 标准terraform.log或部署日志
            log_files = ['terraform.log', 'deployment.log']
            for log_file in log_files:
                log_path = os.path.join(tf_dir, log_file)
                if os.path.exists(log_path):
                    tf_files.append({
                        "name": log_file,
                        "path": log_path,
                        "size": os.path.getsize(log_path),
                        "lastModified": os.path.getmtime(log_path)
                    })
            
            # 检查是否有状态文件 - 模板部署
            status_path = os.path.join(tf_dir, 'status.json')
            if os.path.exists(status_path):
                tf_files.append({
                    "name": "status.json",
                    "path": status_path,
                    "size": os.path.getsize(status_path),
                    "lastModified": os.path.getmtime(status_path)
                })
            
            return jsonify({
                "success": True, 
                "message": f"找到 {len(tf_files)} 个文件",
                "files": tf_files
            })
            
        except Exception as e:
            self.logger.error(f"列出文件失败: {str(e)}", exc_info=True)
            return jsonify({
                "success": False, 
                "message": f"列出文件时发生错误: {str(e)}"
            }), 500
    
    def _list_tf_files(self, directory: str) -> List[Dict[str, Any]]:
        """列出目录中的所有.tf文件
        
        Args:
            directory (str): 目录路径
            
        Returns:
            List[Dict[str, Any]]: 文件信息列表
        """
        result = []
        
        try:
            for filename in os.listdir(directory):
                if filename.endswith('.tf'):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        result.append({
                            "name": filename,
                            "path": file_path,
                            "size": os.path.getsize(file_path),
                            "lastModified": os.path.getmtime(file_path)
                        })
        except Exception as e:
            self.logger.error(f"列出.tf文件失败: {str(e)}", exc_info=True)
        
        return result
    
    def download_file(self) -> Any:
        """下载文件
        
        Returns:
            Any: 文件下载响应
        """
        try:
            # 获取文件路径参数
            file_path = request.args.get('path')
            
            if not file_path:
                return jsonify({"success": False, "message": "缺少文件路径"}), 400
            
            self.logger.info(f"下载文件: {file_path}")
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                self.logger.warning(f"找不到文件: {file_path}")
                return jsonify({
                    "success": False, 
                    "message": f"找不到文件: {file_path}"
                }), 404
            
            # 获取文件名
            filename = os.path.basename(file_path)
            
            # 确定MIME类型
            mime_type = self._get_mime_type(file_path)
            
            # 返回文件
            return send_file(
                file_path,
                mimetype=mime_type,
                as_attachment=True,
                download_name=filename
            )
            
        except Exception as e:
            self.logger.error(f"下载文件失败: {str(e)}", exc_info=True)
            return jsonify({
                "success": False, 
                "message": f"下载文件时发生错误: {str(e)}"
            }), 500
    
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
    
    def get_deployment_file(self) -> Any:
        """获取部署相关文件，例如拓扑图
        
        Returns:
            Any: 文件响应
        """
        try:
            # 获取部署ID和文件名
            deploy_id = request.args.get('deploy_id')
            filename = request.args.get('filename', 'graph.png')  # 默认为拓扑图
            deploy_type = request.args.get('type', 'deploy')  # 默认为deploy类型
            
            if not deploy_id:
                return jsonify({"success": False, "message": "缺少部署ID"}), 400
            
            self.logger.info(f"获取部署文件: ID={deploy_id}, 文件={filename}, 类型={deploy_type}")
            
            # 根据部署类型确定基础目录
            if deploy_type == 'query':
                base_dir = 'query'
            elif deploy_type == 'template':
                # 对于模板部署类型，使用deployments目录
                base_dir = 'deployments'
            else:
                # 默认为deploy类型
                base_dir = 'deploy'
            
            # 尝试多个可能的文件路径
            possible_paths = [
                os.path.join(base_dir, deploy_id, 'output', filename),          # 首选：在output子目录中使用请求的文件名
                os.path.join(base_dir, deploy_id, filename),                    # 直接在部署目录下
                os.path.join(base_dir, deploy_id, 'output', deploy_id + '.png') # 使用部署ID命名的文件
            ]
            
            # 检查文件是否存在于任何一个可能的路径
            file_path = None
            for path in possible_paths:
                self.logger.info(f"检查路径: {path}")
                if os.path.exists(path) and os.path.isfile(path):
                    file_path = path
                    file_size = os.path.getsize(path)
                    self.logger.info(f"找到文件: {file_path}, 大小: {file_size} 字节")
                    
                    # 检查文件是否为空或太小（可能不是有效的图像文件）
                    if file_size < 100:  # 一个有效的PNG图像通常至少有100字节
                        self.logger.warning(f"文件太小，可能不是有效的图像: {file_path}, 大小: {file_size} 字节")
                        continue  # 尝试下一个路径
                    
                    # 检查文件的前几个字节，确认它是PNG格式
                    if filename.lower().endswith('.png'):
                        try:
                            with open(path, 'rb') as f:
                                header = f.read(8)
                                # PNG文件头标记: 89 50 4E 47 0D 0A 1A 0A
                                png_signature = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'
                                if header != png_signature:
                                    self.logger.warning(f"文件不是有效的PNG图像: {path}")
                                    self.logger.warning(f"文件头: {header.hex()}, 期望PNG头: {png_signature.hex()}")
                                    continue  # 尝试下一个路径
                        except Exception as e:
                            self.logger.warning(f"检查文件头时出错: {str(e)}")
                            continue  # 尝试下一个路径
                    
                    break  # 找到有效文件，停止查找
            
            if not file_path:
                # 如果没有找到文件路径，且是模板部署类型，则尝试运行terraform生成拓扑图
                if deploy_type == 'template' and filename.lower() == 'graph.png':
                    self.logger.info(f"尝试为模板部署生成拓扑图: {deploy_id}")
                    
                    # 检查目录是否存在
                    template_dir = os.path.join(base_dir, deploy_id)
                    if os.path.exists(template_dir):
                        # 创建输出目录
                        output_dir = os.path.join(template_dir, 'output')
                        os.makedirs(output_dir, exist_ok=True)
                        
                        # 生成拓扑图
                        graph_path = os.path.join(output_dir, filename)
                        try:
                            import subprocess
                            cmd = f"cd {template_dir} && terraform graph -type=plan | dot -Tpng > \"{graph_path}\""
                            process = subprocess.run(
                                cmd,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE
                            )
                            
                            if process.returncode == 0 and os.path.exists(graph_path) and os.path.getsize(graph_path) > 100:
                                self.logger.info(f"成功生成模板部署拓扑图: {graph_path}")
                                file_path = graph_path
                            else:
                                self.logger.warning(f"生成模板部署拓扑图失败: {cmd}")
                                self.logger.warning(f"退出代码: {process.returncode}")
                                self.logger.warning(f"错误输出: {process.stderr.decode('utf-8', errors='ignore')}")
                        except Exception as e:
                            self.logger.error(f"尝试生成拓扑图失败: {str(e)}", exc_info=True)
                
                # 如果仍未找到有效文件
                if not file_path:
                    self.logger.warning(f"找不到有效文件: {filename} (部署ID: {deploy_id}, 类型: {deploy_type})")
                    return jsonify({
                        "success": False, 
                        "message": f"找不到有效文件: {filename}"
                    }), 404
            
            # 确定MIME类型
            mime_type = self._get_mime_type(file_path)
            self.logger.info(f"文件MIME类型: {mime_type}")
            
            # 使用绝对路径，确保文件能被找到
            abs_path = os.path.abspath(file_path)
            self.logger.info(f"返回文件的绝对路径: {abs_path}")
            
            # 返回文件，设置明确的mime类型和缓存控制
            response = send_file(
                abs_path,
                mimetype=mime_type,
                as_attachment=False,  # 直接在浏览器中显示
                etag=False,
                max_age=0,
                conditional=False
            )
            
            # 添加额外的头信息，确保不缓存
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            response.headers["Content-Disposition"] = "inline"  # 确保内联显示
            
            return response
            
        except Exception as e:
            self.logger.error(f"获取部署文件失败: {str(e)}", exc_info=True)
            return jsonify({
                "success": False, 
                "message": f"获取部署文件时发生错误: {str(e)}"
            }), 500 