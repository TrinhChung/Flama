from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class DeckCloneAddedNote(db.Model):
    __tablename__ = "deck_clone_added_notes"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    deck_install_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_installs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    note_id = db.Column(
        db.String(36),
        db.ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    deck_install = db.relationship("DeckInstall", back_populates="clone_added_notes")
    note = db.relationship("Note", foreign_keys=[note_id])
