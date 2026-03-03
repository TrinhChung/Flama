"""Authentication service logic and transaction boundaries."""

from __future__ import annotations

from app.services.user_roles import ensure_default_user_roles
from models import db
from models.user import User

def register_user_and_commit(email: str, username: str, password: str) -> None:
    existing_user_count = User.query.count()
    roles = ensure_default_user_roles(db.session)
    user = User(email=email, username=username)
    if existing_user_count == 0 and roles.get("admin"):
        user.role_id = roles["admin"].id
        user.is_admin = True
    elif roles.get("regular"):
        user.role_id = roles["regular"].id
        user.is_admin = bool(roles["regular"].is_admin)
    else:
        user.is_admin = existing_user_count == 0
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
