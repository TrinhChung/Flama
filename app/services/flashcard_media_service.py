"""Service for handling transaction commits for media assets and templates."""

from __future__ import annotations

from models import db
from models.flashcard import Template, MediaAsset, Note
from app.routes.flashcards import _audit

def delete_template_and_commit(template: Template, note_type_id: str) -> None:
    db.session.delete(template)
    _audit("template.delete", {"note_type_id": note_type_id, "template_id": template.id})
    db.session.commit()

def upload_note_media_and_commit(note: Note, asset: MediaAsset, field_name: str) -> None:
    db.session.add(asset)
    db.session.flush()
    values = dict(note.field_values or {})
    values[field_name] = asset.id
    note.field_values = values
    _audit("media.upload", {"note_id": note.id, "asset_id": asset.id, "field_name": field_name})
    db.session.commit()
    
def link_existing_media_and_commit(note: Note, existing_asset: MediaAsset, field_name: str) -> None:
    values = dict(note.field_values or {})
    values[field_name] = existing_asset.id
    note.field_values = values
    db.session.commit()

def delete_media_and_commit(asset: MediaAsset) -> None:
    note = asset.note
    values = dict(note.field_values or {})
    if values.get(asset.field_name) == asset.id:
        values[asset.field_name] = ""
        note.field_values = values
    db.session.delete(asset)
    _audit("media.delete", {"asset_id": asset.id, "note_id": note.id})
    db.session.commit()
