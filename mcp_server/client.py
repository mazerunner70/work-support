"""
HTTP Client for Work-Support REST API

Handles HTTP communication between MCP server and work-support REST API,
including error handling, timeout management, and response formatting.
"""
import json
import logging
from typing import Any, Dict, Optional
import httpx
from config import config

logger = logging.getLogger(__name__)


class WorkSupportAPIError(Exception):
    """Exception raised for work-support API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class WorkSupportClient:
    """HTTP client for work-support REST API."""
    
    def __init__(self):
        self.base_url = config.work_support_url.rstrip("/")
        self.headers = config.work_support_headers
        self.timeout = config.request_timeout
        
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to work-support API."""
        url = f"{self.base_url}{endpoint}"
        
        logger.debug(f"Making {method} request to {url} with params: {params}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=data
                )
                
                # Log response status
                logger.debug(f"Response status: {response.status_code}")
                
                # Handle different response status codes
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    raise WorkSupportAPIError(
                        f"Resource not found: {endpoint}",
                        status_code=404,
                        response_data=response.json() if response.content else None
                    )
                elif response.status_code >= 400:
                    error_data = response.json() if response.content else {}
                    raise WorkSupportAPIError(
                        f"API error ({response.status_code}): {error_data.get('detail', 'Unknown error')}",
                        status_code=response.status_code,
                        response_data=error_data
                    )
                else:
                    # Unexpected status code
                    raise WorkSupportAPIError(
                        f"Unexpected response status: {response.status_code}",
                        status_code=response.status_code
                    )
                    
        except httpx.TimeoutException:
            raise WorkSupportAPIError(f"Request timeout after {self.timeout}s")
        except httpx.RequestError as e:
            raise WorkSupportAPIError(f"Request failed: {str(e)}")
        except json.JSONDecodeError:
            raise WorkSupportAPIError("Invalid JSON response from API")
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request to work-support API."""
        return await self._make_request("GET", endpoint, params=params)
    
    async def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make POST request to work-support API."""
        return await self._make_request("POST", endpoint, params=params, data=data)
    
    # Specific API methods
    async def query_issues(
        self,
        assignee: Optional[str] = None,
        status: Optional[str] = None,
        team: Optional[str] = None,
        issue_type: Optional[str] = None,
        parent_key: Optional[str] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Query issues via MCP API endpoint."""
        params = {}
        if assignee is not None:
            params["assignee"] = assignee
        if status is not None:
            params["status"] = status
        if team is not None:
            params["team"] = team
        if issue_type is not None:
            params["issue_type"] = issue_type
        if parent_key is not None:
            params["parent_key"] = parent_key
        if source is not None:
            params["source"] = source
        if limit is not None:
            params["limit"] = limit
            
        return await self.get("/api/mcp/issues", params=params)
    
    async def get_issue_details(
        self,
        issue_key: str,
        include_comments: bool = True,
        include_changelog: bool = True,
        include_children: bool = False
    ) -> Dict[str, Any]:
        """Get detailed issue information."""
        params = {
            "include_comments": include_comments,
            "include_changelog": include_changelog,
            "include_children": include_children
        }
        return await self.get(f"/api/mcp/issues/{issue_key}", params=params)
    
    async def get_issue_descendants(
        self,
        issue_key: str,
        include_comments: bool = True,
        include_changelog: bool = True
    ) -> Dict[str, Any]:
        """Get all descendant issues recursively."""
        params = {
            "include_comments": include_comments,
            "include_changelog": include_changelog
        }
        return await self.get(f"/api/mcp/issues/{issue_key}/descendants", params=params)
    
    async def get_team_metrics(
        self,
        team_name: str,
        date_range: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get team metrics and performance data."""
        params = {}
        if date_range:
            params["date_range"] = date_range
        return await self.get(f"/api/mcp/team/{team_name}/metrics", params=params)
    
    async def test_connectivity(self) -> Dict[str, Any]:
        """Test system connectivity and health."""
        return await self.get("/api/mcp/system/connectivity")
    
    async def trigger_harvest(
        self,
        harvest_type: str = "incremental",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Trigger a harvest job."""
        data = {
            "harvest_type": harvest_type,
            "dry_run": dry_run
        }
        return await self.post("/api/mcp/harvest/trigger", data=data)
    
    async def search_issues_by_comments(
        self,
        issue_type: Optional[str] = None,
        days_ago: int = 10,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """Search issues with comments within a specified time period."""
        params = {
            "days_ago": days_ago
        }
        if issue_type:
            params["issue_type"] = issue_type
        if limit:
            params["limit"] = limit
        return await self.get("/api/mcp/issues/search/by-comments", params=params)
    
    async def get_issue_types(self) -> Dict[str, Any]:
        """Get all issue types with their IDs."""
        return await self.get("/api/mcp/issue-types")


# Global client instance
client = WorkSupportClient() 