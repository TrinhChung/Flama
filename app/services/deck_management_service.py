"""Deck management services encapsulating transaction boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.exc import SQLAlchemyError

from models import db
from models.deck import Deck
from models.flashcard import Card, DeckCloneDeckMap, DeckInstall, DeckMarketplaceItem, Note
from models.card_progress import CardProgress
from app.repositories import vocabulary_repository as vocabulary_ctrl
from app.repositories.deck_tree_query import (
    collect_ancestor_ids as _collect_deck_ancestor_ids,
    collect_subtree_ids as _collect_deck_subtree_ids,
)
from app.utils.deck_move_token import parse_deck_move_token

UTC = timezone.utc

class DeckManagementError(Exception):
    pass

def create_decks_path(*, tokens: List[str], parent_id: Optional[int] = None) -> tuple[int, Optional[Deck]]:
    """Creates a path of decks under the given parent_id mapping tokens to deck names.
    Commits the transaction and returns the number of newly created decks and the deepest leaf Deck.
    """
    created_count = 0
    final_deck = None
    current_parent_id = parent_id

    for token in tokens:
        existing = (
            Deck.query.filter(
                Deck.parent_id == current_parent_id,
                Deck.name == token,
            )
            .order_by(Deck.id.asc())
            .first()
        )
        if existing:
            final_deck = existing
            current_parent_id = existing.id
            continue

        position = vocabulary_ctrl.next_deck_position(current_parent_id)
        node = Deck(
            parent_id=current_parent_id,
            name=token,
            position=position,
        )
        db.session.add(node)
        db.session.flush()
        created_count += 1
        final_deck = node
        current_parent_id = node.id

    db.session.commit()
    return created_count, final_deck

def rename_deck(*, deck_obj: Deck, new_name: str) -> None:
    """Renames a deck and commits the transaction."""
    deck_obj.name = new_name
    db.session.commit()

def move_deck(*, deck_obj: Deck, new_parent_id: Optional[int]) -> None:
    """Moves a deck under a new parent and commits the transaction."""
    deck_obj.parent_id = new_parent_id
    deck_obj.position = vocabulary_ctrl.next_deck_position(new_parent_id)
    db.session.commit()

def delete_deck_subtree(*, deck_obj: Deck, user_id: int, is_admin: bool) -> str:
    """Delete a local deck, or archive a shared source while preserving installs."""
    deck_ids_to_delete = _collect_deck_subtree_ids(deck_obj.id)

    marketplace_source_ids = set(deck_ids_to_delete)
    marketplace_source_ids.update(_collect_deck_ancestor_ids(deck_obj.id))
    marketplace_items = (
        DeckMarketplaceItem.query.filter(
            DeckMarketplaceItem.source_deck_id.in_(marketplace_source_ids)
        ).all()
    )
    has_overlay_dependents = (
        db.session.query(DeckCloneDeckMap.id)
        .filter(DeckCloneDeckMap.source_deck_id.in_(deck_ids_to_delete))
        .first()
        is not None
    )
    has_source_installs = (
        db.session.query(DeckInstall.id)
        .filter(DeckInstall.source_deck_id.in_(deck_ids_to_delete))
        .first()
        is not None
    )

    if marketplace_items or has_overlay_dependents or has_source_installs:
        deleted_at = datetime.now(UTC).replace(tzinfo=None)
        Deck.query.filter(Deck.id.in_(deck_ids_to_delete)).update(
            {Deck.deleted_at: deleted_at},
            synchronize_session=False,
        )
        for marketplace_item in marketplace_items:
            marketplace_item.publish_status = "archived"
            marketplace_item.archived_at = deleted_at
        db.session.commit()
        return "archived"

    install_query = DeckInstall.query.filter(DeckInstall.local_deck_id.in_(deck_ids_to_delete))
    if not is_admin:
        install_query = install_query.filter(DeckInstall.user_id == user_id)
    install_query.delete(synchronize_session=False)

    note_rows = db.session.query(Note.id).filter(Note.deck_id.in_(deck_ids_to_delete)).all()
    note_ids = [str(row[0]) for row in note_rows if row and row[0]]
    if note_ids:
        card_rows = db.session.query(Card.id).filter(Card.note_id.in_(note_ids)).all()
        card_ids = [str(row[0]) for row in card_rows if row and row[0]]
        if card_ids:
            CardProgress.query.filter(CardProgress.card_id.in_(card_ids)).delete(
                synchronize_session=False
            )
            Card.query.filter(Card.id.in_(card_ids)).delete(synchronize_session=False)
        Note.query.filter(Note.id.in_(note_ids)).delete(synchronize_session=False)

    db.session.delete(deck_obj)
    db.session.commit()
    return "deleted"

def reset_deck_progress(*, deck_obj: Deck, user_id: int) -> int:
    """Resets the review progress for all cards in a deck subtree for a specific user. Commits."""
    deck_ids = _collect_deck_subtree_ids(deck_obj.id)
    card_rows = (
        db.session.query(Card.id)
        .join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id.in_(deck_ids))
        .all()
    )
    card_ids = [str(row[0]) for row in card_rows if row and row[0]]

    deleted_count = 0
    if card_ids:
        deleted_count = CardProgress.query.filter(
            CardProgress.user_id == user_id,
            CardProgress.card_id.in_(card_ids),
        ).delete(synchronize_session=False) or 0
        db.session.commit()
    return deleted_count
