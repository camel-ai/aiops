#!/bin/bash

# 数据库状态检查脚本 - Linux版本

echo "🔍 MCDP数据库状态检查"
echo "===================="

# 检查Docker服务
echo "📋 检查Docker容器状态..."
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "📊 检查数据库连接..."

# 获取数据库容器ID
DB_CONTAINER=$(docker-compose -f docker-compose.prod.yml ps -q mcdp-database)

if [ -z "$DB_CONTAINER" ]; then
    echo "❌ 数据库容器未运行！"
    exit 1
fi

echo "✅ 数据库容器ID: $DB_CONTAINER"

# 检查数据库连接
echo ""
echo "🔌 测试数据库连接..."

# 从环境变量或.env文件读取密码
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
elif [ -f "env.example" ]; then
    echo "⚠️  使用env.example作为默认配置"
    export $(grep -v '^#' env.example | xargs)
fi

# 检查数据库是否可连接
docker exec -i $DB_CONTAINER mysql -u root -p${DB_PASSWORD} -e "SELECT 1;" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ 数据库连接成功"
else
    echo "❌ 数据库连接失败，请检查密码配置"
    exit 1
fi

echo ""
echo "📋 当前数据库和表："
docker exec -i $DB_CONTAINER mysql -u root -p${DB_PASSWORD} -e "SHOW DATABASES;"

echo ""
echo "📋 MCDP数据库中的表："
docker exec -i $DB_CONTAINER mysql -u root -p${DB_PASSWORD} -e "USE mcdp; SHOW TABLES;"

echo ""
echo "🔍 检查关键表结构..."

# 检查start表是否存在
echo "📋 检查START表（FAQ功能）："
docker exec -i $DB_CONTAINER mysql -u root -p${DB_PASSWORD} -e "USE mcdp; DESCRIBE start;" 2>/dev/null || echo "❌ START表不存在"

# 检查cloud表字段
echo ""
echo "📋 检查CLOUD表字段（应该有新的ELB, EC2, S3等字段）："
docker exec -i $DB_CONTAINER mysql -u root -p${DB_PASSWORD} -e "USE mcdp; SHOW COLUMNS FROM cloud;"

# 检查chat_history表
echo ""
echo "📋 检查CHAT_HISTORY表："
docker exec -i $DB_CONTAINER mysql -u root -p${DB_PASSWORD} -e "USE mcdp; DESCRIBE chat_history;" 2>/dev/null || echo "❌ CHAT_HISTORY表不存在"

echo ""
echo "✅ 数据库检查完成！" 