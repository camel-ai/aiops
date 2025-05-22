from typing import Dict, Any, Optional, List
from .base import TextPrompt, TextPromptDict


class DevOpsPromptTemplateDict(TextPromptDict):
    """Dictionary of prompt templates for DevOps assistant.
    
    This class provides specialized prompt templates for DevOps tasks
    such as cloud resource management, deployment automation, and
    infrastructure monitoring.
    """
    
    CLOUD_RESOURCE_MANAGEMENT = TextPrompt(
        """作为DevOps助手，请帮助用户管理以下云资源：
        
云服务提供商: {cloud_provider}
资源类型: {resource_type}
区域: {region}
项目ID: {project_id}

用户需求: {user_request}

请提供详细的资源管理建议，包括：
1. 资源创建和配置的最佳实践
2. 成本优化建议
3. 安全合规考虑
4. 自动化管理方案

如果需要执行具体操作，请提供详细的步骤或代码示例。"""
    )
    
    DEPLOYMENT_AUTOMATION = TextPrompt(
        """作为DevOps助手，请帮助用户设计和实现以下部署自动化流程：
        
应用类型: {application_type}
部署环境: {environment}
CI/CD工具: {ci_cd_tools}
项目ID: {project_id}

用户需求: {user_request}

请提供详细的部署自动化方案，包括：
1. CI/CD流程设计
2. 配置文件和脚本示例
3. 测试和验证策略
4. 回滚和灾难恢复计划

如果需要执行具体操作，请提供详细的步骤或代码示例。"""
    )
    
    INFRASTRUCTURE_MONITORING = TextPrompt(
        """作为DevOps助手，请帮助用户设计和实现以下基础设施监控方案：
        
监控对象: {monitoring_targets}
监控工具: {monitoring_tools}
告警需求: {alerting_requirements}
项目ID: {project_id}

用户需求: {user_request}

请提供详细的监控方案，包括：
1. 监控指标和阈值设置
2. 告警规则和通知渠道
3. 仪表盘和可视化设计
4. 自动化响应策略

如果需要执行具体操作，请提供详细的步骤或代码示例。"""
    )
    
    TROUBLESHOOTING = TextPrompt(
        """作为DevOps助手，请帮助用户诊断和解决以下问题：
        
问题描述: {issue_description}
环境信息: {environment_info}
相关日志: {logs}
项目ID: {project_id}

请提供详细的问题分析和解决方案，包括：
1. 问题根因分析
2. 解决步骤
3. 验证方法
4. 预防措施

如果需要执行具体操作，请提供详细的步骤或代码示例。"""
    )
    
    TERRAFORM_TEMPLATE = TextPrompt(
        """作为DevOps助手，请帮助用户创建以下Terraform配置：
        
资源类型: {resource_type}
云服务提供商: {cloud_provider}
配置参数: {configuration}
项目ID: {project_id}

用户需求: {user_request}

请提供完整的Terraform配置文件，包括：
1. 提供商配置
2. 资源定义
3. 变量和输出
4. 模块组织（如适用）

配置应遵循Terraform最佳实践，并包含适当的注释。"""
    )
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize DevOpsPromptTemplateDict with default templates."""
        super().__init__(*args, **kwargs)
        self.update({
            "cloud_resource_management": self.CLOUD_RESOURCE_MANAGEMENT,
            "deployment_automation": self.DEPLOYMENT_AUTOMATION,
            "infrastructure_monitoring": self.INFRASTRUCTURE_MONITORING,
            "troubleshooting": self.TROUBLESHOOTING,
            "terraform_template": self.TERRAFORM_TEMPLATE,
        })
