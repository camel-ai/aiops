from typing import Any, List, Union, Dict, Optional
import requests
import json

from toolkits import FunctionTool
from .base import BaseRuntime


class RemoteHTTPRuntime(BaseRuntime):
    """Runtime for remote HTTP services.
    
    This class implements the BaseRuntime interface for remote HTTP services,
    allowing tools to be executed via HTTP requests.
    
    Args:
        base_url: Base URL of the remote service.
        headers: Optional HTTP headers to include in requests.
        timeout: Optional timeout for HTTP requests.
    """
    
    def __init__(
        self,
        base_url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0
    ):
        """Initialize a RemoteHTTPRuntime."""
        super().__init__()
        self.base_url = base_url.rstrip('/')
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout
        
    def add(
        self,
        funcs: Union[FunctionTool, List[FunctionTool]],
        *args: Any,
        **kwargs: Any,
    ) -> "RemoteHTTPRuntime":
        """Add a new tool or tools to the runtime.
        
        Args:
            funcs: A FunctionTool or list of FunctionTools to add.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
            
        Returns:
            RemoteHTTPRuntime: The runtime instance for method chaining.
        """
        if isinstance(funcs, FunctionTool):
            funcs = [funcs]
            
        for func in funcs:
            self.tools_map[func.name] = func
            
        return self
        
    def reset(self, *args: Any, **kwargs: Any) -> bool:
        """Reset the runtime connection.
        
        Args:
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
            
        Returns:
            bool: True if reset was successful.
        """
        # For HTTP runtime, reset is a no-op
        return True
        
    def execute(self, tool_name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a tool via HTTP request.
        
        Args:
            tool_name: Name of the tool to execute.
            *args: Positional arguments for the tool.
            **kwargs: Keyword arguments for the tool.
            
        Returns:
            Any: Result of the tool execution.
            
        Raises:
            ValueError: If the tool is not found.
        """
        if tool_name not in self.tools_map:
            raise ValueError(f"Tool '{tool_name}' not found")
            
        tool = self.tools_map[tool_name]
        
        # Prepare request payload
        payload = {
            "tool": tool_name,
            "args": args,
            "kwargs": kwargs
        }
        
        # Determine endpoint URL
        endpoint = f"{self.base_url}/api/tools/execute"
        
        try:
            # Make HTTP request
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            
            # Check for HTTP errors
            response.raise_for_status()
            
            # Parse and return response
            return response.json()
        except requests.RequestException as e:
            return {
                "error": f"HTTP request failed: {str(e)}"
            }
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse response as JSON"
            }
