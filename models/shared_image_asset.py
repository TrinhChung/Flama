from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class SharedImageAsset(db.Model):
    """Language-neutral image entry addressed by a stable reusable key."""

    __tablename__ = "shared_image_assets"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    image_key = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(255), nullable=True)
    mime_type = db.Column(db.String(255), nullable=True)
    storage_path = db.Column(db.String(1024), nullable=True)
    sha256 = db.Column(db.String(64), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    is_enabled = db.Column(db.Boolean, nullable=False, default=True)
    source_url = db.Column(db.String(2048), nullable=True)
    tags = db.Column(db.JSON, nullable=False, default=list)
    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_user_id])

    __table_args__ = (
        UniqueConstraint("image_key", name="uq_shared_image_assets_image_key"),
        Index("ix_shared_image_assets_is_enabled", "is_enabled"),
        Index("ix_shared_image_assets_updated_at", "updated_at"),
        Index("ix_shared_image_assets_sha256", "sha256"),
    )
