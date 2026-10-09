"""Immutable content snapshots for the existing Template identity."""

from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class TemplateVersion(db.Model):
    __tablename__ = "template_versions"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    template_id = db.Column(
        db.String(36),
        db.ForeignKey("templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_no = db.Column(db.Integer, nullable=False)
    front_html = db.Column(db.Text, nullable=False, default="")
    back_html = db.Column(db.Text, nullable=False, default="")
    shared_css = db.Column(db.Text, nullable=False, default="")
    input_schema = db.Column(db.JSON, nullable=False, default=list)
    content_hash = db.Column(db.String(64), nullable=False)
    origin = db.Column(db.String(24), nullable=False)
    change_note = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("template_id", "version_no", name="uq_template_versions_template_no"),
        db.CheckConstraint("version_no > 0", name="ck_template_versions_version_no_positive"),
    )
