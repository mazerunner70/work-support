"""
Jira API integration service for data harvesting.
"""
import asyncio
import logging
import json
import re
import time
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
import httpx
from pydantic import BaseModel

from app.config.settings import config_manager
from app.utils.jql_builder import JQLBuilder
from app.models.schemas import JiraCommentSchema

logger = logging.getLogger(__name__)


class JiraIssue(BaseModel):
    """Represents a Jira issue with relevant fields."""
    key: str
    issue_id: Optional[str] = None  # Maps to "id" field in response
    summary: str
    assignee: Optional[str] = None
    status: str
    labels: List[str] = []
    issue_type_id: int
    issue_type_name: str
    parent_key: Optional[str] = None
    team: Optional[str] = None  # Team from customfield_10001
    start_date: Optional[datetime] = None  # Start date from customfield_14339
    transition_date: Optional[datetime] = None  # Transition date from customfield_14343
    end_date: Optional[datetime] = None  # End date from customfield_13647
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    comments: List[JiraCommentSchema] = []  # Issue comments
    blacklist_reason: Optional[str] = None  # Reason issue was blacklisted, None if allowed


class JiraServiceError(Exception):
    """Custom exception for Jira service errors."""
    pass


class JiraEndpointNotWhitelistedError(JiraServiceError):
    """Exception raised when trying to access a non-whitelisted endpoint."""
    pass


