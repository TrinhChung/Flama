"""Request parsing helpers shared by versioned API resources."""

from __future__ import annotations

from flask import request

from .responses import error_response


def json_object() -> dict | None:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else None


def optional_int_query(name: str):
    raw_value = str(request.args.get(name) or "").strip()
    if not raw_value:
        return None, None
    try:
        return int(raw_value), None
    except ValueError:
        return None, error_response(
            "VALIDATION_ERROR",
            f"{name} must be an integer.",
            status=400,
            field=name,
        )
