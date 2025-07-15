#!/usr/bin/env python3
"""
Terraform进程清理脚本
用于清理可能卡住的Terraform进程和临时文件
"""

import os
import sys
import subprocess
import shutil
import time
import logging

# 尝试导入psutil，如果失败则使用替代方案
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("警告: 未安装psutil模块，将使用系统命令替代")

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def kill_terraform_processes():
    """杀死所有Terraform相关进程"""
    killed_count = 0
    
    if HAS_PSUTIL:
        # 使用psutil库查找和杀死进程
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                # 检查进程名称或命令行参数中是否包含terraform
                if proc.info['name'] and 'terraform' in proc.info['name'].lower():
                    logger.info(f"发现Terraform进程: PID={proc.info['pid']}, 名称={proc.info['name']}")
                    proc.kill()
                    killed_count += 1
                    logger.info(f"已杀死进程 PID={proc.info['pid']}")
                elif proc.info['cmdline']:
                    cmdline_str = ' '.join(proc.info['cmdline']).lower()
                    if 'terraform' in cmdline_str:
                        logger.info(f"发现Terraform相关进程: PID={proc.info['pid']}, 命令={cmdline_str}")
                        proc.kill()
                        killed_count += 1
                        logger.info(f"已杀死进程 PID={proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # 进程可能已经结束或没有权限访问
                pass
            except Exception as e:
                logger.error(f"处理进程时出错: {str(e)}")
    else:
        # 使用系统命令查找和杀死进程（Windows）
        try:
            # 查找terraform.exe进程
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq terraform.exe'], 
                                  capture_output=True, text=True)
            if 'terraform.exe' in result.stdout:
                logger.info("发现terraform.exe进程，正在终止...")
                kill_result = subprocess.run(['taskkill', '/F', '/IM', 'terraform.exe'], 
                                           capture_output=True, text=True)
                if kill_result.returncode == 0:
                    killed_count += 1
                    logger.info("已成功终止terraform.exe进程")
                else:
                    logger.warning(f"终止terraform.exe进程失败: {kill_result.stderr}")
            else:
                logger.info("没有发现terraform.exe进程")
        except Exception as e:
            logger.error(f"使用系统命令查找进程时出错: {str(e)}")
    
    if killed_count > 0:
        logger.info(f"总共杀死了 {killed_count} 个Terraform相关进程")
        # 等待进程完全结束
        time.sleep(2)
    else:
        logger.info("没有发现运行中的Terraform进程")
    
    return killed_count

def cleanup_terraform_directories():
    """清理Terraform临时目录和状态文件"""
    cleanup_paths = []
    
    # 获取当前脚本所在目录（backend目录）
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 查找需要清理的目录
    query_dir = os.path.join(backend_dir, 'query')
    deployments_dir = os.path.join(backend_dir, 'deployments')
    
    cleanup_paths.extend([query_dir, deployments_dir])
    
    # 添加临时目录中的terraform相关文件
    temp_dirs = ['/tmp', os.environ.get('TEMP', ''), os.environ.get('TMP', '')]
    for temp_dir in temp_dirs:
        if temp_dir and os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                if 'terraform' in item.lower() and os.path.isdir(item_path):
                    cleanup_paths.append(item_path)
    
    cleaned_count = 0
    for path in cleanup_paths:
        if os.path.exists(path):
            try:
                if os.path.isdir(path):
                    # 清理目录中的.terraform文件夹和状态文件
                    for root, dirs, files in os.walk(path):
                        # 删除.terraform目录
                        if '.terraform' in dirs:
                            terraform_dir = os.path.join(root, '.terraform')
                            logger.info(f"删除Terraform目录: {terraform_dir}")
                            shutil.rmtree(terraform_dir, ignore_errors=True)
                            cleaned_count += 1
                        
                        # 删除状态文件
                        for file in files:
                            if file.endswith(('.tfstate', '.tfstate.backup', '.terraform.lock.hcl')):
                                file_path = os.path.join(root, file)
                                logger.info(f"删除Terraform状态文件: {file_path}")
                                try:
                                    os.remove(file_path)
                                    cleaned_count += 1
                                except OSError as e:
                                    logger.warning(f"无法删除文件 {file_path}: {str(e)}")
                else:
                    # 删除单个文件
                    logger.info(f"删除文件: {path}")
                    os.remove(path)
                    cleaned_count += 1
            except Exception as e:
                logger.error(f"清理路径 {path} 时出错: {str(e)}")
    
    if cleaned_count > 0:
        logger.info(f"总共清理了 {cleaned_count} 个Terraform相关文件/目录")
    else:
        logger.info("没有发现需要清理的Terraform文件")
    
    return cleaned_count

def check_terraform_locks():
    """检查并清理可能的Terraform锁文件"""
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    lock_files_found = []
    
    # 搜索.terraform.lock.hcl文件
    for root, dirs, files in os.walk(backend_dir):
        for file in files:
            if file == '.terraform.lock.hcl':
                lock_files_found.append(os.path.join(root, file))
    
    if lock_files_found:
        logger.info(f"发现 {len(lock_files_found)} 个Terraform锁文件:")
        for lock_file in lock_files_found:
            logger.info(f"  - {lock_file}")
            try:
                os.remove(lock_file)
                logger.info(f"已删除锁文件: {lock_file}")
            except OSError as e:
                logger.warning(f"无法删除锁文件 {lock_file}: {str(e)}")
    else:
        logger.info("没有发现Terraform锁文件")
    
    return len(lock_files_found)

def main():
    """主函数"""
    logger.info("开始清理Terraform进程和文件...")
    
    # 1. 杀死Terraform进程
    logger.info("步骤1: 清理Terraform进程")
    processes_killed = kill_terraform_processes()
    
    # 2. 清理Terraform目录和文件
    logger.info("步骤2: 清理Terraform目录和状态文件")
    files_cleaned = cleanup_terraform_directories()
    
    # 3. 检查并清理锁文件
    logger.info("步骤3: 清理Terraform锁文件")
    locks_cleaned = check_terraform_locks()
    
    # 总结
    logger.info("清理完成!")
    logger.info(f"清理总结: 进程={processes_killed}, 文件={files_cleaned}, 锁文件={locks_cleaned}")
    
    if processes_killed > 0 or files_cleaned > 0 or locks_cleaned > 0:
        logger.info("建议重启应用程序以确保完全清理")
    else:
        logger.info("系统状态良好，无需额外操作")

if __name__ == "__main__":
    main() 