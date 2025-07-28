"""
Admin Tools for MCP Server

System administration tools for connectivity testing, harvest management,
and system health monitoring.
"""
import logging
from typing import Any, Dict, List, Optional
from fastmcp import FastMCP

import mcp_types as types
from client import client, WorkSupportAPIError
from utils import format_connectivity_status, safe_json_dumps

logger = logging.getLogger(__name__)


class AdminTools:
    """System administration and health monitoring tools."""
    
    def __init__(self, mcp_server: FastMCP):
        self.server = mcp_server
        self._register_tools()
    
    def _register_tools(self):
        """Register all admin tools with the MCP server."""
        self.server.tool()(self.test_connectivity)
        self.server.tool()(self.trigger_harvest)
        self.server.tool()(self.get_harvest_status)
    
    async def test_connectivity(
        self,
        include_details: bool = False
    ) -> List[types.TextContent]:
        """
        Test Jira connectivity and system health.
        
        Use this tool to check if the work-support system can connect to Jira,
        the database is accessible, and data is up to date.
        
        Args:
            include_details: Include detailed diagnostic information
        
        Returns:
            System health status and connectivity information
        """
        try:
            logger.info("Testing system connectivity")
            
            # Call work-support API
            response = await client.test_connectivity()
            
            # Parse the API response format
            services = response.get("services", {})
            jira_connected = services.get("jira") == "connected"
            db_connected = services.get("database") == "connected"
            last_harvest = response.get("last_harvest")
            
            # Format the response
            text = format_connectivity_status({
                "jira_connected": jira_connected,
                "database_connected": db_connected,
                "last_harvest": last_harvest
            })
            
            text += "\n\n**🔧 Recommendations:**"
            
            if not jira_connected:
                text += "\n• 🔴 Jira connection failed - check API credentials and network"
                text += "\n• Consider running harvest job when connection is restored"
            
            if not db_connected:
                text += "\n• 🔴 Database connection failed - check database service"
            
            if jira_connected and db_connected:
                text += "\n• ✅ All systems operational"
                
                # Check data freshness
                if last_harvest:
                    # Simple check - in real implementation would parse the date
                    text += "\n• 💡 Consider running incremental harvest if data seems stale"
                else:
                    text += "\n• ⚠️ No recent harvest data - consider running full harvest"
            
            # Add detailed info if requested
            if include_details:
                details = response.get("details", {})
                if details:
                    text += "\n\n**🔍 Detailed Information:**"
                    for key, value in details.items():
                        text += f"\n• {key}: {value}"
            
            return [types.TextContent(type="text", text=text)]
            
        except WorkSupportAPIError as e:
            logger.error(f"API error in test_connectivity: {e}")
            
            error_text = "**System Health Check Failed**\n\n"
            error_text += f"❌ **Error:** {str(e)}\n\n"
            
            if e.status_code >= 500:
                error_text += "*The work-support server appears to be experiencing issues.*\n"
                error_text += "*Please check server logs or contact system administrator.*"
            else:
                error_text += "*This may be a temporary issue. Please try again in a moment.*"
            
            return [types.TextContent(type="text", text=error_text)]
        
        except Exception as e:
            logger.error(f"Unexpected error in test_connectivity: {e}")
            return [types.TextContent(
                type="text",
                text=f"**System check failed:** {str(e)}\n\n*Unable to reach work-support server.*"
            )]
    
    async def trigger_harvest(
        self,
        harvest_type: str = "incremental",
        dry_run: bool = False
    ) -> List[types.TextContent]:
        """
        Trigger a data harvest from Jira.
        
        Use this tool to initiate data synchronization from Jira. This should be used
        when data seems outdated or after system maintenance.
        
        Args:
            harvest_type: Type of harvest (full, incremental, team_only)
            dry_run: Run in test mode without making changes
        
        Returns:
            Harvest job status and information
        """
        try:
            logger.info(f"Triggering harvest: type={harvest_type}, dry_run={dry_run}")
            
            # Call work-support API
            response = await client.trigger_harvest(
                harvest_type=harvest_type,
                dry_run=dry_run
            )
            
            job_id = response.get("job_id")
            status = response.get("status", "unknown")
            message = response.get("message", "")
            
            text = f"**🔄 Harvest Job {'(Dry Run)' if dry_run else 'Started'}**\n\n"
            text += f"📋 **Details:**\n"
            text += f"• Job ID: {job_id}\n"
            text += f"• Type: {harvest_type}\n"
            text += f"• Status: {status}\n"
            
            if message:
                text += f"• Message: {message}\n"
            
            text += "\n**ℹ️ What happens next:**\n"
            
            if dry_run:
                text += "• This was a test run - no data was actually harvested\n"
                text += "• Review the results and run without dry_run if everything looks good\n"
            else:
                if harvest_type == "full":
                    text += "• Full harvest will sync all data from Jira\n"
                    text += "• This may take several minutes depending on data volume\n"
                elif harvest_type == "incremental":
                    text += "• Incremental harvest will sync only recent changes\n"
                    text += "• This should complete quickly\n"
                
                text += "• Use get_harvest_status to check progress\n"
                text += "• Data will be available once harvest completes\n"
            
            return [types.TextContent(type="text", text=text)]
            
        except WorkSupportAPIError as e:
            logger.error(f"API error in trigger_harvest: {e}")
            
            error_text = f"**🔄 Harvest Failed**\n\n"
            error_text += f"❌ **Error:** {str(e)}\n\n"
            
            if e.status_code == 403:
                error_text += "*You may not have permission to trigger harvest jobs.*"
            elif e.status_code == 409:
                error_text += "*A harvest job may already be running. Check harvest status.*"
            else:
                error_text += "*Please check system connectivity and try again.*"
            
            return [types.TextContent(type="text", text=error_text)]
        
        except Exception as e:
            logger.error(f"Unexpected error in trigger_harvest: {e}")
            return [types.TextContent(
                type="text",
                text=f"**Harvest failed:** {str(e)}\n\n*Please check parameters and try again.*"
            )]
    
    async def get_harvest_status(
        self,
        limit: Optional[int] = None,
        include_failed: bool = True
    ) -> List[types.TextContent]:
        """
        Check status of recent harvest jobs.
        
        Use this tool to monitor harvest job progress and review recent
        data synchronization activities.
        
        Args:
            limit: Maximum number of jobs to show (default 10)
            include_failed: Include failed jobs in the results
        
        Returns:
            Status of recent harvest jobs
        """
        try:
            # This would typically call a dedicated harvest status endpoint
            # For now, we'll return a helpful message
            text = "**🔄 Harvest Status**\n\n"
            text += "ℹ️ **Note:** Harvest status monitoring is not yet implemented in the current API.\n\n"
            text += "**Alternative approaches:**\n"
            text += "• Use `test_connectivity` to check last harvest timestamp\n"
            text += "• Check work-support server logs for harvest job status\n"
            text += "• Monitor issue data freshness to verify harvest completion\n\n"
            text += "**Typical harvest job lifecycle:**\n"
            text += "1. **Started** - Job has been queued\n"
            text += "2. **Running** - Data synchronization in progress\n"
            text += "3. **Completed** - Successfully finished\n"
            text += "4. **Failed** - Encountered errors (check logs)\n"
            
            return [types.TextContent(type="text", text=text)]
            
        except Exception as e:
            logger.error(f"Error in get_harvest_status: {e}")
            return [types.TextContent(
                type="text",
                text=f"**Status check failed:** {str(e)}\n\n*Unable to retrieve harvest status.*"
            )] 