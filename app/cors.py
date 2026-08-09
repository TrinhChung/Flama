"""Exact-origin CORS support for the separately deployed React frontend."""

from __future__ import annotations

from collections.abc import Iterable

from flask import request

_ALLOWED_HEADERS = (
    "Authorization, Content-Type, Content-Encoding, X-CSRF-Token, "
    "X-CSRFToken, X-Package-SHA256"
)
_ALLOWED_METHODS = "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS"
_EXPOSED_HEADERS = "Content-Disposition, X-VoiceVox-Warnings"


def _normalized_origins(values: Iterable[str]) -> frozenset[str]:
    return frozenset(
        origin
        for value in values
        if (origin := str(value or "").strip().rstrip("/"))
    )


def init_cors(app) -> None:
    """Allow credentialed requests from explicitly configured frontend origins."""

    @app.after_request
    def apply_cors_headers(response):
        request_origin = str(request.headers.get("Origin") or "").strip().rstrip("/")
        allowed_origins = _normalized_origins(
            app.config.get("CORS_ALLOWED_ORIGINS", ())
        )
        if not request_origin or request_origin not in allowed_origins:
            return response

        response.headers["Access-Control-Allow-Origin"] = request_origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = _ALLOWED_HEADERS
        response.headers["Access-Control-Allow-Methods"] = _ALLOWED_METHODS
        response.headers["Access-Control-Expose-Headers"] = _EXPOSED_HEADERS
        response.vary.add("Origin")
        return response
