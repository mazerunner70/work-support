"""
Pydantic schemas for API request/response models.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class JiraCommentSchema(BaseModel):
    """Jira comment schema."""
    body: str
    created: Optional[datetime] = None
    updated: Optional[datetime] = None


class CommentSchema(BaseModel):
    """Comment schema for database model."""
    id: Optional[int] = None
    issue_key: str
    body: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    jira_comment_id: Optional[str] = None

    class Config:
        from_attributes = True


class ChangelogSchema(BaseModel):
    """Changelog schema for database model."""
    id: Optional[int] = None
    issue_id: str
    jira_changelog_id: str
    field_name: str
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    from_display: Optional[str] = None
    to_display: Optional[str] = None
    created_at: datetime
    harvested_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChangesLogSchema(BaseModel):
    """Changes log schema for database model."""
    id: Optional[int] = None
    issue_key: str
    timestamp: datetime
    field_name: str
    updated_value: Optional[str] = None
    change_type: str

    class Config:
        from_attributes = True


class TeamMemberSchema(BaseModel):
    """Team member schema."""
    id: Optional[int] = None
    name: str
    jira_id: str
    github_id: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IssueTypeSchema(BaseModel):
    """Issue type schema."""
    id: int
    name: str
    url: Optional[str] = None
    child_type_ids: List[int] = Field(default_factory=list)
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class IssueSchema(BaseModel):
    """Issue schema."""
    id: Optional[int] = None
    issue_key: str
    issue_id: Optional[str] = None  # Jira issue ID from the "id" field
    summary: Optional[str] = None
    assignee: Optional[str] = None
    status: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    issue_type_id: Optional[int] = None
    parent_key: Optional[str] = None
    source: str
    team: Optional[str] = None  # Team from Jira customfield_10001
    start_date: Optional[datetime] = None  # Start date from Jira customfield_14339
    transition_date: Optional[datetime] = None  # Transition date from Jira customfield_14343
    end_date: Optional[datetime] = None  # End date from Jira customfield_13647
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    harvested_at: Optional[datetime] = None
    blacklist_reason: Optional[str] = None  # Reason issue was blacklisted, None if allowed
    comments: List[JiraCommentSchema] = Field(default_factory=list)  # DEPRECATED: Use comment_records instead
    comment_records: List['CommentSchema'] = Field(default_factory=list)  # Comments from separate table
    changelog_records: List['ChangelogSchema'] = Field(default_factory=list)  # Changelogs from separate table
    changes_log_records: List['ChangesLogSchema'] = Field(default_factory=list)  # System changes log

    class Config:
        from_attributes = True


class IssueHierarchySchema(BaseModel):
    """Issue hierarchy schema for nested issue display."""
    issue_key: str
    summary: Optional[str] = None
    issue_type: Optional[str] = None
    children: List['IssueHierarchySchema'] = Field(default_factory=list)


class HarvestJobSchema(BaseModel):
    """Harvest job schema."""
    id: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: Optional[str] = None
    records_processed: int = 0
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class ReloadTrackingSchema(BaseModel):
    """Reload tracking schema."""
    id: Optional[int] = None
    reload_started: Optional[datetime] = None
    status: str = 'running'
    completed_at: Optional[datetime] = None
    records_processed: int = 0
    error_message: Optional[str] = None
    source: str = 'manual'
    triggered_by: Optional[str] = None
    issues_deleted: int = 0
    duration_seconds: Optional[int] = None

    class Config:
        from_attributes = True


# API Response schemas

class IssueKeysResponse(BaseModel):
    """Response schema for issue keys endpoint."""
    issue_keys: List[str]
    total_count: int
    harvested_at: Optional[datetime] = None


class IssueHierarchyResponse(BaseModel):
    """Response schema for issue hierarchy endpoint."""
    hierarchy: List[IssueHierarchySchema]
    total_count: int
    harvested_at: Optional[datetime] = None


class ReloadStatusResponse(BaseModel):
    """Response schema for reload status endpoint."""
    reload_id: int
    reload_started: datetime
    status: str
    completed_at: Optional[datetime] = None
    records_processed: int
    source: str
    triggered_by: Optional[str] = None
    issues_deleted: int = 0
    duration_seconds: Optional[int] = None


class HealthCheckResponse(BaseModel):
    """Response schema for health check endpoint."""
    status: str
    database: str
    last_harvest: Optional[datetime] = None
    reload_in_progress: bool = False


class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Update forward references
IssueHierarchySchema.model_rebuild()
IssueSchema.model_rebuild()
