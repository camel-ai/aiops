from typing import Dict, List, Optional, Any

from .model_factory import ModelFactory
from .base_model import BaseModelBackend


class ModelManager:
    """Manager class for handling model instances.
    
    This class provides methods for creating, caching, and managing model instances.
    """
    
    def __init__(self):
        """Initialize the ModelManager."""
        self.models: Dict[str, BaseModelBackend] = {}
        self.default_model_name = "gpt-4"
        self.default_config: Dict[str, Any] = {
            "temperature": 0.7,
            "max_tokens": 2048
        }
        
    def get_model(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        url: Optional[str] = None,
        model_config: Optional[Dict] = None,
        force_new: bool = False
    ) -> BaseModelBackend:
        """Get a model instance, creating it if necessary.
        
        Args:
            model_name (Optional[str]): Name of the model to get.
            api_key (Optional[str]): API key for the model service.
            url (Optional[str]): URL for the model service.
            model_config (Optional[Dict]): Configuration for the model.
            force_new (bool): Whether to force creation of a new instance.
            
        Returns:
            BaseModelBackend: An instance of the appropriate model backend.
        """
        model_name = model_name or self.default_model_name
        model_config = model_config or self.default_config.copy()
        
        # Create a cache key based on model parameters
        cache_key = f"{model_name}_{api_key}_{url}_{hash(frozenset(model_config.items()))}"
        
        # Return cached model if available and not forcing new
        if not force_new and cache_key in self.models:
            return self.models[cache_key]
        
        # Create a new model instance
        model = ModelFactory.create_model(model_name, api_key, url, model_config)
        
        # Cache the model
        self.models[cache_key] = model
        
        return model
    
    def set_default_model(self, model_name: str, model_config: Optional[Dict] = None):
        """Set the default model name and configuration.
        
        Args:
            model_name (str): Name of the default model.
            model_config (Optional[Dict]): Configuration for the default model.
        """
        self.default_model_name = model_name
        if model_config:
            self.default_config = model_config.copy()
    
    def clear_cache(self):
        """Clear the model cache."""
        self.models = {}
