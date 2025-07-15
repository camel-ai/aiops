-- 数据库修复脚本
-- 添加缺失的user_id列到projects表

-- 检查projects表是否存在user_id列
SET @column_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'projects'
    AND COLUMN_NAME = 'user_id'
);

-- 如果不存在，则添加user_id列
SET @query = IF(@column_exists = 0,
    'ALTER TABLE projects ADD COLUMN user_id INT NOT NULL AFTER description',
    'SELECT "user_id column already exists in projects table"'
);

PREPARE stmt FROM @query;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 查看表结构
DESCRIBE projects;
