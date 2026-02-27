from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class FieldRenameJob(db.Model):
    __tablename__ = "field_rename_jobs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
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

