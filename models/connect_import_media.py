from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class ConnectImportMedia(db.Model):
    __tablename__ = "connect_import_media"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    session_id = db.Column(
        db.String(36),
        db.ForeignKey("connect_import_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = db.Column(db.String(255), nullable=False)
    media_kind = db.Column(db.String(16), nullable=False)
    mime_type = db.Column(db.String(64), nullable=False)
    storage_path = db.Column(db.String(1024), nullable=False)
    sha256 = db.Column(db.String(64), nullable=False, index=True)
    size_bytes = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "filename",
            name="uq_connect_import_media_session_filename",
        ),
    )

