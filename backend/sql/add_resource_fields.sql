-- 添加resource_type和resource_index字段到cloud表
ALTER TABLE `cloud` ADD COLUMN `resource_type` VARCHAR(50) COMMENT '资源类型(vpc, subnet, iam)' AFTER `iam_user_policy`;
ALTER TABLE `cloud` ADD COLUMN `resource_index` INT DEFAULT 0 COMMENT '资源索引' AFTER `resource_type`; 