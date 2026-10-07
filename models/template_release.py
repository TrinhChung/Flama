"""Immutable publication of one template content version."""

from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class TemplateRelease(db.Model):
    __tablename__ = "template_releases"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    template_id = db.Column(db.String(36), db.ForeignKey("templates.id", ondelete="RESTRICT"), nullable=False, index=True)
    version_id = db.Column(db.String(36), db.ForeignKey("template_versions.id", ondelete="RESTRICT"), nullable=False, index=True)
    sequence_no = db.Column(db.BigInteger, nullable=False)
    version_label = db.Column(db.String(50), nullable=False)
    parent_release_id = db.Column(db.String(36), db.ForeignKey("template_releases.id", ondelete="SET NULL", name="fk_template_releases_parent"), nullable=True)
    publish_mode = db.Column(db.String(16), nullable=False, default="manual", server_default="manual")
    idempotency_key = db.Column(db.String(64), nullable=True)
    change_note = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    published_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("template_id", "sequence_no", name="uq_template_releases_template_sequence"),
        db.UniqueConstraint("template_id", "version_label", name="uq_template_releases_template_label"),
        db.UniqueConstraint("template_id", "version_id", name="uq_template_releases_template_version"),
        db.UniqueConstraint("template_id", "idempotency_key", name="uq_template_releases_template_idempotency"),
        db.CheckConstraint("sequence_no > 0", name="ck_template_releases_sequence_positive"),
        db.CheckConstraint("publish_mode IN ('manual', 'automatic')", name="ck_template_releases_publish_mode"),
    )
