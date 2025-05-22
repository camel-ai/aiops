from typing import Any, Dict, List, Optional, Union

from .base import BaseMessage


class FunctionCallingMessage(BaseMessage):
    """Message class for function calling in MCDP chat system.
    
    This class extends BaseMessage to support function calling capabilities,
    including function name, arguments, and results.
    
    Args:
        role_name (str): The name of the user or assistant role.
        role_type (str): The type of role (user, assistant, or system).
        meta_dict (Optional[Dict[str, Any]]): Additional metadata for the message.
        content (str): The content of the message.
        func_name (str): The name of the function being called.
        args (Optional[Dict[str, Any]]): The arguments for the function call.
        result (Optional[Any]): The result of the function call.
    """

    def __init__(
        self,
        role_name: str,
        role_type: str,
        meta_dict: Optional[Dict[str, Any]],
        content: str,
        func_name: str,
        args: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None,
    ):
        super().__init__(role_name, role_type, meta_dict, content)
        self.func_name = func_name
        self.args = args or {}
        self.result = result
        
    def to_openai_message(self) -> Dict[str, Any]:
        """Converts the message to an OpenAI message format with function calling.

        Returns:
            Dict[str, Any]: The message in OpenAI format with function calling.
        """
        base_message = super().to_openai_message()
        
        # If this is a function call (from assistant)
        if self.args and not self.result:
            base_message["function_call"] = {
                "name": self.func_name,
                "arguments": self.args,
            }
            
        # If this is a function result (from function)
        if self.result is not None:
            base_message["role"] = "function"
            base_message["name"] = self.func_name
            base_message["content"] = str(self.result)
            
        return base_message
