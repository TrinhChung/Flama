from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
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

