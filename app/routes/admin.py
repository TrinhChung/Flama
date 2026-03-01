"""Admin-only user management routes."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.utils.permissions import is_admin_user
from app.services import admin_service

from models import db
from models.user import User
from models.user_permission_audit_log import UserPermissionAuditLog
from models.user_role import UserRole

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50



















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
    status_filter = admin_service.normalize_status_filter(request.args.get("status"))
    page = admin_service.coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = admin_service.coerce_int(request.args.get("per_page"), default=DEFAULT_PAGE_SIZE, minimum=1, maximum=MAX_PAGE_SIZE)
    selected_ids = admin_service.parse_user_ids(request.args.get("selected_ids"))

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
        **admin_service.load_user_summary(),
    }

    try:
        query = admin_service.build_users_query(search_term=search_term, status_filter=status_filter)
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

    selected_ids = admin_service.parse_user_ids(request.args.get("user_ids") or request.args.get("selected_ids"))
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






@admin_bp.route("/api/users", methods=["GET"])
@login_required
def list_users_api():
    if not is_admin_user(current_user):
        return jsonify({"message": "Unauthorized"}), 403

    search_term = (request.args.get("q") or "").strip()
    status_filter = admin_service.normalize_status_filter(request.args.get("status"))
    page = admin_service.coerce_int(request.args.get("page"), default=1, minimum=1)
    per_page = admin_service.coerce_int(request.args.get("per_page"), default=DEFAULT_PAGE_SIZE, minimum=1, maximum=MAX_PAGE_SIZE)

    query = admin_service.build_users_query(search_term=search_term, status_filter=status_filter)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    summary = admin_service.load_user_summary()
    return jsonify(
        {
            "items": [admin_service.serialize_user_row(user) for user in pagination.items],
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
    user_ids = admin_service.parse_user_ids_payload(payload)
    role_id = admin_service.coerce_int(payload.get("target_role_id"), default=0, minimum=1)
    mode = (payload.get("mode") or "replace").strip().lower()

    if not user_ids:
        return jsonify({"message": "Danh sach user_ids khong hop le.", "results": []}), 400
    if mode != "replace":
        return jsonify({"message": "He thong role hien tai chi ho tro mode 'replace'.", "results": []}), 400

    role = UserRole.query.get(role_id)
    if role is None:
        return jsonify({"message": "Khong tim thay role.", "results": []}), 404

    try:
        success_count, fail_count, results = admin_service.batch_assign_roles(actor_user_id=current_user.id, user_ids=user_ids, target_role=role)
    except SQLAlchemyError:
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
    user_ids = admin_service.parse_user_ids_payload(payload)
    action = (payload.get("action") or "").strip().lower()

    if not user_ids:
        return jsonify({"message": "Danh sach user_ids khong hop le.", "results": []}), 400
    if action not in {"activate", "disable"}:
        return jsonify({"message": "Action phai la 'activate' hoac 'disable'.", "results": []}), 400

    try:
        success_count, fail_count, results = admin_service.batch_update_status(actor_user_id=current_user.id, user_ids=user_ids, action=action)
    except SQLAlchemyError:
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
        success_count, fail_count, _ = admin_service.batch_assign_roles(actor_user_id=current_user.id, user_ids=[user_id], target_role=role)
    except SQLAlchemyError:
        flash("Khong the cap nhat quyen user.", "danger")
        return redirect(url_for("admin.user_management_page"))

    if success_count > 0 and fail_count == 0:
        flash("Da cap nhat quyen user thanh cong.", "success")
    else:
        flash("Khong the cap nhat quyen user.", "danger")
    return redirect(url_for("admin.user_management_page"))
