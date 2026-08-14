"""Resumable, checksum-verified package transport for Anki imports."""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import zipfile

from flask import current_app

from app.services import flama_connect_media_service
from app.validators.flashcard_input import RequestValidationError, resolve_safe_storage_path
from models import db
from models.connect_import_package import ConnectImportPackage
from models.connect_import_media import ConnectImportMedia
from models.connect_import_session import ConnectImportSession


PACKAGE_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ENTRY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$")
AUDIO_EXTENSIONS = {"mp3", "ogg", "wav", "webm"}
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "svg"}


class ConnectPackageError(ValueError):
    pass


def _config_int(name: str, default: int) -> int:
    return max(1, int(current_app.config.get(name, default)))


def _safe_path(relative: Path) -> Path:
    try:
        return resolve_safe_storage_path(
            upload_root=Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]),
            relative_path=relative,
        )
    except RequestValidationError as exc:
        raise ConnectPackageError("package storage path is unsafe") from exc


def _session(user_id: int, session_id: str) -> ConnectImportSession:
    session = ConnectImportSession.query.filter_by(id=session_id, user_id=user_id).first()
    if session is None:
        raise ConnectPackageError("import session was not found")
    if session.status not in {"note_types_ready", "importing"}:
        raise ConnectPackageError("all NoteTypes must be ready before uploading packages")
    return session


def capabilities() -> dict[str, object]:
    package_max_bytes = _config_int("CONNECT_PACKAGE_MAX_BYTES", 16 * 1024 * 1024)
    package_max_uncompressed_bytes = _config_int(
        "CONNECT_PACKAGE_MAX_UNCOMPRESSED_BYTES",
        64 * 1024 * 1024,
    )
    return {
        "formatVersion": 1,
        "syncFormatVersion": 2,
        "mediaPackageMaxBytes": package_max_bytes,
        "mediaPackageMaxEntries": _config_int("CONNECT_PACKAGE_MAX_ENTRIES", 500),
        "mediaPackageMaxUncompressedBytes": package_max_uncompressed_bytes,
        "mediaFileMaxBytes": _config_int("CONNECT_IMPORT_MEDIA_MAX_BYTES", 10 * 1024 * 1024),
        # Kept for older clients: this is the server's internal DB work chunk,
        # not the transport package size.
        "cardBatchMaxItems": 50,
        "cardPackageTargetItems": min(
            _config_int("CONNECT_CARD_PACKAGE_TARGET_ITEMS", 500),
            _config_int("CONNECT_CARD_PACKAGE_MAX_ITEMS", 1000),
        ),
        "cardPackageMaxItems": _config_int("CONNECT_CARD_PACKAGE_MAX_ITEMS", 1000),
        "cardPackageMaxBytes": package_max_bytes,
        "cardPackageMaxUncompressedBytes": package_max_uncompressed_bytes,
        "progressBatchMaxItems": _config_int("CONNECT_SYNC_PACKAGE_MAX_ITEMS", 1000),
        "reviewBatchMaxItems": _config_int("CONNECT_SYNC_PACKAGE_MAX_ITEMS", 1000),
        "reviewSessionMaxItems": _config_int("CONNECT_REVIEW_SESSION_MAX_ITEMS", 2_000_000),
        "supportedMediaExtensions": sorted(AUDIO_EXTENSIONS | IMAGE_EXTENSIONS),
    }


def cleanup_session_staging(session: ConnectImportSession) -> None:
    media_rows = ConnectImportMedia.query.filter_by(session_id=session.id).all()
    package_rows = ConnectImportPackage.query.filter_by(session_id=session.id).all()
    for row in [*media_rows, *package_rows]:
        try:
            _safe_path(Path(row.storage_path)).unlink(missing_ok=True)
        except OSError:
            current_app.logger.warning("Unable to remove Connect staging file: %s", row.storage_path)
        db.session.delete(row)


