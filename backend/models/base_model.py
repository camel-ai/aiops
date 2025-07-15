from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Type

from messages import OpenAIMessage


class BaseModelBackend(ABC):
    """Base class for different model backends.
    
    This class defines the interface that all model backends must implement.
    It may be OpenAI API, Anthropic API, Google API, or a local LLM.
    
    Args:
        model_type (str): Model for which a backend is created.
        model_config_dict (Optional[Dict[str, Any]]): A config dictionary.
        api_key (Optional[str]): The API key for authenticating with the model service.
        url (Optional[str]): The url to the model service.
    """

    def __init__(
        self,
        model_type: str,
        model_config_dict: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
    ) -> None:
        self.model_type = model_type
        self.model_config_dict = model_config_dict or {}
        self._api_key = api_key
        self._url = url
        self.check_model_config()

    def preprocess_messages(
        self, messages: List[OpenAIMessage]
    ) -> List[OpenAIMessage]:
        """Preprocess messages before sending to model API.
        
        Args:
            messages (List[OpenAIMessage]): Original messages.
            
        Returns:
            List[OpenAIMessage]: Preprocessed messages
        """
        # Simple implementation - can be extended for more complex preprocessing
        return messages

    @abstractmethod
    def generate(
        self,
        messages: List[OpenAIMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate a response from the model.
        
        Args:
            messages (List[OpenAIMessage]): Message list with the chat history.
            tools (Optional[List[Dict[str, Any]]]): The schema of tools to use.
            **kwargs: Additional parameters for the model.
            
        Returns:
            Dict[str, Any]: The model's response.
        """
        pass

    @abstractmethod
    def check_model_config(self):
        """Check whether the input model configuration contains unexpected arguments.
        
        Raises:
            ValueError: If the model configuration dictionary contains any
                unexpected argument for this model class.
        """
        pass

    @property
    def token_limit(self) -> int:
        """Returns the maximum token limit for a given model.
        
        Returns:
            int: The maximum token limit for the given model.
        """
        return self.model_config_dict.get("max_tokens", 4096)
