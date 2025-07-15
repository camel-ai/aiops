import logging
from typing import Dict, Any, List
from flask import request, jsonify
from models.clouds_model import CloudsModel
from config.config import Config
import json

class CloudsController:
    """云服务提供商控制器类，处理与云服务提供商相关的请求"""
    
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 初始化云服务提供商模型
        self.clouds_model = CloudsModel({
            'host': config.db_host,
            'user': config.db_user,
            'password': config.db_password,
            'database': config.db_name
        })
        
        # 确保clouds表存在
        self.clouds_model.init_table()
    
    def get_all_clouds(self):
        """获取所有云服务提供商列表"""
        try:
            clouds = self.clouds_model.get_all_clouds()
            self.logger.info(f"查询到{len(clouds)}个云服务提供商")
            
            return jsonify({
                "success": True,
                "clouds": clouds
            })
        except Exception as e:
            self.logger.error(f"获取云服务提供商列表出错: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"获取云服务提供商列表失败: {str(e)}"
            }), 500
    
    def get_cloud_by_id(self):
        """根据ID获取云服务提供商信息"""
        try:
            cloud_id = request.args.get('id')
            if not cloud_id:
                return jsonify({
                    "success": False,
                    "error": "缺少云服务提供商ID参数"
                }), 400
            
            cloud = self.clouds_model.get_cloud_by_id(int(cloud_id))
            if not cloud:
                return jsonify({
                    "success": False,
                    "error": f"未找到ID为{cloud_id}的云服务提供商"
                }), 404
            
            return jsonify({
                "success": True,
                "cloud": cloud
            })
        except Exception as e:
            self.logger.error(f"获取云服务提供商信息出错: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"获取云服务提供商信息失败: {str(e)}"
            }), 500
    
    def get_cloud_by_name(self):
        """根据名称获取云服务提供商信息"""
        try:
            name = request.args.get('name')
            if not name:
                return jsonify({
                    "success": False,
                    "error": "缺少云服务提供商名称参数"
                }), 400
            
            cloud = self.clouds_model.get_cloud_by_name(name)
            if not cloud:
                return jsonify({
                    "success": False,
                    "error": f"未找到名称为{name}的云服务提供商"
                }), 404
            
            return jsonify({
                "success": True,
                "cloud": cloud
            })
        except Exception as e:
            self.logger.error(f"获取云服务提供商信息出错: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"获取云服务提供商信息失败: {str(e)}"
            }), 500
    
    def add_cloud(self):
        """添加新的云服务提供商"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "缺少请求数据"
                }), 400
            
            name = data.get('name')
            if not name:
                return jsonify({
                    "success": False,
                    "error": "缺少云服务提供商名称"
                }), 400
            
            # 检查同名云服务提供商是否已存在
            existing_cloud = self.clouds_model.get_cloud_by_name(name)
            if existing_cloud:
                return jsonify({
                    "success": False,
                    "error": f"名称为{name}的云服务提供商已存在"
                }), 409
            
            logo = data.get('logo')
            provider = data.get('provider')
            regions = data.get('regions', [])
            is_active = data.get('is_active', True)
            
            success = self.clouds_model.add_cloud(
                name=name,
                logo=logo,
                provider=provider,
                regions=regions,
                is_active=is_active
            )
            
            if success:
                # 获取新添加的云服务提供商
                new_cloud = self.clouds_model.get_cloud_by_name(name)
                
                return jsonify({
                    "success": True,
                    "message": f"成功添加云服务提供商: {name}",
                    "cloud": new_cloud
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "添加云服务提供商失败"
                }), 500
                
        except Exception as e:
            self.logger.error(f"添加云服务提供商出错: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"添加云服务提供商失败: {str(e)}"
            }), 500
    
    def update_cloud(self):
        """更新云服务提供商信息"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "success": False,
                    "error": "缺少请求数据"
                }), 400
            
            cloud_id = data.get('id')
            if not cloud_id:
                return jsonify({
                    "success": False,
                    "error": "缺少云服务提供商ID"
                }), 400
            
            # 检查云服务提供商是否存在
            existing_cloud = self.clouds_model.get_cloud_by_id(cloud_id)
            if not existing_cloud:
                return jsonify({
                    "success": False,
                    "error": f"未找到ID为{cloud_id}的云服务提供商"
                }), 404
            
            # 检查name是否需要更新，如果需要则检查同名是否已存在
            if 'name' in data and data['name'] != existing_cloud['name']:
                name_check = self.clouds_model.get_cloud_by_name(data['name'])
                if name_check:
                    return jsonify({
                        "success": False,
                        "error": f"名称为{data['name']}的云服务提供商已存在"
                    }), 409
            
            # 执行更新
            update_data = {}
            for field in ['name', 'logo', 'provider', 'regions', 'is_active']:
                if field in data:
                    update_data[field] = data[field]
            
            success = self.clouds_model.update_cloud(cloud_id, update_data)
            
            if success:
                # 获取更新后的云服务提供商
                updated_cloud = self.clouds_model.get_cloud_by_id(cloud_id)
                
                return jsonify({
                    "success": True,
                    "message": f"成功更新云服务提供商ID: {cloud_id}",
                    "cloud": updated_cloud
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "更新云服务提供商失败"
                }), 500
                
        except Exception as e:
            self.logger.error(f"更新云服务提供商出错: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"更新云服务提供商失败: {str(e)}"
            }), 500
    
    def delete_cloud(self):
        """删除云服务提供商"""
        try:
            cloud_id = request.args.get('id')
            if not cloud_id:
                return jsonify({
                    "success": False,
                    "error": "缺少云服务提供商ID参数"
                }), 400
            
            # 检查云服务提供商是否存在
            existing_cloud = self.clouds_model.get_cloud_by_id(int(cloud_id))
            if not existing_cloud:
                return jsonify({
                    "success": False,
                    "error": f"未找到ID为{cloud_id}的云服务提供商"
                }), 404
            
            success = self.clouds_model.delete_cloud(int(cloud_id))
            
            if success:
                return jsonify({
                    "success": True,
                    "message": f"成功删除云服务提供商ID: {cloud_id}"
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "删除云服务提供商失败"
                }), 500
                
        except Exception as e:
            self.logger.error(f"删除云服务提供商出错: {str(e)}")
            return jsonify({
                "success": False,
                "error": f"删除云服务提供商失败: {str(e)}"
            }), 500 