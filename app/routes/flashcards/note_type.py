"""Sub-module for flashcard routes."""

from __future__ import annotations

from flask import jsonify, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app.spa import serve_react_spa
from models import db
from models.flashcard import *
from models.deck import Deck
from app.utils.permissions import is_admin_user

# Import everything from core module so routes can use helpers
from . import *

from app.routes.flashcards import (
    _api_error,
)
from app.validators import (
    escape_like_pattern,
    RequestValidationError,
    sanitize_query_text,
)
from app.services import field_array_conversion_service, flashcard_content_service
from app.repositories.field_value_query_repository import note_values_search_condition
from app.validators.field_array_conversion import ArrayConversionError


def _content_error(exc: flashcard_content_service.ContentApiError):
    return _api_error(
        exc.error,
        str(exc),
        status=exc.status,
        field=exc.field,
    )


def _conversion_error(exc: ArrayConversionError):
    payload = {"error": exc.code, "message": str(exc)}
    if exc.details:
        payload["details"] = exc.details
    return jsonify(payload), exc.status



@flashcards_bp.route("/note-types")
@flashcards_bp.route("/flashcards/note-types")
@login_required
def note_type_manager():
    from app.spa import serve_react_spa
    return serve_react_spa()

@flashcards_bp.route("/note-types/<note_type_id>")
@flashcards_bp.route("/flashcards/note-types/<note_type_id>")
@login_required
def note_type_detail_page(note_type_id: str):
    from app.spa import serve_react_spa
    return serve_react_spa()

@flashcards_bp.route("/note-types/<note_type_id>/fields")
@flashcards_bp.route("/flashcards/note-types/<note_type_id>/fields")
@login_required
def note_type_fields_page(note_type_id: str):
    from app.spa import serve_react_spa
    return serve_react_spa()

@flashcards_bp.route("/flashcards/notes/new")
@login_required
def note_editor_page():
    if not is_admin_user(current_user):
        flash("Bạn không có quyền truy cập trang này.", "danger")
        return redirect(url_for("main.dashboard"))
    note_types = NoteType.query.filter_by(user_id=current_user.id).order_by(NoteType.name.asc()).all()
    decks = Deck.query.filter(Deck.deleted_at.is_(None)).order_by(Deck.name.asc()).all()
    return serve_react_spa()

