"""Service for note type management and transactions."""

from __future__ import annotations

from models import db
from models.flashcard import NoteType, Template
from app.routes.flashcards import _audit


def update_note_type_and_commit(note_type: NoteType) -> None:
    _audit("note_type.update", {"note_type_id": note_type.id})
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
