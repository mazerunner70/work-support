"""
Jira search operations with DRY patterns and pagination support.
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional

from app.config.settings import config_manager
from app.utils.jql_builder import JQLBuilder
from app.services.jira.client import JiraClient
from app.services.jira.parsers import JiraDataParser
from app.models.jira import JiraIssue, JiraServiceError, JiraEndpointNotWhitelistedError

logger = logging.getLogger(__name__)


class JiraSearchOperations:
    """All issue search related operations with DRY patterns."""
    
    def __init__(self, client: JiraClient, parser: JiraDataParser):
        """Initialize search operations with client and parser dependencies."""
        self.client = client
        self.parser = parser
        self.jql_builder = JQLBuilder()

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
        return await self._execute_search(
            jql_query=jql_query,
            operation_name="issue search",
            max_results=max_results,
            fields=fields
        )

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
        return await self._execute_search(
            jql_query=jql_query,
            operation_name="product version search"
        )

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
        return await self._execute_search(
            jql_query=jql_query,
            operation_name=f"child issues search for {parent_key}"
        )

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
        return await self._execute_search(
            jql_query=jql_query,
            operation_name=f"team member search for {assignee_email}"
        )

    async def _execute_search(
        self,
        jql_query: str,
        operation_name: str,
        max_results: int = 1000,
        fields: Optional[List[str]] = None
    ) -> List[JiraIssue]:
        """
        Common search execution pattern with pagination and blacklist filtering.
        
        Args:
            jql_query: JQL query string
            operation_name: Name of the operation for logging
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
                    "fields": fields or self._get_default_fields()
                }
                
                response = await self.client.make_request("POST", "search", payload, timeout=60.0)
                data = self.client.handle_response(
                    response, 
                    operation_name,
                    f"Retrieved page {start_at//page_size + 1} from Jira for {operation_name}"
                )
                
                page_issues = self._process_search_page(data, blacklisted_count)
                page_issues, page_blacklisted = page_issues
                
                all_issues.extend(page_issues)
                blacklisted_count += page_blacklisted
                
                # Check if we have more pages and haven't hit our limit
                total = data.get("total", 0)
                start_at += page_size
                
                if start_at >= total or (max_results > 0 and len(all_issues) >= max_results):
                    break
            
            # Trim to max_results if specified
            if max_results > 0 and len(all_issues) > max_results:
                all_issues = all_issues[:max_results]
            
            self._log_search_results(operation_name, len(all_issues), blacklisted_count, data.get("total", 0))
            return all_issues
                    
        except (JiraServiceError, JiraEndpointNotWhitelistedError):
            raise
        except Exception as e:
            error_msg = f"Unexpected error during {operation_name}: {e}"
            logger.error(error_msg)
            raise JiraServiceError(error_msg)

    def _process_search_page(self, data: Dict[str, Any], current_blacklisted: int) -> tuple[List[JiraIssue], int]:
        """
        Process a single page of search results with blacklist filtering.
        
        Args:
            data: Response data from Jira API
            current_blacklisted: Current count of blacklisted issues
            
        Returns:
            Tuple of (page_issues, blacklisted_count_for_page)
        """
        page_issues = []
        page_blacklisted = 0
        
        for issue_data in data.get("issues", []):
            try:
                issue_key = issue_data.get('key', '')
                jira_issue = self.parser.parse_issue(issue_data)
                
                # Determine blacklist reason
                blacklist_reason = self._determine_blacklist_reason(jira_issue, issue_key)
                jira_issue.blacklist_reason = blacklist_reason
                
                # Skip blacklisted issues
                if blacklist_reason:
                    page_blacklisted += 1
                    logger.debug(f"Skipping blacklisted issue: {issue_key} (reason: {blacklist_reason})")
                    continue
                
                page_issues.append(jira_issue)
            except Exception as e:
                logger.warning(f"Error parsing issue {issue_data.get('key', 'Unknown')}: {e}")
                continue
        
        return page_issues, page_blacklisted

    def _determine_blacklist_reason(self, jira_issue: JiraIssue, issue_key: str) -> Optional[str]:
        """
        Determine if an issue should be blacklisted and why.
        
        Args:
            jira_issue: Parsed Jira issue
            issue_key: Issue key for project checking
            
        Returns:
            Blacklist reason or None if not blacklisted
        """
        if config_manager.is_project_blacklisted(issue_key):
            return "project"
        elif jira_issue.team and config_manager.is_team_blacklisted(jira_issue.team):
            return f"team:{jira_issue.team}"
        elif config_manager.is_status_blacklisted(jira_issue.status):
            return f"status:{jira_issue.status}"
        
        return None

    def _get_default_fields(self) -> List[str]:
        """Get the default list of fields to retrieve from Jira."""
        return [
            "key", "summary", "assignee", "status", "labels",
            "issuetype", "parent", "created", "updated", "comment",
            "customfield_10001",  # Team field
            "customfield_14339",  # Start date
            "customfield_14343",  # Transition date  
            "customfield_13647"   # End date
        ]

    def _log_search_results(self, operation_name: str, found_count: int, blacklisted_count: int, total_count: int):
        """Log search results summary."""
        if blacklisted_count > 0:
            logger.info(f"Filtered out {blacklisted_count} blacklisted issues")
        logger.info(f"Successfully parsed {found_count} issues from {total_count} total found for {operation_name}") 