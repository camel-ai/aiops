FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    wget \
    unzip \
    graphviz \
    && rm -rf /var/lib/apt/lists/*

# 安装Terraform
RUN TERRAFORM_VERSION=1.12.1 && \
    wget https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip && \
    unzip terraform_${TERRAFORM_VERSION}_linux_amd64.zip && \
    mv terraform /usr/local/bin/ && \
    rm terraform_${TERRAFORM_VERSION}_linux_amd64.zip && \
    terraform --version

# 配置Terraform provider缓存
# 创建.terraformrc配置文件
RUN echo 'provider_installation {\n  filesystem_mirror {\n    path    = "/root/terraform.d/plugins"\n    include = ["registry.terraform.io/*/*"]\n  }\n}' > /root/.terraformrc

# 创建terraform provider目录结构
RUN mkdir -p /root/terraform.d/plugins/registry.terraform.io/hashicorp/external/2.3.5/linux_amd64 && \
    mkdir -p /root/terraform.d/plugins/registry.terraform.io/hashicorp/aws/5.84.0/linux_amd64

# 复制terraform provider文件
COPY docker/backend/terraform-provider-external_v2.3.5_x5 /root/terraform.d/plugins/registry.terraform.io/hashicorp/external/2.3.5/linux_amd64/terraform-provider-external_v2.3.5_x5
COPY docker/backend/terraform-provider-aws_v5.84.0_x5 /root/terraform.d/plugins/registry.terraform.io/hashicorp/aws/5.84.0/linux_amd64/terraform-provider-aws_v5.84.0_x5

# 设置terraform provider文件权限
RUN chmod 777 /root/terraform.d/plugins/registry.terraform.io/hashicorp/external/2.3.5/linux_amd64/terraform-provider-external_v2.3.5_x5 && \
    chmod 777 /root/terraform.d/plugins/registry.terraform.io/hashicorp/aws/5.84.0/linux_amd64/terraform-provider-aws_v5.84.0_x5

# 验证terraform配置
RUN cat /root/.terraformrc && \
    ls -la /root/terraform.d/plugins/registry.terraform.io/hashicorp/external/2.3.5/linux_amd64/ && \
    ls -la /root/terraform.d/plugins/registry.terraform.io/hashicorp/aws/5.84.0/linux_amd64/

# 复制requirements文件
COPY backend/requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY backend/ .

# 创建必要目录
RUN mkdir -p upload static/uploads static/downloads templates/uploads

# 设置权限
RUN chmod -R 755 upload static

# 设置环境变量
ENV PYTHONPATH=/app
ENV FLASK_APP=app.py
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# 启动命令
CMD ["python", "app.py"] 