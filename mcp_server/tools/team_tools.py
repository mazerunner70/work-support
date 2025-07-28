"""
Team Tools for MCP Server

Tools for team analytics, metrics, and workload analysis.
"""
import logging
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

import mcp_types as types
from client import client, WorkSupportAPIError
from utils import format_team_metrics, safe_json_dumps

logger = logging.getLogger(__name__)


class TeamTools:
    """Team analytics and metrics tools."""
    
    def __init__(self, mcp_server: FastMCP):
        self.server = mcp_server
        self._register_tools()
    
    def _register_tools(self):
        """Register all team tools with the MCP server."""
        self.server.tool()(self.get_team_metrics)
        self.server.tool()(self.analyze_assignee_workload)
    
    async def get_team_metrics(
        self,
        team_name: str,
        date_range: Optional[str] = None
    ) -> List[types.TextContent]:
        """
        Get team performance metrics and workload analysis.
        
        Use this tool to analyze team productivity, completion rates, and workload distribution.
        
        Args:
            team_name: Name of the team to analyze (e.g., "Backend Team", "Frontend Team")
            date_range: Optional date range in format "YYYY-MM-DD,YYYY-MM-DD" for historical analysis
        
        Returns:
            Comprehensive team metrics including completion rates, cycle times, and workload
        """
        try:
            logger.info(f"Getting team metrics for: {team_name}")
            
            # Call work-support API
            response = await client.get_team_metrics(
                team_name=team_name,
                date_range=date_range
            )
            
            # Format the response
            text = format_team_metrics(response)
            
            # Add additional insights
            metrics = response.get("metrics", {})
            completion_rate = metrics.get("completion_rate", 0)
            active_issues = metrics.get("active_issues", 0)
            
            text += "\n\n**📈 Insights:**"
            
            if completion_rate >= 0.8:
                text += "\n• ✅ Excellent completion rate - team is performing well"
            elif completion_rate >= 0.6:
                text += "\n• ⚠️ Moderate completion rate - room for improvement"
            else:
                text += "\n• 🔴 Low completion rate - may need attention"
            
            if active_issues > 20:
                text += "\n• ⚠️ High number of active issues - consider workload distribution"
            elif active_issues < 5:
                text += "\n• ℹ️ Low active workload - team may be available for new work"
            else:
                text += "\n• ✅ Healthy active workload"
            
            return [types.TextContent(type="text", text=text)]
            
        except WorkSupportAPIError as e:
            logger.error(f"API error in get_team_metrics: {e}")
            
            if e.status_code == 404:
                error_text = f"**Team not found:** {team_name}\n\n*Check the team name spelling or available teams.*"
            else:
                error_text = f"**Error getting team metrics:** {str(e)}"
            
            return [types.TextContent(type="text", text=error_text)]
        
        except Exception as e:
            logger.error(f"Unexpected error in get_team_metrics: {e}")
            return [types.TextContent(
                type="text",
                text=f"**Unexpected error:** {str(e)}\n\n*Please check the team name and try again.*"
            )]
    
    async def analyze_assignee_workload(
        self,
        assignee: str,
        include_historical: bool = False,
        time_period: Optional[str] = None
    ) -> List[types.TextContent]:
        """
        Analyze individual assignee workload and patterns.
        
        Use this tool to understand an individual's current workload, productivity patterns,
        and work distribution across different types of issues.
        
        Args:
            assignee: Name or email of the assignee to analyze
            include_historical: Include historical performance data
            time_period: Time period for analysis (week, month, quarter)
        
        Returns:
            Detailed workload analysis for the specified assignee
        """
        try:
            logger.info(f"Analyzing workload for assignee: {assignee}")
            
            # Get current assigned issues
            response = await client.query_issues(
                assignee=assignee,
                limit=100  # Get more for analysis
            )
            
            issues = response.get("issues", [])
            total_count = response.get("total_count", 0)
            
            if not issues:
                text = f"**Workload Analysis: {assignee}**\n\n"
                text += "📭 **No issues currently assigned**\n\n"
                text += "*This person may be available for new assignments.*"
                return [types.TextContent(type="text", text=text)]
            
            # Analyze issues by status
            status_counts = {}
            issue_type_counts = {}
            
            for issue in issues:
                status = issue.get("status", "Unknown")
                issue_type = issue.get("issue_type", "Unknown")
                
                status_counts[status] = status_counts.get(status, 0) + 1
                issue_type_counts[issue_type] = issue_type_counts.get(issue_type, 0) + 1
            
            # Format workload analysis
            text = f"**Workload Analysis: {assignee}**\n\n"
            text += f"📊 **Summary:**\n"
            text += f"• Total Assigned Issues: {len(issues)}"
            if total_count > len(issues):
                text += f" (showing {len(issues)} of {total_count})"
            text += "\n\n"
            
            # Status breakdown
            text += "📈 **By Status:**\n"
            for status, count in sorted(status_counts.items()):
                percentage = (count / len(issues)) * 100
                text += f"• {status}: {count} ({percentage:.0f}%)\n"
            
            # Issue type breakdown
            text += "\n📋 **By Type:**\n"
            for issue_type, count in sorted(issue_type_counts.items()):
                percentage = (count / len(issues)) * 100
                text += f"• {issue_type}: {count} ({percentage:.0f}%)\n"
            
            # Workload insights
            in_progress = status_counts.get("In Progress", 0)
            to_do = status_counts.get("To Do", 0)
            
            text += "\n**💡 Insights:**\n"
            
            if in_progress > 5:
                text += "• ⚠️ High number of in-progress items - may indicate context switching\n"
            elif in_progress == 0:
                text += "• 🔴 No items in progress - may need task assignment\n"
            else:
                text += "• ✅ Healthy number of active tasks\n"
            
            if to_do > 10:
                text += "• 📈 Large backlog - consider prioritization\n"
            
            workload_level = len(issues)
            if workload_level > 15:
                text += "• 🔴 Heavy workload - consider load balancing\n"
            elif workload_level < 5:
                text += "• ✅ Light workload - available for additional tasks\n"
            else:
                text += "• ✅ Balanced workload\n"
            
            return [types.TextContent(type="text", text=text)]
            
        except WorkSupportAPIError as e:
            logger.error(f"API error in analyze_assignee_workload: {e}")
            return [types.TextContent(
                type="text",
                text=f"**Error analyzing workload:** {str(e)}\n\n*Check the assignee name and try again.*"
            )]
        
        except Exception as e:
            logger.error(f"Unexpected error in analyze_assignee_workload: {e}")
            return [types.TextContent(
                type="text",
                text=f"**Unexpected error:** {str(e)}\n\n*Please check the assignee name and try again.*"
            )] 