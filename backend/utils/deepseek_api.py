import os
import json
import requests
import logging
import time

# 配置日志
logger = logging.getLogger(__name__)

# 从环境变量获取API密钥
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = os.environ.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')

def query_deepseek_stream(user_query, system_prompt=None, is_command=False):
    """
    向DeepSeek API发送流式查询并生成SSE响应
    
    Args:
        user_query (str): 用户查询内容
        system_prompt (str, optional): 系统提示词
        is_command (bool, optional): 是否是命令模式
        
    Yields:
        str: SSE格式的数据流
    """
    try:
        # 检查API密钥是否设置
        if not DEEPSEEK_API_KEY:
            logger.error("DeepSeek API密钥未设置，请在环境变量中设置DEEPSEEK_API_KEY")
            yield f"data: {json.dumps({'error': 'DeepSeek API密钥未设置，请检查环境配置', 'done': True})}\n\n"
            return
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        # 添加系统提示
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加用户查询
        messages.append({"role": "user", "content": user_query})
            
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4000,
            "stream": True  # 启用流式输出
        }
        
        logger.info(f"发送流式查询到DeepSeek API: {user_query[:50]}...")
        
        # 使用流式请求
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, stream=True)
        
        # 检查响应状态
        if response.status_code != 200:
            logger.error(f"DeepSeek API错误: {response.status_code} - {response.text}")
            yield f"data: {json.dumps({'error': f'API错误: {response.status_code}', 'done': True})}\n\n"
            return
        
        full_content = ""
        chunk_count = 0
        
        # 处理流式响应
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                
                # 跳过非数据行
                if not line.startswith('data: '):
                    continue
                
                # 提取数据部分
                data_str = line[6:]  # 移除 "data: " 前缀
                
                # 检查是否为结束标志
                if data_str.strip() == '[DONE]':
                    break
                
                try:
                    # 解析JSON数据
                    data = json.loads(data_str)
                    
                    # 提取内容
                    if 'choices' in data and len(data['choices']) > 0:
                        choice = data['choices'][0]
                        
                        # 获取增量内容
                        if 'delta' in choice and 'content' in choice['delta']:
                            content = choice['delta']['content']
                            full_content += content
                            chunk_count += 1
                            
                            # 发送增量内容
                            if chunk_count <= 5:  # 只记录前5个详细日志
                                logger.info(f"发送增量内容 {chunk_count}: {repr(content)}")
                            elif chunk_count % 100 == 0:  # 每100个记录一次
                                logger.info(f"已发送 {chunk_count} 个增量内容")
                            
                            yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"
                            
                            # 减少延迟时间
                            time.sleep(0.001)  # 1毫秒延迟
                        
                        # 检查是否完成
                        if choice.get('finish_reason') == 'stop':
                            break
                            
                except json.JSONDecodeError as e:
                    logger.warning(f"无法解析流式响应数据: {data_str}, 错误: {e}")
                    continue
        
        logger.info(f"DeepSeek流式处理完成，共发送 {chunk_count} 个增量内容")
        
        # 处理命令模式的JSON提取
        json_content = None
        if is_command and full_content:
            try:
                # 寻找JSON代码块
                import re
                json_matches = re.findall(r'```(?:json)?\s*([\s\S]*?)\s*```', full_content)
                
                if json_matches:
                    json_content = json.loads(json_matches[0])
                    logger.info(f"成功从流式回复中提取JSON: {str(json_content)[:100]}...")
                else:
                    # 尝试直接解析整个回复内容
                    json_content = json.loads(full_content)
                    logger.info("成功直接解析流式回复为JSON")
            except Exception as e:
                logger.info(f"流式回复内容不是有效的JSON或无法提取JSON: {str(e)}")
        
        # 发送最终完成信号
        final_data = {
            'done': True,
            'full_content': full_content,
            'is_command': is_command
        }
        
        if json_content:
            final_data['json_content'] = json_content
            final_data['has_json'] = True
        
        yield f"data: {json.dumps(final_data)}\n\n"
        
    except Exception as e:
        logger.error(f"调用DeepSeek流式API时出错: {str(e)}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

def query_deepseek(user_query, system_prompt=None, is_command=False):
    """
    向DeepSeek API发送查询并返回结果
    
    Args:
        user_query (str): 用户查询内容
        system_prompt (str, optional): 系统提示词
        is_command (bool, optional): 是否是命令模式，如果是则尝试提取JSON
        
    Returns:
        dict: API响应的JSON数据
    """
    try:
        # 检查API密钥是否设置
        if not DEEPSEEK_API_KEY:
            logger.error("DeepSeek API密钥未设置，请在环境变量中设置DEEPSEEK_API_KEY")
            return {"error": "DeepSeek API密钥未设置，请检查环境配置", "content": None}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        # 添加系统提示
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加用户查询
        messages.append({"role": "user", "content": user_query})
            
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        logger.info(f"发送查询到DeepSeek API: {user_query[:50]}...")
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
        
        # 检查响应状态
        if response.status_code != 200:
            logger.error(f"DeepSeek API错误: {response.status_code} - {response.text}")
            return {"error": f"API错误: {response.status_code}", "content": None}
        
        response_data = response.json()
        logger.info(f"收到DeepSeek API响应: {str(response_data)[:100]}...")
        
        # 提取回复内容
        content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # 初始化json_content为None
        json_content = None
        
        # 只有当is_command为True时才尝试提取JSON
        if is_command:
            try:
                # 寻找JSON代码块
                import re
                json_matches = re.findall(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
                
                if json_matches:
                    # 尝试解析第一个匹配的JSON
                    json_content = json.loads(json_matches[0])
                    logger.info(f"成功从回复中提取JSON: {str(json_content)[:100]}...")
                else:
                    # 尝试直接解析整个回复内容
                    json_content = json.loads(content)
                    logger.info("成功直接解析回复为JSON")
            except Exception as e:
                logger.info(f"回复内容不是有效的JSON或无法提取JSON: {str(e)}")
        else:
            logger.info("非命令模式请求，不尝试提取JSON")
        
        return {
            "content": content,
            "json_content": json_content
        }
    
    except Exception as e:
        logger.error(f"调用DeepSeek API时出错: {str(e)}", exc_info=True)
        return {"error": str(e), "content": None} 