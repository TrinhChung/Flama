"""Attach staged Go media using authenticated metadata and private commit messages.

File bytes stay on the media worker. This service participates in its caller's
database transaction; callers report success only after worker acknowledgement.
"""
from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

from app.services import flama_media_client, quota_service
from app.services.media_field_codec import store_media_url
from app.validators import RequestValidationError
from models import db
from models.audit_log import AuditLog
from models.media_asset import MediaAsset
from models.note import Note

STAGE_ID = re.compile(r"^stg_[a-f0-9]{32}$")
STAGED_URL = re.compile(r'''(?:https?://[^/\s<>"'()]+)?/media/staged/(stg_[a-f0-9]{32})(?![A-Za-z0-9_-])''')
CAS_PATH = re.compile(r"^[a-f0-9]{2}/[a-f0-9]{2}/[a-f0-9]{64}\.(?:png|jpg|jpeg|gif|webp|mp3|wav|ogg|webm)$")
WORKER_PREFIX = "worker:"


def enabled() -> bool:
    return bool(current_app.config.get("FLAMA_MEDIA_DIRECT_UPLOAD_ENABLED"))


def public_base() -> str:
    base = str(current_app.config.get("FLAMA_MEDIA_PUBLIC_URL") or "").rstrip("/")
    parts = urlsplit(base)
    local = parts.hostname in {"127.0.0.1", "localhost", "::1"}
    if not parts.netloc or parts.username or parts.password or parts.query or parts.fragment or parts.path or (
        parts.scheme != "https" and not (parts.scheme == "http" and local)
    ):
        raise RequestValidationError("Media public URL is not configured.", code="MEDIA_NOT_CONFIGURED", status=503)
    return base


def upload_ticket(*, user_id: int, payload: Any) -> dict[str, Any]:
    if not enabled():
        raise RequestValidationError("Direct media uploads are not configured.", code="MEDIA_NOT_CONFIGURED", status=503)
    if not isinstance(payload, dict):
        raise RequestValidationError("Payload must be a JSON object.")
    note_id = payload.get("note_id")
    if note_id:
        note = Note.query.filter_by(id=str(note_id), user_id=user_id).first()
        if note is None:
            raise RequestValidationError("Note not found or not editable.", code="FIELD_NOT_FOUND", status=404)
        field_name = str(payload.get("field_name") or "").strip()
        if field_name and not any(field.name == field_name for field in note.note_type.field_defs):
            raise RequestValidationError("Field not found.", field="field_name", code="FIELD_NOT_FOUND", status=404)
    base = public_base()
    limit = int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 20 * 1024 * 1024))
    ttl = 3600
    try:
        ticket = flama_media_client.generate_upload_ticket(user_id=user_id, max_bytes=limit, ttl_seconds=ttl)
    except flama_media_client.FlamaMediaClientError as exc:
        raise _worker_error(exc) from exc
    return {"ticket": ticket, "upload_url": f"{base}/media/upload", "upload_zip_url": f"{base}/media/upload-zip",
            "expires_at": int(time.time()) + ttl, "max_bytes": limit,
            "staging_ttl_seconds": int(current_app.config.get("FLAMA_MEDIA_STAGING_TTL_SECONDS", 86400))}


def _worker_error(exc: flama_media_client.FlamaMediaClientError) -> RequestValidationError:
    return RequestValidationError(exc.message, code=exc.error_code, status=exc.status_code)


