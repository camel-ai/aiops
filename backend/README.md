# 多云着陆区部署平台改造说明文档

## 项目概述

本项目完成了多云着陆区部署平台的以下改造任务：

1. 将整体站点后端代码从Go改写为Python 3.12
2. 将页面右边聊天窗口从嵌入iframe修改为调用Python MCP client
3. 实现用户聊天窗口输入内容替换示例中的固定内容，通过后端发给MCP SERVER，并将响应显示在聊天窗口中

## 技术栈

- 后端：Python 3.12、Flask、PyJWT、Requests
- 前端：Vue.js、Element Plus
- 通信：RESTful API、HTTP请求

## 项目结构

```
python_backend/
├── .env                  # 环境配置文件
├── app.py                # 应用入口文件
├── requirements.txt      # 依赖列表
├── config/               # 配置模块
│   └── config.py         # 配置加载
├── controllers/          # 控制器
│   ├── auth_controller.py    # 认证控制器
│   ├── chat_controller.py    # 聊天控制器
│   └── project_controller.py # 项目控制器
├── db/                   # 数据库模块
│   └── db.py             # 数据库连接
├── middlewares/          # 中间件
│   └── middlewares.py    # 认证和CORS中间件
├── models/               # 数据模型
├── routes/               # 路由
│   └── routes.py         # 路由设置
└── utils/                # 工具函数
    └── mcp_client.py     # MCP客户端
```

## 安装与部署

### 环境要求

- Python 3.12或更高版本
- MySQL数据库（可选，仅用于用户认证和项目管理）

### 安装步骤

1. 克隆项目代码

2. 安装Python 3.12（如果尚未安装）

3. 创建并激活虚拟环境
   ```bash
   cd python_backend
   python3.12 -m venv venv
   source venv/bin/activate  # Linux/Mac
   # 或
   venv\Scripts\activate  # Windows
   ```

4. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

5. 配置环境变量
   编辑`.env`文件，设置数据库连接信息和API密钥：
   ```
   DB_HOST=localhost
   DB_USER=root
   DB_PASSWORD=your_password
   DB_NAME=multi_cloud_platform
   DEEPSEEK_API_KEY=your_api_key_here
   ```

6. 启动后端服务
   ```bash
   python app.py
   ```
   服务将在`http://localhost:8080`上运行

7. 部署前端代码
   将修改后的前端代码部署到Web服务器

## 功能说明

### 后端API

- `POST /api/register`: 用户注册
- `POST /api/login`: 用户登录
- `POST /api/projects`: 创建项目
- `GET /api/projects`: 获取所有项目
- `GET /api/projects/:id`: 获取特定项目
- `POST /api/chat`: 发送聊天消息到MCP服务器

### 聊天功能

聊天功能通过以下流程工作：

1. 用户在前端聊天窗口输入问题
2. 前端将问题发送到后端API `/api/chat`
3. 后端聊天控制器接收问题并调用MCP客户端
4. MCP客户端向MCP服务器发送请求，查询多个数据集
5. MCP服务器返回响应
6. 后端合并响应并返回给前端
7. 前端在聊天窗口显示响应

## 注意事项

1. 数据库连接
   - 如果不需要用户认证和项目管理功能，可以忽略数据库连接错误
   - 如果需要这些功能，请确保创建了正确的数据库和表结构

2. MCP服务器连接
   - 确保MCP服务器地址正确配置在`utils/mcp_client.py`中
   - 默认配置为`http://rag.cloudet.cn:9382/api/ragflow_retrieval`

3. 安全性
   - 生产环境中应使用HTTPS
   - 应对密码进行哈希处理
   - 应使用更安全的JWT配置

## 故障排除

1. 数据库连接错误
   - 检查`.env`文件中的数据库配置
   - 确保数据库服务器正在运行
   - 确保数据库和表已创建

2. MCP服务器连接错误
   - 检查网络连接
   - 验证MCP服务器URL是否正确
   - 检查服务器日志中的详细错误信息

3. 前端显示问题
   - 检查浏览器控制台是否有错误
   - 确保API请求URL正确
   - 验证认证令牌是否有效

## 未来改进

1. 添加更完善的错误处理和日志记录
2. 实现更高级的聊天功能，如历史记录和上下文保持
3. 添加用户界面主题和个性化设置
4. 实现更安全的认证机制
5. 添加单元测试和集成测试

## 环境变量配置

系统支持通过`.env`文件配置环境变量。请在backend目录下创建`.env`文件，配置示例如下：

```
# 调试模式
DEBUG=False

# 数据库配置
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=
DB_NAME=mcdp

# JWT配置
JWT_SECRET=mcdp-jwt-secret-key
JWT_TOKEN_EXPIRES=86400

# 应用密钥
SECRET_KEY=mcdp-secret-key

# OpenAI API 配置
OPENAI_API_KEY=your-api-key-here
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_API_MODEL=gpt-4o
```

### OpenAI API 配置说明

- `OPENAI_API_KEY`: OpenAI API密钥
- `OPENAI_API_BASE_URL`: OpenAI API基础URL，默认为`https://api.openai.com/v1`
- `OPENAI_API_MODEL`: 使用的OpenAI模型，默认为`gpt-4o`

如果你需要使用其他LLM模型或API服务，只需修改这些配置即可。
