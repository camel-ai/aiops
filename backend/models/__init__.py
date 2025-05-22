"""
Models module for MCDP.

This module provides interfaces and implementations for various language models,
supporting multiple model backends including:
- OpenAI (GPT series)
- Anthropic (Claude series)
- Google (Gemini series)
- Ollama (locally deployed models)
"""

from .base_model import BaseModelBackend
from .openai_model import OpenAIModel
from .anthropic_model import AnthropicModel
from .gemini_model import GeminiModel
from .ollama_model import OllamaModel
from .model_factory import ModelFactory
from .model_manager import ModelManager

__all__ = [
    'BaseModelBackend',
    'OpenAIModel',
    'AnthropicModel',
    'GeminiModel',
    'OllamaModel',
    'ModelFactory',
    'ModelManager',
]
