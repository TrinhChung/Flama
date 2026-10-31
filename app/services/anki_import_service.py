"""Transport-neutral application service for browser-driven Anki imports.

The React application reads Anki Desktop through the user's loopback
AnkiConnect endpoint.  This module owns the server-side import operations used
by the canonical Flask API; it deliberately exposes neither the AnkiConnect
action protocol nor long-lived Flama Connect token authentication.

The existing implementation is delegated to while the import domain is being
separated from the Yomitan compatibility adapter.  Keeping the seam here lets
the REST API and its tests remain independent from ``app.connect``.
"""

from __future__ import annotations

from typing import Any

from app.services import flama_connect_package_service, flama_connect_service
from app.services.review_analytics_projection_service import flush_review_analytics_deltas
from models import db
from models.connect_import_session import ConnectImportSession


AnkiImportError = flama_connect_service.ConnectError
AnkiImportPackageError = flama_connect_package_service.ConnectPackageError
LEGACY_MACHINE_SOURCE_PREFIX = "anki-v2:"


def _commit_with_analytics() -> None:
    try:
        flush_review_analytics_deltas(db.session)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def capabilities() -> dict[str, object]:
    return flama_connect_package_service.capabilities()


def create_session(*, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    # anki-v2 keys included the machine's media folder path. Current pages send
    # the profile-only anki-v3 key and move v2 refs to it, so a page still
    # sending v2 would find no refs and import every note again.
    if str(payload.get("sourceKey") or "").startswith(LEGACY_MACHINE_SOURCE_PREFIX):
        raise AnkiImportError(
            "Trang đồng bộ đang dùng phiên bản cũ. Vui lòng tải lại trang (F5) rồi đồng bộ lại."
        )
    try:
        normalized = dict(payload)
        # The authenticated web route, not the browser payload, owns the source
        # provider.  This prevents a caller from impersonating another integration.
        normalized["source"] = "anki"
        result = flama_connect_service.create_import_session(user_id, normalized)
        _commit_with_analytics()
        return result
    except Exception:
        db.session.rollback()
        raise


def get_status(*, user_id: int, session_id: str) -> dict[str, Any]:
    return flama_connect_service.get_import_status(user_id, session_id)


def get_note_statuses(
    *,
    user_id: int,
    session_id: str,
    notes: object,
) -> dict[str, Any]:
    return flama_connect_service.get_import_note_statuses(user_id, session_id, notes)


def receive_media_package(
    *,
    user_id: int,
    session_id: str,
    sequence: int,
    expected_sha256: str,
    content: bytes,
) -> dict[str, object]:
    try:
        result = flama_connect_package_service.receive_media_package(
            user_id=user_id,
            session_id=session_id,
            sequence=sequence,
            expected_sha256=expected_sha256,
            content=content,
        )
        _commit_with_analytics()
        return result
    except Exception:
        db.session.rollback()
        raise


def receive_card_package(
    *,
    user_id: int,
    session_id: str,
    sequence: int,
    expected_sha256: str,
    content: bytes,
    content_encoding: str,
) -> dict[str, object]:
    try:
        result = flama_connect_package_service.receive_card_package(
            user_id=user_id,
            session_id=session_id,
            sequence=sequence,
            expected_sha256=expected_sha256,
            content=content,
            content_encoding=content_encoding,
        )
        _commit_with_analytics()
        return result
    except Exception:
        db.session.rollback()
        raise


def complete_session(
    *,
    user_id: int,
    session_id: str,
    expected_notes: object,
) -> dict[str, Any]:
    try:
        result = flama_connect_service.complete_import_session(
            user_id,
            session_id,
            expected_notes=expected_notes,
        )
        _commit_with_analytics()
        return result
    except Exception:
        db.session.rollback()
        raise


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
    try:
        result = flama_connect_package_service.receive_sync_package(
            user_id=user_id,
            session_id=session_id,
            sequence=sequence,
            kind=kind,
            expected_sha256=expected_sha256,
            content=content,
            content_encoding=content_encoding,
        )
        _commit_with_analytics()
        return result
    except Exception:
        db.session.rollback()
        raise


def cancel_session(*, user_id: int, session_id: str) -> dict[str, Any]:
    try:
        session = ConnectImportSession.query.filter_by(
            id=str(session_id or "").strip(),
            user_id=user_id,
        ).first()
        if session is None:
            raise AnkiImportError("import session was not found")
        if session.status != "cancelled":
            session.status = "cancelled"
            flama_connect_package_service.cleanup_session_staging(session)
            db.session.flush()
        result = flama_connect_service.get_import_status(user_id, session.id)
        _commit_with_analytics()
        return result
    except Exception:
        db.session.rollback()
        raise
