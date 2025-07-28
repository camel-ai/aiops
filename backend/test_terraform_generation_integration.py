#!/usr/bin/env python3
"""
Terraform代码生成集成测试
模拟实际的AI生成流程，测试不同云提供商的Terraform代码生成
"""

import sys
import os

# 添加backend路径到sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from prompts.cloud_terraform_prompts import CloudTerraformPrompts

def simulate_terraform_generation(user_description: str, mermaid_code: str, expected_cloud: str = None):
    """
    模拟Terraform代码生成过程
    
    Args:
        user_description: 用户描述
        mermaid_code: Mermaid图表代码
        expected_cloud: 期望的云提供商
    
    Returns:
        dict: 包含生成结果的字典
    """
    print(f"\n🔵 模拟生成 - 用户描述: {user_description}")
    print(f"📊 Mermaid代码: {mermaid_code}")
    
    # 1. 检测云提供商
    detected_cloud = CloudTerraformPrompts.detect_cloud_from_description(user_description)
    print(f"🔍 检测到的云提供商: {detected_cloud}")
    
    if expected_cloud:
        status = "✅" if detected_cloud == expected_cloud else "❌"
        print(f"{status} 期望: {expected_cloud}, 实际: {detected_cloud}")
    
    # 2. 生成系统prompt
    system_prompt = CloudTerraformPrompts.get_cloud_specific_prompt(detected_cloud, user_description)
    print(f"📝 系统prompt长度: {len(system_prompt)} 字符")
    
    # 3. 生成用户prompt
    user_prompt_template = CloudTerraformPrompts.get_user_prompt_template()
    user_prompt = user_prompt_template.format(
        user_description=user_description,
        mermaid_code=mermaid_code,
        cloud_provider=detected_cloud
    )
    print(f"📝 用户prompt长度: {len(user_prompt)} 字符")
    
    # 4. 分析prompt内容
    analysis = analyze_prompt_content(system_prompt, detected_cloud)
    
    return {
        "detected_cloud": detected_cloud,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "analysis": analysis,
        "success": detected_cloud == expected_cloud if expected_cloud else True
    }

def analyze_prompt_content(prompt: str, cloud_provider: str) -> dict:
    """分析prompt内容，检查是否包含云特定的关键信息"""
    prompt_lower = prompt.lower()
    
    # 定义每个云提供商应该包含的关键词
    required_keywords = {
        "AWS": ["aws", "provider \"aws\"", "hashicorp/aws"],
        "AZURE": ["azurerm", "provider \"azurerm\"", "hashicorp/azurerm"],
        "阿里云": ["alicloud", "provider \"alicloud\"", "aliyun/alicloud"],
        "华为云": ["huaweicloud", "provider \"huaweicloud\"", "huaweicloud/huaweicloud"],
        "腾讯云": ["tencentcloud", "provider \"tencentcloud\"", "tencentcloudstack/tencentcloud"],
        "百度云": ["baiducloud", "provider \"baiducloud\"", "baidubce/baiducloud"],
        "火山云": ["volcengine", "provider \"volcengine\"", "volcengine/volcengine"],
        "AWS(CHINA)": ["aws", "provider \"aws\"", "cn-north-1", "cn-northwest-1"],
        "AZURE(CHINA)": ["azurerm", "provider \"azurerm\"", "chinanorth", "chinaeast"]
    }
    
    keywords = required_keywords.get(cloud_provider, [])
    found_keywords = []
    missing_keywords = []
    
    for keyword in keywords:
        if keyword in prompt_lower:
            found_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)
    
    # 检查是否包含资源命名规范
    resource_patterns = {
        "AWS": ["aws_vpc", "aws_instance", "aws_s3_bucket"],
        "AZURE": ["azurerm_virtual_network", "azurerm_virtual_machine", "azurerm_storage_account"],
        "阿里云": ["alicloud_vpc", "alicloud_instance", "alicloud_oss_bucket"],
        "华为云": ["huaweicloud_vpc", "huaweicloud_compute_instance", "huaweicloud_obs_bucket"],
        "腾讯云": ["tencentcloud_vpc", "tencentcloud_instance", "tencentcloud_cos_bucket"],
        "百度云": ["baiducloud_vpc", "baiducloud_instance", "baiducloud_bos_bucket"],
        "火山云": ["volcengine_vpc", "volcengine_ecs_instance", "volcengine_tos_bucket"],
        "AWS(CHINA)": ["aws_vpc", "aws_instance", "aws_s3_bucket"],
        "AZURE(CHINA)": ["azurerm_virtual_network", "azurerm_virtual_machine", "azurerm_storage_account"]
    }
    
    resource_keywords = resource_patterns.get(cloud_provider, [])
    found_resources = []
    
    for resource in resource_keywords:
        if resource in prompt_lower:
            found_resources.append(resource)
    
    return {
        "found_keywords": found_keywords,
        "missing_keywords": missing_keywords,
        "found_resources": found_resources,
        "keyword_coverage": len(found_keywords) / len(keywords) if keywords else 0,
        "resource_coverage": len(found_resources) / len(resource_keywords) if resource_keywords else 0
    }

