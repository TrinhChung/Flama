"""Shared image library management and key-based resolution routes."""

from __future__ import annotations

from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from app.spa import serve_react_spa

from app.repositories import image_library_repository
from app.services import image_library_service
from app.utils.permissions import is_admin_user
from app.validators import (
    RequestValidationError,
    build_safe_download_filename,
    sanitize_query_text,
)
from app.validators.image_library import (
    normalize_image_key,
    parse_enabled_value,
)


image_library_bp = Blueprint("image_library", __name__)

DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 60
VALID_STATUS_FILTERS = {"", "enabled", "disabled", "missing_file"}


def _admin_page_guard():
    if is_admin_user(current_user):
        return None
    flash("Bạn không có quyền truy cập kho hình ảnh dùng chung.", "warning")
    return redirect(url_for("main.dashboard"))


def _require_admin_api() -> None:
    if not is_admin_user(current_user):
        abort(403)


def _upload_root() -> Path:
    return Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()


def _fallback_path() -> Path:
    return Path(current_app.static_folder or "") / "images" / "image-library-fallback.svg"


def _parse_positive_int(raw_value: str | None, *, default: int, maximum: int) -> int:
    try:
        value = int(str(raw_value or "").strip())
    except (TypeError, ValueError):
        return default
    return min(max(1, value), maximum)


def _redirect_to_management(*, edit_id: str | None = None):
    values: dict[str, object] = {}
    search_term = (request.form.get("return_q") or "").strip()
    status = (request.form.get("return_status") or "").strip()
    page = _parse_positive_int(
        request.form.get("return_page"),
        default=1,
        maximum=100000,
    )
    if search_term:
        values["q"] = search_term
    if status in VALID_STATUS_FILTERS and status:
        values["status"] = status
    if page > 1:
        values["page"] = page
    if edit_id:
        values["edit"] = edit_id
    return redirect(url_for("image_library.admin_page", **values))


@image_library_bp.route("/admin/image-library", methods=["GET", "POST"])
@login_required
def admin_page():
    guard = _admin_page_guard()
    if guard is not None:
        return guard

    if request.method == "POST":
        action = (request.form.get("action") or "").strip().lower()
        actor_user_id = int(current_user.id)

        if action == "toggle":
            row = image_library_repository.get_by_id(
                (request.form.get("asset_id") or "").strip()
            )
            if row is None:
                flash("Không tìm thấy image key cần cập nhật.", "danger")
                return _redirect_to_management()
            try:
                image_library_service.set_enabled(
                    row=row,
                    is_enabled=not bool(row.is_enabled),
                    actor_user_id=actor_user_id,
                )
            except image_library_service.ImageLibraryPersistenceError:
                flash("Không thể cập nhật trạng thái hình ảnh.", "danger")
            else:
                state_label = "bật" if row.is_enabled else "tắt"
                flash(f"Đã {state_label} image key “{row.image_key}”.", "success")
            return _redirect_to_management()

        if action not in {"create", "update"}:
            flash("Thao tác kho hình ảnh không hợp lệ.", "danger")
            return _redirect_to_management()

        row = None
        if action == "update":
            row = image_library_repository.get_by_id(
                (request.form.get("asset_id") or "").strip()
            )
            if row is None:
                flash("Không tìm thấy image key cần chỉnh sửa.", "danger")
                return _redirect_to_management()

        max_bytes = int(
            current_app.config.get(
                "IMAGE_LIBRARY_MAX_BYTES",
                current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 5 * 1024 * 1024),
            )
        )
        try:
            validated_upload = image_library_service.prepare_image_upload(
                request.files.get("image"),
                source_url=request.form.get("source_url") or "",
                max_bytes=max_bytes,
                max_pixels=int(
                    current_app.config.get(
                        "IMAGE_LIBRARY_MAX_PIXELS",
                        25_000_000,
                    )
                ),
                remote_timeout_seconds=float(
                    current_app.config.get(
                        "IMAGE_LIBRARY_REMOTE_FETCH_TIMEOUT_SECONDS",
                        6,
                    )
                ),
                remote_max_redirects=int(
                    current_app.config.get(
                        "IMAGE_LIBRARY_REMOTE_FETCH_MAX_REDIRECTS",
                        3,
                    )
                ),
                scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
                scan_enabled=bool(
                    current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)
                ),
            )
            if action == "create":
                row = image_library_service.create_image(
                    image_key=request.form.get("image_key") or request.form.get("name") or "",
                    description=request.form.get("description") or "",
                    is_enabled=parse_enabled_value(
                        request.form.get("is_enabled"),
                        default=False,
                    ),
                    tags=request.form.get("tags"),
                    source_url=request.form.get("source_url"),
                    validated_upload=validated_upload,
                    upload_root=_upload_root(),
                    actor_user_id=actor_user_id,
                )
            else:
                row = image_library_service.update_image(
                    row=row,
                    description=request.form.get("description") or "",
                    is_enabled=parse_enabled_value(
                        request.form.get("is_enabled"),
                        default=False,
                    ),
                    tags=request.form.get("tags") if "tags" in request.form else None,
                    source_url=request.form.get("source_url") if "source_url" in request.form else None,
                    validated_upload=validated_upload,
                    upload_root=_upload_root(),
                    actor_user_id=actor_user_id,
                )
        except RequestValidationError as exc:
            flash(str(exc), "danger")
            return _redirect_to_management(edit_id=row.id if row is not None else None)
        except image_library_service.ImageLibraryConflictError:
            flash("image_key này đã tồn tại. Hãy dùng key khác.", "warning")
            return _redirect_to_management()
        except image_library_service.ImageLibraryPersistenceError:
            flash("Không thể lưu hình ảnh. Vui lòng thử lại.", "danger")
            return _redirect_to_management(edit_id=row.id if row is not None else None)

        action_label = "tạo" if action == "create" else "cập nhật"
        flash(f"Đã {action_label} image key “{row.image_key}”.", "success")
        return _redirect_to_management()

    try:
        search_term = sanitize_query_text(
            request.args.get("q"),
            field_name="q",
            max_length=120,
        )
    except RequestValidationError as exc:
        flash(str(exc), "danger")
        search_term = ""
    tag = (request.args.get("tag") or "").strip().lower()
    status = (request.args.get("status") or "").strip().lower()
    if status not in VALID_STATUS_FILTERS:
        status = ""
    page = _parse_positive_int(request.args.get("page"), default=1, maximum=100000)
    per_page = _parse_positive_int(
        request.args.get("per_page"),
        default=DEFAULT_PAGE_SIZE,
        maximum=MAX_PAGE_SIZE,
    )
    assets_page = image_library_repository.list_assets(
        search_term=search_term,
        tag=tag,
        status=status,
        page=page,
        per_page=per_page,
    )
    edit_row = None
    edit_id = (request.args.get("edit") or "").strip()
    if edit_id:
        edit_row = image_library_repository.get_by_id(edit_id)
        if edit_row is None:
            flash("Không tìm thấy image key cần chỉnh sửa.", "warning")

    return serve_react_spa(
        "admin/image_library.html",
        page=assets_page,
        summary=image_library_repository.count_summary(),
        query=search_term,
        status=status or "all",
        edit_asset=edit_row,
        max_upload_bytes=int(
            current_app.config.get(
                "IMAGE_LIBRARY_MAX_BYTES",
                current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 5 * 1024 * 1024),
            )
        ),
    )


