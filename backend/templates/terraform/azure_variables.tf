# Azure Terraform 变量定义
# 这个文件定义了Azure provider需要的变量

variable "tenant_id" {
  description = "Azure AD tenant ID"
  type        = string
  sensitive   = true
}

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
  sensitive   = true
}

# 输出变量说明
output "variable_instructions" {
  value = <<EOF
Azure Terraform部署需要以下变量：

1. tenant_id: Azure AD租户ID
   获取方法: az account show --query tenantId --output tsv

2. subscription_id: Azure订阅ID  
   获取方法: az account show --query id --output tsv

在terraform.tfvars文件中设置这些值：
tenant_id = "your-tenant-id"
subscription_id = "your-subscription-id"
EOF
} 