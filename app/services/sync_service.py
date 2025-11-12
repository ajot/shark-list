import logging
from datetime import datetime, timedelta
from flask import current_app
from app import db
from app.models import ListMember, SyncLog, Submission
from app.services.twitter_service import TwitterService

logger = logging.getLogger(__name__)


class SyncService:
    """Service for syncing Twitter list members with the database"""

    @staticmethod
    def can_sync() -> tuple[bool, str]:
        """
        Check if a sync operation is allowed based on cooloff period.

        Returns:
            tuple: (can_sync: bool, message: str)
        """
        cooloff_minutes = current_app.config.get('SYNC_COOLOFF_MINUTES', 5)

        # Get the last sync log
        last_sync = SyncLog.query.order_by(SyncLog.sync_started_at.desc()).first()

        if not last_sync:
            return True, "No previous sync found"

        # Check if cooloff period has passed
        cooloff_delta = timedelta(minutes=cooloff_minutes)
        time_since_last_sync = datetime.utcnow() - last_sync.sync_started_at

        if time_since_last_sync < cooloff_delta:
            remaining = cooloff_delta - time_since_last_sync
            minutes_remaining = int(remaining.total_seconds() / 60)
            return False, f"Please wait {minutes_remaining} more minute(s) before syncing again"

        return True, "Sync allowed"

    @staticmethod
    def sync_list_members() -> dict:
        """
        Sync Twitter list members with the database.

        Returns:
            dict: Sync results with statistics

        Raises:
            Exception: If sync operation fails
        """
        # Check if sync is allowed
        can_sync, message = SyncService.can_sync()
        if not can_sync:
            raise Exception(message)

        # Create sync log
        sync_log = SyncLog(
            sync_started_at=datetime.utcnow(),
            status=SyncLog.STATUS_IN_PROGRESS
        )
        db.session.add(sync_log)
        db.session.commit()

        try:
            # Fetch members from Twitter API
            twitter_service = TwitterService()
            twitter_members = twitter_service.get_list_members()

            sync_log.members_fetched = len(twitter_members)
            db.session.commit()

            # Create lookup dictionaries
            twitter_user_ids = {member['id'] for member in twitter_members}
            db_members = {m.twitter_user_id: m for m in ListMember.query.all()}

            members_added = 0
            members_updated = 0
            members_removed = 0

            # Process Twitter members
            for twitter_member in twitter_members:
                user_id = twitter_member['id']
                username = twitter_member['username']
                name = twitter_member.get('name', '')

                if user_id in db_members:
                    # Update existing member
                    db_member = db_members[user_id]
                    updated = False

                    if db_member.username != username:
                        db_member.username = username
                        updated = True

                    if db_member.name != name:
                        db_member.name = name
                        updated = True

                    # Always update synced_at
                    db_member.synced_at = datetime.utcnow()

                    if updated:
                        members_updated += 1
                        logger.info(f"Updated member @{username}")
                else:
                    # Add new member
                    # Check if this user has a submission
                    submission = Submission.query.filter_by(
                        twitter_user_id=user_id
                    ).first()

                    # Determine source based on submission
                    if submission:
                        # Check if it was bulk-added (email is the placeholder)
                        if submission.email == 'bulk-added@system':
                            source = ListMember.SOURCE_BULK_ADDED
                        else:
                            source = ListMember.SOURCE_APP_SUBMITTED
                    else:
                        source = ListMember.SOURCE_PRE_EXISTING

                    new_member = ListMember(
                        twitter_user_id=user_id,
                        username=username,
                        name=name,
                        source=source,
                        submission_id=submission.id if submission else None,
                        added_at=datetime.utcnow(),
                        synced_at=datetime.utcnow()
                    )
                    db.session.add(new_member)
                    members_added += 1
                    logger.info(f"Added new member @{username} (source: {source})")

            # Remove members no longer on Twitter list
            for db_user_id, db_member in db_members.items():
                if db_user_id not in twitter_user_ids:
                    logger.info(f"Removing member @{db_member.username} (no longer on Twitter list)")
                    db.session.delete(db_member)
                    members_removed += 1

            # Update sync log
            sync_log.members_added = members_added
            sync_log.members_updated = members_updated
            sync_log.members_removed = members_removed
            sync_log.sync_completed_at = datetime.utcnow()
            sync_log.status = SyncLog.STATUS_COMPLETED

            db.session.commit()

            result = {
                'success': True,
                'members_fetched': sync_log.members_fetched,
                'members_added': members_added,
                'members_updated': members_updated,
                'members_removed': members_removed,
                'sync_id': sync_log.id
            }

            logger.info(f"Sync completed successfully: {result}")
            return result

        except Exception as e:
            # Mark sync as failed
            sync_log.status = SyncLog.STATUS_FAILED
            sync_log.error_message = str(e)
            sync_log.sync_completed_at = datetime.utcnow()
            db.session.commit()

            logger.error(f"Sync failed: {str(e)}")
            raise

    @staticmethod
    def get_sync_history(limit: int = 10) -> list:
        """
        Get recent sync history.

        Args:
            limit: Maximum number of sync logs to return

        Returns:
            list: List of sync log dictionaries
        """
        sync_logs = SyncLog.query.order_by(
            SyncLog.sync_started_at.desc()
        ).limit(limit).all()

        return [log.to_dict() for log in sync_logs]
