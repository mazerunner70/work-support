"""
Service for retrieving all descendant issues recursively.

This service takes a root issue and finds all descendant issues in the hierarchy,
including their comments and changelog entries.
"""
import logging
from typing import List, Dict, Any, Set
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from app.models.database import Issue, Comment, Changelog

logger = logging.getLogger(__name__)


class DescendantService:
    """Service for retrieving descendant issues recursively."""
    
    def __init__(self):
        self.batch_size = 100  # Process issues in batches of 100
    
    def get_all_descendants(
        self, 
        db: Session, 
        root_issue_key: str,
        include_comments: bool = True,
        include_changelog: bool = True
    ) -> Dict[str, Any]:
        """
        Get all descendant issues recursively from a root issue.
        
        Args:
            db: Database session
            root_issue_key: The root issue key to start from
            include_comments: Whether to include comments for each issue
            include_changelog: Whether to include changelog entries for each issue
            
        Returns:
            Dictionary containing root issue and all descendants with their details
        """
        try:
            # First, verify the root issue exists
            root_issue = db.query(Issue).filter(Issue.issue_key == root_issue_key).first()
            if not root_issue:
                return {
                    "error": f"Root issue '{root_issue_key}' not found",
                    "root_issue": None,
                    "descendants": [],
                    "total_count": 0
                }
            
            # Get all descendant issue keys recursively
            descendant_keys = self._get_descendant_keys(db, root_issue_key)
            
            # Get full issue details with relationships
            descendants = self._get_issues_with_details(
                db, 
                descendant_keys, 
                include_comments, 
                include_changelog
            )
            
            # Get root issue details
            root_details = self._get_issue_with_details(
                db, 
                root_issue, 
                include_comments, 
                include_changelog
            )
            
            return {
                "root_issue": root_details,
                "descendants": descendants,
                "total_count": len(descendants),
                "hierarchy_depth": self._calculate_max_depth(descendants, root_issue_key)
            }
            
        except Exception as e:
            logger.error(f"Error getting descendants for {root_issue_key}: {e}")
            return {
                "error": f"Failed to retrieve descendants: {str(e)}",
                "root_issue": None,
                "descendants": [],
                "total_count": 0
            }
    
    def _get_descendant_keys(self, db: Session, root_key: str) -> Set[str]:
        """Recursively get all descendant issue keys."""
        descendant_keys = set()
        to_process = {root_key}
        processed = set()
        
        while to_process:
            # Process in batches to avoid memory issues
            batch = list(to_process)[:self.batch_size]
            to_process = to_process - set(batch)
            
            # Find direct children of this batch
            children = db.query(Issue.issue_key).filter(
                Issue.parent_key.in_(batch)
            ).all()
            
            new_keys = {child[0] for child in children} - processed
            descendant_keys.update(new_keys)
            to_process.update(new_keys)
            processed.update(batch)
            
            logger.info(f"Processed batch of {len(batch)} issues, found {len(new_keys)} new descendants")
        
        return descendant_keys
    
    def _get_issues_with_details(
        self, 
        db: Session, 
        issue_keys: Set[str], 
        include_comments: bool, 
        include_changelog: bool
    ) -> List[Dict[str, Any]]:
        """Get full details for multiple issues with relationships."""
        if not issue_keys:
            return []
        
        # Build query with eager loading
        query = db.query(Issue).filter(Issue.issue_key.in_(issue_keys))
        
        if include_comments:
            query = query.options(joinedload(Issue.comment_records))
        
        if include_changelog:
            query = query.options(joinedload(Issue.changelog_records))
        
        issues = query.all()
        
        # Format each issue
        return [
            self._get_issue_with_details(db, issue, include_comments, include_changelog)
            for issue in issues
        ]
    
    def _get_issue_with_details(
        self, 
        db: Session, 
        issue: Issue, 
        include_comments: bool, 
        include_changelog: bool
    ) -> Dict[str, Any]:
        """Format a single issue with its details."""
        issue_data = {
            "issue_key": issue.issue_key,
            "issue_id": issue.issue_id,
            "summary": issue.summary,
            "assignee": issue.assignee,
            "status": issue.status,
            "team": issue.team,
            "parent_key": issue.parent_key,
            "source": issue.source,
            "labels": self._parse_labels(issue.labels),
            "dates": {
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
                "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                "start_date": issue.start_date.isoformat() if issue.start_date else None,
                "transition_date": issue.transition_date,
                "end_date": issue.end_date.isoformat() if issue.end_date else None,
                "harvested_at": issue.harvested_at.isoformat() if issue.harvested_at else None
            }
        }
        
        # Add issue type if available
        if hasattr(issue, 'issue_type') and issue.issue_type:
            issue_data["issue_type"] = {
                "id": issue.issue_type.id,
                "name": issue.issue_type.name
            }
        
        # Add comments if requested
        if include_comments and issue.comment_records:
            issue_data["comments"] = [
                {
                    "id": comment.id,
                    "body": comment.body,
                    "created_at": comment.created_at.isoformat(),
                    "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
                    "jira_comment_id": comment.jira_comment_id
                }
                for comment in issue.comment_records
            ]
            issue_data["comments_count"] = len(issue.comment_records)
        else:
            issue_data["comments"] = []
            issue_data["comments_count"] = 0
        
        # Add changelog if requested
        if include_changelog and issue.changelog_records:
            issue_data["changelog"] = [
                {
                    "id": changelog.id,
                    "jira_changelog_id": changelog.jira_changelog_id,
                    "field_name": changelog.field_name,
                    "from_value": changelog.from_value,
                    "to_value": changelog.to_value,
                    "from_display": changelog.from_display,
                    "to_display": changelog.to_display,
                    "created_at": changelog.created_at.isoformat(),
                    "harvested_at": changelog.harvested_at.isoformat() if changelog.harvested_at else None
                }
                for changelog in issue.changelog_records
            ]
            issue_data["changelog_count"] = len(issue.changelog_records)
        else:
            issue_data["changelog"] = []
            issue_data["changelog_count"] = 0
        
        return issue_data
    
    def _parse_labels(self, labels: str) -> List[str]:
        """Parse labels from JSON string."""
        if not labels:
            return []
        try:
            import json
            return json.loads(labels) if isinstance(labels, str) else labels
        except (json.JSONDecodeError, TypeError):
            return []
    
    def _calculate_max_depth(self, descendants: List[Dict[str, Any]], root_key: str) -> int:
        """Calculate the maximum depth of the hierarchy."""
        if not descendants:
            return 0
        
        # Build parent-child mapping
        parent_map = {issue["issue_key"]: issue["parent_key"] for issue in descendants}
        
        max_depth = 0
        for issue in descendants:
            depth = 0
            current = issue["issue_key"]
            while current in parent_map and parent_map[current] != root_key:
                current = parent_map[current]
                depth += 1
            max_depth = max(max_depth, depth)
        
        return max_depth


# Global instance
descendant_service = DescendantService() 