"""
MCP-specific API routes for work-support data.

These endpoints are optimized for MCP (Model Context Protocol) clients,
providing clean JSON responses with consistent formatting for AI agents.
"""
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_db
from app.models.database import Issue, HarvestJob
from app.services.mcp_adapters import MCPResponseFormatter, MCPQueryBuilder
from app.services.database_service import db_service
from app.services.harvest_service import HarvestService

logger = logging.getLogger(__name__)

# Create MCP router with prefix
mcp_router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@mcp_router.get("/issues")
async def mcp_query_issues(
    db: Session = Depends(get_db),
    assignee: Optional[str] = Query(None, description="Filter by assignee name"),
    status: Optional[str] = Query(None, description="Filter by status"),
    team: Optional[str] = Query(None, description="Filter by team"),
    issue_type: Optional[str] = Query(None, description="Filter by issue type name"),
    parent_key: Optional[str] = Query(None, description="Filter by parent issue key"),
    source: Optional[str] = Query(None, description="Filter by source (jira/github)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results")
):
    """
    Query issues with flexible filtering - optimized for MCP clients.
    
    Returns a clean JSON response with issue data formatted for AI agent consumption.
    """
    try:
        # Build filters dictionary
        filters = {
            "assignee": assignee,
            "status": status,
            "team": team,
            "issue_type": issue_type,
            "parent_key": parent_key,
            "source": source
        }
        
        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}
        
        # Validate source filter
        if "source" in filters and filters["source"] not in ["jira", "github"]:
            return MCPResponseFormatter.format_error_response(
                "validation_error",
                "Source must be 'jira' or 'github'",
                {"valid_sources": ["jira", "github"]}
            )
        
        # Build and execute query
        query = MCPQueryBuilder.build_issue_query(db, filters)
        query = query.limit(limit)
        
        # Execute query with relationships loaded
        issues = query.all()
        
        # Format response for MCP
        return MCPResponseFormatter.format_issues_list(issues, include_details=False)
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in MCP issue query: {e}")
        return MCPResponseFormatter.format_error_response(
            "database_error",
            "Failed to query issues from database",
            {"filters": filters}
        )
    except Exception as e:
        logger.error(f"Unexpected error in MCP issue query: {e}")
        return MCPResponseFormatter.format_error_response(
            "internal_error",
            "An unexpected error occurred while querying issues"
        )


