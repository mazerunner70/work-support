"""
Database models for the Work Support Python Server.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class TeamMember(Base):
    """Team members table."""
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    jira_id = Column(String, nullable=False)
    github_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.current_timestamp())

    def __repr__(self):
        return f"<TeamMember(name='{self.name}', jira_id='{self.jira_id}', github_id='{self.github_id}')>"


class IssueType(Base):
    """Issue types table for hierarchical relationships."""
    __tablename__ = "issue_types"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String)
    child_type_ids = Column(Text)  # JSON array of child type IDs
    created_at = Column(DateTime, default=func.current_timestamp())

    # Relationship to issues
    issues = relationship("Issue", back_populates="issue_type")

    def __repr__(self):
        return f"<IssueType(id={self.id}, name='{self.name}')>"


class Comment(Base):
    """Comments table for issue comments."""
    __tablename__ = "comments"
    __table_args__ = (
        Index('ix_comments_created_at', 'created_at'),
        Index('ix_comments_issue_created', 'issue_key', 'created_at'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_key = Column(String, ForeignKey('jira_issues.issue_key'), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime)
    jira_comment_id = Column(String)  # Original Jira comment ID for tracking

    # Relationship to issue
    issue = relationship("Issue", back_populates="comment_records")

    def __repr__(self):
        return f"<Comment(issue_key='{self.issue_key}', created_at='{self.created_at}')>"


class Changelog(Base):
    """Changelog table for issue change history."""
    __tablename__ = "jira_changelogs"
    __table_args__ = (
        Index('ix_jira_changelogs_created_at', 'created_at'),
        Index('ix_jira_changelogs_issue_created', 'issue_id', 'created_at'),
        Index('ix_jira_changelogs_field', 'field_name'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(String, ForeignKey('jira_issues.issue_id'), nullable=False)  # Maps to Jira issueId
    jira_changelog_id = Column(String, nullable=False)  # Jira changelog ID
    field_name = Column(String, nullable=False)  # Field that changed (status, assignee, etc.)
    from_value = Column(Text)  # Previous value
    to_value = Column(Text)  # New value
    from_display = Column(Text)  # Human-readable previous value
    to_display = Column(Text)  # Human-readable new value
    created_at = Column(DateTime, nullable=False)  # When change occurred
    harvested_at = Column(DateTime, default=func.current_timestamp())

    # Relationship to issue via issue_id
    issue = relationship("Issue", back_populates="changelog_records", foreign_keys=[issue_id])

    def __repr__(self):
        return f"<Changelog(issue_id='{self.issue_id}', field='{self.field_name}', created_at='{self.created_at}')>"


class ChangesLog(Base):
    """Changes log table for tracking all system changes."""
    __tablename__ = "changes_log"
    __table_args__ = (
        Index('ix_changes_log_timestamp', 'timestamp'),
        Index('ix_changes_log_issue_timestamp', 'issue_key', 'timestamp'),
        Index('ix_changes_log_field', 'field_name'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_key = Column(String, ForeignKey('jira_issues.issue_key'), nullable=False)
    timestamp = Column(DateTime, default=func.current_timestamp(), nullable=False)
    field_name = Column(String, nullable=False)  # Field that changed (status, assignee, comments, changelogs, etc.)
    updated_value = Column(Text)  # New value as string
    change_type = Column(String, nullable=False)  # 'field_update', 'comment_added', 'changelog_added'

    # Relationship to issue
    issue = relationship("Issue", back_populates="changes_log_records")

    def __repr__(self):
        return f"<ChangesLog(issue_key='{self.issue_key}', field='{self.field_name}', timestamp='{self.timestamp}')>"


class Issue(Base):
    """Issues table."""
    __tablename__ = "jira_issues"
    __table_args__ = (
        Index('ix_jira_issues_issue_id', 'issue_id'),  # Index for issue_id lookups
        Index('ix_jira_issues_start_date', 'start_date'),  # Index for start date queries
        Index('ix_jira_issues_transition_date', 'transition_date'),  # Index for transition date queries
        Index('ix_jira_issues_end_date', 'end_date'),  # Index for end date queries
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_key = Column(String, nullable=False, unique=True)
    issue_id = Column(String)  # Jira issue ID from the "id" field  
    summary = Column(String)
    assignee = Column(String)
    status = Column(String)
    labels = Column(Text)  # JSON array
    issue_type_id = Column(Integer, ForeignKey('issue_types.id'))
    parent_key = Column(String)  # Reference to parent issue key
    source = Column(String, nullable=False)  # 'jira' or 'github'
    team = Column(String)  # Team from Jira customfield_10001
    start_date = Column(DateTime)  # Start date from Jira customfield_14339
    transition_date = Column(DateTime)  # Transition date from Jira customfield_14343
    end_date = Column(DateTime)  # End date from Jira customfield_13647
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    harvested_at = Column(DateTime, default=func.current_timestamp())
    blacklist_reason = Column(String)  # Reason issue was blacklisted, NULL if allowed
    comments = Column(Text)  # JSON array of comments with body, created, updated - DEPRECATED, use comment_records

    # Relationships
    issue_type = relationship("IssueType", back_populates="issues")
    comment_records = relationship("Comment", back_populates="issue", cascade="all, delete-orphan")
    changelog_records = relationship("Changelog", back_populates="issue", cascade="all, delete-orphan", foreign_keys="[Changelog.issue_id]")
    changes_log_records = relationship("ChangesLog", back_populates="issue", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Issue(key='{self.issue_key}', summary='{self.summary}', source='{self.source}')>"


class HarvestJob(Base):
    """Harvest jobs table."""
    __tablename__ = "harvest_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=func.current_timestamp())
    completed_at = Column(DateTime)
    status = Column(String)  # 'running', 'completed', 'failed'
    records_processed = Column(Integer, default=0)
    error_message = Column(Text)

    def __repr__(self):
        return f"<HarvestJob(id={self.id}, status='{self.status}', records={self.records_processed})>"


class ReloadTracking(Base):
    """Data reload tracking table."""
    __tablename__ = "reload_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reload_started = Column(DateTime, default=func.current_timestamp())
    status = Column(String, default='running')  # 'running', 'completed', 'failed'
    completed_at = Column(DateTime)
    records_processed = Column(Integer, default=0)
    error_message = Column(Text)
    source = Column(String, default='manual')  # 'manual', 'automatic', 'scheduled'
    triggered_by = Column(String)  # user info for manual reloads, 'system' for others
    issues_deleted = Column(Integer, default=0)  # count of old issues deleted
    duration_seconds = Column(Integer)  # total duration in seconds

    def __repr__(self):
        return (f"<ReloadTracking(id={self.id}, status='{self.status}', "
                f"source='{self.source}', started={self.reload_started})>")
