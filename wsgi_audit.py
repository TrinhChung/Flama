"""Dedicated read-only WSGI and CLI entrypoint for study architecture audit."""

import os
import sys

# Ensure startup maintenance is disabled in environment prior to app creation
os.environ["STARTUP_RUN_MAINTENANCE"] = "0"
os.environ["STARTUP_RUN_DB_CREATE_ALL"] = "0"
os.environ["STARTUP_RUN_USER_MANAGEMENT_SCHEMA"] = "0"
os.environ["STARTUP_RUN_BACKWARD_COMPAT_SCHEMA"] = "0"
os.environ["STARTUP_RUN_DEFAULT_USER_ROLE_SEED"] = "0"
os.environ["STARTUP_RUN_DEFAULT_TAXONOMY_SEED"] = "0"
os.environ["STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED"] = "0"
os.environ["STARTUP_RUN_CLONE_CUTOVER"] = "0"

from app.cli import run_study_architecture_audit_command


def create_app():
    """Factory for Flask CLI or WSGI server (--app wsgi_audit)."""
    from app import create_audit_app

    return create_audit_app()


def __getattr__(name: str):
    """Lazy resolver for module attribute 'app' (e.g. gunicorn wsgi_audit:app)."""
    if name == "app":
        return create_app()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def main(argv: list[str] | None = None) -> int:
    """Execute audit command directly from CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run study architecture reconciliation audit in read-only mode."
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        default=False,
        help="Emit compact JSON instead of indented JSON.",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        default=None,
        help="Optional file path to write audit JSON.",
    )
    args = parser.parse_args(argv)
    return run_study_architecture_audit_command(
        app=None,
        compact=args.compact,
        output_path=args.output_path,
    )


if __name__ == "__main__":
    sys.exit(main())
