"""
Main Jira service that orchestrates all operations.
"""
import logging
from typing import List, Dict, Any, Optional

from app.services.jira.client import JiraClient
from app.services.jira.parsers import JiraDataParser
from app.services.jira.operations.search import JiraSearchOperations
from app.services.jira.operations.changelog import JiraChangelogOperations
from app.services.jira.operations.metadata import JiraMetadataOperations
from app.utils.jql_builder import JQLBuilder
from app.models.jira import JiraIssue

logger = logging.getLogger(__name__)


class JiraService:
    """Main Jira service that orchestrates all operations."""
    
    def __init__(self):
        """Initialize the service with all operation components."""
        # Core components
        self.client = JiraClient()
        self.parser = JiraDataParser()
        self.jql_builder = JQLBuilder()
        
        # Operation modules
        self.search = JiraSearchOperations(self.client, self.parser)
        self.changelog = JiraChangelogOperations(self.client)
        self.metadata = JiraMetadataOperations(self.client)
        
        logger.info("Jira service initialized with modular architecture")

    # Delegate methods to maintain backward compatibility
    
    # Search operations
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
        """
        return await self.search.search_issues(jql_query, max_results, fields)

    async def search_product_versions(self, projects: List[str], label: str) -> List[JiraIssue]:
        """
        Search for Product Version issues.
        
        Args:
            projects: List of project keys
            label: Label to filter by
            
        Returns:
            List of Product Version issues
        """
        return await self.search.search_product_versions(projects, label)

    async def search_child_issues(self, parent_key: str, child_type_names: List[str]) -> List[JiraIssue]:
        """
        Search for child issues of a specific parent.
        
        Args:
            parent_key: Key of the parent issue
            child_type_names: List of child issue type names
            
        Returns:
            List of child issues
        """
        return await self.search.search_child_issues(parent_key, child_type_names)

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
        return await self.search.search_team_member_issues(assignee_email, label, issue_types)

    # Changelog operations
    async def bulk_fetch_changelogs(self, issue_ids: List[str], chunk_size: int = 100) -> List[Dict[str, Any]]:
        """
        Bulk fetch changelogs for multiple issues efficiently.
        
        Args:
            issue_ids: List of Jira issue IDs to fetch changelogs for
            chunk_size: Number of issues to process per API call (max 100)
            
        Returns:
            List of changelog data from Jira API
        """
        return await self.changelog.bulk_fetch_changelogs(issue_ids, chunk_size)

    # Metadata operations

    async def test_connection(self) -> bool:
        """Test connection to Jira API."""
        return await self.metadata.test_connection()

    def get_whitelisted_endpoints_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all whitelisted endpoints for debugging/monitoring.
        
        Returns:
            Dictionary with endpoint information
        """
        return self.metadata.get_whitelisted_endpoints_info()

    # Legacy compatibility methods (these were part of the original private API)
    def _parse_issue(self, issue_data: Dict[str, Any]) -> JiraIssue:
        """Parse Jira issue data into JiraIssue object. (Legacy compatibility)"""
        return self.parser.parse_issue(issue_data)

    async def _make_request(self, method: str, endpoint: str, payload: Optional[Dict[str, Any]] = None, timeout: float = 30.0):
        """Make HTTP request to Jira API. (Legacy compatibility)"""
        return await self.client.make_request(method, endpoint, payload, timeout)

    def _handle_response(self, response, operation: str, success_message: Optional[str] = None):
        """Handle HTTP response. (Legacy compatibility)"""
        return self.client.handle_response(response, operation, success_message)


# Global instance for backward compatibility
jira_service = JiraService() 