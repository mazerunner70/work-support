"""
Scheduler service for automated data harvesting.
"""
import logging
import asyncio
import time
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from app.config.settings import config_manager
from app.services.harvest_service import harvest_service, HarvestServiceError
from app.services.database_service import db_service

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for managing scheduled data harvesting."""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.harvest_service = harvest_service
        self.db_service = db_service

    def start_scheduler(self):
        """Start the APScheduler for automated harvesting."""
        try:
            if self.scheduler is not None:
                logger.warning("Scheduler is already running")
                return

            # Configure scheduler
            jobstores = {
                'default': MemoryJobStore()
            }
            executors = {
                'default': AsyncIOExecutor()
            }
            job_defaults = {
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 300  # 5 minutes
            }

            self.scheduler = AsyncIOScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone='UTC'
            )

            # Add scheduled harvest job
            harvest_interval_hours = config_manager.settings.harvest_interval_hours
            logger.info(f"Scheduling automated harvest every {harvest_interval_hours} hours")

            self.scheduler.add_job(
                func=self._scheduled_harvest_wrapper,
                trigger=IntervalTrigger(hours=harvest_interval_hours),
                id='scheduled_harvest',
                name='Scheduled Data Harvest',
                replace_existing=True
            )

            # Add a startup job to run immediately if no recent harvest exists
            self.scheduler.add_job(
                func=self._startup_harvest_check,
                trigger='date',
                id='startup_harvest_check',
                name='Startup Harvest Check',
                replace_existing=True
            )

            # Start the scheduler
            self.scheduler.start()
            logger.info("✅ Scheduler started successfully")

        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")
            raise

    def stop_scheduler(self):
        """Stop the scheduler."""
        try:
            if self.scheduler is not None:
                self.scheduler.shutdown(wait=True)
                self.scheduler = None
                logger.info("✅ Scheduler stopped successfully")
            else:
                logger.warning("Scheduler is not running")

        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")

    async def _scheduled_harvest_wrapper(self):
        """
        Wrapper for scheduled harvest that handles errors and reload tracking.
        """
        try:
            logger.info("🕐 SCHEDULED HARVEST - Starting automated harvest")
            
            # Check if there's already an active reload
            active_reload = self.db_service.get_active_reload()
            if active_reload:
                logger.warning(f"Scheduled harvest skipped - reload {active_reload.id} already in progress")
                return

            # Create reload tracking for scheduled harvest
            reload_record = self.db_service.create_reload_tracking(
                source='scheduled',
                triggered_by='system-scheduler'
            )

            if not reload_record:
                logger.error("Failed to create reload tracking for scheduled harvest")
                return

            scheduled_start_time = time.time()
            logger.info(f"📅 SCHEDULED HARVEST - Starting for ID: {reload_record.id} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
            
            try:
                # Perform the harvest
                records_processed, status_message = await self.harvest_service.perform_full_harvest()
                self.db_service.complete_reload(reload_record.id, records_processed)
                
                # Calculate scheduled harvest duration
                scheduled_duration = time.time() - scheduled_start_time
                scheduled_duration_str = f"{scheduled_duration:.2f}s"
                if scheduled_duration >= 60:
                    minutes = int(scheduled_duration // 60)
                    seconds = scheduled_duration % 60
                    scheduled_duration_str = f"{minutes}m {seconds:.1f}s"
                
                logger.info(f"✅ SCHEDULED HARVEST COMPLETED - {status_message} - Duration: {scheduled_duration_str} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

            except HarvestServiceError as e:
                # Calculate duration even for failed scheduled harvests
                scheduled_duration = time.time() - scheduled_start_time
                scheduled_duration_str = f"{scheduled_duration:.2f}s"
                if scheduled_duration >= 60:
                    minutes = int(scheduled_duration // 60)
                    seconds = scheduled_duration % 60
                    scheduled_duration_str = f"{minutes}m {seconds:.1f}s"
                
                error_msg = f"Scheduled harvest failed: {e}"
                logger.error(f"❌ SCHEDULED HARVEST FAILED - {error_msg} - Duration: {scheduled_duration_str} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
                self.db_service.fail_reload(reload_record.id, error_msg)

            except Exception as e:
                # Calculate duration even for unexpected errors
                scheduled_duration = time.time() - scheduled_start_time
                scheduled_duration_str = f"{scheduled_duration:.2f}s"
                if scheduled_duration >= 60:
                    minutes = int(scheduled_duration // 60)
                    seconds = scheduled_duration % 60
                    scheduled_duration_str = f"{minutes}m {seconds:.1f}s"
                
                error_msg = f"Unexpected error in scheduled harvest: {e}"
                logger.error(f"❌ SCHEDULED HARVEST ERROR - {error_msg} - Duration: {scheduled_duration_str} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
                self.db_service.fail_reload(reload_record.id, error_msg)

        except Exception as e:
            logger.error(f"Critical error in scheduled harvest wrapper: {e}")

    async def _startup_harvest_check(self):
        """
        Check if a harvest is needed on startup (if no recent harvest exists).
        """
        try:
            logger.info("🔍 STARTUP HARVEST CHECK - Checking if harvest is needed")
            
            # This logic is similar to what's in database_service.py
            # but we're doing it here to avoid circular dependencies
            harvest_interval_hours = config_manager.settings.harvest_interval_hours
            
            # Check if we need a harvest based on the reload interval logic
            reload_needed = self.db_service._check_reload_needed_with_session()
            
            if reload_needed:
                logger.info("🚀 STARTUP HARVEST - Triggering immediate harvest due to no recent data")
                
                # Use the same wrapper to ensure proper error handling
                await self._scheduled_harvest_wrapper()
            else:
                logger.info("✅ STARTUP HARVEST CHECK - Recent harvest found, no action needed")

        except Exception as e:
            logger.error(f"Error in startup harvest check: {e}")

    def get_next_harvest_time(self) -> Optional[str]:
        """
        Get the next scheduled harvest time.
        
        Returns:
            ISO formatted timestamp of next harvest, or None if scheduler not running
        """
        try:
            if self.scheduler is None:
                return None

            job = self.scheduler.get_job('scheduled_harvest')
            if job and job.next_run_time:
                return job.next_run_time.isoformat()
            
            return None

        except Exception as e:
            logger.error(f"Error getting next harvest time: {e}")
            return None

    def get_scheduler_status(self) -> dict:
        """
        Get scheduler status information.
        
        Returns:
            Dictionary with scheduler status
        """
        try:
            if self.scheduler is None:
                return {
                    "running": False,
                    "jobs": 0,
                    "next_harvest": None
                }

            jobs = self.scheduler.get_jobs()
            next_harvest = self.get_next_harvest_time()

            return {
                "running": self.scheduler.running,
                "jobs": len(jobs),
                "next_harvest": next_harvest,
                "harvest_interval_hours": config_manager.settings.harvest_interval_hours
            }

        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {
                "running": False,
                "jobs": 0,
                "next_harvest": None,
                "error": str(e)
            }

    def trigger_immediate_harvest(self):
        """
        Trigger an immediate harvest job (in addition to the scheduled ones).
        """
        try:
            if self.scheduler is None:
                raise Exception("Scheduler is not running")

            self.scheduler.add_job(
                func=self._scheduled_harvest_wrapper,
                trigger='date',
                id='immediate_harvest',
                name='Immediate Harvest',
                replace_existing=True
            )
            
            logger.info("Immediate harvest job scheduled")

        except Exception as e:
            logger.error(f"Error scheduling immediate harvest: {e}")
            raise


# Global instance
scheduler_service = SchedulerService() 