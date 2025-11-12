from flask import Blueprint, render_template, request, flash, redirect, url_for
from sqlalchemy.exc import IntegrityError
from email_validator import validate_email, EmailNotValidError
from app import db
from app.models import Submission

bp = Blueprint('public', __name__)


@bp.route('/')
def index():
    """Display the submission form"""
    return render_template('index.html')


@bp.route('/submit', methods=['POST'])
def submit():
    """Handle form submission - supports single or multiple Twitter handles"""
    email = request.form.get('email', '').strip()
    twitter_handles_text = request.form.get('twitter_handles', '').strip()

    # Validation
    errors = []

    if not email:
        errors.append("Email is required")
    else:
        try:
            # Validate email format
            valid = validate_email(email)
            email = valid.email
        except EmailNotValidError as e:
            errors.append(f"Invalid email: {str(e)}")

    if not twitter_handles_text:
        errors.append("At least one Twitter handle is required")

    # If there are validation errors, show them and return to form
    if errors:
        for error in errors:
            flash(error, 'error')
        return render_template('index.html'), 400

    # Parse handles (split by newlines, strip whitespace, remove @ symbols)
    handles = []
    for line in twitter_handles_text.split('\n'):
        handle = line.strip().lstrip('@')
        if handle:  # Skip empty lines
            # Validate handle length
            if len(handle) < 1 or len(handle) > 15:
                flash(f"Twitter handle '{handle}' must be between 1 and 15 characters", 'error')
                return render_template('index.html'), 400
            handles.append(handle)

    if not handles:
        flash("No valid Twitter handles found", 'error')
        return render_template('index.html'), 400

    # Process each handle
    results = {
        'success': [],
        'skipped': [],
        'failed': []
    }

    for handle in handles:
        # Normalize handle for comparison
        normalized_handle = Submission.normalize_handle(handle)

        # Check if submission already exists
        existing_submission = Submission.query.filter_by(twitter_handle=normalized_handle).first()

        if existing_submission:
            if existing_submission.status == Submission.STATUS_PENDING:
                results['skipped'].append({
                    'handle': handle,
                    'reason': 'Already pending approval'
                })
                continue
            elif existing_submission.status == Submission.STATUS_APPROVED:
                results['skipped'].append({
                    'handle': handle,
                    'reason': 'Already approved'
                })
                continue
            # If rejected, allow re-submission by deleting the old one
            else:
                try:
                    db.session.delete(existing_submission)
                    db.session.flush()  # Ensure deletion happens before insert
                except Exception as e:
                    db.session.rollback()
                    results['failed'].append({
                        'handle': handle,
                        'error': f"Failed to delete old submission: {str(e)}"
                    })
                    continue

        try:
            # Create submission
            submission = Submission(
                email=email,
                twitter_handle=handle
            )
            db.session.add(submission)
            db.session.commit()

            results['success'].append(handle)

        except Exception as e:
            db.session.rollback()
            results['failed'].append({
                'handle': handle,
                'error': str(e)
            })

    # Show summary message
    message_parts = []
    if results['success']:
        handles_str = ", ".join([f"@{h}" for h in results['success']])
        message_parts.append(f"Successfully submitted: {handles_str}")
    if results['skipped']:
        for item in results['skipped']:
            message_parts.append(f"@{item['handle']} - {item['reason']}")
    if results['failed']:
        for item in results['failed']:
            message_parts.append(f"@{item['handle']} - Error: {item['error']}")

    if results['success']:
        flash(
            f"Thank you! {len(results['success'])} handle(s) submitted successfully. "
            "We'll review them shortly and add you to our Twitter list.",
            'success'
        )

    if results['skipped'] or results['failed']:
        for msg in message_parts[len(results['success']):]:
            flash(msg, 'error')

    return redirect(url_for('public.index'))
