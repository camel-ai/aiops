import networkx as nx
from typing import Any, Dict, List, Optional, Union, Tuple
import json
import os

from . import GraphStorage

class NetworkXGraphStorage(GraphStorage):
    """Graph storage implementation using NetworkX.
    
    This class implements the GraphStorage interface using NetworkX
    for storing and manipulating graph data structures.
    
    Args:
        storage_path: Optional path to save the graph to disk.
        directed: Whether the graph is directed.
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        directed: bool = True
    ):
        """Initialize a NetworkXGraphStorage."""
        self.storage_path = storage_path
        self.directed = directed
        
        # Create graph
        if directed:
            self.graph = nx.DiGraph()
        else:
            self.graph = nx.Graph()
            
        # Load from disk if storage path is provided and file exists
        if storage_path and os.path.exists(storage_path):
            self.load()
        
    def save(self) -> bool:
        """Save the graph to disk.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.storage_path:
            return False
            
        try:
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Convert graph to serializable format
            data = nx.node_link_data(self.graph)
            
            # Save to file
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
                
            return True
        except Exception:
            return False
            
    def load(self) -> bool:
        """Load the graph from disk.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.storage_path or not os.path.exists(self.storage_path):
            return False
            
        try:
            # Load from file
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Convert to NetworkX graph
            if self.directed:
                self.graph = nx.node_link_graph(data, directed=True)
            else:
                self.graph = nx.node_link_graph(data, directed=False)
                
            return True
        except Exception:
            return False
    
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
        try:
            self.graph.add_node(node_id, **(properties or {}))
            
            # Save to disk if storage path is provided
            if self.storage_path:
                self.save()
                
            return True
        except Exception:
            return False
    
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
        try:
            # Ensure nodes exist
            if source_id not in self.graph:
                self.add_node(source_id)
                
            if target_id not in self.graph:
                self.add_node(target_id)
                
            # Prepare edge properties
            edge_props = properties or {}
            if edge_type:
                edge_props['type'] = edge_type
                
            # Add edge
            self.graph.add_edge(source_id, target_id, **edge_props)
            
            # Save to disk if storage path is provided
            if self.storage_path:
                self.save()
                
            return True
        except Exception:
            return False
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by ID.
        
        Args:
            node_id: ID of the node to get.
            
        Returns:
            Optional[Dict[str, Any]]: Node data if found, None otherwise.
        """
        if node_id not in self.graph:
            return None
            
        # Get node attributes
        attrs = dict(self.graph.nodes[node_id])
        
        # Add ID to result
        return {
            'id': node_id,
            **attrs
        }
    
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
        results = []
        
        # Get all edges
        if source_id and target_id:
            # Get specific edge
            if self.graph.has_edge(source_id, target_id):
                edges = [(source_id, target_id, self.graph.edges[source_id, target_id])]
            else:
                edges = []
        elif source_id:
            # Get outgoing edges
            edges = [(source_id, target, attrs) for target, attrs in self.graph[source_id].items()]
        elif target_id:
            # Get incoming edges
            edges = [(source, target_id, attrs) for source, attrs in self.graph.pred[target_id].items()]
        else:
            # Get all edges
            edges = [(source, target, attrs) for source, target, attrs in self.graph.edges(data=True)]
            
        # Filter by edge type if specified
        for source, target, attrs in edges:
            if edge_type is None or attrs.get('type') == edge_type:
                results.append({
                    'source': source,
                    'target': target,
                    **attrs
                })
                
        return results
    
    def delete_node(self, node_id: str) -> bool:
        """Delete a node by ID.
        
        Args:
            node_id: ID of the node to delete.
            
        Returns:
            bool: True if successful, False otherwise.
        """
        if node_id not in self.graph:
            return False
            
        try:
            self.graph.remove_node(node_id)
            
            # Save to disk if storage path is provided
            if self.storage_path:
                self.save()
                
            return True
        except Exception:
            return False
    
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
        if not self.graph.has_edge(source_id, target_id):
            return False
            
        # Check edge type if specified
        if edge_type is not None:
            edge_attrs = self.graph.edges[source_id, target_id]
            if edge_attrs.get('type') != edge_type:
                return False
                
        try:
            self.graph.remove_edge(source_id, target_id)
            
            # Save to disk if storage path is provided
            if self.storage_path:
                self.save()
                
            return True
        except Exception:
            return False
