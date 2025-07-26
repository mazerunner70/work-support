"""
Database models for the Work Support Python Server.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
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


class Issue(Base):
    """Issues table."""
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_key = Column(String, nullable=False, unique=True)
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

    # Relationship to issue type
    issue_type = relationship("IssueType", back_populates="issues")

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
