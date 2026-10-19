"""Mutable publisher settings and current immutable template release pointer."""

from datetime import datetime

from models import db


class TemplatePublication(db.Model):
    __tablename__ = "template_publications"
    __table_args__ = (
        db.Index("ix_template_publications_marketplace", "marketplace_status", "marketplace_published_at"),
    )

    template_id = db.Column(db.String(36), db.ForeignKey("templates.id", ondelete="CASCADE"), primary_key=True)
    current_release_id = db.Column(db.String(36), nullable=True)
    auto_publish_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    last_auto_published_at = db.Column(db.DateTime, nullable=True)
    last_auto_publish_error = db.Column(db.Text, nullable=True)
    # Standalone template marketplace listing. Releases alone never list a
    # template: decks and NoteTypes publish releases for their own buyers.
    marketplace_status = db.Column(db.String(16), nullable=False, default="private", server_default="private")
    pricing_mode = db.Column(db.String(16), nullable=False, default="free", server_default="free")
    price_amount_minor = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    marketplace_published_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
