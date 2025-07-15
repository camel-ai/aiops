-- 添加支持各种云产品的字段到cloud表
-- ELB字段
ALTER TABLE `cloud` ADD COLUMN `elb_name` VARCHAR(255) COMMENT 'ELB名称' AFTER `iamarn`;
ALTER TABLE `cloud` ADD COLUMN `elb_arn` VARCHAR(255) COMMENT 'ELB ARN' AFTER `elb_name`;
ALTER TABLE `cloud` ADD COLUMN `elb_type` VARCHAR(100) COMMENT 'ELB类型' AFTER `elb_arn`;

-- EC2字段
ALTER TABLE `cloud` ADD COLUMN `ec2_name` VARCHAR(255) COMMENT 'EC2实例名称' AFTER `elb_type`;
ALTER TABLE `cloud` ADD COLUMN `ec2_id` VARCHAR(255) COMMENT 'EC2实例ID' AFTER `ec2_name`;
ALTER TABLE `cloud` ADD COLUMN `ec2_type` VARCHAR(100) COMMENT 'EC2实例类型' AFTER `ec2_id`;
ALTER TABLE `cloud` ADD COLUMN `ec2_state` VARCHAR(100) COMMENT 'EC2实例状态' AFTER `ec2_type`;

-- S3字段
ALTER TABLE `cloud` ADD COLUMN `s3_name` VARCHAR(255) COMMENT 'S3存储桶名称' AFTER `ec2_state`;
ALTER TABLE `cloud` ADD COLUMN `s3_region` VARCHAR(100) COMMENT 'S3存储桶区域' AFTER `s3_name`;

-- RDS字段
ALTER TABLE `cloud` ADD COLUMN `rds_identifier` VARCHAR(255) COMMENT 'RDS标识符' AFTER `s3_region`;
ALTER TABLE `cloud` ADD COLUMN `rds_engine` VARCHAR(100) COMMENT 'RDS引擎' AFTER `rds_identifier`;
ALTER TABLE `cloud` ADD COLUMN `rds_status` VARCHAR(100) COMMENT 'RDS状态' AFTER `rds_engine`;

-- Lambda字段
ALTER TABLE `cloud` ADD COLUMN `lambda_name` VARCHAR(255) COMMENT 'Lambda函数名' AFTER `rds_status`;

-- 通用资源字段（用于其他类型的资源）
ALTER TABLE `cloud` ADD COLUMN `resource_name` VARCHAR(255) COMMENT '通用资源名称' AFTER `lambda_name`;
ALTER TABLE `cloud` ADD COLUMN `resource_type` VARCHAR(100) COMMENT '资源类型' AFTER `resource_name`;
ALTER TABLE `cloud` ADD COLUMN `resource_index` INT COMMENT '资源索引' AFTER `resource_type`; 