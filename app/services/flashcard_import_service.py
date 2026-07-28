"""Service for handling transaction commits for flashcard imports and exports."""

from __future__ import annotations

from models import db
from models.flashcard import DeckMarketplaceItem, NoteType
from models.user import User
from app.routes.flashcards import _audit


def admin_user_set_is_admin(system_admin: User) -> None:
    system_admin.is_admin = True
    db.session.commit()


def share_deck_and_commit(existing_item: DeckMarketplaceItem, is_new: bool) -> None:
    if is_new:
        db.session.add(existing_item)
    db.session.commit()


def seed_marketplace_defaults_commit(
    admin_id: int,
    note_type: NoteType,
    deck_item: DeckMarketplaceItem,
    is_new_deck_item: bool,
) -> None:
    if is_new_deck_item:
        db.session.add(deck_item)

    _audit("market.seed_defaults", {"note_type_id": note_type.id, "deck_item_id": deck_item.id})
    db.session.commit()
