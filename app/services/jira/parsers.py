"""
Jira data parsing and transformation utilities.
"""
import logging
import re
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from app.config.settings import config_manager
from app.models.schemas import JiraCommentSchema
from app.models.jira import JiraIssue, JiraParsingError

logger = logging.getLogger(__name__)


class FieldParser:
    """Utility class for parsing common field types."""
    
    @staticmethod
    def parse_user_field(user_data: Optional[Dict]) -> Optional[str]:
        """Parse user field data to extract email or display name."""
        if not user_data:
            return None
        return user_data.get("emailAddress") or user_data.get("displayName")
    
    @staticmethod
    def parse_select_field(select_data: Optional[Dict]) -> Optional[str]:
        """Parse select/option field data to extract value."""
        if not select_data:
            return None
        return select_data.get("value") or select_data.get("name") or select_data.get("displayName")
    
    @staticmethod
    def parse_team_field(team_data: Any) -> Optional[str]:
        """Parse team field with various possible formats."""
        if not team_data:
            return None
            
        if isinstance(team_data, str):
            return team_data
        elif isinstance(team_data, dict):
            # If it's an object, try common field names
            return team_data.get("value") or team_data.get("name") or team_data.get("displayName") or str(team_data)
        elif team_data is not None:
            return str(team_data)
        
        return None


class JiraDataParser:
    """Handles all Jira data parsing and transformation."""
    
    def __init__(self):
        """Initialize the parser."""
        self.field_parser = FieldParser()

    def parse_issue(self, issue_data: Dict[str, Any]) -> JiraIssue:
        """Parse Jira issue data into JiraIssue object."""
        try:
            fields = issue_data.get("fields", {})
            
            # Parse assignee
            assignee = self.field_parser.parse_user_field(fields.get("assignee"))
            
            # Parse issue type
            issue_type = fields.get("issuetype", {})
            issue_type_id = int(issue_type.get("id", -1))
            issue_type_name = issue_type.get("name", "Unknown")
            
            # Parse parent
            parent_key = None
            if parent_data := fields.get("parent"):
                parent_key = parent_data.get("key")
            
            # Parse team from customfield_10001
            team = self.field_parser.parse_team_field(fields.get("customfield_10001"))
            
            # Parse custom date fields
            start_date = self.parse_custom_date(fields.get("customfield_14339"))
            transition_date = self.parse_custom_date(fields.get("customfield_14343"))
            end_date = self.parse_custom_date(fields.get("customfield_13647"))
            
            # Parse dates
            created, updated = self.parse_dates(fields, issue_data.get("key"))
            
            # Parse comments
            comments = self.parse_comments(fields.get("comment", {}))
            
            # Map assignee to anonymised name
            anonymised_assignee = config_manager.get_anonymised_name_for_assignee(assignee) if assignee else assignee

            return JiraIssue(
                key=issue_data.get("key", ""),
                issue_id=issue_data.get("id"),
                summary=fields.get("summary", ""),
                assignee=anonymised_assignee,
                status=fields.get("status", {}).get("name", "Unknown"),
                labels=fields.get("labels", []),
                issue_type_id=issue_type_id,
                issue_type_name=issue_type_name,
                parent_key=parent_key,
                team=team,
                start_date=start_date,
                transition_date=transition_date,
                end_date=end_date,
                created=created,
                updated=updated,
                comments=comments
            )
        except Exception as e:
            issue_key = issue_data.get("key", "Unknown")
            logger.error(f"Error parsing issue {issue_key}: {e}")
            raise JiraParsingError(f"Failed to parse issue {issue_key}: {e}")

    def parse_dates(self, fields: Dict[str, Any], issue_key: Optional[str] = None) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Parse created and updated dates from issue fields."""
        created = None
        updated = None
        
        try:
            if created_str := fields.get("created"):
                created = self.parse_iso_datetime(created_str)
            if updated_str := fields.get("updated"):
                updated = self.parse_iso_datetime(updated_str)
        except Exception as e:
            logger.warning(f"Error parsing dates for issue {issue_key or 'Unknown'}: {e}")
        
        return created, updated

    def parse_comments(self, comment_data: Dict[str, Any]) -> List[JiraCommentSchema]:
        """Parse comments from Jira issue comment field."""
        comments = []
        
        try:
            # Jira comment field structure: {"comments": [array of comment objects]}
            comment_list = comment_data.get("comments", [])
            
            for comment_obj in comment_list:
                try:
                    # Extract comment body (could be in body or rendered body)
                    body = comment_obj.get("body", "")
                    if isinstance(body, dict):
                        # Handle ADF (Atlassian Document Format) or other structured content
                        body = str(body)  # Convert to string representation for now
                    
                    # Parse comment dates
                    created = None
                    if created_str := comment_obj.get("created"):
                        created = self.parse_iso_datetime(created_str)
                    
                    updated = None
                    if updated_str := comment_obj.get("updated"):
                        updated = self.parse_iso_datetime(updated_str)
                    
                    comments.append(JiraCommentSchema(
                        body=body,
                        created=created,
                        updated=updated
                    ))
                except Exception as e:
                    logger.warning(f"Error parsing individual comment: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error parsing comments: {e}")
        
        return comments

    def parse_iso_datetime(self, date_str: str) -> datetime:
        """
        Parse ISO datetime string with various timezone formats.
        
        Handles formats like:
        - 2025-04-24T16:32:35.307Z
        - 2025-04-24T16:32:35.307+0100
        - 2025-04-24T16:32:35.307+01:00
        """
        try:
            # Handle 'Z' timezone indicator
            if date_str.endswith('Z'):
                date_str = date_str.replace('Z', '+00:00')
            
            # Handle timezone offsets without colon (e.g., +0100 -> +01:00)
            # Match timezone offset pattern at the end: +/-HHMM
            tz_pattern = r'([+-])(\d{2})(\d{2})$'
            match = re.search(tz_pattern, date_str)
            if match:
                sign, hours, minutes = match.groups()
                # Replace with colon format: +/-HH:MM
                date_str = re.sub(tz_pattern, f'{sign}{hours}:{minutes}', date_str)
            
            return datetime.fromisoformat(date_str)
        except Exception as e:
            logger.error(f"Error parsing ISO datetime '{date_str}': {e}")
            raise JiraParsingError(f"Invalid datetime format: {date_str}")

    def parse_custom_date(self, date_value: Any) -> Optional[datetime]:
        """
        Parse a custom date field from Jira.
        
        Handles various formats that custom date fields might return:
        - ISO date strings
        - Date objects
        - None/null values
        """
        if date_value is None:
            return None
            
        try:
            if isinstance(date_value, str):
                # Use the existing ISO datetime parser
                return self.parse_iso_datetime(date_value)
            elif isinstance(date_value, dict):
                # If it's an object, look for common date field names
                date_str = date_value.get("value") or date_value.get("date") or date_value.get("displayValue")
                if date_str:
                    return self.parse_iso_datetime(date_str)
            elif hasattr(date_value, 'isoformat'):
                # If it's already a datetime object
                return date_value
            else:
                # Try to convert to string and parse
                return self.parse_iso_datetime(str(date_value))
        except Exception as e:
            logger.warning(f"Error parsing custom date field '{date_value}': {e}")
            return None 