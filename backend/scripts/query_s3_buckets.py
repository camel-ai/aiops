#!/usr/bin/env python3
"""
S3存储桶查询脚本
用于查询AWS S3存储桶信息，作为Terraform查询的补充工具
"""

import boto3
import json
import sys
import os
from datetime import datetime
from botocore.exceptions import NoCredentialsError, ClientError

def get_s3_buckets(aws_access_key_id=None, aws_secret_access_key=None, region_name='us-east-1'):
    """
    获取所有S3存储桶列表
    
    Args:
        aws_access_key_id: AWS访问密钥ID
        aws_secret_access_key: AWS秘密访问密钥
        region_name: AWS区域（S3是全局服务，但需要指定区域创建客户端）
        
    Returns:
        list: 存储桶信息列表
    """
    try:
        # 创建S3客户端
        if aws_access_key_id and aws_secret_access_key:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region_name
            )
        else:
            # 使用默认凭证（环境变量、配置文件等）
            s3_client = boto3.client('s3', region_name=region_name)
        
        # 获取存储桶列表
        response = s3_client.list_buckets()
        buckets = []
        
        for bucket in response['Buckets']:
            bucket_name = bucket['Name']
            creation_date = bucket['CreationDate'].isoformat()
            
            try:
                # 获取存储桶位置
                location_response = s3_client.get_bucket_location(Bucket=bucket_name)
                bucket_region = location_response.get('LocationConstraint') or 'us-east-1'
                
                # 获取存储桶标签（如果有）
                try:
                    tags_response = s3_client.get_bucket_tagging(Bucket=bucket_name)
                    tags = {tag['Key']: tag['Value'] for tag in tags_response.get('TagSet', [])}
                except ClientError:
                    tags = {}
                
                # 获取存储桶大小和对象数量（注意：这可能需要较长时间）
                bucket_info = {
                    'name': bucket_name,
                    'creation_date': creation_date,
                    'region': bucket_region,
                    'tags': tags
                }
                
                # 可选：获取存储桶策略和ACL信息
                try:
                    # 获取存储桶ACL
                    acl_response = s3_client.get_bucket_acl(Bucket=bucket_name)
                    bucket_info['owner'] = acl_response.get('Owner', {}).get('DisplayName', 'Unknown')
                except ClientError:
                    bucket_info['owner'] = 'Unknown'
                
                buckets.append(bucket_info)
                
            except ClientError as e:
                # 如果无法访问某个存储桶的详细信息，至少包含基本信息
                print(f"警告: 无法获取存储桶 {bucket_name} 的详细信息: {e}", file=sys.stderr)
                buckets.append({
                    'name': bucket_name,
                    'creation_date': creation_date,
                    'region': 'unknown',
                    'tags': {},
                    'owner': 'unknown',
                    'error': str(e)
                })
        
        return buckets
        
    except NoCredentialsError:
        print("错误: 未找到AWS凭证。请确保配置了AWS访问密钥。", file=sys.stderr)
        return None
    except ClientError as e:
        print(f"错误: AWS客户端错误: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"错误: 查询S3存储桶时发生未知错误: {e}", file=sys.stderr)
        return None

def format_output(buckets, output_format='table'):
    """
    格式化输出存储桶信息
    
    Args:
        buckets: 存储桶信息列表
        output_format: 输出格式 ('table', 'json', 'csv')
    """
    if not buckets:
        print("未找到S3存储桶或查询失败")
        return
    
    if output_format == 'json':
        print(json.dumps(buckets, indent=2, ensure_ascii=False))
    elif output_format == 'csv':
        print("存储桶名称,创建时间,区域,所有者,标签数量")
        for bucket in buckets:
            tags_count = len(bucket.get('tags', {}))
            print(f"{bucket['name']},{bucket['creation_date']},{bucket['region']},{bucket.get('owner', 'unknown')},{tags_count}")
    else:  # table格式
        print("=" * 80)
        print(f"{'存储桶名称':<30} {'区域':<15} {'创建时间':<20} {'所有者':<15}")
        print("=" * 80)
        
        for bucket in buckets:
            name = bucket['name'][:28] + '..' if len(bucket['name']) > 30 else bucket['name']
            region = bucket['region'][:13] + '..' if len(bucket['region']) > 15 else bucket['region']
            creation_date = bucket['creation_date'][:19]  # 移除毫秒部分
            owner = bucket.get('owner', 'unknown')[:13] + '..' if len(bucket.get('owner', 'unknown')) > 15 else bucket.get('owner', 'unknown')
            
            print(f"{name:<30} {region:<15} {creation_date:<20} {owner:<15}")
            
            # 显示标签信息（如果有）
            if bucket.get('tags'):
                print(f"    标签: {', '.join([f'{k}={v}' for k, v in bucket['tags'].items()])}")
            
            if bucket.get('error'):
                print(f"    错误: {bucket['error']}")
        
        print("=" * 80)
        print(f"总计: {len(buckets)} 个存储桶")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='查询AWS S3存储桶信息')
    parser.add_argument('--access-key', help='AWS访问密钥ID')
    parser.add_argument('--secret-key', help='AWS秘密访问密钥')
    parser.add_argument('--region', default='us-east-1', help='AWS区域 (默认: us-east-1)')
    parser.add_argument('--format', choices=['table', 'json', 'csv'], default='table', help='输出格式')
    parser.add_argument('--save', help='保存结果到文件')
    
    args = parser.parse_args()
    
    print(f"正在查询S3存储桶...")
    print(f"区域: {args.region}")
    print("=" * 50)
    
    # 查询存储桶
    buckets = get_s3_buckets(
        aws_access_key_id=args.access_key,
        aws_secret_access_key=args.secret_key,
        region_name=args.region
    )
    
    if buckets is not None:
        # 格式化输出
        if args.save:
            # 保存到文件
            with open(args.save, 'w', encoding='utf-8') as f:
                if args.format == 'json':
                    json.dump(buckets, f, indent=2, ensure_ascii=False)
                else:
                    # 重定向标准输出到文件
                    import contextlib
                    with contextlib.redirect_stdout(f):
                        format_output(buckets, args.format)
            print(f"结果已保存到: {args.save}")
        else:
            format_output(buckets, args.format)
    else:
        print("查询失败，请检查AWS凭证和网络连接")
        sys.exit(1)

if __name__ == "__main__":
    main() 