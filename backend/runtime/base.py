from abc import ABC, abstractmethod
from typing import Any, List, Union, Dict, Optional

from toolkits import FunctionTool


class BaseRuntime(ABC):
    """Abstract base class for all MCDP runtimes.
    
    This class defines the interface for runtime environments that can
    execute tools and manage their lifecycle.
    """

    def __init__(self):
        """Initialize a BaseRuntime."""
        super().__init__()
        self.tools_map: Dict[str, FunctionTool] = {}

    @abstractmethod
    def add(
        self,
        funcs: Union[FunctionTool, List[FunctionTool]],
        *args: Any,
        **kwargs: Any,
    ) -> "BaseRuntime":
        """Add a new tool or tools to the runtime.
        
        Args:
            funcs: A FunctionTool or list of FunctionTools to add.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
            
        Returns:
            BaseRuntime: The runtime instance for method chaining.
        """
        pass

    @abstractmethod
    def reset(self, *args: Any, **kwargs: Any) -> Any:
        """Reset the runtime to its initial state.
        
        Args:
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
            
        Returns:
            Any: Result of the reset operation.
        """
        pass

    def get_tools(self) -> List[FunctionTool]:
        """Return a list of all tools in the runtime.
        
        Returns:
            List[FunctionTool]: List of all tools in the runtime.
        """
        return list(self.tools_map.values())
        
    def get_tool(self, name: str) -> Optional[FunctionTool]:
        """Get a tool by name.
        
        Args:
            name: Name of the tool to get.
            
        Returns:
            Optional[FunctionTool]: The tool if found, None otherwise.
        """
        return self.tools_map.get(name)
