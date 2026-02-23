"""Helpers for issuing and resolving temporary move identifiers for decks."""

from __future__ import annotations

from flask import current_app
from itsdangerous import BadSignature, BadTimeSignature, SignatureExpired, URLSafeTimedSerializer

MOVE_TOKEN_SALT = "deck-move-token-v1"
MOVE_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 4


def _serializer() -> URLSafeTimedSerializer:
    secret_key = str(current_app.config.get("SECRET_KEY") or "")
    return URLSafeTimedSerializer(secret_key=secret_key, salt=MOVE_TOKEN_SALT)


def create_deck_move_token(deck_id: int, user_id: int) -> str:
    """Create a signed temporary token for deck move operations."""
    payload = {"deck_id": int(deck_id), "user_id": int(user_id)}
    return _serializer().dumps(payload)


def parse_deck_move_token(
    token: str | None,
    *,
    user_id: int,
    max_age_seconds: int = MOVE_TOKEN_MAX_AGE_SECONDS,
) -> int | None:
    """Resolve a temporary deck move token into a deck id for the same user."""
    if not token:
        return None
    serializer = _serializer()
    try:
        payload = serializer.loads(token, max_age=max_age_seconds)
    except (BadSignature, BadTimeSignature, SignatureExpired):
        return None

    if not isinstance(payload, dict):
        return None

    token_user_id = payload.get("user_id")
    token_deck_id = payload.get("deck_id")
    try:
        if int(token_user_id) != int(user_id):
            return None
        deck_id = int(token_deck_id)
    except (TypeError, ValueError):
        return None

    return deck_id if deck_id > 0 else None
