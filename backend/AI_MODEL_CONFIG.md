# AI模型配置指南

本文档说明如何在MCDP平台中配置不同的AI模型提供商。

## 支持的AI模型提供商

目前系统支持以下AI模型提供商：
- OpenAI (GPT-4, GPT-3.5等)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Opus等)

## 配置方法

### 1. 复制环境变量示例文件

```bash
cd backend
cp env.example .env
```

### 2. 编辑.env文件

根据您要使用的AI模型提供商，配置相应的环境变量：

#### 使用OpenAI

```env
# AI模型配置
AI_MODEL_PROVIDER=openai

# OpenAI API配置
OPENAI_API_KEY=your-openai-api-key
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_API_MODEL=gpt-4o
```

#### 使用Anthropic

```env
# AI模型配置
AI_MODEL_PROVIDER=anthropic

# Anthropic API配置
ANTHROPIC_API_KEY=your-anthropic-api-key
ANTHROPIC_API_BASE_URL=https://api.anthropic.com/v1
ANTHROPIC_API_MODEL=claude-3-5-sonnet-20241022
```

### 3. 支持的模型列表

#### OpenAI模型
- `gpt-4o` - GPT-4 Optimized (推荐)
- `gpt-4-turbo-preview` - GPT-4 Turbo
- `gpt-4` - GPT-4
- `gpt-3.5-turbo` - GPT-3.5 Turbo

#### Anthropic模型
- `claude-3-5-sonnet-20241022` - Claude 3.5 Sonnet (推荐)
- `claude-3-opus-20240229` - Claude 3 Opus
- `claude-3-sonnet-20240229` - Claude 3 Sonnet
- `claude-3-haiku-20240307` - Claude 3 Haiku

### 4. 自定义API端点

如果您使用的是兼容的API服务（如Azure OpenAI Service或其他代理服务），可以通过修改`API_BASE_URL`来指定自定义端点：

```env
# 使用Azure OpenAI Service
OPENAI_API_BASE_URL=https://your-resource.openai.azure.com/
OPENAI_API_KEY=your-azure-api-key
OPENAI_API_MODEL=your-deployment-name

# 使用Anthropic兼容服务
ANTHROPIC_API_BASE_URL=https://your-anthropic-proxy.com/v1
```

## 功能说明

配置完成后，系统会在以下功能中使用您选择的AI模型：

1. **@ai命令** - 生成云架构拓扑图和Terraform代码
   - 支持文字描述生成架构图
   - 支持上传图片分析并生成架构图
   - 自动生成对应的Terraform部署代码

2. **功能特性**
   - 两种AI提供商都支持完整的功能
   - 生成的Mermaid图表格式一致
   - Terraform代码生成质量相当

## 注意事项

1. **API密钥安全**
   - 请勿将API密钥提交到版本控制系统
   - .env文件应该被添加到.gitignore中

2. **API限制**
   - 不同的AI提供商有不同的速率限制
   - 请参考各自的官方文档了解限制详情

3. **成本考虑**
   - 不同模型的定价不同
   - Claude 3.5 Sonnet通常比GPT-4更经济
   - 建议根据实际需求选择合适的模型

## 故障排除

### 常见问题

1. **"未配置API密钥"错误**
   - 检查.env文件中是否正确设置了API密钥
   - 确保环境变量名称正确

2. **"API调用失败"错误**
   - 检查API密钥是否有效
   - 检查网络连接
   - 确认API端点URL正确

3. **"不支持的AI模型提供商"错误**
   - 检查AI_MODEL_PROVIDER的值是否为`openai`或`anthropic`
   - 注意大小写

## 扩展开发

如果需要添加新的AI模型提供商支持，请参考以下步骤：

1. 在`backend/utils/ai_client_factory.py`中添加新的客户端类
2. 实现`BaseAIClient`接口的所有方法
3. 在`AIClientFactory.create_client()`方法中添加新的分支
4. 更新配置文件和文档

## 更新日志

- 2024-01-XX: 添加Anthropic Claude支持
- 初始版本: 仅支持OpenAI 