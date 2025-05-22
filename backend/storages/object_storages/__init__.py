"""
Object Storage module for MCDP.

This module provides object storage capabilities for storing and retrieving arbitrary objects.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, BinaryIO

class ObjectStorage(ABC):
    """Abstract base class for object storage implementations.
    
    This class defines the interface for object storage systems that can
    store, retrieve, and delete arbitrary objects.
    """
    
    @abstractmethod
    def put(
        self, 
        key: str, 
        data: Union[bytes, BinaryIO, str],
        metadata: Optional[Dict[str, str]] = None
    ) -> bool:
        """Store an object.
        
        Args:
            key: Key to store the object under.
            data: Object data to store.
            metadata: Optional metadata for the object.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def get(self, key: str) -> Optional[bytes]:
        """Get an object by key.
        
        Args:
            key: Key of the object to get.
            
        Returns:
            Optional[bytes]: Object data if found, None otherwise.
        """
        pass
    
    @abstractmethod
    def get_metadata(self, key: str) -> Optional[Dict[str, str]]:
        """Get object metadata by key.
        
        Args:
            key: Key of the object to get metadata for.
            
        Returns:
            Optional[Dict[str, str]]: Metadata if found, None otherwise.
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete an object by key.
        
        Args:
            key: Key of the object to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def list(self, prefix: Optional[str] = None) -> List[str]:
        """List objects with optional prefix.
        
        Args:
            prefix: Optional prefix to filter by.
            
        Returns:
            List[str]: List of object keys.
        """
        pass

# Import implementations after defining the base class to avoid circular imports
from .file_storage import FileObjectStorage
from .s3_storage import S3ObjectStorage

__all__ = [
    'ObjectStorage',
    'FileObjectStorage',
    'S3ObjectStorage',
]
