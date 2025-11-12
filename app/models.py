from datetime import datetime
from app import db


class Submission(db.Model):
    """Model for Twitter list submission requests"""
    __tablename__ = 'submissions'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    twitter_handle = db.Column(db.String(50), nullable=False, unique=True, index=True)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    twitter_user_id = db.Column(db.String(50), nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    processed_by = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Status constants
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    def __init__(self, email, twitter_handle, **kwargs):
        """Initialize submission with normalized twitter handle"""
        super(Submission, self).__init__(**kwargs)
        self.email = email.lower().strip()
        self.twitter_handle = self.normalize_handle(twitter_handle)

    @staticmethod
    def normalize_handle(handle):
        """Remove @ symbol and convert to lowercase"""
        return handle.lstrip('@').lower().strip()

    def approve(self, twitter_user_id):
        """Mark submission as approved"""
        self.status = self.STATUS_APPROVED
        self.twitter_user_id = twitter_user_id
        self.processed_at = datetime.utcnow()

    def reject(self, notes=None):
        """Mark submission as rejected"""
        self.status = self.STATUS_REJECTED
        self.processed_at = datetime.utcnow()
        if notes:
            self.notes = notes

    def to_dict(self):
        """Convert submission to dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'twitter_handle': self.twitter_handle,
            'status': self.status,
            'twitter_user_id': self.twitter_user_id,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'processed_by': self.processed_by,
            'notes': self.notes,
        }

    def __repr__(self):
        return f'<Submission {self.twitter_handle} ({self.status})>'


class ListMember(db.Model):
    """Model for Twitter list members (source of truth for who's on the list)"""
    __tablename__ = 'list_members'

    id = db.Column(db.Integer, primary_key=True)
    twitter_user_id = db.Column(db.String(50), nullable=False, unique=True, index=True)
    username = db.Column(db.String(50), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=True)

    # Source tracking
    source = db.Column(db.String(20), nullable=False, default='synced', index=True)
    # Values: 'app_submitted', 'pre_existing', 'synced', 'bulk_added'

    # Link to submission if app-added
    submission_id = db.Column(db.Integer, db.ForeignKey('submissions.id'), nullable=True)
    submission = db.relationship('Submission', backref='list_member')

    # Timestamps
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Source constants
    SOURCE_APP_SUBMITTED = 'app_submitted'
    SOURCE_PRE_EXISTING = 'pre_existing'
    SOURCE_SYNCED = 'synced'
    SOURCE_BULK_ADDED = 'bulk_added'

    def to_dict(self):
        """Convert member to dictionary"""
        return {
            'id': self.id,
            'twitter_user_id': self.twitter_user_id,
            'username': self.username,
            'name': self.name,
            'source': self.source,
            'submission_id': self.submission_id,
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'synced_at': self.synced_at.isoformat() if self.synced_at else None,
        }

    def __repr__(self):
        return f'<ListMember @{self.username} ({self.source})>'


class SyncLog(db.Model):
    """Model for tracking Twitter list sync operations"""
    __tablename__ = 'sync_logs'

    id = db.Column(db.Integer, primary_key=True)
    sync_started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    sync_completed_at = db.Column(db.DateTime, nullable=True)

    members_fetched = db.Column(db.Integer, default=0)
    members_added = db.Column(db.Integer, default=0)
    members_removed = db.Column(db.Integer, default=0)
    members_updated = db.Column(db.Integer, default=0)

    status = db.Column(db.String(20), default='in_progress')  # in_progress, completed, failed
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Status constants
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    def to_dict(self):
        """Convert sync log to dictionary"""
        return {
            'id': self.id,
            'sync_started_at': self.sync_started_at.isoformat() if self.sync_started_at else None,
            'sync_completed_at': self.sync_completed_at.isoformat() if self.sync_completed_at else None,
            'members_fetched': self.members_fetched,
            'members_added': self.members_added,
            'members_removed': self.members_removed,
            'members_updated': self.members_updated,
            'status': self.status,
            'error_message': self.error_message,
        }

    def __repr__(self):
        return f'<SyncLog {self.id} ({self.status})>'
