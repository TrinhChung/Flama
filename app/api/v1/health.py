"""Deployment readiness endpoint."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.services import redis_state_service
from models import db


health_bp = Blueprint("health", __name__)


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
    return jsonify({"status": "ok"})
