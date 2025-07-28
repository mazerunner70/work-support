"""
API routes for the Work Support Python Server.
"""
import logging
import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import get_db
from app.models.database import Issue, HarvestJob, ReloadTracking
from app.models.schemas import (
    HealthCheckResponse, IssueKeysResponse, ReloadStatusResponse
)
from app.services.database_service import db_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Check database connectivity
        database_status = "connected" if db_service.check_database_health() else "disconnected"

        # Get last harvest time
        last_harvest_job = db.query(HarvestJob).filter(
            HarvestJob.status == 'completed'
        ).order_by(HarvestJob.completed_at.desc()).first()

        last_harvest = last_harvest_job.completed_at if last_harvest_job else None

        # Check if reload is in progress
        active_reload = db_service.get_active_reload()
        reload_in_progress = active_reload is not None

        return HealthCheckResponse(
            status="healthy" if database_status == "connected" else "unhealthy",
            database=database_status,
            last_harvest=last_harvest,
            reload_in_progress=reload_in_progress
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(
            status="unhealthy",
            database="error",
            last_harvest=None,
            reload_in_progress=False
        )


@router.get("/api/issues/keys", response_model=IssueKeysResponse)
async def get_issue_keys(
    db: Session = Depends(get_db),
    source: Optional[str] = Query(None, description="Filter by source: 'jira' or 'github'"),
    assignee: Optional[str] = Query(None, description="Filter by assignee name"),
    label: Optional[str] = Query(None, description="Filter by label"),
    issue_type: Optional[str] = Query(None, description="Filter by issue type name"),
    parent_key: Optional[str] = Query(None, description="Filter by parent issue key")
):
    """Get list of issue keys with optional filtering."""
    try:
        query = db.query(Issue)

        # Apply filters
        if source:
            if source not in ['jira', 'github']:
                raise HTTPException(status_code=400, detail="Source must be 'jira' or 'github'")
            query = query.filter(Issue.source == source)

        if assignee:
            query = query.filter(Issue.assignee == assignee)

        if label:
            # Note: This is a simple text search. In production, you'd parse the JSON labels
            query = query.filter(Issue.labels.contains(label))

        if parent_key:
            query = query.filter(Issue.parent_key == parent_key)

        if issue_type:
            # Join with issue_type table to filter by name
            from app.models.database import IssueType
            query = query.join(IssueType).filter(IssueType.name == issue_type)

        # Get results
        issues = query.all()
        issue_keys = [issue.issue_key for issue in issues]

        # Get most recent harvest time
        latest_harvest = db.query(Issue.harvested_at).order_by(
            Issue.harvested_at.desc()
        ).first()

        harvested_at = latest_harvest[0] if latest_harvest else None

        return IssueKeysResponse(
            issue_keys=issue_keys,
            total_count=len(issue_keys),
            harvested_at=harvested_at
        )

    except SQLAlchemyError as e:
        logger.error(f"Database error in get_issue_keys: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in get_issue_keys: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/harvest/reload", response_model=ReloadStatusResponse)
async def trigger_reload(
    force: bool = Query(False, description="Force reload even if one is already running"),
    db: Session = Depends(get_db)
):
    """Trigger a full data reload."""
    try:
        # Check if reload is already running
        active_reload = db_service.get_active_reload()

        if active_reload and not force:
            raise HTTPException(
                status_code=409,
                detail=f"Reload already in progress (ID: {active_reload.id})"
            )

        # If forcing and there's an active reload, fail the old one
        if active_reload and force:
            db_service.fail_reload(
                active_reload.id,
                "Forcibly terminated by new reload request"
            )

        # Create new reload tracking record
        # TODO: In Phase 2, capture user information from authentication
        reload_record = db_service.create_reload_tracking(
            source='manual',
            triggered_by='api-user'  # In Phase 2: get from JWT/auth context
        )

        if not reload_record:
            raise HTTPException(status_code=500, detail="Failed to create reload tracking")

        # Perform actual data harvesting
        reload_start_time = time.time()
        logger.info(f"🎯 MANUAL RELOAD - Starting full reload process for ID: {reload_record.id} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
        
        try:
            from app.services.harvest_service import harvest_service
            records_processed, status_message = await harvest_service.perform_full_harvest()
            db_service.complete_reload(reload_record.id, records_processed)
            
            # Calculate total reload duration
            reload_duration = time.time() - reload_start_time
            reload_duration_str = f"{reload_duration:.2f}s"
            if reload_duration >= 60:
                minutes = int(reload_duration // 60)
                seconds = reload_duration % 60
                reload_duration_str = f"{minutes}m {seconds:.1f}s"
            
            logger.info(f"✅ MANUAL RELOAD COMPLETED - {status_message} - Total Duration: {reload_duration_str} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
            
            # Get updated reload record to return current status
            with db_service.get_db_session() as db:
                updated_record = db.query(ReloadTracking).filter(
                    ReloadTracking.id == reload_record.id
                ).first()
                
                if updated_record:
                    return ReloadStatusResponse(
                        reload_id=updated_record.id,
                        reload_started=updated_record.reload_started,
                        status=updated_record.status,
                        records_processed=updated_record.records_processed or 0,
                        source=updated_record.source or 'manual',
                        triggered_by=updated_record.triggered_by,
                        issues_deleted=updated_record.issues_deleted or 0,
                        duration_seconds=updated_record.duration_seconds
                    )
                    
        except Exception as e:
            # Calculate duration even for failed reloads
            reload_duration = time.time() - reload_start_time
            reload_duration_str = f"{reload_duration:.2f}s"
            if reload_duration >= 60:
                minutes = int(reload_duration // 60)
                seconds = reload_duration % 60
                reload_duration_str = f"{minutes}m {seconds:.1f}s"
            
            error_msg = f"Manual reload failed: {e}"
            logger.error(f"❌ MANUAL RELOAD FAILED - {error_msg} - Duration: {reload_duration_str} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
            db_service.fail_reload(reload_record.id, error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        return ReloadStatusResponse(
            reload_id=reload_record.id,
            reload_started=reload_record.reload_started,
            status="failed",
            records_processed=0,
            source=reload_record.source or 'manual',
            triggered_by=reload_record.triggered_by,
            issues_deleted=0,
            duration_seconds=None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering reload: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/harvest/reload/{reload_id}", response_model=ReloadStatusResponse)
async def get_reload_status(reload_id: int, db: Session = Depends(get_db)):
    """Get the status of a specific reload."""
    try:
        reload_record = db.query(ReloadTracking).filter(
            ReloadTracking.id == reload_id
        ).first()

        if not reload_record:
            raise HTTPException(status_code=404, detail="Reload not found")

        return ReloadStatusResponse(
            reload_id=reload_record.id,
            reload_started=reload_record.reload_started,
            status=reload_record.status,
            completed_at=reload_record.completed_at,
            records_processed=reload_record.records_processed,
            source=reload_record.source or 'manual',
            triggered_by=reload_record.triggered_by,
            issues_deleted=getattr(reload_record, 'issues_deleted', None) or 0,
            duration_seconds=reload_record.duration_seconds
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting reload status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/harvest/reload", response_model=List[ReloadStatusResponse])
async def get_reload_history(
    db: Session = Depends(get_db),
    limit: int = Query(10, description="Maximum number of reload records to return", ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: 'running', 'completed', 'failed'")
):
    """Get reload history for audit purposes."""
    try:
        query = db.query(ReloadTracking).order_by(ReloadTracking.reload_started.desc())

        # Apply status filter if provided
        if status:
            if status not in ['running', 'completed', 'failed']:
                raise HTTPException(status_code=400, detail="Status must be 'running', 'completed', or 'failed'")
            query = query.filter(ReloadTracking.status == status)

        # Apply limit
        reload_records = query.limit(limit).all()

        return [
            ReloadStatusResponse(
                reload_id=record.id,
                reload_started=record.reload_started,
                status=record.status,
                completed_at=record.completed_at,
                records_processed=record.records_processed,
                source=record.source or 'manual',
                triggered_by=record.triggered_by,
                issues_deleted=getattr(record, 'issues_deleted', None) or 0,
                duration_seconds=record.duration_seconds
            )
            for record in reload_records
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting reload history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/issues/{issue_key}")
async def get_issue_by_key(
    issue_key: str,
    db: Session = Depends(get_db)
):
    """Get a specific issue by its key."""
    try:
        # Query for the issue
        issue = db.query(Issue).filter(Issue.issue_key == issue_key).first()
        
        if not issue:
            raise HTTPException(status_code=404, detail=f"Issue with key '{issue_key}' not found")
        
        # Return issue data
        return {
            "issue_key": issue.issue_key,
            "summary": issue.summary,
            "assignee": issue.assignee,
            "status": issue.status,
            "team": issue.team,
            "source": issue.source,
            "parent_key": issue.parent_key,
            "labels": issue.labels,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "start_date": issue.start_date,
            "transition_date": issue.transition_date,
            "end_date": issue.end_date
        }
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error getting issue {issue_key}: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error getting issue {issue_key}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/issues/{issue_key}/descendants")
async def get_issue_descendants(
    issue_key: str,
    db: Session = Depends(get_db),
    include_comments: bool = Query(True, description="Include comments for each issue"),
    include_changelog: bool = Query(True, description="Include changelog entries for each issue")
):
    """Get all descendant issues recursively from a root issue."""
    try:
        from app.services.descendant_service import descendant_service
        
        result = descendant_service.get_all_descendants(
            db=db,
            root_issue_key=issue_key,
            include_comments=include_comments,
            include_changelog=include_changelog
        )
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting descendants for {issue_key}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/harvest/test", response_model=dict)
async def test_harvest_connectivity():
    """Test connectivity to external services for harvesting."""
    try:
        from app.services.harvest_service import harvest_service
        
        result = await harvest_service.test_jira_connectivity()
        
        return {
            "status": "success" if result.get("jira_connected", False) else "warning",
            "jira_connectivity": result,
            "message": "Connectivity test completed"
        }
        
    except Exception as e:
        logger.error(f"Error in connectivity test: {e}")
        raise HTTPException(status_code=500, detail=f"Connectivity test failed: {e}")


@router.get("/api/harvest/scheduler", response_model=dict)
async def get_scheduler_status():
    """Get the status of the harvest scheduler."""
    try:
        from app.services.scheduler_service import scheduler_service
        
        status = scheduler_service.get_scheduler_status()
        
        return {
            "status": "success",
            "scheduler": status,
            "message": "Scheduler status retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {e}")


@router.post("/api/harvest/trigger", response_model=dict)
async def trigger_immediate_harvest():
    """Trigger an immediate harvest job via the scheduler."""
    try:
        from app.services.scheduler_service import scheduler_service
        
        scheduler_service.trigger_immediate_harvest()
        
        return {
            "status": "success",
            "message": "Immediate harvest job scheduled successfully"
        }
        
    except Exception as e:
        logger.error(f"Error triggering immediate harvest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger immediate harvest: {e}")
