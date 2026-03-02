"""Sub-module for flashcard routes."""

from __future__ import annotations

import logging
from datetime import datetime
from flask import jsonify, request, redirect, url_for, flash, render_template, send_file, current_app
from flask_login import current_user, login_required
from sqlalchemy.exc import OperationalError
from models import db
from models.flashcard import *
from models.deck import Deck
from models.card_progress import CardProgress
from app.utils.permissions import is_admin_user

# Import everything from core module so routes can use helpers
from . import *

from app.routes.flashcards import (
    _api_error,
    _apply_note_type_marketplace_payload,
    _audit,
    _create_cards_for_note,
    _get_note_type_or_404,
    _normalize_tags,
    _recompute_note_type_market_stats,
    _reorder_fields,
    _run_field_rename_job,
    _serialize_field,
    _serialize_note_type,
    _touch_note_type_install_usage,
    _validate_note_payload,
    _validate_note_type_consistency_for_deck,
)



@flashcards_bp.route("/flashcards/note-types")
@login_required
def note_type_manager():
    note_types = (
        NoteType.query.filter_by(user_id=current_user.id)
        .order_by(NoteType.updated_at.desc(), NoteType.created_at.desc())
        .all()
    )
    return render_template("flashcards/note_types.html", note_types=note_types)

