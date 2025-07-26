"""
Main data harvesting orchestration service.
"""
import logging
import json
import time
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from app.config.settings import config_manager
from app.services.jira_service import jira_service, JiraIssue, JiraServiceError
from app.services.hierarchy_service import hierarchy_service, HierarchyServiceError
from app.services.database_service import db_service
from app.models.database import Issue, HarvestJob

logger = logging.getLogger(__name__)


class HarvestServiceError(Exception):
    """Custom exception for harvest service errors."""
    pass


class HarvestService:
    """Main service for orchestrating data harvesting from Jira."""

    def __init__(self):
        self.jira_service = jira_service
        self.hierarchy_service = hierarchy_service
        self.db_service = db_service

    async def perform_full_harvest(self) -> Tuple[int, str]:
        """
        Perform a complete data harvest from Jira.
        
        Returns:
            Tuple of (records_processed, status_message)
            
        Raises:
            HarvestServiceError: If harvest fails
        """
        start_time = time.time()
        harvest_job_id = None
        
        try:
            # Create harvest job record
            harvest_job_id = self._create_harvest_job()
            logger.info(f"🚀 HARVEST STARTED - Job ID: {harvest_job_id} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")

            # Test Jira connection first
            if not await self.jira_service.test_connection():
                raise HarvestServiceError("Failed to connect to Jira API")

            # Validate hierarchy configuration
            validation_result = self.hierarchy_service.validate_hierarchy_integrity()
            if not validation_result["valid"]:
                error_msg = f"Invalid hierarchy configuration: {validation_result['issues']}"
                logger.error(error_msg)
                raise HarvestServiceError(error_msg)

            if validation_result["warnings"]:
                for warning in validation_result["warnings"]:
                    logger.warning(f"Hierarchy warning: {warning}")

            total_records = 0

            # Phase 1: Hierarchical harvest starting from Product Versions
            logger.info("📊 PHASE 1 - Hierarchical harvest starting...")
            hierarchical_records = await self._harvest_hierarchical_issues()
            total_records += hierarchical_records
            logger.info(f"✅ PHASE 1 COMPLETED - {hierarchical_records} hierarchical issues processed")

            # Phase 2: Team member specific harvest
            logger.info("👥 PHASE 2 - Team member specific harvest starting...")
            team_member_records = await self._harvest_team_member_issues()
            total_records += team_member_records
            logger.info(f"✅ PHASE 2 COMPLETED - {team_member_records} team member issues processed")

            # Complete harvest job
            self._complete_harvest_job(harvest_job_id, total_records)
            
            # Calculate total duration
            duration = time.time() - start_time
            duration_str = f"{duration:.2f}s"
            if duration >= 60:
                minutes = int(duration // 60)
                seconds = duration % 60
                duration_str = f"{minutes}m {seconds:.1f}s"
            
            status_message = f"Harvest completed successfully. Total records: {total_records}"
            logger.info(f"🎉 HARVEST COMPLETED - {status_message} - Duration: {duration_str} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
            
            return total_records, status_message

        except Exception as e:
            # Calculate duration even for failed harvests
            duration = time.time() - start_time
            duration_str = f"{duration:.2f}s"
            if duration >= 60:
                minutes = int(duration // 60)
                seconds = duration % 60
                duration_str = f"{minutes}m {seconds:.1f}s"
            
            error_msg = f"Harvest failed: {e}"
            logger.error(f"❌ HARVEST FAILED - {error_msg} - Duration: {duration_str} - {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
            
            if harvest_job_id:
                self._fail_harvest_job(harvest_job_id, error_msg)
            
            if isinstance(e, (JiraServiceError, HierarchyServiceError)):
                raise HarvestServiceError(error_msg)
            else:
                raise HarvestServiceError(f"Unexpected error: {error_msg}")

    async def _harvest_hierarchical_issues(self) -> int:
        """
        Harvest issues using layered hierarchical traversal.
        This new approach processes issues layer by layer for better efficiency.
        
        Returns:
            Number of issues processed
        """
        try:
            # Get projects and label from configuration
            projects = ["IAIPORT", "AIPRDV", "AIMP", "IACU"]  # As per design doc
            label = config_manager.settings.jira_issue_label
            
            if label == "work-support":
                # Use the correct label from design doc for hierarchical harvest
                label = "SE_product_family"
                logger.info(f"Using hierarchical label 'SE_product_family' instead of default")

            logger.info(f"Harvesting hierarchical issues from projects: {projects} using LAYERED approach (Layer 0: Product Versions only, Layer 1+: all child types, 5-iteration limit)")
            
            # Get all issues in the hierarchy using the new layered approach
            issues = await self.hierarchy_service.harvest_hierarchical_issues_layered(projects, label)
            
            # Store issues in database
            records_stored = self._store_issues_in_database(issues, "jira")
            
            logger.info(f"Layered hierarchical harvest: {len(issues)} fetched, {records_stored} stored")
            return records_stored

        except (JiraServiceError, HierarchyServiceError) as e:
            logger.error(f"Error in layered hierarchical harvest: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in layered hierarchical harvest: {e}")
            raise HarvestServiceError(f"Layered hierarchical harvest failed: {e}")

    async def _harvest_team_member_issues(self) -> int:
        """
        Harvest issues assigned to specific team members.
        
        Returns:
            Number of issues processed
        """
        try:
            team_members = config_manager.team_members
            label = config_manager.settings.jira_issue_label
            total_records = 0

            logger.info(f"Harvesting team member issues for {len(team_members)} members")

            for member_name, member in team_members.items():
                try:
                    logger.info(f"Harvesting issues for team member: {member_name} ({member.jira_id})")
                    
                    # Get issues for this team member
                    issues = await self.hierarchy_service.harvest_team_member_issues(
                        member.jira_id, label
                    )
                    
                    # Store issues in database
                    records_stored = self._store_issues_in_database(issues, "jira")
                    total_records += records_stored
                    
                    logger.info(f"Team member {member_name}: {len(issues)} fetched, {records_stored} stored")

                except Exception as e:
                    logger.error(f"Error harvesting issues for {member_name}: {e}")
                    # Continue with other team members even if one fails

            logger.info(f"Team member harvest completed: {total_records} total records")
            return total_records

        except Exception as e:
            logger.error(f"Error in team member harvest: {e}")
            raise HarvestServiceError(f"Team member harvest failed: {e}")

    def _store_issues_in_database(self, jira_issues: List[JiraIssue], source: str) -> int:
        """
        Store Jira issues in the database.
        
        Args:
            jira_issues: List of JiraIssue objects
            source: Source of the issues ('jira' or 'github')
            
        Returns:
            Number of issues actually stored/updated
        """
        if not jira_issues:
            return 0

        stored_count = 0
        
        try:
            with self.db_service.get_db_session() as db:
                for jira_issue in jira_issues:
                    try:
                        # Map Jira issue type to local issue type
                        local_issue_type_id = self.hierarchy_service.map_issue_type_id(
                            jira_issue.issue_type_id, jira_issue.issue_type_name
                        )

                        # Check if issue already exists
                        existing_issue = db.query(Issue).filter(
                            Issue.issue_key == jira_issue.key
                        ).first()

                        if existing_issue:
                            # Update existing issue
                            existing_issue.summary = jira_issue.summary
                            existing_issue.assignee = jira_issue.assignee
                            existing_issue.status = jira_issue.status
                            existing_issue.labels = json.dumps(jira_issue.labels)
                            existing_issue.issue_type_id = local_issue_type_id
                            existing_issue.parent_key = jira_issue.parent_key
                            existing_issue.team = jira_issue.team
                            existing_issue.start_date = jira_issue.start_date
                            existing_issue.transition_date = jira_issue.transition_date
                            existing_issue.end_date = jira_issue.end_date
                            existing_issue.created_at = jira_issue.created
                            existing_issue.updated_at = jira_issue.updated
                            existing_issue.harvested_at = datetime.utcnow()
                            existing_issue.comments = json.dumps([comment.model_dump() for comment in jira_issue.comments], default=str)
                            
                            logger.debug(f"Updated existing issue: {jira_issue.key}")
                        else:
                            # Create new issue
                            new_issue = Issue(
                                issue_key=jira_issue.key,
                                summary=jira_issue.summary,
                                assignee=jira_issue.assignee,
                                status=jira_issue.status,
                                labels=json.dumps(jira_issue.labels),
                                issue_type_id=local_issue_type_id,
                                parent_key=jira_issue.parent_key,
                                source=source,
                                team=jira_issue.team,
                                start_date=jira_issue.start_date,
                                transition_date=jira_issue.transition_date,
                                end_date=jira_issue.end_date,
                                created_at=jira_issue.created,
                                updated_at=jira_issue.updated,
                                harvested_at=datetime.utcnow(),
                                comments=json.dumps([comment.model_dump() for comment in jira_issue.comments], default=str)
                            )
                            db.add(new_issue)
                            
                            logger.debug(f"Created new issue: {jira_issue.key}")

                        stored_count += 1

                    except Exception as e:
                        logger.error(f"Error storing issue {jira_issue.key}: {e}")
                        continue

                # Commit all changes
                db.commit()
                logger.info(f"Successfully stored {stored_count} issues in database")

        except Exception as e:
            logger.error(f"Database error storing issues: {e}")
            raise HarvestServiceError(f"Failed to store issues in database: {e}")

        return stored_count

    def _create_harvest_job(self) -> int:
        """
        Create a new harvest job record.
        
        Returns:
            Harvest job ID
        """
        try:
            with self.db_service.get_db_session() as db:
                harvest_job = HarvestJob(
                    started_at=datetime.utcnow(),
                    status='running'
                )
                db.add(harvest_job)
                db.commit()
                db.refresh(harvest_job)
                
                logger.info(f"Created harvest job: {harvest_job.id}")
                return harvest_job.id

        except Exception as e:
            logger.error(f"Error creating harvest job: {e}")
            raise HarvestServiceError(f"Failed to create harvest job: {e}")

    def _complete_harvest_job(self, job_id: int, records_processed: int):
        """Complete a harvest job with success status."""
        try:
            with self.db_service.get_db_session() as db:
                harvest_job = db.query(HarvestJob).filter(HarvestJob.id == job_id).first()
                if harvest_job:
                    harvest_job.completed_at = datetime.utcnow()
                    harvest_job.status = 'completed'
                    harvest_job.records_processed = records_processed
                    db.commit()
                    
                    logger.info(f"Completed harvest job {job_id}: {records_processed} records")

        except Exception as e:
            logger.error(f"Error completing harvest job {job_id}: {e}")

    def _fail_harvest_job(self, job_id: int, error_message: str):
        """Mark a harvest job as failed."""
        try:
            with self.db_service.get_db_session() as db:
                harvest_job = db.query(HarvestJob).filter(HarvestJob.id == job_id).first()
                if harvest_job:
                    harvest_job.completed_at = datetime.utcnow()
                    harvest_job.status = 'failed'
                    harvest_job.error_message = error_message
                    db.commit()
                    
                    logger.info(f"Failed harvest job {job_id}: {error_message}")

        except Exception as e:
            logger.error(f"Error failing harvest job {job_id}: {e}")

    async def test_jira_connectivity(self) -> Dict[str, any]:
        """
        Test connectivity to Jira and return status information.
        
        Returns:
            Dictionary with connectivity test results
        """
        result = {
            "jira_connected": False,
            "jira_user": None,
            "hierarchy_valid": False,
            "team_members_count": 0,
            "issue_types_count": 0
        }

        try:
            # Test Jira connection
            result["jira_connected"] = await self.jira_service.test_connection()
            
            # Get issue types from Jira
            if result["jira_connected"]:
                jira_issue_types = await self.jira_service.get_issue_types()
                result["issue_types_count"] = len(jira_issue_types)

            # Validate hierarchy
            validation = self.hierarchy_service.validate_hierarchy_integrity()
            result["hierarchy_valid"] = validation["valid"]
            
            # Count team members
            result["team_members_count"] = len(config_manager.team_members)
            
            logger.info(f"Connectivity test completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Error in connectivity test: {e}")
            result["error"] = str(e)
            return result


# Global instance
harvest_service = HarvestService() 