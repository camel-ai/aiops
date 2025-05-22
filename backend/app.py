import os
import logging
import traceback
from flask import Flask, jsonify, request
from flask_cors import CORS
# 使用相对导入
from config.config import load_config
from db.db import init_db, close_db
from routes.routes import setup_routes
from controllers.chat_controller import ChatController
from controllers.auth_controller import AuthController
from controllers.cloud_controller import CloudController
from controllers.deploy_controller import DeployController
from controllers.topology_controller import TopologyController
from controllers.file_controller import FileController
from utils.auth import require_login, token_required, get_current_user
from controllers.clouds_controller import CloudsController

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 启用CORS

# 加载配置
config = load_config()

# 配置上传文件夹
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'upload')
# 确保上传文件夹存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# 允许的文件扩展名
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
# 设置最大上传文件大小为16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 设置日志级别
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# 初始化控制器
auth_controller = AuthController(config)
chat_controller = ChatController(config)
cloud_controller = CloudController(config)
deploy_controller = DeployController(config)  # 部署控制器
topology_controller = TopologyController(config)  # 拓扑图控制器
file_controller = FileController(config)  # 文件控制器
clouds_controller = CloudsController(config)  # 云服务提供商控制器

# 添加CORS请求日志记录
@app.before_request
def log_request_info():
    logging.info(f"请求方法: {request.method}")
    logging.info(f"请求路径: {request.path}")
    logging.info(f"请求头: {request.headers}")
    logging.info(f"请求源: {request.origin if hasattr(request, 'origin') else request.headers.get('Origin')}")

# 初始化数据库连接
db_error = init_db(config)
if db_error:
    logging.error(f"数据库连接失败: {db_error}")
else:
    # 初始化clouds表
    clouds_controller.clouds_model.init_table()
    logging.info("初始化clouds表完成")

# 设置路由
setup_routes(app, config)

# 错误处理
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "资源不存在"}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({"error": "服务器内部错误"}), 500

if __name__ == "__main__":
    try:
        logging.info("服务器启动在 :8081 端口")
        # 注意：当作为模块运行时，debug=True 可能导致重载问题，暂时禁用
        app.run(host='0.0.0.0', port=8081, debug=False)
    finally:
        close_db()

