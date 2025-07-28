# Azure API密钥映射修复总结

## 问题描述

用户报告了Azure部署时的两个关键问题：

1. **API密钥映射错误**：
   - AK (Access Key) 应该对应 `client_id`，但代码中错误地映射到 `subscription_id`
   - SK (Secret Key) 正确对应 `client_secret`

2. **版本问题**：
   - Azure provider默认使用3.0版本，需要更新到4.0版本

## 修复内容

### 1. API密钥映射修复

**修复前 (错误映射)**：
```hcl
provider "azurerm" {
  features {}
  subscription_id = "340fbb69-5b10-4f05-b1ca-c403e036cc70"  # 错误：AK映射到subscription_id
  client_secret   = "b7l8Q~l4_2nCZjlq-QwpV62vEd.umYZ5gKK__bxD"
  client_id       = var.client_id                           # 错误：使用变量
  tenant_id       = var.tenant_id
  use_cli         = false
}
```

**修复后 (正确映射)**：
```hcl
provider "azurerm" {
  features {}
  client_id       = "your-actual-client-id"                 # 正确：AK映射到client_id
  client_secret   = "b7l8Q~l4_2nCZjlq-QwpV62vEd.umYZ5gKK__bxD"  # 正确：SK映射到client_secret
  tenant_id       = var.tenant_id
  subscription_id = var.subscription_id
  use_cli         = false
}
```

### 2. 版本更新

**修复前**：
```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"                                    # 旧版本
    }
  }
}
```

**修复后**：
```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"                                    # 新版本
    }
  }
}
```

## 修改的文件

1. **backend/toolkits/terraform_generator.py**
   - `_generate_azure_config()` 方法
   - 修复AK→client_id映射
   - 更新版本到4.0

2. **backend/controllers/terraform_controller.py**
   - `_add_azure_credentials_to_code()` 方法
   - 修复凭证添加逻辑

3. **backend/controllers/deploy_controller.py**
   - 6个Azure provider配置位置
   - 统一修复映射和版本

4. **backend/prompts/cloud_terraform_prompts.py**
   - Azure提示模板
   - 更新示例配置

5. **backend/templates/terraform/azure_variables.tf** (新增)
   - 变量定义文件
   - 使用说明

## Azure认证参数说明

| 参数 | 用途 | 获取方法 |
|------|------|----------|
| `client_id` | 应用程序ID (对应AK) | Azure Portal → App registrations → Application ID |
| `client_secret` | 应用程序密钥 (对应SK) | Azure Portal → App registrations → Certificates & secrets |
| `tenant_id` | 租户ID | `az account show --query tenantId --output tsv` |
| `subscription_id` | 订阅ID | `az account show --query id --output tsv` |

## 用户需要设置的变量

在使用Azure部署时，用户需要在 `terraform.tfvars` 文件中设置：

```hcl
tenant_id = "your-tenant-id"
subscription_id = "your-subscription-id"
```

而 `client_id` 和 `client_secret` 会自动从API密钥设置中获取。

## 验证修复

修复后，Azure VM部署生成的 `main.tf` 文件将正确包含：

```hcl
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  client_id       = "your-actual-client-id"       # AK正确映射
  client_secret   = "your-actual-client-secret"   # SK正确映射
  tenant_id       = var.tenant_id
  subscription_id = var.subscription_id
  use_cli         = false
}
```

## 影响范围

此修复影响所有Azure相关的Terraform代码生成，包括：
- VM部署
- 网络配置  
- 存储配置
- IAM配置
- 所有其他Azure资源部署

修复确保了Azure认证的正确性和与Azure provider 4.0版本的兼容性。 