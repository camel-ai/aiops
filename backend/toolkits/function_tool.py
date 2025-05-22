from typing import List, Optional, Callable, Dict, Any
import inspect
import functools


class FunctionTool:
    """Base class for function tools in MCDP.
    
    This class wraps a function to make it available as a tool for agents.
    
    Args:
        func: The function to wrap.
        name: Optional custom name for the tool.
        description: Optional description of the tool.
        timeout: Optional timeout for the function execution.
    """
    
    def __init__(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        """Initialize a FunctionTool."""
        self.func = func
        self.name = name or func.__name__
        self.description = description or func.__doc__ or f"Tool for {self.name}"
        self.timeout = timeout
        
        # Get function signature
        self.signature = inspect.signature(func)
        
    def __call__(self, *args, **kwargs):
        """Call the wrapped function."""
        return self.func(*args, **kwargs)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert the tool to a dictionary format for API schemas.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the tool.
        """
        parameters = {}
        for name, param in self.signature.parameters.items():
            if name == 'self':
                continue
                
            param_info = {
                "type": "string"  # Default type
            }
            
            # Try to infer type from annotation
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == str:
                    param_info["type"] = "string"
                elif param.annotation == int:
                    param_info["type"] = "integer"
                elif param.annotation == float:
                    param_info["type"] = "number"
                elif param.annotation == bool:
                    param_info["type"] = "boolean"
                elif param.annotation == list or param.annotation == List:
                    param_info["type"] = "array"
                    param_info["items"] = {"type": "string"}
                elif param.annotation == dict or param.annotation == Dict:
                    param_info["type"] = "object"
            
            # Add description if available from docstring
            if self.func.__doc__:
                param_desc_match = f":param {name}:" in self.func.__doc__ or f"@param {name}" in self.func.__doc__
                if param_desc_match:
                    # This is a simple approach, a more robust parser would be better
                    param_info["description"] = "Parameter from function"
            
            # Handle default values
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
            
            parameters[name] = param_info
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "required": [
                        name for name, param in self.signature.parameters.items()
                        if param.default == inspect.Parameter.empty and name != 'self'
                    ]
                }
            }
        }
