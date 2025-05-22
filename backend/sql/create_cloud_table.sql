-- 创建cloud表，用于存储用户的云资源配置信息
CREATE TABLE IF NOT EXISTS `cloud` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `username` VARCHAR(255) NOT NULL COMMENT '用户名',
  `user_id` INT NOT NULL COMMENT '用户ID',
  `project` VARCHAR(255) NOT NULL COMMENT '项目名称',
  `cloud` VARCHAR(255) NOT NULL COMMENT '云服务提供商',
  `ak` VARCHAR(255) NOT NULL COMMENT 'Access Key',
  `sk` VARCHAR(255) NOT NULL COMMENT 'Secret Key',
  `region` VARCHAR(100) COMMENT '区域',
  `deployid` VARCHAR(20) COMMENT '部署ID',
  `vpc` VARCHAR(255) COMMENT 'VPC名称',
  `vpcid` VARCHAR(255) COMMENT 'VPC ID标识符',
  `vpccidr` VARCHAR(100) COMMENT 'VPC CIDR地址块',
  `subnet` VARCHAR(255) COMMENT '子网ID',
  `subnetid` VARCHAR(255) COMMENT '子网ID标识符',
  `subnetvpc` VARCHAR(255) COMMENT '子网所属VPC ID',
  `subnetcidr` VARCHAR(100) COMMENT '子网CIDR地址块',
  `object` VARCHAR(255) COMMENT '对象存储',
  `iam_user` VARCHAR(255) COMMENT 'IAM用户',
  `iamid` VARCHAR(255) COMMENT 'IAM用户ID',
  `iamarn` VARCHAR(255) COMMENT 'IAM用户ARN',
  `iam_user_group` VARCHAR(255) COMMENT 'IAM用户组',
  `iam_user_policy` VARCHAR(255) COMMENT 'IAM用户策略',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  INDEX `idx_user_id` (`user_id`),
  INDEX `idx_username` (`username`),
  INDEX `idx_project_cloud` (`project`, `cloud`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='云资源配置表'; 

-- 注意：在表已存在的情况下，以上CREATE语句不会修改表结构
-- 如果表已经存在但缺少某些列，请手动执行以下语句添加列

-- 以下语句可在MySQL客户端单独执行，添加缺少的列
-- ALTER TABLE `cloud` ADD COLUMN `region` VARCHAR(100) COMMENT '区域';
-- ALTER TABLE `cloud` ADD COLUMN `deployid` VARCHAR(20) COMMENT '部署ID';
-- ALTER TABLE `cloud` ADD COLUMN `vpcid` VARCHAR(255) COMMENT 'VPC ID标识符' AFTER `vpc`;
-- ALTER TABLE `cloud` ADD COLUMN `vpccidr` VARCHAR(100) COMMENT 'VPC CIDR地址块' AFTER `vpcid`;
-- ALTER TABLE `cloud` ADD COLUMN `subnetid` VARCHAR(255) COMMENT '子网ID标识符' AFTER `subnet`;
-- ALTER TABLE `cloud` ADD COLUMN `subnetvpc` VARCHAR(255) COMMENT '子网所属VPC ID' AFTER `subnetid`;
-- ALTER TABLE `cloud` ADD COLUMN `subnetcidr` VARCHAR(100) COMMENT '子网CIDR地址块' AFTER `subnetvpc`;
-- ALTER TABLE `cloud` ADD COLUMN `iamid` VARCHAR(255) COMMENT 'IAM用户ID' AFTER `iam_user`;
-- ALTER TABLE `cloud` ADD COLUMN `iamarn` VARCHAR(255) COMMENT 'IAM用户ARN' AFTER `iamid`; 