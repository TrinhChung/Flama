"""One HTTP/auth/transaction pipeline for legacy and standard Connect routes."""

import hmac
import logging

from flask import current_app, jsonify, make_response, request
from werkzeug.exceptions import RequestEntityTooLarge

from app.connect.protocol import ProtocolError, encode_result, parse_body, validate_payload
from app.services import flama_connect_service as service, user_api_token_service as tokens
from app.services.connect.registry import ACTIONS, MAX_MULTI_ACTIONS
from app.services.connect.rate_limit import rate_allowed
from app.services.connect.unit_of_work import ConnectUnitOfWork
from app.services.redis_state_service import SharedStateUnavailable
from models import db

logger = logging.getLogger(__name__)


def _same_key(left, right):
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def protocol_response(*, result=None, error=None, status=200, version=4, standard=False):
    versioned = standard or bool(current_app.config.get("CONNECT_VERSIONED_PROTOCOL_ENABLED", False))
    response = make_response(jsonify(encode_result(result, error, version=version, versioned=versioned)), status)
    response.headers["Cache-Control"] = "no-store"
    if status == 429:
        response.headers["Retry-After"] = str(current_app.config.get("CONNECT_RATE_LIMIT_WINDOW_SECONDS", 60))
    return response


def _required_scope(payload, scopes, *, standard):
    action = payload["action"]
    required = "media:write" if standard and action == "storeMediaFile" else ACTIONS[action].scope
    if standard and action == "multi":
        required = None  # Each nested action is checked separately.
    if required and not tokens.has_scope(scopes, required):
        raise ProtocolError("permission denied")


def _batch(payload, key, scopes, *, standard):
    items = payload["params"].get("actions")
    if not isinstance(items, list) or len(items) > MAX_MULTI_ACTIONS:
        raise ProtocolError("actions must be an array with at most 10 entries")
    validated = []
    for item in items:
        if not isinstance(item, dict):
            raise ProtocolError("multi action is invalid")
        if not standard:
            if set(item) - {"action", "params", "key"} or item.get("action") != "findNotes":
                raise ProtocolError("multi only supports findNotes")
            item = {**item, "version": 4}
        nested = validate_payload(item, standard=standard)
        if standard and not ACTIONS[nested["action"]].batch_read:
            raise ProtocolError("multi supports read actions only; nested multi is not supported")
        if nested.get("key") is not None and not _same_key(str(nested["key"]), key):
            raise ProtocolError("multi key does not match the request key")
        _required_scope(nested, scopes, standard=standard)
        validated.append(nested)
    return validated


