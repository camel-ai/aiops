#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
import subprocess
import traceback
from config.config import Config
from flask import request, jsonify, send_file
import shutil
from typing import Dict, Any

# 不要在顶部导入PIL，改为在需要时导入
# from PIL import Image, ImageDraw, ImageFont

class TopologyController:
    """拓扑图控制器，处理拓扑图生成和获取"""

    def __init__(self, config: Config):
        """初始化拓扑图控制器
        
        Args:
            config (Config): 配置对象
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def generate_topology(self) -> Dict[str, Any]:
        """生成拓扑图
        
        Returns:
            Dict[str, Any]: 包含拓扑图URL的响应
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "缺少参数"}), 400
            
            deploy_id = data.get('id')
            deploy_type = data.get('type', 'deploy')  # 默认为部署类型
            
            if not deploy_id:
                return jsonify({"success": False, "message": "缺少部署ID"}), 400
            
            self.logger.info(f"生成拓扑图: ID={deploy_id}, 类型={deploy_type}")
            
            # 确定工作目录路径（使用相对路径，后续转为绝对路径）
            if deploy_type == 'deploy':
                work_dir = 'deploy'
            elif deploy_type == 'query': 
                work_dir = 'query'
            elif deploy_type == 'template':
                # 模板部署使用deployments目录
                work_dir = 'deployments'
            else:
                work_dir = 'deploy'  # 默认
                
            tf_dir = os.path.join(work_dir, deploy_id)
            
            # 确保工作目录存在 - 使用绝对路径
            abs_tf_dir = os.path.join(self.base_dir, tf_dir)
            if not os.path.exists(abs_tf_dir):
                # 创建工作目录
                os.makedirs(abs_tf_dir, exist_ok=True)
                self.logger.info(f"已创建工作目录: {abs_tf_dir}")
            
            # 创建用于保存拓扑图的输出目录 - 使用绝对路径
            output_dir = os.path.join(abs_tf_dir, 'output')
            os.makedirs(output_dir, exist_ok=True)
            self.logger.info(f"已创建输出目录: {output_dir}")
            
            # 设置拓扑图文件路径（使用graph.png作为文件名，与前端请求匹配）
            graph_path = os.path.join(output_dir, "graph.png")
            self.logger.info(f"拓扑图将保存到: {graph_path}")
            
            # 额外创建一个以部署ID命名的副本，用于兼容性
            id_graph_path = os.path.join(output_dir, f"{deploy_id}.png")
            
            # 生成拓扑图 - 使用terraform graph命令
            if self.generate_graph_image(abs_tf_dir, graph_path):
                # 如果生成成功，创建一个副本（用于兼容旧版本的请求）
                try:
                    if not os.path.exists(id_graph_path) and os.path.exists(graph_path):
                        shutil.copy2(graph_path, id_graph_path)
                        self.logger.info(f"已创建拓扑图副本: {id_graph_path}")
                except Exception as copy_error:
                    self.logger.warning(f"创建拓扑图副本时出错: {str(copy_error)}")
                
                # 构建访问URL（根据部署类型使用不同的路径，但都保持与前端请求格式一致）
                image_url = f"/api/files/deployments/{deploy_id}/graph.png"
                self.logger.info(f"生成的图像URL: {image_url}")
                
                return jsonify({
                    "success": True,
                    "message": "拓扑图生成成功",
                    "imageUrl": image_url
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "拓扑图生成失败"
                }), 500
                
        except Exception as e:
            self.logger.error(f"生成拓扑图失败: {str(e)}", exc_info=True)
            return jsonify({
                "success": False, 
                "message": f"生成拓扑图时发生错误: {str(e)}"
            }), 500
    
    def generate_graph_image(self, tf_dir: str, output_path: str) -> bool:
        """生成拓扑图图像文件
        
        Args:
            tf_dir (str): Terraform工作目录
            output_path (str): 图像输出路径
            
        Returns:
            bool: 是否成功生成图像
        """
        try:
            self.logger.info(f"开始生成拓扑图: {tf_dir} -> {output_path}")
            
            # 使用shell命令执行完整的管道命令：terraform graph -type=plan | dot -Tpng >graph.png
            cmd = f"cd {tf_dir} && terraform graph -type=plan | dot -Tpng > \"{output_path}\""
            self.logger.info(f"执行命令: {cmd}")
            
            # 在shell中执行命令
            process = subprocess.run(
                cmd,
                shell=True,  # 使用shell执行以支持管道
                cwd=None,    # cwd在命令中已通过cd设置
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 检查命令执行结果
            if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                self.logger.info(f"成功生成拓扑图: {output_path}")
                
                # 额外验证生成的PNG文件
                try:
                    with open(output_path, 'rb') as f:
                        header = f.read(8)
                        png_signature = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'
                        if header == png_signature:
                            self.logger.info(f"验证PNG文件有效: {output_path}")
                            return True
                        else:
                            self.logger.warning(f"生成的文件不是有效的PNG: 文件头={header.hex()}, 期望={png_signature.hex()}")
                except Exception as e:
                    self.logger.warning(f"验证PNG文件时出错: {str(e)}")
            else:
                # 记录详细的错误信息
                if process.returncode != 0:
                    self.logger.warning(f"命令执行失败，返回代码: {process.returncode}")
                    self.logger.warning(f"标准错误输出: {process.stderr.decode('utf-8', errors='ignore')}")
                elif not os.path.exists(output_path):
                    self.logger.warning(f"命令执行后输出文件不存在: {output_path}")
                elif os.path.getsize(output_path) <= 100:
                    self.logger.warning(f"生成的文件太小: {os.path.getsize(output_path)} 字节")
            
            # 如果生成失败或验证失败，创建简单的替代图像
            return self._create_simple_image(output_path)
            
        except Exception as e:
            self.logger.error(f"生成拓扑图图像失败: {str(e)}", exc_info=True)
            return self._create_simple_image(output_path)
    
    def _create_simple_image(self, output_path: str) -> bool:
        """创建简单的替代图像
        
        Args:
            output_path (str): 图像输出路径
            
        Returns:
            bool: 是否成功创建图像
        """
        try:
            self.logger.info(f"创建简单的替代图像: {output_path}")
            
            # 确保输出路径是绝对路径
            if not os.path.isabs(output_path):
                output_path = os.path.join(self.base_dir, output_path)
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)
            
            # 动态导入PIL
            try:
                from PIL import Image, ImageDraw, ImageFont
            except ImportError:
                self.logger.error("无法导入PIL，无法创建替代图像")
                return False
            
            # 创建透明背景图像
            width, height = 800, 400
            image = Image.new('RGBA', (width, height), color=(255, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            
            # 绘制蓝色边框
            border_width = 2
            draw.rectangle(
                [(border_width, border_width), (width - border_width, height - border_width)],
                outline=(0, 0, 255, 255),
                width=border_width
            )
            
            # 添加文本
            text = "拓扑图无法生成 - 使用临时图像替代"
            try:
                # 尝试加载字体，如果失败则使用默认字体
                try:
                    font = ImageFont.truetype("arial.ttf", 20)
                except:
                    try:
                        font = ImageFont.truetype("DejaVuSans.ttf", 20)
                    except:
                        font = ImageFont.load_default()
                        
                # 文本位置居中
                text_position = (width/2, height/2)
                text_color = (0, 0, 0, 255)  # 黑色文本
                
                # 检查是否有anchor参数
                try:
                    draw.text(text_position, text, fill=text_color, font=font, anchor="mm")
                except TypeError:
                    # 如果没有anchor参数，手动计算位置
                    text_bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]
                    x = text_position[0] - text_width // 2
                    y = text_position[1] - text_height // 2
                    draw.text((x, y), text, fill=text_color, font=font)
            except Exception as e:
                self.logger.error(f"绘制文本时出错: {str(e)}")
                # 如果找不到字体，使用默认绘制方法
                draw.text((width/2 - 150, height/2 - 10), text, fill=(0, 0, 0, 255))
            
            # 转换为RGB模式并保存为PNG
            rgb_image = image.convert('RGB')
            
            # 保存图像时使用临时文件
            temp_path = output_path + '.tmp'
            try:
                rgb_image.save(temp_path, format='PNG')
                self.logger.info(f"图像已保存到临时路径: {temp_path}")
                
                # 验证生成的文件
                if os.path.exists(temp_path) and os.path.getsize(temp_path) > 100:
                    # 检查文件头
                    with open(temp_path, 'rb') as f:
                        header = f.read(8)
                        png_signature = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'
                        if header == png_signature:
                            # 文件有效，移动到最终位置
                            if os.path.exists(output_path):
                                os.remove(output_path)
                            os.rename(temp_path, output_path)
                            self.logger.info(f"临时图像已移动到最终路径: {output_path}")
                        else:
                            self.logger.warning(f"生成的临时文件不是有效的PNG: {temp_path}")
                            return False
                else:
                    self.logger.warning(f"临时文件太小或不存在: {temp_path}")
                    return False
            except Exception as save_error:
                self.logger.error(f"保存图像失败: {save_error}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.logger.info(f"成功创建替代图像: {output_path}")
                return True
            
            self.logger.warning(f"创建替代图像失败: {output_path}")
            return False
            
        except Exception as e:
            self.logger.error(f"创建替代图像失败: {str(e)}", exc_info=True)
            return False
    
    def get_topology_image(self, path):
        """获取拓扑图图像
        
        Args:
            path: 图像路径
            
        Returns:
            拓扑图图像文件
        """
        try:
            # 构建完整路径
            image_path = os.path.join(self.base_dir, path)
            
            # 检查文件是否存在
            if not os.path.exists(image_path):
                self.logger.warning(f"拓扑图图像不存在: {image_path}")
                return jsonify({
                    "success": False,
                    "message": "拓扑图图像不存在"
                }), 404
            
            # 返回图像文件
            return send_file(image_path, mimetype='image/png')
            
        except Exception as e:
            self.logger.error(f"获取拓扑图图像时出错: {str(e)}")
            self.logger.error(traceback.format_exc())
            return jsonify({
                "success": False,
                "message": f"获取拓扑图图像失败: {str(e)}"
            }), 500 