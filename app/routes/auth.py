"""Authentication related routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.services.user_roles import ensure_default_user_roles
from models import db
from models.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or not username or not password:
            flash("Vui lòng điền đầy đủ thông tin.", "warning")
            return render_template("register.html")

        if password != confirm_password:
            flash("Mật khẩu xác nhận không trùng khớp.", "danger")
            return render_template("register.html")

        if username.lower() == email:
            flash("Tên đăng nhập không được trùng với email.", "danger")
            return render_template("register.html")

        existing_user = User.query.filter(
            (User.email == email) | (User.username == username)
        ).first()
        if existing_user:
            flash("Email hoặc tên đăng nhập đã tồn tại.", "danger")
            return render_template("register.html")

        from app.services.auth_service import register_user_and_commit
        register_user_and_commit(email, username, password)

        flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Vui lòng nhập email và mật khẩu.", "warning")
            return render_template("login.html")

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash("Thông tin đăng nhập không chính xác.", "danger")
            return render_template("login.html")

        if not login_user(user):
            flash("Tai khoan da bi vo hieu hoa.", "danger")
            return render_template("login.html")
        flash("Đăng nhập thành công!", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("main.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for("main.index"))
