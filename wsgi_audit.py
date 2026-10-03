"""Dedicated read-only WSGI and CLI entrypoint for study audits.

Production runs ``flask --app wsgi_audit.py study-phase9-readiness`` with a
SELECT-only MySQL principal; startup maintenance never runs here.
"""

import os

# Ensure startup maintenance is disabled in environment prior to app creation
os.environ["STARTUP_RUN_MAINTENANCE"] = "0"
os.environ["STARTUP_RUN_DB_CREATE_ALL"] = "0"
os.environ["STARTUP_RUN_USER_MANAGEMENT_SCHEMA"] = "0"
os.environ["STARTUP_RUN_BACKWARD_COMPAT_SCHEMA"] = "0"
os.environ["STARTUP_RUN_DEFAULT_USER_ROLE_SEED"] = "0"
os.environ["STARTUP_RUN_DEFAULT_TAXONOMY_SEED"] = "0"
os.environ["STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED"] = "0"
os.environ["STARTUP_RUN_CLONE_CUTOVER"] = "0"


def create_app():
    """Factory for Flask CLI or WSGI server (--app wsgi_audit)."""
    from app import create_audit_app

    return create_audit_app()


def __getattr__(name: str):
    """Lazy resolver for module attribute 'app' (e.g. gunicorn wsgi_audit:app)."""
    if name == "app":
        return create_app()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
