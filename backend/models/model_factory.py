from typing import Dict, Optional, Type

from .base_model import BaseModelBackend
from .openai_model import OpenAIModel
from .anthropic_model import AnthropicModel
from .gemini_model import GeminiModel
from .ollama_model import OllamaModel


class ModelFactory:
    """Factory class for creating model instances.
    
    This class provides methods for creating instances of different model backends.
    """
    
    @staticmethod
    def create_model(
        model_name: str,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        model_config: Optional[Dict] = None
    ) -> BaseModelBackend:
        """Create a model instance based on the model name.
        
        Args:
            model_name (str): Name of the model to create.
            api_key (Optional[str]): API key for the model service.
            url (Optional[str]): URL for the model service.
            model_config (Optional[Dict]): Configuration for the model.
            
        Returns:
            BaseModelBackend: An instance of the appropriate model backend.
            
        Raises:
            ValueError: If the model name is not recognized.
        """
        model_config = model_config or {}
        
        # OpenAI models
        if model_name.startswith(("gpt-", "text-davinci")):
            return OpenAIModel(model_name, model_config, api_key, url)
        
        # Anthropic models
        elif model_name.startswith("claude"):
            return AnthropicModel(model_name, model_config, api_key, url)
        
        # Google models
        elif model_name.startswith("gemini"):
            return GeminiModel(model_name, model_config, api_key, url)
        
        # Ollama models
        elif model_name.startswith("ollama/"):
            ollama_model_type = model_name.split('/', 1)[1] # Extract model name after "ollama/"
            # Pass the extracted model type and the url to OllamaModel
            return OllamaModel(ollama_model_type, model_config, api_key, url)
        
        # Default to OpenAI if model not recognized
        else:
            raise ValueError(f"Unrecognized model: {model_name}")
