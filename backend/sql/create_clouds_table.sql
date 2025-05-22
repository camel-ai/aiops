-- 创建clouds表，用于存储云服务商信息
CREATE TABLE IF NOT EXISTS `clouds` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(100) NOT NULL COMMENT '云服务提供商名称',
  `logo` VARCHAR(500) COMMENT '云服务提供商Logo URL',
  `provider` VARCHAR(100) COMMENT '提供商公司名称',
  `regions` TEXT COMMENT '支持的区域，JSON格式存储',
  `is_active` TINYINT(1) DEFAULT 1 COMMENT '是否激活，1表示激活，0表示禁用',
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  UNIQUE INDEX `idx_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='云服务提供商表';

-- 初始化一些默认云服务提供商数据
INSERT INTO `clouds` (`name`, `logo`, `provider`, `regions`, `is_active`) VALUES
('AWS', 'https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg', 'Amazon', '["ap-south-1", "eu-north-1", "eu-west-3", "eu-west-2", "eu-west-1", "ap-northeast-3", "ap-northeast-2", "ap-northeast-1", "ca-central-1", "sa-east-1", "ap-southeast-1", "ap-southeast-2", "eu-central-1", "us-east-1", "us-east-2", "us-west-1", "us-west-2", "cn-north-1", "cn-northwest-1"]', 1),
('AZURE', 'https://upload.wikimedia.org/wikipedia/commons/a/a8/Microsoft_Azure_Logo.svg', 'Microsoft', '["eastus", "westus", "northeurope", "eastasia"]', 1),
('阿里云', 'https://upload.wikimedia.org/wikipedia/commons/b/b3/AlibabaCloudLogo.svg', 'Alibaba', '["cn-hangzhou", "cn-shanghai", "cn-beijing", "cn-shenzhen"]', 1),
('华为云', 'https://res-static.hc-cdn.cn/cloudbu-site/china/zh-cn/wangxue/header/logo.svg', 'Huawei', '["cn-north-1", "cn-east-2", "cn-south-1"]', 1),
('腾讯云', 'https://www.leixue.com/uploads/2021/08/Tencent-Cloud.png!760', 'Tencent', '["ap-guangzhou", "ap-shanghai", "ap-beijing", "ap-chengdu"]', 1),
('百度云', 'https://p1.itc.cn/q_70/images03/20220927/541c2f06e42e4253825ee211b5b46e2e.jpeg', 'Baidu', '["bd-beijing-a", "bd-guangzhou-a"]', 1),
('火山云', 'https://res.volccdn.com/obj/volc-console-fe/vconsole-auth/volcengine/static/svg/login-logo.872b6ea3.svg', 'ByteDance', '["cn-beijing", "cn-shanghai"]', 1),
('四维云', 'https://img1.baidu.com/it/u=3340841224,2861483210&fm=253&fmt=auto&app=120&f=JPEG?w=500&h=500', 'SDCloud', '["cn-beijing", "cn-hangzhou"]', 1); 