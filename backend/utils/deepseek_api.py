import os
import json
import requests
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 从环境变量获取API密钥，如果不存在则使用硬编码值
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'yourdeepseekapikey')
DEEPSEEK_API_URL = os.environ.get('DEEPSEEK_API_URL', 'https://api.deepseek.com/v1/chat/completions')

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
