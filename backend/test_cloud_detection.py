#!/usr/bin/env python3
"""
云平台检测功能测试脚本
用于验证 CloudTerraformPrompts.detect_cloud_from_description 是否正常工作
"""

import sys
import os

# 添加backend路径到sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_cloud_detection():
    """测试云平台检测功能"""
    print("=" * 60)
    print("测试云平台检测功能")
    print("=" * 60)
    
    try:
        # 测试模块导入
        print("1. 测试模块导入...")
        from prompts.cloud_terraform_prompts import CloudTerraformPrompts
        print("✅ 成功导入 CloudTerraformPrompts 模块")
        
        # 测试云平台检测
        print("\n2. 测试云平台检测...")
        test_cases = [
            ("@ai  火山云创建一个vpc", "火山云"),
            ("@ai  华为云创建一个ECS", "华为云"),
            ("@ai  阿里云创建一个VPC", "阿里云"),
            ("@ai  AWS创建一个EC2", "AWS"),
            ("@ai  Azure创建一个VM", "AZURE"),
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
            print()
        
        print("3. 测试完成")
        
    except ImportError as e:
        print(f"❌ 模块导入失败: {str(e)}")
        print("请检查 prompts/__init__.py 文件是否正确导出了 CloudTerraformPrompts")
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_cloud_detection() 