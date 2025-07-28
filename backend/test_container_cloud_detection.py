#!/usr/bin/env python3
"""
容器环境云平台检测测试脚本
用于在Docker容器中验证云平台检测功能
"""

import sys
import os
import traceback

def test_container_cloud_detection():
    """在容器环境中测试云平台检测功能"""
    print("=" * 60)
    print("容器环境云平台检测测试")
    print("=" * 60)
    
    # 显示当前工作目录和Python路径
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python路径: {sys.path}")
    print(f"Python版本: {sys.version}")
    
    try:
        # 测试1: 检查prompts目录是否存在
        print("\n1. 检查prompts目录...")
        prompts_dir = os.path.join(os.getcwd(), 'prompts')
        if os.path.exists(prompts_dir):
            print(f"✅ prompts目录存在: {prompts_dir}")
            print(f"   目录内容: {os.listdir(prompts_dir)}")
        else:
            print(f"❌ prompts目录不存在: {prompts_dir}")
            return
        
        # 测试2: 检查cloud_terraform_prompts.py文件是否存在
        print("\n2. 检查cloud_terraform_prompts.py文件...")
        cloud_prompts_file = os.path.join(prompts_dir, 'cloud_terraform_prompts.py')
        if os.path.exists(cloud_prompts_file):
            print(f"✅ cloud_terraform_prompts.py文件存在: {cloud_prompts_file}")
        else:
            print(f"❌ cloud_terraform_prompts.py文件不存在: {cloud_prompts_file}")
            return
        
        # 测试3: 检查__init__.py文件
        print("\n3. 检查__init__.py文件...")
        init_file = os.path.join(prompts_dir, '__init__.py')
        if os.path.exists(init_file):
            print(f"✅ __init__.py文件存在: {init_file}")
            with open(init_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'CloudTerraformPrompts' in content:
                    print("✅ __init__.py文件包含CloudTerraformPrompts导入")
                else:
                    print("❌ __init__.py文件不包含CloudTerraformPrompts导入")
        else:
            print(f"❌ __init__.py文件不存在: {init_file}")
            return
        
        # 测试4: 尝试导入模块
        print("\n4. 尝试导入CloudTerraformPrompts模块...")
        try:
            from prompts.cloud_terraform_prompts import CloudTerraformPrompts
            print("✅ 成功导入CloudTerraformPrompts模块")
        except ImportError as e:
            print(f"❌ 导入CloudTerraformPrompts模块失败: {str(e)}")
            print(f"   错误详情: {traceback.format_exc()}")
            return
        
        # 测试5: 测试云平台检测功能
        print("\n5. 测试云平台检测功能...")
        test_cases = [
            ("@ai  火山云创建一个vpc", "火山云"),
            ("@ai  华为云创建一个ECS", "华为云"),
            ("@ai  阿里云创建一个VPC", "阿里云"),
        ]
        
        for description, expected in test_cases:
            try:
                detected = CloudTerraformPrompts.detect_cloud_from_description(description)
                status = "✅" if detected == expected else "❌"
                print(f"{status} 描述: {description}")
                print(f"   期望: {expected}, 检测到: {detected}")
            except Exception as e:
                print(f"❌ 检测失败: {description}")
                print(f"   错误: {str(e)}")
                print(f"   错误详情: {traceback.format_exc()}")
            print()
        
        print("6. 测试完成")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {str(e)}")
        print(f"   错误详情: {traceback.format_exc()}")

if __name__ == "__main__":
    test_container_cloud_detection() 