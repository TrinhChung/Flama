"""Canonical REST API implementation.

The package name remains ``v1`` as an internal implementation boundary, while
the public HTTP namespace is intentionally unversioned at ``/api``.
"""

from __future__ import annotations

from flask import Blueprint

from .analytics import analytics_bp
from .admin import admin_bp
from .billing import billing_bp
from .creator import creator_deck_keys_bp
from .decks import decks_bp
from .flashcards import flashcards_v1_bp
from .health import health_bp
from .identity import identity_bp
from .learning import learning_bp
from .marketplace import (
    marketplace_deck_keys_bp,
    marketplace_deck_releases_bp,
    marketplace_installations_bp,
    marketplace_note_types_bp,
    marketplace_taxonomy_bp,
    marketplace_templates_bp,
)
from .download import download_bp
from .images import images_bp
from .profile import profile_bp
from .settings import settings_bp
from .strokes import strokes_bp
from .tickets import tickets_bp
from .wallet import wallet_bp
from .worksheets import worksheets_bp
from .internal import internal_security_bp


api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api")


api_v1_bp.register_blueprint(health_bp)
api_v1_bp.register_blueprint(identity_bp)
api_v1_bp.register_blueprint(decks_bp, url_prefix="/decks")
api_v1_bp.register_blueprint(flashcards_v1_bp)
api_v1_bp.register_blueprint(analytics_bp)
api_v1_bp.register_blueprint(admin_bp, url_prefix="/admin")
api_v1_bp.register_blueprint(billing_bp)
api_v1_bp.register_blueprint(download_bp)
api_v1_bp.register_blueprint(learning_bp)
api_v1_bp.register_blueprint(
    marketplace_installations_bp,
    url_prefix="/marketplace",
)
api_v1_bp.register_blueprint(marketplace_deck_keys_bp)
api_v1_bp.register_blueprint(marketplace_deck_releases_bp)
api_v1_bp.register_blueprint(marketplace_note_types_bp)
api_v1_bp.register_blueprint(marketplace_taxonomy_bp)
api_v1_bp.register_blueprint(marketplace_templates_bp)
api_v1_bp.register_blueprint(creator_deck_keys_bp)
api_v1_bp.register_blueprint(profile_bp, url_prefix="/profile")
api_v1_bp.register_blueprint(wallet_bp, url_prefix="/wallet")
api_v1_bp.register_blueprint(settings_bp)
api_v1_bp.register_blueprint(strokes_bp)
api_v1_bp.register_blueprint(images_bp, url_prefix="/images")
api_v1_bp.register_blueprint(tickets_bp)
api_v1_bp.register_blueprint(worksheets_bp)
api_v1_bp.register_blueprint(internal_security_bp)
