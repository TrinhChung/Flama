from datetime import datetime

from models import db
from models.model_uuid import uuid_str

LIVE_FIELD_VALUE_CODEC = "field-id.v1"


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    note_type_id = db.Column(db.String(36), db.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    deck_id = db.Column(db.Integer, db.ForeignKey("decks.id", ondelete="SET NULL"), nullable=True, index=True)
    # The only live value store. Labels are projected at API/render boundaries.
    field_values_by_id = db.Column(db.JSON, nullable=False, default=dict)
    field_values_codec = db.Column(db.String(32), nullable=False, default="field-id.v1", server_default="field-id.v1")
    field_values_extras = db.Column(db.JSON, nullable=False, default=dict)
    content_revision = db.Column(db.BigInteger, nullable=False, default=0, server_default="0")
    tags = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    __mapper_args__ = {"version_id_col": content_revision, "version_id_generator": False}
    __table_args__ = (db.Index('ix_notes_user_deck', 'user_id', 'deck_id'),)

    note_type = db.relationship("NoteType", back_populates="notes")
    # Derived presentations (ADR P11): one per ACTIVE application of the NoteType.
    cards = db.relationship(
        "Card", primaryjoin="foreign(Card.note_id) == Note.id", viewonly=True, order_by="Card.id"
    )
    media_assets = db.relationship("MediaAsset", back_populates="note", cascade="all, delete-orphan")

    @property
    def field_values(self):
        from app.services.field_value_runtime_service import read_note_named_values
        return read_note_named_values(self)

    @field_values.setter
    def field_values(self, values):
        from app.services.field_value_runtime_service import write_note_named_values
        write_note_named_values(self, values)
