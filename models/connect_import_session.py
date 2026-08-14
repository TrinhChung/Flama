from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class ConnectImportSession(db.Model):
    __tablename__ = "connect_import_sessions"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = db.Column(db.String(64), nullable=False, default="anki")
    source_key = db.Column(db.String(255), nullable=False)
    mode = db.Column(db.String(32), nullable=False, default="strict")
    status = db.Column(db.String(32), nullable=False, default="preflighting", index=True)
    source_root_path = db.Column(db.String(2048), nullable=True)
    target_root_path = db.Column(db.String(2048), nullable=True)
    selected_decks = db.Column(db.JSON, nullable=False, default=list)
    note_type_bindings = db.Column(db.JSON, nullable=False, default=dict)
    blockers = db.Column(db.JSON, nullable=False, default=list)
    plan_hash = db.Column(db.String(64), nullable=True, index=True)
    total_notes = db.Column(db.Integer, nullable=False, default=0)
    total_media = db.Column(db.Integer, nullable=False, default=0)
    processed_notes = db.Column(db.Integer, nullable=False, default=0)
    attempted_notes = db.Column(db.Integer, nullable=False, default=0)
    processed_media = db.Column(db.Integer, nullable=False, default=0)
    error_summary = db.Column(db.JSON, nullable=False, default=list)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = db.relationship("User", foreign_keys=[user_id])

