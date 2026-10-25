"""Persistence helpers for quota policies and per-user overrides."""

from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.validators import escape_like_pattern
from models import db
from models.quota import QuotaPolicy, UserQuotaOverride
from models.user import User


def list_policies() -> list[QuotaPolicy]:
    return QuotaPolicy.query.all()


def get_policy(quota_kind: str) -> QuotaPolicy | None:
    return db.session.get(QuotaPolicy, quota_kind)


def add_policy(policy: QuotaPolicy) -> QuotaPolicy:
    db.session.add(policy)
    return policy


def list_overrides_for_user(user_id: int) -> list[UserQuotaOverride]:
    # Primary-key prefix lookup on (user_id, quota_kind).
    return UserQuotaOverride.query.filter(UserQuotaOverride.user_id == int(user_id)).all()


def get_override(*, user_id: int, quota_kind: str) -> UserQuotaOverride | None:
    return db.session.get(UserQuotaOverride, (int(user_id), quota_kind))


def add_override(row: UserQuotaOverride) -> UserQuotaOverride:
    db.session.add(row)
    return row


def delete_override(row: UserQuotaOverride) -> None:
    db.session.delete(row)


def list_all_overrides() -> list[UserQuotaOverride]:
    # The table holds at most a few rows per granted user, so a scan is cheap.
    return UserQuotaOverride.query.order_by(
        UserQuotaOverride.user_id.asc(), UserQuotaOverride.quota_kind.asc()
    ).all()


def get_users_by_ids(user_ids: list[int]) -> dict[int, User]:
    if not user_ids:
        return {}
    users = (
        User.query.options(selectinload(User.role))
        .filter(User.id.in_(sorted(set(int(uid) for uid in user_ids))))
        .all()
    )
    return {int(user.id): user for user in users}


def search_users(*, query_text: str, limit: int) -> list[User]:
    like_pattern = f"%{escape_like_pattern(query_text)}%"
    return (
        User.query.options(selectinload(User.role))
        .filter(
            or_(
                User.username.ilike(like_pattern, escape="\\"),
                User.email.ilike(like_pattern, escape="\\"),
                User.display_name.ilike(like_pattern, escape="\\"),
            )
        )
        .order_by(User.id.asc())
        .limit(limit)
        .all()
    )
