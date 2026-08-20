from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class DeckCloneNoteFieldOverride(db.Model):
    __tablename__ = "deck_clone_note_field_overrides"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    deck_install_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_installs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_note_id = db.Column(
        db.String(36),
        db.ForeignKey("notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_field_def_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "field_defs.id",
            name="fk_clone_note_overrides_source_field_def",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    base_release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_clone_note_overrides_base_release",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    field_name = db.Column(db.String(255), nullable=False)
    operation = db.Column(
        db.Enum("set", "remove", name="deck_clone_note_field_op_enum", native_enum=False),
        nullable=False,
        default="set",
    )
    value = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    deck_install = db.relationship("DeckInstall", back_populates="clone_note_field_overrides")
    source_note = db.relationship("Note", foreign_keys=[source_note_id])
    source_field_def = db.relationship("FieldDef", foreign_keys=[source_field_def_id])
    base_release = db.relationship("DeckRelease", foreign_keys=[base_release_id])

    __table_args__ = (
        UniqueConstraint(
            "deck_install_id",
            "source_note_id",
            "field_name",
            name="uq_clone_note_override_install_note_field",
        ),
        UniqueConstraint(
            "deck_install_id",
            "source_note_id",
            "source_field_def_id",
            name="uq_clone_note_override_install_note_field_def",
        ),
    )
