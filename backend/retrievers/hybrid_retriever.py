from typing import List, Dict, Any, Optional, Union
import numpy as np
from collections import defaultdict

from .base import BaseRetriever
from .vector_retriever import VectorRetriever
from .bm25_retriever import BM25Retriever


class HybridRetriever(BaseRetriever):
    """Retriever combining multiple retrieval methods.
    
    This class implements the BaseRetriever interface by combining results
    from multiple retrievers, such as vector-based and keyword-based methods.
    
    Args:
        retrievers: List of retrievers to combine.
        weights: Optional weights for each retriever.
        collection_name: Optional name for the document collection.
    """
    
    def __init__(
        self,
        retrievers: Optional[List[BaseRetriever]] = None,
        weights: Optional[List[float]] = None,
        collection_name: str = "default"
    ):
        """Initialize a HybridRetriever."""
        super().__init__()
        self.retrievers = retrievers or []
        self.weights = weights or [1.0] * len(self.retrievers)
        self.collection_name = collection_name
        
        # Ensure weights match retrievers
        if len(self.weights) != len(self.retrievers):
            self.weights = [1.0] * len(self.retrievers)
            
    def add_retriever(
        self, 
        retriever: BaseRetriever, 
        weight: float = 1.0
    ) -> None:
        """Add a retriever to the hybrid retriever.
        
        Args:
            retriever: Retriever to add.
            weight: Weight for the retriever.
        """
        self.retrievers.append(retriever)
        self.weights.append(weight)
        
    def process(
        self,
        documents: List[Dict[str, Any]],
        **kwargs
    ) -> None:
        """Process documents with all retrievers.
        
        Args:
            documents: List of documents to process.
            **kwargs: Additional arguments passed to each retriever.
        """
        # Process documents with each retriever
        for retriever in self.retrievers:
            retriever.process(documents, **kwargs)
    
    def query(
        self,
        query: str,
        top_k: int = 5,
        fusion_method: str = "reciprocal_rank",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Query for relevant documents using all retrievers.
        
        Args:
            query: Query string.
            top_k: Number of top results to return.
            fusion_method: Method for combining results ("reciprocal_rank", "weighted_score", or "round_robin").
            **kwargs: Additional arguments passed to each retriever.
            
        Returns:
            List[Dict[str, Any]]: List of relevant documents with scores.
        """
        if not self.retrievers:
            return []
            
        # Get results from each retriever
        all_results = []
        for i, retriever in enumerate(self.retrievers):
            results = retriever.query(query, top_k=top_k*2, **kwargs)  # Get more results for better fusion
            weight = self.weights[i]
            all_results.append((results, weight))
            
        # Combine results using the specified fusion method
        if fusion_method == "reciprocal_rank":
            return self._reciprocal_rank_fusion(all_results, top_k)
        elif fusion_method == "weighted_score":
            return self._weighted_score_fusion(all_results, top_k)
        elif fusion_method == "round_robin":
            return self._round_robin_fusion(all_results, top_k)
        else:
            # Default to reciprocal rank fusion
            return self._reciprocal_rank_fusion(all_results, top_k)
            
    def _reciprocal_rank_fusion(
        self,
        all_results: List[tuple],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Combine results using reciprocal rank fusion.
        
        Args:
            all_results: List of (results, weight) tuples.
            top_k: Number of top results to return.
            
        Returns:
            List[Dict[str, Any]]: Combined results.
        """
        # Track document scores by ID
        doc_scores = defaultdict(float)
        doc_map = {}
        
        # Constant for RRF formula
        k = 60
        
        # Calculate RRF scores
        for results, weight in all_results:
            for rank, doc in enumerate(results):
                doc_id = doc.get("id", str(hash(str(doc))))
                # RRF formula: 1 / (rank + k)
                doc_scores[doc_id] += weight * (1.0 / (rank + k))
                doc_map[doc_id] = doc
                
        # Sort by score and return top-k
        top_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)[:top_k]
        
        # Create result list
        results = []
        for doc_id in top_ids:
            doc = doc_map[doc_id].copy()
            doc["score"] = doc_scores[doc_id]
            results.append(doc)
            
        return results
        
    def _weighted_score_fusion(
        self,
        all_results: List[tuple],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Combine results using weighted score fusion.
        
        Args:
            all_results: List of (results, weight) tuples.
            top_k: Number of top results to return.
            
        Returns:
            List[Dict[str, Any]]: Combined results.
        """
        # Track document scores by ID
        doc_scores = defaultdict(float)
        doc_map = {}
        
        # Calculate weighted scores
        for results, weight in all_results:
            for doc in results:
                doc_id = doc.get("id", str(hash(str(doc))))
                # Weighted score
                doc_scores[doc_id] += weight * doc.get("score", 0.0)
                doc_map[doc_id] = doc
                
        # Sort by score and return top-k
        top_ids = sorted(doc_scores.keys(), key=lambda x: doc_scores[x], reverse=True)[:top_k]
        
        # Create result list
        results = []
        for doc_id in top_ids:
            doc = doc_map[doc_id].copy()
            doc["score"] = doc_scores[doc_id]
            results.append(doc)
            
        return results
        
    def _round_robin_fusion(
        self,
        all_results: List[tuple],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Combine results using round robin fusion.
        
        Args:
            all_results: List of (results, weight) tuples.
            top_k: Number of top results to return.
            
        Returns:
            List[Dict[str, Any]]: Combined results.
        """
        # Track seen document IDs
        seen_ids = set()
        results = []
        
        # Round robin selection
        while len(results) < top_k:
            for i, (retriever_results, _) in enumerate(all_results):
                if not retriever_results:
                    continue
                    
                # Get next result
                doc = retriever_results.pop(0)
                doc_id = doc.get("id", str(hash(str(doc))))
                
                # Add if not seen before
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    results.append(doc)
                    
                    # Check if we have enough results
                    if len(results) >= top_k:
                        break
                        
            # Break if all retrievers are empty
            if all(not r for r, _ in all_results):
                break
                
        return results
