"""Shared password policy validators."""

from __future__ import annotations

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 255


def validate_password_policy(password: str) -> str | None:
    """Validate password against the shared length policy (8..255 characters).

    Returns an error message string if invalid, or None if valid.
    """
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must not exceed {MAX_PASSWORD_LENGTH} characters."
    return None
