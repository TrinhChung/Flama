"""Canonical REST API implementation.

The package name remains ``v1`` as an internal implementation boundary, while
the public HTTP namespace is intentionally unversioned at ``/api``.
"""

from __future__ import annotations

from flask import Blueprint

from .analytics import analytics_bp
from .admin import admin_bp
from .billing import billing_bp
from .decks import decks_bp
from .flashcards import flashcards_v1_bp
from .health import health_bp
from .identity import identity_bp
from .learning import learning_bp
from .marketplace import (
    marketplace_installations_bp,
    marketplace_note_types_bp,
)
from .settings import settings_bp

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api")
api_v1_bp.register_blueprint(health_bp)
api_v1_bp.register_blueprint(identity_bp)
api_v1_bp.register_blueprint(decks_bp, url_prefix="/decks")
api_v1_bp.register_blueprint(flashcards_v1_bp)
api_v1_bp.register_blueprint(analytics_bp)
api_v1_bp.register_blueprint(admin_bp, url_prefix="/admin")
api_v1_bp.register_blueprint(billing_bp)
api_v1_bp.register_blueprint(learning_bp)
api_v1_bp.register_blueprint(
    marketplace_installations_bp,
    url_prefix="/marketplace",
)
api_v1_bp.register_blueprint(marketplace_note_types_bp)
api_v1_bp.register_blueprint(settings_bp)

