import uuid
import numpy as np
from typing import Any, Dict, List, Optional, Union, Tuple
from sklearn.metrics.pairwise import cosine_similarity

from . import VectorStorage

class SimpleVectorStorage(VectorStorage):
    """Simple in-memory vector storage implementation.
    
    This class implements the VectorStorage interface using in-memory
    arrays for storing and searching vector embeddings.
    
    Args:
        dimension: Dimension of vectors to store.
    """
    
    def __init__(self, dimension: int = 768):
        """Initialize a SimpleVectorStorage."""
        self.dimension = dimension
        self.vectors = []
        self.metadata = []
        self.ids = []
        
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
        # Validate vectors
        for vector in vectors:
            if len(vector) != self.dimension:
                raise ValueError(f"Vector dimension mismatch: expected {self.dimension}, got {len(vector)}")
                
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
            
        # Add vectors, metadata, and IDs
        self.vectors.extend(vectors)
        self.metadata.extend(metadata)
        self.ids.extend(ids)
        
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
        if not self.vectors:
            return []
            
        # Validate query vector
        if len(query_vector) != self.dimension:
            raise ValueError(f"Query vector dimension mismatch: expected {self.dimension}, got {len(query_vector)}")
            
        # Convert to numpy arrays
        query_np = np.array(query_vector).reshape(1, -1)
        vectors_np = np.array(self.vectors)
        
        # Compute similarities
        similarities = cosine_similarity(query_np, vectors_np)[0]
        
        # Apply filter if provided
        filtered_indices = []
        if filter:
            for i, meta in enumerate(self.metadata):
                match = True
                for key, value in filter.items():
                    if key not in meta or meta[key] != value:
                        match = False
                        break
                if match:
                    filtered_indices.append(i)
        else:
            filtered_indices = list(range(len(self.vectors)))
            
        # Sort by similarity
        results = []
        for i in sorted(filtered_indices, key=lambda i: similarities[i], reverse=True)[:top_k]:
            results.append({
                "id": self.ids[i],
                "vector": self.vectors[i],
                "metadata": self.metadata[i],
                "score": float(similarities[i])
            })
            
        return results
    
    def get(self, id: str) -> Optional[Dict[str, Any]]:
        """Get a vector by ID.
        
        Args:
            id: ID of the vector to get.
            
        Returns:
            Optional[Dict[str, Any]]: Vector data if found, None otherwise.
        """
        try:
            index = self.ids.index(id)
            return {
                "id": id,
                "vector": self.vectors[index],
                "metadata": self.metadata[index]
            }
        except ValueError:
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
            
        success = True
        for id in ids:
            try:
                index = self.ids.index(id)
                self.ids.pop(index)
                self.vectors.pop(index)
                self.metadata.pop(index)
            except ValueError:
                success = False
                
        return success
    
    def count(self) -> int:
        """Get the number of vectors in the storage.
        
        Returns:
            int: Number of vectors.
        """
        return len(self.vectors)
