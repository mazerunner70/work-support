"""
MCP Server Configuration

Configuration settings for the MCP server including work-support API connection,
logging, and server behavior settings.
"""
import os
from typing import Optional


class MCPConfig:
    """Configuration settings for the MCP server."""
    
    def __init__(self):
        # Work-support REST API configuration
        self.work_support_url = os.getenv("WORK_SUPPORT_URL", "http://localhost:8000")
        self.work_support_api_key = os.getenv("WORK_SUPPORT_API_KEY")
        
        # MCP Server configuration
        self.server_name = "work-support"
        self.server_version = "0.1.0"
        self.description = "Work Support MCP Server - Provides access to Jira issue data and team metrics"
        
        # Logging configuration
        self.log_level = os.getenv("MCP_LOG_LEVEL", "INFO")
        
        # Request timeout settings
        self.request_timeout = float(os.getenv("MCP_REQUEST_TIMEOUT", "30.0"))
        
        # Default limits for queries
        self.default_limit = int(os.getenv("MCP_DEFAULT_LIMIT", "50"))
        self.max_limit = int(os.getenv("MCP_MAX_LIMIT", "500"))

    @property
    def work_support_headers(self) -> dict:
        """Get headers for work-support API requests."""
        headers = {"Content-Type": "application/json"}
        if self.work_support_api_key:
            headers["Authorization"] = f"Bearer {self.work_support_api_key}"
        return headers

    def validate(self) -> None:
        """Validate configuration settings."""
        if not self.work_support_url:
            raise ValueError("WORK_SUPPORT_URL environment variable is required")
        
        if not self.work_support_url.startswith(("http://", "https://")):
            raise ValueError("WORK_SUPPORT_URL must be a valid HTTP/HTTPS URL")


# Global config instance
config = MCPConfig() 