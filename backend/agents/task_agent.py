from typing import Any, Dict, List, Optional

from messages import BaseMessage
from .base import BaseAgent


class TaskAgent(BaseAgent):
    """Task agent for handling specific task processing.
    
    This agent is responsible for executing specific tasks based on user requests
    and system requirements.
    """
    
    def __init__(
        self,
        task_type: str,
        model_name: str = "gpt-4",
        tools: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize a TaskAgent.
        
        Args:
            task_type: The type of task this agent handles
            model_name: The name of the model to use
            tools: Optional list of tools available to the agent
        """
        self.task_type = task_type
        self.tools = tools or []
        self.state = {}
        
    def reset(self) -> None:
        """Reset the agent's state."""
        self.state = {}
        
    def step(self, task_input: Any) -> Dict[str, Any]:
        """Process a task and generate a result.
        
        Args:
            task_input: The input for the task
            
        Returns:
            A dictionary containing the task result and any additional information
        """
        # Process task based on task_type
        # This is a placeholder implementation
        result = {
            "status": "completed",
            "result": f"Processed {self.task_type} task",
            "input": task_input,
        }
        
        return result
