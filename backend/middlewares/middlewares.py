import logging
from functools import wraps
from flask import request, jsonify
import jwt

# 使用相对导入
from config.config import Config

def setup_middlewares(app, config: Config):
    """设置中间件"""
    
    @app.before_request
    def log_request_info():
        """记录每个请求的信息"""
        # 避免记录OPTIONS请求的日志，减少干扰
        if request.method != "OPTIONS":
            logging.debug(f"请求路径: {request.path}")
            logging.debug(f"请求方法: {request.method}")
            logging.debug(f"请求头: {request.headers}")
            # 尝试获取请求体，注意处理可能的错误
            try:
                body = request.get_data(as_text=True)
                if body:
                    logging.debug(f"请求体: {body[:500]}...") # 只记录前500个字符
            except Exception as e:
                logging.warning(f"无法读取请求体: {e}")

    @app.after_request
    def log_response_info(response):
        """记录每个响应的信息"""
        # 避免记录OPTIONS请求的日志
        if request.method != "OPTIONS":
            logging.debug(f"响应状态码: {response.status_code}")
            # 尝试获取响应体，注意处理可能的错误和流式响应
            try:
                if not response.direct_passthrough:
                    body = response.get_data(as_text=True)
                    if body:
                        logging.debug(f"响应体: {body[:500]}...") # 只记录前500个字符
            except Exception as e:
                logging.warning(f"无法读取响应体: {e}")
        return response

    # 定义认证中间件
    def auth_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = None
            # 从 Authorization 头获取令牌
            if "Authorization" in request.headers:
                auth_header = request.headers["Authorization"]
                try:
                    token = auth_header.split(" ")[1]
                except IndexError:
                    logging.warning("无效的 Authorization 头格式")
                    return jsonify({"error": "无效的令牌格式"}), 401

            if not token:
                logging.warning("缺少 Authorization 令牌")
                return jsonify({"error": "缺少认证令牌"}), 401

            try:
                # 验证JWT令牌
                payload = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
                # 将用户信息附加到请求对象，以便后续路由使用
                request.user_id = payload["user_id"]
                request.username = payload["username"]
                # 添加完整的用户信息对象
                request.current_user = payload
                logging.info(f"用户认证成功: {request.username} (ID: {request.user_id})")
            except jwt.ExpiredSignatureError:
                logging.warning("令牌已过期")
                return jsonify({"error": "令牌已过期"}), 401
            except jwt.InvalidTokenError as e:
                logging.error(f"无效的令牌: {e}")
                return jsonify({"error": "无效的令牌"}), 401

            return f(*args, **kwargs)
        return decorated

    # 将认证中间件附加到app对象，以便在路由中使用 @app.auth_middleware
    app.auth_middleware = auth_required

