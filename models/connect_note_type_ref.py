from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class ConnectNoteTypeRef(db.Model):
    __tablename__ = "connect_note_type_refs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_key = db.Column(db.String(255), nullable=False)
    external_model_id = db.Column(db.String(128), nullable=False)
    external_model_name = db.Column(db.String(255), nullable=False)
    note_type_id = db.Column(
        db.String(36),
        db.ForeignKey("note_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    schema_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    note_type = db.relationship("NoteType", foreign_keys=[note_type_id])

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_key",
            "external_model_id",
            name="uq_connect_note_type_refs_source_model",
        ),
    )

