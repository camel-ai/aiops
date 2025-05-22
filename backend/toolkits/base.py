from typing import List, Optional, Dict, Any
import time
import functools

from .function_tool import FunctionTool


def with_timeout(func):
    """Decorator to add timeout functionality to a function."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.timeout is None:
            return func(self, *args, **kwargs)
        
        # Simple timeout implementation
        start_time = time.time()
        result = func(self, *args, **kwargs)
        elapsed_time = time.time() - start_time
        
        if elapsed_time > self.timeout:
            print(f"Warning: Function {func.__name__} exceeded timeout of {self.timeout}s")
        
        return result
    return wrapper


class BaseToolkit:
    """Base class for toolkits in MCDP.
    
    This class provides the foundation for creating toolkits that contain
    multiple related tools.
    
    Args:
        timeout: Optional timeout for all tools in the toolkit.
    """
    
    def __init__(self, timeout: Optional[float] = None):
        """Initialize a BaseToolkit."""
        # Check if timeout is a positive number
        if timeout is not None and timeout <= 0:
            raise ValueError("Timeout must be a positive number.")
        self.timeout = timeout
        
    def __init_subclass__(cls, **kwargs):
        """Add timeout to all callable methods in the toolkit."""
        super().__init_subclass__(**kwargs)
        for attr_name, attr_value in cls.__dict__.items():
            if callable(attr_value) and not attr_name.startswith("__"):
                setattr(cls, attr_name, with_timeout(attr_value))
    
    def get_tools(self) -> List[FunctionTool]:
        """Returns a list of FunctionTool objects representing the functions in the toolkit.
        
        Returns:
            List[FunctionTool]: A list of FunctionTool objects.
        """
        tools = []
        
        for attr_name in dir(self):
            # Skip private methods and get_tools itself
            if attr_name.startswith("__") or attr_name == "get_tools":
                continue
                
            attr = getattr(self, attr_name)
            if callable(attr) and not isinstance(attr, type):
                # Create a FunctionTool for each method
                tool = FunctionTool(
                    func=attr,
                    name=attr_name,
                    timeout=self.timeout
                )
                tools.append(tool)
                
        return tools
