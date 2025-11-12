"""
WSGI entry point for the application.
This file is used by gunicorn and other WSGI servers.
"""
import os
from app import create_app

# Create the Flask application
app = create_app(os.getenv('FLASK_ENV', 'production'))

if __name__ == "__main__":
    app.run()
