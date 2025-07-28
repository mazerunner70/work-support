"""
Query Tools for MCP Server

Core tools for querying issues and getting detailed issue information.
These are the essential tools from Phase 2 of the implementation plan.
"""
import logging
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

import mcp_types as types
from client import client, WorkSupportAPIError
from utils import (
    format_issues_list, 
    format_issue_details, 
    format_issue_descendants,
    validate_limit, 
    safe_json_dumps,
    clean_response_data
)

logger = logging.getLogger(__name__)


class QueryTools:
    """Query tools for issues and detailed information."""
    
    def __init__(self, mcp_server: FastMCP):
        self.server = mcp_server
        self._register_tools()
    
    def _register_tools(self):
        """Register all query tools with the MCP server."""
        # Register tools using FastMCP decorators
        self.server.tool()(self.query_issues)
        self.server.tool()(self.get_issue_details)
        self.server.tool()(self.get_issue_descendants)
        self.server.tool()(self.search_issues)
        self.server.tool()(self.search_issues_by_comments)
        self.server.tool()(self.get_issue_types)
    
    async def query_issues(
        self,
        assignee: Optional[str] = None,
        status: Optional[str] = None,
        team: Optional[str] = None,
        issue_type: Optional[str] = None,
        parent_key: Optional[str] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[types.TextContent]:
        """
        Query Jira issues with flexible filtering options.
        
        Use this tool when you need to find, list, or search for issues based on 
        various criteria like team, status, assignee, or issue type.
        
        Args:
            assignee: Filter by assignee name or email address
            status: Filter by issue status (e.g., "In Progress", "Done", "To Do")
            team: Filter by team name (e.g., "Backend Team", "Frontend Team")
            issue_type: Filter by issue type (e.g., "Story", "Bug", "Epic")
            parent_key: Filter by parent issue key for hierarchical issues
            source: Filter by source (e.g., "jira", "github")
            limit: Maximum number of results (1-500, default 50)
        
        Returns:
            Formatted list of issues matching the criteria
        """
        try:
            # Validate and normalize limit
            normalized_limit = validate_limit(limit, default=50, maximum=500)
            
            logger.info(f"Querying issues with filters: assignee={assignee}, status={status}, team={team}, limit={normalized_limit}")
            
            # Call work-support API
            response = await client.query_issues(
                assignee=assignee,
                status=status,
                team=team,
                issue_type=issue_type,
                parent_key=parent_key,
                source=source,
                limit=normalized_limit
            )
            
            # Extract issues from response
            issues = response.get("issues", [])
            total_count = response.get("total_count", len(issues))
            timestamp = response.get("timestamp", "")
            
            # Format response for display
            if not issues:
                filter_desc = []
                if assignee:
                    filter_desc.append(f"assignee={assignee}")
                if status:
                    filter_desc.append(f"status={status}")
                if team:
                    filter_desc.append(f"team={team}")
                if issue_type:
                    filter_desc.append(f"type={issue_type}")
                
                filter_str = ", ".join(filter_desc) if filter_desc else "no filters"
                text = f"**No issues found** matching criteria: {filter_str}"
            else:
                # Create title with filter info
                title_parts = ["Issues"]
                if team:
                    title_parts.append(f"for {team}")
                if status:
                    title_parts.append(f"({status})")
                
                title = " ".join(title_parts)
                text = format_issues_list(issues, title)
                
                # Add summary info
                if total_count > len(issues):
                    text += f"\n\n*Showing {len(issues)} of {total_count} total issues*"
                    text += f"\n*Use smaller filters or increase limit to see more*"
            
            return [types.TextContent(type="text", text=text)]
            
        except WorkSupportAPIError as e:
            logger.error(f"API error in query_issues: {e}")
            error_text = f"**Error querying issues:** {str(e)}"
            if e.status_code == 404:
                error_text += "\n\n*Check that team names and filters are spelled correctly.*"
            elif e.status_code >= 500:
                error_text += "\n\n*This appears to be a server issue. Try again in a moment.*"
            
            return [types.TextContent(type="text", text=error_text)]
        
        except Exception as e:
            logger.error(f"Unexpected error in query_issues: {e}")
            return [types.TextContent(
                type="text", 
                text=f"**Unexpected error:** {str(e)}\n\n*Please try again or contact support if the issue persists.*"
            )]
    
    async def get_issue_details(
        self,
        issue_key: str,
        include_comments: bool = True,
        include_changelog: bool = True,
        include_children: bool = False
    ) -> List[types.TextContent]:
        """
        Get comprehensive details for a specific issue.
        
        Use this tool when you need detailed information about a specific issue,
        including its description, comments, change history, and relationships.
        
        Args:
            issue_key: The issue key (e.g., "PROJ-123", "IAIPORT-456")
            include_comments: Include issue comments in the response
            include_changelog: Include change history in the response  
            include_children: Include child issues for epics/stories
        
        Returns:
            Detailed issue information formatted for display
        """
        try:
            # Log received parameters for debugging
            logger.info(f"get_issue_details called with:")
            logger.info(f"  issue_key: {issue_key} (type: {type(issue_key)})")
            logger.info(f"  include_comments: {include_comments} (type: {type(include_comments)})")
            logger.info(f"  include_changelog: {include_changelog} (type: {type(include_changelog)})")
            logger.info(f"  include_children: {include_children} (type: {type(include_children)})")
            
            if not issue_key:
                return [types.TextContent(
                    type="text",
                    text="**Error:** Issue key is required. Please provide a valid issue key (e.g., 'PROJ-123')."
                )]
            
            logger.info(f"Getting details for issue: {issue_key}")
            
            # Call work-support API
            response = await client.get_issue_details(
                issue_key=issue_key,
                include_comments=include_comments,
                include_changelog=include_changelog,
                include_children=include_children
            )
            
            # Format the response
            text = format_issue_details(response)
            
            # Add comments if included and available
            comments = response.get("comments", [])
            if include_comments and comments:
                text += f"\n\n**💬 Recent Comments ({len(comments)}):**"
                for i, comment in enumerate(comments[:5], 1):  # Show max 5 recent comments
                    author = comment.get("author", "Unknown")
                    created = comment.get("created", "")
                    body = comment.get("body", "")[:200]  # Truncate long comments
                    text += f"\n\n{i}. **{author}** ({created}):\n{body}"
                    if len(comment.get("body", "")) > 200:
                        text += "..."
                
                if len(comments) > 5:
                    text += f"\n\n*... and {len(comments) - 5} more comments*"
            
            # Add changelog if included and available
            changelog = response.get("changelog", [])
            if include_changelog and changelog:
                text += f"\n\n**📝 Recent Changes ({len(changelog)}):**"
                for i, change in enumerate(changelog[:3], 1):  # Show max 3 recent changes
                    author = change.get("author", "Unknown")
                    created = change.get("created", "")
                    field = change.get("field", "Unknown")
                    from_value = change.get("from_value", "")
                    to_value = change.get("to_value", "")
                    text += f"\n\n{i}. **{author}** changed **{field}** from '{from_value}' to '{to_value}' ({created})"
                
                if len(changelog) > 3:
                    text += f"\n\n*... and {len(changelog) - 3} more changes*"
            
            return [types.TextContent(type="text", text=text)]
            
        except WorkSupportAPIError as e:
            logger.error(f"API error in get_issue_details: {e}")
            
            if e.status_code == 404:
                error_text = f"**Issue not found:** {issue_key}\n\n*Check that the issue key is correct and you have access to view it.*"
            else:
                error_text = f"**Error getting issue details:** {str(e)}"
            
            return [types.TextContent(type="text", text=error_text)]
        
        except Exception as e:
            logger.error(f"Unexpected error in get_issue_details: {e}")
            return [types.TextContent(
                type="text",
                text=f"**Unexpected error:** {str(e)}\n\n*Please check the issue key format and try again.*"
            )]
    
    async def get_issue_descendants(
        self,
        issue_key: str,
        include_comments: bool = True,
        include_changelog: bool = True
    ) -> List[types.TextContent]:
        """
        Get all descendant issues recursively from a root issue.
        
        Use this tool when you need to explore the complete hierarchy of issues
        starting from a root issue (like an epic or product version), including
        all child issues, their comments, and change history.
        
        Args:
            issue_key: The root issue key (e.g., "PROJ-123", "IAIPORT-456")
            include_comments: Include comments for each descendant issue
            include_changelog: Include changelog entries for each descendant issue
        
        Returns:
            Complete hierarchy of descendant issues with their details
        """
        try:
            # Log received parameters for debugging
            logger.info(f"get_issue_descendants called with:")
            logger.info(f"  issue_key: {issue_key}")
            logger.info(f"  include_comments: {include_comments}")
            logger.info(f"  include_changelog: {include_changelog}")
            
            if not issue_key:
                return [types.TextContent(
                    type="text",
                    text="**Error:** Issue key is required. Please provide a valid issue key (e.g., 'PROJ-123')."
                )]
            
            logger.info(f"Getting descendants for issue: {issue_key}")
            
            # Call work-support API
            response = await client.get_issue_descendants(
                issue_key=issue_key,
                include_comments=include_comments,
                include_changelog=include_changelog
            )
            
            # Check for errors
            if "error" in response:
                return [types.TextContent(
                    type="text",
                    text=f"**Error:** {response['error']}"
                )]
            
            # Format the response
            text = format_issue_descendants(response)
            
            return [types.TextContent(type="text", text=text)]
            
        except WorkSupportAPIError as e:
            logger.error(f"API error in get_issue_descendants: {e}")
            
            if e.status_code == 404:
                error_text = f"**Issue not found:** {issue_key}\n\n*Check that the issue key is correct and you have access to view it.*"
            else:
                error_text = f"**Error getting issue descendants:** {str(e)}"
            
            return [types.TextContent(type="text", text=error_text)]
        
        except Exception as e:
            logger.error(f"Unexpected error in get_issue_descendants: {e}")
            return [types.TextContent(
                type="text",
                text=f"**Unexpected error:** {str(e)}\n\n*Please check the issue key format and try again.*"
            )]

    async def search_issues(
        self,
        query: str,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[types.TextContent]:
        """
        Search for issues using text search across summaries and descriptions.
        
        Use this tool when you need to find issues containing specific keywords
        or phrases in their title, description, or comments.
        
        Args:
            query: Search query text (keywords, phrases)
            fields: Fields to search in (summary, description, comments) - defaults to all
            limit: Maximum number of results (1-100, default 25)
        
        Returns:
            List of issues matching the search query
        """
        try:
            # Log received parameters for debugging
            logger.info(f"search_issues called with:")
            logger.info(f"  query: {query} (type: {type(query)})")
            logger.info(f"  fields: {fields} (type: {type(fields)})")
            logger.info(f"  limit: {limit} (type: {type(limit)})")
            
            # Validate inputs
            if not query or not query.strip():
                return [types.TextContent(
                    type="text",
                    text="**Error:** Search query is required. Please provide keywords or phrases to search for."
                )]
            
            # Normalize limit for search (smaller default)
            normalized_limit = validate_limit(limit, default=25, maximum=100)
            
            logger.info(f"Searching issues for: '{query}' with limit {normalized_limit}")
            
            # For now, we'll use the regular query_issues with a text filter
            # In a real implementation, this would use a dedicated search endpoint
            response = await client.query_issues(limit=normalized_limit)
            
            all_issues = response.get("issues", [])
            
            # Simple text search across issue summaries
            query_lower = query.lower()
            matching_issues = []
            
            for issue in all_issues:
                summary = issue.get("summary", "").lower()
                if query_lower in summary:
                    matching_issues.append(issue)
            
            if not matching_issues:
                text = f"**No issues found** containing '{query}'\n\n*Try different keywords or check spelling.*"
            else:
                text = format_issues_list(matching_issues, f"Search Results for '{query}'")
                text += f"\n\n*Found {len(matching_issues)} issues containing '{query}'*"
            
            return [types.TextContent(type="text", text=text)]
            
        except Exception as e:
            logger.error(f"Error in search_issues: {e}")
            return [types.TextContent(
                type="text",
                text=f"**Search error:** {str(e)}\n\n*Please try a simpler search query.*"
            )]
    
    async def search_issues_by_comments(
        self,
        issue_type: Optional[str] = None,
        days_ago: int = 10,
        limit: Optional[str] = None
    ) -> List[types.TextContent]:
        """
        Search for issues that have comments within a specified time period.
        
        Use this tool to find active issues or issues that need attention based on
        recent comment activity. This is useful for identifying issues that are
        actively being discussed or worked on.
        
        Args:
            issue_type: Filter by issue type (e.g., "Product Version", "Task", "Story")
            days_ago: Find issues with comments within this many days (1-365, default 10)
            limit: Maximum number of results (1-500, default 50)
        
        Returns:
            List of issues with recent comments, ordered by most recent comment first
        """
        try:
            # Log received parameters for debugging
            logger.info(f"search_issues_by_comments called with:")
            logger.info(f"  issue_type: {issue_type} (type: {type(issue_type)})")
            logger.info(f"  days_ago: {days_ago} (type: {type(days_ago)})")
            logger.info(f"  limit: {limit} (type: {type(limit)})")
            
            # Validate inputs
            if days_ago < 1 or days_ago > 365:
                return [types.TextContent(
                    type="text",
                    text="**Error:** days_ago must be between 1 and 365 days."
                )]
            
            # Convert and normalize limit
            limit_int = None
            if limit is not None:
                try:
                    limit_int = int(limit)
                except (ValueError, TypeError):
                    return [types.TextContent(
                        type="text",
                        text="**Error:** limit must be a valid number."
                    )]
            
            normalized_limit = validate_limit(limit_int, default=50, maximum=500)
            
            logger.info(f"Searching issues by comments: type={issue_type}, days_ago={days_ago}, limit={normalized_limit}")
            
            # Call the new search endpoint
            response = await client.search_issues_by_comments(
                issue_type=issue_type,
                days_ago=days_ago,
                limit=normalized_limit
            )
            
            # Extract issues from response
            issues = response.get("issues", [])
            total_count = response.get("total_count", len(issues))
            timestamp = response.get("timestamp", "")
            
            # Format response for display
            if not issues:
                filter_desc = []
                if issue_type:
                    filter_desc.append(f"type={issue_type}")
                filter_desc.append(f"comments in last {days_ago} days")
                
                filter_str = ", ".join(filter_desc)
                text = f"**No issues found** with {filter_str}\n\n"
                text += "*Try adjusting the time period or issue type filter.*"
            else:
                # Build title
                title_parts = []
                if issue_type:
                    title_parts.append(f"{issue_type} issues")
                else:
                    title_parts.append("Issues")
                title_parts.append(f"with comments in last {days_ago} days")
                
                title = " - ".join(title_parts)
                
                text = format_issues_list(issues, title)
                text += f"\n\n*Found {len(issues)} issues with recent comments*"
                if total_count > len(issues):
                    text += f" (showing {len(issues)} of {total_count})"
            
            return [types.TextContent(type="text", text=text)]
            
        except WorkSupportAPIError as e:
            logger.error(f"API error in search_issues_by_comments: {e}")
            return [types.TextContent(
                type="text",
                text=f"**API Error:** {str(e)}\n\n*Please check the parameters and try again.*"
            )]
        
        except Exception as e:
            logger.error(f"Unexpected error in search_issues_by_comments: {e}")
            return [types.TextContent(
                type="text",
                text=f"**Unexpected error:** {str(e)}\n\n*Please try again with different parameters.*"
            )]
    
    async def get_issue_types(self) -> List[types.TextContent]:
        """
        Get all issue types with their database IDs.
        
        Use this tool to see all available issue types in the system and their
        corresponding database IDs. This is useful for understanding the issue
        type hierarchy and for filtering queries by issue type.
        
        Returns:
            List of all issue types with their IDs, descriptions, and hierarchy information
        """
        try:
            logger.info("Getting all issue types")
            
            # Call work-support API
            response = await client.get_issue_types()
            
            # Extract issue types from response
            issue_types = response.get("issue_types", [])
            total_count = response.get("total_count", len(issue_types))
            
            if not issue_types:
                text = "**No issue types found**\n\n*The system may not have any issue types configured.*"
            else:
                # Build the response text
                text = f"**Issue Types** ({total_count} found):\n\n"
                
                for issue_type in issue_types:
                    issue_id = issue_type.get("id", "N/A")
                    name = issue_type.get("name", "Unknown")
                    url = issue_type.get("url", "")
                    child_type_ids = issue_type.get("child_type_ids", [])
                    is_leaf = issue_type.get("is_leaf", False)
                    
                    text += f"**{name}** (ID: {issue_id})\n"
                    if url:
                        text += f"  URL: {url}\n"
                    if child_type_ids:
                        text += f"  Child Type IDs: {', '.join(map(str, child_type_ids))}\n"
                    else:
                        text += f"  Leaf Type: {is_leaf}\n"
                    text += "\n"
            
            return [types.TextContent(type="text", text=text)]
            
        except WorkSupportAPIError as e:
            logger.error(f"API error in get_issue_types: {e}")
            return [types.TextContent(
                type="text",
                text=f"**API Error:** {str(e)}\n\n*Please check the system connectivity.*"
            )]
        
        except Exception as e:
            logger.error(f"Unexpected error in get_issue_types: {e}")
            return [types.TextContent(
                type="text",
                text=f"**Unexpected error:** {str(e)}\n\n*Please try again.*"
            )] 