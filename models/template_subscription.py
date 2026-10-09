"""One canonical received template and release pin per user/source pair."""

from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class TemplateSubscription(db.Model):
    __tablename__ = "template_subscriptions"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_template_id = db.Column(db.String(36), db.ForeignKey("templates.id", ondelete="RESTRICT"), nullable=False)
    local_template_id = db.Column(db.String(36), db.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False)
    applied_release_id = db.Column(db.String(36), db.ForeignKey("template_releases.id", ondelete="RESTRICT"), nullable=False)
    seen_release_id = db.Column(db.String(36), db.ForeignKey("template_releases.id", ondelete="SET NULL"), nullable=True)
    auto_update_enabled = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    pending_update_json = db.Column(db.JSON, nullable=True)
    last_sync_status = db.Column(db.String(24), nullable=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "source_template_id", name="uq_template_subscriptions_user_source"),
        db.UniqueConstraint("local_template_id", name="uq_template_subscriptions_local_template"),
    )
