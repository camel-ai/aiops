# 🚀 MCDP Docker 容器化 - 快速开始指南

## ✅ 已配置完成的文件

所有Docker配置文件已经准备就绪，您现在可以直接上传到Linux服务器进行构建和部署！

```
✅ docker/frontend/Dockerfile      # 前端镜像构建文件
✅ docker/frontend/nginx.conf      # Nginx配置
✅ docker/backend/Dockerfile       # 后端镜像构建文件
✅ docker/mysql/01-schema.sql      # 数据库初始化脚本
✅ docker/mysql/my.cnf             # MySQL配置
✅ docker-compose.yml              # 开发/构建环境
✅ docker-compose.prod.yml         # 生产环境
✅ env.example                     # 环境变量模板
✅ build-and-push.sh              # 构建推送脚本
✅ deploy.sh                      # 一键部署脚本
✅ README-Docker.md               # 详细部署文档
```

## 🔧 在Linux服务器上构建并推送镜像

### 第1步：上传项目到服务器
```bash
# 方法1：使用SCP上传
tar -czf mcdp.tar.gz mcdp/
scp mcdp.tar.gz user@your-server:/opt/
ssh user@your-server "cd /opt && tar -xzf mcdp.tar.gz"

# 方法2：使用Git（推荐）
ssh user@your-server
cd /opt
git clone https://github.com/yourname/mcdp.git
cd mcdp
```

### 第2步：修复脚本权限（可选）
```bash
# 脚本会自动检测并修复权限，但如果需要手动处理：
cd /opt/mcdp

# 方式1：使用权限修复脚本
bash fix-permissions.sh

# 方式2：手动修复权限
chmod +x *.sh

# 方式3：如果遇到权限问题，直接用bash运行
# bash build-and-push.sh v1.0.0
```

### 第3步：配置环境变量
```bash
# 在服务器上
cd /opt/mcdp
cp env.example .env
nano .env

# 必须配置的关键项：
REGISTRY_USERNAME=your_dockerhub_username
DB_PASSWORD=your_secure_password
JWT_SECRET=your_32_character_jwt_secret
SECRET_KEY=your_32_character_app_secret
OPENAI_API_KEY=sk-your_openai_key
DEEPSEEK_API_KEY=sk-your_deepseek_key
```

### 第4步：构建并推送镜像
```bash
# 一键构建和推送（脚本会自动修复权限）
./build-and-push.sh

# 或指定版本号
./build-and-push.sh v1.0.0

# 如果遇到权限问题，可以直接用bash运行：
# bash build-and-push.sh v1.0.0
```

## 🚀 其他人一键部署使用

### 创建部署包
为其他部署者创建一个轻量级部署包：

```bash
# 创建部署包目录
mkdir mcdp-deploy
cd mcdp-deploy

# 复制必要文件
cp ../docker-compose.prod.yml .
cp ../env.example .
cp ../deploy.sh .
cp -r ../docker/mysql ./docker/

# 打包发布
tar -czf mcdp-deploy.tar.gz mcdp-deploy/
```

### 部署者使用方法
```bash
# 1. 下载部署包
wget https://yourserver.com/mcdp-deploy.tar.gz
tar -xzf mcdp-deploy.tar.gz
cd mcdp-deploy

# 2. 配置环境变量
cp env.example .env
nano .env  # 填入API密钥等配置

# 3. 一键部署（脚本会自动修复权限）
./deploy.sh

# 如果遇到权限问题：
# bash deploy.sh
```

## 📋 推送到Docker Hub后的结果

推送成功后，将生成以下镜像：

```
your-dockerhub-username/mcdp-frontend:latest
your-dockerhub-username/mcdp-frontend:v1.0.0
your-dockerhub-username/mcdp-backend:latest  
your-dockerhub-username/mcdp-backend:v1.0.0
```

## 🎯 使用场景

### 开发者（您）
1. ✅ 本地开发完成后推送代码
2. ✅ 在服务器上运行 `./build-and-push.sh`
3. ✅ 镜像自动构建并推送到Docker Hub
4. ✅ 创建部署包供其他人使用

### 部署者（其他人）
1. ✅ 下载轻量级部署包（~20KB）
2. ✅ 配置环境变量（API密钥等）
3. ✅ 运行 `./deploy.sh` 一键部署
4. ✅ 自动拉取镜像并启动所有服务

## 📊 优势对比

| 传统部署 | 容器化部署 |
|---------|-----------|
| 需要完整源码（50MB+） | 只需部署包（20KB） |
| 需要安装Node.js、Python | 只需要Docker |
| 手动配置各种环境 | 一键部署 |
| 环境差异问题 | 容器保证一致性 |
| 复杂的依赖管理 | 镜像包含所有依赖 |

## 🔧 常用命令

### 本地测试
```bash
# 本地构建测试
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 生产部署
```bash
# 部署到生产环境
docker-compose -f docker-compose.prod.yml up -d

# 更新镜像
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# 备份数据
docker exec mcdp_mcdp-database_1 mysqldump -u root -p$DB_PASSWORD mcdp > backup.sql
```

## 🎉 完成状态

✅ **Docker配置完成** - 所有必要文件已创建  
✅ **构建脚本就绪** - 可直接在服务器上运行  
✅ **部署脚本就绪** - 其他人可一键部署  
✅ **安全配置** - 敏感信息通过环境变量管理  
✅ **文档完整** - 详细的使用和故障排查指南  

**🎯 现在您可以将项目上传到Linux服务器，运行构建脚本即可完成镜像构建和推送！**

## 📞 下一步操作

1. **上传项目** 到Linux服务器
2. **配置.env** 文件（重要！）
3. **运行构建脚本** `./build-and-push.sh`
4. **验证镜像** 在Docker Hub上
5. **创建部署包** 供其他人使用

---

💡 **提示**: 所有脚本都有详细的进度显示和错误处理，按照提示操作即可！ 