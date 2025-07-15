-- 数据库数据修复脚本
-- 修复start表和clouds表的数据

USE mcdp;

-- 设置字符编码
SET NAMES utf8mb4;
SET CHARACTER_SET_CLIENT = utf8mb4;

-- 清空并重置clouds表
DELETE FROM `clouds`;
ALTER TABLE `clouds` AUTO_INCREMENT = 1;

-- 清空并重置start表  
DELETE FROM `start`;
ALTER TABLE `start` AUTO_INCREMENT = 1;

-- 重新插入clouds表数据（包含所有9条记录）
INSERT INTO `clouds` (`id`, `name`, `logo`, `provider`, `regions`, `is_active`, `created_at`, `updated_at`) VALUES
(1267, 'AWS', 'https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg', 'Amazon', '["ap-south-1", "eu-north-1", "eu-west-3", "eu-west-2", "eu-west-1", "ap-northeast-3", "ap-northeast-2", "ap-northeast-1", "ca-central-1", "sa-east-1", "ap-southeast-1", "ap-southeast-2", "eu-central-1", "us-east-1", "us-east-2", "us-west-1", "us-west-2", "all"]', 1, '2025-06-10 10:37:54', '2025-06-24 02:12:15'),
(1268, 'AZURE', 'https://upload.wikimedia.org/wikipedia/commons/a/a8/Microsoft_Azure_Logo.svg', 'Microsoft', '["eastus", "westus", "northeurope", "eastasia", "all"]', 1, '2025-06-10 10:37:54', '2025-06-24 02:12:15'),
(1269, '阿里云', 'https://upload.wikimedia.org/wikipedia/commons/b/b3/AlibabaCloudLogo.svg', 'Alibaba', '["cn-hangzhou", "cn-shanghai", "cn-beijing", "cn-shenzhen", "all"]', 1, '2025-06-10 10:37:54', '2025-06-24 02:12:15'),
(1270, '华为云', 'https://res-static.hc-cdn.cn/cloudbu-site/china/zh-cn/wangxue/header/logo.svg', 'Huawei', '["cn-north-1", "cn-east-2", "cn-south-1", "all"]', 1, '2025-06-10 10:37:54', '2025-06-24 02:12:15'),
(1271, '腾讯云', 'https://www.leixue.com/uploads/2021/08/Tencent-Cloud.png!760', 'Tencent', '["ap-guangzhou", "ap-shanghai", "ap-beijing", "ap-chengdu", "all"]', 1, '2025-06-10 10:37:54', '2025-06-24 02:12:15'),
(1272, '百度云', 'https://p1.itc.cn/q_70/images03/20220927/541c2f06e42e4253825ee211b5b46e2e.jpeg', 'Baidu', '["bd-beijing-a", "bd-guangzhou-a", "all"]', 1, '2025-06-10 10:37:54', '2025-06-24 02:12:15'),
(1273, '火山云', 'https://res.volccdn.com/obj/volc-console-fe/vconsole-auth/volcengine/static/svg/login-logo.872b6ea3.svg', 'ByteDance', '["cn-beijing", "cn-shanghai", "all"]', 1, '2025-06-10 10:37:54', '2025-06-24 02:12:15'),
(2149, 'AWS(China)', 'https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg', 'Amazon', '["cn-north-1", "cn-northwest-1", "all"]', 1, '2025-06-24 01:59:43', '2025-06-24 02:12:15'),
(2150, 'Azure(China)', 'https://upload.wikimedia.org/wikipedia/commons/f/fa/Microsoft_Azure.svg', 'Microsoft', '["chinanorth", "chinaeast", "chinanorth2", "chinaeast2", "all"]', 1, '2025-06-24 01:59:44', '2025-06-24 02:12:15');