def _control(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return flama_media_client.internal_request(path, payload)
    except flama_media_client.FlamaMediaClientError as exc:
        raise _worker_error(exc) from exc


def _references(value: Any):
    if isinstance(value, list):
        for item in value:
            yield from _references(item)
    elif isinstance(value, str):
        yield from STAGED_URL.finditer(value)


def _validate_stage_paths(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            _validate_stage_paths(item)
    elif isinstance(value, str) and "/media/staged/" in STAGED_URL.sub("", value):
        raise RequestValidationError("Invalid staged media URL.", code="INVALID_MEDIA_STAGE")


def has_staged_urls(values: Any) -> bool:
    if isinstance(values, dict):
        return any(has_staged_urls(value) for value in values.values())
    return any(_references(values))


def _replace(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, list):
        return [_replace(item, replacements) for item in value]
    if isinstance(value, str):
        return STAGED_URL.sub(lambda match: replacements[match.group(1)], value)
    return value


def commit_field_values(*, user_id: int, note_id: str, field_values: dict[str, Any]) -> dict[str, Any]:
    """Promote only referenced stages, preserving native arrays and inline markup."""
    for value in field_values.values():
        _validate_stage_paths(value)
    refs = {name: list(_references(value)) for name, value in field_values.items()}
    if not any(refs.values()):
        return field_values
    if not enabled():
        raise RequestValidationError("Direct media storage is not configured.", code="MEDIA_NOT_CONFIGURED", status=503)
    base = public_base()
    for matches in refs.values():
        for match in matches:
            absolute = urlsplit(match.group(0))
            if absolute.netloc and f"{absolute.scheme}://{absolute.netloc}" != base:
                raise RequestValidationError("Untrusted staged media origin.", code="INVALID_MEDIA_ORIGIN")
    note = db.session.get(Note, note_id)
    if note is None or note.user_id != user_id:
        raise RequestValidationError("Note not found or not editable.", code="FIELD_NOT_FOUND", status=404)
    stage_ids = list(dict.fromkeys(match.group(1) for matches in refs.values() for match in matches))
    inspected = _control("/media/staged/inspect", {"user_id": user_id, "stage_ids": stage_ids})
    items = inspected.get("items")
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise RequestValidationError("Invalid media metadata.", code="MEDIA_WORKER_ERROR", status=502)
    metadata = {item.get("stage_id"): item for item in items}
    if set(metadata) != set(stage_ids):
        raise RequestValidationError("Staged media is missing or expired.", code="MEDIA_STAGE_NOT_FOUND", status=410)
    field_types = {field.name: field.field_type for field in note.note_type.field_defs}
    plans: list[dict[str, str]] = []
    replaced = dict(field_values)
    from app.repositories.media_field_identity_repository import find_note_field_media
    for field_name, matches in refs.items():
        replacements: dict[str, str] = {}
        for match in matches:
            stage_id = match.group(1)
            if stage_id in replacements:
                continue
            item = metadata[stage_id]
            mime = str(item.get("content_type") or "")
            sha = str(item.get("sha256") or "")
            relative = str(item.get("relative_path") or "")
            size = item.get("size_bytes")
            if (not re.fullmatch(r"[a-f0-9]{64}", sha) or not CAS_PATH.fullmatch(relative)
                    or relative.split("/")[-1].split(".")[0] != sha
                    or type(size) is not int or size <= 0):
                raise RequestValidationError("Invalid media metadata.", code="MEDIA_WORKER_ERROR", status=502)
            kind = field_types.get(field_name)
            if kind not in {"image", "diagram", "audio", "markdown", "array", "text", "textarea"}:
                raise RequestValidationError("Field does not accept media.", field=field_name)
            if (kind == "audio" and not mime.startswith("audio/")) or (
                kind in {"image", "diagram", "markdown"} and not mime.startswith("image/")
            ):
                raise RequestValidationError("Media does not match field type.", field=field_name, code="INVALID_MEDIA_TYPE")
            if mime not in {"image/png", "image/jpeg", "image/gif", "image/webp", "audio/mpeg", "audio/wav", "audio/ogg", "audio/webm"}:
                raise RequestValidationError("Unsupported media type.", field=field_name)
            asset = find_note_field_media(note_id=note_id, field_name=field_name, sha256=sha, note=note)
            if asset is None:
                quota = quota_service.consume_media(user_id, size)
                if not quota.allowed:
                    raise RequestValidationError(quota.message, field=field_name, code="MEDIA_QUOTA_EXCEEDED", status=429)
                filename = secure_filename(str(item.get("filename") or "")) or relative.rsplit("/", 1)[-1]
                asset = MediaAsset(id=str(uuid4()), note_id=note_id, field_name=field_name,
                    filename=filename[:255], mime_type=mime, storage_path=f"{WORKER_PREFIX}{relative}",
                    sha256=sha, size_bytes=size)
                db.session.add(asset)
                db.session.flush()
                # Keep the already-loaded relationship current for rendering this response.
                if asset not in note.media_assets:
                    note.media_assets.append(asset)
                db.session.add(AuditLog(user_id=user_id, action="media.staged.committed",
                    payload={"note_id": note_id, "asset_id": asset.id, "field_name": field_name, "stage_id": stage_id}))
            # CAS duplicates from legacy storage keep their existing URL without moving the legacy file.
            if str(asset.storage_path).startswith(WORKER_PREFIX) and not any(plan["asset_id"] == asset.id for plan in plans):
                plans.append({"stage_id": stage_id, "asset_id": asset.id})
            replacements[stage_id] = store_media_url(asset.id)
        replaced[field_name] = _replace(field_values[field_name], replacements)
    if plans:
        result = _control("/media/commit", {"user_id": user_id, "items": plans})
        receipts = result.get("items")
        if not isinstance(receipts, list) or {(item.get("stage_id"), item.get("asset_id")) for item in receipts if isinstance(item, dict)} != {
            (item["stage_id"], item["asset_id"]) for item in plans
        }:
            raise RequestValidationError("Media commit was not acknowledged.", code="MEDIA_COMMIT_FAILED", status=502)
    return replaced


def attach(*, user_id: int, note_id: str, payload: Any, markdown_inline: bool = False) -> tuple[dict[str, Any], int]:
    """Explicit-save media clients (for example generated audio) attach JSON receipts."""
    if not isinstance(payload, dict):
        raise RequestValidationError("Payload must be a JSON object.")
    field_name, stage_id = str(payload.get("field_name") or "").strip(), str(payload.get("stage_id") or "")
    if not field_name or not STAGE_ID.fullmatch(stage_id):
        raise RequestValidationError("field_name and a valid stage_id are required.")
    note = Note.query.filter_by(id=note_id, user_id=user_id).first()
    if note is None:
        raise RequestValidationError("Note not found or not editable.", code="FIELD_NOT_FOUND", status=404)
    field = next((field for field in note.note_type.field_defs if field.name == field_name), None)
    if field is None or (field.field_type != "markdown" if markdown_inline else field.field_type not in {"image", "audio", "diagram"}):
        raise RequestValidationError("Field does not accept this media.", field="field_name")
    try:
        values = commit_field_values(user_id=user_id, note_id=note_id, field_values={field_name: f"/media/staged/{stage_id}"})
        url = values[field_name]
        asset_id = url.rsplit("/", 1)[-1]
        if not markdown_inline:
            from app.services import deck_working_tree_service
            note.field_values = {**(note.field_values or {}), field_name: url}
            deck_working_tree_service.mark_note_fields_changed(note=note, field_names={field_name})
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    asset = db.session.get(MediaAsset, asset_id)
    return {"asset_id": asset_id, "url": url, "field_name": field_name, "filename": asset.filename}, 201


def attach_batch(*, user_id: int, payload: Any) -> dict[str, Any]:
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not 1 <= len(items) <= 100 or not all(isinstance(item, dict) for item in items):
        raise RequestValidationError("items must contain between 1 and 100 media receipts.")
    results = []
    for index, item in enumerate(items):
        result = {"item_id": str(item.get("item_id", index)), "note_id": str(item.get("note_id") or ""),
                  "field_name": str(item.get("field_name") or "")}
        try:
            attached, _status = attach(user_id=user_id, note_id=result["note_id"], payload=item,
                markdown_inline=item.get("markdown_inline") is True)
            result.update(attached, status="success")
        except RequestValidationError as exc:
            db.session.rollback()
            result.update(status="failed", error=exc.code, message=str(exc))
        results.append(result)
    succeeded = sum(item["status"] == "success" for item in results)
    return {"success": True, "success_count": succeeded, "failed_count": len(results) - succeeded, "items": results}


def inspect_assets(asset_ids: list[str]) -> dict[str, bool]:
    """Check permanent worker files in bounded batches without downloading bytes."""
    found = {}
    for offset in range(0, len(asset_ids), 500):
        batch = asset_ids[offset:offset + 500]
        response = _control("/media/assets/inspect", {"asset_ids": batch})
        items = response.get("items")
        if not isinstance(items, list) or {item.get("asset_id") for item in items if isinstance(item, dict)} != set(batch):
            raise RequestValidationError("Invalid media integrity response.", code="MEDIA_WORKER_ERROR", status=502)
        for item in items:
            if type(item.get("exists")) is not bool or type(item.get("size_bytes")) is not int:
                raise RequestValidationError("Invalid media integrity response.", code="MEDIA_WORKER_ERROR", status=502)
            found[item["asset_id"]] = item["exists"] and item["size_bytes"] > 0
    return found
