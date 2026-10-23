"""Gunicorn production configuration for Flama application."""

from __future__ import annotations

import multiprocessing
import os

# Binding
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:4789")

# Concurrency & Worker Model
# Default to 2-4 workers with multithreading (gthread) to prevent
# heavy CPU/IO requests (e.g. worksheet generation, Anki import) from blocking other users.
cpu_count = multiprocessing.cpu_count() or 2
default_workers = max(2, min(cpu_count, 4))
workers = int(os.environ.get("GUNICORN_WORKERS", default_workers))
threads = int(os.environ.get("GUNICORN_THREADS", 4))
worker_class = os.environ.get("GUNICORN_WORKER_CLASS", "gthread")

# Timeouts
# Extended timeout for large worksheet PDFs, Anki APKG imports, and media sync
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", 30))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))

# Server Mechanics & Limits
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", 100))

# Logging
accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
