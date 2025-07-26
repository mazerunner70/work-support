"""
JQL query construction utilities for Jira API integration.
"""
from typing import List, Optional


class JQLBuilder:
    """Utility class for constructing JQL queries for hierarchical issue traversal."""

    @staticmethod
    def build_initial_product_version_query(projects: List[str], label: str) -> str:
        """
        Build the initial query for Product Version issues.
        
        Args:
            projects: List of project keys (e.g., ['IAIPORT', 'AIPRDV', 'AIMP', 'IACU'])
            label: Label to filter by (e.g., 'SE_product_family')
            
        Returns:
            JQL query string
        """
        projects_str = ", ".join(projects)
        return f'project in ({projects_str}) AND type = "Product Version" AND labels = {label}'

    @staticmethod
    def build_child_issues_query(parent_key: str, child_type_names: List[str]) -> str:
        """
        Build query for child issues of a specific parent.
        
        Args:
            parent_key: Key of the parent issue (e.g., 'PV-123')
            child_type_names: List of child issue type names (e.g., ['Feature', 'Customer Adoption'])
            
        Returns:
            JQL query string
        """
        if not child_type_names:
            return ""
            
        # Escape issue type names that might contain spaces
        escaped_types = [f'"{type_name}"' for type_name in child_type_names]
        types_str = ", ".join(escaped_types)
        
        return f'parent = "{parent_key}" AND type IN ({types_str})'

    @staticmethod
    def build_assignee_filter_query(base_query: str, assignee_email: str) -> str:
        """
        Add assignee filter to an existing query.
        
        Args:
            base_query: Base JQL query
            assignee_email: Email of the assignee
            
        Returns:
            Enhanced JQL query with assignee filter
        """
        if not base_query:
            return f'assignee = "{assignee_email}"'
        return f'({base_query}) AND assignee = "{assignee_email}"'

    @staticmethod
    def build_label_filter_query(base_query: str, label: str) -> str:
        """
        Add label filter to an existing query.
        
        Args:
            base_query: Base JQL query
            label: Label to filter by
            
        Returns:
            Enhanced JQL query with label filter
        """
        if not base_query:
            return f'labels = {label}'
        return f'({base_query}) AND labels = {label}'

    @staticmethod
    def build_team_member_query(assignee_email: str, label: str, issue_types: Optional[List[str]] = None) -> str:
        """
        Build query for team member specific issues.
        
        Args:
            assignee_email: Email of the team member
            label: Label to filter by
            issue_types: Optional list of issue types to filter by
            
        Returns:
            JQL query string
        """
        query_parts = [
            f'assignee = "{assignee_email}"',
            f'labels = {label}'
        ]
        
        if issue_types:
            escaped_types = [f'"{type_name}"' for type_name in issue_types]
            types_str = ", ".join(escaped_types)
            query_parts.append(f'type IN ({types_str})')
        
        return " AND ".join(query_parts)

    @staticmethod
    def validate_jql_syntax(query: str) -> bool:
        """
        Basic validation of JQL syntax.
        
        Args:
            query: JQL query string
            
        Returns:
            True if basic syntax looks valid
        """
        if not query or not query.strip():
            return False
            
        # Check for balanced quotes
        quote_count = query.count('"')
        if quote_count % 2 != 0:
            return False
            
        # Check for balanced parentheses
        open_parens = query.count('(')
        close_parens = query.count(')')
        if open_parens != close_parens:
            return False
            
        return True 