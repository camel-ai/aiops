FROM mysql:8.0

# 复制数据库初始化脚本
COPY 01-schema.sql /docker-entrypoint-initdb.d/01-schema.sql
COPY 02-data.sql /docker-entrypoint-initdb.d/02-data.sql

# 复制MySQL配置文件
COPY my.cnf /etc/mysql/conf.d/custom.cnf

# 设置权限
RUN chmod 644 /docker-entrypoint-initdb.d/01-schema.sql
RUN chmod 644 /docker-entrypoint-initdb.d/02-data.sql
RUN chmod 644 /etc/mysql/conf.d/custom.cnf

# 暴露端口
EXPOSE 3306

# 使用官方镜像的默认启动命令 