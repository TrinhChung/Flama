"""Authenticated REST transport for browser-driven Anki imports."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.api.common import error_response
from app.services import anki_import_service
from app.services.review_analytics_projection_service import flush_review_analytics_deltas
from models import db


anki_imports_bp = Blueprint("api_v1_anki_imports", __name__)


def _package_limit() -> int:
    return max(
        1,
        int(
            current_app.config.get(
                "ANKI_IMPORT_PACKAGE_MAX_BYTES",
                current_app.config.get("CONNECT_PACKAGE_MAX_BYTES", 16 * 1024 * 1024),
            )
        ),
    )


def _read_package() -> bytes:
    limit = _package_limit()
    content = request.stream.read(limit + 1)
    if len(content) > limit:
        raise anki_import_service.AnkiImportPackageError(
            f"package must contain between 1 and {limit} bytes"
        )
    return content


def _error(exc: Exception):
    message = str(exc)
    authority_code = getattr(exc, "code", None)
    if getattr(exc, "status", None) == 409 and isinstance(authority_code, str):
        return error_response(authority_code, message, status=409)
    lowered = message.lower()
    if "was not found" in lowered:
        code, status = "NOT_FOUND", 404
    elif "different checksum" in lowered or "changed after preflight" in lowered:
        code, status = "CONFLICT", 409
    elif "too large" in lowered or "beyond the allowed size" in lowered:
        code, status = "PAYLOAD_TOO_LARGE", 413
    else:
        code, status = "VALIDATION_ERROR", 400
    return error_response(code, message, status=status)


@anki_imports_bp.get("/flashcards/import/anki/capabilities")
@login_required
def capabilities():
    return jsonify(anki_import_service.capabilities())


@anki_imports_bp.post("/flashcards/import/anki/sessions")
@login_required
def create_session():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "A JSON object is required.", status=400)
    try:
        result = anki_import_service.create_session(
            user_id=current_user.id,
            payload=payload,
        )
        flush_review_analytics_deltas(db.session)
        db.session.commit()
    except anki_import_service.AnkiImportError as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
    return jsonify(result), 201


@anki_imports_bp.get("/flashcards/import/anki/sessions/<session_id>")
@login_required
def get_session(session_id: str):
    try:
        return jsonify(
            anki_import_service.get_status(
                user_id=current_user.id,
                session_id=session_id,
            )
        )
    except anki_import_service.AnkiImportError as exc:
        db.session.rollback()
        return _error(exc)


@anki_imports_bp.post("/flashcards/import/anki/sessions/<session_id>/note-status")
@login_required
def get_note_statuses(session_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "A JSON object is required.", status=400)
    try:
        return jsonify(
            anki_import_service.get_note_statuses(
                user_id=current_user.id,
                session_id=session_id,
                notes=payload.get("notes"),
            )
        )
    except anki_import_service.AnkiImportError as exc:
        db.session.rollback()
        return _error(exc)


@anki_imports_bp.put(
    "/flashcards/import/anki/sessions/<session_id>/packages/media/<int:sequence>"
)
@login_required
def upload_media_package(session_id: str, sequence: int):
    try:
        result = anki_import_service.receive_media_package(
            user_id=current_user.id,
            session_id=session_id,
            sequence=sequence,
            expected_sha256=request.headers.get("X-Package-SHA256", ""),
            content=_read_package(),
        )
        flush_review_analytics_deltas(db.session)
        db.session.commit()
    except (
        anki_import_service.AnkiImportError,
        anki_import_service.AnkiImportPackageError,
    ) as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
    return jsonify(result)


@anki_imports_bp.put(
    "/flashcards/import/anki/sessions/<session_id>/packages/cards/<int:sequence>"
)
@login_required
def upload_card_package(session_id: str, sequence: int):
    try:
        result = anki_import_service.receive_card_package(
            user_id=current_user.id,
            session_id=session_id,
            sequence=sequence,
            expected_sha256=request.headers.get("X-Package-SHA256", ""),
            content=_read_package(),
            content_encoding=request.headers.get("Content-Encoding", "identity"),
        )
        flush_review_analytics_deltas(db.session)
        db.session.commit()
    except (
        anki_import_service.AnkiImportError,
        anki_import_service.AnkiImportPackageError,
    ) as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
    return jsonify(result)


def _upload_sync_package(session_id: str, sequence: int, kind: str):
    try:
        result = anki_import_service.receive_sync_package(
            user_id=current_user.id,
            session_id=session_id,
            sequence=sequence,
            kind=kind,
            expected_sha256=request.headers.get("X-Package-SHA256", ""),
            content=_read_package(),
            content_encoding=request.headers.get("Content-Encoding", "identity"),
        )
        flush_review_analytics_deltas(db.session)
        db.session.commit()
    except (
        anki_import_service.AnkiImportError,
        anki_import_service.AnkiImportPackageError,
    ) as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
    return jsonify(result)


@anki_imports_bp.put(
    "/flashcards/import/anki/sessions/<session_id>/packages/progress/<int:sequence>"
)
@login_required
def upload_progress_package(session_id: str, sequence: int):
    return _upload_sync_package(session_id, sequence, "progress")


@anki_imports_bp.put(
    "/flashcards/import/anki/sessions/<session_id>/packages/reviews/<int:sequence>"
)
@login_required
def upload_review_package(session_id: str, sequence: int):
    return _upload_sync_package(session_id, sequence, "reviews")


@anki_imports_bp.post("/flashcards/import/anki/sessions/<session_id>/complete")
@login_required
def complete_session(session_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "A JSON object is required.", status=400)
    try:
        result = anki_import_service.complete_session(
            user_id=current_user.id,
            session_id=session_id,
            expected_notes=payload.get("expectedNotes"),
        )
        flush_review_analytics_deltas(db.session)
        db.session.commit()
    except anki_import_service.AnkiImportError as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
    return jsonify(result)


@anki_imports_bp.delete("/flashcards/import/anki/sessions/<session_id>")
@login_required
def cancel_session(session_id: str):
    try:
        result = anki_import_service.cancel_session(
            user_id=current_user.id,
            session_id=session_id,
        )
        flush_review_analytics_deltas(db.session)
        db.session.commit()
    except anki_import_service.AnkiImportError as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
    return jsonify(result)
