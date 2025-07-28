# Azure Provider属性重复定义问题修复

## 问题描述

用户在部署Azure VM时遇到Terraform初始化错误：

```
Error: Attribute redefined

  on main.tf line 16, in provider "azurerm":
  16:   tenant_id = var.tenant_id

The argument "tenant_id" was already set at main.tf:12,3-12. Each argument
may be set only once.

Error: Attribute redefined

  on main.tf line 17, in provider "azurerm":
  17:   subscription_id = var.subscription_id

The argument "subscription_id" was already set at main.tf:13,3-18. Each argument
may be set only once.
```

## 原因分析

问题出现在`_add_azure_credentials_to_code`方法中：

1. **用户明确提供了租户ID和订阅ID**：
   ```hcl
   provider "azurerm" {
     features {}
     tenant_id       = "b6463641-ad49-4585-8d26-d6b74af98d54"    # 第12行
     subscription_id = "b6ff4863-83cf-4faa-9119-afb68d015bb7"    # 第13行
     client_id = "340fbb69-5b10-4f05-b1ca-c403e036cc70"
     client_secret = "b7l8Q~l4_2nCZjlq-QwpV62vEd.umYZ5gKK__bxD"
     use_cli = false
   }
   ```

2. **系统仍然添加变量形式的配置**：
   ```hcl
   # 系统自动添加的
   tenant_id = var.tenant_id          # 第16行 - 重复定义
   subscription_id = var.subscription_id   # 第17行 - 重复定义
   ```

## 修复方案

### 修复前的逻辑

```python
# 简单检查是否有凭证
has_credentials = False
for i in range(start, end):
    if re.search(r'subscription_id\s*=\s*".+?"', lines[i]) and re.search(r'client_secret\s*=\s*".+?"', lines[i]):
        has_credentials = True
        break

if not has_credentials:
    # 无条件添加所有配置
    credentials = [
        f"  client_id = \"{ak}\"",
        f"  client_secret = \"{sk}\"",
        f"  tenant_id = var.tenant_id",
        f"  subscription_id = var.subscription_id",
        f"  use_cli = false"
    ]
```

### 修复后的逻辑

```python
# 详细检查每个配置属性
has_client_id = False
has_client_secret = False
has_tenant_id = False
has_subscription_id = False
has_use_cli = False

for i in range(start, end):
    line = lines[i]
    if re.search(r'client_id\s*=', line):
        has_client_id = True
    elif re.search(r'client_secret\s*=', line):
        has_client_secret = True
    elif re.search(r'tenant_id\s*=', line):
        has_tenant_id = True
    elif re.search(r'subscription_id\s*=', line):
        has_subscription_id = True
    elif re.search(r'use_cli\s*=', line):
        has_use_cli = True

# 只添加缺失的配置
credentials_to_add = []
if not has_client_id:
    credentials_to_add.append(f"  client_id = \"{ak}\"")
if not has_client_secret:
    credentials_to_add.append(f"  client_secret = \"{sk}\"")
if not has_tenant_id:
    credentials_to_add.append(f"  tenant_id = var.tenant_id")
if not has_subscription_id:
    credentials_to_add.append(f"  subscription_id = var.subscription_id")
if not has_use_cli:
    credentials_to_add.append(f"  use_cli = false")
```

## 修复效果

### 场景1：用户明确提供租户ID和订阅ID

**输入代码**：
```hcl
provider "azurerm" {
  features {}
  tenant_id       = "b6463641-ad49-4585-8d26-d6b74af98d54"
  subscription_id = "b6ff4863-83cf-4faa-9119-afb68d015bb7"
  client_id = "340fbb69-5b10-4f05-b1ca-c403e036cc70"
  client_secret = "b7l8Q~l4_2nCZjlq-QwpV62vEd.umYZ5gKK__bxD"
  use_cli = false
}
```

**修复后输出**：
```hcl
provider "azurerm" {
  features {}
  tenant_id       = "b6463641-ad49-4585-8d26-d6b74af98d54"
  subscription_id = "b6ff4863-83cf-4faa-9119-afb68d015bb7"
  client_id = "340fbb69-5b10-4f05-b1ca-c403e036cc70"
  client_secret = "b7l8Q~l4_2nCZjlq-QwpV62vEd.umYZ5gKK__bxD"
  use_cli = false
}
# 不会添加任何重复配置，因为所有配置都已存在
```

### 场景2：用户只提供部分配置

**输入代码**：
```hcl
provider "azurerm" {
  features {}
}
```

**修复后输出**：
```hcl
provider "azurerm" {
  features {}
  client_id = "your-ak-value"
  client_secret = "your-sk-value"
  tenant_id = var.tenant_id
  subscription_id = var.subscription_id
  use_cli = false
}
```

### 场景3：混合配置

**输入代码**：
```hcl
provider "azurerm" {
  features {}
  tenant_id = "specific-tenant-id"
}
```

**修复后输出**：
```hcl
provider "azurerm" {
  features {}
  tenant_id = "specific-tenant-id"
  client_id = "your-ak-value"
  client_secret = "your-sk-value"
  subscription_id = var.subscription_id
  use_cli = false
}
# 只添加缺失的配置，保留已有的具体值
```

## 技术细节

### 智能检测逻辑

1. **属性检测**：使用正则表达式`r'属性名\s*='`检测每个属性是否存在
2. **条件添加**：只有当属性不存在时才添加
3. **日志记录**：记录添加的配置和跳过的配置，便于调试

### 支持的配置属性

- `client_id`：应用程序ID (对应AK)
- `client_secret`：应用程序密钥 (对应SK) 
- `tenant_id`：租户ID
- `subscription_id`：订阅ID
- `use_cli`：是否使用CLI认证

## 验证方法

部署Azure资源时，检查生成的main.tf文件：

1. **无重复属性**：每个属性只出现一次
2. **保留用户配置**：明确提供的值不被覆盖
3. **补充缺失配置**：自动添加缺失的必要配置

## 日志输出

修复后的方法会输出详细日志：

```
[INFO] 添加缺失的Azure凭证配置: ['  client_id = "your-ak"', '  client_secret = "your-sk"']
```

或

```
[INFO] Azure provider配置已完整，无需添加凭证
```

这样可以清楚地了解系统的处理过程。 