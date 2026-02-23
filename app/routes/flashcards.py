"""Flashcard v2 API + minimal management/study pages."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required

from app.services.anki_scheduler import (
    CardState,
    applyAnswer,
    computeAnswerPreview,
    default_deck_options,
)
from app.services.flashcard_legacy import (
    LEGACY_BACK_TEMPLATE,
    LEGACY_FRONT_TEMPLATE,
    LEGACY_SHARED_CSS,
    ensure_legacy_note_type,
)
from app.services.flashcard_renderer import (
    PREVIEW_MEDIA_AUDIO_TOKEN,
    PREVIEW_MEDIA_DIAGRAM_TOKEN,
    PREVIEW_MEDIA_IMAGE_TOKEN,
    TemplateCompileError,
    is_field_empty,
    render_template_pair,
    sanitize_richtext,
)
from app.utils.permissions import is_admin_user
from models import db
from models.flashcard import (
    AuditLog,
    Card,
    FieldDef,
    FieldRenameJob,
    MediaAsset,
    Note,
    NoteType,
    Template,
)
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_progress import VocabularyProgress

flashcards_bp = Blueprint("flashcards", __name__)
logger = logging.getLogger(__name__)

FIELD_TYPES = {"text", "richtext", "image", "audio", "diagram"}
MEDIA_ALLOWED_PREFIX = "/media/proxy/"
ALLOWED_MEDIA_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
}
CSP_CARD_POLICY = (
    "default-src 'none'; "
    "style-src 'unsafe-inline'; "
    "img-src /media/proxy/; "
    "media-src /media/proxy/; "
    "frame-ancestors 'self'"
)


def _api_error(
    error: str,
    message: str,
    *,
    status: int = 400,
    field: str | None = None,
    line: int | None = None,
):
    payload: dict[str, Any] = {"error": error, "message": message}
    if field is not None:
        payload["field"] = field
    if line is not None:
        payload["line"] = line
    return jsonify(payload), status


def _audit(action: str, payload: dict[str, Any] | None = None) -> None:
    entry = AuditLog(
        user_id=getattr(current_user, "id", None) if getattr(current_user, "is_authenticated", False) else None,
        action=action,
        payload=payload or {},
    )
    db.session.add(entry)


def _get_note_type_or_404(note_type_id: str) -> NoteType | None:
    return NoteType.query.filter_by(id=note_type_id, user_id=current_user.id).first()


def _serialize_field(field: FieldDef) -> dict[str, Any]:
    return {
        "id": field.id,
        "note_type_id": field.note_type_id,
        "name": field.name,
        "field_type": field.field_type,
        "position": field.position,
        "required": bool(field.required),
    }


def _serialize_template(template: Template) -> dict[str, Any]:
    return {
        "id": template.id,
        "note_type_id": template.note_type_id,
        "name": template.name,
        "front_html": template.front_html,
        "back_html": template.back_html,
        "shared_css": template.shared_css,
        "position": template.position,
        "is_default": bool(template.is_default),
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def _serialize_note_type(note_type: NoteType) -> dict[str, Any]:
    return {
        "id": note_type.id,
        "name": note_type.name,
        "created_at": note_type.created_at.isoformat() if note_type.created_at else None,
        "updated_at": note_type.updated_at.isoformat() if note_type.updated_at else None,
        "field_defs": [_serialize_field(field) for field in sorted(note_type.field_defs, key=lambda item: item.position)],
        "templates": [
            _serialize_template(template)
            for template in sorted(note_type.templates, key=lambda item: item.position)
        ],
    }


def _clean_field_value(field_def: FieldDef, raw_value: Any) -> Any:
    if field_def.field_type == "richtext":
        return sanitize_richtext("" if raw_value is None else str(raw_value))
    if field_def.field_type in {"image", "audio", "diagram"}:
        if raw_value is None:
            return ""
        candidate = str(raw_value).strip()
        if candidate.startswith(MEDIA_ALLOWED_PREFIX):
            return candidate
        if MediaAsset.query.get(candidate):
            return candidate
        return ""
    return "" if raw_value is None else str(raw_value).strip()


def _validate_note_payload(note_type: NoteType, payload: dict[str, Any], *, partial: bool) -> tuple[dict[str, Any], str | None]:
    field_map = {field.name: field for field in note_type.field_defs}
    field_values = payload.get("field_values")
    if field_values is None:
        field_values = {}
    if not isinstance(field_values, dict):
        return {}, "field_values must be an object."

    unknown = [key for key in field_values.keys() if key not in field_map]
    if unknown:
        return {}, f"Unknown fields: {', '.join(unknown)}"

    cleaned: dict[str, Any] = {}
    for name, field_def in field_map.items():
        if name in field_values:
            cleaned[name] = _clean_field_value(field_def, field_values.get(name))

    if not partial:
        for name, field_def in field_map.items():
            if name not in cleaned:
                cleaned[name] = ""
            if field_def.required and is_field_empty(cleaned[name]):
                return {}, f"Field '{name}' is required."
    return cleaned, None


def _normalize_tags(raw_tags: Any) -> list[str]:
    if raw_tags is None:
        return []
    if isinstance(raw_tags, list):
        tags = [str(item).strip() for item in raw_tags if str(item).strip()]
        return tags
    if isinstance(raw_tags, str):
        return [item.strip() for item in raw_tags.split(",") if item.strip()]
    return []


def _build_preview_sample_values(field_defs: list[FieldDef]) -> dict[str, Any]:
    sample_values: dict[str, Any] = {}
    for field_def in field_defs:
        if field_def.field_type == "image":
            sample_values[field_def.name] = PREVIEW_MEDIA_IMAGE_TOKEN
        elif field_def.field_type == "audio":
            sample_values[field_def.name] = PREVIEW_MEDIA_AUDIO_TOKEN
        elif field_def.field_type == "diagram":
            sample_values[field_def.name] = PREVIEW_MEDIA_DIAGRAM_TOKEN
        else:
            sample_values[field_def.name] = field_def.name
    return sample_values


def _create_cards_for_note(note: Note) -> None:
    templates = Template.query.filter_by(note_type_id=note.note_type_id).order_by(Template.position.asc()).all()
    existing_template_ids = {card.template_id for card in note.cards}
    for template in templates:
        if template.id in existing_template_ids:
            continue
        card = Card(
            note_id=note.id,
            template_id=template.id,
            queue="new",
        )
        db.session.add(card)


def _reorder_fields(note_type_id: str, reorder_payload: list[dict[str, Any]]) -> tuple[bool, str | None]:
    fields = FieldDef.query.filter_by(note_type_id=note_type_id).all()
    field_map = {field.id: field for field in fields}
    if len(reorder_payload) != len(fields):
        return False, "Reorder payload must include all fields."

    seen = set()
    for row in reorder_payload:
        fid = row.get("id")
        position = row.get("position")
        if fid not in field_map:
            return False, f"Unknown field id: {fid}"
        if fid in seen:
            return False, "Duplicate field id in reorder payload."
        seen.add(fid)
        try:
            field_map[fid].position = int(position)
        except (TypeError, ValueError):
            return False, f"Invalid position for field {fid}"
    return True, None


def _run_field_rename_job(note_type: NoteType, field_def: FieldDef, old_name: str, new_name: str) -> FieldRenameJob:
    job = FieldRenameJob(
        note_type_id=note_type.id,
        user_id=current_user.id,
        field_def_id=field_def.id,
        old_name=old_name,
        new_name=new_name,
        status="running",
        total_notes=Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).count(),
        processed_notes=0,
    )
    db.session.add(job)
    db.session.flush()
    try:
        notes = Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).all()
        for note in notes:
            values = dict(note.field_values or {})
            if old_name in values and new_name not in values:
                values[new_name] = values.pop(old_name)
            elif old_name in values:
                values.pop(old_name)
            note.field_values = values
            job.processed_notes += 1
        job.status = "completed"
    except Exception as exc:  # pragma: no cover - defensive
        job.status = "failed"
        job.error_message = str(exc)
        logger.exception("Field rename job failed: %s", job.id)
    return job


def _normalize_progress_queue(value: str | None) -> str:
    normalized = (value or "new").strip().lower()
    if normalized == "learn":
        return "learning"
    if normalized in {"new", "learning", "review", "relearning"}:
        return normalized
    return "new"


def _card_state_from_progress(progress: VocabularyProgress | None, now: datetime) -> CardState:
    options = default_deck_options()
    if not progress:
        return CardState(
            type="new",
            stepIndex=0,
            due=now,
            dueDay=None,
            intervalDays=0,
            ease=options.startingEase,
            reps=0,
            lapses=0,
            lastReviewAt=None,
        )

    queue = _normalize_progress_queue(progress.queue)
    due_at = progress.due_at or now
    due_day = progress.due_day
    if due_day is None and queue == "review":
        shifted = due_at - timedelta(hours=options.dayBoundaryHourLocal)
        due_day = shifted.date().toordinal()

    return CardState(
        type=queue,  # type: ignore[arg-type]
        stepIndex=int(progress.step_index or 0),
        due=due_at,
        dueDay=due_day,
        intervalDays=float(progress.interval_days or 0),
        ease=float(progress.ease_factor or options.startingEase),
        reps=int(progress.reps or 0),
        lapses=int(progress.lapses or 0),
        lastReviewAt=progress.last_reviewed_at,
    )


def _apply_card_state_to_progress(progress: VocabularyProgress, card_state: CardState, now: datetime) -> VocabularyProgress:
    options = default_deck_options()
    queue = _normalize_progress_queue(card_state.type)
    due_at = card_state.due
    due_day = card_state.dueDay
    if due_day is not None:
        day_date = datetime.fromordinal(int(due_day)).date()
        due_at = datetime.combine(day_date, datetime.min.time()) + timedelta(
            hours=options.dayBoundaryHourLocal
        )

    progress.queue = queue
    progress.step_index = int(card_state.stepIndex or 0)
    progress.due_at = due_at
    progress.due_day = due_day
    progress.interval_days = int(round(float(card_state.intervalDays or 0)))
    progress.ease_factor = float(card_state.ease or options.startingEase)
    progress.reps = int(card_state.reps or 0)
    progress.lapses = int(card_state.lapses or 0)
    progress.last_reviewed_at = card_state.lastReviewAt or now
    return progress


def _is_due(progress: VocabularyProgress | None, now: datetime) -> bool:
    if progress is None:
        return True
    queue = _normalize_progress_queue(progress.queue)
    if queue == "new":
        return True
    if progress.due_at is None:
        return True
    return progress.due_at <= now


def _pick_due_card(cards: list[Card], progress_map: dict[str, VocabularyProgress], now: datetime) -> Card | None:
    due_relearn: list[Card] = []
    due_learn: list[Card] = []
    due_review: list[Card] = []
    due_new: list[Card] = []
    for card in cards:
        progress = progress_map.get(card.id)
        if not _is_due(progress, now):
            continue
        queue = _normalize_progress_queue(progress.queue) if progress else "new"
        if queue == "relearning":
            due_relearn.append(card)
        elif queue == "learning":
            due_learn.append(card)
        elif queue == "review":
            due_review.append(card)
        else:
            due_new.append(card)
    for group in (due_relearn, due_learn, due_review, due_new):
        if group:
            return group[0]
    return None


@flashcards_bp.after_request
def _set_card_security_headers(response):
    if request.path.endswith("/preview") or request.path.startswith("/api/study"):
        response.headers["Content-Security-Policy"] = CSP_CARD_POLICY
    return response


@flashcards_bp.route("/flashcards")
@login_required
def flashcards_home():
    return redirect(url_for("flashcards.note_type_manager"))


@flashcards_bp.route("/flashcards/note-types")
@login_required
def note_type_manager():
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    note_types = (
        NoteType.query.filter_by(user_id=current_user.id)
        .order_by(NoteType.updated_at.desc(), NoteType.created_at.desc())
        .all()
    )
    return render_template("flashcards/note_types.html", note_types=note_types)


@flashcards_bp.route("/flashcards/note-types/<note_type_id>")
@login_required
def note_type_detail_page(note_type_id: str):
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return redirect(url_for("flashcards.note_type_manager"))
    notes = Note.query.filter_by(note_type_id=note_type_id, user_id=current_user.id).order_by(Note.created_at.desc()).limit(30).all()
    return render_template("flashcards/note_type_detail.html", note_type=note_type, notes=notes)


@flashcards_bp.route("/flashcards/note-types/<note_type_id>/fields")
@login_required
def note_type_fields_page(note_type_id: str):
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return redirect(url_for("flashcards.note_type_manager"))
    return render_template("flashcards/note_type_fields.html", note_type=note_type)


@flashcards_bp.route("/flashcards/notes/new")
@login_required
def note_editor_page():
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    note_types = NoteType.query.filter_by(user_id=current_user.id).order_by(NoteType.name.asc()).all()
    decks = VocabularyDeck.query.order_by(VocabularyDeck.name.asc()).all()
    return render_template("flashcards/note_editor.html", note_types=note_types, decks=decks)


@flashcards_bp.route("/flashcards/study")
@login_required
def flashcard_study_page():
    decks = VocabularyDeck.query.order_by(VocabularyDeck.name.asc()).all()
    return render_template("flashcards/study.html", decks=decks)


@flashcards_bp.route("/flashcards/notes")
@login_required
def notes_list_page():
    """Note management — list, filter, quick delete."""
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    note_types = (
        NoteType.query.filter_by(user_id=current_user.id)
        .order_by(NoteType.name.asc())
        .all()
    )
    decks = VocabularyDeck.query.order_by(VocabularyDeck.name.asc()).all()

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
        return redirect(url_for("main.dashboard"))
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return redirect(url_for("flashcards.notes_list_page"))
    note_type = NoteType.query.get(note.note_type_id)
    decks = VocabularyDeck.query.order_by(VocabularyDeck.name.asc()).all()
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


@flashcards_bp.route("/api/note-types", methods=["POST"])
@login_required
def create_note_type():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return _api_error("VALIDATION_ERROR", "Note type name is required.", field="name")

    if NoteType.query.filter_by(user_id=current_user.id, name=name).first():
        return _api_error("VALIDATION_ERROR", "Note type already exists.", field="name")

    note_type = NoteType(user_id=current_user.id, name=name)
    db.session.add(note_type)
    db.session.flush()

    input_fields = payload.get("field_defs")
    if not isinstance(input_fields, list) or not input_fields:
        input_fields = [{"name": "Word", "field_type": "text", "position": 0, "required": True}]

    for idx, row in enumerate(input_fields):
        field_name = (row.get("name") or "").strip()
        field_type = (row.get("field_type") or "text").strip()
        required = bool(row.get("required", False))
        if not field_name:
            return _api_error("VALIDATION_ERROR", "Field name is required.", field="field_defs")
        if field_type not in FIELD_TYPES:
            return _api_error("VALIDATION_ERROR", f"Unsupported field_type: {field_type}", field="field_defs")
        db.session.add(
            FieldDef(
                note_type_id=note_type.id,
                name=field_name,
                field_type=field_type,
                position=int(row.get("position", idx)),
                required=required,
            )
        )

    template_payload = payload.get("template") or {}
    front_html = (template_payload.get("front_html") or "{{Word}}").strip()
    back_html = (template_payload.get("back_html") or "{{Word}}").strip()
    shared_css = (template_payload.get("shared_css") or "").strip()
    template = Template(
        note_type_id=note_type.id,
        name=(template_payload.get("name") or "Card 1").strip() or "Card 1",
        front_html=front_html,
        back_html=back_html,
        shared_css=shared_css,
        position=0,
        is_default=True,
    )
    db.session.add(template)
    _audit("note_type.create", {"note_type_id": note_type.id, "name": note_type.name})
    db.session.commit()
    return jsonify(_serialize_note_type(note_type)), 201


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
    name = (payload.get("name") or "").strip()
    if not name:
        return _api_error("VALIDATION_ERROR", "Name is required.", field="name")
    existing = NoteType.query.filter(NoteType.user_id == current_user.id, NoteType.name == name, NoteType.id != note_type.id).first()
    if existing:
        return _api_error("VALIDATION_ERROR", "Another note type already uses this name.", field="name")
    note_type.name = name
    _audit("note_type.rename", {"note_type_id": note_type.id, "name": name})
    db.session.commit()
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
    db.session.delete(note_type)
    _audit("note_type.delete", {"note_type_id": note_type_id})
    db.session.commit()
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
    max_pos = db.session.query(db.func.max(FieldDef.position)).filter_by(note_type_id=note_type.id).scalar() or -1
    field = FieldDef(
        note_type_id=note_type.id,
        name=name,
        field_type=field_type,
        required=required,
        position=max_pos + 1,
    )
    db.session.add(field)
    _audit("field.create", {"note_type_id": note_type.id, "field_id": field.id, "name": field.name})
    db.session.commit()
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

    _audit(
        "field.update",
        {"note_type_id": note_type.id, "field_id": field.id, "old_name": old_name, "new_name": field.name},
    )
    db.session.commit()
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

    db.session.delete(field)
    _audit("field.delete", {"note_type_id": note_type.id, "field_id": field_id, "field_name": field.name})
    db.session.commit()
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
    _audit("field.reorder", {"note_type_id": note_type.id})
    db.session.commit()
    return jsonify({"success": True})


@flashcards_bp.route("/api/note-types/<note_type_id>/templates", methods=["GET"])
@login_required
def list_templates(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    templates = Template.query.filter_by(note_type_id=note_type.id).order_by(Template.position.asc()).all()
    return jsonify({"items": [_serialize_template(template) for template in templates]})


@flashcards_bp.route("/api/note-types/<note_type_id>/templates", methods=["POST"])
@login_required
def create_template(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip() or f"Card {Template.query.filter_by(note_type_id=note_type.id).count() + 1}"
    front_html = (payload.get("front_html") or "{{Word}}").strip()
    back_html = (payload.get("back_html") or "{{Word}}").strip()
    shared_css = (payload.get("shared_css") or "").strip()
    max_pos = db.session.query(db.func.max(Template.position)).filter_by(note_type_id=note_type.id).scalar() or -1
    template = Template(
        note_type_id=note_type.id,
        name=name,
        front_html=front_html,
        back_html=back_html,
        shared_css=shared_css,
        position=max_pos + 1,
        is_default=False,
    )
    db.session.add(template)
    db.session.flush()
    notes = Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).all()
    for note in notes:
        db.session.add(Card(note_id=note.id, template_id=template.id, queue="new"))
    _audit("template.create", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify(_serialize_template(template)), 201


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>", methods=["PATCH"])
@login_required
def patch_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)
    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        template.name = (payload.get("name") or "").strip() or template.name
    if "front_html" in payload:
        template.front_html = str(payload.get("front_html") or "")
    if "back_html" in payload:
        template.back_html = str(payload.get("back_html") or "")
    if "shared_css" in payload:
        template.shared_css = str(payload.get("shared_css") or "")

    try:
        render_template_pair(
            template=template,
            field_defs=note_type.field_defs,
            field_values={},
            media_assets=[],
            preview_note_key="validation",
        )
    except TemplateCompileError as exc:
        db.session.rollback()
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    _audit("template.update", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify(_serialize_template(template))


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>", methods=["DELETE"])
@login_required
def delete_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)
    if template.is_default:
        return _api_error("VALIDATION_ERROR", "Cannot delete default template.", status=409)
    if Template.query.filter_by(note_type_id=note_type.id).count() <= 1:
        return _api_error("VALIDATION_ERROR", "A note type requires at least one template.", status=409)
    Card.query.filter_by(template_id=template.id).delete()
    db.session.delete(template)
    _audit("template.delete", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify({"success": True})


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>/reset", methods=["POST"])
@login_required
def reset_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)
    template.front_html = LEGACY_FRONT_TEMPLATE.strip()
    template.back_html = LEGACY_BACK_TEMPLATE.strip()
    template.shared_css = LEGACY_SHARED_CSS.strip()
    db.session.commit()
    return jsonify(_serialize_template(template))


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)

    payload = request.get_json(silent=True) or {}
    note_id = (payload.get("note_id") or "").strip()
    raw_use_sample_data = payload.get("use_sample_data", False)
    use_sample_data = bool(raw_use_sample_data)
    if isinstance(raw_use_sample_data, str):
        use_sample_data = raw_use_sample_data.strip().lower() in {"1", "true", "yes", "on"}
    
    # Cho phép ghi đè nội dung HTML/CSS thông qua payload (phục vụ Live Preview chưa lưu)
    preview_front_html = template.front_html
    preview_back_html = template.back_html
    preview_shared_css = template.shared_css
    if "front_html" in payload:
        preview_front_html = str(payload.get("front_html") or "")
    if "back_html" in payload:
        preview_back_html = str(payload.get("back_html") or "")
    if "shared_css" in payload:
        preview_shared_css = str(payload.get("shared_css") or "")

    preview_template_obj = SimpleNamespace(
        id=template.id,
        front_html=preview_front_html,
        back_html=preview_back_html,
        shared_css=preview_shared_css,
        updated_at=template.updated_at,
    )

    sample_field_values: dict[str, Any]
    sample_media_assets: list[MediaAsset]
    preview_note_key: str
    if use_sample_data:
        sample_field_values = _build_preview_sample_values(note_type.field_defs)
        sample_media_assets = []
        preview_note_key = f"sample:{note_type.id}"
    else:
        note = None
        if note_id:
            note = Note.query.filter_by(id=note_id, user_id=current_user.id, note_type_id=note_type.id).first()
        if note is None:
            note = (
                Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id)
                .order_by(Note.created_at.asc())
                .first()
            )
        sample_field_values = {}
        sample_media_assets = []
        preview_note_key = note.id if note else "empty-note"
        if note:
            sample_field_values = note.field_values or {}
            sample_media_assets = note.media_assets

    try:
        rendered = render_template_pair(
            template=preview_template_obj,
            field_defs=note_type.field_defs,
            field_values=sample_field_values,
            media_assets=sample_media_assets,
            preview_note_key=preview_note_key,
            allow_inline_script=True,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    return jsonify(rendered)


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

    note = Note(
        note_type_id=note_type.id,
        user_id=current_user.id,
        deck_id=parsed_deck_id,
        field_values=cleaned_values,
        tags=tags,
    )
    db.session.add(note)
    db.session.flush()
    _create_cards_for_note(note)
    _audit("note.create", {"note_id": note.id, "note_type_id": note.note_type_id})
    db.session.commit()
    return jsonify({"id": note.id, "field_values": note.field_values, "tags": note.tags}), 201


@flashcards_bp.route("/api/notes/<note_id>", methods=["GET"])
@login_required
def get_note(note_id: str):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    return jsonify(
        {
            "id": note.id,
            "note_type_id": note.note_type_id,
            "deck_id": note.deck_id,
            "field_values": note.field_values or {},
            "tags": note.tags or [],
            "media_assets": [
                {
                    "id": asset.id,
                    "field_name": asset.field_name,
                    "filename": asset.filename,
                    "mime_type": asset.mime_type,
                    "url": f"/media/proxy/{asset.id}",
                }
                for asset in note.media_assets
            ],
        }
    )


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
    _audit("note.update", {"note_id": note.id})
    db.session.commit()
    return jsonify({"id": note.id, "field_values": note.field_values, "tags": note.tags})


@flashcards_bp.route("/api/notes/<note_id>", methods=["DELETE"])
@login_required
def delete_note(note_id: str):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    db.session.delete(note)
    _audit("note.delete", {"note_id": note_id})
    db.session.commit()
    return jsonify({"success": True})


@flashcards_bp.route("/api/notes/<note_id>/media", methods=["POST"])
@login_required
def upload_note_media(note_id: str):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    field_name = (request.form.get("field_name") or "").strip()
    if not field_name:
        return _api_error("VALIDATION_ERROR", "field_name is required.", field="field_name")
    field_def = FieldDef.query.filter_by(note_type_id=note.note_type_id, name=field_name).first()
    if not field_def:
        return _api_error("FIELD_NOT_FOUND", "Field not found in note type.", field="field_name", status=404)
    if field_def.field_type not in {"image", "audio", "diagram"}:
        return _api_error("VALIDATION_ERROR", "Field does not accept media.", field="field_name")

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return _api_error("VALIDATION_ERROR", "Missing uploaded file.", field="file")

    content = uploaded.read()
    if not content:
        return _api_error("VALIDATION_ERROR", "Uploaded file is empty.", field="file")

    max_bytes = int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024))
    if len(content) > max_bytes:
        return _api_error("MEDIA_TOO_LARGE", f"File exceeds {max_bytes} bytes.", field="file", status=413)

    mime_type = uploaded.mimetype or "application/octet-stream"
    if mime_type not in ALLOWED_MEDIA_MIME_TYPES:
        return _api_error("MEDIA_TYPE_NOT_ALLOWED", f"Unsupported media type: {mime_type}", field="file", status=415)

    digest = hashlib.sha256(content).hexdigest()
    existing = MediaAsset.query.filter_by(note_id=note.id, field_name=field_name, sha256=digest).first()
    if existing:
        values = dict(note.field_values or {})
        values[field_name] = existing.id
        note.field_values = values
        db.session.commit()
        return jsonify({"asset_id": existing.id, "url": f"/media/proxy/{existing.id}", "field_name": field_name})

    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"])
    safe_name = Path(uploaded.filename).name.replace(" ", "_")
    relative_dir = Path(str(current_user.id)) / note.id
    final_dir = upload_root / relative_dir
    final_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{digest[:8]}_{safe_name}"
    relative_path = relative_dir / filename
    full_path = upload_root / relative_path
    full_path.write_bytes(content)

    asset = MediaAsset(
        note_id=note.id,
        field_name=field_name,
        filename=safe_name,
        mime_type=mime_type,
        storage_path=str(relative_path).replace("\\", "/"),
        sha256=digest,
        size_bytes=len(content),
    )
    db.session.add(asset)
    db.session.flush()
    values = dict(note.field_values or {})
    values[field_name] = asset.id
    note.field_values = values
    _audit("media.upload", {"note_id": note.id, "asset_id": asset.id, "field_name": field_name})
    db.session.commit()
    return jsonify({"asset_id": asset.id, "url": f"/media/proxy/{asset.id}", "field_name": field_name}), 201


@flashcards_bp.route("/api/media/<asset_id>", methods=["DELETE"])
@login_required
def delete_media(asset_id: str):
    asset = (
        MediaAsset.query.join(Note, MediaAsset.note_id == Note.id)
        .filter(MediaAsset.id == asset_id, Note.user_id == current_user.id)
        .first()
    )
    if not asset:
        return _api_error("FIELD_NOT_FOUND", "Media asset not found.", status=404)
    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"])
    full_path = (upload_root / asset.storage_path).resolve()
    if full_path.exists():
        try:
            full_path.unlink()
        except OSError:
            logger.warning("Failed to delete media file %s", full_path)
    note = asset.note
    values = dict(note.field_values or {})
    if values.get(asset.field_name) == asset.id:
        values[asset.field_name] = ""
        note.field_values = values
    db.session.delete(asset)
    _audit("media.delete", {"asset_id": asset_id, "note_id": note.id})
    db.session.commit()
    return jsonify({"success": True})


@flashcards_bp.route("/media/proxy/<asset_id>", methods=["GET"])
@login_required
def proxy_media(asset_id: str):
    asset = (
        MediaAsset.query.join(Note, MediaAsset.note_id == Note.id)
        .filter(MediaAsset.id == asset_id, Note.user_id == current_user.id)
        .first()
    )
    if not asset:
        return _api_error("FIELD_NOT_FOUND", "Media asset not found.", status=404)
    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"])
    full_path = (upload_root / asset.storage_path).resolve()
    if not full_path.exists():
        return _api_error("FIELD_NOT_FOUND", "Media file not found on disk.", status=404)
    return send_file(full_path, mimetype=asset.mime_type, conditional=True, max_age=3600)


@flashcards_bp.route("/api/study/next", methods=["GET"])
@login_required
def study_next():
    scope = (request.args.get("scope") or "deck").strip().lower()
    scope_id_raw = (request.args.get("scope_id") or "").strip()

    query = Card.query.join(Note, Card.note_id == Note.id).filter(Note.user_id == current_user.id)
    if scope == "deck":
        if not scope_id_raw:
            return _api_error("VALIDATION_ERROR", "scope_id is required for deck scope.", field="scope_id")
        try:
            scope_id = int(scope_id_raw)
        except ValueError:
            return _api_error("VALIDATION_ERROR", "scope_id must be an integer for deck scope.", field="scope_id")
        query = query.filter(Note.deck_id == scope_id)
    elif scope == "note_type":
        if not scope_id_raw:
            return _api_error("VALIDATION_ERROR", "scope_id is required for note_type scope.", field="scope_id")
        query = query.filter(Note.note_type_id == scope_id_raw)
    else:
        return _api_error("VALIDATION_ERROR", f"Unsupported scope: {scope}", field="scope")

    cards = query.order_by(Card.created_at.asc(), Card.id.asc()).all()
    if not cards:
        return jsonify({"card_id": None, "message": "No cards found for selected scope."})

    card_ids = [card.id for card in cards]
    progress_rows = VocabularyProgress.query.filter(
        VocabularyProgress.user_id == current_user.id,
        VocabularyProgress.new_card_id.in_(card_ids),
    ).all()
    progress_map = {row.new_card_id: row for row in progress_rows if row.new_card_id}
    now = datetime.utcnow()
    selected_card = _pick_due_card(cards, progress_map, now)
    if not selected_card:
        return jsonify({"card_id": None, "message": "No due cards."})

    progress = progress_map.get(selected_card.id)
    card_state = _card_state_from_progress(progress, now)
    interval_preview = computeAnswerPreview(card_state, default_deck_options(), now)

    note = selected_card.note
    template = selected_card.template
    try:
        rendered = render_template_pair(
            template=template,
            field_defs=note.note_type.field_defs,
            field_values=note.field_values or {},
            media_assets=note.media_assets,
            allow_inline_script=True,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc))

    return jsonify(
        {
            "card_id": selected_card.id,
            "note_id": note.id,
            "template_id": template.id,
            "rendered_front_html": rendered["front_html"],
            "rendered_back_html": rendered["back_html"],
            "intervals_preview": interval_preview,
        }
    )


@flashcards_bp.route("/api/study/<card_id>/answer", methods=["POST"])
@login_required
def study_answer(card_id: str):
    payload = request.get_json(silent=True) or {}
    rating = (payload.get("rating") or "").strip().lower()
    if rating not in {"again", "hard", "good", "easy"}:
        return _api_error("VALIDATION_ERROR", "rating must be one of: again, hard, good, easy.", field="rating")

    card = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id, Note.user_id == current_user.id).first()
    if not card:
        return _api_error("FIELD_NOT_FOUND", "Card not found.", status=404)

    progress = VocabularyProgress.query.filter_by(user_id=current_user.id, new_card_id=card.id).first()
    if progress is None:
        progress = VocabularyProgress(
            user_id=current_user.id,
            entry_id=None,
            new_card_id=card.id,
            queue="new",
            step_index=0,
            due_at=None,
            due_day=None,
            interval_days=0,
            ease_factor=default_deck_options().startingEase,
            reps=0,
            lapses=0,
        )
        db.session.add(progress)
        db.session.flush()

    now = datetime.utcnow()
    current_state = _card_state_from_progress(progress, now)
    updated_state = applyAnswer(current_state, default_deck_options(), now, rating)  # type: ignore[arg-type]
    _apply_card_state_to_progress(progress, updated_state, now)
    _audit("study.answer", {"card_id": card.id, "rating": rating})
    db.session.commit()
    next_url = url_for("flashcards.study_next", scope="deck", scope_id=card.note.deck_id) if card.note.deck_id else None
    return jsonify({"success": True, "next_card_url": next_url, "intervals_preview": computeAnswerPreview(updated_state, default_deck_options(), now)})


@flashcards_bp.route("/api/flashcards/seed-legacy", methods=["POST"])
@login_required
def seed_legacy_note_type():
    if not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Admin only endpoint.", status=403)
    note_type, template = ensure_legacy_note_type(db.session, current_user.id)
    _audit("legacy.seed", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify({"note_type_id": note_type.id, "template_id": template.id})