@flashcards_bp.route("/flashcards/note-types/<note_type_id>")
@login_required
def note_type_detail_page(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return redirect(url_for("flashcards.note_type_manager"))
    notes = Note.query.filter_by(note_type_id=note_type_id, user_id=current_user.id).order_by(Note.created_at.desc()).limit(30).all()
    return render_template("flashcards/note_type_detail.html", note_type=note_type, notes=notes)

@flashcards_bp.route("/flashcards/note-types/<note_type_id>/fields")
@login_required
def note_type_fields_page(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return redirect(url_for("flashcards.note_type_manager"))
    return render_template("flashcards/note_type_fields.html", note_type=note_type)

@flashcards_bp.route("/flashcards/notes/new")
@login_required
def note_editor_page():
    if not is_admin_user(current_user):
        flash("Bạn không có quyền truy cập trang này.", "danger")
        return redirect(url_for("main.dashboard"))
    note_types = NoteType.query.filter_by(user_id=current_user.id).order_by(NoteType.name.asc()).all()
    decks = Deck.query.order_by(Deck.name.asc()).all()
    return render_template("flashcards/note_editor.html", note_types=note_types, decks=decks)

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
    decks = Deck.query.order_by(Deck.name.asc()).all()

    # Filters from query string
    selected_nt = request.args.get("note_type_id", "")
    selected_deck = request.args.get("deck_id", "")
    search_q = request.args.get("q", "").strip()
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
        query = query.filter(
            Note.field_values.cast(db.Text).ilike(f"%{search_q}%")
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
                if fd.field_type in {"text", "richtext"}:
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

    return render_template(
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
    decks = Deck.query.order_by(Deck.name.asc()).all()
    return render_template(
        "flashcards/note_edit.html",
        note=note,
        note_type=note_type,
        decks=decks,
    )

@flashcards_bp.route("/api/note-types", methods=["GET"])
@login_required
def list_note_types():
    note_types = NoteType.query.filter_by(user_id=current_user.id).order_by(NoteType.updated_at.desc()).all()
    return jsonify({"items": [_serialize_note_type(note_type) for note_type in note_types]})

@flashcards_bp.route("/api/note-types/<note_type_id>", methods=["GET"])
@login_required
def get_note_type_detail(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    return jsonify(_serialize_note_type(note_type))

@flashcards_bp.route("/api/note-types/<note_type_id>", methods=["PATCH"])
@login_required
def patch_note_type(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    payload = request.get_json(silent=True) or {}
    validation_error = _apply_note_type_marketplace_payload(note_type, payload)
    if validation_error:
        return _api_error("VALIDATION_ERROR", validation_error)
    from app.services.note_type_service import update_note_type_and_commit
    update_note_type_and_commit(note_type)
    return jsonify(_serialize_note_type(note_type))

@flashcards_bp.route("/api/note-types/<note_type_id>", methods=["DELETE"])
@login_required
def delete_note_type(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    note_count = Note.query.filter_by(note_type_id=note_type.id).count()
    if note_count > 0:
        return _api_error("NOTE_TYPE_HAS_NOTES", "Cannot delete note type with existing notes.", status=409)
    from app.services.note_type_service import delete_note_type_and_commit
    delete_note_type_and_commit(note_type)
    return jsonify({"success": True})

@flashcards_bp.route("/api/note-types/<note_type_id>/fields", methods=["GET"])
@login_required
def list_fields(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    fields = FieldDef.query.filter_by(note_type_id=note_type.id).order_by(FieldDef.position.asc()).all()
    return jsonify({"items": [_serialize_field(field) for field in fields]})

@flashcards_bp.route("/api/note-types/<note_type_id>/fields", methods=["POST"])
@login_required
def create_field(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    field_type = (payload.get("field_type") or "text").strip()
    required = bool(payload.get("required", False))
    if not name:
        return _api_error("VALIDATION_ERROR", "Field name is required.", field="name")
    if field_type not in FIELD_TYPES:
        return _api_error("VALIDATION_ERROR", "Unsupported field_type.", field="field_type")
    if FieldDef.query.filter_by(note_type_id=note_type.id, name=name).first():
        return _api_error("VALIDATION_ERROR", "Field name already exists in this note type.", field="name")
    from app.services.note_type_service import get_max_field_position
    max_pos = get_max_field_position(note_type.id)
    field = FieldDef(
        note_type_id=note_type.id,
        name=name,
        field_type=field_type,
        required=required,
        position=max_pos + 1,
    )
    from app.services.note_type_service import create_field_and_commit
    create_field_and_commit(field, note_type.id)
    return jsonify(_serialize_field(field)), 201

@flashcards_bp.route("/api/note-types/<note_type_id>/fields/<field_id>", methods=["PATCH"])
@login_required
def patch_field(note_type_id: str, field_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    field = FieldDef.query.filter_by(id=field_id, note_type_id=note_type.id).first()
    if not field:
        return _api_error("FIELD_NOT_FOUND", "Field not found.", status=404)
    payload = request.get_json(silent=True) or {}

    old_name = field.name
    new_name = (payload.get("name") or field.name).strip()
    new_type = (payload.get("field_type") or field.field_type).strip()
    required = payload.get("required")

    if not new_name:
        return _api_error("VALIDATION_ERROR", "Field name is required.", field="name")
    if new_type not in FIELD_TYPES:
        return _api_error("VALIDATION_ERROR", "Unsupported field_type.", field="field_type")
    conflict = FieldDef.query.filter(
        FieldDef.note_type_id == note_type.id,
        FieldDef.name == new_name,
        FieldDef.id != field.id,
    ).first()
    if conflict:
        return _api_error("VALIDATION_ERROR", "Field name already exists.", field="name")

    field.field_type = new_type
    if required is not None:
        field.required = bool(required)

    job_payload = None
    if old_name != new_name:
        job = _run_field_rename_job(note_type, field, old_name, new_name)
        field.name = new_name
        job_payload = {"job_id": job.id, "status": job.status, "processed_notes": job.processed_notes}

    from app.services.note_type_service import update_field_and_commit
    update_field_and_commit(note_type.id, field.id, old_name, field.name)
    response_payload = {"field": _serialize_field(field)}
    if job_payload:
        response_payload["rename_job"] = job_payload
    return jsonify(response_payload)

@flashcards_bp.route("/api/note-types/<note_type_id>/fields/<field_id>", methods=["DELETE"])
@login_required
def delete_field(note_type_id: str, field_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    field = FieldDef.query.filter_by(id=field_id, note_type_id=note_type.id).first()
    if not field:
        return _api_error("FIELD_NOT_FOUND", "Field not found.", status=404)

    notes = Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).all()
    for note in notes:
        values = dict(note.field_values or {})
        values.pop(field.name, None)
        note.field_values = values

    from app.services.note_type_service import delete_field_and_commit
    delete_field_and_commit(field, note_type.id)
    return jsonify({"success": True})

@flashcards_bp.route("/api/note-types/<note_type_id>/fields/reorder", methods=["POST"])
@login_required
def reorder_fields(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    payload = request.get_json(silent=True)
    if not isinstance(payload, list):
        return _api_error("VALIDATION_ERROR", "Payload must be a list.", field="body")
    ok, err = _reorder_fields(note_type.id, payload)
    if not ok:
        return _api_error("VALIDATION_ERROR", err or "Invalid reorder payload.", field="body")
    from app.services.note_type_service import reorder_fields_and_commit
    reorder_fields_and_commit(note_type.id)
    return jsonify({"success": True})

@flashcards_bp.route("/api/notes", methods=["GET"])
@login_required
def list_notes():
    note_type_id = (request.args.get("note_type_id") or "").strip()
    deck_id_raw = (request.args.get("deck_id") or "").strip()
    page = max(1, int(request.args.get("page", "1")))
    per_page = max(1, min(100, int(request.args.get("per_page", "20"))))

    query = Note.query.filter_by(user_id=current_user.id)
    if note_type_id:
        query = query.filter(Note.note_type_id == note_type_id)
    if deck_id_raw:
        try:
            deck_id = int(deck_id_raw)
            query = query.filter(Note.deck_id == deck_id)
        except ValueError:
            return _api_error("VALIDATION_ERROR", "deck_id must be an integer.", field="deck_id")

    pagination = query.order_by(Note.updated_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for note in pagination.items:
        items.append(
            {
                "id": note.id,
                "note_type_id": note.note_type_id,
                "deck_id": note.deck_id,
                "field_values": note.field_values or {},
                "tags": note.tags or [],
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "updated_at": note.updated_at.isoformat() if note.updated_at else None,
            }
        )
    return jsonify(
        {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
        }
    )

@flashcards_bp.route("/api/notes", methods=["POST"])
@login_required
def create_note():
    payload = request.get_json(silent=True) or {}
    note_type_id = (payload.get("note_type_id") or "").strip()
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    cleaned_values, err = _validate_note_payload(note_type, payload, partial=False)
    if err:
        return _api_error("VALIDATION_ERROR", err, field="field_values")
    tags = _normalize_tags(payload.get("tags"))
    deck_id = payload.get("deck_id")
    if deck_id in ("", None):
        parsed_deck_id = None
    else:
        try:
            parsed_deck_id = int(deck_id)
        except (TypeError, ValueError):
            return _api_error("VALIDATION_ERROR", "deck_id must be an integer.", field="deck_id")

    deck_consistency_error = _validate_note_type_consistency_for_deck(
        deck_id=parsed_deck_id,
        note_type_id=note_type.id,
        user_id=current_user.id,
    )
    if deck_consistency_error:
        return _api_error("VALIDATION_ERROR", deck_consistency_error, field="deck_id")

    note = Note(
        note_type_id=note_type.id,
        user_id=current_user.id,
        deck_id=parsed_deck_id,
        field_values=cleaned_values,
        tags=tags,
    )
    from app.services.note_type_service import create_note_and_commit
    create_note_and_commit(note, current_user.id)
    return jsonify({"id": note.id, "field_values": note.field_values, "tags": note.tags}), 201

@flashcards_bp.route("/api/notes/<note_id>", methods=["PATCH"])
@login_required
def patch_note(note_id: str):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    payload = request.get_json(silent=True) or {}
    note_type = _get_note_type_or_404(note.note_type_id)
    if note_type is None:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    cleaned_values, err = _validate_note_payload(note_type, payload, partial=True)
    if err:
        return _api_error("VALIDATION_ERROR", err, field="field_values")
    values = dict(note.field_values or {})
    values.update(cleaned_values)
    for field in note_type.field_defs:
        if field.required and is_field_empty(values.get(field.name)):
            return _api_error("VALIDATION_ERROR", f"Field '{field.name}' is required.", field=field.name)
    note.field_values = values

    if "tags" in payload:
        note.tags = _normalize_tags(payload.get("tags"))
    if "deck_id" in payload:
        deck_id = payload.get("deck_id")
        if deck_id in ("", None):
            note.deck_id = None
        else:
            try:
                note.deck_id = int(deck_id)
            except (TypeError, ValueError):
                return _api_error("VALIDATION_ERROR", "deck_id must be an integer.", field="deck_id")

    deck_consistency_error = _validate_note_type_consistency_for_deck(
        deck_id=note.deck_id,
        note_type_id=note.note_type_id,
        user_id=current_user.id,
        exclude_note_id=note.id,
    )
    if deck_consistency_error:
        return _api_error("VALIDATION_ERROR", deck_consistency_error, field="deck_id")
    from app.services.note_type_service import update_note_and_commit
    update_note_and_commit(note.id)
    return jsonify({"id": note.id, "field_values": note.field_values, "tags": note.tags})

@flashcards_bp.route("/api/notes/<note_id>", methods=["DELETE"])
@login_required
def delete_note(note_id: str):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    from app.services.note_type_service import delete_note_and_commit
    delete_note_and_commit(note)
    return jsonify({"success": True})

@flashcards_bp.route("/api/flashcards/seed-default-note-type", methods=["POST"])
@login_required
def seed_default_note_type():
    if not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Admin only endpoint.", status=403)
    from app.services.note_type_service import ensure_legacy_note_type_and_commit
    note_type, template = ensure_legacy_note_type_and_commit(current_user.id)
    return jsonify({"note_type_id": note_type.id, "template_id": template.id})
