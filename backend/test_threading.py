import threading
import time
import sys
import os

# 添加当前目录到路径，以便导入本地模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.aideployment_model import AIDeploymentModel
from datetime import datetime

def test_threading():
    """测试线程功能"""
    print("开始测试线程功能")
    
    def thread_function(name):
        print(f"线程 {name} 开始运行")
        time.sleep(2)
        print(f"线程 {name} 完成")
    
    # 创建一个新线程
    t = threading.Thread(target=thread_function, args=("测试线程",))
    t.start()
    
    print("主线程继续执行")
    t.join()
    print("测试线程已完成")

def test_deployment_model():
    """测试AIDeployment模型"""
    print("开始测试AIDeployment模型")
    
    # 创建模型实例
    model = AIDeploymentModel()
    
    # 创建测试数据
    deploy_id = f"TEST_{int(time.time())}"
    test_data = {
        'id': deploy_id,
        'user_id': 1,
        'username': 'test_user',
        'name': 'Test Deployment',
        'description': 'This is a test deployment',
        'status': 'pending',
        'terraform_code': 'provider "aws" {}',
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # 尝试创建记录
    success = model.create_deployment(test_data)
    print(f"创建部署记录结果: {'成功' if success else '失败'}")
    
    # 获取创建的记录
    deploy = model.get_deployment(deploy_id)
    print(f"获取部署记录: {deploy}")
    
    # 更新状态
    if deploy:
        success = model.update_deployment_status(deploy_id, 'completed')
        print(f"更新部署状态结果: {'成功' if success else '失败'}")
        
        # 重新获取更新后的记录
        updated_deploy = model.get_deployment(deploy_id)
        print(f"更新后的部署记录: {updated_deploy}")
    
    print("AIDeployment模型测试完成")

if __name__ == "__main__":
    # 测试线程模块
    test_threading()
    
    # 测试部署模型
    test_deployment_model() 