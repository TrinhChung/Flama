from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class ConnectImportPackage(db.Model):
    __tablename__ = "connect_import_packages"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    session_id = db.Column(
        db.String(36),
        db.ForeignKey("connect_import_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind = db.Column(db.String(16), nullable=False)
    sequence = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    storage_path = db.Column(db.String(1024), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="received", index=True)
    item_count = db.Column(db.Integer, nullable=False, default=0)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "kind",
            "sequence",
            name="uq_connect_import_packages_session_kind_sequence",
        ),
    )

