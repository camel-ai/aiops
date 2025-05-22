from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """An abstract base class for all MCDP agents.
    
    This class defines the basic interface that all agents must implement.
    """

    @abstractmethod
    def reset(self, *args: Any, **kwargs: Any) -> Any:
        """Resets the agent to its initial state."""
        pass

    @abstractmethod
    def step(self, *args: Any, **kwargs: Any) -> Any:
        """Performs a single step of the agent."""
        pass
