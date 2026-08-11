"""Lightweight CSRF protection for form posts and same-origin API calls."""

from __future__ import annotations

import hmac
import secrets

from flask import current_app, jsonify, request, session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
SESSION_TOKEN_KEY = "_csrf_token"


def init_csrf_protection(app) -> None:
    """Register CSRF helpers on the Flask app."""

    app.before_request(protect_from_csrf)


def csrf_enabled() -> bool:
    return bool(current_app.config.get("WTF_CSRF_ENABLED", True))


def generate_csrf_token() -> str:
    if not csrf_enabled():
        return ""
    token = str(session.get(SESSION_TOKEN_KEY) or "").strip()
    if token:
        return token
    token = secrets.token_urlsafe(32)
    session[SESSION_TOKEN_KEY] = token
    return token


def protect_from_csrf():
    if not csrf_enabled() or request.method in SAFE_METHODS:
        return None

    if _is_exempt_endpoint():
        return None

    auth_header = str(request.headers.get("Authorization") or "")
    if auth_header.startswith("Bearer "):
        return None

    session_token = str(session.get(SESSION_TOKEN_KEY) or "")
    request_token = _extract_request_token()
    if session_token and request_token and hmac.compare_digest(request_token, session_token):
        return None

    return _csrf_error_response()


def _is_exempt_endpoint() -> bool:
    exempt_endpoints = set(current_app.config.get("CSRF_EXEMPT_ENDPOINTS", ()))
    return (request.endpoint or "") in exempt_endpoints


def _extract_request_token() -> str:
    for header_name in ("X-CSRF-Token", "X-CSRFToken"):
        value = str(request.headers.get(header_name) or "").strip()
        if value:
            return value

    for field_name in ("_csrf_token", "csrf_token"):
        value = str(request.form.get(field_name) or "").strip()
        if value:
            return value

    if request.is_json:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            for field_name in ("_csrf_token", "csrf_token"):
                value = str(payload.get(field_name) or "").strip()
                if value:
                    return value

    return ""


def _csrf_error_response():
    message = "CSRF validation failed."
    return jsonify({"error": "CSRF_FAILED", "message": message}), 400
