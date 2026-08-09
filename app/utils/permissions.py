"""Permission helpers."""


def is_admin_user(user) -> bool:
    """Return True when the authenticated user has admin capability."""
    if not user:
        return False
    role = getattr(user, "role", None)
    if role is not None and hasattr(role, "is_admin"):
        return bool(role.is_admin)
    return bool(getattr(user, "is_admin", False))


def is_creator_user(user) -> bool:
    """Return True when the user can access creator-only features."""
    if is_admin_user(user):
        return True
    role = getattr(user, "role", None)
    return str(getattr(role, "code", "") or "").strip().lower() == "creator"
