"""Media staging service for temporary clipboard image paste with 30m TTL in Redis."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import re
import threading
from typing import Any
from uuid import uuid4

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.services import quota_service, redis_state_service
from app.services.image_processor import process_image_preset
from app.services.image_security_service import validate_image_security
from app.validators import RequestValidationError, resolve_safe_storage_path
from models import db
from models.audit_log import AuditLog
from models.field_types import stored_field_value
from models.media_asset import MediaAsset
from models.note import Note
from app.services.media_field_codec import store_media_url

logger = logging.getLogger(__name__)

STAGE_TTL_SECONDS = 1800  # 30 minutes
STAGE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_STAGED_URL_RE = re.compile(r"/media/staged/([A-Za-z0-9_-]{8,64})")

_LOCK = threading.Lock()
_MEMORY_STAGE_STORE: dict[str, dict[str, Any]] = {}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _upload_root() -> Path:
    if current_app:
        return Path(current_app.config.get("FLASHCARD_MEDIA_UPLOAD_ROOT", "media")).resolve()
    return Path("media").resolve()


def _redis_key(stage_id: str) -> str:
    return redis_state_service.private_key("media-stage", stage_id)


def _cleanup_memory_store(now: datetime) -> None:
    expired_keys = [
        k for k, v in _MEMORY_STAGE_STORE.items()
        if datetime.fromisoformat(v["expires_at"]) <= now
    ]
    for k in expired_keys:
        _MEMORY_STAGE_STORE.pop(k, None)


def stage_pasted_image(
    *,
    user_id: int,
    file: Any = None,
    base64_data: str | bytes | None = None,
    source_ip: str | None = None,
    upload_root: Path | None = None,
) -> dict[str, Any]:
    """Validate, sanitize, resize/optimize to WebP, and stage image temporarily in Redis."""
    raw_bytes: bytes
    if file is not None and getattr(file, "filename", ""):
        raw_bytes = file.read()
    elif base64_data:
        if isinstance(base64_data, str):
            b64_str = base64_data.strip()
            if "," in b64_str and "base64" in b64_str.split(",", 1)[0]:
                b64_str = b64_str.split(",", 1)[1]
            try:
                raw_bytes = base64.b64decode(b64_str, validate=True)
            except Exception as exc:
                raise RequestValidationError(
                    "Dữ liệu ảnh base64 không hợp lệ.",
                    field="base64_data",
                    code="IMAGE_BASE64_INVALID",
                    status=400,
                ) from exc
        elif isinstance(base64_data, bytes):
            raw_bytes = base64_data
        else:
            raise RequestValidationError("Dữ liệu ảnh không hợp lệ.", field="base64_data")
    else:
        raise RequestValidationError("Vui lòng cung cấp tệp ảnh hoặc dữ liệu base64.", field="image")

    # 1. Malware and threat security check
    max_bytes = int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024)) if current_app else 10 * 1024 * 1024
    detected_mime, _, _ = validate_image_security(
        raw_bytes,
        filename="pasted_clipboard",
        max_bytes=max_bytes,
        user_id=user_id,
        source_ip=source_ip,
        field_name="image",
    )

    # 2. Resize and optimize to WebP (max 1600x1600 fit, stripped metadata, quality 90)
    processed = process_image_preset(
        raw_bytes,
        preset_name="note_image",
        usage_type="flashcard_media",
    )

    quota = quota_service.consume_media(user_id, processed.size_bytes)
    if not quota.allowed:
        raise RequestValidationError(quota.message, field="image", code="MEDIA_QUOTA_EXCEEDED", status=429)

    # 3. Store in temporary staging directory
    root = (upload_root or _upload_root()).resolve()
    stage_id = f"stg_{uuid4().hex}"
    relative_path = Path("staging") / f"{stage_id}.webp"
    full_path = resolve_safe_storage_path(
        upload_root=root,
        relative_path=relative_path,
    )
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(processed.content)

    now = _now_utc()
    expires_at = now + timedelta(seconds=STAGE_TTL_SECONDS)
    metadata = {
        "stage_id": stage_id,
        "user_id": user_id,
        "storage_path": str(relative_path).replace("\\", "/"),
        "sha256": processed.sha256,
        "size_bytes": processed.size_bytes,
        "mime_type": "image/webp",
        "width": processed.width,
        "height": processed.height,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    # 4. Save metadata with TTL in Redis and memory fallback
    with _LOCK:
        _cleanup_memory_store(now)
        _MEMORY_STAGE_STORE[stage_id] = metadata

    mode = redis_state_service.backend_mode("MEDIA_STAGING_BACKEND")
    if mode != "local":
        try:
            redis_state_service.redis_client().set(
                _redis_key(stage_id),
                json.dumps(metadata, separators=(",", ":")),
                ex=STAGE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("Redis media stage cache set failed, relying on local store: %s", exc)

    staged_url = f"/media/staged/{stage_id}"
    return {
        "stage_id": stage_id,
        "url": staged_url,
        "mime_type": "image/webp",
        "width": processed.width,
        "height": processed.height,
        "size_bytes": processed.size_bytes,
        "expires_in_seconds": STAGE_TTL_SECONDS,
    }


def get_staged_media(stage_id: str, *, upload_root: Path | None = None) -> tuple[Path, str] | None:
    """Retrieve file path and MIME type of an active staged media asset."""
    if not stage_id or not STAGE_ID_PATTERN.fullmatch(stage_id):
        return None

    root = (upload_root or _upload_root()).resolve()
    record: dict[str, Any] | None = None

    # Check Redis first if enabled
    mode = redis_state_service.backend_mode("MEDIA_STAGING_BACKEND")
    if mode != "local":
        try:
            raw = redis_state_service.redis_client().get(_redis_key(stage_id))
            if raw:
                record = json.loads(raw)
        except Exception:
            pass

    # Fallback to in-memory store
    if record is None:
        with _LOCK:
            record = _MEMORY_STAGE_STORE.get(stage_id)

    # If still not found, check file existence on disk with fallback timestamp
    target_rel = Path("staging") / f"{stage_id}.webp"
    try:
        full_path = resolve_safe_storage_path(upload_root=root, relative_path=target_rel)
    except RequestValidationError:
        return None

    if not full_path.exists() or not full_path.is_file():
        return None

    # Verify TTL
    if record:
        expires_at = datetime.fromisoformat(record["expires_at"])
        if expires_at <= _now_utc():
            try:
                full_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None
    else:
        # Check disk mtime fallback
        mtime = datetime.fromtimestamp(full_path.stat().st_mtime, tz=timezone.utc).replace(tzinfo=None)
        if (_now_utc() - mtime).total_seconds() > STAGE_TTL_SECONDS:
            try:
                full_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    return full_path, record.get("mime_type", "image/webp") if record else "image/webp"


def commit_staged_media(
    stage_id: str,
    *,
    user_id: int,
    note_id: str,
    field_name: str,
    upload_root: Path | None = None,
) -> str | None:
    """Commit a staged image into a permanent MediaAsset for the specified Note.
    
    Returns:
        The permanent canonical store URL (store_media_url(asset.id))
    """
    if not stage_id or not STAGE_ID_PATTERN.fullmatch(stage_id):
        return None

    root = (upload_root or _upload_root()).resolve()
    staged_info = get_staged_media(stage_id, upload_root=root)
    if staged_info is None:
        logger.warning("Attempted to commit nonexistent or expired staged media: %s", stage_id)
        return None

    staged_path, mime_type = staged_info
    content = staged_path.read_bytes()

    # Look up metadata from Redis/memory
    record: dict[str, Any] | None = None
    mode = redis_state_service.backend_mode("MEDIA_STAGING_BACKEND")
    if mode != "local":
        try:
            raw = redis_state_service.redis_client().get(_redis_key(stage_id))
            if raw:
                record = json.loads(raw)
        except Exception:
            pass
    if record is None:
        with _LOCK:
            record = _MEMORY_STAGE_STORE.get(stage_id)

    sha256_hash = record.get("sha256") if record else None
    if not sha256_hash:
        import hashlib
        sha256_hash = hashlib.sha256(content).hexdigest()

    # Destination in user/note media directory
    storage_fn = f"paste_{sha256_hash[:16]}.webp"
    relative_path = Path(str(user_id)) / note_id / storage_fn
    full_path = resolve_safe_storage_path(upload_root=root, relative_path=relative_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)

    from app.repositories.media_field_identity_repository import find_note_field_media
    existing = find_note_field_media(
        note_id=note_id,
        field_name=field_name,
        sha256=sha256_hash,
    )

    if existing:
        asset = existing
    else:
        asset = MediaAsset(
            note_id=note_id,
            field_name=field_name,
            filename=f"pasted_{stage_id[4:12]}.webp",
            mime_type=mime_type,
            storage_path=str(relative_path).replace("\\", "/"),
            sha256=sha256_hash,
            size_bytes=len(content),
        )
        db.session.add(asset)
        db.session.flush()
        db.session.add(
            AuditLog(
                user_id=user_id,
                action="media.staged.committed",
                payload={
                    "note_id": note_id,
                    "asset_id": asset.id,
                    "field_name": field_name,
                    "stage_id": stage_id,
                },
            )
        )

    # Clean up staged file and keys
    try:
        staged_path.unlink(missing_ok=True)
    except OSError:
        pass

    with _LOCK:
        _MEMORY_STAGE_STORE.pop(stage_id, None)

    if mode != "local":
        try:
            redis_state_service.redis_client().delete(_redis_key(stage_id))
        except Exception:
            pass

    return store_media_url(asset.id)


def commit_all_staged_urls_in_field_values(
    *,
    user_id: int,
    note_id: str,
    field_values: dict[str, Any] | None,
    upload_root: Path | None = None,
) -> dict[str, Any]:
    """Scan field_values, commit any /media/staged/<stage_id> to MediaAsset, and replace URLs."""
    if not field_values:
        return {}

    from app.services import worker_media_service
    if worker_media_service.enabled():
        return worker_media_service.commit_field_values(
            user_id=user_id, note_id=note_id, field_values=field_values,
        )

    updated: dict[str, Any] = {}
    for field_name, val in field_values.items():
        if not val or not isinstance(val, str):
            # Array items are plain text and never hold staged media URLs.
            updated[field_name] = stored_field_value(val)
            continue

        text_val = str(val)
        matches = _STAGED_URL_RE.findall(text_val)
        if not matches:
            updated[field_name] = text_val
            continue

        new_val = text_val
        for stage_id in matches:
            committed_url = commit_staged_media(
                stage_id,
                user_id=user_id,
                note_id=note_id,
                field_name=field_name,
                upload_root=upload_root,
            )
            if committed_url:
                new_val = new_val.replace(f"/media/staged/{stage_id}", committed_url)

        updated[field_name] = new_val

    return updated


def cleanup_expired_staged_media(max_age_seconds: int = STAGE_TTL_SECONDS, upload_root: Path | None = None) -> int:
    """Clean up orphan staging files older than max_age_seconds."""
    root = (upload_root or _upload_root()).resolve()
    staging_dir = root / "staging"
    if not staging_dir.exists() or not staging_dir.is_dir():
        return 0

    now = _now_utc()
    deleted_count = 0
    for child in staging_dir.iterdir():
        if not child.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc).replace(tzinfo=None)
            if (now - mtime).total_seconds() > max_age_seconds:
                child.unlink(missing_ok=True)
                deleted_count += 1
        except OSError:
            pass

    return deleted_count
