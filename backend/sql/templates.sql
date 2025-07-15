-- 创建模板表
CREATE TABLE IF NOT EXISTS templates (
    id VARCHAR(36) PRIMARY KEY,
    user_id INT NOT NULL,
    username VARCHAR(100) NOT NULL,
    template_name VARCHAR(100) NOT NULL,
    description TEXT,
    topology_image VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 创建资源部署状态跟踪表
CREATE TABLE IF NOT EXISTS deployment_resources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    deploy_id VARCHAR(20) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_name VARCHAR(100) NOT NULL,
    status ENUM('pending', 'in_progress', 'completed', 'failed') DEFAULT 'pending',
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX (deploy_id),
    FOREIGN KEY (deploy_id) REFERENCES deployments(deployid) ON DELETE CASCADE
);

-- 更新deployments表，添加template_id字段
ALTER TABLE deployments 
ADD COLUMN template_id VARCHAR(36) NULL,
ADD COLUMN deploy_progress INT DEFAULT 0,
ADD INDEX (template_id); 