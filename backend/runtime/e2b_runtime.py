from typing import Any, List, Union, Dict, Optional
import requests
import json
import os
import subprocess
import time

from toolkits import FunctionTool
from .base import BaseRuntime


class E2BRuntime(BaseRuntime):
    """Runtime for E2B sandbox environments.
    
    This class implements the BaseRuntime interface for E2B sandbox environments,
    allowing tools to be executed in isolated cloud environments.
    
    Args:
        sandbox_id: Optional ID of an existing sandbox.
        api_key: Optional API key for E2B service.
        timeout: Optional timeout for sandbox operations.
    """
    
    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 60.0
    ):
        """Initialize an E2BRuntime."""
        super().__init__()
        self.sandbox_id = sandbox_id
        self.api_key = api_key
        self.timeout = timeout
        self.base_url = "https://api.e2b.dev/v1"
        self.headers = {"Content-Type": "application/json"}
        
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
            
        self.sandbox_status = "stopped" if sandbox_id else None
        
    def add(
        self,
        funcs: Union[FunctionTool, List[FunctionTool]],
        *args: Any,
        **kwargs: Any,
    ) -> "E2BRuntime":
        """Add a new tool or tools to the runtime.
        
        Args:
            funcs: A FunctionTool or list of FunctionTools to add.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
            
        Returns:
            E2BRuntime: The runtime instance for method chaining.
        """
        if isinstance(funcs, FunctionTool):
            funcs = [funcs]
            
        for func in funcs:
            self.tools_map[func.name] = func
            
        return self
        
    def reset(self, *args: Any, **kwargs: Any) -> bool:
        """Reset the sandbox environment.
        
        Args:
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
            
        Returns:
            bool: True if reset was successful, False otherwise.
        """
        if not self.sandbox_id:
            return True
            
        try:
            # Stop the sandbox
            response = requests.post(
                f"{self.base_url}/sandboxes/{self.sandbox_id}/stop",
                headers=self.headers,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            self.sandbox_status = "stopped"
            return True
        except requests.RequestException:
            return False
            
    def start(self) -> bool:
        """Start the sandbox environment.
        
        Returns:
            bool: True if sandbox was started successfully, False otherwise.
        """
        if self.sandbox_status == "running":
            return True
            
        try:
            if not self.sandbox_id:
                # Create a new sandbox
                response = requests.post(
                    f"{self.base_url}/sandboxes",
                    headers=self.headers,
                    json={"template": "base"},
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                data = response.json()
                self.sandbox_id = data.get("id")
                self.sandbox_status = "running"
                return True
            else:
                # Start an existing sandbox
                response = requests.post(
                    f"{self.base_url}/sandboxes/{self.sandbox_id}/start",
                    headers=self.headers,
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                self.sandbox_status = "running"
                return True
        except requests.RequestException:
            return False
            
    def execute(self, tool_name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a tool in the sandbox environment.
        
        Args:
            tool_name: Name of the tool to execute.
            *args: Positional arguments for the tool.
            **kwargs: Keyword arguments for the tool.
            
        Returns:
            Any: Result of the tool execution.
            
        Raises:
            ValueError: If the tool is not found or the sandbox cannot be started.
        """
        if tool_name not in self.tools_map:
            raise ValueError(f"Tool '{tool_name}' not found")
            
        if self.sandbox_status != "running":
            if not self.start():
                raise ValueError("Failed to start sandbox environment")
                
        tool = self.tools_map[tool_name]
        
        # Prepare command to execute in sandbox
        command = f"python3 -c \"import json; import sys; sys.path.append('/app'); from tools import {tool_name}; result = {tool_name}(*{json.dumps(args)}, **{json.dumps(kwargs)}); print(json.dumps(result))\""
        
        try:
            # Execute command in sandbox
            response = requests.post(
                f"{self.base_url}/sandboxes/{self.sandbox_id}/terminal",
                headers=self.headers,
                json={"command": command},
                timeout=self.timeout
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Parse output
            output = data.get("output", "")
            try:
                return json.loads(output.strip())
            except json.JSONDecodeError:
                return {
                    "error": "Failed to parse tool output",
                    "raw_output": output
                }
        except requests.RequestException as e:
            return {
                "error": f"Sandbox execution failed: {str(e)}"
            }
