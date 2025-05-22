from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Tuple

class GraphStorage(ABC):
    """Abstract base class for graph storage implementations.
    
    This class defines the interface for graph storage systems that can
    store, retrieve, and manipulate graph data structures.
    """
    
    @abstractmethod
    def add_node(
        self, 
        node_id: str, 
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add a node to the graph.
        
        Args:
            node_id: Unique identifier for the node.
            properties: Optional properties for the node.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def add_edge(
        self, 
        source_id: str, 
        target_id: str,
        edge_type: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add an edge between nodes.
        
        Args:
            source_id: ID of the source node.
            target_id: ID of the target node.
            edge_type: Optional type of the edge.
            properties: Optional properties for the edge.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by ID.
        
        Args:
            node_id: ID of the node to get.
            
        Returns:
            Optional[Dict[str, Any]]: Node data if found, None otherwise.
        """
        pass
    
    @abstractmethod
    def get_edges(
        self, 
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        edge_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get edges matching criteria.
        
        Args:
            source_id: Optional ID of the source node.
            target_id: Optional ID of the target node.
            edge_type: Optional type of the edge.
            
        Returns:
            List[Dict[str, Any]]: List of matching edges.
        """
        pass
    
    @abstractmethod
    def delete_node(self, node_id: str) -> bool:
        """Delete a node by ID.
        
        Args:
            node_id: ID of the node to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def delete_edge(
        self, 
        source_id: str, 
        target_id: str,
        edge_type: Optional[str] = None
    ) -> bool:
        """Delete an edge.
        
        Args:
            source_id: ID of the source node.
            target_id: ID of the target node.
            edge_type: Optional type of the edge.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        pass
