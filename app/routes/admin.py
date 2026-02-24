"""Admin-only user management routes."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.utils.permissions import is_admin_user
from models import db
from models.user import User
from models.user_permission_audit_log import UserPermissionAuditLog
from models.user_role import UserRole

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50
VALID_STATUS_FILTERS = {"all", "active", "disabled"}


def _coerce_int(value: Any, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed < minimum:
        return default
    if maximum is not None and parsed > maximum:
        return maximum
    return parsed


def _normalize_status_filter(value: str | None) -> str:
    normalized = (value or "all").strip().lower()
    if normalized not in VALID_STATUS_FILTERS:
        return "all"
    return normalized


def _parse_user_ids(raw_ids: str | None) -> list[int]:
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


def _parse_user_ids_payload(payload: dict[str, Any]) -> list[int]:
    user_ids = payload.get("user_ids", [])
    parsed: list[int] = []
    seen: set[int] = set()

    if isinstance(user_ids, str):
        return _parse_user_ids(user_ids)

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


def _resolve_account_name(user: User) -> str:
    if not user.email:
        return ""
    account_name = user.email.split("@", 1)[0].strip()
    if not account_name:
        return ""
    if account_name.lower() == (user.username or "").strip().lower():
        return ""
    return account_name


def _build_users_query(search_term: str, status_filter: str):
    query = User.query.options(selectinload(User.role))
    if search_term:
        like_pattern = f"%{search_term}%"
        query = query.filter(or_(User.username.ilike(like_pattern), User.email.ilike(like_pattern)))

    if status_filter == "active":
        query = query.filter(User.is_disabled.is_(False))
    elif status_filter == "disabled":
        query = query.filter(User.is_disabled.is_(True))

    return query.order_by(User.created_at.asc(), User.id.asc())


def _load_user_summary() -> dict[str, int]:
    total_users = User.query.count()
    disabled_users = User.query.filter(User.is_disabled.is_(True)).count()
    return {
        "total_users": total_users,
        "active_users": max(total_users - disabled_users, 0),
        "disabled_users": disabled_users,
    }


def _serialize_user_row(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "account_name": _resolve_account_name(user),
        "email": user.email,
        "status": "disabled" if user.is_disabled else "active",
        "is_disabled": bool(user.is_disabled),
        "is_admin": bool(user.is_admin),
        "role_id": user.role_id,
        "role_name": user.role.name if user.role else None,
    }


def _append_audit_log(
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


def _ensure_admin_access():
    if is_admin_user(current_user):
        return None
    flash("Ban khong co quyen truy cap trang quan ly user.", "warning")
    return redirect(url_for("main.dashboard"))


@admin_bp.route("/users", methods=["GET"])
@login_required
def user_management_page():
    guard = _ensure_admin_access()
    if guard is not None:
        return guard

    search_term = (request.args.get("q") or "").strip()
    status_filter = _normalize_status_filter(request.args.get("status"))
    page = _coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = _coerce_int(request.args.get("per_page"), default=DEFAULT_PAGE_SIZE, minimum=1, maximum=MAX_PAGE_SIZE)
    selected_ids = _parse_user_ids(request.args.get("selected_ids"))

    template_context: dict[str, Any] = {
        "search_term": search_term,
        "status_filter": status_filter,
        "page": page,
        "per_page": per_page,
        "selected_ids": selected_ids,
        "selected_ids_csv": ",".join(str(user_id) for user_id in selected_ids),
        "users": [],
        "pagination_total": 0,
        "total_pages": 1,
        "has_error": False,
        "error_message": "",
        **_load_user_summary(),
    }

    try:
        query = _build_users_query(search_term=search_term, status_filter=status_filter)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        template_context["users"] = pagination.items
        template_context["pagination_total"] = pagination.total
        template_context["total_pages"] = max(pagination.pages, 1)
        template_context["page"] = pagination.page
    except SQLAlchemyError:
        template_context["has_error"] = True
        template_context["error_message"] = "Khong the tai danh sach nguoi dung. Vui long thu lai."

    return render_template("admin/users.html", **template_context)


@admin_bp.route("/users/permissions", methods=["GET"])
@login_required
def permission_assignment_page():
    guard = _ensure_admin_access()
    if guard is not None:
        return guard

    selected_ids = _parse_user_ids(request.args.get("user_ids") or request.args.get("selected_ids"))
    if not selected_ids:
        flash("Hay chon it nhat 1 user de chinh quyen.", "warning")
        return redirect(url_for("admin.user_management_page"))

    users = (
        User.query.options(selectinload(User.role))
        .filter(User.id.in_(selected_ids))
        .order_by(User.username.asc(), User.id.asc())
        .all()
    )
    roles = UserRole.query.order_by(UserRole.position.asc(), UserRole.id.asc()).all()
    active_admin_count = User.query.filter(User.is_admin.is_(True), User.is_disabled.is_(False)).count()

    if not users:
        flash("Khong tim thay user hop le de chinh quyen.", "warning")
        return redirect(url_for("admin.user_management_page"))

    return render_template(
        "admin/permission_assignment.html",
        users=users,
        selected_ids=[user.id for user in users],
        selected_ids_csv=",".join(str(user.id) for user in users),
        roles=roles,
        active_admin_count=active_admin_count,
        current_user_id=current_user.id,
        current_user_is_admin=bool(is_admin_user(current_user)),
    )


def _batch_assign_roles(*, user_ids: list[int], target_role: UserRole) -> tuple[int, int, list[dict[str, Any]]]:
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
            user.id == current_user.id
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

        _append_audit_log(
            actor_user_id=current_user.id,
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

    return success_count, fail_count, results


def _batch_update_status(*, user_ids: list[int], action: str) -> tuple[int, int, list[dict[str, Any]]]:
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

        if target_disabled and user.id == current_user.id:
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

        _append_audit_log(
            actor_user_id=current_user.id,
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

    return success_count, fail_count, results


@admin_bp.route("/api/users", methods=["GET"])
@login_required
def list_users_api():
    if not is_admin_user(current_user):
        return jsonify({"message": "Unauthorized"}), 403

    search_term = (request.args.get("q") or "").strip()
    status_filter = _normalize_status_filter(request.args.get("status"))
    page = _coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = _coerce_int(request.args.get("per_page"), default=DEFAULT_PAGE_SIZE, minimum=1, maximum=MAX_PAGE_SIZE)

    query = _build_users_query(search_term=search_term, status_filter=status_filter)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    summary = _load_user_summary()
    return jsonify(
        {
            "items": [_serialize_user_row(user) for user in pagination.items],
            "page": pagination.page,
            "per_page": per_page,
            "total": pagination.total,
            "total_pages": max(pagination.pages, 1),
            "summary": summary,
        }
    )


@admin_bp.route("/api/users/roles/batch", methods=["POST"])
@login_required
def batch_assign_role_api():
    if not is_admin_user(current_user):
        return jsonify({"message": "Unauthorized"}), 403

    payload = request.get_json(silent=True) or {}
    user_ids = _parse_user_ids_payload(payload)
    role_id = _coerce_int(payload.get("target_role_id"), default=0, minimum=1)
    mode = (payload.get("mode") or "replace").strip().lower()

    if not user_ids:
        return jsonify({"message": "Danh sach user_ids khong hop le.", "results": []}), 400
    if mode != "replace":
        return jsonify({"message": "He thong role hien tai chi ho tro mode 'replace'.", "results": []}), 400

    role = UserRole.query.get(role_id)
    if role is None:
        return jsonify({"message": "Khong tim thay role.", "results": []}), 404

    try:
        success_count, fail_count, results = _batch_assign_roles(user_ids=user_ids, target_role=role)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"message": "Khong the cap nhat role. Vui long thu lai.", "results": []}), 500

    return jsonify(
        {
            "message": "Batch role assignment completed.",
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results,
        }
    )


@admin_bp.route("/api/users/status/batch", methods=["POST"])
@login_required
def batch_update_status_api():
    if not is_admin_user(current_user):
        return jsonify({"message": "Unauthorized"}), 403

    payload = request.get_json(silent=True) or {}
    user_ids = _parse_user_ids_payload(payload)
    action = (payload.get("action") or "").strip().lower()

    if not user_ids:
        return jsonify({"message": "Danh sach user_ids khong hop le.", "results": []}), 400
    if action not in {"activate", "disable"}:
        return jsonify({"message": "Action phai la 'activate' hoac 'disable'.", "results": []}), 400

    try:
        success_count, fail_count, results = _batch_update_status(user_ids=user_ids, action=action)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"message": "Khong the cap nhat trang thai user. Vui long thu lai.", "results": []}), 500

    return jsonify(
        {
            "message": "Batch status update completed.",
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results,
        }
    )


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
def update_user_role(user_id: int):
    """Backward-compatible single-user role update endpoint."""
    if not is_admin_user(current_user):
        flash("Ban khong co quyen cap nhat quyen user.", "warning")
        return redirect(url_for("main.dashboard"))

    role_id_raw = (request.form.get("role_id") or "").strip()
    if not role_id_raw.isdigit():
        flash("Role khong hop le.", "danger")
        return redirect(url_for("admin.user_management_page"))

    role = UserRole.query.get(int(role_id_raw))
    if role is None:
        flash("Khong tim thay role.", "danger")
        return redirect(url_for("admin.user_management_page"))

    try:
        success_count, fail_count, _ = _batch_assign_roles(user_ids=[user_id], target_role=role)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Khong the cap nhat quyen user.", "danger")
        return redirect(url_for("admin.user_management_page"))

    if success_count > 0 and fail_count == 0:
        flash("Da cap nhat quyen user thanh cong.", "success")
    else:
        flash("Khong the cap nhat quyen user.", "danger")
    return redirect(url_for("admin.user_management_page"))
