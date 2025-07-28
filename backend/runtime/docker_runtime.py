from typing import Any, List, Union, Dict, Optional
import subprocess
import json
import os

from toolkits import FunctionTool
from .base import BaseRuntime


class DockerRuntime(BaseRuntime):
    """Runtime for Docker containers.
    
    This class implements the BaseRuntime interface for Docker containers,
    allowing tools to be executed in isolated Docker environments.
    
    Args:
        image: Docker image to use.
        container_name: Optional name for the container.
        volumes: Optional volume mappings.
        environment: Optional environment variables.
    """
    
    def __init__(
        self,
        image: str,
        container_name: Optional[str] = None,
        volumes: Optional[Dict[str, str]] = None,
        environment: Optional[Dict[str, str]] = None
    ):
        """Initialize a DockerRuntime."""
        super().__init__()
        self.image = image
        self.container_name = container_name
        self.volumes = volumes or {}
        self.environment = environment or {}
        self.container_id = None
        
    def add(
        self,
        funcs: Union[FunctionTool, List[FunctionTool]],
        *args: Any,
        **kwargs: Any,
    ) -> "DockerRuntime":
        """Add a new tool or tools to the runtime.
        
        Args:
            funcs: A FunctionTool or list of FunctionTools to add.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
            
        Returns:
            DockerRuntime: The runtime instance for method chaining.
        """
        if isinstance(funcs, FunctionTool):
            funcs = [funcs]
            
        for func in funcs:
            self.tools_map[func.name] = func
            
        return self
        
    def reset(self, *args: Any, **kwargs: Any) -> bool:
        """Reset the runtime by stopping and removing the container.
        
        Args:
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
            
        Returns:
            bool: True if reset was successful, False otherwise.
        """
        if self.container_id:
            try:
                # Stop the container
                subprocess.run(
                    ["docker", "stop", self.container_id],
                    check=True,
                    capture_output=True
                )
                
                # Remove the container
                subprocess.run(
                    ["docker", "rm", self.container_id],
                    check=True,
                    capture_output=True
                )
                
                self.container_id = None
                return True
            except subprocess.CalledProcessError:
                return False
                
        return True
        
    def start(self) -> bool:
        """Start the Docker container.
        
        Returns:
            bool: True if container was started successfully, False otherwise.
        """
        if self.container_id:
            return True
            
        cmd = ["docker", "run", "-d"]
        
        # Add container name if specified
        if self.container_name:
            cmd.extend(["--name", self.container_name])
            
        # Add volume mappings
        for host_path, container_path in self.volumes.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])
            
        # Add environment variables
        for key, value in self.environment.items():
            cmd.extend(["-e", f"{key}={value}"])
            
        # Add image name
        cmd.append(self.image)
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
            self.container_id = result.stdout.strip()
            return True
        except subprocess.CalledProcessError:
            return False
            
    def execute(self, tool_name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a tool in the Docker container.
        
        Args:
            tool_name: Name of the tool to execute.
            *args: Positional arguments for the tool.
            **kwargs: Keyword arguments for the tool.
            
        Returns:
            Any: Result of the tool execution.
            
        Raises:
            ValueError: If the tool is not found or the container is not running.
        """
        if tool_name not in self.tools_map:
            raise ValueError(f"Tool '{tool_name}' not found")
            
        if not self.container_id:
            if not self.start():
                raise ValueError("Failed to start Docker container")
                
        tool = self.tools_map[tool_name]
        
        # Prepare command to execute in container
        cmd = [
            "docker", "exec", self.container_id,
            "python", "-c",
            f"import json; print(json.dumps({tool.name}(*{args}, **{json.dumps(kwargs)})))"
        ]
        
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            
            return json.loads(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            return {
                "error": f"Tool execution failed: {e.stderr}"
            }
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse tool output"
            }
