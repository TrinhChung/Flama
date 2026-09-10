"""Dedicated read-only WSGI and CLI entrypoint for study architecture audit."""

import os
import sys
from datetime import datetime, timezone

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
    parser.add_argument(
        "--observed-at",
        type=_parse_observed_at,
        default=None,
        help="Freeze the audit observation time (ISO-8601) for repeatability.",
    )
    args = parser.parse_args(argv)
    return run_study_architecture_audit_command(
        app=None,
        compact=args.compact,
        output_path=args.output_path,
        observed_at=args.observed_at,
    )


def _parse_observed_at(value: str) -> datetime:
    """Parse ISO-8601 into the naive UTC convention used by persisted timestamps."""

    normalized = str(value or "").strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("expected an ISO-8601 timestamp") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


if __name__ == "__main__":
    sys.exit(main())
