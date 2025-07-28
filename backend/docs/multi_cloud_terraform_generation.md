# 多云Terraform代码生成功能

## 概述

本系统现在支持为9个不同的云提供商生成对应的Terraform代码，不再仅限于AWS。AI会根据用户的描述自动检测目标云平台，并生成相应的云特定Terraform代码。

## 支持的云提供商

1. **AWS** - Amazon Web Services
2. **AZURE** - Microsoft Azure
3. **阿里云** - Alibaba Cloud
4. **华为云** - Huawei Cloud
5. **腾讯云** - Tencent Cloud
6. **百度云** - Baidu Cloud
7. **火山云** - Volcengine (ByteDance)
8. **AWS(CHINA)** - AWS中国区域
9. **AZURE(CHINA)** - Azure中国区域

## 功能特性

### 1. 自动云平台检测

系统会自动分析用户输入的描述，检测目标云平台：

```python
# 示例检测结果
"在AWS上部署VPC" → "AWS"
"在阿里云上创建ECS" → "阿里云"
"使用火山云部署应用" → "火山云"
"在Azure上创建虚拟网络" → "AZURE"
```

### 2. 云特定的AI Prompts

每个云平台都有专门的AI提示模板，包含：

- 云特定的资源命名规范
- Provider配置示例
- 最佳实践指导
- 版本要求

### 3. 资源命名规范

不同云平台使用不同的资源命名规范：

| 云平台 | VPC资源 | 计算实例 | 存储 |
|--------|---------|----------|------|
| AWS | `aws_vpc` | `aws_instance` | `aws_s3_bucket` |
| Azure | `azurerm_virtual_network` | `azurerm_virtual_machine` | `azurerm_storage_account` |
| 阿里云 | `alicloud_vpc` | `alicloud_instance` | `alicloud_oss_bucket` |
| 华为云 | `huaweicloud_vpc` | `huaweicloud_compute_instance` | `huaweicloud_obs_bucket` |
| 腾讯云 | `tencentcloud_vpc` | `tencentcloud_instance` | `tencentcloud_cos_bucket` |
| 百度云 | `baiducloud_vpc` | `baiducloud_instance` | `baiducloud_bos_bucket` |
| 火山云 | `volcengine_vpc` | `volcengine_ecs_instance` | `volcengine_tos_bucket` |

## 技术实现

### 核心组件

1. **CloudTerraformPrompts** - 云平台特定的prompt管理器
2. **云平台检测逻辑** - 基于关键词的自动检测
3. **更新的控制器** - terraform_controller.py, diagram_controller.py
4. **AI客户端工厂** - 支持多云的AI客户端

### 文件结构

```
backend/
├── prompts/
│   └── cloud_terraform_prompts.py      # 云平台prompt管理器
├── controllers/
│   ├── terraform_controller.py         # 更新支持多云
│   └── diagram_controller.py           # 更新支持多云
├── utils/
│   └── ai_client_factory.py            # 更新AI客户端接口
└── docs/
    └── multi_cloud_terraform_generation.md
```

### 使用示例

#### 在控制器中使用

```python
from prompts.cloud_terraform_prompts import CloudTerraformPrompts

# 1. 检测云平台
cloud_provider = CloudTerraformPrompts.detect_cloud_from_description(user_description)

# 2. 生成云特定的系统prompt
system_prompt = CloudTerraformPrompts.get_cloud_specific_prompt(cloud_provider, user_description)

# 3. 生成用户prompt
user_prompt = CloudTerraformPrompts.get_user_prompt_template().format(
    user_description=user_description,
    mermaid_code=mermaid_code,
    cloud_provider=cloud_provider
)

# 4. 调用AI生成Terraform代码
terraform_code = ai_client.generate_terraform(user_description, mermaid_code, cloud_provider)
```

## 测试验证

系统包含完整的测试套件：

1. **基础功能测试** - `test_multi_cloud_terraform.py`
   - 云平台检测准确性
   - Prompt模板完整性
   - 关键词覆盖率验证

2. **集成测试** - `test_terraform_generation_integration.py`
   - 端到端生成流程
   - 多云场景测试
   - 性能指标统计

### 测试结果

最新测试结果：
- **检测准确率**: 100%
- **关键词覆盖率**: 100%
- **资源覆盖率**: 91.7%

## 配置要求

### Provider版本要求

```hcl
# AWS
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.84.0"
    }
  }
}

# Azure
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

# 阿里云
terraform {
  required_providers {
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.0"
    }
  }
}

# 火山云
terraform {
  required_providers {
    volcengine = {
      source = "volcengine/volcengine"
      version = "0.0.167"
    }
  }
}
```

## 使用指南

### 1. 用户输入示例

用户可以使用自然语言描述他们想要在特定云平台上部署的基础设施：

- "在AWS上创建一个VPC和EC2实例"
- "在阿里云上部署ECS和RDS数据库"
- "使用火山云搭建一个Web应用架构"
- "在Azure上创建虚拟网络和虚拟机"

### 2. 系统处理流程

1. **解析用户输入** - 提取云平台和资源需求
2. **检测目标云平台** - 自动识别或使用默认AWS
3. **生成Mermaid图表** - 可视化基础设施架构
4. **生成Terraform代码** - 使用云特定的资源和语法
5. **返回结果** - 包含图表和可执行的Terraform代码

### 3. 注意事项

- 凭证管理：所有云平台的访问凭证都会在部署时自动添加
- 区域设置：系统会使用云平台特定的默认区域
- 资源依赖：AI会自动添加必要的依赖资源（如安全组、网络规则等）

## 扩展支持

如需添加新的云平台支持：

1. 在`CloudTerraformPrompts.detect_cloud_from_description()`中添加检测关键词
2. 在`CloudTerraformPrompts.get_cloud_specific_prompt()`中添加云特定的prompt
3. 更新测试用例
4. 更新文档

## 故障排除

### 常见问题

1. **检测不准确** - 确保用户描述中包含明确的云平台关键词
2. **生成代码不正确** - 检查prompt模板是否包含正确的资源命名规范
3. **凭证问题** - 确保在部署阶段正确配置了相应云平台的API密钥

### 调试方法

```python
# 启用调试日志
import logging
logging.getLogger('prompts.cloud_terraform_prompts').setLevel(logging.DEBUG)

# 测试云平台检测
from prompts.cloud_terraform_prompts import CloudTerraformPrompts
detected = CloudTerraformPrompts.detect_cloud_from_description("你的描述")
print(f"检测到的云平台: {detected}")
```

## 更新日志

- **v1.0** - 初始实现，支持9个云平台的Terraform代码生成
- 自动云平台检测功能
- 云特定的AI prompt系统
- 完整的测试套件 