"""
Gunicorn configuration file for production deployment.
"""
import os
import multiprocessing

# Bind to port 8080 (required for DigitalOcean App Platform)
bind = "0.0.0.0:8080"

# Worker configuration
# Use 2-4 workers for better performance
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# Use gthread worker class for better I/O handling
worker_class = "gthread"
threads = int(os.getenv("GUNICORN_THREADS", 2))

# Worker temporary directory - use RAM for better performance
worker_tmp_dir = "/dev/shm"

# Timeout configuration
timeout = 120
keepalive = 5

# Logging
errorlog = "-"  # Log to stderr
accesslog = "-"  # Log to stdout
loglevel = os.getenv("LOG_LEVEL", "info")

# Process naming
proc_name = "twitter_list_manager"

# Graceful timeout for worker shutdown
graceful_timeout = 30

# Max requests per worker (for memory leak prevention)
max_requests = 1000
max_requests_jitter = 50

# Preload app for better memory efficiency
preload_app = True
