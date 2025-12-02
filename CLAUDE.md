# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Run development server
flask run

# Run with gunicorn (production-style)
gunicorn --config gunicorn_config.py wsgi:app

# Database migrations
flask db migrate -m "description"
flask db upgrade
flask db downgrade
```

## Architecture

This is a Flask application for managing a Twitter list via a public submission form and admin dashboard. Users submit their Twitter handles through a public form, and admins approve/reject submissions which then add/remove users from a Twitter list via the Twitter API v2.

### Core Components

- **Entry Point**: `wsgi.py` creates the Flask app via the factory pattern in `app/__init__.py`
- **Configuration**: `config.py` loads from `.env` and defines `DevelopmentConfig`/`ProductionConfig`
- **Database**: PostgreSQL with Flask-SQLAlchemy and Flask-Migrate (uses psycopg3 driver)

### Routes (Blueprints)

- `app/routes/public.py` - Public submission form at `/` and `/submit`
- `app/routes/admin.py` - Admin dashboard at `/admin/` with approval workflow, sync, member management

### Models (`app/models.py`)

- `Submission` - User submissions with status tracking (pending/approved/rejected)
- `ListMember` - Source of truth for Twitter list members with source tracking (app_submitted/pre_existing/synced/bulk_added)
- `SyncLog` - Audit log for Twitter list sync operations

### Services (`app/services/`)

- `twitter_service.py` - Twitter API v2 integration with OAuth1 authentication. Handles user lookup, list membership operations, and rate limit tracking
- `sync_service.py` - Syncs Twitter list members with local database, enforces cooloff period between syncs

### Key Flows

1. **Submission Flow**: User submits handle → stored as pending → admin approves → TwitterService adds to list → ListMember created
2. **Sync Flow**: Admin triggers sync → SyncService fetches all list members from Twitter → reconciles with local ListMember table → updates/adds/removes as needed

## Environment Variables

Required in `.env` (see `.env.example`):
- `DATABASE_URL` / `DEV_DATABASE_URL` - PostgreSQL connection string
- `API_KEY`, `API_SECRET`, `ACCESS_TOKEN`, `ACCESS_TOKEN_SECRET` - Twitter API OAuth credentials
- `LIST_ID` - Target Twitter list ID
- `SECRET_KEY` - Flask secret key
- `SYNC_COOLOFF_MINUTES` - Minimum minutes between syncs (default: 5)
