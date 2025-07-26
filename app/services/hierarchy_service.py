"""
Hierarchical issue traversal service for recursive data collection.
"""
import logging
from typing import List, Dict, Set, Optional
import json

from app.config.issue_types import get_issue_type_by_id, get_child_type_ids, ISSUE_TYPES
from app.services.jira_service import jira_service, JiraIssue, JiraServiceError

logger = logging.getLogger(__name__)


class HierarchyServiceError(Exception):
    """Custom exception for hierarchy service errors."""
    pass


class HierarchyService:
    """Service for traversing issue hierarchies and collecting data recursively."""

    def __init__(self):
        self.jira_service = jira_service
        # Build lookup dictionaries for efficient access
        self.issue_type_by_id = {it.id: it for it in ISSUE_TYPES}
        self.issue_type_by_name = {it.name: it for it in ISSUE_TYPES}

    async def harvest_hierarchical_issues(self, projects: List[str], label: str, 
                                         max_depth: int = 5) -> List[JiraIssue]:
        """
        Harvest issues using hierarchical traversal starting from Product Versions.
        
        Args:
            projects: List of project keys to search in
            label: Label to filter by (e.g., 'SE_product_family')
            max_depth: Maximum depth to traverse (prevents infinite loops)
            
        Returns:
            List of all harvested issues
            
        Raises:
            HierarchyServiceError: If harvesting fails
        """
        try:
            all_issues = []
            processed_keys = set()  # Track processed issues to avoid duplicates
            
            logger.info(f"Starting hierarchical harvest for projects {projects} with label '{label}'")
            
            # Step 1: Get all Product Version issues
            product_versions = await self.jira_service.search_product_versions(projects, label)
            logger.info(f"Found {len(product_versions)} Product Version issues")
            
            # Step 2: For each Product Version, traverse the hierarchy
            for pv_issue in product_versions:
                if pv_issue.key not in processed_keys:
                    hierarchy_issues = await self._traverse_issue_hierarchy(
                        pv_issue, max_depth, processed_keys
                    )
                    all_issues.extend(hierarchy_issues)
            
            logger.info(f"Hierarchical harvest completed. Total issues collected: {len(all_issues)}")
            return all_issues
            
        except JiraServiceError as e:
            error_msg = f"Jira service error during hierarchical harvest: {e}"
            logger.error(error_msg)
            raise HierarchyServiceError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during hierarchical harvest: {e}"
            logger.error(error_msg)
            raise HierarchyServiceError(error_msg)

    async def _traverse_issue_hierarchy(self, root_issue: JiraIssue, max_depth: int, 
                                       processed_keys: Set[str], current_depth: int = 0) -> List[JiraIssue]:
        """
        Recursively traverse issue hierarchy starting from a root issue.
        
        Args:
            root_issue: The root issue to start traversal from
            max_depth: Maximum depth to traverse
            processed_keys: Set of already processed issue keys
            current_depth: Current depth in the traversal
            
        Returns:
            List of all issues in the hierarchy
        """
        if current_depth >= max_depth:
            logger.warning(f"Maximum depth {max_depth} reached for issue {root_issue.key}")
            return []
            
        if root_issue.key in processed_keys:
            logger.debug(f"Issue {root_issue.key} already processed, skipping")
            return []
        
        issues = [root_issue]
        processed_keys.add(root_issue.key)
        
        logger.debug(f"Processing issue {root_issue.key} (depth {current_depth})")
        
        # Get child type names for this issue's type
        child_type_names = self._get_child_type_names(root_issue.issue_type_id)
        
        if not child_type_names:
            logger.debug(f"Issue {root_issue.key} has no child types (leaf node)")
            return issues
        
        try:
            # Search for child issues
            child_issues = await self.jira_service.search_child_issues(
                root_issue.key, child_type_names
            )
            
            logger.debug(f"Found {len(child_issues)} child issues for {root_issue.key}")
            
            # Recursively process each child
            for child_issue in child_issues:
                child_hierarchy = await self._traverse_issue_hierarchy(
                    child_issue, max_depth, processed_keys, current_depth + 1
                )
                issues.extend(child_hierarchy)
                
        except JiraServiceError as e:
            logger.error(f"Error searching for children of {root_issue.key}: {e}")
            # Continue processing other issues even if one fails
        
        return issues

    def _get_child_type_names(self, issue_type_id: int) -> List[str]:
        """
        Get child type names for a given issue type ID.
        
        Args:
            issue_type_id: ID of the issue type
            
        Returns:
            List of child type names
        """
        issue_type = self.issue_type_by_id.get(issue_type_id)
        if not issue_type:
            logger.warning(f"Unknown issue type ID: {issue_type_id}")
            return []
        
        child_type_names = []
        for child_id in issue_type.child_type_ids:
            child_type = self.issue_type_by_id.get(child_id)
            if child_type:
                child_type_names.append(child_type.name)
            else:
                logger.warning(f"Unknown child type ID: {child_id}")
        
        return child_type_names

    async def harvest_team_member_issues(self, team_member_jira_id: str, label: str) -> List[JiraIssue]:
        """
        Harvest issues assigned to a specific team member.
        
        Args:
            team_member_jira_id: Jira ID (email) of the team member
            label: Label to filter by
            
        Returns:
            List of issues assigned to the team member
        """
        try:
            logger.info(f"Harvesting issues for team member: {team_member_jira_id}")
            
            issues = await self.jira_service.search_team_member_issues(
                team_member_jira_id, label
            )
            
            logger.info(f"Found {len(issues)} issues for team member {team_member_jira_id}")
            return issues
            
        except JiraServiceError as e:
            error_msg = f"Error harvesting issues for team member {team_member_jira_id}: {e}"
            logger.error(error_msg)
            raise HierarchyServiceError(error_msg)

    def map_issue_type_id(self, jira_issue_type_id: int, jira_issue_type_name: str) -> int:
        """
        Map Jira issue type to our local issue type ID.
        
        Args:
            jira_issue_type_id: Issue type ID from Jira
            jira_issue_type_name: Issue type name from Jira
            
        Returns:
            Local issue type ID (returns -1 for "Error-Type Not Known" if no match)
        """
        # First try to match by ID
        if jira_issue_type_id in self.issue_type_by_id:
            return jira_issue_type_id
        
        # Then try to match by name
        issue_type = self.issue_type_by_name.get(jira_issue_type_name)
        if issue_type:
            logger.info(f"Mapped issue type '{jira_issue_type_name}' (Jira ID: {jira_issue_type_id}) "
                       f"to local ID: {issue_type.id}")
            return issue_type.id
        
        # Unknown issue type - map to "Error-Type Not Known"
        logger.warning(f"Unknown issue type: ID={jira_issue_type_id}, Name='{jira_issue_type_name}'. "
                      f"Mapping to 'Error-Type Not Known'")
        return -1

    def validate_hierarchy_integrity(self) -> Dict[str, List[str]]:
        """
        Validate the integrity of the issue type hierarchy configuration.
        
        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []
        
        for issue_type in ISSUE_TYPES:
            # Check for circular references
            visited = set()
            if self._has_circular_reference(issue_type.id, visited):
                issues.append(f"Circular reference detected for issue type {issue_type.name} (ID: {issue_type.id})")
            
            # Check if child type IDs are valid
            for child_id in issue_type.child_type_ids:
                if child_id not in self.issue_type_by_id:
                    issues.append(f"Invalid child type ID {child_id} in issue type {issue_type.name}")
        
        # Check for orphaned issue types (not referenced as children)
        referenced_ids = set()
        for issue_type in ISSUE_TYPES:
            referenced_ids.update(issue_type.child_type_ids)
        
        root_types = []
        for issue_type in ISSUE_TYPES:
            if issue_type.id not in referenced_ids and issue_type.id != -1:  # Exclude "Error-Type Not Known"
                root_types.append(issue_type.name)
        
        if len(root_types) != 1:
            warnings.append(f"Expected exactly 1 root type, found {len(root_types)}: {root_types}")
        
        return {
            "issues": issues,
            "warnings": warnings,
            "valid": len(issues) == 0
        }

    def _has_circular_reference(self, type_id: int, visited: Set[int]) -> bool:
        """Check if there's a circular reference in the hierarchy."""
        if type_id in visited:
            return True
        
        visited.add(type_id)
        issue_type = self.issue_type_by_id.get(type_id)
        
        if issue_type:
            for child_id in issue_type.child_type_ids:
                if self._has_circular_reference(child_id, visited.copy()):
                    return True
        
        return False


# Global instance
hierarchy_service = HierarchyService() 