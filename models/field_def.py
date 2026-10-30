from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.field_types import FIELD_TYPES
from models.model_uuid import uuid_str


class FieldDef(db.Model):
    __tablename__ = "field_defs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    note_type_id = db.Column(db.String(36), db.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    field_type = db.Column(
        db.Enum(*FIELD_TYPES, name="field_type_enum", native_enum=False),
        nullable=False,
        default="text",
    )
    position = db.Column(db.Integer, nullable=False, default=0)
    required = db.Column(db.Boolean, nullable=False, default=False)
    identity_role = db.Column(db.String(32), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    note_type = db.relationship("NoteType", back_populates="field_defs")

    __table_args__ = (
        UniqueConstraint("note_type_id", "name", name="uq_field_defs_note_type_name"),
        UniqueConstraint("note_type_id", "identity_role", name="uq_field_defs_note_type_identity_role"),
    )
