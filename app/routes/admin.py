"""Admin-only user management routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.utils.permissions import is_admin_user
from app.services import admin_service
from app.services import payout_service
from app.services import support_donation_service
from app.services import tts_provider_service
from app.validators import RequestValidationError, escape_like_pattern, sanitize_query_text

from models import db
from models.support_donation_config import SupportDonationConfig
from models.tts_provider_config import TtsProviderConfig
from models.user import User
from models.user_permission_audit_log import UserPermissionAuditLog
from models.user_role import UserRole

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50



















def _ensure_admin_access():
    if is_admin_user(current_user):
        return None
    flash("Ban khong co quyen truy cap trang quan tri.", "warning")
    return redirect(url_for("main.dashboard"))


def _parse_bool_query(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@admin_bp.route("/support-donation", methods=["GET", "POST"])
@login_required
def support_donation_management_page():
    guard = _ensure_admin_access()
    if guard is not None:
        return guard

    row = support_donation_service.get_latest_config()

    if request.method == "POST":
        payload, errors = support_donation_service.parse_form_payload(request.form)

        qr_max_bytes = min(
            int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", support_donation_service.DEFAULT_QR_MAX_BYTES)),
            support_donation_service.DEFAULT_QR_MAX_BYTES,
        )
        validated_upload, upload_errors = support_donation_service.validate_qr_upload(
            request.files.get("qr_image"),
            max_bytes=qr_max_bytes,
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)),
        )
        errors.extend(upload_errors)

        if errors:
            for message in errors:
                flash(message, "danger")
            return redirect(url_for("admin.support_donation_management_page"))

        remove_qr = support_donation_service.is_truthy(request.form.get("remove_qr_image"))
        if row is None:
            row = SupportDonationConfig()
            db.session.add(row)

        row.title = payload.title
        row.description = payload.description
        row.account_name = payload.account_name
        row.account_number = payload.account_number
        row.thank_you_message = payload.thank_you_message
        row.updated_by_admin_id = current_user.id

        upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
        old_storage_path = str(row.qr_image_storage_path or "").strip() or None
        new_storage_path_written: str | None = None
        obsolete_storage_path: str | None = None

        if validated_upload is not None:
            try:
                storage_path, filename, mime_type = support_donation_service.persist_qr_upload(
                    validated_upload=validated_upload,
                    upload_root=upload_root,
                )
            except RequestValidationError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("admin.support_donation_management_page"))

            row.qr_image_storage_path = storage_path
            row.qr_image_filename = filename
            row.qr_image_mime_type = mime_type
            new_storage_path_written = storage_path
            if old_storage_path and old_storage_path != storage_path:
                obsolete_storage_path = old_storage_path
        elif remove_qr:
            row.qr_image_storage_path = None
            row.qr_image_filename = None
            row.qr_image_mime_type = None
            if old_storage_path:
                obsolete_storage_path = old_storage_path

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            if new_storage_path_written:
                support_donation_service.remove_qr_file(
                    upload_root=upload_root,
                    storage_path=new_storage_path_written,
                )
            flash("Không thể lưu thông tin tài trợ. Vui lòng thử lại.", "danger")
            return redirect(url_for("admin.support_donation_management_page"))

        if obsolete_storage_path:
            support_donation_service.remove_qr_file(
                upload_root=upload_root,
                storage_path=obsolete_storage_path,
            )

        flash("Đã cập nhật thông tin tài trợ.", "success")
        return redirect(url_for("admin.support_donation_management_page"))

    return render_template(
        "admin/support_donation.html",
        config=row,
        default_support_title=support_donation_service.DEFAULT_TITLE,
        default_support_description=support_donation_service.DEFAULT_DESCRIPTION,
        default_thank_you_message=support_donation_service.DEFAULT_THANK_YOU,
    )


@admin_bp.route("/tts-providers", methods=["GET", "POST"])
@login_required
def tts_provider_management_page():
    def _redirect_with_state():
        next_path = (request.form.get("next") or "").strip()
        if next_path.startswith("/admin/tts-providers"):
            return redirect(next_path)
        return redirect(url_for("admin.tts_provider_management_page"))

    def _flash_form_errors(errors: list[str]) -> None:
        for message in errors:
            flash(message, "danger")

    def _query_duplicate(
        *,
        provider_type: str,
        exclude_id: int | None = None,
    ) -> TtsProviderConfig | None:
        query = TtsProviderConfig.query.filter(
            func.lower(TtsProviderConfig.provider_type) == provider_type.lower(),
        )
        if exclude_id is not None:
            query = query.filter(TtsProviderConfig.id != exclude_id)
        return query.first()

    def _build_filtered_query(*, search_term: str, active_filter: str, provider_type_filter: str):
        query = TtsProviderConfig.query
        if search_term:
            escaped = escape_like_pattern(search_term)
            like_pattern = f"%{escaped}%"
            query = query.filter(
                or_(
                    TtsProviderConfig.provider_name.ilike(like_pattern, escape="\\"),
                    TtsProviderConfig.provider_type.ilike(like_pattern, escape="\\"),
                )
            )

        if active_filter == "active":
            query = query.filter(TtsProviderConfig.is_active.is_(True))
        elif active_filter == "inactive":
            query = query.filter(TtsProviderConfig.is_active.is_(False))

        if provider_type_filter:
            query = query.filter(TtsProviderConfig.provider_type == provider_type_filter)

        return query

    guard = _ensure_admin_access()
    if guard is not None:
        return guard

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        if action == "create":
            payload, errors = tts_provider_service.parse_provider_form_payload(
                request.form,
                for_update=False,
            )
            if errors:
                _flash_form_errors(errors)
                return _redirect_with_state()

            duplicate = _query_duplicate(
                provider_type=payload.provider_type,
            )
            if duplicate is not None:
                flash("Đã tồn tại cấu hình dùng chung cho provider_type này.", "warning")
                return _redirect_with_state()

            row = TtsProviderConfig(
                provider_name=payload.provider_name,
                provider_type=payload.provider_type,
                base_url=payload.base_url,
                requires_api_key=payload.requires_api_key,
                is_active=payload.is_active,
                shared_config_json=tts_provider_service.dumps_json_map(payload.shared_config),
                provider_config_json=tts_provider_service.dumps_json_map(payload.provider_config),
                default_settings_json=tts_provider_service.dumps_json_map(payload.default_settings),
                created_by_admin_id=current_user.id,
                updated_by_admin_id=current_user.id,
            )

            try:
                db.session.add(row)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                flash("Không thể tạo cấu hình provider. Vui lòng thử lại.", "danger")
                return _redirect_with_state()
            flash("Đã tạo cấu hình TTS provider.", "success")
            return _redirect_with_state()

        if action == "update":
            row_id = admin_service.coerce_int(request.form.get("id"), default=0, minimum=1)
            row = db.session.get(TtsProviderConfig, row_id)
            if row is None:
                flash("Không tìm thấy bản ghi cần cập nhật.", "danger")
                return _redirect_with_state()

            payload, errors = tts_provider_service.parse_provider_form_payload(
                request.form,
                for_update=True,
            )
            if errors:
                _flash_form_errors(errors)
                return _redirect_with_state()

            duplicate = _query_duplicate(
                provider_type=payload.provider_type,
                exclude_id=row.id,
            )
            if duplicate is not None:
                flash("Đã tồn tại một cấu hình dùng chung với provider_type này.", "warning")
                return _redirect_with_state()

            row.provider_name = payload.provider_name
            row.provider_type = payload.provider_type
            row.base_url = payload.base_url
            row.requires_api_key = payload.requires_api_key
            row.is_active = payload.is_active
            row.shared_config_json = tts_provider_service.dumps_json_map(payload.shared_config)
            row.provider_config_json = tts_provider_service.dumps_json_map(payload.provider_config)
            row.default_settings_json = tts_provider_service.dumps_json_map(payload.default_settings)
            row.updated_by_admin_id = current_user.id

            try:
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                flash("Không thể cập nhật cấu hình provider. Vui lòng thử lại.", "danger")
                return _redirect_with_state()
            flash("Đã cập nhật cấu hình TTS provider.", "success")
            return _redirect_with_state()

        if action == "delete":
            row_id = admin_service.coerce_int(request.form.get("id"), default=0, minimum=1)
            row = db.session.get(TtsProviderConfig, row_id)
            if row is None:
                flash("Không tìm thấy bản ghi để xóa.", "danger")
                return _redirect_with_state()
            try:
                db.session.delete(row)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                flash("Không thể xóa cấu hình provider. Vui lòng thử lại.", "danger")
                return _redirect_with_state()
            flash("Đã xóa cấu hình TTS provider.", "success")
            return _redirect_with_state()

        flash("Action không hợp lệ.", "danger")
        return _redirect_with_state()

    try:
        search_term = sanitize_query_text(request.args.get("q"), field_name="q", max_length=120)
    except RequestValidationError:
        search_term = ""
        flash("Bộ lọc tìm kiếm không hợp lệ và đã được bỏ qua.", "warning")

    active_filter = tts_provider_service.normalize_active_filter(request.args.get("active"))
    provider_type_filter = tts_provider_service.normalize_provider_type_filter(request.args.get("provider_type"))

    rows_query = _build_filtered_query(
        search_term=search_term,
        active_filter=active_filter,
        provider_type_filter=provider_type_filter,
    )
    rows = rows_query.order_by(TtsProviderConfig.updated_at.desc(), TtsProviderConfig.id.desc()).all()
    summary = {
        "total_count": TtsProviderConfig.query.count(),
        "active_count": TtsProviderConfig.query.filter(TtsProviderConfig.is_active.is_(True)).count(),
        "requires_key_count": TtsProviderConfig.query.filter(TtsProviderConfig.requires_api_key.is_(True)).count(),
        "filtered_count": len(rows),
    }
    provider_types = (
        db.session.query(TtsProviderConfig.provider_type)
        .distinct()
        .filter(TtsProviderConfig.provider_type.isnot(None), TtsProviderConfig.provider_type != "")
        .order_by(TtsProviderConfig.provider_type.asc())
        .all()
    )
    provider_type_options = [value for (value,) in provider_types if value]
    current_page_url = url_for(
        "admin.tts_provider_management_page",
        q=search_term or None,
        active=active_filter if active_filter != "all" else None,
        provider_type=provider_type_filter or None,
    )

    return render_template(
        "admin/tts_provider_config.html",
        rows=rows,
        pretty_json=tts_provider_service.pretty_json,
        loads_json_map=tts_provider_service.loads_json_map,
        search_term=search_term,
        active_filter=active_filter,
        provider_type_filter=provider_type_filter,
        provider_type_options=provider_type_options,
        current_page_url=current_page_url,
        summary=summary,
    )


@admin_bp.route("/users", methods=["GET"])
@login_required
def user_management_page():
    guard = _ensure_admin_access()
    if guard is not None:
        return guard

    try:
        search_term = sanitize_query_text(request.args.get("q"), field_name="q", max_length=120)
    except RequestValidationError:
        search_term = ""
        flash("Invalid search query detected and ignored.", "warning")
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

    try:
        search_term = sanitize_query_text(request.args.get("q"), field_name="q", max_length=120)
    except RequestValidationError as exc:
        return jsonify({"message": str(exc), "field": exc.field, "error": exc.code}), exc.status
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


@admin_bp.route("/api/payouts", methods=["POST"])
@login_required
def create_payout_batch_api():
    if not is_admin_user(current_user):
        return jsonify({"message": "Unauthorized"}), 403

    payload = request.get_json(silent=True)
    try:
        result = payout_service.create_payout_batch(
            actor_user_id=current_user.id,
            raw_payload=payload,
        )
    except RequestValidationError as exc:
        return jsonify({"error": exc.code, "message": str(exc), "field": exc.field}), exc.status
    except payout_service.PayoutServiceError as exc:
        return (
            jsonify(
                {
                    "error": exc.code,
                    "message": str(exc),
                    "batch_id": exc.batch_id,
                }
            ),
            exc.status,
        )

    status_code = 201 if result.created else 200
    return (
        jsonify(
            {
                "duplicate_reused": bool(result.duplicate_reused),
                "batch": payout_service.serialize_payout_batch(result.batch),
            }
        ),
        status_code,
    )


@admin_bp.route("/api/payouts/<int:batch_id>", methods=["GET"])
@login_required
def payout_batch_detail_api(batch_id: int):
    if not is_admin_user(current_user):
        return jsonify({"message": "Unauthorized"}), 403

    refresh = _parse_bool_query(request.args.get("refresh"))
    try:
        batch = payout_service.get_payout_batch(batch_id=batch_id, refresh=refresh)
    except payout_service.PayoutServiceError as exc:
        return (
            jsonify(
                {
                    "error": exc.code,
                    "message": str(exc),
                    "batch_id": exc.batch_id,
                }
            ),
            exc.status,
        )

    if batch is None:
        return jsonify({"error": "NOT_FOUND", "message": "Payout batch not found."}), 404

    return jsonify({"batch": payout_service.serialize_payout_batch(batch)})


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
