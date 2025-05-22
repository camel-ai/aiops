"""
Key-Value Storage module for MCDP.

This module provides key-value storage capabilities for storing and retrieving data.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

class KeyValueStorage(ABC):
    """Abstract base class for key-value storage implementations.
    
    This class defines the interface for key-value storage systems that can
    store, retrieve, and delete data by key.
    """
    
    @abstractmethod
    def get(self, key: str) -> Any:
        """Get a value by key.
        
        Args:
            key: The key to retrieve.
            
        Returns:
            Any: The stored value, or None if key not found.
        """
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any) -> bool:
        """Set a value for a key.
        
        Args:
            key: The key to set.
            value: The value to store.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a key-value pair.
        
        Args:
            key: The key to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists.
        
        Args:
            key: The key to check.
            
        Returns:
            bool: True if key exists, False otherwise.
        """
        pass
    
    @abstractmethod
    def keys(self) -> List[str]:
        """Get all keys in the storage.
        
        Returns:
            List[str]: List of all keys.
        """
        pass

# Import implementations after defining the base class to avoid circular imports
from .file_storage import FileKeyValueStorage
from .sqlite_storage import SQLiteKeyValueStorage

__all__ = [
    'KeyValueStorage',
    'FileKeyValueStorage',
    'SQLiteKeyValueStorage',
]
