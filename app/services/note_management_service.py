"""Note management services encapsulating transaction boundaries."""

from __future__ import annotations

from typing import Dict, Any, Optional

from sqlalchemy.exc import SQLAlchemyError

from models import db
from models.flashcard import Note

def update_note_fields_and_deck(
    *, 
    note_obj: Note, 
    field_values: Dict[str, str], 
    new_deck_id: Optional[int] = None, 
    tags: Optional[list[str]] = None,
    update_deck: bool = False,
    update_tags: bool = False
) -> None:
    """Update fields, deck, and tags of a Note and commit to transaction."""
    note_obj.field_values = field_values
    
    if update_deck:
        note_obj.deck_id = new_deck_id
        
    if update_tags and tags is not None:
        note_obj.tags = tags
        
    db.session.commit()
