"""Data-access helpers for in-study card editing."""

from __future__ import annotations

from sqlalchemy.orm import selectinload

from models import db
from models.flashcard import Card, Note, NoteType


def load_owned_card_for_study_edit(*, user_id: int, card_id: str) -> Card | None:
    """Return a card that belongs to the current user's note, or None."""
    return (
        Card.query.join(Note, Card.note_id == Note.id)
        .options(
            selectinload(Card.template),
            selectinload(Card.note).selectinload(Note.media_assets),
            selectinload(Card.note)
            .selectinload(Note.note_type)
            .selectinload(NoteType.field_defs),
        )
        .filter(
            Card.id == card_id,
            Note.user_id == user_id,
        )
        .first()
    )


def commit_note_edit() -> None:
    db.session.commit()