class JiraService:
    """Service for interacting with Jira API."""

    def __init__(self):
        self.base_url = config_manager.settings.jira_base_url
        self.email = config_manager.settings.jira_email
        self.api_token = config_manager.settings.jira_api_token
        self.jql_builder = JQLBuilder()
        
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

    async def _make_request(
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

    def _handle_response(
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
            response = await self._make_request("GET", "myself")
            data = self._handle_response(response, "connection test")
            
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

    async def search_issues(self, jql_query: str, max_results: int = 1000, 
                          fields: Optional[List[str]] = None) -> List[JiraIssue]:
        """
        Search for issues using JQL query with pagination support.
        
        Args:
            jql_query: JQL query string
            max_results: Maximum total results to return (default 1000, 0 = no limit)
            fields: Optional list of fields to retrieve for efficiency
            
        Returns:
            List of JiraIssue objects
            
        Raises:
            JiraServiceError: If the search fails
            JiraEndpointNotWhitelistedError: If search endpoint is not whitelisted
        """
        try:
            if not self.jql_builder.validate_jql_syntax(jql_query):
                raise JiraServiceError(f"Invalid JQL syntax: {jql_query}")

            all_issues = []
            blacklisted_count = 0
            start_at = 0
            page_size = 100
            
            while True:
                payload = {
                    "jql": jql_query,
                    "startAt": start_at,
                    "maxResults": page_size,
                    "fields": fields or [
                        "key", "summary", "assignee", "status", "labels",
                        "issuetype", "parent", "created", "updated", "comment",
                        "customfield_10001",  # Team field
                        "customfield_14339",  # Start date
                        "customfield_14343",  # Transition date  
                        "customfield_13647"   # End date
                    ]
                }
                
                response = await self._make_request("POST", "search", payload, timeout=60.0)
                data = self._handle_response(
                    response, 
                    "issue search",
                    f"Retrieved page {start_at//page_size + 1} from Jira for query: {jql_query}"
                )
                
                page_issues = []
                for issue_data in data.get("issues", []):
                    try:
                        issue_key = issue_data.get('key', '')
                        jira_issue = self._parse_issue(issue_data)
                        
                        # Determine blacklist reason
                        blacklist_reason = None
                        if config_manager.is_project_blacklisted(issue_key):
                            blacklist_reason = "project"
                        elif jira_issue.team and config_manager.is_team_blacklisted(jira_issue.team):
                            blacklist_reason = f"team:{jira_issue.team}"
                        elif config_manager.is_status_blacklisted(jira_issue.status):
                            blacklist_reason = f"status:{jira_issue.status}"
                        
                        # Set blacklist reason on issue
                        jira_issue.blacklist_reason = blacklist_reason
                        
                        # Skip blacklisted issues
                        if blacklist_reason:
                            blacklisted_count += 1
                            logger.debug(f"Skipping blacklisted issue: {issue_key} (reason: {blacklist_reason})")
                            continue
                        
                        page_issues.append(jira_issue)
                    except Exception as e:
                        logger.warning(f"Error parsing issue {issue_data.get('key', 'Unknown')}: {e}")
                        continue
                
                all_issues.extend(page_issues)
                
                # Check if we have more pages and haven't hit our limit
                total = data.get("total", 0)
                start_at += page_size
                
                if start_at >= total or (max_results > 0 and len(all_issues) >= max_results):
                    break
            
            # Trim to max_results if specified
            if max_results > 0 and len(all_issues) > max_results:
                all_issues = all_issues[:max_results]
            
            if blacklisted_count > 0:
                logger.info(f"Filtered out {blacklisted_count} blacklisted issues")
            logger.info(f"Successfully parsed {len(all_issues)} issues from {total} total found")
            return all_issues
                    
        except (JiraServiceError, JiraEndpointNotWhitelistedError):
            raise
        except Exception as e:
            error_msg = f"Unexpected error during Jira search: {e}"
            logger.error(error_msg)
            raise JiraServiceError(error_msg)



    def _parse_issue(self, issue_data: Dict[str, Any]) -> JiraIssue:
        """Parse Jira issue data into JiraIssue object."""
        fields = issue_data.get("fields", {})
        
        # Parse assignee
        assignee = None
        if assignee_data := fields.get("assignee"):
            assignee = assignee_data.get("emailAddress") or assignee_data.get("displayName")
        
        # Parse issue type
        issue_type = fields.get("issuetype", {})
        issue_type_id = int(issue_type.get("id", -1))
        issue_type_name = issue_type.get("name", "Unknown")
        
        # Parse parent
        parent_key = None
        if parent_data := fields.get("parent"):
            parent_key = parent_data.get("key")
        
        # Parse team from customfield_10001
        team = None
        if team_data := fields.get("customfield_10001"):
            # Handle different possible formats for the team field
            if isinstance(team_data, str):
                team = team_data
            elif isinstance(team_data, dict):
                # If it's an object, try common field names
                team = team_data.get("value") or team_data.get("name") or team_data.get("displayName") or str(team_data)
            elif team_data is not None:
                team = str(team_data)
        
        # Parse custom date fields
        start_date = self._parse_custom_date(fields.get("customfield_14339"))
        transition_date = self._parse_custom_date(fields.get("customfield_14343"))
        end_date = self._parse_custom_date(fields.get("customfield_13647"))
        
        # Parse dates
        created, updated = self._parse_dates(fields, issue_data.get("key"))
        
        # Parse comments
        comments = self._parse_comments(fields.get("comment", {}))
        
        # Map assignee to anonymised name
        from app.config.settings import config_manager
        anonymised_assignee = config_manager.get_anonymised_name_for_assignee(assignee) if assignee else assignee

        return JiraIssue(
            key=issue_data.get("key", ""),
            issue_id=issue_data.get("id"),
            summary=fields.get("summary", ""),
            assignee=anonymised_assignee,
            status=fields.get("status", {}).get("name", "Unknown"),
            labels=fields.get("labels", []),
            issue_type_id=issue_type_id,
            issue_type_name=issue_type_name,
            parent_key=parent_key,
            team=team,
            start_date=start_date,
            transition_date=transition_date,
            end_date=end_date,
            created=created,
            updated=updated,
            comments=comments
        )

    def _parse_dates(self, fields: Dict[str, Any], issue_key: Optional[str] = None) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Parse created and updated dates from issue fields."""
        created = None
        updated = None
        
        try:
            if created_str := fields.get("created"):
                created = self._parse_iso_datetime(created_str)
            if updated_str := fields.get("updated"):
                updated = self._parse_iso_datetime(updated_str)
        except Exception as e:
            logger.warning(f"Error parsing dates for issue {issue_key or 'Unknown'}: {e}")
        
        return created, updated

    def _parse_comments(self, comment_data: Dict[str, Any]) -> List[JiraCommentSchema]:
        """Parse comments from Jira issue comment field."""
        comments = []
        
        try:
            # Jira comment field structure: {"comments": [array of comment objects]}
            comment_list = comment_data.get("comments", [])
            
            for comment_obj in comment_list:
                try:
                    # Extract comment body (could be in body or rendered body)
                    body = comment_obj.get("body", "")
                    if isinstance(body, dict):
                        # Handle ADF (Atlassian Document Format) or other structured content
                        body = str(body)  # Convert to string representation for now
                    
                    # Parse comment dates
                    created = None
                    if created_str := comment_obj.get("created"):
                        created = self._parse_iso_datetime(created_str)
                    
                    updated = None
                    if updated_str := comment_obj.get("updated"):
                        updated = self._parse_iso_datetime(updated_str)
                    
                    comments.append(JiraCommentSchema(
                        body=body,
                        created=created,
                        updated=updated
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing individual comment: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error parsing comments: {e}")
        
        return comments

    def _parse_iso_datetime(self, date_str: str) -> datetime:
        """
        Parse ISO datetime string with various timezone formats.
        
        Handles formats like:
        - 2025-04-24T16:32:35.307Z
        - 2025-04-24T16:32:35.307+0100
        - 2025-04-24T16:32:35.307+01:00
        """
        # Handle 'Z' timezone indicator
        if date_str.endswith('Z'):
            date_str = date_str.replace('Z', '+00:00')
        
        # Handle timezone offsets without colon (e.g., +0100 -> +01:00)
        # Match timezone offset pattern at the end: +/-HHMM
        tz_pattern = r'([+-])(\d{2})(\d{2})$'
        match = re.search(tz_pattern, date_str)
        if match:
            sign, hours, minutes = match.groups()
            # Replace with colon format: +/-HH:MM
            date_str = re.sub(tz_pattern, f'{sign}{hours}:{minutes}', date_str)
        
        return datetime.fromisoformat(date_str)

    def _parse_custom_date(self, date_value: Any) -> Optional[datetime]:
        """
        Parse a custom date field from Jira.
        
        Handles various formats that custom date fields might return:
        - ISO date strings
        - Date objects
        - None/null values
        """
        if date_value is None:
            return None
            
        try:
            if isinstance(date_value, str):
                # Use the existing ISO datetime parser
                return self._parse_iso_datetime(date_value)
            elif isinstance(date_value, dict):
                # If it's an object, look for common date field names
                date_str = date_value.get("value") or date_value.get("date") or date_value.get("displayValue")
                if date_str:
                    return self._parse_iso_datetime(date_str)
            elif hasattr(date_value, 'isoformat'):
                # If it's already a datetime object
                return date_value
            else:
                # Try to convert to string and parse
                return self._parse_iso_datetime(str(date_value))
        except Exception as e:
            logger.warning(f"Error parsing custom date field '{date_value}': {e}")
            return None

    async def get_issue_types(self) -> Dict[int, str]:
        """
        Get all available issue types from Jira.
        
        Returns:
            Dictionary mapping issue type ID to name
            
        Raises:
            JiraEndpointNotWhitelistedError: If issuetype endpoint is not whitelisted
        """
        try:
            response = await self._make_request("GET", "issuetype")
            data = self._handle_response(response, "get issue types")
            
            issue_types = {int(issue_type["id"]): issue_type["name"] for issue_type in data}
            logger.info(f"Retrieved {len(issue_types)} issue types from Jira")
            return issue_types
                    
        except (JiraServiceError, JiraEndpointNotWhitelistedError):
            logger.error("Failed to get issue types")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error getting issue types: {e}")
            return {}

    async def search_product_versions(self, projects: List[str], label: str) -> List[JiraIssue]:
        """
        Search for Product Version issues.
        
        Args:
            projects: List of project keys
            label: Label to filter by
            
        Returns:
            List of Product Version issues
        """
        jql_query = self.jql_builder.build_initial_product_version_query(projects, label)
        logger.info(f"Searching for Product Versions with JQL: {jql_query}")
        return await self.search_issues(jql_query)

    async def search_child_issues(self, parent_key: str, child_type_names: List[str]) -> List[JiraIssue]:
        """
        Search for child issues of a specific parent.
        
        Args:
            parent_key: Key of the parent issue
            child_type_names: List of child issue type names
            
        Returns:
            List of child issues
        """
        if not child_type_names:
            return []
            
        jql_query = self.jql_builder.build_child_issues_query(parent_key, child_type_names)
        logger.info(f"Searching for children of {parent_key} with JQL: {jql_query}")
        return await self.search_issues(jql_query)

    async def search_team_member_issues(self, assignee_email: str, label: str, 
                                       issue_types: Optional[List[str]] = None) -> List[JiraIssue]:
        """
        Search for issues assigned to a specific team member.
        
        Args:
            assignee_email: Email of the team member
            label: Label to filter by
            issue_types: Optional list of issue types to filter by
            
        Returns:
            List of issues assigned to the team member
        """
        jql_query = self.jql_builder.build_team_member_query(assignee_email, label, issue_types)
        logger.info(f"Searching for issues assigned to {assignee_email} with JQL: {jql_query}")
        return await self.search_issues(jql_query)

    async def bulk_fetch_changelogs(self, issue_ids: List[str], chunk_size: int = 100) -> List[Dict[str, Any]]:
        """
        Bulk fetch changelogs for multiple issues efficiently.
        
        Args:
            issue_ids: List of Jira issue IDs to fetch changelogs for
            chunk_size: Number of issues to process per API call (max 100)
            
        Returns:
            List of changelog data from Jira API
        """
        if not issue_ids:
            return []
            
        endpoint = "changelog/bulkfetch"
        method = "POST"
        
        # Validate endpoint
        self._validate_endpoint(endpoint, method)
        
        all_changelogs = []
        
        # Process in chunks to respect API limits
        for i in range(0, len(issue_ids), chunk_size):
            chunk = issue_ids[i:i + chunk_size]
            
            logger.info(f"Fetching changelogs for {len(chunk)} issues (chunk {i//chunk_size + 1})")
            
            # Handle pagination within each chunk
            next_page_token = None
            chunk_total_changelogs = 0
            page_num = 1
            
            while True:  # Continue until no more pages
                payload = {
                    "issueIdsOrKeys": chunk,
                    "maxResults": 1000  # Request maximum results per page
                }
                
                # Add pagination token if we have one
                if next_page_token:
                    payload["nextPageToken"] = next_page_token
                
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        url = self._build_api_url(endpoint)
                        headers = self._get_auth_headers()
                        
                        response = await client.post(url, headers=headers, json=payload)
                        response.raise_for_status()
                        
                        chunk_data = response.json()
                        
                        # Log response parsing details
                        if isinstance(chunk_data, dict):
                            if "values" in chunk_data:
                                values = chunk_data["values"]
                                if isinstance(values, list):
                                    logger.info(f"🔍 PARSE: Found {len(values)} changelog entries in response")
                                    if len(values) > 0:
                                        first_entry = values[0]
                                        if isinstance(first_entry, dict):
                                            logger.info(f"🔍 PARSE: Changelog entry structure: {list(first_entry.keys())}")
                                    else:
                                        logger.warning(f"🔍 PARSE: Response values array is empty - no changelog data")
                                else:
                                    logger.error(f"🔍 PARSE: Response values is not a list: {type(values)}")
                            else:
                                logger.error(f"🔍 PARSE: Response missing 'values' key - available keys: {list(chunk_data.keys())}")
                        else:
                            logger.error(f"🔍 PARSE: Response is not a JSON object: {type(chunk_data)}")
                        
                        # Extract changelog data
                        page_changelogs_count = 0
                        if "values" in chunk_data:
                            page_changelogs = chunk_data["values"]
                            all_changelogs.extend(page_changelogs)
                            page_changelogs_count = len(page_changelogs)
                            chunk_total_changelogs += page_changelogs_count
                        
                        logger.info(f"Loaded {page_changelogs_count} changelog entries from chunk {i//chunk_size + 1}, page {page_num}")
                        
                        # Check for next page
                        next_page_token = chunk_data.get("nextPageToken")
                        if not next_page_token:
                            break  # No more pages
                        
                        page_num += 1
                        
                        # Rate limiting between pages
                        await asyncio.sleep(0.1)
                        
                except httpx.HTTPStatusError as e:
                    logger.error(f"HTTP error fetching changelogs for chunk {i//chunk_size + 1}, page {page_num}: {e}")
                    break  # Exit pagination loop on error
                except Exception as e:
                    logger.error(f"Error fetching changelogs for chunk {i//chunk_size + 1}, page {page_num}: {e}")
                    break  # Exit pagination loop on error
            
            logger.info(f"Chunk {i//chunk_size + 1} complete: {chunk_total_changelogs} total changelog entries across {page_num} pages")
            
            # Rate limiting - small delay between chunks
            if i + chunk_size < len(issue_ids):
                await asyncio.sleep(0.2)
        
        logger.info(f"🔍 PARSE: Total changelog entries parsed: {len(all_changelogs)} from {len(issue_ids)} issues")
        
        logger.info(f"Successfully fetched changelogs for {len(all_changelogs)} issue/changelog combinations")
        return all_changelogs


# Global instance
jira_service = JiraService() 