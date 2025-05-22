-- 创建API密钥表
CREATE TABLE IF NOT EXISTS `api_keys` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `userid` INT NOT NULL,
  `username` VARCHAR(100) NOT NULL,
  `apikey_name` VARCHAR(100) NOT NULL,
  `cloud` VARCHAR(50) NOT NULL,
  `ak` VARCHAR(255) NOT NULL,
  `sk` VARCHAR(255) NOT NULL,
  `remark` TEXT,
  `createtime` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  INDEX `idx_userid` (`userid`),
  INDEX `idx_cloud` (`cloud`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4; 