from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.flashcard_entries.common import uuid_str


class NoteType(db.Model):
    __tablename__ = "note_types"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    primary_category = db.Column(db.String(120), nullable=True, index=True)
    tags = db.Column(db.JSON, nullable=False, default=list)
    preview_text = db.Column(db.Text, nullable=True)
    preview_image_url = db.Column(db.String(512), nullable=True)
    pricing_mode = db.Column(
        db.Enum("free", "paid", name="note_type_pricing_mode_enum", native_enum=False),
        nullable=False,
        default="free",
        index=True,
    )
    price_cents = db.Column(db.Integer, nullable=False, default=0)
    version = db.Column(db.String(50), nullable=False, default="1.0.0")
    changelog = db.Column(db.Text, nullable=True)
    publish_status = db.Column(
        db.Enum("private", "published", "unlisted", "archived", name="note_type_publish_status_enum", native_enum=False),
        nullable=False,
        default="private",
        index=True,
    )
    is_official = db.Column(db.Boolean, nullable=False, default=False, index=True)
    published_at = db.Column(db.DateTime, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)
    install_count = db.Column(db.Integer, nullable=False, default=0)
    active_usage_count = db.Column(db.Integer, nullable=False, default=0)
    rating_avg = db.Column(db.Float, nullable=False, default=0.0)
    rating_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = db.relationship("User", foreign_keys=[user_id])
    field_defs = db.relationship(
        "FieldDef",
        back_populates="note_type",
        cascade="all, delete-orphan",
        order_by="FieldDef.position",
    )
    templates = db.relationship(
        "Template",
        back_populates="note_type",
        cascade="all, delete-orphan",
        order_by="Template.position",
    )
    notes = db.relationship(
        "Note",
        back_populates="note_type",
        cascade="all, delete-orphan",
    )
    installs = db.relationship(
        "NoteTypeInstall",
        back_populates="source_note_type",
        cascade="all, delete-orphan",
        foreign_keys="NoteTypeInstall.source_note_type_id",
    )
    reviews = db.relationship(
        "NoteTypeReview",
        back_populates="note_type",
        cascade="all, delete-orphan",
        foreign_keys="NoteTypeReview.note_type_id",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_note_types_user_name"),
    )

