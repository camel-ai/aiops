from typing import List, Dict, Any, Optional, Union
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .base import BaseRetriever


class VectorRetriever(BaseRetriever):
    """Retriever using vector embeddings for document retrieval.
    
    This class implements the BaseRetriever interface using vector embeddings
    to retrieve relevant documents based on semantic similarity.
    
    Args:
        embedding_model: Optional embedding model or function.
        collection_name: Optional name for the document collection.
    """
    
    def __init__(
        self,
        embedding_model: Optional[Any] = None,
        collection_name: str = "default"
    ):
        """Initialize a VectorRetriever."""
        super().__init__()
        self.embedding_model = embedding_model
        self.collection_name = collection_name
        self.documents = []
        self.document_embeddings = []
        
    def process(
        self,
        documents: List[Dict[str, Any]],
        embedding_field: str = "text",
        **kwargs
    ) -> None:
        """Process documents and compute embeddings.
        
        Args:
            documents: List of documents to process.
            embedding_field: Field in documents to use for embeddings.
            **kwargs: Additional arguments.
        """
        self.documents = documents
        
        # Extract text for embedding
        texts = [doc.get(embedding_field, "") for doc in documents]
        
        # Compute embeddings
        if self.embedding_model:
            # Use provided embedding model
            self.document_embeddings = [
                self.embedding_model(text) for text in texts
            ]
        else:
            # Use simple TF-IDF as fallback
            vectorizer = TfidfVectorizer()
            self.document_embeddings = vectorizer.fit_transform(texts).toarray()
            # Save vectorizer for query embedding
            self.vectorizer = vectorizer
    
    def query(
        self,
        query: str,
        top_k: int = 5,
        threshold: float = 0.0,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Query for relevant documents.
        
        Args:
            query: Query string.
            top_k: Number of top results to return.
            threshold: Minimum similarity threshold.
            **kwargs: Additional arguments.
            
        Returns:
            List[Dict[str, Any]]: List of relevant documents with scores.
        """
        if not self.documents or not self.document_embeddings:
            return []
            
        # Compute query embedding
        if self.embedding_model:
            query_embedding = self.embedding_model(query)
        else:
            # Use TF-IDF vectorizer
            query_embedding = self.vectorizer.transform([query]).toarray()[0]
            
        # Convert embeddings to numpy arrays if they aren't already
        query_embedding = np.array(query_embedding).reshape(1, -1)
        document_embeddings = np.array(self.document_embeddings)
        
        # Compute similarities
        similarities = cosine_similarity(
            query_embedding, document_embeddings
        )[0]
        
        # Get top-k results above threshold
        results = []
        for i, score in sorted(
            enumerate(similarities), key=lambda x: x[1], reverse=True
        ):
            if score < threshold or len(results) >= top_k:
                break
                
            # Add document with score
            doc = self.documents[i].copy()
            doc["score"] = float(score)
            results.append(doc)
            
        return results
