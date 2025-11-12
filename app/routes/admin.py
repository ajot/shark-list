from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from sqlalchemy import func
from datetime import datetime
from app import db
from app.models import Submission, ListMember, SyncLog
from app.services.twitter_service import TwitterService
from app.services.sync_service import SyncService

bp = Blueprint('admin', __name__)


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
        stats=stats
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

        # Update submission
        submission.approve(user_id)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Successfully approved @{submission.twitter_handle} and added to Twitter list'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
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

            # Update submission
            submission.approve(user_id)
            db.session.commit()

            results['success'].append({
                'id': submission_id,
                'handle': submission.twitter_handle
            })

        except Exception as e:
            db.session.rollback()
            results['failed'].append({
                'id': submission_id,
                'handle': submission.twitter_handle,
                'error': str(e)
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
