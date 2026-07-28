"""Deck response presenters."""

from __future__ import annotations

from models.deck import Deck


def serialize_deck(deck: Deck) -> dict:
    return {
        "id": int(deck.id),
        "name": str(deck.name or ""),
        "parent_id": (
            int(deck.parent_id) if deck.parent_id is not None else None
        ),
        "owner_user_id": (
            int(deck.owner_user_id)
            if deck.owner_user_id is not None
            else None
        ),
        "position": int(deck.position or 0),
        "deleted_at": (
            deck.deleted_at.isoformat() if deck.deleted_at else None
        ),
        "created_at": (
            deck.created_at.isoformat() if deck.created_at else None
        ),
        "updated_at": (
            deck.updated_at.isoformat() if deck.updated_at else None
        ),
    }
