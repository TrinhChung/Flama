"""Service for handling transaction commits for flashcard imports and exports."""

from __future__ import annotations

from models import db
from models.flashcard import DeckMarketplaceItem, NoteType
from models.user import User
from app.routes.flashcards import _audit

def admin_user_ensure_created(admin_email: str, admin_user_name: str, admin_password: str) -> User:
    system_admin = User.query.filter_by(email=admin_email).first()
    if not system_admin:
        system_admin = User(
            email=admin_email,
            username=admin_user_name,
            is_admin=True,
        )
        system_admin.set_password(admin_password)
        db.session.add(system_admin)
        db.session.commit()
    return system_admin

def admin_user_set_is_admin(system_admin: User) -> None:
    system_admin.is_admin = True
    db.session.commit()

def share_deck_and_commit(existing_item: DeckMarketplaceItem, is_new: bool) -> None:
    if is_new:
        db.session.add(existing_item)
    db.session.commit()

def flashcard_import_execute_commit(note_type: NoteType, target_deck_id: int, mode: str, summary: dict) -> None:
    _audit(
        "note.import",
        {
            "note_type_id": note_type.id,
            "target_deck_id": target_deck_id,
            "mode": mode,
            "summary": summary,
        },
    )
    db.session.commit()

def seed_marketplace_defaults_commit(
    admin_id: int,
    note_type: NoteType, 
    deck_item: DeckMarketplaceItem, 
    is_new_deck_item: bool
) -> None:
    if is_new_deck_item:
        db.session.add(deck_item)
    
    _audit("market.seed_defaults", {"note_type_id": note_type.id, "deck_item_id": deck_item.id})
    db.session.commit()
