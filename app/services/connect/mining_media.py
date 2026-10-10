"""Typed media commands for standard AnkiConnect note mining.

Decoding, content inspection, staging and final storage reuse Connect's media
service. No URLs or local paths are ever fetched.
"""

from dataclasses import dataclass
import io
from pathlib import Path
import re

from flask import current_app
from sqlalchemy import func
from werkzeug.datastructures import FileStorage

from app.services import flama_connect_media_service as media
from app.validators.flashcard_input import RequestValidationError, validate_media_upload_request
from models import db
from models.connect_pending_media import ConnectPendingMedia
from models.connect_import_media import ConnectImportMedia
from models.media_asset import MediaAsset
from models.note import Note
from models.user import User

MIME_TYPES = {"mp3": "audio/mpeg", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
_IMAGE_REFERENCE = re.compile(r'<img\s+src=["\']([\w.-]+)["\']\s*/?>', re.IGNORECASE)


@dataclass(frozen=True)
class InlineMedia:
    filename: str
    mime_type: str
    content: bytes
    size_bytes: int
    sha256: str
    storage_filename: str


def lock_account(user_id):
    # A stable row serializes quota checks and duplicate checks across decks.
    User.query.filter_by(id=user_id).with_for_update().populate_existing().one()


def validate_upload(filename, data, *, expected_kind=None):
    if not isinstance(filename, str) or not media.IMPORT_MEDIA_FILENAME_RE.fullmatch(filename):
        raise media.ConnectMediaError("unsafe media filename")
    mime = MIME_TYPES.get(Path(filename).suffix.lower().lstrip("."))
    if mime is None:
        raise media.ConnectMediaError("only MP3, JPEG and PNG media are supported")
    kind = "audio" if mime.startswith("audio/") else "image"
    if expected_kind and expected_kind != kind:
        raise media.ConnectMediaError("media type does not match its destination field")
    limit = media._config_int("CONNECT_ANKI_MEDIA_MAX_BYTES", 2 * 1024 * 1024)
    content = media._decode_base64_media(data, max_bytes=limit)
    try:
        validated = validate_media_upload_request(
            field_name_raw="connect_media", field_type=kind,
            uploaded=FileStorage(stream=io.BytesIO(content), filename=filename, content_type=mime),
            max_bytes=limit, scanner=current_app.config.get("FLASHCARD_MEDIA_SCANNER"),
            scan_enabled=bool(current_app.config.get("FLASHCARD_MEDIA_SCAN_ENABLED", False)),
        )
    except RequestValidationError as exc:
        raise media.ConnectMediaError(str(exc)) from exc
    return InlineMedia(filename, mime, validated.content, validated.size_bytes, validated.sha256, validated.storage_filename)


def check_quota(user_id, incoming_bytes, *, incoming_items=0):
    """Connect admission cap, including already stored media from other writers.

    Other upload APIs do not yet reserve under this lock; this is deliberately
    not advertised as a global storage quota.
    """
    now = media._utcnow()
    pending = ConnectPendingMedia.query.filter_by(user_id=user_id)
    active = pending.filter(ConnectPendingMedia.expires_at > now)
    active_bytes = sum(row.size_bytes for row in active.all())
    if active.count() + incoming_items > media._config_int("CONNECT_PENDING_MEDIA_MAX_ITEMS", 20):
        raise media.ConnectMediaError("pending media item limit exceeded")
    if active_bytes + incoming_bytes > media._config_int("CONNECT_ANKI_PENDING_MAX_BYTES", 16 * 1024 * 1024):
        raise media.ConnectMediaError("pending media byte limit exceeded")
    stored = int(db.session.query(func.coalesce(func.sum(MediaAsset.size_bytes), 0))
                 .join(Note, Note.id == MediaAsset.note_id).filter(Note.user_id == user_id).scalar() or 0)
    # Count expired rows conservatively until the scheduled cleanup removes them.
    pending_bytes = int(db.session.query(func.coalesce(func.sum(ConnectPendingMedia.size_bytes), 0))
                        .filter(ConnectPendingMedia.user_id == user_id).scalar() or 0)
    imported = int(db.session.query(func.coalesce(func.sum(ConnectImportMedia.size_bytes), 0))
                   .filter(ConnectImportMedia.user_id == user_id).scalar() or 0)
    if stored + pending_bytes + imported + incoming_bytes > media._config_int("CONNECT_ANKI_STORAGE_MAX_BYTES", 512 * 1024 * 1024):
        raise media.ConnectMediaError("Connect storage admission limit exceeded")


def stage(user_id, params, uow):
    if params.get("deleteExisting", False) is not False:
        raise media.ConnectMediaError("deleteExisting=true is not supported")
    uploaded = validate_upload(params.get("filename"), params.get("data"))
    lock_account(user_id)
    return media.stage_validated_pending(user_id=user_id, filename=uploaded.filename, uploaded=uploaded, uow=uow, standard=True)


def prepare(user_id, note_type, raw_note, fields, *, lock=False):
    definitions = {item.name: item.field_type for item in note_type.field_defs}
    fields = dict(fields)
    attachments = {}
    inline_names = {}
    if raw_note.get("video"):
        raise media.ConnectMediaError("video mining is not supported")
    for key, kind in (("audio", "audio"), ("picture", "image")):
        items = raw_note.get(key)
        if items is None:
            continue
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list) or len(items) > 10:
            raise media.ConnectMediaError(f"{key} must be an object or an array with at most 10 entries")
        for item in items:
            if not isinstance(item, dict) or set(item) - {"filename", "data", "fields"}:
                raise media.ConnectMediaError("inline media supports filename, data and fields only")
            targets = item.get("fields")
            if not isinstance(targets, list) or not targets or len(targets) > 10 or any(not isinstance(name, str) for name in targets):
                raise media.ConnectMediaError("media fields must be a nonempty array of field names")
            if any(definitions.get(name) != kind for name in targets):
                raise media.ConnectMediaError("media type does not match its destination field")
            uploaded = validate_upload(item.get("filename"), item.get("data"), expected_kind=kind)
            previous = inline_names.setdefault(uploaded.filename, uploaded.sha256)
            if previous != uploaded.sha256:
                raise media.ConnectMediaError("media filename has conflicting content")
            for name in targets:
                if name in attachments or str(fields.get(name, "")).strip():
                    raise media.ConnectMediaError("only one media attachment per field is supported")
                fields[name] = uploaded.filename
                attachments[name] = uploaded
    for name, kind in definitions.items():
        raw = str(fields.get(name, "")).strip()
        if kind not in {"audio", "image", "diagram"} or not raw or name in attachments:
            continue
        sound = media.IMPORT_SOUND_REFERENCE_RE.fullmatch(raw) if kind == "audio" else _IMAGE_REFERENCE.fullmatch(raw)
        filename = sound.group(1) if sound else raw
        if not media.IMPORT_MEDIA_FILENAME_RE.fullmatch(filename):
            raise media.ConnectMediaError("media must reference a file staged by this account")
        query = ConnectPendingMedia.query.filter_by(user_id=user_id, filename=filename).filter(ConnectPendingMedia.expires_at > media._utcnow())
        if lock:
            query = query.with_for_update()
        row = query.first()
        if row is None:
            raise media.ConnectMediaError("staged media was not found or has expired")
        expected = "audio/" if kind == "audio" else "image/"
        if not row.mime_type.startswith(expected) or Path(filename).suffix.lower().lstrip(".") not in MIME_TYPES:
            raise media.ConnectMediaError("media type does not match its destination field")
        fields[name] = row.filename
        attachments[name] = row
    if sum(item.size_bytes for item in attachments.values()) > media._config_int("CONNECT_ANKI_NOTE_MEDIA_MAX_BYTES", 4 * 1024 * 1024):
        raise media.ConnectMediaError("total note media size limit exceeded")
    allowed = {item.filename for item in attachments.values()}
    return fields, attachments, allowed
