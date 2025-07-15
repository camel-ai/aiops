# 数据库Schema更新指南

## 问题说明
当更新数据库schema（如添加新表或字段）后，重新构建容器时新的schema没有生效。这是因为MySQL使用了持久化存储卷，旧数据仍然存在，MySQL不会重新执行初始化脚本。

## 解决方案

## 🚀 Linux服务器快速操作

### 一键重置（推荐）
```bash
# 给脚本执行权限（首次运行）
chmod +x reset-database.sh check-database.sh

# 重置数据库
./reset-database.sh

# 验证更新
./check-database.sh
```

### 手动操作命令
```bash
# 停止服务
docker-compose -f docker-compose.prod.yml down

# 删除数据库卷
docker volume rm mcdp_mysql_data -f

# 重新启动
docker-compose -f docker-compose.prod.yml up -d

# 检查状态
docker-compose -f docker-compose.prod.yml ps
```

### 快速验证schema
```bash
# 检查所有表
docker exec -i $(docker-compose -f docker-compose.prod.yml ps -q mcdp-database) mysql -u root -p${DB_PASSWORD} -e "USE mcdp; SHOW TABLES;"

# 检查START表
docker exec -i $(docker-compose -f docker-compose.prod.yml ps -q mcdp-database) mysql -u root -p${DB_PASSWORD} -e "USE mcdp; DESCRIBE start;"
```

### 方法1：使用自动脚本（推荐）

#### Linux服务器：
```bash
./reset-database.sh

# 重置后验证schema
./check-database.sh
```

#### Windows (PowerShell)：
```powershell
.\reset-database.ps1
```

### 方法2：手动操作
如果脚本无法运行，请按以下步骤手动操作：

#### 步骤1：停止所有服务
```bash
docker-compose -f docker-compose.prod.yml down
```

#### 步骤2：删除数据库卷
```bash
docker volume ls  # 查看所有卷
docker volume rm mcdp_mysql_data  # 删除数据库卷
```

#### 步骤3：重新启动服务
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 方法3：通过Docker Desktop GUI
1. 打开Docker Desktop应用
2. 点击左侧菜单 "Volumes"
3. 找到 `mcdp_mysql_data` 卷
4. 点击删除按钮
5. 重新运行 `docker-compose -f docker-compose.prod.yml up -d`

## 验证更新是否成功

### 检查新表是否存在

#### 方式1：自动查找容器名
```bash
# 查找数据库容器
docker ps | grep database

# 连接到数据库容器（替换为实际容器名）
docker exec -it $(docker-compose -f docker-compose.prod.yml ps -q mcdp-database) mysql -u root -p
```

#### 方式2：使用具体容器名
```bash
# 如果容器名是 mcdp_mcdp-database_1
docker exec -it mcdp_mcdp-database_1 mysql -u root -p

# 或者如果是 mcdp-mcdp-database-1
docker exec -it mcdp-mcdp-database-1 mysql -u root -p
```

运行SQL查询：
```sql
USE mcdp;
SHOW TABLES;  -- 应该看到 'start' 表
DESCRIBE cloud;  -- 检查cloud表的新字段
DESCRIBE chat_history;  -- 检查chat_history表的更新
```

### 检查新字段
```sql
-- 检查cloud表的新字段
SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'cloud' AND TABLE_SCHEMA = 'mcdp';

-- 检查start表
SELECT * FROM start LIMIT 5;
```

## 注意事项

⚠️ **数据丢失警告**：删除数据库卷会丢失所有现有数据！

- 如果您有重要的生产数据，请先备份
- 开发环境可以安全执行此操作
- 生产环境请考虑数据库迁移策略

## 备份现有数据（可选）
如果需要保留现有数据：

### Linux备份命令：
```bash
# 导出现有数据（自动查找容器）
CONTAINER_NAME=$(docker-compose -f docker-compose.prod.yml ps -q mcdp-database)
docker exec $CONTAINER_NAME mysqldump -u root -p${DB_PASSWORD} mcdp > backup_$(date +%Y%m%d_%H%M%S).sql

# 或者手动指定容器名
docker exec mcdp_mcdp-database_1 mysqldump -u root -p mcdp > backup.sql

# 重置数据库后恢复数据
docker exec -i $CONTAINER_NAME mysql -u root -p${DB_PASSWORD} mcdp < backup.sql
```

### 快速检查当前数据库状态：
```bash
# 检查容器状态
docker-compose -f docker-compose.prod.yml ps

# 检查数据库连接
docker exec -i $(docker-compose -f docker-compose.prod.yml ps -q mcdp-database) mysql -u root -p${DB_PASSWORD} -e "SHOW DATABASES;"

# 检查现有表
docker exec -i $(docker-compose -f docker-compose.prod.yml ps -q mcdp-database) mysql -u root -p${DB_PASSWORD} -e "USE mcdp; SHOW TABLES;"
```

## 预防措施
未来更新schema时，可以考虑：
1. 使用数据库迁移脚本而不是重新初始化
2. 在初始化脚本中添加 `IF NOT EXISTS` 条件
3. 使用专门的迁移工具如Flyway或Liquibase 