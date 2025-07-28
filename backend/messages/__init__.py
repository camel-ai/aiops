"""
Messages module for MCDP.

This module defines the message formats used in the system, including:
- BaseMessage: Base class for all message objects
- OpenAIMessage: Compatible with OpenAI API message format
- FunctionCallingMessage: For handling function calls
"""

from typing import Union, Dict, Any

# Define OpenAI message types for compatibility
OpenAISystemMessage = Dict[str, str]
OpenAIAssistantMessage = Dict[str, Any]
OpenAIUserMessage = Dict[str, Any]
OpenAIMessage = Dict[str, Any]

from .base import BaseMessage
from .function_calling_message import FunctionCallingMessage

__all__ = [
    'OpenAISystemMessage',
    'OpenAIAssistantMessage',
    'OpenAIUserMessage',
    'OpenAIMessage',
    'BaseMessage',
    'FunctionCallingMessage',
]
