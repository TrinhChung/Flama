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
from models.connect_import_media import ConnectImportMedia
from models.connect_import_session import ConnectImportSession
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
IMPORT_MEDIA_FILENAME_RE = re.compile(r"^[\w][\w_.-]{0,254}$")
IMPORT_SOUND_REFERENCE_RE = re.compile(r"^\[sound:([\w][\w_.-]{0,254})\]$")
IMPORT_MEDIA_MIME_BY_EXTENSION = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
    "wav": "audio/wav",
    "webm": "audio/webm",
}


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


def _purge_expired() -> int:
    expired = (
        ConnectPendingMedia.query.filter(ConnectPendingMedia.expires_at <= _utcnow())
        .order_by(ConnectPendingMedia.expires_at.asc())
        .limit(100)
        .with_for_update(skip_locked=True)
        .all()
    )
    if not expired:
        return 0
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
    return len(expired)


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


def _decode_base64_media(raw_data: object, *, max_bytes: int) -> bytes:
    if not isinstance(raw_data, str) or not raw_data:
        raise ConnectMediaError("Dữ liệu media base64 là bắt buộc.")
    max_encoded_length = ((max_bytes + 2) // 3) * 4
    if len(raw_data) > max_encoded_length + 4:
        raise ConnectMediaError(f"Media vượt quá giới hạn {max_bytes} byte.")
    try:
        content = base64.b64decode(raw_data, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ConnectMediaError("Dữ liệu media không phải base64 hợp lệ.") from exc
    if len(content) > max_bytes:
        raise ConnectMediaError(f"Media vượt quá giới hạn {max_bytes} byte.")
    return content


def stage_import_media(
    *,
    user_id: int,
    session_id: object,
    filename: object,
    data: object,
    media_kind: object,
) -> dict[str, object]:
    session = ConnectImportSession.query.filter_by(id=session_id, user_id=user_id).first()
    if session is None or session.status not in {"note_types_ready", "importing"}:
        raise ConnectMediaError("Phiên đồng bộ chưa sẵn sàng để nhận media.")
    if session.expires_at <= _utcnow():
        raise ConnectMediaError("Phiên đồng bộ đã hết hạn.")
    normalized_kind = str(media_kind or "").strip().lower()
    if normalized_kind not in {"audio", "image"}:
        raise ConnectMediaError("mediaKind phải là audio hoặc image.")
    if not isinstance(filename, str) or not IMPORT_MEDIA_FILENAME_RE.fullmatch(filename):
        raise ConnectMediaError("Tên media không an toàn hoặc không hợp lệ.")
    extension = Path(filename).suffix.lower().lstrip(".")
    mime_type = IMPORT_MEDIA_MIME_BY_EXTENSION.get(extension)
    if not mime_type or (normalized_kind == "audio") != mime_type.startswith("audio/"):
        raise ConnectMediaError("Phần mở rộng media không khớp với mediaKind.")

    max_bytes = _config_int(
        "CONNECT_IMPORT_MEDIA_MAX_BYTES",
        int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024)),
    )
    content = _decode_base64_media(data, max_bytes=max_bytes)
    uploaded = FileStorage(stream=io.BytesIO(content), filename=filename, content_type=mime_type)
    try:
        validated = validate_media_upload_request(
            field_name_raw="anki_import_media",
            field_type=normalized_kind,
            uploaded=uploaded,
            max_bytes=max_bytes,
            scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)),
        )
    except RequestValidationError as exc:
        raise ConnectMediaError(f"Media không hợp lệ: {exc}") from exc

    existing = ConnectImportMedia.query.filter_by(session_id=session.id, filename=filename).first()
    if existing is not None:
        if existing.sha256 != validated.sha256:
            raise ConnectMediaError("Tên media đã tồn tại trong phiên với nội dung khác.")
        return {
            "filename": existing.filename,
            "sha256": existing.sha256,
            "mimeType": existing.mime_type,
            "size": existing.size_bytes,
        }

    active_count = ConnectImportMedia.query.filter_by(session_id=session.id).count()
    max_items = _config_int("CONNECT_IMPORT_MEDIA_MAX_ITEMS", 20_000)
    if active_count >= max_items:
        raise ConnectMediaError("Phiên đồng bộ đã vượt quá số lượng media cho phép.")
    relative_path = Path("connect_import") / str(user_id) / session.id / validated.storage_filename
    full_path = _safe_path(relative_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(validated.content)
    row = ConnectImportMedia(
        session_id=session.id,
        user_id=user_id,
        filename=filename,
        media_kind=normalized_kind,
        mime_type=validated.mime_type,
        storage_path=str(relative_path).replace("\\", "/"),
        sha256=validated.sha256,
        size_bytes=validated.size_bytes,
    )
    try:
        db.session.add(row)
        db.session.flush()
        db.session.add(
            AuditLog(
                user_id=user_id,
                action="connect.import_media.stage",
                payload={
                    "session_id": session.id,
                    "media_id": row.id,
                    "sha256": row.sha256,
                    "size_bytes": row.size_bytes,
                    "mime_type": row.mime_type,
                },
            )
        )
    except SQLAlchemyError:
        _unlink_quietly(full_path)
        raise
    session.processed_media = ConnectImportMedia.query.filter_by(session_id=session.id).count()
    return {
        "filename": row.filename,
        "sha256": row.sha256,
        "mimeType": row.mime_type,
        "size": row.size_bytes,
    }


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

    from app.services.connect.mining_media import lock_account
    _purge_expired()
    lock_account(user_id)
    return stage_validated_pending(user_id=user_id, filename=filename, uploaded=validated)


def stage_validated_pending(*, user_id, filename, uploaded, uow=None, standard=False):
    validated = uploaded
    now = _utcnow()
    ttl_seconds = _config_int("CONNECT_PENDING_MEDIA_TTL_SECONDS", 30 * 60)
    expires_at = now + timedelta(seconds=ttl_seconds)
    existing = ConnectPendingMedia.query.filter_by(user_id=user_id, filename=filename).first()
    if existing is not None:
        if standard and existing.expires_at <= now:
            raise ConnectMediaError("staged media has expired; use a new filename")
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
            if uow is None:
                db.session.commit()
            return filename
        if uow is not None:
            raise ConnectMediaError("staged media is expired or damaged; use a new filename")
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
    max_total_bytes = _config_int("CONNECT_ANKI_PENDING_MAX_BYTES", 16 * 1024 * 1024) if standard else _config_int("CONNECT_PENDING_MEDIA_MAX_TOTAL_BYTES", 10 * 1024 * 1024)
    if active_count >= max_items or active_bytes + validated.size_bytes > max_total_bytes:
        raise ConnectMediaError("Đã vượt giới hạn media đang chờ của tài khoản.")

    if standard:
        from app.services.connect.mining_media import check_quota
        check_quota(user_id, validated.size_bytes, incoming_items=1)

    relative_path = (
        Path("connect_pending") / str(user_id) / validated.storage_filename
    )
    full_path = _safe_path(relative_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    if uow is not None:
        uow.created_paths.append(full_path)
    full_path.write_bytes(validated.content)
    row = ConnectPendingMedia(
        user_id=user_id,
        filename=filename,
        mime_type=validated.mime_type,
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
        if uow is None:
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


def resolve_import_media(
    *,
    user_id: int,
    session_id: str,
    note_type: NoteType,
    raw_fields: object,
    lock: bool,
    existing_note: Note | None = None,
) -> tuple[dict[str, ConnectImportMedia], set[str]]:
    if not isinstance(raw_fields, dict):
        return {}, set()
    media_fields = {
        field.name: field.field_type
        for field in note_type.field_defs
        if field.field_type in {"audio", "image", "diagram"}
    }
    requested: dict[str, str] = {}
    for field_name, field_type in media_fields.items():
        raw = str(raw_fields.get(field_name) or "").strip()
        if not raw:
            continue
        if field_type == "audio":
            match = IMPORT_SOUND_REFERENCE_RE.fullmatch(raw)
            filename = match.group(1) if match else raw
        else:
            filename = raw
        if not IMPORT_MEDIA_FILENAME_RE.fullmatch(filename):
            raw_fields[field_name] = ""
            current_app.logger.warning(
                "Skipping invalid Anki media reference field=%s session_id=%s",
                field_name,
                session_id,
            )
            continue
        requested[field_name] = filename
    if not requested:
        return {}, set()

    filenames = sorted(set(requested.values()))
    query = ConnectImportMedia.query.filter(
        ConnectImportMedia.user_id == user_id,
        ConnectImportMedia.session_id == session_id,
        ConnectImportMedia.filename.in_(filenames),
    )
    if lock:
        query = query.with_for_update()
    rows = {row.filename: row for row in query.all()}

    existing_assets: dict[str, list[MediaAsset]] = {}
    if existing_note is not None:
        for asset in MediaAsset.query.filter_by(note_id=existing_note.id).all():
            existing_assets.setdefault(asset.field_name, []).append(asset)

    valid_attachments = {}
    allowed: set[str] = set()
    for field_name, filename in requested.items():
        expected = media_fields[field_name]
        staged = rows.get(filename)
        if staged is None:
            matching_existing = next(
                (
                    asset
                    for asset in existing_assets.get(field_name, [])
                    if (
                        asset.filename == filename
                        or filename.startswith(f"{asset.sha256}.")
                    )
                    and (
                        (expected == "audio")
                        == str(asset.mime_type or "").startswith("audio/")
                    )
                ),
                None,
            )
            if matching_existing is not None:
                canonical_url = f"/media/proxy/{matching_existing.id}"
                raw_fields[field_name] = canonical_url
                allowed.add(canonical_url)
                continue
            raw_fields[field_name] = ""
            current_app.logger.warning(
                "Skipping missing Anki media filename=%s field=%s session_id=%s",
                filename,
                field_name,
                session_id,
            )
            continue
        row_kind = staged.media_kind
        if (expected == "audio") != (row_kind == "audio"):
            raw_fields[field_name] = ""
            current_app.logger.warning(
                "Skipping wrong-kind Anki media filename=%s field=%s session_id=%s",
                filename,
                field_name,
                session_id,
            )
            continue
        valid_attachments[field_name] = staged
        allowed.add(filename)
        allowed.add(f"[sound:{filename}]")
    return valid_attachments, allowed


def materialize_import_media(
    *,
    user_id: int,
    note: Note,
    attachments: dict[str, ConnectImportMedia],
) -> MaterializedMedia:
    if not attachments:
        return MaterializedMedia((), ())
    values = dict(note.field_values or {})
    final_paths: list[Path] = []
    attached_count = 0
    try:
        for field_name, staged in attachments.items():
            try:
                staged_path = _safe_path(staged.storage_path)
                try:
                    content = staged_path.read_bytes()
                except OSError as exc:
                    current_app.logger.warning("Media staging không còn tồn tại cho %s: %s", staged.filename, exc)
                    values[field_name] = ""
                    continue
                if len(content) != staged.size_bytes or hashlib.sha256(content).hexdigest() != staged.sha256:
                    current_app.logger.warning("Media staging không còn toàn vẹn cho %s", staged.filename)
                    values[field_name] = ""
                    continue
                extension = Path(staged.filename).suffix.lower().lstrip(".")
                storage_filename = f"{uuid4().hex}_{staged.sha256[:12]}.{extension}"
                relative_path = Path(str(user_id)) / note.id / storage_filename
                final_path = _safe_path(relative_path)
                final_path.parent.mkdir(parents=True, exist_ok=True)

                existing = MediaAsset.query.filter_by(
                    note_id=note.id,
                    field_name=field_name,
                    sha256=staged.sha256,
                ).first()
                if existing is None:
                    final_path.write_bytes(content)
                    final_paths.append(final_path)
                    existing = MediaAsset(
                        note_id=note.id,
                        field_name=field_name,
                        filename=staged.filename,
                        mime_type=staged.mime_type,
                        storage_path=str(relative_path).replace("\\", "/"),
                        sha256=staged.sha256,
                        size_bytes=staged.size_bytes,
                    )
                    db.session.add(existing)
                    db.session.flush()
                values[field_name] = f"/media/proxy/{existing.id}"
                attached_count += 1
            except Exception as exc:
                current_app.logger.error("Lỗi khi xử lý import media %s: %s", staged.filename, exc)
                values[field_name] = ""
                continue
        note.field_values = values
        db.session.add(
            AuditLog(
                user_id=user_id,
                action="connect.import_media.attach",
                payload={"note_id": note.id, "media_count": attached_count},
            )
        )
    except Exception:
        for path in final_paths:
            _unlink_quietly(path)
        raise
    return MaterializedMedia(tuple(final_paths), ())


def materialize_audio(
    *,
    user_id: int,
    note: Note,
    attachments: dict[str, ConnectPendingMedia],
    managed: bool = False,
) -> MaterializedMedia:
    if not attachments:
        return MaterializedMedia((), ())

    values = dict(note.field_values or {})
    final_paths: list[Path] = []
    pending_paths_by_id: dict[str, Path] = {}
    try:
        for field_name, pending in attachments.items():
            pending_path = None
            if hasattr(pending, "content"):
                content = pending.content
            else:
                pending_path = _safe_path(pending.storage_path)
                try:
                    content = pending_path.read_bytes()
                except OSError as exc:
                    raise ConnectMediaError("File media đang chờ không còn tồn tại.") from exc
            if len(content) != pending.size_bytes or hashlib.sha256(content).hexdigest() != pending.sha256:
                raise ConnectMediaError("File audio đang chờ không còn toàn vẹn.")

            storage_filename = f"{uuid4().hex}_{pending.sha256[:12]}{Path(pending.filename).suffix.lower()}"
            relative_path = Path(str(user_id)) / note.id / storage_filename
            if managed:
                relative_path = Path("connect_mined") / relative_path
            final_path = _safe_path(relative_path)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            final_paths.append(final_path)
            final_path.write_bytes(content)

            asset = MediaAsset(
                note_id=note.id,
                field_name=field_name,
                filename=pending.filename,
                mime_type=pending.mime_type,
                storage_path=str(relative_path).replace("\\", "/"),
                sha256=pending.sha256,
                size_bytes=pending.size_bytes,
            )
            db.session.add(asset)
            db.session.flush()
            values[field_name] = f"/media/proxy/{asset.id}"
            if pending_path is not None:
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
