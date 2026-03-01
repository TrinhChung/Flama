"""Deck access policy and tree query services."""

from __future__ import annotations

from typing import TYPE_CHECKING
from models.deck import Deck
from app.utils.permissions import is_admin_user

if TYPE_CHECKING:
    from models.user import User

def can_user_edit_deck(user: User, deck: Deck) -> bool:
    """Check if a user can edit/share a deck."""
    if is_admin_user(user):
        return True
    return deck.owner_user_id == user.id

def can_user_view_deck(user: User, deck: Deck) -> bool:
    """Check if a user can view a deck."""
    if is_admin_user(user):
        return True
    return deck.owner_user_id == user.id

def is_deck_owned_by(user: User, deck: Deck) -> bool:
    """Strictly checks authorship."""
    return deck.owner_user_id == user.id
