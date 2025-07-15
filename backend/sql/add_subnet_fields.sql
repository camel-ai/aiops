-- 在cloud表中添加新的子网相关字段
ALTER TABLE `cloud` ADD COLUMN `subnetid` VARCHAR(255) COMMENT '子网ID标识符' AFTER `subnet`;
ALTER TABLE `cloud` ADD COLUMN `subnetvpc` VARCHAR(255) COMMENT '子网所属VPC ID' AFTER `subnetid`;
ALTER TABLE `cloud` ADD COLUMN `subnetcidr` VARCHAR(100) COMMENT '子网CIDR地址块' AFTER `subnetvpc`; 