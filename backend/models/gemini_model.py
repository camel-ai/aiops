from typing import Any, Dict, List, Optional

import requests

from messages import OpenAIMessage
from .base_model import BaseModelBackend


class GeminiModel(BaseModelBackend):
    """Google Gemini model backend implementation.
    
    This class implements the BaseModelBackend interface for Google Gemini models.
    
    Args:
        model_type (str): The Gemini model to use (e.g., "gemini-pro", "gemini-ultra").
        model_config_dict (Optional[Dict[str, Any]]): Configuration for the model.
        api_key (Optional[str]): Google API key.
        url (Optional[str]): Custom API endpoint URL.
    """
    
    def __init__(
        self,
        model_type: str = "gemini-pro",
        model_config_dict: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
    ):
        super().__init__(model_type, model_config_dict, api_key, url)
        self.api_url = url or f"https://generativelanguage.googleapis.com/v1/models/{model_type}:generateContent"
        
    def check_model_config(self):
        """Validate the model configuration."""
        valid_params = {
            "temperature", "top_p", "top_k", "max_output_tokens", 
            "stop_sequences", "candidate_count", "safety_settings"
        }
        
        for param in self.model_config_dict:
            if param not in valid_params:
                raise ValueError(f"Unexpected parameter in model config: {param}")
    
    def _convert_to_gemini_messages(self, messages: List[OpenAIMessage]) -> List[Dict[str, Any]]:
        """Convert OpenAI message format to Gemini message format."""
        gemini_messages = []
        
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            
            if role == "user":
                gemini_messages.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                gemini_messages.append({"role": "model", "parts": [{"text": content}]})
            elif role == "system":
                # Gemini handles system messages differently, we'll prepend to the first user message
                if gemini_messages and gemini_messages[0]["role"] == "user":
                    gemini_messages[0]["parts"][0]["text"] = f"System: {content}\n\nUser: {gemini_messages[0]['parts'][0]['text']}"
                else:
                    gemini_messages.append({"role": "user", "parts": [{"text": f"System: {content}"}]})
        
        return gemini_messages
    
    def generate(
        self,
        messages: List[OpenAIMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate a response from the Gemini model.
        
        Args:
            messages (List[OpenAIMessage]): Message list with the chat history.
            tools (Optional[List[Dict[str, Any]]]): The schema of tools to use.
            **kwargs: Additional parameters for the model.
            
        Returns:
            Dict[str, Any]: The model's response.
        """
        # Preprocess messages
        processed_messages = self.preprocess_messages(messages)
        
        # Convert to Gemini format
        gemini_messages = self._convert_to_gemini_messages(processed_messages)
        
        # Prepare request payload
        payload = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": self.model_config_dict.get("temperature", 0.7),
                "topP": self.model_config_dict.get("top_p", 0.95),
                "topK": self.model_config_dict.get("top_k", 40),
                "maxOutputTokens": self.model_config_dict.get("max_output_tokens", 2048),
                "stopSequences": self.model_config_dict.get("stop_sequences", []),
            }
        }
        
        # Add tools/functions if provided (Gemini calls them "tools")
        if tools:
            payload["tools"] = {"functionDeclarations": tools}
            
        # Set up headers
        headers = {
            "Content-Type": "application/json"
        }
        
        # Add API key as query parameter
        params = {"key": self._api_key}
        
        # Make API request
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            # Convert Gemini response to OpenAI-like format for consistency
            gemini_response = response.json()
            
            # Extract the text content from the response
            content = ""
            if "candidates" in gemini_response and gemini_response["candidates"]:
                if "content" in gemini_response["candidates"][0]:
                    if "parts" in gemini_response["candidates"][0]["content"]:
                        for part in gemini_response["candidates"][0]["content"]["parts"]:
                            if "text" in part:
                                content += part["text"]
            
            # Check for function calls
            function_call = None
            if "functionCall" in gemini_response.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0]:
                function_data = gemini_response["candidates"][0]["content"]["parts"][0]["functionCall"]
                function_call = {
                    "name": function_data.get("name", ""),
                    "arguments": function_data.get("arguments", {})
                }
            
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": content,
                            "function_call": function_call
                        },
                        "finish_reason": "stop"
                    }
                ],
                "model": self.model_type,
                "usage": gemini_response.get("usageMetadata", {})
            }
        except Exception as e:
            # Handle errors
            error_msg = f"Error calling Gemini API: {str(e)}"
            if hasattr(response, 'text'):
                error_msg += f"\nResponse: {response.text}"
            raise Exception(error_msg)
