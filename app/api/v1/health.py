"""Deployment readiness endpoint."""

from __future__ import annotations

from flask import Blueprint, jsonify
from sqlalchemy import text

from models import db


health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """Confirm that the application and its database connection are ready."""
    db.session.execute(text("SELECT 1")).scalar_one()
    return jsonify({"status": "ok"})
