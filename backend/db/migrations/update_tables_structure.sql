-- 数据库修复脚本
-- 更新表结构以匹配实际环境需求

-- 检查users表是否存在
SET @users_exists = (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'users'
);

-- 如果users表不存在，则创建
SET @create_users = IF(@users_exists = 0,
    'CREATE TABLE users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL,
        department VARCHAR(255) NULL,
        project VARCHAR(255) NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )',
    'SELECT "users table already exists"'
);

PREPARE stmt FROM @create_users;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 检查users表中是否存在department列
SET @department_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'users'
    AND COLUMN_NAME = 'department'
);

-- 如果department列不存在，则添加
SET @add_department = IF(@department_exists = 0,
    'ALTER TABLE users ADD COLUMN department VARCHAR(255) NULL AFTER password',
    'SELECT "department column already exists in users table"'
);

PREPARE stmt FROM @add_department;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 检查users表中是否存在project列
SET @project_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'users'
    AND COLUMN_NAME = 'project'
);

-- 如果project列不存在，则添加
SET @add_project = IF(@project_exists = 0,
    'ALTER TABLE users ADD COLUMN project VARCHAR(255) NULL AFTER department',
    'SELECT "project column already exists in users table"'
);

PREPARE stmt FROM @add_project;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 检查projects表是否存在
SET @projects_exists = (
    SELECT COUNT(*)
    FROM information_schema.TABLES
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'projects'
);

-- 如果projects表不存在，则创建
SET @create_projects = IF(@projects_exists = 0,
    'CREATE TABLE projects (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        user_id INT NOT NULL,
        created_by INT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )',
    'SELECT "projects table already exists"'
);

PREPARE stmt FROM @create_projects;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 检查projects表中是否存在user_id列
SET @user_id_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'projects'
    AND COLUMN_NAME = 'user_id'
);

-- 如果user_id列不存在，则添加
SET @add_user_id = IF(@user_id_exists = 0,
    'ALTER TABLE projects ADD COLUMN user_id INT NOT NULL AFTER description',
    'SELECT "user_id column already exists in projects table"'
);

PREPARE stmt FROM @add_user_id;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 检查projects表中是否存在created_by列
SET @created_by_exists = (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'projects'
    AND COLUMN_NAME = 'created_by'
);

-- 如果created_by列不存在，则添加
SET @add_created_by = IF(@created_by_exists = 0,
    'ALTER TABLE projects ADD COLUMN created_by INT NULL AFTER user_id',
    'SELECT "created_by column already exists in projects table"'
);

PREPARE stmt FROM @add_created_by;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 如果created_by列存在但类型不是INT，则修改类型
SET @check_created_by_type = CONCAT(
    'SELECT IF(DATA_TYPE != "int", 1, 0) ',
    'FROM information_schema.COLUMNS ',
    'WHERE TABLE_SCHEMA = DATABASE() ',
    'AND TABLE_NAME = "projects" ',
    'AND COLUMN_NAME = "created_by"'
);

SET @created_by_wrong_type = 0;
PREPARE stmt FROM @check_created_by_type;
EXECUTE stmt INTO @created_by_wrong_type;
DEALLOCATE PREPARE stmt;

SET @modify_created_by = IF(@created_by_wrong_type = 1,
    'ALTER TABLE projects MODIFY COLUMN created_by INT NULL',
    'SELECT "created_by column already has correct type"'
);

PREPARE stmt FROM @modify_created_by;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 查看表结构
DESCRIBE users;
DESCRIBE projects;
