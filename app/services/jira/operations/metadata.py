"""
Jira metadata and configuration operations.
"""
import logging
from typing import Dict, Any

from app.services.jira.client import JiraClient


logger = logging.getLogger(__name__)


class JiraMetadataOperations:
    """Metadata and configuration operations."""
    
    def __init__(self, client: JiraClient):
        """Initialize metadata operations with client dependency."""
        self.client = client



    async def test_connection(self) -> bool:
        """
        Test connection to Jira API.
        
        Returns:
            True if connection is successful, False otherwise
        """
        return await self.client.test_connection()

    def get_whitelisted_endpoints_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all whitelisted endpoints for debugging/monitoring.
        
        Returns:
            Dictionary with endpoint information
        """
        return self.client.get_whitelisted_endpoints_info() 