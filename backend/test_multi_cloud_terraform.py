#!/usr/bin/env python3
"""
多云Terraform代码生成测试脚本
测试CloudTerraformPrompts类的功能
"""

import sys
import os

# 添加backend路径到sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompts.cloud_terraform_prompts import CloudTerraformPrompts

def test_cloud_detection():
    """测试云提供商检测功能"""
    print("=" * 60)
    print("测试云提供商检测功能")
    print("=" * 60)
    
    test_cases = [
        ("在AWS上部署一个VPC和EC2实例", "AWS"),
        ("在Azure上创建虚拟网络和虚拟机", "AZURE"),
        ("在阿里云上部署ECS和VPC", "阿里云"),
        ("使用华为云创建计算实例", "华为云"),
        ("在腾讯云上搭建基础设施", "腾讯云"),
        ("使用百度云部署应用", "百度云"),
        ("在火山云上创建ECS实例", "火山云"),
        ("在AWS中国区域部署资源", "AWS(CHINA)"),
        ("创建一个基础的网络架构", "AWS"),  # 默认情况
    ]
    
    for description, expected in test_cases:
        detected = CloudTerraformPrompts.detect_cloud_from_description(description)
        status = "✅" if detected == expected else "❌"
        print(f"{status} 描述: {description}")
        print(f"   期望: {expected}, 检测到: {detected}")
        print()

def test_cloud_specific_prompts():
    """测试不同云提供商的专用prompts"""
    print("=" * 60)
    print("测试云提供商专用prompts")
    print("=" * 60)
    
    clouds = ["AWS", "AZURE", "阿里云", "华为云", "腾讯云", "百度云", "火山云", "AWS(CHINA)", "AZURE(CHINA)"]
    
    for cloud in clouds:
        print(f"\n🔵 测试 {cloud} 的prompt:")
        prompt = CloudTerraformPrompts.get_cloud_specific_prompt(cloud)
        
        # 检查prompt是否包含云特定的关键词
        cloud_keywords = {
            "AWS": ["aws", "hashicorp/aws"],
            "AZURE": ["azurerm", "azurerm_"],
            "阿里云": ["alicloud", "aliyun/alicloud"],
            "华为云": ["huaweicloud", "huaweicloud_"],
            "腾讯云": ["tencentcloud", "tencentcloud_"],
            "百度云": ["baiducloud", "baidubce/baiducloud"],
            "火山云": ["volcengine", "volcengine_"],
            "AWS(CHINA)": ["aws", "cn-north-1"],
            "AZURE(CHINA)": ["azurerm", "chinanorth"]
        }
        
        keywords = cloud_keywords.get(cloud, [])
        found_keywords = []
        
        for keyword in keywords:
            if keyword.lower() in prompt.lower():
                found_keywords.append(keyword)
        
        if found_keywords:
            print(f"   ✅ 找到云特定关键词: {', '.join(found_keywords)}")
        else:
            print(f"   ❌ 未找到预期的云特定关键词: {', '.join(keywords)}")
        
        # 显示prompt的前200个字符
        preview = prompt[:200].replace('\n', ' ').strip()
        print(f"   预览: {preview}...")

def test_user_prompt_template():
    """测试用户prompt模板"""
    print("=" * 60)
    print("测试用户prompt模板")
    print("=" * 60)
    
    template = CloudTerraformPrompts.get_user_prompt_template()
    
    # 测试模板格式化
    test_data = {
        "user_description": "在AWS上创建一个VPC和EC2实例",
        "mermaid_code": "graph TD\n    A[VPC] --> B[EC2]",
        "cloud_provider": "AWS"
    }
    
    formatted_prompt = template.format(**test_data)
    
    print("✅ 用户prompt模板格式化成功")
    print(f"包含描述: {'✅' if test_data['user_description'] in formatted_prompt else '❌'}")
    print(f"包含Mermaid: {'✅' if test_data['mermaid_code'] in formatted_prompt else '❌'}")
    print(f"包含云提供商: {'✅' if test_data['cloud_provider'] in formatted_prompt else '❌'}")
    
    print("\n格式化后的prompt预览:")
    print("-" * 40)
    print(formatted_prompt[:300] + "...")

def main():
    """主测试函数"""
    print("🚀 开始测试多云Terraform代码生成功能")
    print()
    
    try:
        test_cloud_detection()
        test_cloud_specific_prompts()
        test_user_prompt_template()
        
        print("=" * 60)
        print("🎉 所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 