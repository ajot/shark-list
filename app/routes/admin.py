from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, session
from sqlalchemy import func
from datetime import datetime, timezone
import re
from app import db
from app.models import Submission, ListMember, SyncLog
from app.services.twitter_service import TwitterService
from app.services.sync_service import SyncService

bp = Blueprint('admin', __name__)


def parse_rate_limit_reset(error_message: str) -> int:
    """
    Extract rate limit reset timestamp from error message.

    Args:
        error_message: Error message string that may contain reset timestamp

    Returns:
        int: Unix timestamp when rate limit resets, or 0 if not found
    """
    # Look for pattern like "Resets at 2025-11-12 16:27:12"
    match = re.search(r'Resets at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', error_message)
    if match:
        try:
            # Parse and treat as UTC since Twitter API returns UTC timestamps
            dt = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
            dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except:
            pass

    # Look for pattern like "timestamp: 1762982832"
    match = re.search(r'timestamp[:\s]+(\d+)', error_message)
    if match:
        try:
            return int(match.group(1))
        except:
            pass

    return 0


def set_rate_limit_active(reset_timestamp: int):
    """Store rate limit state in session."""
    session['rate_limit_active'] = True
    session['rate_limit_reset'] = reset_timestamp
    session.modified = True


def check_rate_limit():
    """
    Check if rate limit is active.

    Returns:
        tuple: (is_active, reset_timestamp)
    """
    if not session.get('rate_limit_active'):
        return False, 0

    reset_timestamp = session.get('rate_limit_reset', 0)

    # Check if rate limit has expired
    if reset_timestamp and datetime.now().timestamp() >= reset_timestamp:
        session.pop('rate_limit_active', None)
        session.pop('rate_limit_reset', None)
        session.modified = True
        return False, 0

    return True, reset_timestamp


def store_rate_limit_info(twitter_service: TwitterService):
    """
    Store rate limit info from TwitterService in session.

    Args:
        twitter_service: TwitterService instance that just made an API call
    """
    rate_limit_info = twitter_service.get_rate_limit_info()
    if rate_limit_info:
        session['twitter_rate_limit'] = rate_limit_info
        session.modified = True


def get_rate_limit_info():
    """
    Get rate limit info from session.

    Returns:
        dict: Rate limit info or None
    """
    return session.get('twitter_rate_limit')


