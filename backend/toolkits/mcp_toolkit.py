from typing import List, Dict, Any, Optional
import requests
import json

from .base import BaseToolkit
from .function_tool import FunctionTool


class MCPToolkit(BaseToolkit):
    """Toolkit for interacting with MCP (Multi-Cloud Platform) services.
    
    This toolkit provides tools for querying knowledge bases and interacting
    with the MCP server.
    
    Args:
        mcp_url: URL of the MCP server.
        api_key: Optional API key for authentication.
        timeout: Optional timeout for API calls.
    """
    
    def __init__(
        self,
        mcp_url: str,
        api_key: Optional[str] = None,
        timeout: Optional[float] = 30.0
    ):
        """Initialize the MCPToolkit."""
        super().__init__(timeout=timeout)
        self.mcp_url = mcp_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def query_knowledge_base(
        self,
        query: str,
        kb_name: Optional[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """Query the knowledge base for relevant information.
        
        Args:
            query: The query string.
            kb_name: Optional name of the knowledge base to query.
            top_k: Number of top results to return.
            
        Returns:
            Dict[str, Any]: Query results.
        """
        endpoint = f"{self.mcp_url}/api/knowledge/query"
        
        payload = {
            "query": query,
            "top_k": top_k
        }
        
        if kb_name:
            payload["kb_name"] = kb_name
            
        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed",
                "results": []
            }
    
    def deploy_resource(
        self,
        resource_type: str,
        config: Dict[str, Any],
        cloud_provider: str = "aws"
    ) -> Dict[str, Any]:
        """Deploy a resource to the cloud.
        
        Args:
            resource_type: Type of resource to deploy (e.g., "vm", "database").
            config: Configuration for the resource.
            cloud_provider: Cloud provider to use.
            
        Returns:
            Dict[str, Any]: Deployment result.
        """
        endpoint = f"{self.mcp_url}/api/deploy"
        
        payload = {
            "resource_type": resource_type,
            "config": config,
            "cloud_provider": cloud_provider
        }
            
        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "error": str(e),
                "status": "failed",
                "deployment_id": None
            }
    
    def check_deployment_status(
        self,
        deployment_id: str
    ) -> Dict[str, Any]:
        """Check the status of a deployment.
        
        Args:
            deployment_id: ID of the deployment to check.
            
        Returns:
            Dict[str, Any]: Deployment status.
        """
        endpoint = f"{self.mcp_url}/api/deploy/status"
        
        payload = {
            "deployment_id": deployment_id
        }
            
        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                "error": str(e),
                "status": "unknown"
            }
