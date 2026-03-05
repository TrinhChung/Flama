"""Primary navigation routes."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.services.anki_scheduler import (
    _day_index as scheduler_day_index,
    _day_index_to_datetime as scheduler_day_index_to_datetime,
)
from app.services import support_donation_service
from app.services import tts_provider_service
from app.services.stats_overview import build_stats_overview
from app.services.stats_today_future import build_today_future_stats, list_stats_decks
from app.utils.deck_move_token import create_deck_move_token
from app.utils.permissions import is_admin_user
from app.validators import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from models import db
from models.flashcard import Card, DeckCloneDeckMap, DeckInstall, Note
from models.deck import Deck
from models.card_progress import CardProgress

main_bp = Blueprint("main", __name__)


def _day_index(moment: datetime, boundary_hour: int) -> int:
    return scheduler_day_index(moment, boundary_hour)


def _day_index_to_datetime(day_index: int, boundary_hour: int) -> datetime:
    return scheduler_day_index_to_datetime(day_index, boundary_hour)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@main_bp.route("/terms")
def terms():
    return render_template("terms.html")


@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@main_bp.route("/cookies")
def cookies():
    return render_template("cookies.html")


@main_bp.route("/support-donation")
def support_donation_page():
    row = support_donation_service.get_latest_config()
    return render_template(
        "support_donation.html",
        donation_config=row,
        default_support_title=support_donation_service.DEFAULT_TITLE,
        default_support_description=support_donation_service.DEFAULT_DESCRIPTION,
        default_thank_you_message=support_donation_service.DEFAULT_THANK_YOU,
    )


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
    return response


@main_bp.route("/dashboard")
@login_required
def dashboard():
    from app.services.dashboard_service import build_dashboard_data
    rows, total_new, total_learn, total_due, admin_mode = build_dashboard_data(current_user)

    return render_template(
        "dashboard.html",
        deck_rows=rows,
        total_new=total_new,
        total_learn=total_learn,
        total_due=total_due,
        admin_mode=admin_mode,
        stats_initial_year=datetime.utcnow().year,
    )


@main_bp.route("/statistics", methods=["GET"])
@login_required
def statistics_page():
    decks = list_stats_decks(current_user.id)
    deck_id_raw = (request.args.get("deck_id") or "").strip()
    initial_deck_id = None
    if deck_id_raw:
        try:
            initial_deck_id = int(deck_id_raw)
        except ValueError:
            initial_deck_id = None

    deck_ids = {int(deck["id"]) for deck in decks}
    if initial_deck_id not in deck_ids:
        initial_deck_id = int(decks[0]["id"]) if decks else None

    return render_template(
        "statistics.html",
        stats_decks=decks,
        stats_initial_deck_id=initial_deck_id,
    )


@main_bp.route("/api/stats/overview", methods=["GET"])
@login_required
def stats_overview():
    year_raw = (request.args.get("year") or "").strip()
    year: int | None = None
    if year_raw:
        try:
            year = int(year_raw)
        except ValueError:
            return jsonify({"error": "VALIDATION_ERROR", "message": "year must be an integer."}), 400
        if year < 1970 or year > 2100:
            return jsonify({"error": "VALIDATION_ERROR", "message": "year must be between 1970 and 2100."}), 400

    payload = build_stats_overview(
        user_id=current_user.id,
        year=year,
        timezone_name=getattr(current_user, "timezone", "UTC"),
    )
    return jsonify(payload)


@main_bp.route("/api/stats/today-future", methods=["GET"])
@login_required
def stats_today_future():
    scope = (request.args.get("scope") or "deck").strip().lower()
    history_range = (request.args.get("history_range") or "12m").strip().lower()
    future_range = (request.args.get("future_range") or "30").strip().lower()
    backlog = (request.args.get("backlog") or "false").strip().lower()

    deck_id_raw = (request.args.get("deck_id") or "").strip()
    deck_id = None
    if deck_id_raw:
        try:
            deck_id = int(deck_id_raw)
        except ValueError:
            return jsonify({"error": "VALIDATION_ERROR", "message": "deck_id must be an integer."}), 400

    if scope not in {"deck", "collection"}:
        return jsonify({"error": "VALIDATION_ERROR", "message": "scope must be deck or collection."}), 400
    if history_range not in {"12m", "all"}:
        return jsonify({"error": "VALIDATION_ERROR", "message": "history_range must be 12m or all."}), 400
    if future_range not in {"30", "90", "365", "all"}:
        return jsonify({"error": "VALIDATION_ERROR", "message": "future_range must be 30, 90, 365, or all."}), 400
    if backlog not in {"0", "1", "true", "false", "yes", "no", "on", "off"}:
        return jsonify({"error": "VALIDATION_ERROR", "message": "backlog must be a boolean-like value."}), 400

    payload = build_today_future_stats(
        user_id=current_user.id,
        timezone_name=getattr(current_user, "timezone", "UTC"),
        scope=scope,
        deck_id=deck_id,
        history_range=history_range,
        future_range=future_range,
        backlog=backlog,
    )
    return jsonify(payload)


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
