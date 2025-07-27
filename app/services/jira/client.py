"""
Jira HTTP client for API requests with authentication and validation.
"""
import logging
import time
from typing import Dict, Any, Optional
import httpx

from app.config.settings import config_manager
from app.models.jira import (
    JiraServiceError,
    JiraEndpointNotWhitelistedError,
    JiraEndpointInfo
)

logger = logging.getLogger(__name__)


class JiraClient:
    """Pure HTTP client for Jira API with authentication and validation."""
    
    def __init__(self):
        """Initialize the Jira client with configuration."""
        self.base_url = config_manager.settings.jira_base_url
        self.email = config_manager.settings.jira_email
        self.api_token = config_manager.settings.jira_api_token
        
        if not self.api_token or not self.email:
            logger.warning("Jira API credentials not configured")

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Jira API."""
        import base64
        
        credentials = f"{self.email}:{self.api_token}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        return {
            "Authorization": f"Basic {encoded_credentials}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def _build_api_url(self, endpoint: str) -> str:
        """Build full API URL for given endpoint."""
        return f"{self.base_url}/rest/api/3/{endpoint.lstrip('/')}"

    def _validate_endpoint(self, endpoint: str, method: str) -> None:
        """
        Validate that the endpoint and method are whitelisted.
        
        Args:
            endpoint: API endpoint path (without base URL)
            method: HTTP method
            
        Raises:
            JiraEndpointNotWhitelistedError: If the endpoint/method is not whitelisted
        """
        if not config_manager.is_endpoint_whitelisted(endpoint, method):
            whitelisted_endpoints = config_manager.get_whitelisted_endpoints()
            if whitelisted_endpoints:
                available_endpoints = []
                for ep in whitelisted_endpoints.values():
                    available_endpoints.append(f"{ep.path} ({', '.join(ep.methods)})")
                
                error_msg = (
                    f"Endpoint '{endpoint}' with method '{method}' is not whitelisted. "
                    f"Available endpoints: {', '.join(available_endpoints)}"
                )
            else:
                error_msg = f"Endpoint '{endpoint}' with method '{method}' is not whitelisted (no whitelist loaded)"
            
            logger.error(error_msg)
            raise JiraEndpointNotWhitelistedError(error_msg)

    async def make_request(
        self, 
        method: str, 
        endpoint: str, 
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> httpx.Response:
        """
        Make HTTP request to Jira API with common error handling and whitelist validation.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            payload: Optional JSON payload for POST requests
            timeout: Request timeout in seconds
            
        Returns:
            HTTP response object
            
        Raises:
            JiraServiceError: If request fails
            JiraEndpointNotWhitelistedError: If endpoint is not whitelisted
        """
        # Validate endpoint against whitelist
        self._validate_endpoint(endpoint, method)
        
        url = self._build_api_url(endpoint)
        headers = self._get_auth_headers()
        
        # Start timing the request
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                # Log outgoing request
                logger.info(f"JIRA API → {method} {endpoint}")
                
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, timeout=timeout)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=payload, timeout=timeout)
                else:
                    raise JiraServiceError(f"Unsupported HTTP method: {method}")
                
                # Calculate duration
                duration = time.time() - start_time
                
                # Log response with status code and timing
                logger.info(f"JIRA API ← {method} {endpoint} - {response.status_code} - {duration:.3f}s")
                return response
                
        except httpx.TimeoutException:
            duration = time.time() - start_time
            error_msg = f"JIRA API ← {method} {endpoint} - TIMEOUT - {duration:.3f}s"
            logger.error(error_msg)
            raise JiraServiceError(f"Request timeout for {method} {endpoint}")
        except httpx.RequestError as e:
            duration = time.time() - start_time
            error_msg = f"JIRA API ← {method} {endpoint} - ERROR - {duration:.3f}s - {e}"
            logger.error(error_msg)
            raise JiraServiceError(f"Request error for {method} {endpoint}: {e}")

    def handle_response(
        self, 
        response: httpx.Response, 
        operation: str,
        success_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle HTTP response with common error patterns.
        
        Args:
            response: HTTP response object
            operation: Description of the operation for error messages
            success_message: Optional success message to log
            
        Returns:
            Parsed JSON response data
            
        Raises:
            JiraServiceError: If response indicates an error
        """
        if response.status_code == 200:
            data = response.json()
            if success_message:
                logger.info(success_message)
            return data
        elif response.status_code == 400:
            error_msg = f"Bad request for {operation}: {response.text}"
            logger.error(error_msg)
            raise JiraServiceError(error_msg)
        elif response.status_code == 401:
            error_msg = f"Authentication failed for {operation}"
            logger.error(error_msg)
            raise JiraServiceError(error_msg)
        elif response.status_code == 403:
            error_msg = f"Access forbidden for {operation}"
            logger.error(error_msg)
            raise JiraServiceError(error_msg)
        else:
            error_msg = f"{operation} failed: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise JiraServiceError(error_msg)

    async def test_connection(self) -> bool:
        """Test connection to Jira API."""
        try:
            response = await self.make_request("GET", "myself")
            data = self.handle_response(response, "connection test")
            
            logger.info(f"Jira connection successful for user: {data.get('displayName', 'Unknown')}")
            return True
            
        except JiraServiceError:
            return False
        except Exception as e:
            logger.error(f"Unexpected error testing Jira connection: {e}")
            return False

    def get_whitelisted_endpoints_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all whitelisted endpoints for debugging/monitoring.
        
        Returns:
            Dictionary with endpoint information
        """
        endpoints_info = {}
        for key, endpoint in config_manager.get_whitelisted_endpoints().items():
            endpoints_info[key] = {
                "path": endpoint.path,
                "methods": endpoint.methods,
                "description": endpoint.description
            }
        return endpoints_info 