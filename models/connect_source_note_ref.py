from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class ConnectSourceNoteRef(db.Model):
    __tablename__ = "connect_source_note_refs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_key = db.Column(db.String(255), nullable=False)
    external_note_id = db.Column(db.String(128), nullable=False)
    source_model_id = db.Column(db.String(128), nullable=False)
    source_deck_path = db.Column(db.String(2048), nullable=False)
    note_id = db.Column(
        db.String(36),
        db.ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_hash = db.Column(db.String(64), nullable=False)
    last_session_id = db.Column(
        db.String(36),
        db.ForeignKey("connect_import_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    note = db.relationship("Note", foreign_keys=[note_id])

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_key",
            "external_note_id",
            name="uq_connect_source_note_refs_source_note",
        ),
    )

