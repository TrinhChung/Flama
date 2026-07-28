"""Versioned HTTP API registration."""

from __future__ import annotations

from flask import Flask

from .v1 import api_v1_bp


def register_api_blueprints(app: Flask) -> None:
    """Register versioned API blueprints."""
    app.register_blueprint(api_v1_bp)
