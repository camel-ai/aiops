-- 在cloud表中添加新的VPC相关字段
ALTER TABLE `cloud` ADD COLUMN `vpcid` VARCHAR(255) COMMENT 'VPC ID标识符' AFTER `vpc`;
ALTER TABLE `cloud` ADD COLUMN `vpccidr` VARCHAR(100) COMMENT 'VPC CIDR地址块' AFTER `vpcid`; 