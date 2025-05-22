"""
Prompts module for MCDP.

This module defines prompt templates and formats used in the system, including:
- TextPrompt: Base class for text prompts
- PromptTemplate: Template for generating prompts
- DevOpsPrompt: Specialized prompts for DevOps assistant
"""

from .base import TextPrompt, CodePrompt, TextPromptDict
from .prompt_template import PromptTemplate
from .devops_prompt import DevOpsPromptTemplateDict

__all__ = [
    'TextPrompt',
    'CodePrompt',
    'TextPromptDict',
    'PromptTemplate',
    'DevOpsPromptTemplateDict',
]
