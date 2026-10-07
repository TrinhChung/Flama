"""Mutable publisher settings and current immutable template release pointer."""

from datetime import datetime

from models import db


class TemplatePublication(db.Model):
    __tablename__ = "template_publications"

    template_id = db.Column(db.String(36), db.ForeignKey("templates.id", ondelete="CASCADE"), primary_key=True)
    current_release_id = db.Column(db.String(36), nullable=True)
    auto_publish_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    last_auto_published_at = db.Column(db.DateTime, nullable=True)
    last_auto_publish_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
