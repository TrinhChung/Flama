"""Authenticated REST transport for browser-driven Anki imports."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from app.api.common import admin_required, error_response
from app.services import anki_import_service
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
@admin_required
def capabilities():
    return jsonify(anki_import_service.capabilities())


@anki_imports_bp.post("/flashcards/import/anki/sessions")
@admin_required
def create_session():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("INVALID_JSON", "A JSON object is required.", status=400)
    try:
        result = anki_import_service.create_session(
            user_id=current_user.id,
            payload=payload,
        )
        db.session.commit()
    except anki_import_service.AnkiImportError as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
    return jsonify(result), 201


@anki_imports_bp.get("/flashcards/import/anki/sessions/<session_id>")
@admin_required
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


@anki_imports_bp.put(
    "/flashcards/import/anki/sessions/<session_id>/packages/media/<int:sequence>"
)
@admin_required
def upload_media_package(session_id: str, sequence: int):
    try:
        result = anki_import_service.receive_media_package(
            user_id=current_user.id,
            session_id=session_id,
            sequence=sequence,
            expected_sha256=request.headers.get("X-Package-SHA256", ""),
            content=_read_package(),
        )
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
@admin_required
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


@anki_imports_bp.post("/flashcards/import/anki/sessions/<session_id>/complete")
@admin_required
def complete_session(session_id: str):
    try:
        result = anki_import_service.complete_session(
            user_id=current_user.id,
            session_id=session_id,
        )
        db.session.commit()
    except anki_import_service.AnkiImportError as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
    return jsonify(result)


@anki_imports_bp.delete("/flashcards/import/anki/sessions/<session_id>")
@admin_required
def cancel_session(session_id: str):
    try:
        result = anki_import_service.cancel_session(
            user_id=current_user.id,
            session_id=session_id,
        )
        db.session.commit()
    except anki_import_service.AnkiImportError as exc:
        db.session.rollback()
        return _error(exc)
    except Exception:
        db.session.rollback()
        raise
    return jsonify(result)