@flashcards_bp.route("/flashcards/notes")
@login_required
def notes_list_page():
    """Note management — list, filter, quick delete."""
    if not is_admin_user(current_user):
        flash("Bạn không có quyền truy cập trang này.", "danger")
        return redirect(url_for("main.dashboard"))
    note_types = (
        NoteType.query.filter_by(user_id=current_user.id)
        .order_by(NoteType.name.asc())
        .all()
    )
    decks = Deck.query.filter(Deck.deleted_at.is_(None)).order_by(Deck.name.asc()).all()

    # Filters from query string
    selected_nt = request.args.get("note_type_id", "")
    selected_deck = request.args.get("deck_id", "")
    try:
        search_q = sanitize_query_text(request.args.get("q"), field_name="q", max_length=120)
    except RequestValidationError:
        search_q = ""
        flash("Invalid search query detected and ignored.", "warning")
    page = max(1, int(request.args.get("page", "1")))
    per_page = 30

    query = Note.query.filter_by(user_id=current_user.id)
    if selected_nt:
        query = query.filter(Note.note_type_id == selected_nt)
    if selected_deck:
        try:
            query = query.filter(Note.deck_id == int(selected_deck))
        except ValueError:
            pass

    # JSON search by first field value (simple contains)
    if search_q:
        like_pattern = f"%{escape_like_pattern(search_q)}%"
        query = query.filter(
            note_values_search_condition(keyword_like=like_pattern.lower())
        )

    pagination = query.order_by(Note.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Build display rows: extract first text field as "title"
    rows = []
    for note in pagination.items:
        note_type_obj = next(
            (nt for nt in note_types if nt.id == note.note_type_id), None
        )
        first_field = None
        if note_type_obj:
            sorted_fields = sorted(note_type_obj.field_defs, key=lambda f: f.position)
            for fd in sorted_fields:
                if fd.field_type in {"text", "richtext", "markdown"}:
                    first_field = fd.name
                    break
        title = (note.field_values or {}).get(first_field or "", "") or f"Note #{note.id}"
        rows.append(
            {
                "note": note,
                "title": str(title)[:80],
                "note_type_name": note_type_obj.name if note_type_obj else "—",
            }
        )

    return serve_react_spa(
        "flashcards/notes_list.html",
        rows=rows,
        pagination=pagination,
        note_types=note_types,
        decks=decks,
        selected_nt=selected_nt,
        selected_deck=selected_deck,
        search_q=search_q,
    )

@flashcards_bp.route("/flashcards/notes/<note_id>/edit")
@login_required
def note_edit_page(note_id: str):
    """Edit an existing note."""
    if not is_admin_user(current_user):
        flash("Bạn không có quyền truy cập trang này.", "danger")
        return redirect(url_for("main.dashboard"))
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return redirect(url_for("flashcards.notes_list_page"))
    note_type = NoteType.query.get(note.note_type_id)
    decks = Deck.query.filter(Deck.deleted_at.is_(None)).order_by(Deck.name.asc()).all()
    return serve_react_spa(
        "flashcards/note_edit.html",
        note=note,
        note_type=note_type,
        decks=decks,
    )

@flashcards_bp.route("/api/note-types", methods=["GET"])
@login_required
def list_note_types():
    return jsonify(
        flashcard_content_service.list_note_types(user_id=current_user.id)
    )


@flashcards_bp.route("/api/note-types/preview", methods=["POST"])
@login_required
def preview_raw_template():
    try:
        payload = flashcard_content_service.preview_raw_template(
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)
    return jsonify(payload)


@flashcards_bp.route("/api/note-types/<note_type_id>", methods=["GET"])
@login_required
def get_note_type_detail(note_type_id: str):
    try:
        return jsonify(
            flashcard_content_service.get_note_type(
                user_id=current_user.id,
                note_type_id=note_type_id,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/note-types/<note_type_id>", methods=["PATCH"])
@login_required
def patch_note_type(note_type_id: str):
    try:
        return jsonify(
            flashcard_content_service.update_note_type(
                user_id=current_user.id,
                admin_mode=is_admin_user(current_user),
                note_type_id=note_type_id,
                payload=request.get_json(silent=True) or {},
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/note-types/<note_type_id>", methods=["DELETE"])
@login_required
def delete_note_type(note_type_id: str):
    try:
        purge = request.args.get("purge") == "true"
        return jsonify(
            flashcard_content_service.delete_note_type(
                user_id=current_user.id,
                note_type_id=note_type_id,
                purge=purge,
                is_admin=is_admin_user(current_user),
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/note-types/<note_type_id>/fields", methods=["GET"])
@login_required
def list_fields(note_type_id: str):
    try:
        return jsonify(
            flashcard_content_service.list_fields(
                user_id=current_user.id,
                note_type_id=note_type_id,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/note-types/<note_type_id>/fields", methods=["POST"])
@login_required
def create_field(note_type_id: str):
    try:
        return (
            jsonify(
                flashcard_content_service.create_field(
                    user_id=current_user.id,
                    note_type_id=note_type_id,
                    payload=request.get_json(silent=True) or {},
                )
            ),
            201,
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/note-types/<note_type_id>/fields/<field_id>", methods=["PATCH"])
@login_required
def patch_field(note_type_id: str, field_id: str):
    try:
        return jsonify(
            flashcard_content_service.update_field(
                user_id=current_user.id,
                note_type_id=note_type_id,
                field_id=field_id,
                payload=request.get_json(silent=True) or {},
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/note-types/<note_type_id>/fields/<field_id>", methods=["DELETE"])
@login_required
def delete_field(note_type_id: str, field_id: str):
    try:
        return jsonify(
            flashcard_content_service.delete_field(
                user_id=current_user.id,
                note_type_id=note_type_id,
                field_id=field_id,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/note-types/<note_type_id>/fields/<field_id>/array-conversion", methods=["GET"])
@login_required
def get_field_array_conversion(note_type_id: str, field_id: str):
    """Every owner Note value of the field, for the frontend to split and preview."""
    try:
        return jsonify(
            field_array_conversion_service.get_conversion_source(
                user_id=current_user.id,
                note_type_id=note_type_id,
                field_id=field_id,
            )
        )
    except ArrayConversionError as exc:
        return _conversion_error(exc)


@flashcards_bp.route("/api/note-types/<note_type_id>/fields/<field_id>/array-conversion", methods=["POST"])
@login_required
def apply_field_array_conversion(note_type_id: str, field_id: str):
    """Apply a frontend-split conversion (or a restore) to the field and all its Notes at once."""
    try:
        return jsonify(
            field_array_conversion_service.apply_conversion(
                user_id=current_user.id,
                note_type_id=note_type_id,
                field_id=field_id,
                payload=request.get_json(silent=True),
            )
        )
    except ArrayConversionError as exc:
        return _conversion_error(exc)


@flashcards_bp.route("/api/note-types/<note_type_id>/fields/reorder", methods=["POST"])
@login_required
def reorder_fields(note_type_id: str):
    try:
        return jsonify(
            flashcard_content_service.reorder_fields(
                user_id=current_user.id,
                note_type_id=note_type_id,
                payload=request.get_json(silent=True),
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/notes", methods=["GET"])
@login_required
def list_notes():
    try:
        return jsonify(
            flashcard_content_service.list_notes(
                user_id=current_user.id,
                query_args=request.args,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/notes", methods=["POST"])
@login_required
def create_note():
    try:
        return (
            jsonify(
                flashcard_content_service.create_note(
                    user_id=current_user.id,
                    payload=request.get_json(silent=True) or {},
                )
            ),
            201,
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/notes/<note_id>", methods=["PATCH"])
@login_required
def patch_note(note_id: str):
    try:
        return jsonify(
            flashcard_content_service.update_note(
                user_id=current_user.id,
                note_id=note_id,
                payload=request.get_json(silent=True) or {},
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/notes/<note_id>", methods=["DELETE"])
@login_required
def delete_note(note_id: str):
    try:
        return jsonify(
            flashcard_content_service.delete_note(
                user_id=current_user.id,
                note_id=note_id,
            )
        )
    except flashcard_content_service.ContentApiError as exc:
        return _content_error(exc)

@flashcards_bp.route("/api/flashcards/seed-default-note-type", methods=["POST"])
@login_required
def seed_default_note_type():
    if not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Admin only endpoint.", status=403)
    from app.services.note_type_service import ensure_legacy_note_type_and_commit
    note_type, template = ensure_legacy_note_type_and_commit(current_user.id)
    return jsonify({"note_type_id": note_type.id, "template_id": template.id})
