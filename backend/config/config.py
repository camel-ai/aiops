import os
import logging
from dotenv import load_dotenv

# 尝试加载.env文件
load_dotenv()

class Config:
    def __init__(self):
        # 基本配置
        self.debug = os.getenv('DEBUG', 'False').lower() == 'true'
        
        # 数据库配置
        self.db_host = os.getenv('DB_HOST', 'localhost')
        self.db_user = os.getenv('DB_USER', 'root')
        self.db_password = os.getenv('DB_PASSWORD', '')
        self.db_name = os.getenv('DB_NAME', 'mcdp')
        
        # JWT配置
        self.jwt_secret = os.getenv('JWT_SECRET', 'mcdp-jwt-secret-key')
        self.jwt_token_expires = int(os.getenv('JWT_TOKEN_EXPIRES', '86400'))  # 默认一天
        # 添加jwt_expires引用同一个值，以兼容现有代码
        self.jwt_expires = self.jwt_token_expires
        
        # 项目路径配置
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.templates_dir = os.path.join(self.base_dir, 'templates')
        self.static_dir = os.path.join(self.base_dir, 'static')
        self.uploads_dir = os.path.join(self.static_dir, 'uploads')
        self.downloads_dir = os.path.join(self.static_dir, 'downloads')
        
        # 确保目录存在
        for dir_path in [self.static_dir, self.uploads_dir, self.downloads_dir]:
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path)
                except Exception as e:
                    logging.error(f"创建目录失败: {dir_path}, 错误: {e}")
        
        # 设置应用密钥
        self.secret_key = os.getenv('SECRET_KEY', 'mcdp-secret-key')
        
        # DeepSeek API Key
        self.deepseek_api_key = os.getenv('DEEPSEEK_API_KEY', '')
        
        # AI模型提供商配置
        self.ai_model_provider = os.getenv('AI_MODEL_PROVIDER', 'openai').lower()
        
        # OpenAI API 配置
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        self.openai_api_base_url = os.getenv('OPENAI_API_BASE_URL', 'https://api.openai.com/v1')
        self.openai_api_model = os.getenv('OPENAI_API_MODEL', 'gpt-4o')
        
        # Anthropic API 配置
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY', '')
        self.anthropic_api_base_url = os.getenv('ANTHROPIC_API_BASE_URL', 'https://api.anthropic.com/v1')
        self.anthropic_api_model = os.getenv('ANTHROPIC_API_MODEL', 'claude-3-5-sonnet-20241022')
        
        # 打印配置信息
        if self.debug:
            logging.info("配置初始化完成")
            logging.info(f"数据库配置: Host={self.db_host}, User={self.db_user}, DB={self.db_name}")
            logging.info(f"项目路径: {self.base_dir}")
            logging.info(f"模板目录: {self.templates_dir}")
            logging.info(f"静态文件目录: {self.static_dir}")
            logging.info(f"上传目录: {self.uploads_dir}")
            logging.info(f"下载目录: {self.downloads_dir}")
            logging.info(f"AI模型提供商: {self.ai_model_provider}")
            if self.ai_model_provider == 'openai':
                logging.info(f"OpenAI API Base URL: {self.openai_api_base_url}")
                logging.info(f"OpenAI API Model: {self.openai_api_model}")
            elif self.ai_model_provider == 'anthropic':
                logging.info(f"Anthropic API Base URL: {self.anthropic_api_base_url}")
                logging.info(f"Anthropic API Model: {self.anthropic_api_model}")

def load_config():
    """加载配置"""
    return Config()
