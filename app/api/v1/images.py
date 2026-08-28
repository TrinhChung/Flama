"""Unified Image Ingestion REST API."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app.api.common import error_response
from app.services import image_ingestion_service
from app.validators import RequestValidationError
from models.image_asset import ImageAsset

images_bp = Blueprint("api_v1_images", __name__)


@images_bp.post("/ingest")
def ingest_image_api():
    user_id = getattr(current_user, "id", None) if current_user and current_user.is_authenticated else None
    source_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    payload = request.get_json(silent=True) or {}
    form = request.form or {}

    source_url = payload.get("source_url") or form.get("source_url")
    base64_data = payload.get("base64_data") or form.get("base64_data")
    usage_type = (payload.get("usage_type") or form.get("usage_type") or "general").strip().lower()
    preset = payload.get("preset") or form.get("preset")
    uploaded_file = request.files.get("image") or request.files.get("file")

    try:
        asset = image_ingestion_service.ingest_image(
            user_id=user_id,
            source_type="upload" if uploaded_file else ("external_url" if source_url else "base64"),
            file=uploaded_file,
            source_url=source_url,
            base64_data=base64_data,
            usage_type=usage_type,
            preset=preset,
            source_ip=source_ip,
        )
    except RequestValidationError as exc:
        return error_response(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        )

    return jsonify({"asset": asset.to_dict()}), 201


@images_bp.get("/<asset_id>/status")
def get_image_status(asset_id: str):
    asset = ImageAsset.query.get(asset_id)
    if asset is None:
        return error_response(
            "NOT_FOUND",
            "Image asset not found.",
            status=404,
        )
    return jsonify({"asset": asset.to_dict()})
