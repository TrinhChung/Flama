from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    # A reusable definition belongs to its author, independently of attachments.
    owner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE", name="fk_templates_owner_user"),
        nullable=False,
        index=True,
    )
    input_schema = db.Column(db.JSON, nullable=True)
    current_version_id = db.Column(db.String(36), nullable=True)
    description = db.Column(db.Text, nullable=True)
    primary_category = db.Column(db.String(120), nullable=True, index=True)
    origin = db.Column(db.String(24), nullable=False, default="authored", server_default="authored")
    source_template_id = db.Column(
        db.String(36), db.ForeignKey("templates.id", ondelete="SET NULL", name="fk_templates_source_template"),
        nullable=True, index=True,
    )
    source_version_id = db.Column(
        db.String(36),
        db.ForeignKey("template_versions.id", ondelete="SET NULL", name="fk_templates_source_version", use_alter=True),
        nullable=True,
    )
    archived_at = db.Column(db.DateTime, nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    front_html = db.Column(db.Text, nullable=False, default="")
    back_html = db.Column(db.Text, nullable=False, default="")
    shared_css = db.Column(db.Text, nullable=False, default="")
    position = db.Column(db.Integer, nullable=False, default=0)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    cards = db.relationship("Card", primaryjoin="foreign(Card.template_id) == Template.id", viewonly=True)
    owner = db.relationship("User", foreign_keys=[owner_user_id])

    __table_args__ = (
        db.CheckConstraint("origin IN ('authored', 'market_copy')", name="ck_templates_origin"),
    )

