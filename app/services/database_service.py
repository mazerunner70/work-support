"""
Database service for managing database connections and startup recovery.
"""
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from app.config.settings import config_manager
from app.models.database import ReloadTracking, Issue

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service for managing database connections and operations."""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database connection and session factory."""
        database_url = f"sqlite:///{config_manager.settings.database_path}"

        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},  # For SQLite
            echo=config_manager.settings.server_debug
        )

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

        logger.info(f"Database initialized: {database_url}")

    def get_db_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()

    def check_database_health(self) -> bool:
        """Check if the database is accessible."""
        try:
            with self.get_db_session() as db:
                # Simple connectivity test
                db.execute(text("SELECT 1"))
                return True
        except SQLAlchemyError as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def perform_startup_recovery(self) -> tuple[bool, bool]:
        """
        Perform startup recovery for interrupted reloads and check if a new reload is needed.
        Returns tuple: (recovery_performed, reload_needed)
        """
        logger.info("Checking for interrupted reloads...")

        recovery_performed = False
        reload_needed = False

        try:
            with self.get_db_session() as db:
                # Find any reload tracking records with status 'running' (truly interrupted)
                interrupted_reloads = db.query(ReloadTracking).filter(
                    ReloadTracking.status == 'running'
                ).all()

                if interrupted_reloads:
                    logger.warning(f"🚨 STARTUP RECOVERY - Found {len(interrupted_reloads)} interrupted reload(s)")
                    for reload_record in interrupted_reloads:
                        duration_at_interruption = datetime.utcnow() - reload_record.reload_started
                        logger.warning(
                            f"🔧 RECOVERING RELOAD - ID: {reload_record.id} | "
                            f"Started: {reload_record.reload_started.strftime('%Y-%m-%d %H:%M:%S UTC')} | "
                            f"Runtime before interruption: {duration_at_interruption} | "
                            f"Source: {getattr(reload_record, 'source', 'unknown')} | "
                            f"Triggered by: {getattr(reload_record, 'triggered_by', 'unknown')}"
                        )

                        # Perform recovery cleanup
                        self._cleanup_interrupted_reload(db, reload_record)

                    db.commit()
                    logger.info(f"✅ RECOVERY COMPLETED - {len(interrupted_reloads)} interrupted reload(s) processed")
                    recovery_performed = True
                else:
                    logger.info("✅ STARTUP CHECK - No interrupted reloads found")

                # Check if a new reload is needed
                reload_needed = self._check_reload_needed(db)

                return recovery_performed, reload_needed

        except SQLAlchemyError as e:
            logger.error(f"Error during startup recovery: {e}")
            return False, False

    def _check_reload_needed(self, db: Session) -> bool:
        """Check if a reload is needed based on the reload interval."""
        from app.config.settings import config_manager
        from datetime import timedelta

        try:
            # Get the most recent completed or failed reload
            most_recent_reload = db.query(ReloadTracking).filter(
                ReloadTracking.status.in_(['completed', 'failed'])
            ).order_by(ReloadTracking.reload_started.desc()).first()

            if not most_recent_reload:
                logger.info("No previous reload records found - reload needed")
                return True

            # Calculate time since last reload
            reload_interval_hours = config_manager.settings.harvest_interval_hours
            reload_interval = timedelta(hours=reload_interval_hours)
            time_since_last_reload = datetime.utcnow() - most_recent_reload.reload_started

            if time_since_last_reload >= reload_interval:
                logger.info(
                    f"⏰ RELOAD NEEDED - Last reload: {time_since_last_reload} ago | "
                    f"Interval: {reload_interval} | "
                    f"Last reload ID: {most_recent_reload.id} | "
                    f"Last reload source: {getattr(most_recent_reload, 'source', 'unknown')}"
                )
                return True
            else:
                next_reload_in = reload_interval - time_since_last_reload
                logger.info(
                    f"⏱️  RELOAD SCHEDULE - Next reload in: {next_reload_in} | "
                    f"Last reload: {time_since_last_reload} ago | "
                    f"Last reload ID: {most_recent_reload.id} | "
                    f"Interval: {reload_interval}"
                )
                return False

        except Exception as e:
            logger.error(f"Error checking if reload is needed: {e}")
            return False

    def _check_reload_needed_with_session(self) -> bool:
        """
        Check if a reload is needed using a new database session.
        
        Returns:
            True if a reload is needed
        """
        try:
            with self.get_db_session() as db:
                return self._check_reload_needed(db)
        except Exception as e:
            logger.error(f"Error in reload check with session: {e}")
            return False

    def _cleanup_interrupted_reload(self, db: Session, reload_record: ReloadTracking):
        """Clean up data from an interrupted reload."""
        try:
            # Delete all issues harvested during the interrupted reload
            # (harvested_at >= reload_started)
            deleted_count = db.query(Issue).filter(
                Issue.harvested_at >= reload_record.reload_started
            ).delete(synchronize_session=False)

            logger.info(
                f"🗑️  RECOVERY CLEANUP - Deleted {deleted_count} partial issues "
                f"from interrupted reload {reload_record.id}")

            # Mark the reload as failed instead of deleting (for audit trail)
            completion_time = datetime.utcnow()
            duration = completion_time - reload_record.reload_started
            duration_seconds = int(duration.total_seconds())

            reload_record.status = 'failed'
            reload_record.completed_at = completion_time
            reload_record.error_message = "Interrupted by server shutdown - recovered on startup"
            reload_record.duration_seconds = duration_seconds
            reload_record.issues_deleted = 0  # We deleted partial data, not old data

            logger.info(
                f"❌ RELOAD MARKED FAILED - ID: {reload_record.id} | "
                f"Duration: {duration_seconds}s ({duration}) | "
                f"Reason: Server shutdown interruption"
            )

        except SQLAlchemyError as e:
            logger.error(f"Error cleaning up interrupted reload {reload_record.id}: {e}")
            raise

    def get_active_reload(self) -> Optional[ReloadTracking]:
        """Check if there's currently an active reload in progress."""
        try:
            with self.get_db_session() as db:
                return db.query(ReloadTracking).filter(
                    ReloadTracking.status == 'running'
                ).first()
        except SQLAlchemyError as e:
            logger.error(f"Error checking for active reload: {e}")
            return None

    def create_reload_tracking(self, source: str = 'manual', triggered_by: str = 'system') -> Optional[ReloadTracking]:
        """Create a new reload tracking record."""
        try:
            with self.get_db_session() as db:
                start_time = datetime.utcnow()
                reload_record = ReloadTracking(
                    reload_started=start_time,
                    status='running',
                    source=source,
                    triggered_by=triggered_by
                )
                db.add(reload_record)
                db.commit()
                db.refresh(reload_record)

                logger.info(
                    f"📊 RELOAD INITIATED - ID: {reload_record.id} | "
                    f"Source: {source} | Triggered by: {triggered_by} | "
                    f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                return reload_record

        except SQLAlchemyError as e:
            logger.error(f"❌ Error creating reload tracking record: {e}")
            return None

    def complete_reload(self, reload_id: int, records_processed: int = 0) -> bool:
        """Mark a reload as completed and perform cleanup."""
        try:
            with self.get_db_session() as db:
                reload_record = db.query(ReloadTracking).filter(
                    ReloadTracking.id == reload_id
                ).first()

                if not reload_record:
                    logger.error(f"❌ Reload tracking record not found: {reload_id}")
                    return False

                completion_time = datetime.utcnow()
                duration = completion_time - reload_record.reload_started
                duration_seconds = int(duration.total_seconds())

                logger.info(f"🔄 CLEANUP PHASE - Removing old issues for reload {reload_id}...")

                # Delete all issues where harvested_at < reload_started
                deleted_count = db.query(Issue).filter(
                    Issue.harvested_at < reload_record.reload_started
                ).delete(synchronize_session=False)

                logger.info(f"🗑️  Cleanup completed - Deleted {deleted_count} old issues")

                # Mark reload as completed (keep record for audit trail)
                reload_record.status = 'completed'
                reload_record.completed_at = completion_time
                reload_record.records_processed = records_processed
                reload_record.issues_deleted = deleted_count
                reload_record.duration_seconds = duration_seconds

                db.commit()

                logger.info(
                    f"✅ RELOAD COMPLETED - ID: {reload_id} | "
                    f"Duration: {duration_seconds}s ({duration}) | "
                    f"Records processed: {records_processed} | "
                    f"Old issues deleted: {deleted_count} | "
                    f"Source: {reload_record.source} | "
                    f"Triggered by: {reload_record.triggered_by}"
                )
                return True

        except SQLAlchemyError as e:
            logger.error(f"❌ Error completing reload {reload_id}: {e}")
            return False

    def fail_reload(self, reload_id: int, error_message: str) -> bool:
        """Mark a reload as failed."""
        try:
            with self.get_db_session() as db:
                reload_record = db.query(ReloadTracking).filter(
                    ReloadTracking.id == reload_id
                ).first()

                if not reload_record:
                    logger.error(f"❌ Reload tracking record not found: {reload_id}")
                    return False

                completion_time = datetime.utcnow()
                duration = completion_time - reload_record.reload_started
                duration_seconds = int(duration.total_seconds())

                reload_record.status = 'failed'
                reload_record.completed_at = completion_time
                reload_record.error_message = error_message
                reload_record.duration_seconds = duration_seconds

                db.commit()

                logger.error(
                    f"❌ RELOAD FAILED - ID: {reload_id} | "
                    f"Duration: {duration_seconds}s ({duration}) | "
                    f"Source: {reload_record.source} | "
                    f"Triggered by: {reload_record.triggered_by} | "
                    f"Error: {error_message}"
                )
                return True

        except SQLAlchemyError as e:
            logger.error(f"❌ Error failing reload {reload_id}: {e}")
            return False


# Global database service instance
db_service = DatabaseService()
