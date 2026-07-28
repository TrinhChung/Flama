"""Application service for safe flashcard media mutations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.validators import (
    RequestValidationError,
    resolve_safe_storage_path,
    validate_media_upload_request,
)
from models import db
from models.audit_log import AuditLog
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note


logger = logging.getLogger(__name__)


class MediaApiError(ValueError):
    def __init__(
        self,
        error: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error = error
        self.status = int(status)
        self.field = field


def upload_media(
    *,
    user_id: int,
    note_id: str,
    field_name: str,
    uploaded,
    upload_root: Path,
    max_bytes: int,
    scanner,
    scan_enabled: bool,
    markdown_inline: bool,
) -> tuple[dict[str, Any], int]:
    note = Note.query.filter_by(id=note_id, user_id=user_id).first()
    if note is None:
        raise MediaApiError(
            "FIELD_NOT_FOUND",
            "Note not found.",
            status=404,
        )
    normalized_field_name = str(field_name or "").strip()
    if not normalized_field_name:
        raise MediaApiError(
            "VALIDATION_ERROR",
            "field_name is required.",
            field="field_name",
        )
    field_def = FieldDef.query.filter_by(
        note_type_id=note.note_type_id,
        name=normalized_field_name,
    ).first()
    if field_def is None:
        raise MediaApiError(
            "FIELD_NOT_FOUND",
            "Field not found in note type.",
            status=404,
            field="field_name",
        )
    if markdown_inline:
        if field_def.field_type != "markdown":
            raise MediaApiError(
                "VALIDATION_ERROR",
                "Field is not markdown.",
                field="field_name",
            )
        upload_field_type = "image"
    else:
        if field_def.field_type not in {"image", "audio", "diagram"}:
            raise MediaApiError(
                "VALIDATION_ERROR",
                "Field does not accept media.",
                field="field_name",
            )
        upload_field_type = field_def.field_type
    try:
        validated = validate_media_upload_request(
            field_name_raw=normalized_field_name,
            field_type=upload_field_type,
            uploaded=uploaded,
            max_bytes=max_bytes,
            scanner=scanner,
            scan_enabled=scan_enabled,
        )
    except RequestValidationError as exc:
        raise MediaApiError(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        ) from exc

    existing = MediaAsset.query.filter_by(
        note_id=note.id,
        field_name=validated.field_name,
        sha256=validated.sha256,
    ).first()
    if existing:
        if not markdown_inline:
            values = dict(note.field_values or {})
            values[validated.field_name] = existing.id
            note.field_values = values
            db.session.commit()
        return _media_payload(existing, include_filename=markdown_inline), 200

    resolved_root = upload_root.resolve()
    relative_path = (
        Path(str(user_id)) / note.id / validated.storage_filename
    )
    try:
        full_path = resolve_safe_storage_path(
            upload_root=resolved_root,
            relative_path=relative_path,
        )
    except RequestValidationError as exc:
        raise MediaApiError(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        ) from exc
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(validated.content)
    asset = MediaAsset(
        note_id=note.id,
        field_name=validated.field_name,
        filename=validated.safe_original_filename,
        mime_type=validated.mime_type,
        storage_path=str(relative_path).replace("\\", "/"),
        sha256=validated.sha256,
        size_bytes=validated.size_bytes,
    )
    try:
        db.session.add(asset)
        db.session.flush()
        if not markdown_inline:
            values = dict(note.field_values or {})
            values[validated.field_name] = asset.id
            note.field_values = values
        db.session.add(
            AuditLog(
                user_id=user_id,
                action=(
                    "media.upload.inline"
                    if markdown_inline
                    else "media.upload"
                ),
                payload={
                    "note_id": note.id,
                    "asset_id": asset.id,
                    "field_name": validated.field_name,
                },
            )
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        try:
            full_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to compensate media file %s", full_path)
        raise
    return _media_payload(asset, include_filename=markdown_inline), 201


def delete_media(
    *,
    user_id: int,
    asset_id: str,
    upload_root: Path,
) -> dict[str, bool]:
    asset = (
        MediaAsset.query.join(Note, MediaAsset.note_id == Note.id)
        .filter(MediaAsset.id == asset_id, Note.user_id == user_id)
        .first()
    )
    if asset is None:
        raise MediaApiError(
            "FIELD_NOT_FOUND",
            "Media asset not found.",
            status=404,
        )
    try:
        full_path = resolve_safe_storage_path(
            upload_root=upload_root.resolve(),
            relative_path=Path(asset.storage_path),
        )
    except RequestValidationError:
        full_path = None
    note = asset.note
    values = dict(note.field_values or {})
    if values.get(asset.field_name) == asset.id:
        values[asset.field_name] = ""
        note.field_values = values
    db.session.delete(asset)
    db.session.add(
        AuditLog(
            user_id=user_id,
            action="media.delete",
            payload={"asset_id": asset.id, "note_id": note.id},
        )
    )
    db.session.commit()
    if full_path is not None and full_path.exists():
        try:
            full_path.unlink()
        except OSError:
            logger.warning("Failed to delete media file %s", full_path)
    return {"success": True}


def _media_payload(
    asset: MediaAsset,
    *,
    include_filename: bool,
) -> dict[str, Any]:
    payload = {
        "asset_id": asset.id,
        "url": f"/media/proxy/{asset.id}",
        "field_name": asset.field_name,
    }
    if include_filename:
        payload["filename"] = asset.filename
    return payload
