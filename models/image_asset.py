"""Unified Image Asset model for tracking all image inputs across Flama."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index

from models import db
from models.model_uuid import uuid_str


class ImageAsset(db.Model):
    """Centralized record for every image ingested into Flama."""

    __tablename__ = "image_assets"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    owner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type = db.Column(
        db.String(32),
        nullable=False,
        default="upload",
        index=True,
    )  # 'upload', 'external_url', 'clipboard', 'base64', 'generated'
    source_url = db.Column(db.String(2048), nullable=True)
    display_url = db.Column(db.String(2048), nullable=False)
    managed_url = db.Column(db.String(2048), nullable=True)
    storage_path = db.Column(db.String(1024), nullable=True)

    original_filename = db.Column(db.String(255), nullable=True)
    original_mime_type = db.Column(db.String(120), nullable=True)
    output_mime_type = db.Column(db.String(120), nullable=True, default="image/webp")

    original_width = db.Column(db.Integer, nullable=True)
    original_height = db.Column(db.Integer, nullable=True)
    output_width = db.Column(db.Integer, nullable=True)
    output_height = db.Column(db.Integer, nullable=True)

    original_size_bytes = db.Column(db.Integer, nullable=False, default=0)
    output_size_bytes = db.Column(db.Integer, nullable=False, default=0)

    usage_type = db.Column(
        db.String(50),
        nullable=False,
        default="general",
        index=True,
    )  # 'avatar', 'deck_cover', 'note_image', 'image_library', 'general'
    preset = db.Column(db.String(50), nullable=True)

    processing_status = db.Column(
        db.String(32),
        nullable=False,
        default="pending",
        index=True,
    )  # 'pending', 'processing', 'ready', 'failed', 'rejected'
    security_status = db.Column(
        db.String(32),
        nullable=False,
        default="safe",
        index=True,
    )  # 'safe', 'suspicious', 'blocked'
    security_reason = db.Column(db.String(255), nullable=True)

    sha256 = db.Column(db.String(64), nullable=True, index=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    processed_at = db.Column(db.DateTime, nullable=True)

    owner = db.relationship("User", foreign_keys=[owner_user_id])

    __table_args__ = (
        Index("ix_image_assets_owner_status", "owner_user_id", "processing_status"),
        Index("ix_image_assets_usage_status", "usage_type", "processing_status"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "owner_user_id": self.owner_user_id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "display_url": self.display_url,
            "managed_url": self.managed_url,
            "usage_type": self.usage_type,
            "preset": self.preset,
            "original_filename": self.original_filename,
            "original_mime_type": self.original_mime_type,
            "output_mime_type": self.output_mime_type,
            "original_width": self.original_width,
            "original_height": self.original_height,
            "output_width": self.output_width,
            "output_height": self.output_height,
            "original_size_bytes": self.original_size_bytes,
            "output_size_bytes": self.output_size_bytes,
            "processing_status": self.processing_status,
            "security_status": self.security_status,
            "security_reason": self.security_reason,
            "sha256": self.sha256,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }
