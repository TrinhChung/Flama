"""Canonical REST API implementation.

The package name remains ``v1`` as an internal implementation boundary, while
the public HTTP namespace is intentionally unversioned at ``/api``.
"""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from flask_login import current_user

from app.services import daily_rate_limit_service

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
)
from .download import download_bp
from .images import images_bp
from .profile import profile_bp
from .settings import settings_bp
from .tickets import tickets_bp
from .wallet import wallet_bp


api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api")


@api_v1_bp.before_request
def _enforce_daily_rate_limit():
    if request.method == "OPTIONS":
        return None

    path = request.path
    if path in {"/api/health", "/api/v1/health", "/api/csrf-token"} or path.startswith(
        (
            "/api/identity/login",
            "/api/identity/register",
            "/api/identity/logout",
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/forgot-password",
            "/api/auth/reset-password",
            "/api/billing/webhook",
            "/media/proxy",
        )
    ):
        return None


    if not getattr(current_user, "is_authenticated", False):
        return None

    quota = daily_rate_limit_service.resolve_user_daily_quota(current_user)
    if quota is None:
        _, reset_epoch = daily_rate_limit_service.get_current_day_bucket()
        g.daily_rate_limit_headers = daily_rate_limit_service.build_rate_limit_headers(
            quota=None, remaining=-1, reset_epoch=reset_epoch
        )
        return None

    allowed, count, remaining, reset_epoch = daily_rate_limit_service.consume_daily_quota(
        int(current_user.id), quota
    )
    g.daily_rate_limit_headers = daily_rate_limit_service.build_rate_limit_headers(
        quota=quota, remaining=remaining, reset_epoch=reset_epoch
    )

    if not allowed:
        headers = g.daily_rate_limit_headers
        response = jsonify(
            {
                "error": "RATE_LIMIT_EXCEEDED",
                "message": (
                    f"Bạn đã sử dụng hết hạn mức {quota} requests trong ngày. "
                    "Hạn mức sẽ được làm mới vào ngày mai."
                ),
                "limit": quota,
                "remaining": 0,
                "reset_at": reset_epoch,
            }
        )
        response.status_code = 429
        response.headers.update(headers)
        return response

    return None


@api_v1_bp.after_request
def _attach_rate_limit_headers(response):
    headers = getattr(g, "daily_rate_limit_headers", None)
    if headers:
        response.headers.update(headers)
    return response


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
api_v1_bp.register_blueprint(creator_deck_keys_bp)
api_v1_bp.register_blueprint(profile_bp, url_prefix="/profile")
api_v1_bp.register_blueprint(wallet_bp, url_prefix="/wallet")
api_v1_bp.register_blueprint(settings_bp)
api_v1_bp.register_blueprint(images_bp, url_prefix="/images")
api_v1_bp.register_blueprint(tickets_bp)
