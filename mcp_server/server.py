#!/usr/bin/env python3
"""
Work Support MCP Server

Main MCP protocol server that provides access to work support data for AI agents.
This is the entry point for the MCP server implementation.
"""
import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

import mcp_types as types
from config import config
from tools.query_tools import QueryTools
from tools.team_tools import TeamTools  
from tools.admin_tools import AdminTools

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WorkSupportMCPServer:
    """Main Work Support MCP Server class."""
    
    def __init__(self):
        """Initialize the MCP server with configuration and tools."""
        try:
            # Validate configuration
            config.validate()
            
            # Create FastMCP server instance
            self.mcp = FastMCP(
                name=config.server_name,
                version=config.server_version
            )
            
            # Set server description
            self._set_server_description()
            
            # Initialize tool handlers
            self.query_tools = None
            self.team_tools = None
            self.admin_tools = None
            
            logger.info(f"Initialized {config.server_name} v{config.server_version}")
            
        except Exception as e:
            logger.error(f"Failed to initialize MCP server: {e}")
            raise
    
    def _set_server_description(self):
        """Set the server description with usage guidelines."""
        description = f"""
{config.description}

INTERACTION RULES:
- Use reasonable limits (10-50 for exploration, up to 500 for analysis)
- Always provide context and interpret data for users
- Check system connectivity before troubleshooting data issues
- Combine multiple tools for comprehensive analysis
- Start with broad queries, then narrow down based on results

AVAILABLE TOOLS:
- query_issues: Find issues by team, status, assignee, or type
- get_issue_details: Get comprehensive information about specific issues
- search_issues: Search issues by keywords in summary/description
- search_issues_by_comments: Find issues with recent comments (active issues)
- get_issue_types: List all issue types with their database IDs
- get_team_metrics: Analyze team performance and workload
- analyze_assignee_workload: Review individual workload and patterns
- test_connectivity: Check system health and data freshness
- trigger_harvest: Initiate data synchronization from Jira
- get_harvest_status: Monitor harvest job progress

For detailed usage, see the individual tool descriptions.
        """.strip()
        
        # In FastMCP, we would set this via the server properties
        # For now, we'll log it as the server starts
        logger.info("Server description set")
    
    def setup_tools(self):
        """Initialize and register all MCP tools."""
        try:
            logger.info("Setting up MCP tools...")
            
            # Initialize tool handlers with the MCP server instance
            self.query_tools = QueryTools(self.mcp)
            self.team_tools = TeamTools(self.mcp)
            self.admin_tools = AdminTools(self.mcp)
            
            logger.info("All MCP tools registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup tools: {e}")
            raise
    
    def run(self, transport: str = "stdio"):
        """
        Run the MCP server with the specified transport.
        
        Args:
            transport: Transport protocol to use ("stdio", "sse", etc.)
        """
        try:
            logger.info(f"Starting Work Support MCP Server on {transport} transport")
            logger.info(f"Work-support API URL: {config.work_support_url}")
            
            # Setup tools before running
            self.setup_tools()
            
            # Run the FastMCP server - let it handle its own event loop
            self.mcp.run(transport=transport)
            
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise


# Global server instance
server = WorkSupportMCPServer()


def main():
    """Main entry point for the MCP server."""
    try:
        # Check if we have command line arguments for transport
        transport = "stdio"  # Default transport
        
        if len(sys.argv) > 1:
            transport = sys.argv[1]
        
        # Run the server
        server.run(transport=transport)
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the server directly without asyncio
    main() 