"""Sub-module for flashcard routes."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
from flask import jsonify, request, send_file, current_app
from flask_login import current_user, login_required
from models.flashcard import *

# Import everything from core module so routes can use helpers
from . import *

from app.routes.flashcards import (
    _api_error,
)
from app.validators import (
    RequestValidationError,
    build_safe_download_filename,
    resolve_safe_storage_path,
)



@flashcards_bp.route("/api/note-types/<note_type_id>/templates", methods=["GET"])
@login_required
def list_templates(note_type_id: str):
    from app.services import flashcard_content_service

    try:
        return jsonify(
            flashcard_content_service.list_templates(
                user_id=current_user.id,
                note_type_id=note_type_id,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )

@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>", methods=["DELETE"])
@login_required
def delete_template(note_type_id: str, template_id: str):
    from app.services import flashcard_content_service

    try:
        return jsonify(
            flashcard_content_service.delete_template(
                user_id=current_user.id,
                note_type_id=note_type_id,
                template_id=template_id,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )

@flashcards_bp.route("/api/notes/<note_id>", methods=["GET"])
@login_required
def get_note(note_id: str):
    from app.services import flashcard_content_service

    try:
        return jsonify(
            flashcard_content_service.get_note(
                user_id=current_user.id,
                note_id=note_id,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )

@flashcards_bp.route("/api/notes/<note_id>/media", methods=["POST"])
@login_required
def upload_note_media(note_id: str):
    from app.services import flashcard_media_api_service

    try:
        payload, status = flashcard_media_api_service.upload_media(
            user_id=current_user.id,
            note_id=note_id,
            field_name=request.form.get("field_name") or "",
            uploaded=request.files.get("file"),
            upload_root=Path(
                current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
            ),
            max_bytes=int(
                current_app.config.get(
                    "FLASHCARD_MEDIA_MAX_BYTES",
                    10 * 1024 * 1024,
                )
            ),
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(
                current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)
            ),
            markdown_inline=False,
        )
    except flashcard_media_api_service.MediaApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload), status


@flashcards_bp.route("/api/notes/<note_id>/markdown-media", methods=["POST"])
@login_required
def upload_note_markdown_media(note_id: str):
    from app.services import flashcard_media_api_service

    try:
        payload, status = flashcard_media_api_service.upload_media(
            user_id=current_user.id,
            note_id=note_id,
            field_name=request.form.get("field_name") or "",
            uploaded=request.files.get("file"),
            upload_root=Path(
                current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
            ),
            max_bytes=int(
                current_app.config.get(
                    "FLASHCARD_MEDIA_MAX_BYTES",
                    10 * 1024 * 1024,
                )
            ),
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(
                current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)
            ),
            markdown_inline=True,
        )
    except flashcard_media_api_service.MediaApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload), status

@flashcards_bp.route("/api/media/<asset_id>", methods=["DELETE"])
@login_required
def delete_media(asset_id: str):
    from app.services import flashcard_media_api_service

    try:
        return jsonify(
            flashcard_media_api_service.delete_media(
                user_id=current_user.id,
                asset_id=asset_id,
                upload_root=Path(
                    current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
                ),
            )
        )
    except flashcard_media_api_service.MediaApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )

_NO_CACHE_CONTROL = "no-cache, no-store, must-revalidate, max-age=0"
_PRAGMA_NO_CACHE = "no-cache"


def _media_error(error: str, message: str, *, status: int = 404):
    response, code = _api_error(error, message, status=status)
    response.headers["Cache-Control"] = _NO_CACHE_CONTROL
    response.headers["Pragma"] = _PRAGMA_NO_CACHE
    return response, code


@flashcards_bp.route("/media/proxy/<asset_id>", methods=["GET"])
def proxy_media(asset_id: str):
    # Reserved, application-owned samples are available without a MediaAsset.
    from app.services.template_preview_sample_service import preview_sample_media
    sample = preview_sample_media(asset_id)
    if sample is not None:
        from io import BytesIO
        data, mime_type, filename = sample
        response = send_file(BytesIO(data), mimetype=mime_type,
                             download_name=filename, conditional=True, max_age=86400)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response
    asset = MediaAsset.query.filter(MediaAsset.id == asset_id).first()
    if not asset:
        return _media_error("FIELD_NOT_FOUND", "Media asset not found.", status=404)
    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
    try:
        full_path = resolve_safe_storage_path(
            upload_root=upload_root,
            relative_path=Path(asset.storage_path),
        )
    except RequestValidationError:
        return _media_error("FIELD_NOT_FOUND", "Media file not found on disk.", status=404)
    if not full_path.exists():
        return _media_error("FIELD_NOT_FOUND", "Media file not found on disk.", status=404)

    # A short browser TTL keeps deletion/revocation reasonably fresh. Shared
    # caches may retain the immutable-by-ID payload for one day.
    cache_control = "public, max-age=3600, s-maxage=86400"

    if request.if_none_match.contains(asset.sha256):
        response = current_app.response_class(status=304)
    elif current_app.config.get("MEDIA_PROXY_USE_XACCEL", False):
        # Production: Nginx serves the validated file while Gunicorn is freed.
        response = current_app.response_class()
        relative_url_path = Path(asset.storage_path).as_posix().lstrip("/")
        response.headers["X-Accel-Redirect"] = quote(
            f"/internal-media/{relative_url_path}",
            safe="/",
        )
        response.headers["Content-Type"] = asset.mime_type
    else:
        # Development / test fallback: Flask streams the file.
        response = send_file(
            full_path, mimetype=asset.mime_type, conditional=True,
        )

    response.set_etag(asset.sha256)
    response.headers["Cache-Control"] = cache_control
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response.headers["Content-Disposition"] = (
        f'inline; filename="{build_safe_download_filename(asset.filename)}"'
    )
    # Remove Vary: Cookie — media is a public static asset that does not
    # depend on session state.  Keeping Vary prevents CDN caching.
    response.headers.pop("Vary", None)
    return response


@flashcards_bp.route("/api/browse/media/stage-paste", methods=["POST"])
@login_required
def stage_pasted_media():
    from app.services import media_staging_service

    source_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    payload = request.get_json(silent=True) or {}
    form = request.form or {}
    uploaded_file = request.files.get("image") or request.files.get("file")
    base64_data = payload.get("base64_data") or form.get("base64_data")

    try:
        result = media_staging_service.stage_pasted_image(
            user_id=current_user.id,
            file=uploaded_file,
            base64_data=base64_data,
            source_ip=source_ip,
        )
        return jsonify(result), 201
    except RequestValidationError as exc:
        return _api_error(exc.code, str(exc), status=exc.status, field=exc.field)
    except Exception as exc:
        return _api_error("STAGE_MEDIA_ERROR", str(exc), status=400)


@flashcards_bp.route("/media/staged/<stage_id>", methods=["GET"])
def serve_staged_media(stage_id: str):
    from app.services import media_staging_service

    staged = media_staging_service.get_staged_media(stage_id)
    if staged is None:
        return _api_error("NOT_FOUND", "Ảnh tạm không tồn tại hoặc đã hết hạn (30 phút).", status=404)

    file_path, mime_type = staged
    response = send_file(file_path, mimetype=mime_type, conditional=True, max_age=1800)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response.headers["Content-Disposition"] = f'inline; filename="{stage_id}.webp"'
    return response

