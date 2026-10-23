from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import synonym

from models import db
from models.model_uuid import uuid_str


class NoteTypeInstall(db.Model):
    __tablename__ = "note_type_installs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    source_note_type_id = db.Column(
        db.String(36),
        db.ForeignKey("note_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installed_note_type_id = db.Column(
        db.String(36),
        db.ForeignKey("note_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    applied_release_id = db.Column(
        db.String(36), db.ForeignKey("note_type_releases.id", ondelete="SET NULL",
            name="fk_note_type_installs_applied_release"), nullable=True, index=True,
    )
    purchase_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    purchase_price_cents = synonym("purchase_amount_minor")
    installed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    purchased_at = db.Column(db.DateTime, nullable=True)
    first_use_at = db.Column(db.DateTime, nullable=True)
    last_activity_at = db.Column(db.DateTime, nullable=True)
    market_active = db.Column(db.Boolean, nullable=True)
    market_active_evaluated_at = db.Column(db.DateTime, nullable=True)
    market_active_policy_version = db.Column(db.SmallInteger, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    source_note_type = db.relationship(
        "NoteType",
        foreign_keys=[source_note_type_id],
        back_populates="installs",
    )
    installed_note_type = db.relationship(
        "NoteType",
        foreign_keys=[installed_note_type_id],
    )
    user = db.relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("source_note_type_id", "user_id", name="uq_note_type_installs_source_user"),
        db.Index(
            "ix_note_type_installs_source_market_active",
            "source_note_type_id",
            "market_active",
        ),
        db.Index(
            "ix_note_type_installs_user_installed",
            "user_id",
            "installed_note_type_id",
        ),
    )
