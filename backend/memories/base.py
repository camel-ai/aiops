from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any

from messages import BaseMessage, OpenAIMessage


class MemoryBlock(ABC):
    """Abstract base class for memory blocks in MCDP.
    
    This class serves as the fundamental component within the agent memory system.
    It provides basic memory operations like writing records and clearing memory.
    """

    @abstractmethod
    def write_records(self, records: List[Dict[str, Any]]) -> None:
        """Writes records to the memory, appending them to existing ones.

        Args:
            records (List[Dict[str, Any]]): Records to be added to the memory.
        """
        pass

    def write_record(self, record: Dict[str, Any]) -> None:
        """Writes a record to the memory, appending it to existing ones.

        Args:
            record (Dict[str, Any]): Record to be added to the memory.
        """
        self.write_records([record])

    @abstractmethod
    def clear(self) -> None:
        """Clears all records from the memory."""
        pass


class BaseContextCreator(ABC):
    """Abstract base class for context creation strategies.
    
    This class provides a foundation for different strategies to generate
    conversational context from memory records.
    """

    @property
    @abstractmethod
    def token_limit(self) -> int:
        """Returns the maximum number of tokens allowed in the generated context."""
        pass

    @abstractmethod
    def create_context(
        self,
        records: List[Dict[str, Any]],
    ) -> Tuple[List[OpenAIMessage], int]:
        """Creates conversational context from the provided records.
        
        Args:
            records (List[Dict[str, Any]]): A list of context records.
            
        Returns:
            Tuple[List[OpenAIMessage], int]: A tuple containing the constructed
                context in OpenAIMessage format and the total token count.
        """
        pass


class AgentMemory(MemoryBlock, ABC):
    """Base class for agent memory components.
    
    This class represents a specialized form of MemoryBlock designed for
    direct integration with an agent.
    """

    @property
    @abstractmethod
    def agent_id(self) -> Optional[str]:
        """Returns the agent ID associated with this memory."""
        pass

    @agent_id.setter
    @abstractmethod
    def agent_id(self, val: Optional[str]) -> None:
        """Sets the agent ID associated with this memory."""
        pass

    @abstractmethod
    def retrieve(self) -> List[Dict[str, Any]]:
        """Get a record list from the memory for creating model context.
        
        Returns:
            List[Dict[str, Any]]: A record list for creating model context.
        """
        pass

    @abstractmethod
    def get_context_creator(self) -> BaseContextCreator:
        """Gets context creator.
        
        Returns:
            BaseContextCreator: A model context creator.
        """
        pass

    def get_context(self) -> Tuple[List[OpenAIMessage], int]:
        """Gets chat context with a proper size for the agent from the memory.
        
        Returns:
            Tuple[List[OpenAIMessage], int]: A tuple containing the constructed
                context in OpenAIMessage format and the total token count.
        """
        return self.get_context_creator().create_context(self.retrieve())
