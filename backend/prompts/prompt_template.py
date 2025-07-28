from typing import Dict, Any, Optional, List, Union
import re

from .base import TextPrompt, TextPromptDict


class PromptTemplate:
    """Class for generating prompts from templates.
    
    This class provides methods for creating and formatting prompt templates
    for various use cases.
    
    Args:
        template_dict: Dictionary of prompt templates.
    """
    
    def __init__(self, template_dict: Optional[TextPromptDict] = None):
        """Initialize a PromptTemplate."""
        self.template_dict = template_dict or TextPromptDict()
        
    def get_prompt(self, key: Any, **kwargs: Any) -> TextPrompt:
        """Get a prompt by key and format it with the provided kwargs.
        
        Args:
            key: The key for the prompt template.
            **kwargs: Keyword arguments for formatting the template.
            
        Returns:
            TextPrompt: The formatted prompt.
            
        Raises:
            KeyError: If the key is not found in the template dictionary.
        """
        if key not in self.template_dict:
            raise KeyError(f"Prompt template with key '{key}' not found")
            
        template = self.template_dict[key]
        return template.format(**kwargs)
        
    def add_template(self, key: Any, template: Union[str, TextPrompt]) -> None:
        """Add a new template to the template dictionary.
        
        Args:
            key: The key for the prompt template.
            template: The template string or TextPrompt.
        """
        if isinstance(template, str) and not isinstance(template, TextPrompt):
            template = TextPrompt(template)
            
        self.template_dict[key] = template
        
    def get_keywords(self, key: Any) -> List[str]:
        """Get the keywords in a prompt template.
        
        Args:
            key: The key for the prompt template.
            
        Returns:
            List[str]: The keywords in the template.
            
        Raises:
            KeyError: If the key is not found in the template dictionary.
        """
        if key not in self.template_dict:
            raise KeyError(f"Prompt template with key '{key}' not found")
            
        template = self.template_dict[key]
        return list(template.key_words)