-- 重新插入start表数据（8条FAQ记录）
INSERT INTO `start` (`id`, `Q`, `A`, `created_at`, `updated_at`) VALUES
(1, '什么叫「aiops」?', '简单来说，就是用AI给多云部署和运维装上智能大脑！\n跟聊天机器人对话就能查询、部署云资源 (AWS、阿里云、腾讯云、Azure等统统拿下！)\n你说需求，AI自动帮你设计云架构、生成部署脚本 (Terraform代码 so easy!)\n甚至，你给张手绘架构图或文档，它都能帮你变成现实！\n部署出问题？AIOps还能智能修复、自我治愈！ 听起来是不是未来感十足？\nAIOps项目，致力于打造下一代多云AI部署和可执行的DevOps助手！', '2025-06-11 10:56:02', '2025-06-11 10:56:02'),
(2, '每天要运维的云有哪些？ta 们的「登录」和「管理」容易么？', '每天可能我们要运维的云多种多样，公有云、私有云、专属云、混合云\n公有云：AWS、azure、alicloud、baiducloud、volcengine、tencloud、baiducloud等等\n私有云:openstack、cloudstack、Kubernetes等等\n各种各样的云平台的各种形态有各种各样的web控制台、每朵云还存在多个主子账号、多个iam user等，需要不停切换\n每个云组件、每个REGION也需要单独切换去查询，登录和管理都比较耗时耗力', '2025-06-11 10:56:02', '2025-06-11 10:56:02'),
(3, '传统的CMP平台与云portal真的会「思考」吗？和AIOPS有什么不同？', '传统cmp平台一般情况只支持一部分云的资源部署和账单查询，而且是固定程式去执行，没有思考能力\naiops是利用大模型的能力去自动部署、利用提示词工程来进行合理编排，具有思考能力的下一代多云管理平台新范式', '2025-06-11 10:56:02', '2025-06-11 10:56:02'),
(4, '运维过程中面对如此多的「key」我该怎么办？', '每朵云、每个AI工具都有单独的KEY，面对如此多海量的KEY，管理起来是不是觉得头痛\naiops可以统一管理你的各种各样的KEY，后续还计划跟云商与AI社区生态共建KAAS（api key/aksk as a service）服务生态圈,免去你自己申请各种各样KEY的困扰', '2025-06-11 10:56:02', '2025-06-11 10:56:02'),
(5, '我部署过程中需要开如此多的「窗口」协同工作么？', '有没有感觉到每次部署一个不同形态的运维产品，比如云、容器、LINUX应用、APP都需要不同的部署方式千差万别，每次需要到不同的地方去搜索不同的文档和教程？\naiops整合了聊天、查询、部署、分析、排错于一体的整合界面，再也不用打开如此多的窗口啦', '2025-06-11 10:56:02', '2025-06-11 10:56:02'),
(6, '每次「部署失败」都需要「重新开始」么？', '如何让AI来帮助我们在部署多云的时候具有自愈、自动纠错、自动尝试和修正功能？赶快来AIOPS体验一下吧：）', '2025-06-11 10:56:02', '2025-06-11 10:56:02'),
(7, '如何「雇佣AI」帮我干1天的活？', '正在开发中，敬请期待 ^.^', '2025-06-11 10:56:02', '2025-06-11 10:56:02'),
(8, '作为「aiops」运维小助手，我能干些啥？', '你可以尝试使用如下命令让我干活噢：\n@查询:「查询云资源」\n@部署:「部署云组件」\n@模版部署:「通过terraform模版一键部署多个云组件」\n@ai \'自然语言描述你想部署的云项目\'\n点+上传你的架构草图或者手稿 + @ai \'对于附件的补充说明\' ,来根据附件生成架构图及terraform脚本\ntips:执行前需要先添加你的云账号的「api-key」噢~ ：）', '2025-06-11 10:56:02', '2025-06-11 10:56:02');

-- 更新AUTO_INCREMENT值
ALTER TABLE `clouds` AUTO_INCREMENT = 3151;
ALTER TABLE `start` AUTO_INCREMENT = 9;

-- 验证数据
SELECT COUNT(*) as clouds_count FROM clouds;
SELECT COUNT(*) as start_count FROM start; 