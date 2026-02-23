"""Permission helpers."""


def is_admin_user(user) -> bool:
    """Return True when the authenticated user has admin capability."""
    if not user:
        return False
    role = getattr(user, "role", None)
    if role is not None and hasattr(role, "is_admin"):
        return bool(role.is_admin)
    return bool(getattr(user, "is_admin", False))
