from typing import Any, Dict, List, Optional

import requests

from messages import OpenAIMessage
from .base_model import BaseModelBackend


class AnthropicModel(BaseModelBackend):
    """Anthropic model backend implementation.
    
    This class implements the BaseModelBackend interface for Anthropic Claude models.
    
    Args:
        model_type (str): The Anthropic model to use (e.g., "claude-3-opus", "claude-3-sonnet").
        model_config_dict (Optional[Dict[str, Any]]): Configuration for the model.
        api_key (Optional[str]): Anthropic API key.
        url (Optional[str]): Custom API endpoint URL.
    """
    
    def __init__(
        self,
        model_type: str = "claude-3-opus",
        model_config_dict: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
    ):
        super().__init__(model_type, model_config_dict, api_key, url)
        self.api_url = url or "https://api.anthropic.com/v1/messages"
        
    def check_model_config(self):
        """Validate the model configuration."""
        valid_params = {
            "temperature", "top_p", "max_tokens", 
            "stop_sequences", "stream", "system"
        }
        
        for param in self.model_config_dict:
            if param not in valid_params:
                raise ValueError(f"Unexpected parameter in model config: {param}")
    
    def _convert_to_anthropic_messages(self, messages: List[OpenAIMessage]) -> List[Dict[str, Any]]:
        """Convert OpenAI message format to Anthropic message format."""
        anthropic_messages = []
        system_message = None
        
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            
            if role == "system":
                system_message = content
            elif role == "user":
                anthropic_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": content})
            # Anthropic doesn't have a direct equivalent for function messages
            # This is a simplified implementation
        
        return anthropic_messages, system_message
    
    def generate(
        self,
        messages: List[OpenAIMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate a response from the Anthropic model.
        
        Args:
            messages (List[OpenAIMessage]): Message list with the chat history.
            tools (Optional[List[Dict[str, Any]]]): The schema of tools to use.
            **kwargs: Additional parameters for the model.
            
        Returns:
            Dict[str, Any]: The model's response.
        """
        # Preprocess messages
        processed_messages = self.preprocess_messages(messages)
        
        # Convert to Anthropic format
        anthropic_messages, system_message = self._convert_to_anthropic_messages(processed_messages)
        
        # Prepare request payload
        payload = {
            "model": self.model_type,
            "messages": anthropic_messages,
            **self.model_config_dict,
            **kwargs
        }
        
        # Add system message if present
        if system_message:
            payload["system"] = system_message
            
        # Set up headers
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01"
        }
        
        # Make API request
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            # Convert Anthropic response to OpenAI-like format for consistency
            anthropic_response = response.json()
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": anthropic_response.get("content", [{"text": ""}])[0].get("text", "")
                        },
                        "finish_reason": anthropic_response.get("stop_reason", "stop")
                    }
                ],
                "model": self.model_type,
                "usage": anthropic_response.get("usage", {})
            }
        except Exception as e:
            # Handle errors
            error_msg = f"Error calling Anthropic API: {str(e)}"
            if hasattr(response, 'text'):
                error_msg += f"\nResponse: {response.text}"
            raise Exception(error_msg)
