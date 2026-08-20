"""Application service for safe flashcard media mutations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.services import deck_working_tree_service
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
            if values.get(validated.field_name) != existing.id:
                values[validated.field_name] = existing.id
                note.field_values = values
                deck_working_tree_service.mark_note_field_batches_changed(
                    mutations=[
                        {
                            "note": note,
                            "field_names": {validated.field_name},
                            "operation": "set",
                        }
                    ],
                )
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
            deck_working_tree_service.mark_note_field_batches_changed(
                mutations=[
                    {
                        "note": note,
                        "field_names": {validated.field_name},
                        "operation": "set",
                    }
                ],
            )
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


def upload_media_batch(
    *,
    user_id: int,
    items: list[dict[str, Any]],
    upload_root: Path,
    max_bytes: int,
    scanner=None,
    scan_enabled: bool = False,
) -> dict[str, Any]:
    """Upload a batch of media files across multiple notes with a single DB transaction."""
    if not items:
        return {"success": True, "success_count": 0, "failed_count": 0, "items": []}

    note_ids = list({str(it.get("note_id") or "").strip() for it in items if it.get("note_id")})
    if not note_ids:
        raise MediaApiError("VALIDATION_ERROR", "No valid note_ids provided in batch.")

    notes = Note.query.filter(Note.id.in_(note_ids), Note.user_id == user_id).all()
    note_map = {n.id: n for n in notes}

    note_type_ids = {n.note_type_id for n in notes if n.note_type_id}
    field_defs = FieldDef.query.filter(FieldDef.note_type_id.in_(note_type_ids)).all()
    field_def_map = {
        (f.note_type_id, (f.name or "").strip().lower()): f
        for f in field_defs
    }

    existing_assets = MediaAsset.query.filter(MediaAsset.note_id.in_(note_ids)).all()
    existing_map: dict[tuple[str, str, str], MediaAsset] = {
        (a.note_id, a.field_name, a.sha256): a
        for a in existing_assets
    }

    resolved_root = upload_root.resolve()
    created_file_paths: list[Path] = []
    results: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0
    dirty_field_names_by_note_id: dict[str, set[str]] = {}

    try:
        for idx, item in enumerate(items):
            item_id = str(item.get("item_id") if item.get("item_id") is not None else idx)
            raw_note_id = str(item.get("note_id") or "").strip()
            raw_field_name = str(item.get("field_name") or "").strip()
            uploaded = item.get("uploaded")
            markdown_inline = bool(item.get("markdown_inline", False))

            note = note_map.get(raw_note_id)
            if note is None:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": "FIELD_NOT_FOUND",
                    "message": "Note not found.",
                })
                failed_count += 1
                continue

            if not raw_field_name:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": "VALIDATION_ERROR",
                    "message": "field_name is required.",
                })
                failed_count += 1
                continue

            field_def = field_def_map.get((note.note_type_id, raw_field_name.lower()))
            if field_def is None:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": "FIELD_NOT_FOUND",
                    "message": "Field not found in note type.",
                })
                failed_count += 1
                continue

            if markdown_inline:
                if field_def.field_type != "markdown":
                    results.append({
                        "item_id": item_id,
                        "note_id": raw_note_id,
                        "field_name": raw_field_name,
                        "status": "failed",
                        "error": "VALIDATION_ERROR",
                        "message": "Field is not markdown.",
                    })
                    failed_count += 1
                    continue
                upload_field_type = "image"
            else:
                if field_def.field_type not in {"image", "audio", "diagram"}:
                    results.append({
                        "item_id": item_id,
                        "note_id": raw_note_id,
                        "field_name": raw_field_name,
                        "status": "failed",
                        "error": "VALIDATION_ERROR",
                        "message": "Field does not accept media.",
                    })
                    failed_count += 1
                    continue
                upload_field_type = field_def.field_type

            try:
                validated = validate_media_upload_request(
                    field_name_raw=raw_field_name,
                    field_type=upload_field_type,
                    uploaded=uploaded,
                    max_bytes=max_bytes,
                    scanner=scanner,
                    scan_enabled=scan_enabled,
                )
            except RequestValidationError as exc:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": exc.code,
                    "message": str(exc),
                })
                failed_count += 1
                continue

            existing_key = (note.id, validated.field_name, validated.sha256)
            existing = existing_map.get(existing_key)
            if existing:
                if not markdown_inline:
                    values = dict(note.field_values or {})
                    if values.get(validated.field_name) != existing.id:
                        values[validated.field_name] = existing.id
                        note.field_values = values
                        dirty_field_names_by_note_id.setdefault(note.id, set()).add(
                            validated.field_name
                        )
                payload = _media_payload(existing, include_filename=markdown_inline)
                payload["item_id"] = item_id
                payload["status"] = "success"
                results.append(payload)
                success_count += 1
                continue

            relative_path = (
                Path(str(user_id)) / note.id / validated.storage_filename
            )
            try:
                full_path = resolve_safe_storage_path(
                    upload_root=resolved_root,
                    relative_path=relative_path,
                )
            except RequestValidationError as exc:
                results.append({
                    "item_id": item_id,
                    "note_id": raw_note_id,
                    "field_name": raw_field_name,
                    "status": "failed",
                    "error": exc.code,
                    "message": str(exc),
                })
                failed_count += 1
                continue

            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(validated.content)
            created_file_paths.append(full_path)

            asset = MediaAsset(
                note_id=note.id,
                field_name=validated.field_name,
                filename=validated.safe_original_filename,
                mime_type=validated.mime_type,
                storage_path=str(relative_path).replace("\\", "/"),
                sha256=validated.sha256,
                size_bytes=validated.size_bytes,
            )
            db.session.add(asset)
            db.session.flush()
            existing_map[existing_key] = asset

            if not markdown_inline:
                values = dict(note.field_values or {})
                values[validated.field_name] = asset.id
                note.field_values = values
                dirty_field_names_by_note_id.setdefault(note.id, set()).add(
                    validated.field_name
                )

            db.session.add(
                AuditLog(
                    user_id=user_id,
                    action=(
                        "media.upload.batch.inline"
                        if markdown_inline
                        else "media.upload.batch"
                    ),
                    payload={
                        "note_id": note.id,
                        "asset_id": asset.id,
                        "field_name": validated.field_name,
                    },
                )
            )
            payload = _media_payload(asset, include_filename=markdown_inline)
            payload["item_id"] = item_id
            payload["status"] = "success"
            results.append(payload)
            success_count += 1

        deck_working_tree_service.mark_note_field_batches_changed(
            mutations=[
                {
                    "note": note_map[note_id],
                    "field_names": field_names,
                    "operation": "set",
                }
                for note_id, field_names in dirty_field_names_by_note_id.items()
            ],
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        for p in created_file_paths:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                logger.warning("Failed to compensate media file %s", p)
        raise

    return {
        "success": True,
        "success_count": success_count,
        "failed_count": failed_count,
        "items": results,
    }


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
    cleared_field = False
    if values.get(asset.field_name) == asset.id:
        values[asset.field_name] = ""
        note.field_values = values
        cleared_field = True
    db.session.delete(asset)
    db.session.add(
        AuditLog(
            user_id=user_id,
            action="media.delete",
            payload={"asset_id": asset.id, "note_id": note.id},
        )
    )
    if cleared_field:
        deck_working_tree_service.mark_note_field_batches_changed(
            mutations=[
                {
                    "note": note,
                    "field_names": {asset.field_name},
                    "operation": "set",
                }
            ],
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
