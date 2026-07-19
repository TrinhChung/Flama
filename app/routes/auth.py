"""Authentication related routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.services import login_rate_limit_service
from app.services.user_roles import ensure_default_user_roles
from app.utils.redirects import resolve_safe_next_url
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
        remote_addr = request.headers.get("X-Forwarded-For", request.remote_addr)

        if not email or not password:
            flash("Vui lòng nhập email và mật khẩu.", "warning")
            return render_template("login.html")

        lockout_remaining = login_rate_limit_service.get_lockout_remaining(
            email=email,
            remote_addr=remote_addr,
        )
        if lockout_remaining > 0:
            flash(
                f"Bạn đã thử đăng nhập quá nhiều lần. Vui lòng thử lại sau khoảng {lockout_remaining} giây.",
                "danger",
            )
            return render_template("login.html"), 429

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            login_rate_limit_service.register_failure(email=email, remote_addr=remote_addr)
            flash("Thông tin đăng nhập không chính xác.", "danger")
            return render_template("login.html")

        if not login_user(user):
            login_rate_limit_service.register_failure(email=email, remote_addr=remote_addr)
            flash("Tài khoản của bạn đã bị vô hiệu hóa.", "danger")
            return render_template("login.html")
        login_rate_limit_service.register_success(email=email, remote_addr=remote_addr)
        flash("Đăng nhập thành công!", "success")
        next_url = resolve_safe_next_url(
            request.args.get("next"),
            default_endpoint="main.dashboard",
        )
        return redirect(next_url)

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/logout", methods=["GET"])
def logout_get():
    if current_user.is_authenticated:
        flash("Vui lòng dùng nút đăng xuất trong giao diện hiện tại.", "info")
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.index"))
