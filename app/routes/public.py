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
    """Handle form submission"""
    email = request.form.get('email', '').strip()
    twitter_handle = request.form.get('twitter_handle', '').strip()

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

    if not twitter_handle:
        errors.append("Twitter handle is required")
    elif len(twitter_handle) < 1 or len(twitter_handle) > 15:
        errors.append("Twitter handle must be between 1 and 15 characters")

    # If there are validation errors, show them and return to form
    if errors:
        for error in errors:
            flash(error, 'error')
        return render_template('index.html'), 400

    # Check if submission already exists
    normalized_handle = Submission.normalize_handle(twitter_handle)
    existing_submission = Submission.query.filter_by(twitter_handle=normalized_handle).first()

    if existing_submission:
        if existing_submission.status == Submission.STATUS_PENDING:
            flash(
                f"The Twitter handle @{normalized_handle} has already been submitted and is pending approval. "
                "Please check back later.",
                'error'
            )
            return render_template('index.html'), 400
        elif existing_submission.status == Submission.STATUS_APPROVED:
            flash(
                f"The Twitter handle @{normalized_handle} has already been approved and is on the list!",
                'error'
            )
            return render_template('index.html'), 400
        # If rejected, allow re-submission by deleting the old one
        else:
            try:
                db.session.delete(existing_submission)
                db.session.flush()  # Ensure deletion happens before insert
            except Exception as e:
                db.session.rollback()
                flash(f"An error occurred while removing old submission: {str(e)}", 'error')
                return render_template('index.html'), 500

    # Create submission
    try:
        submission = Submission(
            email=email,
            twitter_handle=twitter_handle
        )
        db.session.add(submission)
        db.session.commit()

        flash(
            f"Thank you! Your request to add @{submission.twitter_handle} has been submitted successfully. "
            "We'll review it shortly and add you to our Twitter list.",
            'success'
        )
        return redirect(url_for('public.index'))

    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {str(e)}", 'error')
        return render_template('index.html'), 500
