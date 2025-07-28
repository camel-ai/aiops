from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union, Literal

class RoleType:
    """Role types for messages."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

@dataclass
class BaseMessage:
    """Base class for message objects used in MCDP chat system.
    
    Args:
        role_name (str): The name of the user or assistant role.
        role_type (str): The type of role (user, assistant, or system).
        meta_dict (Optional[Dict[str, Any]]): Additional metadata for the message.
        content (str): The content of the message.
    """

    role_name: str
    role_type: str
    meta_dict: Optional[Dict[str, Any]]
    content: str

    @classmethod
    def make_user_message(
        cls,
        role_name: str,
        content: str,
        meta_dict: Optional[Dict[str, Any]] = None,
    ) -> "BaseMessage":
        """Create a new user message.

        Args:
            role_name (str): The name of the user role.
            content (str): The content of the message.
            meta_dict (Optional[Dict[str, Any]]): Additional metadata for the message.

        Returns:
            BaseMessage: The new user message.
        """
        return cls(
            role_name,
            RoleType.USER,
            meta_dict,
            content,
        )

    @classmethod
    def make_assistant_message(
        cls,
        role_name: str,
        content: str,
        meta_dict: Optional[Dict[str, Any]] = None,
    ) -> "BaseMessage":
        """Create a new assistant message.

        Args:
            role_name (str): The name of the assistant role.
            content (str): The content of the message.
            meta_dict (Optional[Dict[str, Any]]): Additional metadata for the message.

        Returns:
            BaseMessage: The new assistant message.
        """
        return cls(
            role_name,
            RoleType.ASSISTANT,
            meta_dict,
            content,
        )
        
    @classmethod
    def make_system_message(
        cls,
        content: str,
        meta_dict: Optional[Dict[str, Any]] = None,
    ) -> "BaseMessage":
        """Create a new system message.

        Args:
            content (str): The content of the message.
            meta_dict (Optional[Dict[str, Any]]): Additional metadata for the message.

        Returns:
            BaseMessage: The new system message.
        """
        return cls(
            "system",
            RoleType.SYSTEM,
            meta_dict,
            content,
        )

    def create_new_instance(self, content: str) -> "BaseMessage":
        """Create a new instance of the BaseMessage with updated content.

        Args:
            content (str): The new content value.

        Returns:
            BaseMessage: The new instance of BaseMessage.
        """
        return self.__class__(
            role_name=self.role_name,
            role_type=self.role_type,
            meta_dict=self.meta_dict,
            content=content,
        )

    def to_openai_message(self) -> Dict[str, Any]:
        """Converts the message to an OpenAI message format.

        Returns:
            Dict[str, Any]: The message in OpenAI format.
        """
        if self.role_type == RoleType.SYSTEM:
            return {"role": "system", "content": self.content}
        elif self.role_type == RoleType.USER:
            return {"role": "user", "content": self.content}
        elif self.role_type == RoleType.ASSISTANT:
            return {"role": "assistant", "content": self.content}
        else:
            raise ValueError(f"Unsupported role type: {self.role_type}")

    def get(self, key: str, default=None) -> Any:
        """字典样式的获取属性，兼容 dict.get 方法

        Args:
            key: 要获取的属性名
            default: 如果属性不存在，返回的默认值

        Returns:
            属性值或默认值
        """
        if key == "role":
            return self.role_type
        elif key == "content":
            return self.content
        elif key == "role_name":
            return self.role_name
        elif key == "meta_dict" or key == "metadata":
            return self.meta_dict or {}
        return default
    
    def __getitem__(self, key: str) -> Any:
        """支持字典样式的键访问，例如 message["role"]

        Args:
            key: 要获取的属性名

        Returns:
            属性值

        Raises:
            KeyError: 如果属性不存在
        """
        result = self.get(key)
        if result is None:
            raise KeyError(key)
        return result
    
    def __contains__(self, key: str) -> bool:
        """支持 'key in message' 语法

        Args:
            key: 要检查的键名

        Returns:
            是否包含该键
        """
        return key in ["role", "content", "role_name", "meta_dict", "metadata"]
    
    def to_dict(self) -> Dict[str, Any]:
        """将消息转换为字典

        Returns:
            包含消息内容的字典
        """
        return {
            "role": self.role_type,
            "content": self.content,
            "role_name": self.role_name,
            "metadata": self.meta_dict or {}
        }
