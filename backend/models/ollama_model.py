from typing import Any, Dict, List, Optional
import subprocess
import json

from messages import OpenAIMessage
from .base_model import BaseModelBackend


class OllamaModel(BaseModelBackend):
    """Ollama model backend implementation for locally deployed models.
    
    This class implements the BaseModelBackend interface for Ollama models.
    
    Args:
        model_type (str): The Ollama model to use (e.g., "llama3", "mistral").
        model_config_dict (Optional[Dict[str, Any]]): Configuration for the model.
        api_key (Optional[str]): Not used for Ollama, but kept for interface consistency.
        url (Optional[str]): Ollama API endpoint URL.
    """
    
    def __init__(
        self,
        model_type: str = "llama3",
        model_config_dict: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
    ):
        super().__init__(model_type, model_config_dict, api_key, url)
        self.api_url = url or "http://ollama.cloudet.cn:11434/api/chat"
        
    def check_model_config(self):
        """Validate the model configuration."""
        valid_params = {
            "temperature", "top_p", "top_k", "num_predict", 
            "stop", "repeat_penalty", "presence_penalty", "frequency_penalty", "max_tokens"
        }
        
        for param in self.model_config_dict:
            if param not in valid_params:
                raise ValueError(f"Unexpected parameter in model config: {param}")
    
    def _convert_to_ollama_messages(self, messages: List[OpenAIMessage]) -> List[Dict[str, Any]]:
        """Convert OpenAI message format to Ollama message format."""
        ollama_messages = []
        
        # 处理不同格式的消息输入
        message_list = messages
        
        # 如果 messages 是元组 (message_list, token_count)
        if isinstance(messages, tuple) and len(messages) > 0:
            message_list = messages[0]
        
        # 确保 message_list 是列表
        if not isinstance(message_list, list):
            message_list = [message_list]
        
        for message in message_list:
            # 处理字符串消息
            if isinstance(message, str):
                ollama_messages.append({"role": "user", "content": message})
                continue
                
            # 处理 BaseMessage 对象
            if hasattr(message, 'role') and hasattr(message, 'content'):
                role = message.role
                content = message.content
                ollama_messages.append({"role": role, "content": content})
                continue
                
            # 处理字典格式消息
            if isinstance(message, dict):
                role = message.get("role")
                content = message.get("content", "")
                
                if role == "user":
                    ollama_messages.append({"role": "user", "content": content})
                elif role == "assistant":
                    ollama_messages.append({"role": "assistant", "content": content})
                elif role == "system":
                    ollama_messages.append({"role": "system", "content": content})
                continue
        
        # 确保至少有一条消息
        if not ollama_messages:
            raise ValueError("No valid messages to process")
            
        return ollama_messages
    
    def generate(
        self,
        messages: List[OpenAIMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate a response from the Ollama model.
        
        Args:
            messages (List[OpenAIMessage]): Message list with the chat history.
            tools (Optional[List[Dict[str, Any]]]): The schema of tools to use.
            **kwargs: Additional parameters for the model.
            
        Returns:
            Dict[str, Any]: The model's response.
        """
        # Preprocess messages
        processed_messages = self.preprocess_messages(messages)
        
        # Convert to Ollama format
        ollama_messages = self._convert_to_ollama_messages(processed_messages)
        
        # Prepare request payload
        payload = {
            "model": self.model_type,
            "messages": ollama_messages,
            "options": {
                "temperature": self.model_config_dict.get("temperature", 0.7),
                "top_p": self.model_config_dict.get("top_p", 0.9),
                "top_k": self.model_config_dict.get("top_k", 40),
                "num_predict": self.model_config_dict.get("num_predict", 8192),  # 增加输出长度限制
            }
        }
        
        # Add stop sequences if provided
        if "stop" in self.model_config_dict:
            payload["options"]["stop"] = self.model_config_dict["stop"]
            
        # Make API request using curl for better compatibility with Ollama
        try:
            # 打印请求负载信息
            print(f"Payload messages count: {len(ollama_messages)}")
            for i, msg in enumerate(ollama_messages):
                print(f"Message {i+1} - Role: {msg.get('role')}, Content length: {len(msg.get('content', ''))}")
            
            # Convert payload to JSON string
            payload_str = json.dumps(payload)
            
            # Use curl to make the request
            cmd = [
                "curl", "-s", "-X", "POST", self.api_url,
                "-H", "Content-Type: application/json",
                "-d", payload_str
            ]
            
            # Execute curl command
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            response_text = result.stdout
            
            # Process streaming JSON response
            full_content = ""
            final_usage = {}
            lines = response_text.strip().split('\n')
            for line in lines:
                if line:
                    try:
                        response_part = json.loads(line)
                        content_part = response_part.get("message", {}).get("content", "")
                        full_content += content_part
                        # Capture usage/eval_count from the last message if available
                        if response_part.get("done", False) and "eval_count" in response_part:
                            final_usage = {"eval_count": response_part.get("eval_count")}
                    except json.JSONDecodeError:
                        # Ignore lines that are not valid JSON
                        print(f"Warning: Skipping invalid JSON line: {line}")
                        continue

            # 打印完整响应长度
            print(f"Full response content length: {len(full_content)}")
            
            # Convert Ollama response to OpenAI-like format for consistency
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": full_content
                        },
                        "finish_reason": "stop" # Assuming stop since we processed the whole stream
                    }
                ],
                "model": self.model_type,
                "usage": final_usage # Use usage from the final chunk if available
            }
        except subprocess.CalledProcessError as e:
            # Handle curl errors
            error_msg = f"Error calling Ollama API: {str(e)}"
            if e.stderr:
                error_msg += f"\nError output: {e.stderr}"
            raise Exception(error_msg)
        except json.JSONDecodeError as e:
            # Handle JSON parsing errors
            error_msg = f"Error parsing Ollama API response: {str(e)}"
            error_msg += f"\nResponse text: {response_text}"
            raise Exception(error_msg)
        except Exception as e:
            # Handle other errors
            error_msg = f"Unexpected error calling Ollama API: {str(e)}"
            raise Exception(error_msg)
