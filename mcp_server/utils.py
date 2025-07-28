"""
MCP Server Utilities

Utility functions for response formatting, data processing, and 
common operations used across MCP tools.
"""
import json
from typing import Any, Dict, List, Optional
from datetime import datetime


def format_issue_summary(issue: Dict[str, Any]) -> str:
    """Format a single issue for display in MCP responses."""
    key = issue.get("issue_key", "N/A")
    summary = issue.get("summary", "No summary")
    status = issue.get("status", "Unknown")
    assignee = issue.get("assignee", "Unassigned")
    
    return f"**{key}**: {summary}\n  Status: {status} | Assignee: {assignee}"


def format_issues_list(issues: List[Dict[str, Any]], title: str = "Issues") -> str:
    """Format a list of issues for MCP text response."""
    if not issues:
        return f"**{title}**: No issues found."
    
    lines = [f"**{title}** ({len(issues)} found):"]
    lines.extend([format_issue_summary(issue) for issue in issues])
    
    return "\n\n".join(lines)


def format_team_metrics(metrics: Dict[str, Any]) -> str:
    """Format team metrics for display."""
    team = metrics.get("team", "Unknown Team")
    period = metrics.get("period", "Unknown Period")
    data = metrics.get("metrics", {})
    
    lines = [
        f"**Team Metrics: {team}**",
        f"Period: {period}",
        "",
        f"📊 **Summary:**",
        f"• Total Issues: {data.get('total_issues', 0)}",
        f"• Completed Issues: {data.get('completed_issues', 0)}",
        f"• Completion Rate: {data.get('completion_rate', 0):.1%}",
        f"• Average Cycle Time: {data.get('average_cycle_time_days', 0):.1f} days",
        f"• Active Issues: {data.get('active_issues', 0)}"
    ]
    
    # Add status breakdown if available
    status_breakdown = metrics.get("status_breakdown", {})
    if status_breakdown:
        lines.extend([
            "",
            f"📈 **Status Breakdown:**"
        ])
        for status, count in status_breakdown.items():
            lines.append(f"• {status}: {count}")
    
    return "\n".join(lines)


def format_issue_details(issue_data: Dict[str, Any]) -> str:
    """Format detailed issue information."""
    # Issue data is at top level, not nested under "issue" key
    issue = issue_data
    
    lines = [
        f"**Issue Details: {issue.get('issue_key', 'N/A')}**",
        "",
        f"📝 **Summary:** {issue.get('summary', 'No summary')}",
        f"👤 **Assignee:** {issue.get('assignee', 'Unassigned')}",
        f"🏷️ **Status:** {issue.get('status', 'Unknown')}",
        f"🏢 **Team:** {issue.get('team', 'Unknown')}",
        f"📋 **Type:** {issue.get('issue_type', {}).get('name', 'Unknown') if issue.get('issue_type') else 'Unknown'}",
    ]
    
    # Add dates if available
    dates = issue.get("dates", {})
    if dates:
        lines.extend([
            "",
            f"📅 **Dates:**",
            f"• Created: {format_date(dates.get('created_at'))}",
            f"• Updated: {format_date(dates.get('updated_at'))}",
        ])
        
        if dates.get("start_date"):
            lines.append(f"• Started: {format_date(dates.get('start_date'))}")
        if dates.get("end_date"):
            lines.append(f"• Completed: {format_date(dates.get('end_date'))}")
    
    # Add labels if available
    labels = issue.get("labels", [])
    if labels:
        lines.extend([
            "",
            f"🏷️ **Labels:** {', '.join(labels)}"
        ])
    
    # Add parent/children info if available
    parent_key = issue.get("parent_key")
    if parent_key:
        lines.extend([
            "",
            f"⬆️ **Parent Issue:** {parent_key}"
        ])
    
    children = issue.get("children", [])
    if children:
        lines.extend([
            "",
            f"⬇️ **Child Issues:** {', '.join(children)}"
        ])
    
    # Add comments count if available
    comments_count = issue.get("comments_count", 0)
    changelog_count = issue.get("changelog_count", 0)
    if comments_count or changelog_count:
        lines.extend([
            "",
            f"💬 **Activity:** {comments_count} comments, {changelog_count} changes"
        ])
    
    return "\n".join(lines)