@image_library_bp.route("/api/image-library/<image_key>", methods=["GET"])
@login_required
def resolve_api(image_key: str):
    try:
        normalized_key = normalize_image_key(image_key)
        resolution = image_library_service.resolve_image(
            image_key=normalized_key,
            upload_root=_upload_root(),
        )
    except RequestValidationError as exc:
        return jsonify(
            {
                "error": exc.code,
                "message": str(exc),
                "field": exc.field,
            }
        ), exc.status
    stable_url = url_for(
        "image_library.image_content",
        image_key=normalized_key,
    )
    return jsonify(
        image_library_service.serialize_resolution(
            resolution,
            url=stable_url,
        )
    )


@image_library_bp.route("/media/library/<image_key>", methods=["GET"])
def image_content(image_key: str):
    normalized_key = ""
    try:
        normalized_key = normalize_image_key(image_key)
        resolution = image_library_service.resolve_image(
            image_key=normalized_key,
            upload_root=_upload_root(),
        )
    except RequestValidationError:
        resolution = None

    if resolution is None or resolution.is_fallback:
        return _send_fallback(
            image_key=normalized_key or "invalid",
            reason=resolution.fallback_reason if resolution is not None else "invalid_key",
        )
    return _send_image_file(
        file_path=resolution.file_path,
        mime_type=resolution.asset.mime_type,
        filename=resolution.asset.filename,
        image_key=resolution.asset.image_key,
        is_fallback=False,
    )


@image_library_bp.route("/admin/image-library/<asset_id>/preview", methods=["GET"])
@login_required
def admin_preview(asset_id: str):
    _require_admin_api()
    row = image_library_repository.get_by_id(asset_id)
    if row is None:
        abort(404)
    file_path = image_library_service.resolve_admin_preview(
        row=row,
        upload_root=_upload_root(),
    )
    if file_path is None:
        return _send_fallback(image_key=row.image_key, reason="missing_file")
    return _send_image_file(
        file_path=file_path,
        mime_type=row.mime_type,
        filename=row.filename,
        image_key=row.image_key,
        is_fallback=False,
    )


def _send_fallback(*, image_key: str, reason: str):
    fallback_path = _fallback_path()
    if not fallback_path.exists():
        abort(404)
    response = send_file(
        fallback_path,
        mimetype="image/svg+xml",
        conditional=True,
        max_age=300,
    )
    _apply_image_headers(
        response,
        image_key=image_key,
        is_fallback=True,
        fallback_reason=reason,
        filename="image-library-fallback.svg",
    )
    return response


def _send_image_file(
    *,
    file_path: Path | None,
    mime_type: str | None,
    filename: str | None,
    image_key: str,
    is_fallback: bool,
):
    if file_path is None:
        return _send_fallback(image_key=image_key, reason="missing_file")
    response = send_file(
        file_path,
        mimetype=mime_type or "application/octet-stream",
        conditional=True,
        max_age=300,
    )
    _apply_image_headers(
        response,
        image_key=image_key,
        is_fallback=is_fallback,
        fallback_reason=None,
        filename=filename,
    )
    return response


def _apply_image_headers(
    response,
    *,
    image_key: str,
    is_fallback: bool,
    fallback_reason: str | None,
    filename: str | None,
) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    # The URL is intentionally stable across replacements. Always revalidate so
    # existing deck references pick up a changed image on their next request.
    response.headers["Cache-Control"] = "private, no-cache, must-revalidate"
    response.headers["X-Flama-Image-Key"] = image_key
    response.headers["X-Flama-Image-Fallback"] = "1" if is_fallback else "0"
    if fallback_reason:
        response.headers["X-Flama-Image-Fallback-Reason"] = fallback_reason
    response.headers["Content-Disposition"] = (
        f'inline; filename="{build_safe_download_filename(filename, fallback_ext="svg")}"'
    )
