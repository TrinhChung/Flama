from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    note_type_id = db.Column(db.String(36), db.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    deck_id = db.Column(db.Integer, db.ForeignKey("decks.id", ondelete="SET NULL"), nullable=True, index=True)
    field_values = db.Column(db.JSON, nullable=False, default=dict)
    tags = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    note_type = db.relationship("NoteType", back_populates="notes")
    cards = db.relationship("Card", back_populates="note", cascade="all, delete-orphan")
    media_assets = db.relationship("MediaAsset", back_populates="note", cascade="all, delete-orphan")
