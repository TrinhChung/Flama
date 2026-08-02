"""Safe staging and attachment of MP3 audio received from Yomitan."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import io
from pathlib import Path
import re
from uuid import uuid4

from flask import current_app
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

from app.validators.flashcard_input import (
    RequestValidationError,
    resolve_safe_storage_path,
    validate_media_upload_request,
)
from models import db
from models.audit_log import AuditLog
from models.connect_pending_media import ConnectPendingMedia
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType


YOMITAN_MP3_FILENAME_RE = re.compile(
    r"^yomitan_audio_[A-Za-z0-9_-]{8,96}\.mp3$",
    flags=re.IGNORECASE,
)
SOUND_REFERENCE_RE = re.compile(
    r"^\[sound:(yomitan_audio_[A-Za-z0-9_-]{8,96}\.mp3)\]$",
    flags=re.IGNORECASE,
)


class ConnectMediaError(ValueError):
    pass


@dataclass(frozen=True)
class MaterializedMedia:
    final_paths: tuple[Path, ...]
    pending_paths: tuple[Path, ...]


def _utcnow() -> datetime:
    return datetime.utcnow()


def _config_int(name: str, default: int) -> int:
    return max(1, int(current_app.config.get(name, default)))


def _upload_root() -> Path:
    return Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()


def _safe_path(relative_path: str | Path) -> Path:
    try:
        return resolve_safe_storage_path(
            upload_root=_upload_root(),
            relative_path=Path(relative_path),
        )
    except RequestValidationError as exc:
        raise ConnectMediaError("Đường dẫn media không hợp lệ.") from exc


def _unlink_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Unable to remove Flama Connect media file: %s", path)


def _purge_expired() -> None:
    expired = (
        ConnectPendingMedia.query.filter(ConnectPendingMedia.expires_at <= _utcnow())
        .order_by(ConnectPendingMedia.expires_at.asc())
        .limit(100)
        .all()
    )
    if not expired:
        return
    paths: list[Path] = []
    for row in expired:
        try:
            paths.append(_safe_path(row.storage_path))
        except ConnectMediaError:
            pass
        db.session.delete(row)
    db.session.commit()
    for path in paths:
        _unlink_quietly(path)


def _decode_base64_audio(raw_data: object, *, max_bytes: int) -> bytes:
    if not isinstance(raw_data, str) or not raw_data:
        raise ConnectMediaError("Dữ liệu audio base64 là bắt buộc.")
    max_encoded_length = ((max_bytes + 2) // 3) * 4
    if len(raw_data) > max_encoded_length + 4:
        raise ConnectMediaError(f"Audio vượt quá giới hạn {max_bytes} byte.")
    try:
        content = base64.b64decode(raw_data, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ConnectMediaError("Dữ liệu audio không phải base64 hợp lệ.") from exc
    if len(content) > max_bytes:
        raise ConnectMediaError(f"Audio vượt quá giới hạn {max_bytes} byte.")
    return content


def stage_mp3(*, user_id: int, filename: object, data: object) -> str:
    if not isinstance(filename, str) or not YOMITAN_MP3_FILENAME_RE.fullmatch(filename):
        raise ConnectMediaError("Flama Connect chỉ nhận file MP3 do Yomitan tạo.")

    max_bytes = _config_int("CONNECT_MEDIA_MAX_BYTES", 1024 * 1024)
    content = _decode_base64_audio(data, max_bytes=max_bytes)
    uploaded = FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
        content_type="audio/mpeg",
    )
    try:
        validated = validate_media_upload_request(
            field_name_raw="yomitan_audio",
            field_type="audio",
            uploaded=uploaded,
            max_bytes=max_bytes,
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)),
        )
    except RequestValidationError as exc:
        raise ConnectMediaError(f"Audio MP3 không hợp lệ: {exc}") from exc

    _purge_expired()
    now = _utcnow()
    ttl_seconds = _config_int("CONNECT_PENDING_MEDIA_TTL_SECONDS", 30 * 60)
    expires_at = now + timedelta(seconds=ttl_seconds)
    existing = ConnectPendingMedia.query.filter_by(user_id=user_id, filename=filename).first()
    if existing is not None:
        if existing.sha256 != validated.sha256:
            raise ConnectMediaError("Tên media đã tồn tại với nội dung khác.")
        existing_path = _safe_path(existing.storage_path)
        try:
            existing_content = existing_path.read_bytes()
        except OSError:
            existing_content = b""
        if (
            len(existing_content) == existing.size_bytes
            and hashlib.sha256(existing_content).hexdigest() == existing.sha256
        ):
            existing.expires_at = expires_at
            db.session.commit()
            return filename
        db.session.delete(existing)
        db.session.commit()
        _unlink_quietly(existing_path)

    active_query = ConnectPendingMedia.query.filter(
        ConnectPendingMedia.user_id == user_id,
        ConnectPendingMedia.expires_at > now,
    )
    active_count = active_query.count()
    active_bytes = int(
        db.session.query(func.coalesce(func.sum(ConnectPendingMedia.size_bytes), 0))
        .filter(
            ConnectPendingMedia.user_id == user_id,
            ConnectPendingMedia.expires_at > now,
        )
        .scalar()
        or 0
    )
    max_items = _config_int("CONNECT_PENDING_MEDIA_MAX_ITEMS", 20)
    max_total_bytes = _config_int("CONNECT_PENDING_MEDIA_MAX_TOTAL_BYTES", 10 * 1024 * 1024)
    if active_count >= max_items or active_bytes + validated.size_bytes > max_total_bytes:
        raise ConnectMediaError("Đã vượt giới hạn media đang chờ của tài khoản.")

    relative_path = (
        Path("connect_pending") / str(user_id) / validated.storage_filename
    )
    full_path = _safe_path(relative_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(validated.content)
    row = ConnectPendingMedia(
        user_id=user_id,
        filename=filename,
        mime_type="audio/mpeg",
        storage_path=str(relative_path).replace("\\", "/"),
        sha256=validated.sha256,
        size_bytes=validated.size_bytes,
        expires_at=expires_at,
        created_at=now,
    )
    try:
        db.session.add(row)
        db.session.flush()
        db.session.add(
            AuditLog(
                user_id=user_id,
                action="connect.media.stage",
                payload={
                    "pending_media_id": row.id,
                    "size_bytes": row.size_bytes,
                    "mime_type": row.mime_type,
                },
            )
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        _unlink_quietly(full_path)
        raise
    return filename


def _reference_filename(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    sound_match = SOUND_REFERENCE_RE.fullmatch(raw)
    if sound_match:
        return sound_match.group(1)
    if YOMITAN_MP3_FILENAME_RE.fullmatch(raw):
        return raw
    return None


def resolve_pending_audio(
    *,
    user_id: int,
    note_type: NoteType,
    raw_fields: object,
    lock: bool,
) -> tuple[dict[str, ConnectPendingMedia], set[str]]:
    if not isinstance(raw_fields, dict):
        return {}, set()
    audio_fields = {
        field.name for field in note_type.field_defs if field.field_type == "audio"
    }
    requested = {
        field_name: filename
        for field_name, value in raw_fields.items()
        if field_name in audio_fields and (filename := _reference_filename(value)) is not None
    }
    if not requested:
        return {}, set()

    filenames = sorted(set(requested.values()))
    query = ConnectPendingMedia.query.filter(
        ConnectPendingMedia.user_id == user_id,
        ConnectPendingMedia.filename.in_(filenames),
        ConnectPendingMedia.expires_at > _utcnow(),
    )
    if lock:
        query = query.with_for_update()
    rows = {row.filename: row for row in query.all()}
    missing = [filename for filename in filenames if filename not in rows]
    if missing:
        raise ConnectMediaError(
            "Không tìm thấy audio đã tải lên hoặc audio đã hết hạn. Vui lòng thêm lại từ Yomitan."
        )

    attachments = {field_name: rows[filename] for field_name, filename in requested.items()}
    allowed_references: set[str] = set()
    for filename in rows:
        allowed_references.add(filename)
        allowed_references.add(f"[sound:{filename}]")
    return attachments, allowed_references


def materialize_audio(
    *,
    user_id: int,
    note: Note,
    attachments: dict[str, ConnectPendingMedia],
) -> MaterializedMedia:
    if not attachments:
        return MaterializedMedia((), ())

    values = dict(note.field_values or {})
    final_paths: list[Path] = []
    pending_paths_by_id: dict[str, Path] = {}
    try:
        for field_name, pending in attachments.items():
            pending_path = _safe_path(pending.storage_path)
            try:
                content = pending_path.read_bytes()
            except OSError as exc:
                raise ConnectMediaError("File audio đang chờ không còn tồn tại.") from exc
            if len(content) != pending.size_bytes or hashlib.sha256(content).hexdigest() != pending.sha256:
                raise ConnectMediaError("File audio đang chờ không còn toàn vẹn.")

            storage_filename = f"{uuid4().hex}_{pending.sha256[:12]}.mp3"
            relative_path = Path(str(user_id)) / note.id / storage_filename
            final_path = _safe_path(relative_path)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            final_path.write_bytes(content)
            final_paths.append(final_path)

            asset = MediaAsset(
                note_id=note.id,
                field_name=field_name,
                filename=pending.filename,
                mime_type="audio/mpeg",
                storage_path=str(relative_path).replace("\\", "/"),
                sha256=pending.sha256,
                size_bytes=pending.size_bytes,
            )
            db.session.add(asset)
            db.session.flush()
            # Yomitan sends Anki-style ``[sound:filename.mp3]`` references, but
            # Flama's canonical media field value is the original safe filename.
            # The MediaAsset UUID remains the internal proxy/persistence identity.
            values[field_name] = pending.filename
            pending_paths_by_id[pending.id] = pending_path
    except Exception:
        for path in final_paths:
            _unlink_quietly(path)
        raise

    note.field_values = values
    for pending_id in pending_paths_by_id:
        row = db.session.get(ConnectPendingMedia, pending_id)
        if row is not None:
            db.session.delete(row)
    db.session.add(
        AuditLog(
            user_id=user_id,
            action="connect.media.attach",
            payload={"note_id": note.id, "media_count": len(attachments)},
        )
    )
    return MaterializedMedia(
        final_paths=tuple(final_paths),
        pending_paths=tuple(pending_paths_by_id.values()),
    )


def finalize_materialized(result: MaterializedMedia) -> None:
    for path in result.pending_paths:
        _unlink_quietly(path)


def compensate_materialized(result: MaterializedMedia | None) -> None:
    if result is None:
        return
    for path in result.final_paths:
        _unlink_quietly(path)
