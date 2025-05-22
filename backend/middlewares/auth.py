#!/usr/bin/env python
# -*- coding: utf-8 -*-

import functools
import logging
from flask import request, jsonify, current_app
from utils.auth import get_current_user


def jwt_required(f):
    """JWT认证装饰器，用于保护需要认证的API端点
    
    这个装饰器检查请求头中是否包含有效的JWT令牌
    """
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        logger = logging.getLogger('auth')
        
        # 获取当前用户信息
        current_user = get_current_user(request)
        
        # 检查是否获取到用户信息
        if not current_user:
            logger.warning("缺少有效的认证令牌")
            return jsonify({"error": "需要认证", "message": "请提供有效的认证令牌"}), 401
        
        # 将用户信息注入到请求中
        request.current_user = current_user
        
        return f(*args, **kwargs)
    return decorated_function 