"""Standalone Flama Connect application factory.

This process intentionally does not register Flask-Login, session/CSRF handlers,
the main REST blueprints, legacy templates, or startup schema mutation.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from flask import Blueprint, Flask, current_app, jsonify, make_response, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from app.services import flama_connect_package_service, flama_connect_service, user_api_token_service
from app.settings import build_app_config, comma_separated_env, coerce_bool_env, coerce_int_env
from models import db


logger = logging.getLogger(__name__)
connect_bp = Blueprint("flama_connect", __name__)

from app.connect.request_pipeline import handle_request, protocol_response as _protocol_response
from app.services.connect.registry import ACTION_PARAMS, ACTION_SCOPES, LEGACY_WEB_ACTIONS as _LEGACY_WEB_ACTIONS
from app.services.connect.rate_limit import SlidingWindowLimiter, _limiter, rate_allowed as _rate_allowed


def _register_models() -> None:
    # SQLAlchemy resolves string relationships lazily, so every related model
    # used by this app must be registered even though Connect exposes only a few.
    from models.user import User  # noqa: F401
    from models.user_identity import UserIdentity  # noqa: F401
    from models.user_role import UserRole  # noqa: F401
    from models.user_scheduler_settings import UserSchedulerSettings  # noqa: F401
    from models.scheduler_preset import SchedulerPreset  # noqa: F401
    from models.user_api_token import UserApiToken  # noqa: F401
    from models.oauth_client import OAuthClient  # noqa: F401
    from models.oauth_authorization_code import OAuthAuthorizationCode  # noqa: F401
    from models.mcp_access_token import McpAccessToken  # noqa: F401
    from models.connect_note_ref import ConnectNoteRef  # noqa: F401
    from models.connect_pending_media import ConnectPendingMedia  # noqa: F401
    from models.connect_import_session import ConnectImportSession  # noqa: F401
    from models.connect_import_package import ConnectImportPackage  # noqa: F401
    from models.connect_import_media import ConnectImportMedia  # noqa: F401
    from models.connect_note_type_ref import ConnectNoteTypeRef  # noqa: F401
    from models.connect_source_deck_ref import ConnectSourceDeckRef  # noqa: F401
    from models.connect_source_note_ref import ConnectSourceNoteRef  # noqa: F401
    from models.flashcard import (  # noqa: F401
        AuditLog,
        Card,
        CardProgress,
        Deck,
        DeckCloneAddedFieldDef,
        DeckCloneAddedNote,
        DeckCloneDeckMap,
        DeckCloneFieldDefOverride,
        DeckCloneFieldOrderOverride,
        DeckCloneNoteFieldOverride,
        DeckChangeRequest,
        DeckChangeRequestConflict,
        DeckChangeRequestItem,
        DeckInstall,
        DeckMarketplaceItem,
        DeckReview,
        FieldDef,
        FieldRenameJob,
        MediaAsset,
        MarketplaceSavedItem,
        Note,
        NoteType,
        NoteTypeInstall,
        NoteTypeReview,
        ReviewEvent,
        StudySession,
        StudySessionCard,
        StudySessionCommit,
        Template,
    )
    from models.shared_image_asset import SharedImageAsset  # noqa: F401
    from models.template_version import TemplateVersion  # noqa: F401
    from models.template_publication import TemplatePublication  # noqa: F401
    from models.template_release import TemplateRelease  # noqa: F401
    from models.template_subscription import TemplateSubscription  # noqa: F401
    from models.study_template_preset import StudyTemplatePreset  # noqa: F401
    from models.deck_release_template_pin import DeckReleaseTemplatePin  # noqa: F401
    from app.services import template_version_service  # noqa: F401


@connect_bp.get("/healthz")
def healthz():
    return jsonify({"status": "ok", "service": "flama-connect"})


def _authenticate_direct_request(required_scope: str):
    auth_header = request.headers.get("Authorization", "")
    plaintext = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
    status, authenticated = user_api_token_service.authenticate_token_detailed(
        plaintext,
        required_scope=required_scope,
    )
    if authenticated is None:
        logger.info("Connect package authentication rejected status=%s", status)
        db.session.rollback()
        return None, (jsonify({"error": "AUTHENTICATION_FAILED", "message": "authentication failed"}), 401)
    return authenticated, None


@connect_bp.route("/v1/import-sessions/capabilities", methods=["GET", "OPTIONS"])
def import_capabilities():
    if not current_app.config.get("CONNECT_LEGACY_WEB_ACTIONS_ENABLED", False):
        return jsonify({"error": "not found"}), 404
    if request.method == "OPTIONS":
        return "", 204
    authenticated, error = _authenticate_direct_request("note:create")
    if error is not None:
        return error
    _token, _user = authenticated
    return jsonify(flama_connect_package_service.capabilities())


@connect_bp.route(
    "/v1/import-sessions/<session_id>/packages/media/<int:sequence>",
    methods=["PUT", "OPTIONS"],
)
def upload_import_media_package(session_id: str, sequence: int):
    if not current_app.config.get("CONNECT_LEGACY_WEB_ACTIONS_ENABLED", False):
        return jsonify({"error": "not found"}), 404
    if request.method == "OPTIONS":
        return "", 204
    authenticated, error = _authenticate_direct_request("note:create")
    if error is not None:
        return error
    token, user = authenticated
    if not _rate_allowed(f"package:{user.id}", "CONNECT_PACKAGE_RATE_LIMIT", 30):
        db.session.rollback()
        return jsonify({"error": "RATE_LIMITED", "message": "rate limit exceeded"}), 429
    try:
        result = flama_connect_package_service.receive_media_package(
            user_id=user.id,
            session_id=session_id,
            sequence=sequence,
            expected_sha256=request.headers.get("X-Package-SHA256", ""),
            content=request.get_data(cache=False),
        )
        db.session.commit()
        logger.info(
            "Connect media package accepted user_id=%s token_id=%s session_id=%s sequence=%s",
            user.id,
            token.id,
            session_id,
            sequence,
        )
        return jsonify(result)
    except flama_connect_package_service.ConnectPackageError as exc:
        db.session.rollback()
        status = 409 if "different checksum" in str(exc) else 400
        return jsonify({"error": "PACKAGE_REJECTED", "message": str(exc)}), status
    except Exception:
        db.session.rollback()
        logger.exception("Connect media package failed user_id=%s session_id=%s", user.id, session_id)
        return jsonify({"error": "INTERNAL_ERROR", "message": "internal error"}), 500


@connect_bp.route(
    "/v1/import-sessions/<session_id>/packages/cards/<int:sequence>",
    methods=["PUT", "OPTIONS"],
)
def upload_import_card_package(session_id: str, sequence: int):
    if not current_app.config.get("CONNECT_LEGACY_WEB_ACTIONS_ENABLED", False):
        return jsonify({"error": "not found"}), 404
    if request.method == "OPTIONS":
        return "", 204
    authenticated, error = _authenticate_direct_request("note:create")
    if error is not None:
        return error
    token, user = authenticated
    if not _rate_allowed(f"package:{user.id}", "CONNECT_PACKAGE_RATE_LIMIT", 30):
        db.session.rollback()
        return jsonify({"error": "RATE_LIMITED", "message": "rate limit exceeded"}), 429
    try:
        result = flama_connect_package_service.receive_card_package(
            user_id=user.id,
            session_id=session_id,
            sequence=sequence,
            expected_sha256=request.headers.get("X-Package-SHA256", ""),
            content=request.get_data(cache=False),
            content_encoding=request.headers.get("Content-Encoding", "identity"),
        )
        db.session.commit()
        logger.info(
            "Connect card package accepted user_id=%s token_id=%s session_id=%s sequence=%s",
            user.id,
            token.id,
            session_id,
            sequence,
        )
        return jsonify(result)
    except flama_connect_package_service.ConnectPackageError as exc:
        db.session.rollback()
        status = 409 if "different checksum" in str(exc) else 400
        return jsonify({"error": "PACKAGE_REJECTED", "message": str(exc)}), status
    except Exception:
        db.session.rollback()
        logger.exception("Connect card package failed user_id=%s session_id=%s", user.id, session_id)
        return jsonify({"error": "INTERNAL_ERROR", "message": "internal error"}), 500


@connect_bp.route("/v1/flama-connect", methods=["POST", "OPTIONS"])
@connect_bp.route("/v1/flama-connect/<url_token>", methods=["POST", "OPTIONS"])
def flama_connect(url_token: str | None = None):
    return handle_request(url_token=url_token)


@connect_bp.route("/v1/anki-connect", methods=["POST", "OPTIONS"])
def anki_connect():
    return handle_request(standard=True)


def _apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    origin = request.headers.get("Origin")
    standard = request.path == "/v1/anki-connect"
    allowed = set(current_app.config.get("CONNECT_ANKI_ALLOWED_ORIGINS" if standard else "CONNECT_CORS_ALLOWED_ORIGINS", ()))
    if standard:
        allowed -= {"*", "null"}
    if origin and (origin in allowed or (not standard and "*" in allowed)):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Content-Encoding, Authorization, X-Flama-Connect-Key, X-Package-SHA256, MCP-Protocol-Version"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "600"
    return response


def create_connect_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask("flama_connect", static_folder=None, template_folder=None)
    app_config = build_app_config(config)
    app_config.update(
        {
            "MAX_CONTENT_LENGTH": coerce_int_env("CONNECT_PACKAGE_MAX_BYTES", default=16 * 1024 * 1024),
            "CONNECT_JSON_MAX_CONTENT_LENGTH": coerce_int_env("CONNECT_MAX_CONTENT_LENGTH", default=2 * 1024 * 1024),
            "CONNECT_CORS_ALLOWED_ORIGINS": comma_separated_env("CONNECT_CORS_ALLOWED_ORIGINS"),
            "CONNECT_ANKI_ADAPTER_ENABLED": coerce_bool_env("CONNECT_ANKI_ADAPTER_ENABLED", default=False),
            "CONNECT_ANKI_MEDIA_ENABLED": coerce_bool_env("CONNECT_ANKI_MEDIA_ENABLED", default=False),
            "CONNECT_VERSIONED_PROTOCOL_ENABLED": coerce_bool_env("CONNECT_VERSIONED_PROTOCOL_ENABLED", default=False),
            "CONNECT_ANKI_ALLOWED_ORIGINS": comma_separated_env("CONNECT_ANKI_ALLOWED_ORIGINS"),
            "CONNECT_ANKI_MAX_CONTENT_LENGTH": coerce_int_env("CONNECT_ANKI_MAX_CONTENT_LENGTH", default=6 * 1024 * 1024),
            "CONNECT_ANKI_MEDIA_MAX_BYTES": coerce_int_env("CONNECT_ANKI_MEDIA_MAX_BYTES", default=2 * 1024 * 1024),
            "CONNECT_ANKI_NOTE_MEDIA_MAX_BYTES": coerce_int_env("CONNECT_ANKI_NOTE_MEDIA_MAX_BYTES", default=4 * 1024 * 1024),
            "CONNECT_ANKI_PENDING_MAX_BYTES": coerce_int_env("CONNECT_ANKI_PENDING_MAX_BYTES", default=16 * 1024 * 1024),
            "CONNECT_ANKI_STORAGE_MAX_BYTES": coerce_int_env("CONNECT_ANKI_STORAGE_MAX_BYTES", default=512 * 1024 * 1024),
            "CONNECT_RATE_LIMIT_BACKEND": os.environ.get("CONNECT_RATE_LIMIT_BACKEND", "local"),
            "CONNECT_TRUST_PROXY": coerce_bool_env("CONNECT_TRUST_PROXY", default=False),
            "CONNECT_LEGACY_WEB_ACTIONS_ENABLED": coerce_bool_env(
                "CONNECT_LEGACY_WEB_ACTIONS_ENABLED",
                default=False,
            ),
            "CONNECT_RATE_LIMIT_WINDOW_SECONDS": coerce_int_env("CONNECT_RATE_LIMIT_WINDOW_SECONDS", default=60),
            "CONNECT_IP_RATE_LIMIT": coerce_int_env("CONNECT_IP_RATE_LIMIT", default=120),
            "CONNECT_INVALID_TOKEN_RATE_LIMIT": coerce_int_env("CONNECT_INVALID_TOKEN_RATE_LIMIT", default=10),
            "CONNECT_TOKEN_RATE_LIMIT": coerce_int_env("CONNECT_TOKEN_RATE_LIMIT", default=60),
            "CONNECT_USER_RATE_LIMIT": coerce_int_env("CONNECT_USER_RATE_LIMIT", default=120),
            "CONNECT_ADD_NOTE_RATE_LIMIT": coerce_int_env("CONNECT_ADD_NOTE_RATE_LIMIT", default=20),
            "CONNECT_MEDIA_RATE_LIMIT": coerce_int_env("CONNECT_MEDIA_RATE_LIMIT", default=20),
            "CONNECT_MEDIA_MAX_BYTES": coerce_int_env("CONNECT_MEDIA_MAX_BYTES", default=1024 * 1024),
            "CONNECT_IMPORT_MEDIA_MAX_BYTES": coerce_int_env("CONNECT_IMPORT_MEDIA_MAX_BYTES", default=10 * 1024 * 1024),
            "CONNECT_IMPORT_MEDIA_MAX_ITEMS": coerce_int_env("CONNECT_IMPORT_MEDIA_MAX_ITEMS", default=20_000),
            "CONNECT_PACKAGE_MAX_BYTES": coerce_int_env("CONNECT_PACKAGE_MAX_BYTES", default=16 * 1024 * 1024),
            "CONNECT_PACKAGE_MAX_ENTRIES": coerce_int_env("CONNECT_PACKAGE_MAX_ENTRIES", default=500),
            "CONNECT_PACKAGE_MAX_UNCOMPRESSED_BYTES": coerce_int_env(
                "CONNECT_PACKAGE_MAX_UNCOMPRESSED_BYTES",
                default=64 * 1024 * 1024,
            ),
            "CONNECT_PACKAGE_MAX_COMPRESSION_RATIO": coerce_int_env(
                "CONNECT_PACKAGE_MAX_COMPRESSION_RATIO",
                default=100,
            ),
            "CONNECT_PACKAGE_RATE_LIMIT": coerce_int_env("CONNECT_PACKAGE_RATE_LIMIT", default=30),
            "CONNECT_PENDING_MEDIA_TTL_SECONDS": coerce_int_env(
                "CONNECT_PENDING_MEDIA_TTL_SECONDS",
                default=30 * 60,
            ),
            "CONNECT_PENDING_MEDIA_MAX_ITEMS": coerce_int_env(
                "CONNECT_PENDING_MEDIA_MAX_ITEMS",
                default=20,
            ),
            "CONNECT_PENDING_MEDIA_MAX_TOTAL_BYTES": coerce_int_env(
                "CONNECT_PENDING_MEDIA_MAX_TOTAL_BYTES",
                default=10 * 1024 * 1024,
            ),
        }
    )
    if config:
        app_config.update(config)
    if str(app_config.get("SQLALCHEMY_DATABASE_URI", "")).startswith("mysql"):
        # Auth queries precede account locks. READ COMMITTED prevents their
        # earlier snapshot hiding another request's committed note/quota rows.
        app_config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            **app_config.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
            "isolation_level": "READ COMMITTED",
        }
    app.config.update(app_config)
    app.extensions["connect_rate_limiter"] = SlidingWindowLimiter()
    if app.config.get("CONNECT_TRUST_PROXY"):
        # Safe only when Connect is bound behind one trusted reverse proxy.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
    db.init_app(app)
    _register_models()
    app.register_blueprint(connect_bp)

    from app.connect.mcp import mcp_connect_bp
    app.register_blueprint(mcp_connect_bp)

    app.after_request(_apply_security_headers)

    @app.cli.command("cleanup-connect-media")
    def cleanup_connect_media():
        """Purge expired pending uploads; run periodically from a timer/cron."""
        import json
        from app.services.connect.media_cleanup import cleanup
        print(json.dumps(cleanup()))

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        db.session.rollback()
        return _protocol_response(error="request body is too large", status=413, standard=request.path == "/v1/anki-connect")

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "not found"}), 404

    return app
