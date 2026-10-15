from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class DeckCloneFieldDefOverride(db.Model):
    __tablename__ = "deck_clone_field_def_overrides"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    deck_install_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_installs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_field_def_id = db.Column(
        db.String(36),
        nullable=False,
        index=True,
    )
    is_disabled = db.Column(db.Boolean, nullable=False, default=False)
    properties = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    deck_install = db.relationship("DeckInstall", back_populates="clone_field_overrides")
    source_field_def = db.relationship("FieldDef", primaryjoin="foreign(DeckCloneFieldDefOverride.source_field_def_id) == FieldDef.id")

    __table_args__ = (
        UniqueConstraint(
            "deck_install_id",
            "source_field_def_id",
            name="uq_clone_field_override_install_source_field",
        ),
    )
