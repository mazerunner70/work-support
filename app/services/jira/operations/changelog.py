"""
Jira changelog operations with pagination and batch processing.
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from app.services.jira.client import JiraClient
from app.models.jira import JiraServiceError

logger = logging.getLogger(__name__)


class JiraChangelogOperations:
    """Changelog related operations with efficient batch processing."""
    
    def __init__(self, client: JiraClient):
        """Initialize changelog operations with client dependency."""
        self.client = client

    async def bulk_fetch_changelogs(self, issue_ids: List[str], chunk_size: int = 100) -> List[Dict[str, Any]]:
        """
        Bulk fetch changelogs for multiple issues efficiently.
        
        Args:
            issue_ids: List of Jira issue IDs to fetch changelogs for
            chunk_size: Number of issues to process per API call (max 100)
            
        Returns:
            List of changelog data from Jira API
            
        Raises:
            JiraServiceError: If the operation fails
        """
        if not issue_ids:
            return []
            
        all_changelogs = []
        
        # Process in chunks to respect API limits
        for i in range(0, len(issue_ids), chunk_size):
            chunk = issue_ids[i:i + chunk_size]
            chunk_num = i // chunk_size + 1
            
            logger.info(f"Fetching changelogs for {len(chunk)} issues (chunk {chunk_num})")
            
            try:
                chunk_changelogs = await self._fetch_chunk_changelogs(chunk, chunk_num)
                all_changelogs.extend(chunk_changelogs)
                
                # Rate limiting between chunks
                if i + chunk_size < len(issue_ids):
                    await asyncio.sleep(0.2)
                    
            except Exception as e:
                logger.error(f"Error processing changelog chunk {chunk_num}: {e}")
                # Continue with other chunks even if one fails
                continue
        
        logger.info(f"🔍 PARSE: Total changelog entries parsed: {len(all_changelogs)} from {len(issue_ids)} issues")
        logger.info(f"Successfully fetched changelogs for {len(all_changelogs)} issue/changelog combinations")
        return all_changelogs

    async def _fetch_chunk_changelogs(self, chunk: List[str], chunk_num: int) -> List[Dict[str, Any]]:
        """
        Fetch changelogs for a single chunk with pagination support.
        
        Args:
            chunk: List of issue IDs/keys for this chunk
            chunk_num: Chunk number for logging
            
        Returns:
            List of changelog entries for this chunk
        """
        chunk_changelogs = []
        next_page_token = None
        page_num = 1
        
        while True:  # Continue until no more pages
            payload = {
                "issueIdsOrKeys": chunk,
                "maxResults": 1000  # Request maximum results per page
            }
            
            # Add pagination token if we have one
            if next_page_token:
                payload["nextPageToken"] = next_page_token
            
            try:
                response = await self.client.make_request(
                    method="POST",
                    endpoint="changelog/bulkfetch",
                    payload=payload,
                    timeout=30.0
                )
                
                chunk_data = self.client.handle_response(
                    response,
                    f"changelog fetch for chunk {chunk_num}, page {page_num}"
                )
                
                # Log response parsing details and extract data
                page_changelogs = self._process_changelog_response(chunk_data, chunk_num, page_num)
                chunk_changelogs.extend(page_changelogs)
                
                logger.info(f"Loaded {len(page_changelogs)} changelog entries from chunk {chunk_num}, page {page_num}")
                
                # Check for next page
                next_page_token = chunk_data.get("nextPageToken")
                if not next_page_token:
                    break  # No more pages
                
                page_num += 1
                
                # Rate limiting between pages
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error fetching changelogs for chunk {chunk_num}, page {page_num}: {e}")
                break  # Exit pagination loop on error
        
        logger.info(f"Chunk {chunk_num} complete: {len(chunk_changelogs)} total changelog entries across {page_num} pages")
        return chunk_changelogs

    def _process_changelog_response(self, chunk_data: Dict[str, Any], chunk_num: int, page_num: int) -> List[Dict[str, Any]]:
        """
        Process and validate changelog response data.
        
        Args:
            chunk_data: Response data from Jira API
            chunk_num: Chunk number for logging
            page_num: Page number for logging
            
        Returns:
            List of changelog entries from the response
        """
        # Log response parsing details
        if isinstance(chunk_data, dict):
            if "issueChangeLogs" in chunk_data:
                issue_change_logs = chunk_data["issueChangeLogs"]
                if isinstance(issue_change_logs, list):
                    # Extract all changelog entries from all issues
                    all_changelog_entries = []
                    
                    for issue_log in issue_change_logs:
                        if isinstance(issue_log, dict) and "changeHistories" in issue_log:
                            change_histories = issue_log["changeHistories"]
                            issue_id = issue_log.get("issueId", "unknown")
                            
                            if isinstance(change_histories, list):
                                # Add issueId to each changelog entry for context and convert timestamp
                                for history in change_histories:
                                    if isinstance(history, dict):
                                        history_with_issue = history.copy()
                                        history_with_issue["issueId"] = issue_id
                                        
                                        # Convert Unix timestamp to datetime object for database compatibility
                                        if "created" in history_with_issue and isinstance(history_with_issue["created"], (int, float)):
                                            try:
                                                timestamp = history_with_issue["created"]
                                                # Check if timestamp is in milliseconds (typical for Jira)
                                                # Timestamps after year 2001 in seconds would be > 1e9
                                                # If > 1e10, it's likely milliseconds
                                                if timestamp > 1e10:
                                                    timestamp = timestamp / 1000.0
                                                    
                                                history_with_issue["created"] = datetime.fromtimestamp(timestamp)
                                            except (ValueError, OSError) as e:
                                                logger.warning(f"Failed to convert timestamp {history_with_issue['created']} to datetime: {e}")
                                                # Keep original value if conversion fails
                                        
                                        all_changelog_entries.append(history_with_issue)
                    
                    logger.info(f"🔍 PARSE: Found {len(all_changelog_entries)} changelog entries across {len(issue_change_logs)} issues")
                    if len(all_changelog_entries) > 0:
                        first_entry = all_changelog_entries[0]
                        if isinstance(first_entry, dict):
                            logger.info(f"🔍 PARSE: Changelog entry structure: {list(first_entry.keys())}")
                    else:
                        logger.warning(f"🔍 PARSE: No changelog entries found in response")
                    
                    return all_changelog_entries
                else:
                    logger.error(f"🔍 PARSE: issueChangeLogs is not a list: {type(issue_change_logs)}")
                    return []
            else:
                available_keys = list(chunk_data.keys()) if isinstance(chunk_data, dict) else "N/A"
                logger.error(f"🔍 PARSE: Response missing 'issueChangeLogs' key - available keys: {available_keys}")
                return []
        else:
            logger.error(f"🔍 PARSE: Response is not a JSON object: {type(chunk_data)}")
            return [] 