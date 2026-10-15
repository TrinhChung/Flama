from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property

from models import db
from models.model_uuid import uuid_str


class MediaAsset(db.Model):
    __tablename__ = "media_assets"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    note_id = db.Column(db.String(36), db.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True)
    _field_name = db.Column("field_name", db.String(255), nullable=False)
    # Scoped by note.note_type_id; retained after a FieldDef is removed.
    # No FK: historical media identity must survive schema changes.
    field_def_id = db.Column(db.String(36), nullable=True)
    # Scoped stable identity; field_name and field_def_id are historical labels.
    field_identity_key = db.Column(db.String(115), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(1024), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    note = db.relationship("Note", back_populates="media_assets")

    __table_args__ = (
        UniqueConstraint("note_id", "sha256", "field_identity_key", name="uq_media_assets_note_sha_identity"),
    )

    @hybrid_property
    def field_name(self):
        from app.services.field_value_runtime_service import read_media_field_label
        return read_media_field_label(self)

    @field_name.setter
    def field_name(self, value):
        self._field_name = value

    @field_name.expression
    def field_name(cls):
        # Only historical audit queries use the stored advisory label.
        return cls._field_name

