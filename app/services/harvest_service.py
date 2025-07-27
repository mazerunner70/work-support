"""
Main data harvesting orchestration service.
"""
import logging
import json
import time
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime

from app.config.settings import config_manager
from app.services.jira.service import jira_service
from app.models.jira import JiraIssue, JiraServiceError
from app.services.hierarchy_service import hierarchy_service, HierarchyServiceError
from app.services.database_service import db_service
from app.models.database import Issue, HarvestJob, Comment, Changelog, ChangesLog

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

            # Phase 2: Team member specific harvest - DISABLED
            # logger.info("👥 PHASE 2 - Team member specific harvest starting...")
            # team_member_records = await self._harvest_team_member_issues()
            # total_records += team_member_records
            # logger.info(f"✅ PHASE 2 COMPLETED - {team_member_records} team member issues processed")
            logger.info("👥 PHASE 2 - Team member specific harvest SKIPPED (disabled)")
            team_member_records = 0

            # Phase 3: Bulk changelog harvest for non-blacklisted issues
            logger.info("📝 PHASE 3 - Bulk changelog harvest starting...")
            changelog_records = await self._harvest_changelogs_bulk()
            logger.info(f"✅ PHASE 3 COMPLETED - {changelog_records} changelog entries processed")

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
                            # Compare and log field changes before updating
                            self._compare_and_log_field_changes(db, existing_issue, jira_issue, jira_issue.key)
                            
                            # Update existing issue
                            existing_issue.summary = jira_issue.summary
                            existing_issue.issue_id = jira_issue.issue_id
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
                            # Comments are now handled separately
                            
                            # Save comments to separate table
                            self._save_comments_to_table(db, jira_issue.key, jira_issue.comments)
                            
                            logger.debug(f"Updated existing issue: {jira_issue.key}")
                        else:
                            # Create new issue
                            new_issue = Issue(
                                issue_key=jira_issue.key,
                                issue_id=jira_issue.issue_id,
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
                                harvested_at=datetime.utcnow()
                                # Comments are now handled separately
                            )
                            db.add(new_issue)
                            
                            # Log creation of new issue
                            self._log_change(db, jira_issue.key, 'issue_created', 'New issue created', 'field_update')
                            
                            # Save comments to separate table
                            self._save_comments_to_table(db, jira_issue.key, jira_issue.comments)
                            
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
            
            # Get issue types from static configuration
            from app.config.issue_types import ISSUE_TYPES
            result["issue_types_count"] = len(ISSUE_TYPES)

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

    def _save_comments_to_table(self, db, issue_key: str, jira_comments: List) -> None:
        """Save comments to the separate comments table using UPDATE strategy."""
        try:
            # Get existing comments for this issue
            existing_comments = db.query(Comment).filter(Comment.issue_key == issue_key).all()
            existing_by_jira_id = {comment.jira_comment_id: comment for comment in existing_comments if comment.jira_comment_id}
            
            new_count = 0
            updated_count = 0
            
            for comment in jira_comments:
                if not comment.body:  # Skip comments without content
                    continue
                    
                jira_comment_id = getattr(comment, 'id', None)
                
                if jira_comment_id and jira_comment_id in existing_by_jira_id:
                    # Update existing comment if it has changed
                    existing_comment = existing_by_jira_id[jira_comment_id]
                    
                    # Check if comment needs updating
                    needs_update = (
                        existing_comment.body != comment.body or
                        existing_comment.updated_at != comment.updated
                    )
                    
                    if needs_update:
                        existing_comment.body = comment.body
                        existing_comment.updated_at = comment.updated
                        updated_count += 1
                        
                else:
                    # Create new comment
                    new_comment = Comment(
                        issue_key=issue_key,
                        body=comment.body,
                        created_at=comment.created,
                        updated_at=comment.updated,
                        jira_comment_id=jira_comment_id
                    )
                    db.add(new_comment)
                    new_count += 1
            
            # Log comment changes with more accurate information
            if new_count > 0 or updated_count > 0:
                change_details = []
                if new_count > 0:
                    change_details.append(f'{new_count} new')
                if updated_count > 0:
                    change_details.append(f'{updated_count} updated')
                
                change_message = f"{', '.join(change_details)} comments processed"
                change_type = 'comment_added' if new_count > 0 else 'comment_updated'
                self._log_change(db, issue_key, 'comments', change_message, change_type)
                    
        except Exception as e:
            logger.error(f"Error saving comments for issue {issue_key}: {e}")

    def _log_change(self, db, issue_key: str, field_name: str, updated_value: str, change_type: str) -> None:
        """Log a change to the changes_log table."""
        try:
            change_entry = ChangesLog(
                issue_key=issue_key,
                field_name=field_name,
                updated_value=updated_value,
                change_type=change_type
            )
            db.add(change_entry)
        except Exception as e:
            logger.error(f"Error logging change for issue {issue_key}, field {field_name}: {e}")

    def _compare_and_log_field_changes(self, db, existing_issue: Issue, jira_issue, issue_key: str) -> None:
        """Compare existing issue with new data and log any field changes."""
        try:
            # Define fields to check for changes
            field_mappings = {
                'summary': (existing_issue.summary, jira_issue.summary),
                'assignee': (existing_issue.assignee, jira_issue.assignee),
                'status': (existing_issue.status, jira_issue.status),
                'labels': (existing_issue.labels, json.dumps(jira_issue.labels)),
                'team': (existing_issue.team, jira_issue.team),
                'start_date': (str(existing_issue.start_date) if existing_issue.start_date else None, 
                              str(jira_issue.start_date) if jira_issue.start_date else None),
                'transition_date': (str(existing_issue.transition_date) if existing_issue.transition_date else None, 
                                   str(jira_issue.transition_date) if jira_issue.transition_date else None),
                'end_date': (str(existing_issue.end_date) if existing_issue.end_date else None, 
                            str(jira_issue.end_date) if jira_issue.end_date else None)
            }
            
            for field_name, (old_value, new_value) in field_mappings.items():
                if old_value != new_value:
                    self._log_change(db, issue_key, field_name, str(new_value) if new_value else '', 'field_update')
                    
        except Exception as e:
            logger.error(f"Error comparing field changes for issue {issue_key}: {e}")

    async def _harvest_changelogs_bulk(self) -> int:
        """
        Bulk harvest changelogs for all non-blacklisted issues.
        
        Returns:
            Number of changelog entries processed
        """
        try:
            # Get all non-blacklisted issues with issue_id
            with self.db_service.get_db_session() as db:
                issues = db.query(Issue).filter(
                    Issue.blacklist_reason.is_(None),  # Not blacklisted
                    Issue.issue_id.isnot(None),  # Has Jira issue ID
                    Issue.issue_id != ""  # Issue ID is not empty
                ).all()
                
                issue_ids = [issue.issue_id for issue in issues]
                
            if not issue_ids:
                logger.info("No non-blacklisted issues found for changelog harvest")
                return 0
                
            logger.info(f"Fetching changelogs for {len(issue_ids)} non-blacklisted issues")
            
            # Bulk fetch changelogs from Jira
            changelog_data = await self.jira_service.bulk_fetch_changelogs(issue_ids)
            
            if not changelog_data:
                logger.info("No changelog data returned from Jira")
                return 0
            
            # Process and store changelogs
            return self._store_changelogs_in_database(changelog_data)
            
        except Exception as e:
            logger.error(f"Error in bulk changelog harvest: {e}")
            # Don't fail the entire harvest for changelog issues
            return 0

    def _store_changelogs_in_database(self, changelog_data: List[Dict[str, Any]]) -> int:
        """
        Store changelog data in the database using UPDATE strategy.
        
        Args:
            changelog_data: List of changelog data from Jira API
            
        Returns:
            Number of changelog entries stored
        """
        if not changelog_data:
            return 0
            
        new_count = 0
        updated_count = 0
        
        try:
            with self.db_service.get_db_session() as db:
                for changelog_item in changelog_data:
                    try:
                        issue_id = changelog_item.get("issueId")
                        if not issue_id:
                            continue
                            
                        # Get existing changelogs for this issue
                        existing_changelogs = db.query(Changelog).filter(Changelog.issue_id == issue_id).all()
                        existing_by_key = {}
                        for changelog in existing_changelogs:
                            # Use composite key: jira_changelog_id + field_name
                            key = f"{changelog.jira_changelog_id}:{changelog.field_name}"
                            existing_by_key[key] = changelog
                        
                        issue_new_count = 0
                        issue_updated_count = 0
                        
                        # Process changelog histories
                        histories = changelog_item.get("histories", [])
                        for history in histories:
                            changelog_id = history.get("id")
                            created = history.get("created")
                            
                            # Parse created date
                            created_dt = None
                            if created:
                                try:
                                    # Remove timezone info for SQLite compatibility
                                    created_str = created.split('+')[0].split('.')[0]
                                    created_dt = datetime.fromisoformat(created_str)
                                except Exception:
                                    continue
                            
                            # Process each field change in this history
                            items = history.get("items", [])
                            for item in items:
                                field_name = item.get("field")
                                if not field_name or not created_dt:
                                    continue
                                
                                # Create composite key for matching
                                composite_key = f"{changelog_id}:{field_name}"
                                
                                if composite_key in existing_by_key:
                                    # Update existing changelog if it has changed
                                    existing_changelog = existing_by_key[composite_key]
                                    
                                    # Check if changelog needs updating
                                    needs_update = (
                                        existing_changelog.from_value != item.get("fromString") or
                                        existing_changelog.to_value != item.get("toString") or
                                        existing_changelog.from_display != item.get("from") or
                                        existing_changelog.to_display != item.get("to") or
                                        existing_changelog.created_at != created_dt
                                    )
                                    
                                    if needs_update:
                                        existing_changelog.from_value = item.get("fromString")
                                        existing_changelog.to_value = item.get("toString")
                                        existing_changelog.from_display = item.get("from")
                                        existing_changelog.to_display = item.get("to")
                                        existing_changelog.created_at = created_dt
                                        existing_changelog.harvested_at = datetime.utcnow()
                                        updated_count += 1
                                        issue_updated_count += 1
                                        
                                else:
                                    # Create new changelog entry
                                    new_changelog = Changelog(
                                        issue_id=issue_id,
                                        jira_changelog_id=changelog_id,
                                        field_name=field_name,
                                        from_value=item.get("fromString"),
                                        to_value=item.get("toString"),
                                        from_display=item.get("from"),
                                        to_display=item.get("to"),
                                        created_at=created_dt
                                    )
                                    db.add(new_changelog)
                                    new_count += 1
                                    issue_new_count += 1
                        
                        # Log changelog processing for this issue with more accurate information
                        if issue_new_count > 0 or issue_updated_count > 0:
                            change_details = []
                            if issue_new_count > 0:
                                change_details.append(f'{issue_new_count} new')
                            if issue_updated_count > 0:
                                change_details.append(f'{issue_updated_count} updated')
                            
                            change_message = f"{', '.join(change_details)} changelog entries processed"
                            change_type = 'changelog_added' if issue_new_count > 0 else 'changelog_updated'
                            self._log_change(db, issue_id, 'changelogs', change_message, change_type)
                        
                        db.commit()
                        
                    except Exception as e:
                        logger.error(f"Error storing changelog for issue {issue_id}: {e}")
                        db.rollback()
                        continue
                        
        except Exception as e:
            logger.error(f"Error storing changelogs in database: {e}")
            
        total_stored = new_count + updated_count
        logger.info(f"Successfully processed {total_stored} changelog entries ({new_count} new, {updated_count} updated)")
        return total_stored


# Global instance
harvest_service = HarvestService() 