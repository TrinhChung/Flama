"""Application service for administrative user REST resources."""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.services import admin_service
from models import db
from models.user import User
from models.user_role import UserRole


class AdminUserApiError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int,
        field: str | None = None,
        extras: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.field = field
        self.extras = extras or {}


def list_users(
    *,
    search_term: str,
    status_filter: str,
    page: int,
    per_page: int,
) -> dict[str, Any]:
    pagination = admin_service.build_users_query(
        search_term=search_term,
        status_filter=status_filter,
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    roles = UserRole.query.order_by(
        UserRole.position.asc(),
        UserRole.id.asc(),
    ).all()
    return {
        "items": [
            admin_service.serialize_user_row(user)
            for user in pagination.items
        ],
        "page": pagination.page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": max(pagination.pages, 1),
        "summary": admin_service.load_user_summary(),
        "filters": {
            "q": search_term,
            "status": status_filter,
        },
        "roles": [_serialize_role(role) for role in roles],
    }


def update_user(
    *,
    actor_user_id: int,
    user_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    user = db.session.get(User, user_id)
    if user is None:
        raise AdminUserApiError(
            "NOT_FOUND",
            "User not found.",
            status=404,
        )
    fields_present = {
        field_name
        for field_name in ("role_id", "is_disabled")
        if field_name in payload
    }
    if len(fields_present) != 1:
        raise AdminUserApiError(
            "VALIDATION_ERROR",
            "Provide exactly one of role_id or is_disabled.",
            status=400,
        )

    result_rows: list[dict[str, Any]] = []
    if "role_id" in payload:
        try:
            role_id = int(payload.get("role_id"))
        except (TypeError, ValueError) as exc:
            raise AdminUserApiError(
                "VALIDATION_ERROR",
                "role_id must be an integer.",
                status=400,
                field="role_id",
            ) from exc
        target_role = _get_role(role_id)
        _, fail_count, rows = _assign_roles(
            actor_user_id=actor_user_id,
            user_ids=[user_id],
            target_role=target_role,
        )
        result_rows.extend(rows)
        if fail_count:
            raise AdminUserApiError(
                "UPDATE_REJECTED",
                rows[0]["message"],
                status=409,
                extras={"results": result_rows},
            )

    if "is_disabled" in payload:
        raw_disabled = payload.get("is_disabled")
        if not isinstance(raw_disabled, bool):
            raise AdminUserApiError(
                "VALIDATION_ERROR",
                "is_disabled must be a boolean.",
                status=400,
                field="is_disabled",
            )
        _, fail_count, rows = _update_status(
            actor_user_id=actor_user_id,
            user_ids=[user_id],
            action="disable" if raw_disabled else "activate",
        )
        result_rows.extend(rows)
        if fail_count:
            raise AdminUserApiError(
                "UPDATE_REJECTED",
                rows[0]["message"],
                status=409,
                extras={"results": result_rows},
            )

    return {
        "item": admin_service.serialize_user_row(
            db.session.get(User, user_id)
        ),
        "results": result_rows,
    }


def batch_assign_roles(
    *,
    actor_user_id: int,
    user_ids: list[int],
    role_id: int,
) -> tuple[int, int, list[dict[str, Any]]]:
    return _assign_roles(
        actor_user_id=actor_user_id,
        user_ids=user_ids,
        target_role=_get_role(role_id),
    )


def batch_update_status(
    *,
    actor_user_id: int,
    user_ids: list[int],
    action: str,
) -> tuple[int, int, list[dict[str, Any]]]:
    return _update_status(
        actor_user_id=actor_user_id,
        user_ids=user_ids,
        action=action,
    )


def _get_role(role_id: int) -> UserRole:
    role = db.session.get(UserRole, role_id)
    if role is None:
        raise AdminUserApiError(
            "NOT_FOUND",
            "Role not found.",
            status=404,
        )
    return role


def _assign_roles(
    *,
    actor_user_id: int,
    user_ids: list[int],
    target_role: UserRole,
) -> tuple[int, int, list[dict[str, Any]]]:
    try:
        return admin_service.batch_assign_roles(
            actor_user_id=actor_user_id,
            user_ids=user_ids,
            target_role=target_role,
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise AdminUserApiError(
            "DB_ERROR",
            "Could not update user roles.",
            status=500,
        ) from exc


def _update_status(
    *,
    actor_user_id: int,
    user_ids: list[int],
    action: str,
) -> tuple[int, int, list[dict[str, Any]]]:
    try:
        return admin_service.batch_update_status(
            actor_user_id=actor_user_id,
            user_ids=user_ids,
            action=action,
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise AdminUserApiError(
            "DB_ERROR",
            "Could not update user status.",
            status=500,
        ) from exc


def _serialize_role(role: UserRole) -> dict[str, Any]:
    return {
        "id": int(role.id),
        "code": str(role.code or ""),
        "name": str(role.name or ""),
        "description": str(role.description or ""),
        "is_admin": bool(role.is_admin),
        "position": int(role.position or 0),
    }
