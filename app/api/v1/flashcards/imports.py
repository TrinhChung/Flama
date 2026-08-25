"""Flashcard import REST API V1 resources."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.services import flashcard_import_api_service
from app.utils.permissions import is_admin_user


imports_bp = Blueprint("api_v1_flashcard_imports", __name__)


def _error(exc: flashcard_import_api_service.ImportApiError):
    payload = {"error": "VALIDATION_ERROR", "message": str(exc)}
    if exc.field is not None:
        payload["field"] = exc.field
    if exc.status == 404:
        payload["error"] = "FIELD_NOT_FOUND"
    return jsonify(payload), exc.status


@imports_bp.get("/flashcards/import/options")
@login_required
def import_options():
    return jsonify(
        flashcard_import_api_service.build_import_options(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            deck_id_raw=request.args.get("deck_id"),
            note_type_id_raw=request.args.get("note_type_id"),
        )
    )


@imports_bp.post("/flashcards/import/parse")
@login_required
def parse_import():
    upload = request.files.get("file")
    try:
        payload = flashcard_import_api_service.parse_import_file(
            user_id=current_user.id,
            note_type_id=str(request.form.get("note_type_id") or "").strip(),
            filename=str(getattr(upload, "filename", "") or ""),
            file_bytes=upload.read() if upload is not None else b"",
            delimiter_mode=str(
                request.form.get("delimiter_mode") or "csv"
            ).strip().lower(),
            custom_delimiter=request.form.get("custom_delimiter"),
            has_header=_to_bool(request.form.get("has_header"), default=True),
        )
    except flashcard_import_api_service.ImportApiError as exc:
        return _error(exc)
    return jsonify(payload)


@imports_bp.post("/flashcards/import/estimate")
@login_required
def estimate_import():
    try:
        payload = flashcard_import_api_service.run_import_request(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=request.get_json(silent=True) or {},
            apply_changes=False,
        )
    except flashcard_import_api_service.ImportApiError as exc:
        return _error(exc)
    return jsonify(payload)


@imports_bp.post("/flashcards/import/execute")
@login_required
def execute_import():
    try:
        payload = flashcard_import_api_service.run_import_request(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=request.get_json(silent=True) or {},
            apply_changes=True,
        )
    except flashcard_import_api_service.ImportApiError as exc:
        return _error(exc)
    return jsonify(payload)


@imports_bp.post("/flashcards/import/batch/parse")
@login_required
def parse_batch_import():
    raw_files = request.files.getlist("files") or request.files.getlist("file")
    files_payload: list[tuple[str, bytes]] = []
    for f in raw_files:
        filename = str(getattr(f, "filename", "") or "")
        if filename:
            files_payload.append((filename, f.read()))

    try:
        payload = flashcard_import_api_service.parse_batch_import_files(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            parent_deck_id_raw=request.form.get("parent_deck_id"),
            note_type_id=str(request.form.get("note_type_id") or "").strip(),
            files=files_payload,
            delimiter_mode=str(
                request.form.get("delimiter_mode") or "csv"
            ).strip().lower(),
            custom_delimiter=request.form.get("custom_delimiter"),
            has_header=_to_bool(request.form.get("has_header"), default=True),
            naming_mode=str(request.form.get("naming_mode") or "auto").strip().lower(),
            custom_pattern=request.form.get("custom_pattern"),
        )
    except flashcard_import_api_service.ImportApiError as exc:
        return _error(exc)
    return jsonify(payload)


@imports_bp.post("/flashcards/import/batch/estimate")
@login_required
def estimate_batch_import():
    try:
        payload = flashcard_import_api_service.run_batch_import_request(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=request.get_json(silent=True) or {},
            apply_changes=False,
        )
    except flashcard_import_api_service.ImportApiError as exc:
        return _error(exc)
    return jsonify(payload)


@imports_bp.post("/flashcards/import/batch/execute")
@login_required
def execute_batch_import():
    try:
        payload = flashcard_import_api_service.run_batch_import_request(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=request.get_json(silent=True) or {},
            apply_changes=True,
        )
    except flashcard_import_api_service.ImportApiError as exc:
        return _error(exc)
    return jsonify(payload)


def _to_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
