"""Standalone Flama Connect application factory.

This process intentionally does not register Flask-Login, session/CSRF handlers,
the main REST blueprints, legacy templates, or startup schema mutation.
"""

from __future__ import annotations

from collections import defaultdict, deque
import hmac
import json
import logging
from threading import Lock
import time
from typing import Any

from flask import Blueprint, Flask, current_app, jsonify, make_response, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from app.services import flama_connect_package_service, flama_connect_service, user_api_token_service
from app.settings import build_app_config, comma_separated_env, coerce_bool_env, coerce_int_env
from models import db


logger = logging.getLogger(__name__)
connect_bp = Blueprint("flama_connect", __name__)

_LEGACY_WEB_ACTIONS = frozenset(
    {
        "validateKey",
        "userInfo",
        "createImportSession",
        "importCards",
        "getImportStatus",
        "completeImportSession",
    }
)

ACTION_PARAMS: dict[str, frozenset[str]] = {
    "version": frozenset(),
    "apiReflect": frozenset({"scopes", "actions"}),
    "validateKey": frozenset(),
    "userInfo": frozenset(),
    "deckNames": frozenset(),
    "modelNames": frozenset(),
    "modelFieldNames": frozenset({"modelName"}),
    "canAddNotes": frozenset({"notes"}),
    "canAddNotesWithErrorDetail": frozenset({"notes"}),
    "findNotes": frozenset({"query"}),
    "multi": frozenset({"actions"}),
    "addNote": frozenset({"note"}),
    "storeMediaFile": frozenset({"filename", "data", "path", "url", "deleteExisting", "importSessionId", "mediaKind"}),
    "createImportSession": frozenset({
        "source",
        "sourceKey",
        "sourceRootPath",
        "targetRootPath",
        "selectedDecks",
        "decks",
        "totalNotes",
        "totalMedia",
        "appVersion",
        "mode",
        "noteTypes",
        "planHash",
    }),
    "importCards": frozenset({"importSessionId", "cards", "deckName"}),
    "getImportStatus": frozenset({"importSessionId"}),
    "completeImportSession": frozenset({"importSessionId"}),
}
ACTION_SCOPES = {
    "apiReflect": "note-type:read",
    "validateKey": None,
    "userInfo": None,
    "deckNames": "deck:read",
    "modelNames": "note-type:read",
    "modelFieldNames": "note-type:read",
    "canAddNotes": "note:check",
    "canAddNotesWithErrorDetail": "note:check",
    "findNotes": "note:check",
    "multi": "note:check",
    "addNote": "note:create",
    "storeMediaFile": "note:create",
    "createImportSession": "note:create",
    "importCards": "note:create",
    "getImportStatus": "note:create",
    "completeImportSession": "note:create",
}


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, maximum: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            if len(self._events) >= 10_000:
                stale_keys = [
                    event_key
                    for event_key, events in self._events.items()
                    if not events or events[-1] <= cutoff
                ]
                for event_key in stale_keys:
                    self._events.pop(event_key, None)
            if key not in self._events and len(self._events) >= 20_000:
                return False
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= maximum:
                return False
            bucket.append(now)
            return True


_limiter = SlidingWindowLimiter()


class ProtocolError(ValueError):
    pass


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


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate JSON property")
        result[key] = value
    return result


def _reject_non_json_constant(value: str):
    raise ProtocolError(f"invalid JSON number: {value}")


def _assert_depth(value: Any, *, depth: int = 0) -> None:
    if depth > 12:
        raise ProtocolError("JSON nesting is too deep")
    if isinstance(value, dict):
        for child in value.values():
            _assert_depth(child, depth=depth + 1)
    elif isinstance(value, list):
        for child in value:
            _assert_depth(child, depth=depth + 1)


