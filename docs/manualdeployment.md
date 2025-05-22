# 下载最新Miniconda（Linux x86_64版本）
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh

# 验证文件完整性（可选）
sha256sum Miniconda3-latest-Linux-x86_64.sh

# 执行安装（安装到/opt/miniconda3）
sudo bash Miniconda3-latest-Linux-x86_64.sh -b -p /opt/miniconda3

# 设置全局环境变量
echo 'export PATH="/opt/miniconda3/bin:$PATH"' | sudo tee /etc/profile.d/conda.sh
source /etc/profile.d/conda.sh

# 更新 conda 并安装 Python 3.12
sudo /opt/miniconda3/bin/conda update -n base -c defaults conda -y
sudo /opt/miniconda3/bin/conda install -n base python=3.12 -y

# 验证安装
/opt/miniconda3/bin/python --version  # 应输出 Python 3.12.x

vi .bashrc 最后加入
echo 'conda activate base' >> ~/.bashrc
source ~/.bashrc

#解压mcdp.zip
unzip -o mcdp.zip

#安装前端
cd /root/mcdp/frontend
sudo yum install -y nodejs
npm install
npm run build
cp -rf dist/* /var/www/html

#安装nginx
yum install nginx
vi /etc/nginx/nginx.conf

pid /run/nginx.pid;

events {
    worker_connections 1024;  # 增加连接数
}

http {
    # 基本设置
    sendfile on;
    tcp_nopush on;
    types_hash_max_size 2048;
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # SSL设置
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    # 日志设置
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;

    # Gzip设置
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;

    # 全局请求体大小限制
    client_max_body_size 200M;

    # 超时设置
    client_header_timeout 3600s;
    client_body_timeout 3600s;
    keepalive_timeout 3600s;
    send_timeout 3600s;
    
    # 增加全局缓冲区大小
    client_body_buffer_size 10M;  
    large_client_header_buffers 4 16k;
    
    # 增加代理缓冲区 - 修复配置
    proxy_buffer_size 16k;
    proxy_buffers 8 16k;
    proxy_busy_buffers_size 32k;
    # 确保proxy_temp_file_write_size至少等于proxy_buffer_size和proxy_buffers的最大值
    proxy_temp_file_write_size 128k;  # 修改为至少32k或更大
    proxy_max_temp_file_size 100m;

    server {
        listen 80;
        server_name YOURSERVERIP;

        root /var/www/html;
        index index.html;

        # 安全头部
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        location / {
            # CORS配置
            add_header 'Access-Control-Allow-Origin' '$http_origin' always;
            add_header 'Access-Control-Allow-Credentials' 'true' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Origin, Content-Type, Accept, Authorization' always;
            
            try_files $uri $uri/ /index.html;
        }

        # API代理
        location /api/ {
            # CORS头部
            add_header 'Access-Control-Allow-Origin' '$http_origin' always;
            add_header 'Access-Control-Allow-Credentials' 'true' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Origin, X-Requested-With, Content-Type, Accept, Authorization' always;
            add_header 'Access-Control-Expose-Headers' 'Content-Length, Content-Range' always;
            
            # OPTIONS处理
            if ($request_method = 'OPTIONS') {
                add_header 'Access-Control-Max-Age' 1728000;
                add_header 'Content-Type' 'text/plain charset=UTF-8';
                add_header 'Content-Length' 0;
                return 204;
            }
            
            proxy_pass http://localhost:8081/api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Origin $http_origin;
            
            # 增加代理超时时间
            proxy_connect_timeout 600s;
            proxy_send_timeout 600s;
            proxy_read_timeout 600s;
        }

        # Terraform部署请求特别优化
        location /api/terraform/deploy {
            # CORS头部配置
            add_header 'Access-Control-Allow-Origin' '$http_origin' always;
            add_header 'Access-Control-Allow-Credentials' 'true' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Origin, X-Requested-With, Content-Type, Accept, Authorization' always;
            add_header 'Access-Control-Expose-Headers' 'Content-Length, Content-Range' always;
            
            # OPTIONS处理
            if ($request_method = 'OPTIONS') {
                add_header 'Access-Control-Max-Age' 1728000;
                add_header 'Content-Type' 'text/plain charset=UTF-8';
                add_header 'Content-Length' 0;
                return 204;
            }
            
            proxy_pass http://localhost:8081/api/terraform/deploy;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Origin $http_origin;
            
            # 特别长的超时时间
            proxy_connect_timeout 1800s;
            proxy_send_timeout 1800s;
            proxy_read_timeout 1800s;
        }

        # 分批部署接口专门配置
        location ~* ^/api/terraform/deploy/(init|part|complete) {
            add_header 'Access-Control-Allow-Origin' '$http_origin' always;
            add_header 'Access-Control-Allow-Credentials' 'true' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Origin, X-Requested-With, Content-Type, Accept, Authorization' always;
            add_header 'Access-Control-Expose-Headers' 'Content-Length, Content-Range' always;
            
            if ($request_method = 'OPTIONS') {
                add_header 'Access-Control-Max-Age' 1728000;
                add_header 'Content-Type' 'text/plain charset=UTF-8';
                add_header 'Content-Length' 0;
                return 204;
            }
            
            proxy_pass http://localhost:8081$request_uri;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Origin $http_origin;
            
            # 适中的超时和缓冲区
            proxy_connect_timeout 600s;
            proxy_send_timeout 600s;
            proxy_read_timeout 600s;
            
            client_max_body_size 50M;
            client_body_buffer_size 5M;
        }

        # 普通Terraform API
        location /api/terraform/ {
            # CORS头部配置
            add_header 'Access-Control-Allow-Origin' '$http_origin' always;
            add_header 'Access-Control-Allow-Credentials' 'true' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Origin, X-Requested-With, Content-Type, Accept, Authorization' always;
            add_header 'Access-Control-Expose-Headers' 'Content-Length, Content-Range' always;
            
            # OPTIONS处理
            if ($request_method = 'OPTIONS') {
                add_header 'Access-Control-Max-Age' 1728000;
                add_header 'Content-Type' 'text/plain charset=UTF-8';
                add_header 'Content-Length' 0;
                return 204;
            }
            
            proxy_pass http://localhost:8081/api/terraform/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Origin $http_origin;
            
            # 超时和缓冲区
            proxy_connect_timeout 600s;
            proxy_send_timeout 600s;
            proxy_read_timeout 600s;
            
            client_max_body_size 30M;
        }

        # WebSocket代理
        location /ws/ {
            # WebSocket的CORS头部
            add_header 'Access-Control-Allow-Origin' '$http_origin' always;
            add_header 'Access-Control-Allow-Credentials' 'true' always;
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
            add_header 'Access-Control-Allow-Headers' 'Origin, X-Requested-With, Content-Type, Accept, Authorization' always;
            
            if ($request_method = 'OPTIONS') {
                add_header 'Access-Control-Max-Age' 1728000;
                add_header 'Content-Type' 'text/plain charset=UTF-8';
                add_header 'Content-Length' 0;
                return 204;
            }
            
            proxy_pass http://localhost:8081/ws/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header Origin $http_origin;
            
            # 显著增加WebSocket超时时间
            proxy_connect_timeout 7200s;
            proxy_send_timeout 7200s;
            proxy_read_timeout 7200s;
        }
    }
}
systemctl enable nginx
systemctl start nginx

#安装后端
cd /root/mcdp/backend
pip install -r requirement.txt
部分没安装全的pip install 自行安装

#安装MYSQL数据库
apt update
sudo apt install -y mysql-server
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'yourpassword';
FLUSH PRIVILEGES;


#长期后台运行后端，日志放到/root/backend.log
crontab -e
@reboot /usr/bin/nohup /opt/miniconda3/bin/python /root/mcdp/backend/app.py > /root/mcdp/backend/backend.log 2>&1 &


