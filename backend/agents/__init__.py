"""
Agents module for MCDP.

This module contains various agent implementations for MCDP, including:
- ChatAgent: Handles user-system dialogue interactions
- TaskAgent: Processes specific tasks
- CriticAgent: Provides evaluation and feedback
- SearchAgent: Executes search functionality
- EmbodiedAgent: Handles embodied tasks
- KnowledgeGraphAgent: Interacts with the knowledge graph through MCP
"""

from .base import BaseAgent
from .chat_agent import ChatAgent
from .task_agent import TaskAgent
from .critic_agent import CriticAgent
from .search_agent import SearchAgent
from .embodied_agent import EmbodiedAgent
from .knowledge_graph_agent import KnowledgeGraphAgent

__all__ = [
    'BaseAgent',
    'ChatAgent',
    'TaskAgent',
    'CriticAgent',
    'SearchAgent',
    'EmbodiedAgent',
    'KnowledgeGraphAgent',
]
