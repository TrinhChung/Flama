"""Stable response helpers shared by versioned APIs."""

from __future__ import annotations

from typing import Any

from flask import jsonify


def error_response(
    code: str,
    message: str,
    *,
    status: int,
    field: str | None = None,
    details: list[Any] | None = None,
):
    payload: dict[str, Any] = {
        "error": str(code or "REQUEST_FAILED"),
        "message": str(message or "Request failed."),
    }
    if field:
        payload["field"] = field
    if details is not None:
        payload["details"] = details
    return jsonify(payload), int(status)
