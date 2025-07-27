"""
Jira API data models and exceptions.

These models represent data structures returned from the Jira API,
separate from database schemas in schemas.py.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

from app.models.schemas import JiraCommentSchema


class JiraIssue(BaseModel):
    """Represents a Jira issue with relevant fields from API response."""
    key: str
    issue_id: Optional[str] = None  # Maps to "id" field in response
    summary: str
    assignee: Optional[str] = None
    status: str
    labels: List[str] = []
    issue_type_id: int
    issue_type_name: str
    parent_key: Optional[str] = None
    team: Optional[str] = None  # Team from customfield_10001
    start_date: Optional[datetime] = None  # Start date from customfield_14339
    transition_date: Optional[datetime] = None  # Transition date from customfield_14343
    end_date: Optional[datetime] = None  # End date from customfield_13647
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    comments: List[JiraCommentSchema] = []  # Issue comments
    blacklist_reason: Optional[str] = None  # Reason issue was blacklisted, None if allowed


class JiraSearchResponse(BaseModel):
    """Response model for Jira search operations."""
    issues: List[Dict[str, Any]]
    total: int
    start_at: int
    max_results: int


class JiraChangelogResponse(BaseModel):
    """Response model for changelog operations."""
    values: List[Dict[str, Any]]
    next_page_token: Optional[str] = None


class JiraEndpointInfo(BaseModel):
    """Information about a whitelisted endpoint."""
    endpoint: str
    methods: List[str]
    description: str


# Jira-specific exceptions
class JiraServiceError(Exception):
    """Custom exception for Jira service errors."""
    pass


class JiraEndpointNotWhitelistedError(JiraServiceError):
    """Exception raised when trying to access a non-whitelisted endpoint."""
    pass


class JiraParsingError(JiraServiceError):
    """Exception raised when parsing Jira data fails."""
    pass


class JiraValidationError(JiraServiceError):
    """Exception raised when validation fails."""
    pass 