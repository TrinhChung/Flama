"""Service for note type management and transactions."""

from __future__ import annotations

from typing import Any

from models import db
from models.flashcard import NoteType, FieldDef, Note, NoteTypeInstall, Template
from app.routes.flashcards import _audit

def get_max_field_position(note_type_id: str) -> int:
    return db.session.query(db.func.max(FieldDef.position)).filter_by(note_type_id=note_type_id).scalar() or -1

def update_note_type_and_commit(note_type: NoteType) -> None:
    _audit("note_type.update", {"note_type_id": note_type.id})
    db.session.commit()

def delete_note_type_and_commit(note_type: NoteType) -> None:
    db.session.delete(note_type)
    _audit("note_type.delete", {"note_type_id": note_type.id})
    db.session.commit()

def create_field_and_commit(field: FieldDef, note_type_id: str) -> None:
    db.session.add(field)
    _audit("field.create", {"note_type_id": note_type_id, "field_id": field.id, "name": field.name})
    db.session.commit()

def update_field_and_commit(note_type_id: str, field_id: str, old_name: str, new_name: str) -> None:
    _audit(
        "field.update",
        {"note_type_id": note_type_id, "field_id": field_id, "old_name": old_name, "new_name": new_name},
    )
    db.session.commit()

def delete_field_and_commit(field: FieldDef, note_type_id: str) -> None:
    db.session.delete(field)
    _audit("field.delete", {"note_type_id": note_type_id, "field_id": field.id, "field_name": field.name})
    db.session.commit()

def reorder_fields_and_commit(note_type_id: str) -> None:
    _audit("field.reorder", {"note_type_id": note_type_id})
    db.session.commit()

def create_note_and_commit(note: Note, user_id: int) -> None:
    from app.routes.flashcards import _create_cards_for_note, _touch_note_type_install_usage, _recompute_note_type_market_stats
    db.session.add(note)
    db.session.flush()
    _create_cards_for_note(note)
    _touch_note_type_install_usage(user_id=user_id, installed_note_type_id=note.note_type_id)
    install_rows = NoteTypeInstall.query.filter_by(
        user_id=user_id,
        installed_note_type_id=note.note_type_id,
    ).all()
    for install in install_rows:
        source_note_type = NoteType.query.get(install.source_note_type_id)
        if source_note_type:
            _recompute_note_type_market_stats(source_note_type)
    _audit("note.create", {"note_id": note.id, "note_type_id": note.note_type_id})
    db.session.commit()

def update_note_and_commit(note_id: str) -> None:
    _audit("note.update", {"note_id": note_id})
    db.session.commit()

def delete_note_and_commit(note: Note) -> None:
    db.session.delete(note)
    _audit("note.delete", {"note_id": note.id})
    db.session.commit()

def ensure_legacy_note_type_and_commit(user_id: int) -> tuple[NoteType, Template]:
    from app.services.flashcard_legacy import ensure_legacy_note_type, ensure_quiz_note_type
    note_type, template = ensure_legacy_note_type(db.session, user_id)
    quiz_note_type, quiz_template = ensure_quiz_note_type(db.session, user_id)
    _audit("note_type.seed_default", {"note_type_id": note_type.id, "template_id": template.id})
    _audit(
        "note_type.seed_default",
        {"note_type_id": quiz_note_type.id, "template_id": quiz_template.id},
    )
    db.session.commit()
    return note_type, template
