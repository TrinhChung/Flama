"""Route handler for serving managed image assets."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, current_app, send_file

from app.validators import RequestValidationError, build_safe_download_filename, resolve_safe_storage_path
from models.image_asset import ImageAsset

media_asset_bp = Blueprint("media_asset", __name__)


def _upload_root() -> Path:
    return Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()


@media_asset_bp.get("/media/asset/<asset_id>")
def serve_managed_image_asset(asset_id: str):
    """Serve a clean, managed image asset with strong security headers."""
    asset = ImageAsset.query.get(asset_id)
    if asset is None:
        abort(404)

    if not asset.storage_path or asset.processing_status != "ready":
        abort(404)

    try:
        file_path = resolve_safe_storage_path(
            upload_root=_upload_root(),
            relative_path=Path(asset.storage_path),
        )
    except RequestValidationError:
        abort(404)

    if not file_path.exists() or not file_path.is_file():
        abort(404)

    mime_type = asset.output_mime_type or "image/webp"
    response = send_file(
        file_path,
        mimetype=mime_type,
        conditional=True,
        max_age=31536000 if asset.sha256 else 300,
    )

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    if asset.sha256:
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "private, no-cache, must-revalidate"

    filename = asset.original_filename or f"{asset.id}.webp"
    safe_fn = build_safe_download_filename(filename, fallback_ext="webp")
    response.headers["Content-Disposition"] = f'inline; filename="{safe_fn}"'

    return response
