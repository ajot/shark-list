import os
from dotenv import load_dotenv

load_dotenv()


def get_database_uri():
    """
    Get database URI and ensure it uses the psycopg driver.
    Converts postgresql:// to postgresql+psycopg:// for psycopg3 compatibility.
    """
    db_url = os.getenv('DATABASE_URL') or os.getenv('DEV_DATABASE_URL')
    if db_url and db_url.startswith('postgresql://'):
        # Convert to use psycopg driver (psycopg3)
        db_url = db_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    return db_url


class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_SIZE = 10
    SQLALCHEMY_MAX_OVERFLOW = 20
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # Twitter API credentials
    TWITTER_API_KEY = os.getenv('API_KEY')
    TWITTER_API_SECRET = os.getenv('API_SECRET')
    TWITTER_ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
    TWITTER_ACCESS_TOKEN_SECRET = os.getenv('ACCESS_TOKEN_SECRET')
    TWITTER_LIST_ID = os.getenv('LIST_ID')

    # Pagination
    ITEMS_PER_PAGE = 20

    # Sync settings
    SYNC_COOLOFF_MINUTES = int(os.getenv('SYNC_COOLOFF_MINUTES', 5))


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = get_database_uri()


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False

    # Ensure all required environment variables are set in production
    @staticmethod
    def init_app(app):
        Config.init_app(app)

        # Log to stderr
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
