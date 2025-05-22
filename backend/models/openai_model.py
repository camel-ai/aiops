from typing import Any, Dict, List, Optional

import requests

from messages import OpenAIMessage
from .base_model import BaseModelBackend


class OpenAIModel(BaseModelBackend):
    """OpenAI model backend implementation.
    
    This class implements the BaseModelBackend interface for OpenAI models.
    
    Args:
        model_type (str): The OpenAI model to use (e.g., "gpt-4", "gpt-3.5-turbo").
        model_config_dict (Optional[Dict[str, Any]]): Configuration for the model.
        api_key (Optional[str]): OpenAI API key.
        url (Optional[str]): Custom API endpoint URL.
    """
    
    def __init__(
        self,
        model_type: str = "gpt-4",
        model_config_dict: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
    ):
        super().__init__(model_type, model_config_dict, api_key, url)
        self.api_url = url or "https://api.openai.com/v1/chat/completions"
        
    def check_model_config(self):
        """Validate the model configuration."""
        valid_params = {
            "temperature", "top_p", "n", "stream", "stop", 
            "max_tokens", "presence_penalty", "frequency_penalty",
            "logit_bias", "user", "response_format"
        }
        
        for param in self.model_config_dict:
            if param not in valid_params:
                raise ValueError(f"Unexpected parameter in model config: {param}")
    
    def generate(
        self,
        messages: List[OpenAIMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate a response from the OpenAI model.
        
        Args:
            messages (List[OpenAIMessage]): Message list with the chat history.
            tools (Optional[List[Dict[str, Any]]]): The schema of tools to use.
            **kwargs: Additional parameters for the model.
            
        Returns:
            Dict[str, Any]: The model's response.
        """
        # Preprocess messages
        processed_messages = self.preprocess_messages(messages)
        
        # Prepare request payload
        payload = {
            "model": self.model_type,
            "messages": processed_messages,
            **self.model_config_dict,
            **kwargs
        }
        
        # Add tools if provided
        if tools:
            payload["tools"] = tools
            
        # Set up headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}"
        }
        
        # Make API request
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Handle errors
            error_msg = f"Error calling OpenAI API: {str(e)}"
            if hasattr(response, 'text'):
                error_msg += f"\nResponse: {response.text}"
            raise Exception(error_msg)