def _parse_request() -> dict[str, Any]:
    content_type = (request.mimetype or "").lower()
    if content_type != "application/json":
        raise ProtocolError("Content-Type must be application/json")
    encoding = str(request.headers.get("Content-Encoding") or "identity").strip().lower()
    if encoding not in {"", "identity"}:
        raise ProtocolError("compressed request bodies are not supported")
    raw = request.get_data(cache=False)
    json_limit = int(current_app.config.get("CONNECT_JSON_MAX_CONTENT_LENGTH", 2 * 1024 * 1024))
    if len(raw) > json_limit:
        raise ProtocolError("request body is too large")
    if not raw:
        raise ProtocolError("request body is required")
    try:
        payload = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_json_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("request body is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("request body must be a JSON object")
    _assert_depth(payload)
    unknown = set(payload) - {"action", "params", "version", "key"}
    missing = {"action", "version"} - set(payload)
    if unknown or missing:
        raise ProtocolError("request properties are invalid")
    action = payload.get("action")
    version = payload.get("version")
    if not isinstance(action, str) or not action.isascii() or not 1 <= len(action) <= 64:
        raise ProtocolError("action is invalid")
    if action not in ACTION_PARAMS:
        raise ProtocolError("unsupported action")
    legacy_web_enabled = bool(
        current_app.config.get("CONNECT_LEGACY_WEB_ACTIONS_ENABLED", False)
    )
    if action in _LEGACY_WEB_ACTIONS and not legacy_web_enabled:
        raise ProtocolError("unsupported action")
    if isinstance(version, bool) or not isinstance(version, int) or not 2 <= version <= 6:
        raise ProtocolError("version must be an integer between 2 and 6")
    params = payload.get("params", {})
    if not isinstance(params, dict):
        raise ProtocolError("params must be an object")
    allowed_params = ACTION_PARAMS[action]
    if action == "storeMediaFile" and not legacy_web_enabled:
        allowed_params = frozenset({"filename", "data"})
    if set(params) - allowed_params:
        raise ProtocolError("params contains unsupported properties")
    payload["params"] = params
    return payload


def _protocol_response(*, result: Any = None, error: str | None = None, status: int = 200):
    # Yomitan currently sends its local protocol version 2. Flama Connect returns
    # successful values directly and an object containing `error` on failure.
    payload = result if error is None else {"result": None, "error": error}
    response = make_response(jsonify(payload), status)
    response.headers["Cache-Control"] = "no-store"
    return response


def _client_ip() -> str:
    # ProxyFix or the edge proxy must establish the trusted remote address.
    # Connect never trusts X-Forwarded-For directly.
    return str(request.remote_addr or "unknown")


def _rate_allowed(key: str, config_name: str, default: int) -> bool:
    maximum = int(current_app.config.get(config_name, default))
    window = int(current_app.config.get("CONNECT_RATE_LIMIT_WINDOW_SECONDS", 60))
    return _limiter.allow(key, maximum=max(1, maximum), window_seconds=max(1, window))


def _dispatch_multi(user_id: int, params: dict[str, Any], outer_key: str) -> list[Any]:
    actions = params.get("actions")
    if not isinstance(actions, list) or len(actions) > flama_connect_service.MAX_MULTI_ACTIONS:
        raise ProtocolError("actions must be an array with at most 10 entries")
    validated_actions: list[dict[str, Any]] = []
    for item in actions:
        if not isinstance(item, dict) or set(item) - {"action", "params", "key"}:
            raise ProtocolError("multi action is invalid")
        action = item.get("action")
        nested_params = item.get("params", {})
        if action != "findNotes" or not isinstance(nested_params, dict):
            raise ProtocolError("multi only supports findNotes")
        if set(nested_params) - ACTION_PARAMS["findNotes"]:
            raise ProtocolError("multi params contains unsupported properties")
        nested_key = item.get("key")
        if nested_key is not None and nested_key != outer_key:
            raise ProtocolError("multi key does not match the request key")
        validated_actions.append(nested_params)
    return [
        flama_connect_service.dispatch(user_id, "findNotes", nested_params)
        for nested_params in validated_actions
    ]


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
    if request.method == "OPTIONS":
        return "", 204
    ip = _client_ip()
    if not _rate_allowed(f"ip:{ip}", "CONNECT_IP_RATE_LIMIT", 120):
        return _protocol_response(error="rate limit exceeded", status=429)
    try:
        payload = _parse_request()
    except ProtocolError as exc:
        logger.info("Connect rejected malformed request from ip=%s", ip)
        return _protocol_response(error=str(exc))

    auth_header = request.headers.get("Authorization", "")
    header_key = None
    if auth_header.startswith("Bearer "):
        header_key = auth_header[7:].strip()
    elif request.headers.get("X-Flama-Connect-Key"):
        header_key = request.headers.get("X-Flama-Connect-Key", "").strip()

    body_key = payload.get("key")
    if body_key is not None and not isinstance(body_key, str):
        body_key = None
    if url_token is not None and body_key is not None and not hmac.compare_digest(url_token, body_key):
        authenticated = None
        authentication_key = None
        auth_status = "mismatch"
    else:
        authentication_key = header_key or url_token or body_key
        auth_status, authenticated = user_api_token_service.authenticate_token_detailed(authentication_key)
    if authenticated is None:
        if not _rate_allowed(f"invalid:{ip}", "CONNECT_INVALID_TOKEN_RATE_LIMIT", 10):
            return _protocol_response(error="rate limit exceeded", status=429)
        logger.warning("Connect authentication failed status=%s from ip=%s", auth_status, ip)
        db.session.rollback()
        error_msg = "authentication failed"
        if auth_status == "revoked":
            error_msg = "revoked key"
        elif auth_status == "expired":
            error_msg = "expired key"
        elif auth_status == "user_disabled":
            error_msg = "account disabled"
        elif auth_status == "permission_denied":
            error_msg = "permission denied"
        elif auth_status in {"invalid_format", "not_found", "mismatch"}:
            error_msg = "authentication failed"
        return _protocol_response(error=error_msg)
    # authenticate_token only succeeds for a validated plaintext token. Keep the
    # validated value for nested multi-action checks without reading it again.
    assert isinstance(authentication_key, str)
    token, user = authenticated
    action = payload["action"]
    required_scope = ACTION_SCOPES.get(action)
    if required_scope and required_scope not in user_api_token_service.parse_scopes(token):
        db.session.rollback()
        return _protocol_response(error="permission denied")
    if not _rate_allowed(f"token:{token.id}", "CONNECT_TOKEN_RATE_LIMIT", 60):
        db.session.rollback()
        return _protocol_response(error="rate limit exceeded", status=429)
    if not _rate_allowed(f"user:{user.id}", "CONNECT_USER_RATE_LIMIT", 120):
        db.session.rollback()
        return _protocol_response(error="rate limit exceeded", status=429)
    if action == "addNote" and not _rate_allowed(f"add:{user.id}", "CONNECT_ADD_NOTE_RATE_LIMIT", 20):
        db.session.rollback()
        return _protocol_response(error="rate limit exceeded", status=429)
    if action == "storeMediaFile" and not _rate_allowed(
        f"media:{user.id}",
        "CONNECT_MEDIA_RATE_LIMIT",
        20,
    ):
        db.session.rollback()
        return _protocol_response(error="rate limit exceeded", status=429)

    try:
        if action == "multi":
            result = _dispatch_multi(user.id, payload["params"], authentication_key)
        else:
            result = flama_connect_service.dispatch(user.id, action, payload["params"])
        db.session.commit()
        logger.info("Connect action succeeded user_id=%s token_id=%s action=%s", user.id, token.id, action)
        return _protocol_response(result=result)
    except (ProtocolError, flama_connect_service.ConnectError) as exc:
        db.session.rollback()
        logger.info(
            "Connect action rejected user_id=%s token_id=%s action=%s",
            user.id,
            token.id,
            action,
        )
        return _protocol_response(error=str(exc))
    except Exception:
        db.session.rollback()
        logger.exception("Connect action failed user_id=%s token_id=%s action=%s", user.id, token.id, action)
        return _protocol_response(error="internal error")


def _apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    origin = request.headers.get("Origin")
    allowed = set(current_app.config.get("CONNECT_CORS_ALLOWED_ORIGINS", ()))
    if origin and ("*" in allowed or origin in allowed):
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
    app.config.update(app_config)
    if app.config.get("CONNECT_TRUST_PROXY"):
        # Safe only when Connect is bound behind one trusted reverse proxy.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
    db.init_app(app)
    _register_models()
    app.register_blueprint(connect_bp)

    from app.connect.mcp import mcp_connect_bp
    app.register_blueprint(mcp_connect_bp)

    app.after_request(_apply_security_headers)

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        db.session.rollback()
        return _protocol_response(error="request body is too large", status=413)

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify({"error": "not found"}), 404

    return app
