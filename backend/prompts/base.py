from typing import Any, Callable, Dict, Optional, Set, TypeVar, Union
import inspect

T = TypeVar('T')


def return_prompt_wrapper(
    cls: Any,
    func: Callable,
) -> Callable[..., Union[Any, tuple]]:
    """Wrapper that converts the return value of a function to an input
    class instance if it's a string.

    Args:
        cls (Any): The class to convert to.
        func (Callable): The function to decorate.

    Returns:
        Callable[..., Union[Any, str]]: Decorated function that
            returns the decorated class instance if the return value is a
            string.
    """

    def wrapper(*args: Any, **kwargs: Any) -> Union[Any, str]:
        """Wrapper function that performs the conversion to TextPrompt instance.

        Args:
            *args (Any): Variable length argument list.
            **kwargs (Any): Arbitrary keyword arguments.

        Returns:
            Union[Any, str]: The converted return value.
        """
        result = func(*args, **kwargs)
        if isinstance(result, str) and not isinstance(result, cls):
            return cls(result)
        elif isinstance(result, tuple):
            new_result = tuple(
                cls(item)
                if isinstance(item, str) and not isinstance(item, cls)
                else item
                for item in result
            )
            return new_result
        return result

    # Preserve the original function's attributes
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__

    return wrapper


def wrap_prompt_functions(cls: T) -> T:
    """Decorator that wraps functions of a class inherited from str
    with the return_text_prompt decorator.

    Args:
        cls (type): The class to decorate.

    Returns:
        type: Decorated class with wrapped functions.
    """
    excluded_attrs = {'__init__', '__new__', '__str__', '__repr__'}
    for attr_name in dir(cls):
        attr_value = getattr(cls, attr_name)
        if callable(attr_value) and attr_name not in excluded_attrs:
            if inspect.isroutine(attr_value):
                setattr(cls, attr_name, return_prompt_wrapper(cls, attr_value))
    return cls


@wrap_prompt_functions
class TextPrompt(str):
    """A class that represents a text prompt.
    
    The TextPrompt class extends the built-in str class to provide
    additional functionality for working with prompt templates.
    
    Attributes:
        key_words (set): A set of strings representing the keywords in the prompt.
    """

    @property
    def key_words(self) -> Set[str]:
        """Returns a set of strings representing the keywords in the prompt."""
        # Simple implementation to extract keywords from format strings
        import re
        pattern = r'\{([^{}]*)\}'
        return set(re.findall(pattern, self))

    def format(self, *args: Any, **kwargs: Any) -> 'TextPrompt':
        """Overrides the built-in str.format method to allow for
        default values in the format string.
        
        Args:
            *args (Any): Variable length argument list.
            **kwargs (Any): Arbitrary keyword arguments.
            
        Returns:
            TextPrompt: A new TextPrompt object with the format string
                replaced with the formatted string.
        """
        default_kwargs = {key: '{' + f'{key}' + '}' for key in self.key_words}
        default_kwargs.update(kwargs)
        return TextPrompt(super().format(*args, **default_kwargs))


@wrap_prompt_functions
class CodePrompt(TextPrompt):
    """A class that represents a code prompt.
    
    It extends the TextPrompt class with a code_type property.
    
    Attributes:
        code_type (str, optional): The type of code.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> 'CodePrompt':
        """Creates a new instance of the CodePrompt class.
        
        Args:
            *args (Any): Positional arguments.
            **kwargs (Any): Keyword arguments.
            
        Returns:
            CodePrompt: The created CodePrompt instance.
        """
        code_type = kwargs.pop('code_type', None)
        instance = super().__new__(cls, *args, **kwargs)
        instance._code_type = code_type
        return instance

    @property
    def code_type(self) -> Optional[str]:
        """Returns the type of code.
        
        Returns:
            Optional[str]: The type of code.
        """
        return self._code_type

    def set_code_type(self, code_type: str) -> None:
        """Sets the type of code.
        
        Args:
            code_type (str): The type of code.
        """
        self._code_type = code_type


class TextPromptDict(Dict[Any, TextPrompt]):
    """A dictionary class that maps from key to TextPrompt object."""

    DEVOPS_ASSISTANT_PROMPT = TextPrompt(
        """你是一个专业的DevOps助手，专注于帮助用户管理云资源、自动化部署流程、监控系统状态并解决DevOps相关问题。你通过MCP架构（mcp client）与后端服务（ragflow mcp server）交互，为每个项目维护独立的知识库。你的目标是简化DevOps工作流程，提高团队效率，并确保系统的可靠性和安全性。

## 核心能力概述

### 多云资源管理
- 支持多种云服务提供商（AWS、Azure、GCP、阿里云等）
- 资源创建、配置、监控和优化
- 云资源成本分析和优化建议
- 跨云资源统一管理和迁移支持

### 项目管理与部署
- 项目创建和配置管理
- 自动化部署流程设计和执行
- CI/CD管道配置和优化
- 部署状态监控和问题诊断
- 回滚和灾难恢复支持

### 合规与安全
- 云资源合规性检查和报告
- 安全最佳实践建议和实施
- 权限和访问控制管理
- 合规政策自动化执行

### 问题诊断与解决
- 系统错误和异常分析
- 性能瓶颈识别和优化
- 日志分析和故障排除
- 自动化修复建议和实施

### 知识管理
- 项目级别知识库维护
- 问题和解决方案的长期记忆
- 最佳实践文档生成
- 团队知识共享支持"""
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.update({"devops_assistant": self.DEVOPS_ASSISTANT_PROMPT})