def handle_request(*, standard=False, url_token=None):
    version = 4
    def respond(**kwargs):
        return protocol_response(version=version, standard=standard, **kwargs)
    if standard and not current_app.config.get("CONNECT_ANKI_ADAPTER_ENABLED", False):
        return respond(error="AnkiConnect adapter is disabled", status=404)
    if standard:
        origin = request.headers.get("Origin")
        allowed = set(current_app.config.get("CONNECT_ANKI_ALLOWED_ORIGINS", ())) - {"*", "null"}
        if origin is not None and origin not in allowed:
            return respond(error="origin is not allowed", status=403)
    if request.method == "OPTIONS":
        return "", 204
    ip = str(request.remote_addr or "unknown")
    uow = ConnectUnitOfWork()
    try:
        if not rate_allowed(f"ip:{ip}", "CONNECT_IP_RATE_LIMIT", 120):
            return respond(error="rate limit exceeded", status=429)
        limit = int(current_app.config.get("CONNECT_ANKI_MAX_CONTENT_LENGTH" if standard else "CONNECT_JSON_MAX_CONTENT_LENGTH", 6 * 1024 * 1024 if standard else 2 * 1024 * 1024))
        if request.content_length is not None and request.content_length > limit:
            raise RequestEntityTooLarge()
        if standard and str(request.mimetype_params.get("charset", "utf-8")).lower() not in {"utf-8", "utf8"}:
            raise ProtocolError("request charset must be UTF-8")
        raw = request.stream.read(limit + 1)
        if len(raw) > limit:
            raise RequestEntityTooLarge()
        payload = parse_body(raw, content_type=request.mimetype or "", encoding=request.headers.get("Content-Encoding", "identity"), limit=limit, standard=standard, legacy_web=bool(current_app.config.get("CONNECT_LEGACY_WEB_ACTIONS_ENABLED", False)))
        version = payload["version"]
        auth = request.headers.get("Authorization", "")
        header = auth[7:].strip() if auth.startswith("Bearer ") else request.headers.get("X-Flama-Connect-Key", "").strip()
        body = payload.get("key")
        body = body if isinstance(body, str) else None
        candidates = [value for value in (header, url_token, body) if value]
        conflict = standard and any(not _same_key(candidates[0], value) for value in candidates[1:])
        conflict = conflict or (url_token is not None and body is not None and not _same_key(url_token, body))
        key = candidates[0] if candidates else None
        auth_status, authenticated = ("mismatch", None) if conflict else tokens.authenticate_token_detailed(key)
        if authenticated is None:
            uow.rollback()
            if not rate_allowed(f"invalid:{ip}", "CONNECT_INVALID_TOKEN_RATE_LIMIT", 10):
                return respond(error="rate limit exceeded", status=429)
            logger.info("Connect authentication rejected status=%s", auth_status)
            error = {"revoked": "revoked key", "expired": "expired key", "user_disabled": "account disabled", "permission_denied": "permission denied"}.get(auth_status, "valid API key must be provided" if standard else "authentication failed")
            return respond(error=error, status=401 if standard else 200)
        token, user = authenticated
        scopes = tokens.parse_scopes(token)
        _required_scope(payload, scopes, standard=standard)
        nested = _batch(payload, key, scopes, standard=standard) if payload["action"] == "multi" else None
        cost = max(1, len(nested)) if nested is not None else 1
        for rate_key, setting, default in ((f"token:{token.id}", "CONNECT_TOKEN_RATE_LIMIT", 60), (f"user:{user.id}", "CONNECT_USER_RATE_LIMIT", 120)):
            if not rate_allowed(rate_key, setting, default, cost=cost):
                uow.rollback()
                return respond(error="rate limit exceeded", status=429)
        action = payload["action"]
        setting = {"addNote": ("add", "CONNECT_ADD_NOTE_RATE_LIMIT"), "storeMediaFile": ("media", "CONNECT_MEDIA_RATE_LIMIT")}.get(action)
        if setting and not rate_allowed(f"{setting[0]}:{user.id}", setting[1], 20):
            uow.rollback()
            return respond(error="rate limit exceeded", status=429)
        if nested is not None:
            result = []
            for item in nested:
                try:
                    value = service.dispatch(user.id, item["action"], item["params"], standard=standard, uow=uow, scopes=scopes)
                    result.append(encode_result(value, version=item["version"], versioned=standard))
                except service.ConnectError as exc:
                    result.append(encode_result(error=str(exc)))
        else:
            result = service.dispatch(user.id, action, payload["params"], standard=standard, uow=uow, scopes=scopes)
        uow.commit()
        logger.info("Connect action succeeded user_id=%s action=%s", user.id, action)
        return respond(result=result)
    except RequestEntityTooLarge:
        uow.rollback()
        return respond(error="request body is too large", status=413)
    except (ProtocolError, service.ConnectError) as exc:
        uow.rollback()
        denied = str(exc).startswith("permission denied")
        return respond(error=str(exc), status=403 if standard and denied else 200)
    except SharedStateUnavailable:
        uow.rollback()
        return respond(error="service temporarily unavailable", status=503)
    except Exception as exc:
        uow.rollback()
        # ORM exception strings can contain field values or query parameters.
        logger.error("Connect action failed category=%s", type(exc).__name__)
        return respond(error="internal error", status=500 if standard else 200)
