#!/bin/bash

# MCDP多云运维管理平台 - 一键部署脚本
# 适用于已有Docker环境的服务器

set -e  # 遇到错误立即退出

# 自动修复脚本权限（如果在Linux/Unix环境）
if [[ "$OSTYPE" == "linux-gnu"* ]] || [[ "$OSTYPE" == "darwin"* ]]; then
    # 检查并修复当前脚本权限
    if [ ! -x "$0" ]; then
        echo "🔧 正在修复脚本执行权限..."
        chmod +x "$0" 2>/dev/null || true
    fi
    
    # 检查并修复其他脚本权限
    for script in "deploy.sh" "build-and-push.sh"; do
        if [ -f "$script" ] && [ ! -x "$script" ]; then
            echo "🔧 正在修复 $script 执行权限..."
            chmod +x "$script" 2>/dev/null || true
        fi
    done
fi

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_message() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE} $1${NC}"
    echo -e "${BLUE}================================================${NC}"
}

# 显示欢迎信息
print_header "🚀 MCDP 多云运维管理平台 - 一键部署"

# 检查Docker环境
print_message "检查系统环境..."

if ! command -v docker &> /dev/null; then
    print_error "Docker 未安装，请先安装 Docker"
    echo "安装命令: curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose 未安装，请先安装 Docker Compose"
    echo "安装命令: curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    print_error "Docker 服务未运行或无权限访问"
    print_message "请运行: sudo systemctl start docker"
    print_message "或将当前用户添加到docker组: sudo usermod -aG docker \$USER"
    exit 1
fi

print_message "✅ Docker 环境检查通过"

# 检查环境变量文件
if [ ! -f .env ]; then
    if [ -f env.example ]; then
        print_warning ".env 文件不存在，正在从 env.example 创建..."
        # 复制文件并转换换行符（去除Windows的\r字符）
        if command -v dos2unix >/dev/null 2>&1; then
            cp env.example .env && dos2unix .env >/dev/null 2>&1
        else
            # 如果没有dos2unix，使用tr命令去除\r字符
            tr -d '\r' < env.example > .env
        fi
        print_error "请先编辑 .env 文件，填入您的 API 密钥和配置"
        print_message "编辑命令: nano .env 或 vim .env"
        print_message "必须配置的项目："
        echo "  - DB_PASSWORD (数据库密码)"
        echo "  - JWT_SECRET (JWT密钥)"
        echo "  - SECRET_KEY (应用密钥)"
        echo "  - OPENAI_API_KEY (OpenAI API密钥)"
        echo "  - DEEPSEEK_API_KEY (DeepSeek API密钥)"
        echo "  - ANTHROPIC_API_KEY (Anthropic API密钥)"
        echo "  - REGISTRY_USERNAME (Docker用户名)"
        exit 1
    else
        print_error ".env 和 env.example 文件都不存在"
        exit 1
    fi
fi

# 加载环境变量（先确保换行符格式正确）
if [ -f .env ]; then
    # 检查是否包含Windows换行符
    if grep -q $'\r' .env 2>/dev/null; then
        print_warning "检测到 .env 文件包含Windows换行符，正在修复..."
        if command -v dos2unix >/dev/null 2>&1; then
            dos2unix .env >/dev/null 2>&1
        else
            # 使用tr命令去除\r字符
            tr -d '\r' < .env > .env.tmp && mv .env.tmp .env
        fi
        print_message "✅ 换行符修复完成"
    fi
    source .env
else
    print_error ".env 文件不存在"
    exit 1
fi

# 验证必要的环境变量
print_message "验证环境变量配置..."

required_vars=("DB_PASSWORD" "JWT_SECRET" "SECRET_KEY" "REGISTRY_USERNAME")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=($var)
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    print_error "以下环境变量未设置:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    print_message "请编辑 .env 文件并设置这些变量"
    exit 1
fi

# 检查API密钥
api_keys=("OPENAI_API_KEY" "DEEPSEEK_API_KEY" "ANTHROPIC_API_KEY")
has_api_key=false

for key in "${api_keys[@]}"; do
    if [ ! -z "${!key}" ] && [ "${!key}" != "your_${key,,}_here" ]; then
        has_api_key=true
        break
    fi
done

if [ "$has_api_key" = false ]; then
    print_warning "⚠️  未检测到有效的 AI API 密钥"
    print_message "至少需要配置一个AI服务的API密钥，否则AI功能将无法使用"
    read -p "是否继续部署? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

print_message "✅ 环境变量验证通过"

# 设置镜像标签
IMAGE_TAG=${IMAGE_TAG:-latest}
print_message "使用镜像版本: $IMAGE_TAG"

# 停止现有容器
print_header "第1步: 停止现有容器"
if docker-compose -f docker-compose.prod.yml ps -q | grep -q .; then
    print_message "停止现有容器..."
    docker-compose -f docker-compose.prod.yml down
else
    print_message "未检测到运行中的容器"
fi

# 拉取最新镜像
print_header "第2步: 拉取镜像"
print_message "正在拉取最新镜像..."
print_message "前端镜像: $REGISTRY_USERNAME/mcdp-frontend:$IMAGE_TAG"
print_message "后端镜像: $REGISTRY_USERNAME/mcdp-backend:$IMAGE_TAG"

export REGISTRY_USERNAME=$REGISTRY_USERNAME
export IMAGE_TAG=$IMAGE_TAG

docker-compose -f docker-compose.prod.yml pull

# 启动服务
print_header "第3步: 启动服务"
print_message "启动所有服务..."
docker-compose -f docker-compose.prod.yml up -d

# 等待服务启动
print_header "第4步: 等待服务启动"
print_message "等待服务完全启动..."

# 等待数据库初始化
print_message "等待数据库初始化..."
sleep 30

# 检查服务状态
for i in {1..12}; do
    if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
        break
    fi
    print_message "等待服务启动... ($i/12)"
    sleep 10
done

# 显示服务状态
print_header "第5步: 服务状态检查"
docker-compose -f docker-compose.prod.yml ps

# 健康检查
print_message "进行健康检查..."

# 检查后端健康状态
if curl -f http://localhost:5000/api/health >/dev/null 2>&1; then
    print_message "✅ 后端服务健康检查通过"
else
    print_warning "⚠️  后端服务可能还在启动中"
fi

# 获取服务器IP
SERVER_IP=$(hostname -I | awk '{print $1}')

# 完成提示
print_header "🎉 部署完成！"

echo ""
print_message "服务访问地址:"
echo "  🌐 前端访问: http://$SERVER_IP"
echo "  🔧 后端API: http://$SERVER_IP:5000"
echo ""
print_message "服务管理命令:"
echo "  📊 查看状态: docker-compose -f docker-compose.prod.yml ps"
echo "  📋 查看日志: docker-compose -f docker-compose.prod.yml logs -f"
echo "  🛑 停止服务: docker-compose -f docker-compose.prod.yml down"
echo "  🔄 重启服务: docker-compose -f docker-compose.prod.yml restart"
echo ""
print_message "数据备份:"
echo "  💾 数据库备份: docker exec mcdp_mcdp-database_1 mysqldump -u root -p\$DB_PASSWORD mcdp > backup.sql"
echo ""

print_message "🎯 MCDP 多云运维管理平台部署成功！"
print_message "请访问 http://$SERVER_IP 开始使用平台"

# 显示日志
print_message "显示最近的日志 (按 Ctrl+C 退出):"
sleep 3
docker-compose -f docker-compose.prod.yml logs -f --tail=50 