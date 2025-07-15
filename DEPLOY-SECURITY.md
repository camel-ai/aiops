# MCDP 安全部署指南

## 🔒 重要安全声明

**您的API密钥和敏感信息是安全的！**

- ✅ Docker镜像**不包含任何API密钥或敏感信息**
- ✅ 您的API密钥只存储在您自己的服务器上
- ✅ 敏感信息通过环境变量在运行时注入
- ✅ 构建者无法访问您的配置信息

## 📋 部署前检查清单

### 开发者已完成（镜像构建）：
- [x] 构建了不包含敏感信息的通用Docker镜像
- [x] 推送到公共Docker Registry
- [x] 提供了部署脚本和配置模板

### 您需要完成（安全部署）：
- [ ] 下载部署脚本
- [ ] 配置您自己的API密钥
- [ ] 一键部署到您的服务器

## 🚀 快速部署（3分钟）

### 步骤1：获取部署文件
```bash
# 下载项目（包含部署脚本）
git clone <项目地址>
cd mcdp

# 或者只下载部署包（更轻量）
wget https://example.com/mcdp-deploy.tar.gz
tar -xzf mcdp-deploy.tar.gz
cd mcdp-deploy
```

### 步骤2：配置您的敏感信息
```bash
# 复制配置模板
cp env.example .env

# 编辑配置文件，添加您的API密钥
nano .env
```

**需要配置的关键信息：**
```bash
# 您的AI API密钥
OPENAI_API_KEY=sk-your-openai-key
DEEPSEEK_API_KEY=sk-your-deepseek-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# 您的云服务凭据
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret

# 数据库密码（您设置）
DB_PASSWORD=your-secure-password

# JWT密钥（系统生成或您设置）
JWT_SECRET=your-jwt-secret
```

### 步骤3：一键部署
```bash
# 启动部署
./deploy.sh

# 等待部署完成（通常2-3分钟）
# 部署成功后访问: http://your-server-ip
```

## 🔍 安全验证

### 验证镜像安全性
您可以验证Docker镜像不包含敏感信息：

```bash
# 拉取镜像并检查
docker pull your-dockerhub-username/mcdp-backend:latest

# 启动临时容器检查环境
docker run --rm -it your-dockerhub-username/mcdp-backend:latest bash

# 在容器内检查（应该看不到任何API密钥）
env | grep -E "(API_KEY|SECRET|PASSWORD)"
# 应该输出为空或只有默认占位符
```

### 验证运行时安全性
```bash
# 检查运行中的容器环境变量
docker exec mcdp-backend env | grep API_KEY
# 应该看到您配置的API密钥（仅在您的服务器上）
```

## 🛡️ 安全最佳实践

### 1. 环境文件安全
```bash
# 设置严格的文件权限
chmod 600 .env

# 确保不会被版本控制跟踪
echo ".env" >> .gitignore
```

### 2. 服务器安全
- 使用防火墙保护服务器
- 定期更新系统和Docker
- 使用非root用户运行服务

### 3. 密钥管理
- 定期轮换API密钥
- 使用强密码生成器
- 不要在聊天或邮件中分享.env文件

## 📞 支持与帮助

如果部署过程中遇到问题：

1. **检查日志**：`docker-compose logs`
2. **健康检查**：`docker-compose ps`
3. **重新部署**：`./deploy.sh --force`

**常见问题：**
- 端口被占用：修改docker-compose.prod.yml中的端口映射
- 权限问题：确保当前用户在docker组中
- 网络问题：检查防火墙和Docker网络配置

---

**记住：您的敏感信息始终在您的控制之下！** 🔐 