@mcp_router.get("/issues/{issue_key}")
async def mcp_get_issue_details(
    issue_key: str,
    db: Session = Depends(get_db),
    include_comments: bool = Query(True, description="Include issue comments"),
    include_changelog: bool = Query(True, description="Include issue changelog"),
    include_children: bool = Query(False, description="Include child issues")
):
    """
    Get comprehensive details for a specific issue - optimized for MCP clients.
    
    Returns detailed issue information including comments and changelog if requested.
    """
    try:
        # Query for the issue with relationships
        query = db.query(Issue).filter(Issue.issue_key == issue_key)
        
        # Eager load relationships if requested
        if include_comments:
            from sqlalchemy.orm import joinedload
            query = query.options(joinedload(Issue.comment_records))
        
        if include_changelog:
            from sqlalchemy.orm import joinedload
            query = query.options(joinedload(Issue.changelog_records))
        
        issue = query.first()
        
        if not issue:
            return MCPResponseFormatter.format_error_response(
                "not_found",
                f"Issue with key '{issue_key}' not found"
            )
        
        # Format detailed response
        issue_data = MCPResponseFormatter.format_issue_details(
            issue, 
            include_comments=include_comments,
            include_changelog=include_changelog
        )
        
        # Add child issues if requested
        if include_children:
            child_issues = db.query(Issue).filter(Issue.parent_key == issue_key).all()
            issue_data["children"] = [
                MCPResponseFormatter.format_issue(child, include_details=False)
                for child in child_issues
            ]
            issue_data["children_count"] = len(child_issues)
        
        return issue_data
        
    except SQLAlchemyError as e:
        logger.error(f"Database error getting issue details for {issue_key}: {e}")
        return MCPResponseFormatter.format_error_response(
            "database_error",
            f"Failed to retrieve issue details for '{issue_key}'"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting issue details for {issue_key}: {e}")
        return MCPResponseFormatter.format_error_response(
            "internal_error",
            "An unexpected error occurred while retrieving issue details"
        )


@mcp_router.get("/issues/{issue_key}/descendants")
async def mcp_get_issue_descendants(
    issue_key: str,
    db: Session = Depends(get_db),
    include_comments: bool = Query(True, description="Include comments for each issue"),
    include_changelog: bool = Query(True, description="Include changelog entries for each issue")
):
    """
    Get all descendant issues recursively from a root issue - optimized for MCP clients.
    
    Returns the root issue and all its descendants with comments and changelog if requested.
    """
    try:
        from app.services.descendant_service import descendant_service
        
        result = descendant_service.get_all_descendants(
            db=db,
            root_issue_key=issue_key,
            include_comments=include_comments,
            include_changelog=include_changelog
        )
        
        if "error" in result:
            return MCPResponseFormatter.format_error_response(
                "not_found",
                result["error"]
            )
        
        # Add timestamp for MCP response
        result["timestamp"] = datetime.utcnow().isoformat()
        
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error getting descendants for {issue_key}: {e}")
        return MCPResponseFormatter.format_error_response(
            "internal_error",
            "An unexpected error occurred while retrieving descendants"
        )


@mcp_router.get("/team/{team_name}/metrics")
async def mcp_team_metrics(
    team_name: str,
    db: Session = Depends(get_db),
    date_range: Optional[str] = Query(None, description="Date range filter (YYYY-MM-DD,YYYY-MM-DD)")
):
    """
    Get team performance metrics - optimized for MCP clients.
    
    Returns team metrics including workload, completion rates, and status breakdown.
    """
    try:
        # Build base query for team
        query = db.query(Issue).filter(Issue.team == team_name)
        
        # Apply date range filter if provided
        parsed_date_range = None
        if date_range:
            try:
                start_date, end_date = date_range.split(",")
                from datetime import datetime
                start_dt = datetime.fromisoformat(start_date)
                end_dt = datetime.fromisoformat(end_date)
                
                query = query.filter(
                    Issue.created_at >= start_dt,
                    Issue.created_at <= end_dt
                )
                parsed_date_range = {"start": start_date, "end": end_date}
                
            except (ValueError, TypeError) as e:
                return MCPResponseFormatter.format_error_response(
                    "validation_error",
                    "Invalid date range format. Use YYYY-MM-DD,YYYY-MM-DD",
                    {"provided": date_range, "error": str(e)}
                )
        
        # Execute query
        issues = query.all()
        
        # Format team metrics response
        return MCPResponseFormatter.format_team_metrics(
            team_name=team_name,
            issues=issues,
            date_range=parsed_date_range
        )
        
    except SQLAlchemyError as e:
        logger.error(f"Database error getting team metrics for {team_name}: {e}")
        return MCPResponseFormatter.format_error_response(
            "database_error",
            f"Failed to retrieve metrics for team '{team_name}'"
        )
    except Exception as e:
        logger.error(f"Unexpected error getting team metrics for {team_name}: {e}")
        return MCPResponseFormatter.format_error_response(
            "internal_error",
            "An unexpected error occurred while retrieving team metrics"
        )


@mcp_router.get("/system/connectivity")
async def mcp_test_connectivity():
    """
    Test system connectivity and health - optimized for MCP clients.
    
    Returns status of database, Jira connectivity, and last harvest information.
    """
    try:
        # Test database connectivity
        db_connected = db_service.check_database_health()
        
        # Test Jira connectivity
        jira_connected = False
        try:
            # Test actual Jira connectivity using existing harvest service
            harvest_service = HarvestService()
            jira_test_result = await harvest_service.test_jira_connectivity()
            jira_connected = jira_test_result.get("jira_connected", False)
        except Exception as e:
            logger.warning(f"Jira connectivity test failed: {e}")
            jira_connected = False
        
        # Get last harvest information
        last_harvest = None
        try:
            # Use the database service to get session
            db_session = db_service.get_db_session()
            try:
                last_harvest_job = db_session.query(HarvestJob).filter(
                    HarvestJob.status == 'completed'
                ).order_by(HarvestJob.completed_at.desc()).first()
                
                if last_harvest_job and last_harvest_job.completed_at:
                    last_harvest = last_harvest_job.completed_at
            finally:
                db_session.close()
                
        except Exception as e:
            logger.warning(f"Could not retrieve last harvest info: {e}")
        
        # Format connectivity response
        return MCPResponseFormatter.format_connectivity_status(
            jira_connected=jira_connected,
            db_connected=db_connected,
            last_harvest=last_harvest
        )
        
    except Exception as e:
        logger.error(f"Unexpected error in connectivity test: {e}")
        return MCPResponseFormatter.format_error_response(
            "internal_error",
            "An unexpected error occurred while testing connectivity"
        )


@mcp_router.post("/harvest/trigger")
async def mcp_trigger_harvest(
    harvest_type: str = Query("incremental", description="Type of harvest: full, incremental, team_only"),
    dry_run: bool = Query(False, description="Perform a dry run without actually harvesting")
):
    """
    Trigger a harvest job - optimized for MCP clients.
    
    Initiates data harvesting from Jira with specified parameters.
    """
    try:
        # Validate harvest type
        valid_types = ["full", "incremental", "team_only"]
        if harvest_type not in valid_types:
            return MCPResponseFormatter.format_error_response(
                "validation_error",
                f"Invalid harvest type '{harvest_type}'",
                {"valid_types": valid_types}
            )
        
        # Initialize harvest service
        harvest_service = HarvestService()
        
        # Trigger harvest based on type
        if dry_run:
            # For dry run, just return what would be done
            return {
                "harvest_type": harvest_type,
                "dry_run": True,
                "message": f"Dry run: Would trigger {harvest_type} harvest",
                "timestamp": MCPResponseFormatter.format_connectivity_status(True, True)["timestamp"]
            }
        else:
            # Actually trigger the harvest
            # Note: Currently only full harvest is implemented
            # TODO: Add incremental and team-only harvest options when available
            records_processed, status_message = await harvest_service.perform_full_harvest()
            
            return {
                "harvest_type": harvest_type,
                "dry_run": False,
                "records_processed": records_processed,
                "status_message": status_message,
                "message": f"Successfully triggered {harvest_type} harvest",
                "timestamp": MCPResponseFormatter.format_connectivity_status(True, True)["timestamp"]
            }
        
    except Exception as e:
        logger.error(f"Error triggering harvest: {e}")
        return MCPResponseFormatter.format_error_response(
            "harvest_error",
            f"Failed to trigger {harvest_type} harvest",
            {"error": str(e)}
        ) 


@mcp_router.get("/issues/search/by-comments")
async def mcp_search_issues_by_comments(
    db: Session = Depends(get_db),
    days_ago: int = Query(10, ge=1, le=365, description="Find issues with comments within this many days"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results")
):
    """
    Search issues that have comments within a specified time period.
    Returns issues with their recent comments.
    
    Useful for finding active issues or issues that need attention.
    """
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func, and_
        from sqlalchemy.orm import joinedload
        from app.models.database import Issue, Comment, IssueType
        from collections import defaultdict
        
        # Calculate the date threshold
        threshold_date = datetime.utcnow() - timedelta(days=days_ago)
        
        # Query comments from the last X days and join with their issues
        query = db.query(Comment, Issue).join(
            Issue, Comment.issue_key == Issue.issue_key
        ).outerjoin(
            IssueType, Issue.issue_type_id == IssueType.id
        ).filter(
            Comment.created_at >= threshold_date
        ).options(
            joinedload(Issue.issue_type)
        )
        
        # Order by comment creation date (most recent first)
        query = query.order_by(Comment.created_at.desc())
        
        # Log the SQL query for debugging
        logger.info(f"SQL Query2 for search_by_comments: {query}")
        
        # Execute query
        results = query.all()
        
        # Group comments by issue
        issues_with_comments = defaultdict(lambda: {"issue": None, "comments": []})
        
        for comment, issue in results:
            issue_key = issue.issue_key
            
            # Set the issue (will be the same for all comments of this issue)
            if issues_with_comments[issue_key]["issue"] is None:
                issues_with_comments[issue_key]["issue"] = issue
            
            # Add the comment
            issues_with_comments[issue_key]["comments"].append(comment)
        
        # Convert to list and apply limit
        issues_list = list(issues_with_comments.values())[:limit]
        
        # Format response for MCP with comments included
        response_data = {
            "issues": [],
            "total_count": len(issues_list),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        for item in issues_list:
            issue = item["issue"]
            comments = item["comments"]
            
            # Format the issue
            issue_data = MCPResponseFormatter.format_issue(issue, include_details=False)
            
            # Add the recent comments
            issue_data["recent_comments"] = [
                {
                    "id": comment.id,
                    "body": comment.body,
                    "created_at": comment.created_at.isoformat(),
                    "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
                    "jira_comment_id": comment.jira_comment_id
                }
                for comment in comments
            ]
            issue_data["recent_comments_count"] = len(comments)
            
            response_data["issues"].append(issue_data)
        
        return response_data
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in MCP comment search: {e}")
        return MCPResponseFormatter.format_error_response(
            "database_error",
            "Failed to search issues by comments"
        )
    except Exception as e:
        logger.error(f"Unexpected error in MCP comment search: {e}")
        return MCPResponseFormatter.format_error_response(
            "internal_error",
            "An unexpected error occurred while searching issues by comments"
        )


@mcp_router.get("/issue-types")
async def mcp_get_issue_types():
    """
    Get all issue types with their IDs - optimized for MCP clients.
    
    Returns a list of all issue types from the hardcoded configuration,
    useful for understanding the issue type hierarchy and for filtering queries.
    """
    try:
        from app.config.issue_types import ISSUE_TYPES
        
        # Format the response using hardcoded data
        issue_types_data = []
        for issue_type in ISSUE_TYPES:
            issue_types_data.append({
                "id": issue_type.id,
                "name": issue_type.name,
                "url": issue_type.url,
                "child_type_ids": issue_type.child_type_ids,
                "is_leaf": len(issue_type.child_type_ids) == 0
            })
        
        return {
            "issue_types": issue_types_data,
            "total_count": len(issue_types_data),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in MCP issue types query: {e}")
        return MCPResponseFormatter.format_error_response(
            "internal_error",
            "An unexpected error occurred while retrieving issue types"
        ) 