@bp.route('/')
def dashboard():
    """Admin dashboard showing pending submissions and all list members"""
    # Get pending submissions (oldest first, up to 10)
    pending_submissions = Submission.query.filter_by(
        status=Submission.STATUS_PENDING
    ).order_by(
        Submission.submitted_at.asc()
    ).limit(10).all()

    # Get total count of pending
    total_pending = Submission.query.filter_by(status=Submission.STATUS_PENDING).count()

    # Members list with pagination
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 20)

    # Build members query
    pagination = ListMember.query.order_by(
        ListMember.synced_at.desc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    # Get last sync info
    last_sync = SyncLog.query.order_by(SyncLog.sync_started_at.desc()).first()

    # Check if sync is allowed
    can_sync, sync_message = SyncService.can_sync()

    # Check rate limit status
    rate_limit_active, rate_limit_reset = check_rate_limit()

    # Get rate limit info
    rate_limit_info = get_rate_limit_info()

    # Get stats
    stats = {
        'total': ListMember.query.count(),
        'app_submitted': ListMember.query.filter_by(source=ListMember.SOURCE_APP_SUBMITTED).count(),
        'pre_existing': ListMember.query.filter_by(source=ListMember.SOURCE_PRE_EXISTING).count(),
    }

    return render_template(
        'admin/dashboard.html',
        pending_submissions=pending_submissions,
        total_pending=total_pending,
        members=pagination.items,
        pagination=pagination,
        last_sync=last_sync,
        can_sync=can_sync,
        sync_message=sync_message,
        stats=stats,
        rate_limit_active=rate_limit_active,
        rate_limit_reset=rate_limit_reset,
        rate_limit_info=rate_limit_info
    )


@bp.route('/pending')
def pending():
    """List pending submissions with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 20)

    pagination = Submission.query.filter_by(
        status=Submission.STATUS_PENDING
    ).order_by(
        Submission.submitted_at.asc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template('admin/pending.html', submissions=pagination.items, pagination=pagination)


@bp.route('/approve/<int:submission_id>', methods=['POST'])
def approve(submission_id):
    """Approve a submission and add to Twitter list"""
    submission = Submission.query.get_or_404(submission_id)

    if submission.status != Submission.STATUS_PENDING:
        return jsonify({
            'success': False,
            'message': f'Submission is already {submission.status}'
        }), 400

    try:
        # Initialize Twitter service
        twitter = TwitterService()

        # Get Twitter user ID (use cached if available to save API calls)
        if submission.twitter_user_id:
            user_id = submission.twitter_user_id
        else:
            user_id = twitter.get_user_id(submission.twitter_handle)
            # Cache the user_id for future use
            submission.twitter_user_id = user_id
            db.session.commit()

        # Add to Twitter list
        twitter.add_to_list(user_id)

        # Store rate limit info from the API call
        store_rate_limit_info(twitter)

        # Update submission
        submission.approve(user_id)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully approved @{submission.twitter_handle} and added to Twitter list'
        })

    except Exception as e:
        db.session.rollback()
        error_message = str(e)

        # Check if this is a rate limit error
        if 'rate limit exceeded' in error_message.lower():
            reset_timestamp = parse_rate_limit_reset(error_message)
            if reset_timestamp:
                set_rate_limit_active(reset_timestamp)

        return jsonify({
            'success': False,
            'message': f'Error: {error_message}'
        }), 500


@bp.route('/reject/<int:submission_id>', methods=['POST'])
def reject(submission_id):
    """Reject a submission"""
    submission = Submission.query.get_or_404(submission_id)

    if submission.status != Submission.STATUS_PENDING:
        return jsonify({
            'success': False,
            'message': f'Submission is already {submission.status}'
        }), 400

    try:
        notes = request.json.get('notes') if request.is_json else None
        submission.reject(notes)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Rejected @{submission.twitter_handle}'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@bp.route('/bulk-approve', methods=['POST'])
def bulk_approve():
    """Approve multiple submissions at once"""
    if not request.is_json:
        return jsonify({
            'success': False,
            'message': 'Request must be JSON'
        }), 400

    submission_ids = request.json.get('submission_ids', [])

    if not submission_ids:
        return jsonify({
            'success': False,
            'message': 'No submission IDs provided'
        }), 400

    results = {
        'success': [],
        'failed': []
    }

    twitter = TwitterService()

    for submission_id in submission_ids:
        submission = Submission.query.get(submission_id)

        if not submission:
            results['failed'].append({
                'id': submission_id,
                'error': 'Submission not found'
            })
            continue

        if submission.status != Submission.STATUS_PENDING:
            results['failed'].append({
                'id': submission_id,
                'handle': submission.twitter_handle,
                'error': f'Already {submission.status}'
            })
            continue

        try:
            # Get Twitter user ID (use cached if available to save API calls)
            if submission.twitter_user_id:
                user_id = submission.twitter_user_id
            else:
                user_id = twitter.get_user_id(submission.twitter_handle)
                # Cache the user_id for future use
                submission.twitter_user_id = user_id
                db.session.commit()

            # Add to list
            twitter.add_to_list(user_id)

            # Store rate limit info from the API call
            store_rate_limit_info(twitter)

            # Update submission
            submission.approve(user_id)
            db.session.commit()

            results['success'].append({
                'id': submission_id,
                'handle': submission.twitter_handle
            })

        except Exception as e:
            db.session.rollback()
            error_message = str(e)

            # Check if this is a rate limit error
            if 'rate limit exceeded' in error_message.lower():
                reset_timestamp = parse_rate_limit_reset(error_message)
                if reset_timestamp:
                    set_rate_limit_active(reset_timestamp)

            results['failed'].append({
                'id': submission_id,
                'handle': submission.twitter_handle,
                'error': error_message
            })

    return jsonify({
        'success': len(results['failed']) == 0,
        'message': f"Approved {len(results['success'])} submissions, {len(results['failed'])} failed",
        'results': results
    })


@bp.route('/remove/<int:submission_id>', methods=['POST'])
def remove(submission_id):
    """Remove a member from the Twitter list"""
    submission = Submission.query.get_or_404(submission_id)

    if submission.status != Submission.STATUS_APPROVED:
        return jsonify({
            'success': False,
            'message': 'Submission is not approved'
        }), 400

    if not submission.twitter_user_id:
        return jsonify({
            'success': False,
            'message': 'No Twitter user ID found'
        }), 400

    try:
        # Remove from Twitter list
        twitter = TwitterService()
        twitter.remove_from_list(submission.twitter_user_id)

        # Update submission status back to pending or delete
        # For now, we'll set it to rejected
        submission.reject(notes='Removed from list by admin')
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully removed @{submission.twitter_handle} from Twitter list'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@bp.route('/search')
def search():
    """Search submissions by email or Twitter handle"""
    query = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 20)

    # Build query
    submissions_query = Submission.query

    if query:
        submissions_query = submissions_query.filter(
            db.or_(
                Submission.email.ilike(f'%{query}%'),
                Submission.twitter_handle.ilike(f'%{query}%')
            )
        )

    if status:
        submissions_query = submissions_query.filter_by(status=status)

    pagination = submissions_query.order_by(
        Submission.submitted_at.desc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template(
        'admin/search.html',
        submissions=pagination.items,
        pagination=pagination,
        query=query,
        status=status
    )


@bp.route('/sync', methods=['POST'])
def sync():
    """Trigger Twitter list sync"""
    try:
        result = SyncService.sync_list_members()

        return jsonify({
            'success': True,
            'message': f"Sync completed: {result['members_fetched']} fetched, "
                      f"{result['members_added']} added, "
                      f"{result['members_updated']} updated, "
                      f"{result['members_removed']} removed",
            'result': result
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Sync failed: {str(e)}'
        }), 500


@bp.route('/check-rate-limit', methods=['POST'])
def check_rate_limit_status():
    """Check current rate limit status by making a lightweight API call"""
    try:
        twitter = TwitterService()
        # Make a lightweight API call to refresh rate limit info
        twitter.get_list_info()

        # Store rate limit info from the API call
        store_rate_limit_info(twitter)

        # Get the updated rate limit info
        rate_limit_info = get_rate_limit_info()

        if rate_limit_info:
            return jsonify({
                'success': True,
                'message': f"{rate_limit_info['remaining']} requests remaining",
                'rate_limit_info': rate_limit_info
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Could not retrieve rate limit information'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@bp.route('/remove-member/<int:member_id>', methods=['POST'])
def remove_member(member_id):
    """Remove a member from the Twitter list and database"""
    member = ListMember.query.get_or_404(member_id)

    try:
        # Remove from Twitter list
        twitter = TwitterService()
        twitter.remove_from_list(member.twitter_user_id)

        # Remove from database
        db.session.delete(member)

        # If this member has an associated submission, update it
        if member.submission:
            member.submission.reject(notes='Removed from list by admin')

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully removed @{member.username} from Twitter list'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@bp.route('/sync-history')
def sync_history():
    """View sync history"""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 20)

    pagination = SyncLog.query.order_by(
        SyncLog.sync_started_at.desc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template(
        'admin/sync_history.html',
        sync_logs=pagination.items,
        pagination=pagination
    )
