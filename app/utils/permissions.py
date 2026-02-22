"""Permission helpers."""


def is_admin_user(user) -> bool:
    """Return True when the authenticated user has admin capability."""
    if not user:
        return False
    return bool(getattr(user, "is_admin", False))

