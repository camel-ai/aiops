import jwt
import logging
from datetime import datetime, timedelta
from config.config import Config
from functools import wraps
from flask import request, jsonify

# 初始化日志记录器
logger = logging.getLogger(__name__)

def create_token(user_id, username, expires_delta=None):
    """
    创建JWT令牌
    
    Args:
        user_id: 用户ID
        username: 用户名
        expires_delta: 过期时间差
        
    Returns:
        jwt令牌
    """
    if expires_delta is None:
        expires_delta = timedelta(days=90)  # 默认90天有效期，原来是30天
    
    expire = datetime.utcnow() + expires_delta
    
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": expire
    }
    
    token = jwt.encode(payload, Config().jwt_secret, algorithm="HS256")
    
    return token

def decode_token(token):
    """
    解码JWT令牌
    
    Args:
        token: JWT令牌
        
    Returns:
        解码后的payload或None
    """
    try:
        logger.info(f"解码JWT令牌: {token[:20]}...")
        payload = jwt.decode(token, Config().jwt_secret, algorithms=["HS256"])
        logger.info(f"解码成功，获取到用户信息: {payload}")
        return payload
    except jwt.PyJWTError as e:
        logger.error(f"JWT解码失败: {str(e)}")
        return None

def require_login(f):
    """
    登录验证装饰器，检查请求头中的JWT令牌是否有效
    
    Args:
        f: 被装饰的函数
        
    Returns:
        包装后的函数
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning("请求缺少有效的Authorization头")
            return jsonify({"error": "请先登录", "code": 401}), 401
            
        token = auth_header.split(' ')[1]
        payload = decode_token(token)
        
        if not payload:
            logger.warning("无效的令牌")
            return jsonify({"error": "登录已过期，请重新登录", "code": 401}), 401
            
        # 将用户信息添加到request对象中，方便后续使用
        request.current_user = payload
        
        return f(*args, **kwargs)
    return decorated

def token_required(f):
    """
    令牌验证装饰器，与require_login功能相同，为了保持代码一致性重命名
    
    Args:
        f: 被装饰的函数
        
    Returns:
        包装后的函数
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logger.warning("请求缺少有效的Authorization头")
            return jsonify({"error": "请先登录", "code": 401}), 401
            
        token = auth_header.split(' ')[1]
        payload = decode_token(token)
        
        if not payload:
            logger.warning("无效的令牌")
            return jsonify({"error": "登录已过期，请重新登录", "code": 401}), 401
            
        # 将用户信息添加到request对象中，方便后续使用
        request.current_user = payload
        
        return f(*args, **kwargs)
    return decorated

def get_current_user(request):
    """
    从请求中获取当前用户信息
    
    Args:
        request: Flask请求对象
        
    Returns:
        用户信息字典
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return {"user_id": 0, "username": "guest"}
            
    token = auth_header.split(' ')[1]
    payload = decode_token(token)
    
    if not payload:
        return {"user_id": 0, "username": "guest"}
    
    return payload 