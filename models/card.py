from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class Card(db.Model):
    __tablename__ = "cards"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
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

