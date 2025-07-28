-- 1. 先删除外键约束
ALTER TABLE `projects` DROP FOREIGN KEY `projects_ibfk_1`;

-- 2. 修改created_by字段类型为VARCHAR(50)，用于存储用户名
ALTER TABLE `projects` MODIFY COLUMN `created_by` VARCHAR(50) COMMENT '创建人用户名';

-- 添加日志信息
INSERT INTO `system_logs` (`message`, `created_at`) 
VALUES ('已将projects表的created_by字段从用户ID外键修改为用户名字符串', NOW()); 