def receive_media_package(
    *,
    user_id: int,
    session_id: str,
    sequence: int,
    expected_sha256: str,
    content: bytes,
) -> dict[str, object]:
    session = _session(user_id, session_id)
    if sequence < 0 or sequence > 1_000_000:
        raise ConnectPackageError("package sequence is invalid")
    normalized_hash = str(expected_sha256 or "").strip().lower()
    if not PACKAGE_HASH_RE.fullmatch(normalized_hash):
        raise ConnectPackageError("X-Package-SHA256 must be a lowercase SHA-256 hex string")
    max_bytes = _config_int("CONNECT_PACKAGE_MAX_BYTES", 16 * 1024 * 1024)
    if not content or len(content) > max_bytes:
        raise ConnectPackageError(f"package must contain between 1 and {max_bytes} bytes")
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != normalized_hash:
        raise ConnectPackageError("package checksum does not match")

    existing = ConnectImportPackage.query.filter_by(
        session_id=session.id,
        kind="media",
        sequence=sequence,
    ).first()
    if existing is not None:
        if existing.sha256 != actual_hash:
            raise ConnectPackageError("package sequence already exists with a different checksum")
        stored = dict(existing.result_json or {})
        accepted_filenames = list(stored.get("acceptedFilenames") or [])
        if not accepted_filenames and existing.item_count:
            accepted_filenames = [
                row.filename
                for row in ConnectImportMedia.query.filter_by(session_id=session.id).all()
            ]
        return {
            "packageId": existing.id,
            "sequence": existing.sequence,
            "sha256": existing.sha256,
            "itemCount": existing.item_count,
            "status": existing.status,
            "replayed": True,
            "acceptedFilenames": accepted_filenames,
            "rejectedFilenames": list(stored.get("rejectedFilenames") or []),
        }

    max_entries = _config_int("CONNECT_PACKAGE_MAX_ENTRIES", 500)
    max_uncompressed = _config_int("CONNECT_PACKAGE_MAX_UNCOMPRESSED_BYTES", 64 * 1024 * 1024)
    max_ratio = _config_int("CONNECT_PACKAGE_MAX_COMPRESSION_RATIO", 100)
    staged_count = 0
    total_uncompressed = 0
    seen_names: set[str] = set()
    entries: list[tuple[str, str, bytes]] = []
    rejected_filenames: list[str] = []
    try:
        archive = zipfile.ZipFile(io.BytesIO(content), mode="r")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ConnectPackageError("media package is not a valid ZIP archive") from exc
    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > max_entries:
            raise ConnectPackageError(f"media package must contain between 1 and {max_entries} files")
        for info in infos:
            unix_mode = info.external_attr >> 16
            if info.is_dir() or stat.S_ISLNK(unix_mode):
                raise ConnectPackageError("directories and symlinks are not allowed in media packages")
            name = info.filename
            normalized_name = name.casefold()
            if not SAFE_ENTRY_RE.fullmatch(name) or normalized_name in seen_names:
                raise ConnectPackageError("media package contains an unsafe or duplicate filename")
            seen_names.add(normalized_name)
            extension = Path(name).suffix.lower().lstrip(".")
            total_uncompressed += int(info.file_size)
            if total_uncompressed > max_uncompressed:
                raise ConnectPackageError("media package expands beyond the allowed size")
            if info.compress_size > 0 and info.file_size / info.compress_size > max_ratio:
                raise ConnectPackageError("media package contains a suspicious compression ratio")
            entry = archive.read(info)
            if len(entry) != info.file_size:
                raise ConnectPackageError("media package entry is truncated")
            if extension not in AUDIO_EXTENSIONS | IMAGE_EXTENSIONS:
                rejected_filenames.append(name)
                continue
            entries.append((name, "audio" if extension in AUDIO_EXTENSIONS else "image", entry))

    existing_ids = {
        row.id for row in ConnectImportMedia.query.filter_by(session_id=session.id).all()
    }
    accepted_filenames: list[str] = []
    try:
        for name, media_kind, entry in entries:
            try:
                flama_connect_media_service.stage_import_media(
                    user_id=user_id,
                    session_id=session.id,
                    filename=name,
                    data=base64.b64encode(entry).decode("ascii"),
                    media_kind=media_kind,
                )
                staged_count += 1
                accepted_filenames.append(name)
            except flama_connect_media_service.ConnectMediaError as exc:
                rejected_filenames.append(name)
                current_app.logger.warning(
                    "Skipping invalid Connect media session_id=%s filename=%s error=%s",
                    session.id,
                    name,
                    exc,
                )
    except Exception:
        new_rows = [
            row
            for row in ConnectImportMedia.query.filter_by(session_id=session.id).all()
            if row.id not in existing_ids
        ]
        for row in new_rows:
            try:
                _safe_path(Path(row.storage_path)).unlink(missing_ok=True)
            except OSError:
                pass
            db.session.delete(row)
        raise

    relative_path = Path("connect_packages") / str(user_id) / session.id / f"media-{sequence:06d}.zip"
    full_path = _safe_path(relative_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)
    package = ConnectImportPackage(
        session_id=session.id,
        kind="media",
        sequence=sequence,
        sha256=actual_hash,
        size_bytes=len(content),
        storage_path=str(relative_path).replace("\\", "/"),
        status="partial_failed" if rejected_filenames else "validated",
        item_count=staged_count,
        result_json={
            "acceptedFilenames": accepted_filenames,
            "rejectedFilenames": rejected_filenames,
        },
        error=(
            f"{len(rejected_filenames)} media files were skipped"
            if rejected_filenames
            else None
        ),
    )
    db.session.add(package)
    db.session.flush()
    return {
        "packageId": package.id,
        "sequence": sequence,
        "sha256": actual_hash,
        "itemCount": staged_count,
        "status": package.status,
        "replayed": False,
        "acceptedFilenames": accepted_filenames,
        "rejectedFilenames": rejected_filenames,
    }


