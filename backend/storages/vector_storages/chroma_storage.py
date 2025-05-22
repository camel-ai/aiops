import os
import chromadb
from typing import Any, Dict, List, Optional, Union, Tuple
import uuid
import numpy as np

from . import VectorStorage

class ChromaVectorStorage(VectorStorage):
    """Vector storage implementation using ChromaDB.
    
    This class implements the VectorStorage interface using ChromaDB
    for storing and searching vector embeddings.
    
    Args:
        collection_name: Name of the collection to use.
        persist_directory: Directory to persist data to.
    """
    
    def __init__(
        self,
        collection_name: str = "default",
        persist_directory: Optional[str] = None
    ):
        """Initialize a ChromaVectorStorage."""
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # Initialize ChromaDB client
        if persist_directory:
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.Client()
            
        # Get or create collection
        self.collection = self.client.get_or_create_collection(name=collection_name)
        
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
        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
        elif len(ids) != len(vectors):
            raise ValueError("Number of IDs must match number of vectors")
            
        # Use empty metadata if not provided
        if metadata is None:
            metadata = [{} for _ in range(len(vectors))]
        elif len(metadata) != len(vectors):
            raise ValueError("Number of metadata items must match number of vectors")
            
        # Add to collection
        self.collection.add(
            embeddings=vectors,
            metadatas=metadata,
            ids=ids
        )
        
        return ids
    
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
        # Search collection
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=filter
        )
        
        # Format results
        formatted_results = []
        if results["ids"] and results["ids"][0]:
            for i, id in enumerate(results["ids"][0]):
                formatted_results.append({
                    "id": id,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": float(results["distances"][0][i]) if results["distances"] else 0.0
                })
                
        return formatted_results
    
    def get(self, id: str) -> Optional[Dict[str, Any]]:
        """Get a vector by ID.
        
        Args:
            id: ID of the vector to get.
            
        Returns:
            Optional[Dict[str, Any]]: Vector data if found, None otherwise.
        """
        try:
            result = self.collection.get(ids=[id])
            
            if not result["ids"]:
                return None
                
            return {
                "id": id,
                "vector": result["embeddings"][0] if result["embeddings"] else None,
                "metadata": result["metadatas"][0] if result["metadatas"] else {}
            }
        except Exception:
            return None
    
    def delete(self, ids: Union[str, List[str]]) -> bool:
        """Delete vectors by ID.
        
        Args:
            ids: ID or list of IDs to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        if isinstance(ids, str):
            ids = [ids]
            
        try:
            self.collection.delete(ids=ids)
            return True
        except Exception:
            return False
    
    def count(self) -> int:
        """Get the number of vectors in the storage.
        
        Returns:
            int: Number of vectors.
        """
        return self.collection.count()
