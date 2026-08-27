"""Common datetime helpers extracted from repeated patterns across service layer.

Previously each service file had its own private ``_utcnow()`` (12 copies),
``_utc_iso()``, ``_parse_utc_iso()``, ``_stable_json()``, and ``_json_dumps()``.
This module provides a single canonical implementation for each.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


UTC = timezone.utc


def utcnow() -> datetime:
    """Return a timezone-naive ``datetime`` representing the current UTC time.

    Uses ``datetime.now(UTC).replace(tzinfo=None)`` — the recommended
    replacement for the deprecated ``datetime.utcnow()``.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def utc_iso(moment: datetime | None) -> str | None:
    """Format a datetime as an ISO-8601 UTC string with ``Z`` suffix.

    If *moment* is timezone-aware it is first converted to UTC.
    Returns ``None`` when *moment* is ``None``.
    """
    if moment is None:
        return None
    value = moment
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return f"{value.isoformat(timespec='milliseconds')}Z"


def parse_utc_iso(value: Any) -> datetime | None:
    """Parse an ISO-8601 string into a timezone-naive UTC datetime.

    Accepts trailing ``Z`` and ``+00:00`` variants.  Returns ``None`` for
    falsy or empty input.  Raises ``ValueError`` on un-parseable input.
    """
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def stable_json(value: Any) -> str:
    """Deterministic JSON encoding for fingerprinting / comparison.

    Uses sorted keys, ASCII-safe, compact separators.
    """
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )


def compact_json(payload: Any) -> str:
    """Compact JSON encoding preserving unicode and using ``str`` as default.

    Suitable for storing payloads where readability is secondary.
    """
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
