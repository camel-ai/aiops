"""
Vector Storage module for MCDP.

This module provides vector storage capabilities for storing and retrieving vector embeddings.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple

import numpy as np

class VectorStorage(ABC):
    """Abstract base class for vector storage implementations.
    
    This class defines the interface for vector storage systems that can
    store, retrieve, and search vector embeddings.
    """
    
    @abstractmethod
    def add(
        self, 
        vectors: List[List[float]], 
        metadata: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """Add vectors to the storage.
        
        Args:
            vectors: List of vector embeddings to add.
            metadata: Optional metadata for each vector.
            ids: Optional IDs for each vector.
            
        Returns:
            List[str]: List of IDs for the added vectors.
        """
        pass
    
    @abstractmethod
    def search(
        self, 
        query_vector: List[float], 
        top_k: int = 5,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors.
        
        Args:
            query_vector: Vector to search for.
            top_k: Number of results to return.
            filter: Optional filter for metadata.
            
        Returns:
            List[Dict[str, Any]]: List of search results with scores.
        """
        pass
    
    @abstractmethod
    def get(self, id: str) -> Optional[Dict[str, Any]]:
        """Get a vector by ID.
        
        Args:
            id: ID of the vector to get.
            
        Returns:
            Optional[Dict[str, Any]]: Vector data if found, None otherwise.
        """
        pass
    
    @abstractmethod
    def delete(self, ids: Union[str, List[str]]) -> bool:
        """Delete vectors by ID.
        
        Args:
            ids: ID or list of IDs to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def count(self) -> int:
        """Get the number of vectors in the storage.
        
        Returns:
            int: Number of vectors.
        """
        pass

# Import implementations after defining the base class to avoid circular imports
from .simple_storage import SimpleVectorStorage
from .chroma_storage import ChromaVectorStorage

__all__ = [
    'VectorStorage',
    'SimpleVectorStorage',
    'ChromaVectorStorage',
]
