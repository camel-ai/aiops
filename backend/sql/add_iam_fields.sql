-- 在cloud表中添加新的IAM用户相关字段
ALTER TABLE `cloud` ADD COLUMN `iamid` VARCHAR(255) COMMENT 'IAM用户ID' AFTER `iam_user`;
ALTER TABLE `cloud` ADD COLUMN `iamarn` VARCHAR(255) COMMENT 'IAM用户ARN' AFTER `iamid`; 