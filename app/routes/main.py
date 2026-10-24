"""Primary navigation routes."""

from dataclasses import field
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, request, send_file, url_for
from flask_login import current_user, login_required
from app.spa import serve_react_spa

from app.services.anki_scheduler import (
    _day_index as scheduler_day_index,
    _day_index_to_datetime as scheduler_day_index_to_datetime,
)
from app.services import mcp_access_token_service
from app.services import support_donation_service
from app.services import tts_provider_service
from app.services.support_checkout_service import (
    SupportCheckoutError,
    prepare_support_checkout,
)
from app.utils.permissions import is_admin_user
from app.validators import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from models import db

main_bp = Blueprint("main", __name__)


def _day_index(moment: datetime, boundary_hour: int) -> int:
    return scheduler_day_index(moment, boundary_hour)


def _day_index_to_datetime(day_index: int, boundary_hour: int) -> datetime:
    return scheduler_day_index_to_datetime(day_index, boundary_hour)


def _support_api_error(error: str, message: str, *, status: int = 400, field: str | None = None):
    payload = {"error": error, "message": message}
    if field is not None:
        payload["field"] = field
    return jsonify(payload), status


@main_bp.route("/assets/<path:filename>")
def serve_react_assets(filename: str):
    from app.spa import serve_react_spa_assets
    return serve_react_spa_assets(filename)



def _render_mcp_tokens_page(*, generated_mcp_token: dict | None = None):
    return serve_react_spa(
        "mcp_tokens.html",
        mcp_generated_token=generated_mcp_token,
        mcp_access_tokens=mcp_access_token_service.list_token_summaries(user_id=current_user.id),
        mcp_token_policy=mcp_access_token_service.get_token_policy(),
    )


def _ensure_mcp_admin_access():
    if is_admin_user(current_user):
        return None
    flash("Chỉ quản trị viên mới có thể truy cập MCP.", "warning")
    return redirect(url_for("main.dashboard"))


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    from app.spa import serve_react_spa
    return serve_react_spa()


@main_bp.route("/terms")
def terms():
    from app.spa import serve_react_spa
    return serve_react_spa()


@main_bp.route("/privacy")
def privacy():
    from app.spa import serve_react_spa
    return serve_react_spa()


@main_bp.route("/cookies")
def cookies():
    from app.spa import serve_react_spa
    return serve_react_spa()


@main_bp.route("/support-donation")
def support_donation_page():
    from app.spa import serve_react_spa
    return serve_react_spa()


@main_bp.route("/support-donation/result")
def support_donation_result_page():
    return serve_react_spa()


