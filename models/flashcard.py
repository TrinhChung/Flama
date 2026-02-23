"""Flashcard v2 domain models (note type, note, template, card, media)."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import UniqueConstraint

from models import db


def _uuid_str() -> str:
    return str(uuid4())


class NoteType(db.Model):
    __tablename__ = "note_types"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    field_defs = db.relationship(
        "FieldDef",
        back_populates="note_type",
        cascade="all, delete-orphan",
        order_by="FieldDef.position",
    )
    templates = db.relationship(
        "Template",
        back_populates="note_type",
        cascade="all, delete-orphan",
        order_by="Template.position",
    )
    notes = db.relationship(
        "Note",
        back_populates="note_type",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_note_types_user_name"),
    )


class FieldDef(db.Model):
    __tablename__ = "field_defs"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    note_type_id = db.Column(db.String(36), db.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    field_type = db.Column(
        db.Enum("text", "richtext", "image", "audio", "diagram", name="field_type_enum", native_enum=False),
        nullable=False,
        default="text",
    )
    position = db.Column(db.Integer, nullable=False, default=0)
    required = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    note_type = db.relationship("NoteType", back_populates="field_defs")

    __table_args__ = (
        UniqueConstraint("note_type_id", "name", name="uq_field_defs_note_type_name"),
    )


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    note_type_id = db.Column(db.String(36), db.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    front_html = db.Column(db.Text, nullable=False, default="")
    back_html = db.Column(db.Text, nullable=False, default="")
    shared_css = db.Column(db.Text, nullable=False, default="")
    position = db.Column(db.Integer, nullable=False, default=0)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    note_type = db.relationship("NoteType", back_populates="templates")
    cards = db.relationship("Card", back_populates="template")


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    note_type_id = db.Column(db.String(36), db.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    deck_id = db.Column(db.Integer, db.ForeignKey("vocabulary_decks.id", ondelete="SET NULL"), nullable=True, index=True)
    field_values = db.Column(db.JSON, nullable=False, default=dict)
    tags = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    note_type = db.relationship("NoteType", back_populates="notes")
    cards = db.relationship("Card", back_populates="note", cascade="all, delete-orphan")
    media_assets = db.relationship("MediaAsset", back_populates="note", cascade="all, delete-orphan")


class Card(db.Model):
    __tablename__ = "cards"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    note_id = db.Column(db.String(36), db.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = db.Column(db.String(36), db.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True)
    queue = db.Column(db.String(20), nullable=False, default="new", index=True)
    due_at = db.Column(db.DateTime, nullable=True, index=True)
    due_day = db.Column(db.Integer, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    note = db.relationship("Note", back_populates="cards")
    template = db.relationship("Template", back_populates="cards")

    __table_args__ = (
        UniqueConstraint("note_id", "template_id", name="uq_cards_note_template"),
    )


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    note_id = db.Column(db.String(36), db.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    field_name = db.Column(db.String(255), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(1024), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    note = db.relationship("Note", back_populates="media_assets")

    __table_args__ = (
        UniqueConstraint("note_id", "sha256", "field_name", name="uq_media_assets_note_sha_field"),
    )


class FieldRenameJob(db.Model):
    __tablename__ = "field_rename_jobs"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    note_type_id = db.Column(db.String(36), db.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    field_def_id = db.Column(db.String(36), db.ForeignKey("field_defs.id", ondelete="CASCADE"), nullable=False, index=True)
    old_name = db.Column(db.String(255), nullable=False)
    new_name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="pending")
    total_notes = db.Column(db.Integer, nullable=False, default=0)
    processed_notes = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LegacyMigrationMap(db.Model):
    __tablename__ = "legacy_migration_maps"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    entry_id = db.Column(db.Integer, db.ForeignKey("vocabulary_entries.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    note_id = db.Column(db.String(36), db.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id = db.Column(db.String(36), db.ForeignKey("cards.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
