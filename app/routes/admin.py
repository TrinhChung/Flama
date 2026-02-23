"""Admin-only user management routes."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from app.utils.permissions import is_admin_user
from models import db
from models.user import User
from models.user_role import UserRole

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users", methods=["GET"])
@login_required
def user_management_page():
    if not is_admin_user(current_user):
        flash("Ban khong co quyen truy cap trang quan ly user.", "warning")
        return redirect(url_for("main.dashboard"))

    users = (
        User.query.options(selectinload(User.role))
        .order_by(User.created_at.asc(), User.id.asc())
        .all()
    )
    roles = UserRole.query.order_by(UserRole.position.asc(), UserRole.id.asc()).all()
    return render_template("admin/users.html", users=users, roles=roles)


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
def update_user_role(user_id: int):
    if not is_admin_user(current_user):
        flash("Ban khong co quyen cap nhat quyen user.", "warning")
        return redirect(url_for("main.dashboard"))

    role_id_raw = (request.form.get("role_id") or "").strip()
    if not role_id_raw.isdigit():
        flash("Role khong hop le.", "danger")
        return redirect(url_for("admin.user_management_page"))

    user = User.query.get(user_id)
    if user is None:
        flash("Khong tim thay user.", "danger")
        return redirect(url_for("admin.user_management_page"))

    role = UserRole.query.get(int(role_id_raw))
    if role is None:
        flash("Khong tim thay role.", "danger")
        return redirect(url_for("admin.user_management_page"))

    admin_count = User.query.filter_by(is_admin=True).count()
    demoting_admin = bool(user.is_admin) and not bool(role.is_admin)
    if demoting_admin and admin_count <= 1:
        flash("Khong the ha quyen admin cuoi cung.", "danger")
        return redirect(url_for("admin.user_management_page"))

    user.role_id = role.id
    user.is_admin = bool(role.is_admin)
    db.session.commit()
    flash(f"Da cap nhat quyen cho user '{user.username}' -> {role.name}.", "success")
    return redirect(url_for("admin.user_management_page"))