@main_bp.route("/support-donation/qr")
def support_donation_qr_image():
    row = support_donation_service.get_latest_config()
    if row is None or not row.qr_image_storage_path:
        abort(404)

    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
    try:
        full_path = support_donation_service.resolve_qr_file_path(
            upload_root=upload_root,
            storage_path=row.qr_image_storage_path,
        )
    except RequestValidationError:
        abort(404)

    if not full_path.exists() or not full_path.is_file():
        abort(404)

    response = send_file(
        full_path,
        mimetype=row.qr_image_mime_type or "image/png",
        conditional=True,
        max_age=300,
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


@main_bp.route("/api/support-donation/checkout", methods=["POST"])
def support_donation_checkout_api():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _support_api_error(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
        )

    try:
        result, status_code = prepare_support_checkout(
            payload=payload,
            authenticated=bool(current_user.is_authenticated),
            user_id=int(current_user.id) if current_user.is_authenticated else None,
            default_return_url=url_for(
                "main.support_donation_result_page",
                _external=True,
            ),
        )
    except SupportCheckoutError as exc:
        return _support_api_error(
            exc.code,
            exc.message,
            status=exc.status,
            field=exc.field,
        )
    return jsonify(result), status_code


@main_bp.route("/api/support-donation/checkout-status", methods=["GET"])
def support_donation_checkout_status_api():
    from app.services.payment.provider import payos_provider

    provider_order_code = str(request.args.get("provider_order_code") or "").strip()
    if not provider_order_code:
        return _support_api_error(
            "VALIDATION_ERROR",
            "provider_order_code is required.",
            field="provider_order_code",
        )

    try:
        payload = support_donation_service.get_anonymous_checkout_status(
            provider_order_code=provider_order_code,
        )
    except payos_provider.PayOSProviderError as exc:
        return _support_api_error(exc.code, str(exc), status=exc.status)
    return jsonify(payload)


@main_bp.route("/dashboard")
@login_required
def dashboard():
    from app.spa import serve_react_spa
    return serve_react_spa()


@main_bp.route("/settings/mcp-tokens", methods=["GET"])
@login_required
def mcp_tokens_page():
    guard = _ensure_mcp_admin_access()
    if guard is not None:
        return guard
    return _render_mcp_tokens_page()


@main_bp.route("/settings/mcp-tokens/generate", methods=["POST"])
@login_required
def generate_mcp_token():
    guard = _ensure_mcp_admin_access()
    if guard is not None:
        return guard
    try:
        issued_token = mcp_access_token_service.issue_short_lived_token(user_id=current_user.id)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Không thể tạo MCP token lúc này. Vui lòng thử lại.", "danger")
        return redirect(url_for("main.mcp_tokens_page"))

    flash("MCP token mới đã được tạo. Hãy copy ngay bây giờ vì token chỉ hiện đúng một lần.", "success")
    return _render_mcp_tokens_page(generated_mcp_token=issued_token.to_display_payload())


@main_bp.route("/settings/mcp-tokens/<int:token_id>/revoke", methods=["POST"])
@login_required
def revoke_mcp_token(token_id: int):
    guard = _ensure_mcp_admin_access()
    if guard is not None:
        return guard
    try:
        revoked = mcp_access_token_service.revoke_token(user_id=current_user.id, token_id=token_id)
        if revoked:
            db.session.commit()
            flash("MCP token đã bị thu hồi.", "success")
        else:
            db.session.rollback()
            flash("Không tìm thấy MCP token để thu hồi.", "warning")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Không thể thu hồi MCP token lúc này. Vui lòng thử lại.", "danger")
    return redirect(url_for("main.mcp_tokens_page"))


@main_bp.route("/statistics", methods=["GET"])
@login_required
def statistics_page():
    from app.spa import serve_react_spa
    return serve_react_spa()


def _parse_boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return tts_provider_service.is_truthy(value)


def _serialize_validation_result(result: tts_provider_service.ApiKeyValidationResult) -> dict:
    return {
        "valid": bool(result.valid),
        "status": tts_provider_service.normalize_key_status(result.status),
        "message": str(result.message or ""),
        "checked_at": result.checked_at.isoformat() if result.checked_at else None,
    }


@main_bp.route("/api/tts/providers", methods=["GET"])
@login_required
def tts_provider_list():
    items = tts_provider_service.list_active_provider_profiles_for_user(current_user.id)
    return jsonify({"items": items})


@main_bp.route("/api/tts/providers/<provider_type>/profile", methods=["GET", "PUT"])
@login_required
def tts_provider_profile(provider_type: str):
    provider = tts_provider_service.find_provider_by_type(provider_type, include_inactive=False)
    if provider is None:
        return jsonify({"error": "NOT_FOUND", "message": "Provider không tồn tại hoặc đang bị tắt."}), 404

    if request.method == "GET":
        payload = tts_provider_service.get_provider_profile_payload_for_user(
            user_id=current_user.id,
            provider_type=provider.provider_type,
            include_inactive=False,
        )
        if payload is None:
            return jsonify({"error": "NOT_FOUND", "message": "Provider không tồn tại."}), 404
        return jsonify(payload)

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "VALIDATION_ERROR", "message": "Payload phải là object JSON."}), 400

    raw_api_key = tts_provider_service.UNSET
    if "api_key" in body:
        raw_api_key = str(body.get("api_key") or "")

    settings_payload = tts_provider_service.UNSET
    if "settings" in body:
        settings_payload = body.get("settings")

    clear_api_key = _parse_boolean(body.get("clear_api_key"))
    validate_key = _parse_boolean(body.get("validate_key"))

    try:
        profile, validation_result, errors = tts_provider_service.update_user_provider_profile(
            db.session,
            user_id=current_user.id,
            provider=provider,
            raw_api_key=raw_api_key,
            clear_api_key=clear_api_key,
            settings_payload=settings_payload,
            validate_key=validate_key,
        )
        if errors:
            db.session.rollback()
            return jsonify({"error": "VALIDATION_ERROR", "message": "; ".join(errors), "errors": errors}), 400
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "DB_ERROR", "message": "Không thể cập nhật cấu hình TTS của user."}), 500

    payload = tts_provider_service.serialize_user_provider_profile(provider=provider, profile=profile)
    if validation_result is not None:
        payload["validation"] = _serialize_validation_result(validation_result)
    return jsonify(payload)


@main_bp.route("/api/tts/providers/<provider_type>/validate-key", methods=["POST"])
@login_required
def tts_validate_provider_key(provider_type: str):
    provider = tts_provider_service.find_provider_by_type(provider_type, include_inactive=False)
    if provider is None:
        return jsonify({"error": "NOT_FOUND", "message": "Provider không tồn tại hoặc đang bị tắt."}), 404

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "VALIDATION_ERROR", "message": "Payload phải là object JSON."}), 400

    api_key_override: str | None = None
    if "api_key" in body:
        api_key_override = str(body.get("api_key") or "").strip() or None

    try:
        result, errors = tts_provider_service.validate_user_provider_key(
            db.session,
            user_id=current_user.id,
            provider=provider,
            api_key_override=api_key_override,
        )
        if errors or result is None:
            db.session.rollback()
            messages = errors or ["Không thể validate API key."]
            return jsonify({"error": "VALIDATION_ERROR", "message": "; ".join(messages), "errors": messages}), 400
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "DB_ERROR", "message": "Không thể lưu kết quả validate API key."}), 500

    payload = tts_provider_service.get_provider_profile_payload_for_user(
        user_id=current_user.id,
        provider_type=provider.provider_type,
        include_inactive=False,
    )
    return jsonify(
        {
            "validation": _serialize_validation_result(result),
            "item": payload,
        }
    )


@main_bp.route("/api/tts/providers/<provider_type>/voices", methods=["POST"])
@login_required
def tts_provider_voices(provider_type: str):
    provider = tts_provider_service.find_provider_by_type(provider_type, include_inactive=False)
    if provider is None:
        return jsonify({"error": "NOT_FOUND", "message": "Provider không tồn tại hoặc đang bị tắt."}), 404

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "VALIDATION_ERROR", "message": "Payload phải là object JSON."}), 400

    api_key_override = str(body.get("api_key") or "").strip() or None
    try:
        items, errors = tts_provider_service.list_provider_voices_for_user(
            db.session,
            user_id=current_user.id,
            provider=provider,
            api_key_override=api_key_override,
        )
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "DB_ERROR", "message": "Không thể tải danh sách nhân vật VoiceVox."}), 500

    if errors:
        return jsonify({"error": "VALIDATION_ERROR", "message": "; ".join(errors), "errors": errors}), 400
    return jsonify({"items": items})
