# 构建阶段
FROM node:18-alpine as builder

WORKDIR /app

# 复制package文件
COPY frontend/package*.json ./
RUN npm install

# 复制源代码并构建
COPY frontend/ ./
RUN npm run build

# 生产阶段
FROM nginx:alpine

# 复制构建结果
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制nginx配置（完整优化版本）
COPY docker/frontend/nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"] 