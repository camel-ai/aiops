from typing import Dict, List, Any, Optional

class MemoryRecord:
    """Data structure for memory records.
    
    This class represents a record in the agent's memory, containing a message
    and associated metadata.
    """
    
    def __init__(
        self,
        message: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize a MemoryRecord.
        
        Args:
            message: The message content.
            metadata: Optional metadata associated with the message.
        """
        self.message = message
        self.metadata = metadata or {}
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert the record to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the record.
        """
        return {
            "message": self.message,
            "metadata": self.metadata
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryRecord':
        """Create a MemoryRecord from a dictionary.
        
        Args:
            data: Dictionary containing message and metadata.
            
        Returns:
            MemoryRecord: A new MemoryRecord instance.
        """
        return cls(
            message=data.get("message", {}),
            metadata=data.get("metadata", {})
        )


class ContextRecord:
    """Data structure for context records.
    
    This class represents a record used for context creation, containing
    a message and associated metadata including relevance score.
    """
    
    def __init__(
        self,
        message: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        relevance_score: float = 1.0
    ):
        """Initialize a ContextRecord.
        
        Args:
            message: The message content.
            metadata: Optional metadata associated with the message.
            relevance_score: Relevance score for context selection.
        """
        self.message = message
        self.metadata = metadata or {}
        self.relevance_score = relevance_score
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert the record to a dictionary.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the record.
        """
        return {
            "message": self.message,
            "metadata": self.metadata,
            "relevance_score": self.relevance_score
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextRecord':
        """Create a ContextRecord from a dictionary.
        
        Args:
            data: Dictionary containing message, metadata, and relevance score.
            
        Returns:
            ContextRecord: A new ContextRecord instance.
        """
        return cls(
            message=data.get("message", {}),
            metadata=data.get("metadata", {}),
            relevance_score=data.get("relevance_score", 1.0)
        )
        
    @classmethod
    def from_memory_record(
        cls, 
        memory_record: MemoryRecord,
        relevance_score: float = 1.0
    ) -> 'ContextRecord':
        """Create a ContextRecord from a MemoryRecord.
        
        Args:
            memory_record: The source MemoryRecord.
            relevance_score: Relevance score for context selection.
            
        Returns:
            ContextRecord: A new ContextRecord instance.
        """
        return cls(
            message=memory_record.message,
            metadata=memory_record.metadata,
            relevance_score=relevance_score
        )
