"""Admin domain service logic."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from models import db
from models.user import User
from models.user_permission_audit_log import UserPermissionAuditLog
from models.user_role import UserRole

def commit_transaction() -> None:
    db.session.commit()

def rollback_transaction() -> None:
    db.session.rollback()

VALID_STATUS_FILTERS = {"all", "active", "disabled"}

def coerce_int(value: Any, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return default
    if maximum is not None and parsed > maximum:
        return maximum
    return parsed

def normalize_status_filter(value: str | None) -> str:
    normalized = (value or "all").strip().lower()
    if normalized not in VALID_STATUS_FILTERS:
        return "all"
    return normalized

def parse_user_ids(raw_ids: str | None) -> list[int]:
    if not raw_ids:
        return []
    parsed: list[int] = []
    seen: set[int] = set()
    for part in raw_ids.split(","):
        token = part.strip()
        if not token.isdigit():
            continue
        user_id = int(token)
        if user_id <= 0 or user_id in seen:
            continue
        parsed.append(user_id)
        seen.add(user_id)
    return parsed

def parse_user_ids_payload(payload: dict[str, Any]) -> list[int]:
    user_ids = payload.get("user_ids", [])
    parsed: list[int] = []
    seen: set[int] = set()

    if isinstance(user_ids, str):
        return parse_user_ids(user_ids)

    if not isinstance(user_ids, list):
        return []

    for item in user_ids:
        if isinstance(item, int) and item > 0 and item not in seen:
            parsed.append(item)
            seen.add(item)
            continue
        if isinstance(item, str) and item.isdigit():
            user_id = int(item)
            if user_id > 0 and user_id not in seen:
                parsed.append(user_id)
                seen.add(user_id)
    return parsed

def resolve_account_name(user: User) -> str:
    if not user.email:
        return ""
    account_name = user.email.split("@", 1)[0].strip()
    if not account_name:
        return ""
    if account_name.lower() == (user.username or "").strip().lower():
        return ""
    return account_name

def build_users_query(search_term: str, status_filter: str):
    query = User.query.options(selectinload(User.role))
    if search_term:
        like_pattern = f"%{search_term}%"
        query = query.filter(or_(User.username.ilike(like_pattern), User.email.ilike(like_pattern)))

    if status_filter == "active":
        query = query.filter(User.is_disabled.is_(False))
    elif status_filter == "disabled":
        query = query.filter(User.is_disabled.is_(True))

    return query.order_by(User.created_at.asc(), User.id.asc())

def load_user_summary() -> dict[str, int]:
    total_users = User.query.count()
    disabled_users = User.query.filter(User.is_disabled.is_(True)).count()
    return {
        "total_users": total_users,
        "active_users": max(total_users - disabled_users, 0),
        "disabled_users": disabled_users,
    }

def serialize_user_row(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "account_name": resolve_account_name(user),
        "email": user.email,
        "status": "disabled" if user.is_disabled else "active",
        "is_disabled": bool(user.is_disabled),
        "is_admin": bool(user.is_admin),
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else None,
    }

def append_audit_log(
    *,
    actor_user_id: int,
    target_user_id: int,
    action: str,
    from_role_id: int | None,
    to_role_id: int | None,
    from_is_admin: bool,
    to_is_admin: bool,
    from_is_disabled: bool,
    to_is_disabled: bool,
    message: str,
) -> None:
    db.session.add(
        UserPermissionAuditLog(
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            action=action,
            from_role_id=from_role_id,
            to_role_id=to_role_id,
            from_is_admin=bool(from_is_admin),
            to_is_admin=bool(to_is_admin),
            from_is_disabled=bool(from_is_disabled),
            to_is_disabled=bool(to_is_disabled),
            message=message,
        )
    )

def batch_assign_roles(*, actor_user_id: int, user_ids: list[int], target_role: UserRole) -> tuple[int, int, list[dict[str, Any]]]:
    if not user_ids:
        return 0, 0, []

    users = (
        User.query.options(selectinload(User.role))
        .filter(User.id.in_(user_ids))
        .all()
    )
    user_by_id = {user.id: user for user in users}

    active_admin_count = User.query.filter(User.is_admin.is_(True), User.is_disabled.is_(False)).count()
    demoted_admin_ids = {
        user.id
        for user in users
        if user.is_admin and (not user.is_disabled) and (not bool(target_role.is_admin))
    }

    blocked_last_admin_ids: set[int] = set()
    if demoted_admin_ids and active_admin_count - len(demoted_admin_ids) < 1:
        blocked_last_admin_ids = set(demoted_admin_ids)

    success_count = 0
    fail_count = 0
    results: list[dict[str, Any]] = []

    try:
        for user_id in user_ids:
            user = user_by_id.get(user_id)
            if user is None:
                fail_count += 1
                results.append(
                    {
                        "user_id": user_id,
                        "username": f"#{user_id}",
                        "email": None,
                        "status": "fail",
                        "message": "Khong tim thay user.",
                    }
                )
                continue

            if (
                user.id == actor_user_id
                and bool(user.is_admin)
                and not bool(target_role.is_admin)
            ):
                fail_count += 1
                results.append(
                    {
                        "user_id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "status": "fail",
                        "message": "Khong the tu ha quyen admin cua chinh minh.",
                    }
                )
                continue

            if user.id in blocked_last_admin_ids:
                fail_count += 1
                results.append(
                    {
                        "user_id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "status": "fail",
                        "message": "Khong the ha quyen admin cuoi cung dang hoat dong.",
                    }
                )
                continue

            from_role_id = user.role_id
            from_is_admin = bool(user.is_admin)
            from_is_disabled = bool(user.is_disabled)

            user.role_id = target_role.id
            user.is_admin = bool(target_role.is_admin)

            append_audit_log(
                actor_user_id=actor_user_id,
                target_user_id=user.id,
                action="assign_role",
                from_role_id=from_role_id,
                to_role_id=target_role.id,
                from_is_admin=from_is_admin,
                to_is_admin=bool(user.is_admin),
                from_is_disabled=from_is_disabled,
                to_is_disabled=from_is_disabled,
                message=f"Assign role -> {target_role.name}",
            )

            success_count += 1
            results.append(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "status": "success",
                    "message": f"Da cap nhat role -> {target_role.name}.",
                }
            )

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e

    return success_count, fail_count, results

def batch_update_status(*, actor_user_id: int, user_ids: list[int], action: str) -> tuple[int, int, list[dict[str, Any]]]:
    if not user_ids:
        return 0, 0, []

    target_disabled = action == "disable"
    users = User.query.options(selectinload(User.role)).filter(User.id.in_(user_ids)).all()
    user_by_id = {user.id: user for user in users}

    blocked_last_admin_ids: set[int] = set()
    if target_disabled:
        active_admin_count = User.query.filter(User.is_admin.is_(True), User.is_disabled.is_(False)).count()
        disabled_admin_ids = {
            user.id for user in users if user.is_admin and not user.is_disabled
        }
        if disabled_admin_ids and active_admin_count - len(disabled_admin_ids) < 1:
            blocked_last_admin_ids = set(disabled_admin_ids)

    success_count = 0
    fail_count = 0
    results: list[dict[str, Any]] = []

    try:
        for user_id in user_ids:
            user = user_by_id.get(user_id)
            if user is None:
                fail_count += 1
                results.append(
                    {
                        "user_id": user_id,
                        "username": f"#{user_id}",
                        "email": None,
                        "status": "fail",
                        "message": "Khong tim thay user.",
                    }
                )
                continue

            if target_disabled and user.id == actor_user_id:
                fail_count += 1
                results.append(
                    {
                        "user_id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "status": "fail",
                        "message": "Khong the vo hieu hoa chinh tai khoan dang dang nhap.",
                    }
                )
                continue

            if target_disabled and user.id in blocked_last_admin_ids:
                fail_count += 1
                results.append(
                    {
                        "user_id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "status": "fail",
                        "message": "Khong the vo hieu hoa admin cuoi cung dang hoat dong.",
                    }
                )
                continue

            from_role_id = user.role_id
            from_is_admin = bool(user.is_admin)
            from_is_disabled = bool(user.is_disabled)
            to_is_disabled = target_disabled
            user.is_disabled = to_is_disabled

            append_audit_log(
                actor_user_id=actor_user_id,
                target_user_id=user.id,
                action="disable_user" if target_disabled else "activate_user",
                from_role_id=from_role_id,
                to_role_id=from_role_id,
                from_is_admin=from_is_admin,
                to_is_admin=from_is_admin,
                from_is_disabled=from_is_disabled,
                to_is_disabled=to_is_disabled,
                message="Disable user" if target_disabled else "Activate user",
            )

            success_count += 1
            results.append(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "status": "success",
                    "message": "Da vo hieu hoa." if target_disabled else "Da kich hoat.",
                }
            )

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e

    return success_count, fail_count, results
