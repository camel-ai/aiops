from typing import List, Dict, Any, Optional
import numpy as np
from rank_bm25 import BM25Okapi
import re

from .base import BaseRetriever


class BM25Retriever(BaseRetriever):
    """Retriever using BM25 algorithm for document retrieval.
    
    This class implements the BaseRetriever interface using the BM25 algorithm
    to retrieve relevant documents based on keyword matching.
    
    Args:
        tokenizer: Optional custom tokenizer function.
        collection_name: Optional name for the document collection.
    """
    
    def __init__(
        self,
        tokenizer: Optional[Any] = None,
        collection_name: str = "default"
    ):
        """Initialize a BM25Retriever."""
        super().__init__()
        self.tokenizer = tokenizer or self._default_tokenizer
        self.collection_name = collection_name
        self.documents = []
        self.bm25 = None
        self.corpus = []
        
    def _default_tokenizer(self, text: str) -> List[str]:
        """Default tokenization function.
        
        Args:
            text: Text to tokenize.
            
        Returns:
            List[str]: List of tokens.
        """
        # Simple tokenization: lowercase, remove punctuation, split on whitespace
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        return text.split()
        
    def process(
        self,
        documents: List[Dict[str, Any]],
        text_field: str = "text",
        **kwargs
    ) -> None:
        """Process documents and build BM25 index.
        
        Args:
            documents: List of documents to process.
            text_field: Field in documents to use for indexing.
            **kwargs: Additional arguments.
        """
        self.documents = documents
        
        # Extract and tokenize text
        self.corpus = []
        for doc in documents:
            text = doc.get(text_field, "")
            tokens = self.tokenizer(text)
            self.corpus.append(tokens)
            
        # Create BM25 index
        self.bm25 = BM25Okapi(self.corpus)
    
    def query(
        self,
        query: str,
        top_k: int = 5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Query for relevant documents using BM25.
        
        Args:
            query: Query string.
            top_k: Number of top results to return.
            **kwargs: Additional arguments.
            
        Returns:
            List[Dict[str, Any]]: List of relevant documents with scores.
        """
        if not self.documents or not self.bm25:
            return []
            
        # Tokenize query
        query_tokens = self.tokenizer(query)
        
        # Get BM25 scores
        scores = self.bm25.get_scores(query_tokens)
        
        # Get top-k results
        results = []
        for i, score in sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:top_k]:
            if score <= 0:
                continue
                
            # Add document with score
            doc = self.documents[i].copy()
            doc["score"] = float(score)
            results.append(doc)
            
        return results
