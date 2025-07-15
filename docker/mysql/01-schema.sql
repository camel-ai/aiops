-- MySQL dump 10.13  Distrib 8.0.42, for Linux (x86_64)
--
-- Host: localhost    Database: multi_cloud_platform
-- ------------------------------------------------------
-- Server version	8.0.42

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `ai_deployments`
--

DROP TABLE IF EXISTS `ai_deployments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ai_deployments` (
  `id` varchar(255) NOT NULL COMMENT '部署ID',
  `user_id` int NOT NULL COMMENT '用户ID',
  `username` varchar(255) NOT NULL COMMENT '用户名',
  `name` varchar(255) NOT NULL COMMENT '部署名称',
  `description` text COMMENT '部署描述',
  `status` varchar(50) NOT NULL COMMENT '部署状态',
  `error_message` text COMMENT '错误信息',
  `terraform_code` text NOT NULL COMMENT 'Terraform代码',
  `deployment_summary` text COMMENT '部署摘要（JSON格式）',
  `template_id` varchar(36) DEFAULT NULL COMMENT '关联的模板ID',
  `deploy_progress` int DEFAULT '0' COMMENT '部署进度（0-100）',
  `created_at` varchar(50) NOT NULL COMMENT '创建时间',
  `updated_at` varchar(50) NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_status` (`status`),
  KEY `idx_template_id` (`template_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI部署表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `aideployments`
--

DROP TABLE IF EXISTS `aideployments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `aideployments` (
  `id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` int NOT NULL,
  `username` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `status` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `error_message` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `terraform_code` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `deployment_summary` text CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
  `created_at` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `updated_at` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL,
  `project` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cloud` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `api_keys`
--

DROP TABLE IF EXISTS `api_keys`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `api_keys` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `userid` int NOT NULL COMMENT '用户ID',
  `username` varchar(100) NOT NULL COMMENT '用户名',
  `apikey_name` varchar(100) NOT NULL COMMENT 'API密钥名称',
  `cloud` varchar(50) NOT NULL COMMENT '云服务商',
  `ak` varchar(255) NOT NULL COMMENT 'Access Key',
  `sk` varchar(255) NOT NULL COMMENT 'Secret Key',
  `remark` text COMMENT '备注',
  `createtime` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_userid` (`userid`),
  KEY `idx_cloud` (`cloud`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='API密钥表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `chat_history`
--

DROP TABLE IF EXISTS `chat_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `chat_history` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `username` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `question` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `answer` text COLLATE utf8mb4_unicode_ci,
  `message_type` enum('user','system') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'user',
  `session_id` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `metadata` json DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_username` (`username`),
  KEY `idx_created_at` (`created_at`),
  KEY `idx_session_id` (`session_id`),
  CONSTRAINT `chat_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=275 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='聊天历史记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `cloud`
--

DROP TABLE IF EXISTS `cloud`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `cloud` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(255) NOT NULL COMMENT '用户名',
  `user_id` int NOT NULL COMMENT '用户ID',
  `project` varchar(255) NOT NULL COMMENT '项目名称',
  `cloud` varchar(255) NOT NULL COMMENT '云服务提供商',
  `ak` varchar(255) NOT NULL COMMENT 'Access Key',
  `sk` varchar(255) NOT NULL COMMENT 'Secret Key',
  `region` varchar(500) DEFAULT NULL COMMENT '区域',
  `deployid` varchar(50) DEFAULT NULL COMMENT '部署ID',
  `vpc` varchar(255) DEFAULT NULL COMMENT 'VPC名称',
  `vpcid` varchar(255) DEFAULT NULL COMMENT 'VPC ID标识符',
  `vpccidr` varchar(100) DEFAULT NULL COMMENT 'VPC CIDR地址块',
  `subnet` varchar(255) DEFAULT NULL COMMENT '子网ID',
  `subnetid` varchar(255) DEFAULT NULL COMMENT '子网ID标识符',
  `subnetvpc` varchar(255) DEFAULT NULL COMMENT '子网所属VPC ID',
  `subnetcidr` varchar(100) DEFAULT NULL COMMENT '子网CIDR地址块',
  `object` varchar(255) DEFAULT NULL COMMENT '对象存储',
  `iam_user` varchar(255) DEFAULT NULL COMMENT 'IAM用户',
  `iamid` varchar(255) DEFAULT NULL COMMENT 'IAM用户ID',
  `iamarn` varchar(255) DEFAULT NULL COMMENT 'IAM用户ARN',
  `elb_name` varchar(255) DEFAULT NULL COMMENT 'ELB名称',
  `elb_arn` varchar(255) DEFAULT NULL COMMENT 'ELB ARN',
  `elb_type` varchar(100) DEFAULT NULL COMMENT 'ELB类型',
  `ec2_name` varchar(255) DEFAULT NULL COMMENT 'EC2实例名称',
  `ec2_id` varchar(255) DEFAULT NULL COMMENT 'EC2实例ID',
  `ec2_type` varchar(100) DEFAULT NULL COMMENT 'EC2实例类型',
  `ec2_state` varchar(100) DEFAULT NULL COMMENT 'EC2实例状态',
  `s3_name` varchar(255) DEFAULT NULL COMMENT 'S3存储桶名称',
  `s3_region` varchar(100) DEFAULT NULL COMMENT 'S3存储桶区域',
  `rds_identifier` varchar(255) DEFAULT NULL COMMENT 'RDS标识符',
  `rds_engine` varchar(100) DEFAULT NULL COMMENT 'RDS引擎',
  `rds_status` varchar(100) DEFAULT NULL COMMENT 'RDS状态',
  `lambda_name` varchar(255) DEFAULT NULL COMMENT 'Lambda函数名',
  `resource_name` varchar(255) DEFAULT NULL COMMENT '通用资源名称',
  `iam_user_group` varchar(255) DEFAULT NULL COMMENT 'IAM用户组',
  `iam_user_policy` varchar(255) DEFAULT NULL COMMENT 'IAM用户策略',
  `resource_type` varchar(50) DEFAULT NULL COMMENT '资源类型',
  `resource_index` int DEFAULT NULL COMMENT '资源索引',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_username` (`username`),
  KEY `idx_project_cloud` (`project`,`cloud`)
) ENGINE=InnoDB AUTO_INCREMENT=1314 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='云资源配置表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `clouddeploy`
--

DROP TABLE IF EXISTS `clouddeploy`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clouddeploy` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(255) NOT NULL COMMENT '用户名',
  `user_id` int NOT NULL COMMENT '用户ID',
  `project` varchar(255) NOT NULL COMMENT '项目名称',
  `cloud` varchar(255) NOT NULL COMMENT '云服务提供商',
  `ak` varchar(255) NOT NULL COMMENT 'Access Key',
  `sk` varchar(255) NOT NULL COMMENT 'Secret Key',
  `region` varchar(100) DEFAULT NULL COMMENT '区域',
  `deployid` varchar(20) DEFAULT NULL COMMENT '部署ID',
  `vpc` varchar(255) DEFAULT NULL COMMENT 'VPC名称',
  `vpcid` varchar(255) DEFAULT NULL COMMENT 'VPC ID标识符',
  `vpccidr` varchar(100) DEFAULT NULL COMMENT 'VPC CIDR地址块',
  `subnet` varchar(255) DEFAULT NULL COMMENT '子网ID',
  `subnetid` varchar(255) DEFAULT NULL COMMENT '子网ID标识符',
  `subnetvpc` varchar(255) DEFAULT NULL COMMENT '子网所属VPC ID',
  `subnetcidr` varchar(100) DEFAULT NULL COMMENT '子网CIDR地址块',
  `object` varchar(255) DEFAULT NULL COMMENT '对象存储',
  `objectid` varchar(255) DEFAULT NULL COMMENT '对象存储ID',
  `objectarn` varchar(255) DEFAULT NULL COMMENT '对象存储ARN',
  `iam_user` varchar(255) DEFAULT NULL COMMENT 'IAM用户',
  `iamid` varchar(255) DEFAULT NULL COMMENT 'IAM用户ID',
  `iamarn` varchar(255) DEFAULT NULL COMMENT 'IAM用户ARN',
  `iam_user_group` varchar(255) DEFAULT NULL COMMENT 'IAM用户组',
  `iam_user_policy` varchar(255) DEFAULT NULL COMMENT 'IAM用户策略',
  `iam_policy` varchar(255) DEFAULT NULL COMMENT 'IAM策略',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deploy_progress` int DEFAULT '0' COMMENT '部署进度',
  `deploytype` int DEFAULT NULL COMMENT '部署类型',
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_username` (`username`),
  KEY `idx_project_cloud` (`project`,`cloud`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='云资源部署表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `clouds`
--

DROP TABLE IF EXISTS `clouds`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `clouds` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL COMMENT '云服务提供商名称',
  `logo` varchar(500) DEFAULT NULL COMMENT '云服务提供商Logo URL',
  `provider` varchar(100) DEFAULT NULL COMMENT '提供商公司名称',
  `regions` text COMMENT '支持的区域，JSON格式存储',
  `is_active` tinyint(1) DEFAULT '1' COMMENT '是否激活，1表示激活，0表示禁用',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=3104 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='云服务提供商表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `deployment_resources`
--

DROP TABLE IF EXISTS `deployment_resources`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `deployment_resources` (
  `id` int NOT NULL AUTO_INCREMENT,
  `deploy_id` varchar(20) NOT NULL COMMENT '部署ID',
  `resource_type` varchar(50) NOT NULL COMMENT '资源类型',
  `resource_name` varchar(100) NOT NULL COMMENT '资源名称',
  `status` enum('pending','in_progress','completed','failed','planned') DEFAULT 'pending' COMMENT '资源状态',
  `details` text COMMENT '详细信息',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_deploy_id` (`deploy_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='资源部署状态跟踪表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `deployments`
--

DROP TABLE IF EXISTS `deployments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `deployments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `deployid` varchar(20) NOT NULL COMMENT '部署ID',
  `deploy_type` varchar(20) DEFAULT 'template' COMMENT '部署类型（template/manual）',
  `cloud` varchar(50) NOT NULL COMMENT '云服务商',
  `project` varchar(255) NOT NULL COMMENT '项目名称',
  `region` varchar(100) DEFAULT NULL COMMENT '区域',
  `user_id` int NOT NULL COMMENT '用户ID',
  `username` varchar(100) NOT NULL COMMENT '用户名',
  `status` varchar(50) DEFAULT 'in_progress' COMMENT '部署状态',
  `template_id` varchar(36) DEFAULT NULL COMMENT '关联的模板ID',
  `deploy_progress` int DEFAULT '0' COMMENT '部署进度（0-100）',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `deployid` (`deployid`),
  KEY `idx_deployid` (`deployid`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_status` (`status`),
  KEY `idx_template_id` (`template_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='部署记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `projects`
--

DROP TABLE IF EXISTS `projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `projects` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL COMMENT '项目名称',
  `description` text COMMENT '项目描述',
  `user_id` int NOT NULL COMMENT '项目所属用户ID',
  `created_by` varchar(50) DEFAULT NULL COMMENT '创建人用户名',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`),
  KEY `idx_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='项目表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `start`
--

DROP TABLE IF EXISTS `start`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `start` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '序号',
  `Q` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '问题',
  `A` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '答案',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='FAQ问答表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `system_logs`
--

DROP TABLE IF EXISTS `system_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `system_logs` (
  `id` int NOT NULL AUTO_INCREMENT,
  `message` text NOT NULL COMMENT '日志消息',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='系统日志表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `templates`
--

DROP TABLE IF EXISTS `templates`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `templates` (
  `id` varchar(36) NOT NULL COMMENT '模板ID（UUID）',
  `user_id` int NOT NULL COMMENT '用户ID',
  `username` varchar(100) NOT NULL COMMENT '用户名',
  `template_name` varchar(100) NOT NULL COMMENT '模板名称',
  `description` text COMMENT '模板描述',
  `topology_image` varchar(255) DEFAULT NULL COMMENT '拓扑图片URL',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='模板表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(255) NOT NULL COMMENT '用户名',
  `password` varchar(255) NOT NULL COMMENT '密码（加密后）',
  `department` varchar(255) DEFAULT NULL COMMENT '部门',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  KEY `idx_username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户表';
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-07-14 18:10:18
