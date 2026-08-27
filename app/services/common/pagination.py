"""Cursor-based pagination helpers extracted from service layer duplicates.

The ``encode_cursor`` / ``decode_cursor`` pair is used by deck change requests,
deck releases, and marketplace queries.  ``coerce_page_limit`` normalises
``limit`` query parameters across all paginated endpoints.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from app.services.common.datetime_utils import stable_json


# ---------------------------------------------------------------------------
# Cursor encode / decode
# ---------------------------------------------------------------------------


def encode_cursor(payload: dict[str, Any]) -> str:
    """Encode a cursor payload as a URL-safe base64 string (no padding)."""
    raw = stable_json(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(
    raw_cursor: str | None,
    *,
    expected_kind: str,
) -> dict[str, Any] | None:
    """Decode a cursor string, validating its ``kind`` field.

    Returns ``None`` for empty / None input.
    Raises ``ValueError`` on malformed or kind-mismatched cursors.
    """
    normalized = str(raw_cursor or "").strip()
    if not normalized:
        return None
    try:
        padded = normalized + "=" * (-len(normalized) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        )
        if not isinstance(payload, dict) or payload.get("kind") != expected_kind:
            raise ValueError("cursor kind mismatch")
        return payload
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        raise ValueError("cursor is invalid.")


# ---------------------------------------------------------------------------
# Page limit coercion
# ---------------------------------------------------------------------------


def coerce_page_limit(
    raw_limit: Any,
    *,
    default: int,
    maximum: int,
) -> int:
    """Normalise a raw ``limit`` parameter to a bounded integer.

    Returns *default* for ``None`` / empty values.
    Raises ``ValueError`` when the value is non-integer or out of range.
    """
    if raw_limit is None or str(raw_limit).strip() == "":
        return default
    try:
        value = int(raw_limit)
    except (TypeError, ValueError):
        raise ValueError("limit must be an integer.")
    if value < 1 or value > maximum:
        raise ValueError(f"limit must be between 1 and {maximum}.")
    return value
