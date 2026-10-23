"""Durable publication fan-out and independently retried subscription deliveries."""

from datetime import datetime
from sqlalchemy.dialects.mysql import DATETIME

from models import db


class TemplateSyncJob(db.Model):
    __tablename__ = "template_sync_jobs"

    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), primary_key=True, autoincrement=True)
    # Release FK already protects the source's lifetime. Avoid a second FK
    # whose validation would lock the author's mutable draft during fan-out.
    source_template_id = db.Column(db.String(36), nullable=False)
    release_id = db.Column(db.String(36), db.ForeignKey("template_releases.id", ondelete="RESTRICT"), nullable=False)
    # Empty key identifies the single dispatcher. Delivery keys are stable
    # subscription IDs, so repeated pages cannot enqueue duplicate recipients.
    recipient_key = db.Column(db.String(36), nullable=False, default="", server_default="")
    after_subscription_id = db.Column(db.String(36), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="pending", server_default="pending")
    attempt_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    available_at = db.Column(db.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=True)
    last_error_code = db.Column(db.String(100), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("release_id", "recipient_key", name="uq_template_sync_jobs_release_recipient"),
        db.Index("ix_template_sync_jobs_pending", "status", "available_at", "id"),
        db.CheckConstraint("status IN ('pending', 'done', 'failed')", name="ck_template_sync_jobs_status"),
        db.CheckConstraint("attempt_count >= 0", name="ck_template_sync_jobs_attempts"),
    )
