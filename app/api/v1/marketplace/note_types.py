"""Marketplace shared note types and templates REST API V1 resources."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, url_for
from flask_login import current_user, login_required

from app.api.common.responses import error_response
from app.services import marketplace_note_type_service
from app.services.marketplace_note_type_service import MarketplaceNoteTypeError
from app.utils.permissions import is_admin_user

marketplace_note_types_bp = Blueprint("api_v1_marketplace_note_types", __name__)


def _handle_error(exc: MarketplaceNoteTypeError):
    return error_response(exc.error, exc.message, status=exc.status, field=exc.field)


@marketplace_note_types_bp.get("/shared/note-types/hub")
@marketplace_note_types_bp.get("/marketplace/note-types/hub")
@login_required
def shared_note_types_hub():
    payload = marketplace_note_type_service.get_note_types_hub(
        user_id=current_user.id,
        args=request.args,
        compact=request.args.get("compact") == "1",
    )
    return jsonify(payload)


@marketplace_note_types_bp.get("/shared/note-types/recommendations")
@marketplace_note_types_bp.get("/marketplace/note-types/recommendations")
@login_required
def shared_note_type_recommendations():
    payload = marketplace_note_type_service.get_recommendations(
        user_id=current_user.id
    )
    return jsonify(payload)


@marketplace_note_types_bp.get("/shared/note-types")
@marketplace_note_types_bp.get("/marketplace/note-types")
@login_required
def list_shared_note_types():
    payload = marketplace_note_type_service.list_shared_note_types(
        user_id=current_user.id,
        args=request.args,
    )
    return jsonify(payload)


@marketplace_note_types_bp.get("/shared/note-types/<note_type_id>")
@marketplace_note_types_bp.get("/marketplace/note-types/<note_type_id>")
@login_required
def get_shared_note_type_detail(note_type_id: str):
    try:
        payload = marketplace_note_type_service.get_shared_note_type_detail(
            user_id=current_user.id,
            note_type_id=note_type_id,
        )
    except MarketplaceNoteTypeError as exc:
        return _handle_error(exc)
    return jsonify(payload)


@marketplace_note_types_bp.route(
    "/shared/note-types/<note_type_id>/save", methods=["POST", "DELETE"]
)
@marketplace_note_types_bp.route(
    "/marketplace/note-types/<note_type_id>/save", methods=["POST", "DELETE"]
)
@login_required
def save_shared_note_type(note_type_id: str):
    try:
        payload = marketplace_note_type_service.save_shared_note_type(
            user_id=current_user.id,
            note_type_id=note_type_id,
            is_save=(request.method == "POST"),
        )
    except MarketplaceNoteTypeError as exc:
        return _handle_error(exc)
    return jsonify(payload)


@marketplace_note_types_bp.post("/note-types/<note_type_id>/publish")
@marketplace_note_types_bp.post("/marketplace/note-types/<note_type_id>/publish")
@login_required
def publish_note_type(note_type_id: str):
    try:
        payload = marketplace_note_type_service.publish_note_type(
            user_id=current_user.id,
            is_admin=is_admin_user(current_user),
            note_type_id=note_type_id,
            payload=request.get_json(silent=True) or {},
        )
    except MarketplaceNoteTypeError as exc:
        return _handle_error(exc)
    return jsonify(payload)


@marketplace_note_types_bp.post(
    "/shared/note-types/<note_type_id>/templates/<template_id>/preview"
)
@marketplace_note_types_bp.post(
    "/marketplace/note-types/<note_type_id>/templates/<template_id>/preview"
)
@login_required
def preview_shared_note_type_template(note_type_id: str, template_id: str):
    try:
        payload = marketplace_note_type_service.preview_shared_note_type_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            template_id=template_id,
        )
    except MarketplaceNoteTypeError as exc:
        return _handle_error(exc)
    return jsonify(payload)


@marketplace_note_types_bp.post("/shared/note-types/<note_type_id>/install")
@marketplace_note_types_bp.post("/marketplace/note-types/<note_type_id>/install")
@login_required
def install_shared_note_type(note_type_id: str):
    try:
        payload, status_code = marketplace_note_type_service.install_shared_note_type(
            user_id=current_user.id,
            note_type_id=note_type_id,
            return_url=url_for("payments.marketplace_payment_result_page", _external=True),
            cancel_url=url_for("payments.marketplace_payment_result_page", _external=True),
        )
    except MarketplaceNoteTypeError as exc:
        return _handle_error(exc)
    return jsonify(payload), status_code


@marketplace_note_types_bp.post("/shared/note-types/<note_type_id>/rate")
@marketplace_note_types_bp.post("/marketplace/note-types/<note_type_id>/rate")
@login_required
def rate_shared_note_type(note_type_id: str):
    req_json = request.get_json(silent=True) or {}
    try:
        rating = int(req_json.get("rating"))
    except (TypeError, ValueError):
        return error_response(
            "VALIDATION_ERROR",
            "rating must be an integer 1-5.",
            status=400,
            field="rating",
        )

    try:
        payload = marketplace_note_type_service.rate_shared_note_type(
            user_id=current_user.id,
            note_type_id=note_type_id,
            rating=rating,
            comment=req_json.get("comment"),
        )
    except MarketplaceNoteTypeError as exc:
        return _handle_error(exc)
    return jsonify(payload)
