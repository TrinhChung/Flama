"""Startup maintenance orchestration for app bootstrap."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from flask import Flask
from sqlalchemy import text

from models import db

from .services import flashcards_share
from .services.tts_provider_service import ensure_default_tts_providers
from .services.user_management_schema import ensure_user_management_schema
from .services.user_roles import ensure_default_user_roles


def run_startup_maintenance(
    app: Flask,
    *,
    ensure_backward_compatible_schema: Callable[[], None],
    config_overrides: Mapping[str, Any] | None = None,
) -> None:
    """Run legacy bootstrap tasks behind explicit config flags."""
    runtime_config = dict(app.config)
    if config_overrides:
        runtime_config.update(config_overrides)

    with app.app_context():
        # Step 1: Verify database connectivity
        if bool(runtime_config.get("STARTUP_CHECK_DB_CONNECTIVITY", True)):
            try:
                db.session.execute(text("SELECT 1"))
            except Exception as conn_err:
                app.logger.error("Database connectivity check failed on startup: %s", conn_err)
                if not bool(runtime_config.get("TESTING", False)):
                    raise

        # Step 2: Check if schema maintenance tasks should run
        if not bool(runtime_config.get("STARTUP_RUN_MAINTENANCE", False)):
            app.logger.info(
                "App bootstrap ready. Startup schema mutation is disabled (managed by Alembic migrations)."
            )
            return

        completed_tasks: list[str] = []
        try:
            if bool(runtime_config.get("STARTUP_RUN_DB_CREATE_ALL", True)):
                db.create_all()
                completed_tasks.append("db.create_all")

            if bool(runtime_config.get("STARTUP_RUN_USER_MANAGEMENT_SCHEMA", True)):
                ensure_user_management_schema(db.session)
                completed_tasks.append("ensure_user_management_schema")

            if bool(runtime_config.get("STARTUP_RUN_BACKWARD_COMPAT_SCHEMA", True)):
                ensure_backward_compatible_schema()
                completed_tasks.append("ensure_backward_compatible_schema")

            if bool(runtime_config.get("STARTUP_RUN_DEFAULT_USER_ROLE_SEED", bool(app.config.get("TESTING")))):
                ensure_default_user_roles(db.session)
                completed_tasks.append("ensure_default_user_roles")

            if bool(runtime_config.get("STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED", False)):
                ensure_default_tts_providers(db.session)
                completed_tasks.append("ensure_default_tts_providers")

            if bool(runtime_config.get("STARTUP_RUN_CLONE_CUTOVER", False)):
                cutover_summary = flashcards_share.cutover_clone_model_to_overlay_only(
                    fail_on_mismatch=bool(runtime_config.get("STARTUP_CUTOVER_FAIL_ON_MISMATCH", True)),
                )
                completed_tasks.append("cutover_clone_model_to_overlay_only")
                failed_cutovers = int(cutover_summary.get("failed") or 0)
                if failed_cutovers > 0:
                    app.logger.warning(
                        "Clone cutover completed with %s failed installs (migrated=%s, total=%s). "
                        "Set STARTUP_CUTOVER_FAIL_ON_MISMATCH=1 (or legacy "
                        "FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH=1) to enforce strict startup.",
                        failed_cutovers,
                        int(cutover_summary.get("migrated") or 0),
                        int(cutover_summary.get("total_installs") or 0),
                    )

            if completed_tasks:
                db.session.commit()
                app.logger.info("Startup maintenance completed: %s", ", ".join(completed_tasks))
        except Exception:
            db.session.rollback()
            app.logger.exception("Startup maintenance failed.")
            raise
