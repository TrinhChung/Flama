"""Data-access helpers for browse card detail and edit flows."""

from __future__ import annotations

from sqlalchemy.orm import selectinload

from app.repositories import vocabulary_repository as vocabulary_ctrl
from models import db
from models.card_progress import CardProgress
from models.deck import Deck
from models.flashcard import Card, Note, NoteType


def load_card_for_browse_update(*, card_id: str) -> Card | None:
    """Return a browse card with note, note type, media, and template preloaded."""
    return (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Card.id == card_id)
        .options(
            selectinload(Card.note).selectinload(Note.note_type).selectinload(NoteType.field_defs),
            selectinload(Card.note).selectinload(Note.media_assets),
            selectinload(Card.template),
        )
        .first()
    )


def load_browse_progress(*, user_id: int, card_id: str) -> CardProgress | None:
    return CardProgress.query.filter_by(user_id=user_id, card_id=card_id).first()


def load_accessible_browse_decks(*, user_id: int, admin_mode: bool) -> list[Deck]:
    return vocabulary_ctrl.collect_accessible_browse_decks(
        user_id=user_id,
        admin_mode=admin_mode,
    )


def deck_lookup_for_browse(*, user_id: int, admin_mode: bool) -> dict[int, str]:
    return {
        deck.id: deck.name
        for deck in load_accessible_browse_decks(user_id=user_id, admin_mode=admin_mode)
    }


def accessible_browse_deck_ids(*, user_id: int, admin_mode: bool) -> set[int]:
    return {
        int(deck.id)
        for deck in load_accessible_browse_decks(user_id=user_id, admin_mode=admin_mode)
        if deck.id is not None
    }


def get_deck(*, deck_id: int) -> Deck | None:
    return db.session.get(Deck, deck_id)


def commit_changes() -> None:
    db.session.commit()


def rollback_changes() -> None:
    db.session.rollback()
