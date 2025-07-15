from typing import List, Dict, Any, Optional
import subprocess
import json
import os

from .base import BaseToolkit
from .function_tool import FunctionTool


class E2BSandboxToolkit(BaseToolkit):
    """Toolkit for interacting with E2B sandbox for deployment and testing.
    
    This toolkit provides tools for deploying applications, testing deployments,
    and querying cloud data.
    
    Args:
        sandbox_url: URL of the E2B sandbox service.
        api_key: Optional API key for authentication.
        timeout: Optional timeout for API calls.
    """
    
    def __init__(
        self,
        sandbox_url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        timeout: Optional[float] = 60.0
    ):
        """Initialize the E2BSandboxToolkit."""
        super().__init__(timeout=timeout)
        self.sandbox_url = sandbox_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def deploy_application(
        self,
        app_dir: str,
        app_type: str = "static",
        env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Deploy an application to the sandbox.
        
        Args:
            app_dir: Directory containing the application code.
            app_type: Type of application (static, nodejs, python, etc.).
            env_vars: Optional environment variables for the application.
            
        Returns:
            Dict[str, Any]: Deployment result.
        """
        # Validate app directory
        if not os.path.isdir(app_dir):
            return {
                "error": f"Directory not found: {app_dir}",
                "status": "failed",
                "url": None
            }
            
        # Prepare deployment command
        cmd = [
            "curl", "-s", "-X", "POST",
            f"{self.sandbox_url}/api/deploy",
            "-H", "Content-Type: application/json",
        ]
        
        if self.api_key:
            cmd.extend(["-H", f"Authorization: Bearer {self.api_key}"])
            
        # Prepare payload
        payload = {
            "app_dir": app_dir,
            "app_type": app_type
        }
        
        if env_vars:
            payload["env_vars"] = env_vars
            
        cmd.extend(["-d", json.dumps(payload)])
            
        try:
            # Execute deployment command
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            return {
                "error": f"Deployment failed: {e.stderr}",
                "status": "failed",
                "url": None
            }
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse deployment response",
                "status": "failed",
                "url": None
            }
    
    def test_deployment(
        self,
        url: str,
        test_type: str = "http",
        test_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Test a deployed application.
        
        Args:
            url: URL of the deployed application.
            test_type: Type of test to run (http, load, etc.).
            test_params: Optional parameters for the test.
            
        Returns:
            Dict[str, Any]: Test results.
        """
        # Prepare test command
        cmd = [
            "curl", "-s", "-X", "POST",
            f"{self.sandbox_url}/api/test",
            "-H", "Content-Type: application/json",
        ]
        
        if self.api_key:
            cmd.extend(["-H", f"Authorization: Bearer {self.api_key}"])
            
        # Prepare payload
        payload = {
            "url": url,
            "test_type": test_type
        }
        
        if test_params:
            payload["test_params"] = test_params
            
        cmd.extend(["-d", json.dumps(payload)])
            
        try:
            # Execute test command
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            return {
                "error": f"Test failed: {e.stderr}",
                "status": "failed",
                "results": None
            }
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse test response",
                "status": "failed",
                "results": None
            }
    
    def query_cloud_data(
        self,
        query_type: str,
        query_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Query cloud data.
        
        Args:
            query_type: Type of query (resources, costs, metrics, etc.).
            query_params: Parameters for the query.
            
        Returns:
            Dict[str, Any]: Query results.
        """
        # Prepare query command
        cmd = [
            "curl", "-s", "-X", "POST",
            f"{self.sandbox_url}/api/query",
            "-H", "Content-Type: application/json",
        ]
        
        if self.api_key:
            cmd.extend(["-H", f"Authorization: Bearer {self.api_key}"])
            
        # Prepare payload
        payload = {
            "query_type": query_type,
            "query_params": query_params
        }
            
        cmd.extend(["-d", json.dumps(payload)])
            
        try:
            # Execute query command
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            return {
                "error": f"Query failed: {e.stderr}",
                "status": "failed",
                "results": None
            }
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse query response",
                "status": "failed",
                "results": None
            }
