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
from models import db
from models.connect_import_session import ConnectImportSession


AnkiImportError = flama_connect_service.ConnectError
AnkiImportPackageError = flama_connect_package_service.ConnectPackageError


def capabilities() -> dict[str, object]:
    return flama_connect_package_service.capabilities()


def create_session(*, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    # The authenticated web route, not the browser payload, owns the source
    # provider.  This prevents a caller from impersonating another integration.
    normalized["source"] = "anki"
    return flama_connect_service.create_import_session(user_id, normalized)


def get_status(*, user_id: int, session_id: str) -> dict[str, Any]:
    return flama_connect_service.get_import_status(user_id, session_id)


def receive_media_package(
    *,
    user_id: int,
    session_id: str,
    sequence: int,
    expected_sha256: str,
    content: bytes,
) -> dict[str, object]:
    return flama_connect_package_service.receive_media_package(
        user_id=user_id,
        session_id=session_id,
        sequence=sequence,
        expected_sha256=expected_sha256,
        content=content,
    )


def receive_card_package(
    *,
    user_id: int,
    session_id: str,
    sequence: int,
    expected_sha256: str,
    content: bytes,
    content_encoding: str,
) -> dict[str, object]:
    return flama_connect_package_service.receive_card_package(
        user_id=user_id,
        session_id=session_id,
        sequence=sequence,
        expected_sha256=expected_sha256,
        content=content,
        content_encoding=content_encoding,
    )


def complete_session(*, user_id: int, session_id: str) -> dict[str, Any]:
    return flama_connect_service.complete_import_session(user_id, session_id)


def cancel_session(*, user_id: int, session_id: str) -> dict[str, Any]:
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
    return flama_connect_service.get_import_status(user_id, session.id)