def test_cloud_specific_scenarios():
    """测试不同云提供商的具体场景"""
    print("=" * 80)
    print("🧪 测试云提供商特定场景的Terraform代码生成")
    print("=" * 80)
    
    test_scenarios = [
        {
            "description": "在AWS上创建一个VPC、子网和EC2实例",
            "mermaid": "graph TD\n    A[VPC] --> B[Subnet]\n    B --> C[EC2 Instance]",
            "expected_cloud": "AWS"
        },
        {
            "description": "在Azure上部署虚拟网络、子网和虚拟机",
            "mermaid": "graph TD\n    A[Virtual Network] --> B[Subnet]\n    B --> C[Virtual Machine]",
            "expected_cloud": "AZURE"
        },
        {
            "description": "在阿里云上创建VPC、交换机和ECS实例",
            "mermaid": "graph TD\n    A[VPC] --> B[VSwitch]\n    B --> C[ECS Instance]",
            "expected_cloud": "阿里云"
        },
        {
            "description": "在华为云上部署VPC、子网和弹性云服务器",
            "mermaid": "graph TD\n    A[VPC] --> B[Subnet]\n    B --> C[ECS]",
            "expected_cloud": "华为云"
        },
        {
            "description": "在腾讯云上创建私有网络、子网和云服务器",
            "mermaid": "graph TD\n    A[VPC] --> B[Subnet]\n    B --> C[CVM]",
            "expected_cloud": "腾讯云"
        },
        {
            "description": "在百度云上部署VPC、子网和云服务器",
            "mermaid": "graph TD\n    A[VPC] --> B[Subnet]\n    B --> C[BCC]",
            "expected_cloud": "百度云"
        },
        {
            "description": "在火山云上创建VPC、子网和ECS实例",
            "mermaid": "graph TD\n    A[VPC] --> B[Subnet]\n    B --> C[ECS Instance]",
            "expected_cloud": "火山云"
        },
        {
            "description": "在AWS中国区域部署VPC和EC2",
            "mermaid": "graph TD\n    A[VPC] --> B[EC2]",
            "expected_cloud": "AWS(CHINA)"
        }
    ]
    
    results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n--- 场景 {i} ---")
        result = simulate_terraform_generation(
            scenario["description"],
            scenario["mermaid"],
            scenario["expected_cloud"]
        )
        results.append(result)
        
        # 打印分析结果
        analysis = result["analysis"]
        print(f"🎯 关键词覆盖率: {analysis['keyword_coverage']:.1%}")
        print(f"🎯 资源覆盖率: {analysis['resource_coverage']:.1%}")
        print(f"✅ 找到关键词: {', '.join(analysis['found_keywords'][:3])}{'...' if len(analysis['found_keywords']) > 3 else ''}")
        print(f"✅ 找到资源: {', '.join(analysis['found_resources'][:3])}{'...' if len(analysis['found_resources']) > 3 else ''}")
        
        if analysis['missing_keywords']:
            print(f"❌ 缺失关键词: {', '.join(analysis['missing_keywords'][:3])}{'...' if len(analysis['missing_keywords']) > 3 else ''}")
    
    return results

def generate_summary_report(results):
    """生成测试总结报告"""
    print("\n" + "=" * 80)
    print("📊 测试总结报告")
    print("=" * 80)
    
    total_tests = len(results)
    successful_detections = sum(1 for r in results if r["success"])
    
    print(f"总测试数: {total_tests}")
    print(f"成功检测: {successful_detections}")
    print(f"检测准确率: {successful_detections/total_tests:.1%}")
    
    # 计算平均覆盖率
    avg_keyword_coverage = sum(r["analysis"]["keyword_coverage"] for r in results) / total_tests
    avg_resource_coverage = sum(r["analysis"]["resource_coverage"] for r in results) / total_tests
    
    print(f"平均关键词覆盖率: {avg_keyword_coverage:.1%}")
    print(f"平均资源覆盖率: {avg_resource_coverage:.1%}")
    
    # 按云提供商统计
    cloud_stats = {}
    for result in results:
        cloud = result["detected_cloud"]
        if cloud not in cloud_stats:
            cloud_stats[cloud] = {"count": 0, "keyword_coverage": 0, "resource_coverage": 0}
        
        cloud_stats[cloud]["count"] += 1
        cloud_stats[cloud]["keyword_coverage"] += result["analysis"]["keyword_coverage"]
        cloud_stats[cloud]["resource_coverage"] += result["analysis"]["resource_coverage"]
    
    print(f"\n📈 各云提供商统计:")
    for cloud, stats in cloud_stats.items():
        count = stats["count"]
        avg_kw = stats["keyword_coverage"] / count
        avg_res = stats["resource_coverage"] / count
        print(f"  {cloud}: 测试{count}次, 关键词覆盖{avg_kw:.1%}, 资源覆盖{avg_res:.1%}")

def main():
    """主测试函数"""
    print("🚀 开始Terraform代码生成集成测试")
    
    try:
        # 运行云特定场景测试
        results = test_cloud_specific_scenarios()
        
        # 生成总结报告
        generate_summary_report(results)
        
        print("\n🎉 集成测试完成！")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 