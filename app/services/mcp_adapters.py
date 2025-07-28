"""
MCP response formatting utilities for work-support data.

Provides standardized response formatting for MCP (Model Context Protocol) clients,
ensuring clean, consistent JSON responses that are easy for AI agents to parse.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models.database import Issue, Changelog, Comment, TeamMember, HarvestJob


class MCPResponseFormatter:
    """Formats database objects for MCP client consumption."""
    


    @staticmethod
    def format_issue(issue: Issue, include_details: bool = False) -> Dict[str, Any]:
        """Format a single issue for MCP response."""
        print(f"Formatting issue: {issue}")
        base_issue = {
            "issue_key": issue.issue_key,
            "issue_id": issue.issue_id,
            "summary": issue.summary,
            "assignee": issue.assignee,
            "status": issue.status,
            "team": issue.team,
            "parent_key": issue.parent_key,
            "source": issue.source,
            "dates": {
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
                "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
                "start_date": issue.start_date.isoformat() if issue.start_date else None,
                "transition_date": issue.transition_date,
                "end_date": issue.end_date.isoformat() if issue.end_date else None,
                "harvested_at": issue.harvested_at.isoformat() if issue.harvested_at else None
            }
        }
        
        # Add labels if present
        if issue.labels:
            try:
                import json
                base_issue["labels"] = json.loads(issue.labels) if isinstance(issue.labels, str) else issue.labels
            except (json.JSONDecodeError, TypeError):
                base_issue["labels"] = []
        else:
            base_issue["labels"] = []
        
        # Add issue type if available
        if hasattr(issue, 'issue_type') and issue.issue_type:
            base_issue["issue_type"] = {
                "id": issue.issue_type.id,
                "name": issue.issue_type.name
            }
        else:
            base_issue["issue_type"] = None
        
        # Add details if requested
        if include_details:
            base_issue["blacklist_reason"] = issue.blacklist_reason
            base_issue["comments_count"] = len(issue.comment_records) if issue.comment_records else 0
            base_issue["changelog_count"] = len(issue.changelog_records) if issue.changelog_records else 0
        
        return base_issue
    
    @staticmethod
    def format_issues_list(issues: List[Issue], include_details: bool = False) -> Dict[str, Any]:
        """Format a list of issues for MCP response."""
        return {
            "issues": [MCPResponseFormatter.format_issue(issue, include_details) for issue in issues],
            "total_count": len(issues),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def format_issue_details(issue: Issue, include_comments: bool = True, include_changelog: bool = True) -> Dict[str, Any]:
        """Format comprehensive issue details for MCP response."""
        issue_data = MCPResponseFormatter.format_issue(issue, include_details=True)
        
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
        
        return issue_data
    
    @staticmethod
    def format_team_metrics(team_name: str, issues: List[Issue], date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Format team metrics for MCP response."""
        if not issues:
            return {
                "team": team_name,
                "period": date_range,
                "metrics": {
                    "total_issues": 0,
                    "completed_issues": 0,
                    "completion_rate": 0.0,
                    "active_issues": 0,
                    "status_breakdown": {}
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Calculate metrics
        total_issues = len(issues)
        completed_issues = len([issue for issue in issues if issue.status and issue.status.lower() in ['done', 'completed', 'closed']])
        completion_rate = completed_issues / total_issues if total_issues > 0 else 0.0
        active_issues = len([issue for issue in issues if issue.status and issue.status.lower() in ['in progress', 'in review', 'testing']])
        
        # Status breakdown
        status_breakdown = {}
        for issue in issues:
            status = issue.status or "Unknown"
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
        
        # Get unique assignees
        assignees = list(set([issue.assignee for issue in issues if issue.assignee]))
        
        return {
            "team": team_name,
            "period": date_range,
            "metrics": {
                "total_issues": total_issues,
                "completed_issues": completed_issues,
                "completion_rate": round(completion_rate, 3),
                "active_issues": active_issues,
                "team_members": assignees
            },
            "status_breakdown": status_breakdown,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def format_connectivity_status(jira_connected: bool, db_connected: bool, last_harvest: Optional[datetime] = None) -> Dict[str, Any]:
        """Format system connectivity status for MCP response."""
        overall_status = "healthy" if jira_connected and db_connected else "degraded"
        
        return {
            "status": overall_status,
            "services": {
                "jira": "connected" if jira_connected else "disconnected",
                "database": "connected" if db_connected else "disconnected"
            },
            "last_harvest": last_harvest.isoformat() if last_harvest else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def format_error_response(error_type: str, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Format error response for MCP clients."""
        return {
            "error": {
                "type": error_type,
                "message": message,
                "details": details or {},
                "timestamp": datetime.utcnow().isoformat()
            }
        }


class MCPQueryBuilder:
    """Helper for building database queries for MCP endpoints."""
    
    @staticmethod
    def build_issue_query(db_session, filters: Dict[str, Any]):
        """Build SQLAlchemy query for issues with MCP filters."""
        from app.models.database import Issue, IssueType
        
        query = db_session.query(Issue)
        
        # Apply filters
        if filters.get("assignee"):
            query = query.filter(Issue.assignee == filters["assignee"])
        
        if filters.get("status"):
            query = query.filter(Issue.status == filters["status"])
        
        if filters.get("team"):
            query = query.filter(Issue.team == filters["team"])
        
        if filters.get("issue_type"):
            query = query.join(IssueType).filter(IssueType.name == filters["issue_type"])
        
        if filters.get("parent_key"):
            query = query.filter(Issue.parent_key == filters["parent_key"])
        
        if filters.get("source"):
            query = query.filter(Issue.source == filters["source"])
        
        return query 