"""Deployment readiness endpoint."""

from __future__ import annotations

from pathlib import Path
import re

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.services import redis_state_service
from models import db


health_bp = Blueprint("health", __name__)

# deploy.yml stamps the commit into each release directory. The frontend
# deploy reads it back to refuse publishing a SPA ahead of its backend.
_RELEASE_FILE = Path(__file__).resolve().parents[3] / "REVISION"
_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")


def _release_id() -> str | None:
    """Return the deployed commit, or None outside a stamped release."""
    try:
        value = _RELEASE_FILE.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    return value if _COMMIT_SHA.fullmatch(value) else None


@health_bp.get("/health")
def health():
    """Confirm that the application and its database connection are ready."""
    db.session.execute(text("SELECT 1")).scalar_one()
    redis_required = any(
        redis_state_service.backend_mode(config_name) == "redis"
        for config_name in ("RATE_LIMIT_BACKEND", "MCP_PREVIEW_BACKEND")
    )
    if redis_required:
        try:
            redis_state_service.redis_client().ping()
        except Exception as exc:
            current_app.logger.error("Redis readiness check failed: %s", exc)
            return jsonify({"status": "unavailable", "dependency": "redis"}), 503
    return jsonify({"status": "ok", "release": _release_id()})
