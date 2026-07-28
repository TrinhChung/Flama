"""Canonical React routes that do not have a legacy Flask page handler."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, url_for
from flask_login import current_user, login_required

from app.spa import serve_react_spa
from app.utils.permissions import is_admin_user


spa_routes_bp = Blueprint("spa_routes", __name__)


@spa_routes_bp.get("/support")
def support_page():
    return serve_react_spa()


@spa_routes_bp.get("/browse")
@spa_routes_bp.get("/study")
@spa_routes_bp.get("/installed-decks")
@spa_routes_bp.get("/import")
@spa_routes_bp.get("/marketplace/decks")
@spa_routes_bp.get("/marketplace/decks/<item_id>")
@spa_routes_bp.get("/marketplace/note-types")
@spa_routes_bp.get("/marketplace/note-types/<item_id>")
@login_required
def authenticated_spa_page(item_id: str | None = None):
    del item_id
    return serve_react_spa()


@spa_routes_bp.get("/admin/tts")
@login_required
def admin_tts_page():
    if not is_admin_user(current_user):
        flash("Bạn không có quyền truy cập khu vực quản trị.", "warning")
        return redirect(url_for("main.dashboard"))
    return serve_react_spa()