def format_issue_descendants(descendants_data: Dict[str, Any]) -> str:
    """Format issue descendants hierarchy."""
    root_issue = descendants_data.get("root_issue", {})
    descendants = descendants_data.get("descendants", [])
    total_count = descendants_data.get("total_count", 0)
    hierarchy_depth = descendants_data.get("hierarchy_depth", 0)
    
    lines = [
        f"**Issue Hierarchy: {root_issue.get('issue_key', 'N/A')}**",
        "",
        f"📝 **Root Issue:** {root_issue.get('summary', 'No summary')}",
        f"👤 **Assignee:** {root_issue.get('assignee', 'Unassigned')}",
        f"🏷️ **Status:** {root_issue.get('status', 'Unknown')}",
        f"🏢 **Team:** {root_issue.get('team', 'Unknown')}",
        "",
        f"📊 **Hierarchy Statistics:**",
        f"• Total descendants: {total_count}",
        f"• Maximum depth: {hierarchy_depth}",
    ]
    
    # Add root issue dates if available
    dates = root_issue.get("dates", {})
    if dates:
        lines.extend([
            "",
            f"📅 **Root Issue Dates:**",
            f"• Created: {format_date(dates.get('created_at'))}",
            f"• Updated: {format_date(dates.get('updated_at'))}",
        ])
        
        if dates.get("start_date"):
            lines.append(f"• Started: {format_date(dates.get('start_date'))}")
        if dates.get("end_date"):
            lines.append(f"• Completed: {format_date(dates.get('end_date'))}")
    
    # Add descendants summary
    if descendants:
        lines.extend([
            "",
            f"⬇️ **Descendant Issues ({total_count} total):**"
        ])
        
        # Group by parent for better organization
        parent_groups = {}
        for descendant in descendants:
            parent = descendant.get("parent_key", "Unknown")
            if parent not in parent_groups:
                parent_groups[parent] = []
            parent_groups[parent].append(descendant)
        
        # Show first few descendants from each group
        for parent, children in list(parent_groups.items())[:5]:  # Limit to first 5 groups
            lines.append(f"")
            lines.append(f"**Children of {parent}:**")
            
            for i, child in enumerate(children[:10]):  # Limit to first 10 per group
                status_emoji = "🟢" if child.get("status") in ["Done", "Closed"] else "🟡" if child.get("status") in ["In Progress"] else "🔴"
                lines.append(f"  {i+1}. {status_emoji} **{child['issue_key']}** - {child['summary']}")
                lines.append(f"     👤 {child.get('assignee', 'Unassigned')} | 💬 {child.get('comments_count', 0)} comments")
            
            if len(children) > 10:
                lines.append(f"     ... and {len(children) - 10} more")
        
        if len(parent_groups) > 5:
            lines.append(f"")
            lines.append(f"... and {len(parent_groups) - 5} more parent groups")
    
    else:
        lines.extend([
            "",
            "📭 **No descendant issues found**"
        ])
    
    return "\n".join(lines)


def format_date(date_str: Optional[str]) -> str:
    """Format ISO date string for display."""
    if not date_str:
        return "Not set"
    
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, AttributeError):
        return date_str


def format_connectivity_status(status: Dict[str, Any]) -> str:
    """Format system connectivity status."""
    lines = [
        "**System Health Status**",
        ""
    ]
    
    # Overall status
    jira_status = status.get("jira_connected", False)
    db_status = status.get("database_connected", False)
    
    lines.extend([
        f"🔗 **Jira Connection:** {'✅ Connected' if jira_status else '❌ Disconnected'}",
        f"🗄️ **Database:** {'✅ Connected' if db_status else '❌ Disconnected'}",
    ])
    
    # Last harvest info
    last_harvest = status.get("last_harvest")
    if last_harvest:
        lines.extend([
            "",
            f"🔄 **Last Data Harvest:** {format_date(last_harvest)}"
        ])
    
    # Additional details if available
    details = status.get("details", {})
    if details:
        lines.extend([
            "",
            "📋 **Details:**"
        ])
        for key, value in details.items():
            lines.append(f"• {key}: {value}")
    
    return "\n".join(lines)


def clean_response_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and prepare response data for MCP consumption."""
    # Remove any sensitive fields or internal metadata
    cleaned = {}
    
    for key, value in data.items():
        # Skip internal fields
        if key.startswith("_") or key in ["password", "token", "secret"]:
            continue
        
        cleaned[key] = value
    
    return cleaned


def validate_limit(limit: Optional[int], default: int = 50, maximum: int = 500) -> int:
    """Validate and normalize limit parameter."""
    if limit is None:
        return default
    
    if limit < 1:
        return 1
    
    if limit > maximum:
        return maximum
    
    return limit


def safe_json_dumps(data: Any, indent: int = 2) -> str:
    """Safely serialize data to JSON string."""
    try:
        return json.dumps(data, indent=indent, default=str, ensure_ascii=False)
    except (TypeError, ValueError) as e:
        return f"Error serializing data: {str(e)}" 