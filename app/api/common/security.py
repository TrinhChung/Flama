"""Authentication and authorization decorators for versioned APIs."""

from __future__ import annotations

from functools import wraps

from flask_login import current_user, login_required

from app.utils.permissions import is_admin_user, is_creator_user

from .responses import error_response


def admin_required(view):
    """Require an authenticated administrator and keep failures JSON-shaped."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not is_admin_user(current_user):
            return error_response(
                "FORBIDDEN",
                "Administrator access is required.",
                status=403,
            )
        return view(*args, **kwargs)

    return wrapped


def creator_required(view):
    """Require an authenticated creator or administrator."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not is_creator_user(current_user):
            return error_response(
                "FORBIDDEN",
                "Creator access is required.",
                status=403,
            )
        return view(*args, **kwargs)

    return wrapped