def receive_card_package(
    *,
    user_id: int,
    session_id: str,
    sequence: int,
    expected_sha256: str,
    content: bytes,
    content_encoding: str,
) -> dict[str, object]:
    session = _session(user_id, session_id)
    normalized_hash = str(expected_sha256 or "").strip().lower()
    if sequence < 0 or sequence > 1_000_000 or not PACKAGE_HASH_RE.fullmatch(normalized_hash):
        raise ConnectPackageError("card package metadata is invalid")
    max_bytes = _config_int("CONNECT_PACKAGE_MAX_BYTES", 16 * 1024 * 1024)
    if not content or len(content) > max_bytes:
        raise ConnectPackageError(f"package must contain between 1 and {max_bytes} bytes")
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != normalized_hash:
        raise ConnectPackageError("package checksum does not match")
    existing = ConnectImportPackage.query.filter_by(
        session_id=session.id,
        kind="cards",
        sequence=sequence,
    ).first()
    if existing is not None:
        if existing.sha256 != actual_hash:
            raise ConnectPackageError("package sequence already exists with a different checksum")
        stored = dict(existing.result_json or {})
        return {
            "packageId": existing.id,
            "sequence": existing.sequence,
            "sha256": existing.sha256,
            "itemCount": existing.item_count,
            "status": existing.status,
            "replayed": True,
            "results": list(stored.get("results") or []),
        }
    replayed = False

    max_uncompressed = _config_int("CONNECT_PACKAGE_MAX_UNCOMPRESSED_BYTES", 64 * 1024 * 1024)
    encoding = str(content_encoding or "identity").strip().lower()
    try:
        if encoding in {"gzip", "x-gzip"}:
            with gzip.GzipFile(fileobj=io.BytesIO(content), mode="rb") as stream:
                decoded = stream.read(max_uncompressed + 1)
        elif encoding in {"", "identity"}:
            decoded = content
        else:
            raise ConnectPackageError("unsupported card package Content-Encoding")
    except (OSError, EOFError) as exc:
        raise ConnectPackageError("card package gzip stream is invalid") from exc
    if len(decoded) > max_uncompressed:
        raise ConnectPackageError("card package expands beyond the allowed size")
    try:
        text = decoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConnectPackageError("card package must be UTF-8 NDJSON") from exc
    lines = [line for line in text.splitlines() if line.strip()]
    max_items = _config_int("CONNECT_CARD_PACKAGE_MAX_ITEMS", 1000)
    if not lines or len(lines) > max_items:
        raise ConnectPackageError(f"card package must contain between 1 and {max_items} records")
    cards: list[dict[str, object]] = []
    for line in lines:
        if len(line.encode("utf-8")) > 1024 * 1024:
            raise ConnectPackageError("one card package record exceeds 1 MiB")
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConnectPackageError("card package contains invalid NDJSON") from exc
        if not isinstance(item, dict):
            raise ConnectPackageError("each card package record must be an object")
        cards.append(item)

    from app.services import flama_connect_service

    results: list[dict[str, object]] = []
    batch_context = flama_connect_service.prepare_import_batch_context(
        user_id=user_id,
        session=session,
        cards=cards,
    )
    for offset in range(0, len(cards), flama_connect_service.MAX_NOTES_PER_REQUEST):
        batch_result = flama_connect_service.import_cards(
            user_id,
            {
                "importSessionId": session.id,
                "cards": cards[offset : offset + flama_connect_service.MAX_NOTES_PER_REQUEST],
            },
            commit=False,
            batch_context=batch_context,
        )
        results.extend(batch_result["results"])

    failed = sum(1 for item in results if not item.get("imported"))
    if existing is None:
        relative_path = Path("connect_packages") / str(user_id) / session.id / f"cards-{sequence:06d}.ndjson.gz"
        full_path = _safe_path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
        package = ConnectImportPackage(
            session_id=session.id,
            kind="cards",
            sequence=sequence,
            sha256=actual_hash,
            size_bytes=len(content),
            storage_path=str(relative_path).replace("\\", "/"),
            status="partial_failed" if failed else "processed",
            item_count=len(cards),
            result_json={"results": results},
            error=f"{failed} card records failed" if failed else None,
        )
        db.session.add(package)
    else:
        package = existing
        package.status = "partial_failed" if failed else "processed"
        package.error = f"{failed} card records failed" if failed else None
    db.session.flush()
    return {
        "packageId": package.id,
        "sequence": sequence,
        "sha256": actual_hash,
        "itemCount": len(cards),
        "status": package.status,
        "replayed": replayed,
        "results": results,
    }


