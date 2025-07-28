"""
Issue type synchronization service.

Ensures the database issue_types table stays in sync with the authoritative
configuration in app/config/issue_types.py
"""
import logging
from typing import Tuple
from sqlalchemy.orm import Session
from app.config.issue_types import ISSUE_TYPES
from app.models.database import IssueType


logger = logging.getLogger(__name__)


class IssueTypeSyncService:
    """Service for synchronizing issue types between config and database."""
    
    @staticmethod
    def sync_issue_types(db: Session) -> Tuple[int, int]:
        """
        Sync issue types from config to database.
        
        Args:
            db: Database session
            
        Returns:
            Tuple of (added_count, updated_count)
        """
        logger.info("Starting issue types sync...")
        
        # Get current issue types from database
        existing_types = {it.id: it for it in db.query(IssueType).all()}
        logger.debug(f"Found {len(existing_types)} existing issue types in database")
        
        # Track changes
        added_count = 0
        updated_count = 0
        
        # Sync each configured issue type
        for config_type in ISSUE_TYPES:
            if config_type.id in existing_types:
                # Update existing if needed
                db_type = existing_types[config_type.id]
                if (db_type.name != config_type.name or 
                    db_type.url != config_type.url):
                    logger.debug(f"Updating issue type {config_type.id}: {config_type.name}")
                    db_type.name = config_type.name
                    db_type.url = config_type.url
                    updated_count += 1
            else:
                # Add new
                logger.debug(f"Adding issue type {config_type.id}: {config_type.name}")
                new_type = IssueType(
                    id=config_type.id,
                    name=config_type.name,
                    url=config_type.url
                )
                db.add(new_type)
                added_count += 1
        
        # Commit changes
        db.commit()
        
        if added_count > 0 or updated_count > 0:
            logger.info(f"Issue types sync complete: added {added_count}, updated {updated_count}")
        else:
            logger.debug("Issue types already in sync")
        
        return added_count, updated_count
    
    @staticmethod
    def sync_on_startup(db: Session) -> None:
        """
        Sync issue types at application startup.
        
        This ensures the database is always up to date with the configuration.
        """
        try:
            added, updated = IssueTypeSyncService.sync_issue_types(db)
            if added > 0 or updated > 0:
                logger.info(f"Startup sync: {added} issue types added, {updated} updated")
        except Exception as e:
            logger.error(f"Failed to sync issue types on startup: {e}")
            # Don't fail startup for this - just log the error 