def receive_sync_package(
    *,
    user_id: int,
    session_id: str,
    sequence: int,
    kind: str,
    expected_sha256: str,
    content: bytes,
    content_encoding: str,
) -> dict[str, object]:
    """Receive an idempotent progress or review NDJSON package."""
    if kind not in {"progress", "reviews"}:
        raise ConnectPackageError("sync package kind is invalid")
    session = _session(user_id, session_id)
    normalized_hash = str(expected_sha256 or "").strip().lower()
    if sequence < 0 or sequence > 1_000_000 or not PACKAGE_HASH_RE.fullmatch(normalized_hash):
        raise ConnectPackageError("sync package metadata is invalid")
    max_bytes = _config_int("CONNECT_PACKAGE_MAX_BYTES", 16 * 1024 * 1024)
    if not content or len(content) > max_bytes:
        raise ConnectPackageError(f"package must contain between 1 and {max_bytes} bytes")
    actual_hash = hashlib.sha256(content).hexdigest()
    if actual_hash != normalized_hash:
        raise ConnectPackageError("package checksum does not match")
    existing = ConnectImportPackage.query.filter_by(
        session_id=session.id,
        kind=kind,
        sequence=sequence,
    ).first()
    if existing is not None:
        if existing.sha256 != actual_hash:
            raise ConnectPackageError("package sequence already exists with a different checksum")
        stored = dict(existing.result_json or {})
        return {
            "packageId": existing.id,
            "sequence": existing.sequence,
            "sha256": existing.sha256,
            "itemCount": existing.item_count,
            "status": existing.status,
            "replayed": True,
            "results": list(stored.get("results") or []),
        }

    max_uncompressed = _config_int("CONNECT_PACKAGE_MAX_UNCOMPRESSED_BYTES", 64 * 1024 * 1024)
    encoding = str(content_encoding or "identity").strip().lower()
    try:
        if encoding in {"gzip", "x-gzip"}:
            with gzip.GzipFile(fileobj=io.BytesIO(content), mode="rb") as stream:
                decoded = stream.read(max_uncompressed + 1)
        elif encoding in {"", "identity"}:
            decoded = content
        else:
            raise ConnectPackageError("unsupported sync package Content-Encoding")
    except (OSError, EOFError) as exc:
        raise ConnectPackageError("sync package gzip stream is invalid") from exc
    if len(decoded) > max_uncompressed:
        raise ConnectPackageError("sync package expands beyond the allowed size")
    try:
        text = decoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConnectPackageError("sync package must be UTF-8 NDJSON") from exc
    lines = [line for line in text.splitlines() if line.strip()]
    max_items = _config_int("CONNECT_SYNC_PACKAGE_MAX_ITEMS", 1000)
    if not lines or len(lines) > max_items:
        raise ConnectPackageError(f"sync package must contain between 1 and {max_items} records")
    records: list[dict[str, object]] = []
    for line in lines:
        if len(line.encode("utf-8")) > 64 * 1024:
            raise ConnectPackageError("one sync package record exceeds 64 KiB")
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConnectPackageError("sync package contains invalid NDJSON") from exc
        if not isinstance(item, dict):
            raise ConnectPackageError("each sync package record must be an object")
        records.append(item)

    prior_items, prior_bytes, prior_packages = db.session.query(
        db.func.coalesce(db.func.sum(ConnectImportPackage.item_count), 0),
        db.func.coalesce(db.func.sum(ConnectImportPackage.size_bytes), 0),
        db.func.count(ConnectImportPackage.id),
    ).filter(
        ConnectImportPackage.session_id == session.id,
        ConnectImportPackage.kind == kind,
    ).one()
    session_max_items = _config_int(
        "CONNECT_REVIEW_SESSION_MAX_ITEMS" if kind == "reviews" else "CONNECT_PROGRESS_SESSION_MAX_ITEMS",
        2_000_000 if kind == "reviews" else 200_000,
    )
    session_max_bytes = _config_int("CONNECT_SYNC_SESSION_MAX_BYTES", 512 * 1024 * 1024)
    session_max_packages = _config_int("CONNECT_SYNC_SESSION_MAX_PACKAGES", 10_000)
    if int(prior_items or 0) + len(records) > session_max_items:
        raise ConnectPackageError(f"{kind} session exceeds its aggregate record limit")
    if int(prior_bytes or 0) + len(content) > session_max_bytes:
        raise ConnectPackageError(f"{kind} session exceeds its aggregate byte limit")
    if int(prior_packages or 0) + 1 > session_max_packages:
        raise ConnectPackageError(f"{kind} session exceeds its package limit")

    from app.services import anki_sync_service

    results = (
        anki_sync_service.import_progress(user_id, session, records)
        if kind == "progress"
        else anki_sync_service.import_reviews(user_id, session, records)
    )
    failed = sum(1 for item in results if item.get("state") == "failed")
    relative_path = Path("connect_packages") / str(user_id) / session.id / f"{kind}-{sequence:06d}.ndjson.gz"
    full_path = _safe_path(relative_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)
    package = ConnectImportPackage(
        session_id=session.id,
        kind=kind,
        sequence=sequence,
        sha256=actual_hash,
        size_bytes=len(content),
        storage_path=str(relative_path).replace("\\", "/"),
        status="partial_failed" if failed else "processed",
        item_count=len(records),
        result_json={"results": results},
        error=f"{failed} {kind} records failed" if failed else None,
    )
    db.session.add(package)
    db.session.flush()
    return {
        "packageId": package.id,
        "sequence": sequence,
        "sha256": actual_hash,
        "itemCount": len(records),
        "status": package.status,
        "replayed": False,
        "results": results,
    }
