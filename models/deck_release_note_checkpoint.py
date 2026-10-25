from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db


class DeckReleaseNoteCheckpoint(db.Model):
    __tablename__ = "deck_release_note_checkpoints"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_deck_release_note_checkpoints_release",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    release_sequence_no = db.Column(db.BigInteger, nullable=False)
    source_note_id = db.Column(db.String(36), nullable=False)
    source_deck_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "decks.id",
            name="fk_deck_release_note_checkpoints_source_deck",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    note_type_id = db.Column(db.String(36), nullable=False)
    field_values = db.Column(db.JSON, nullable=False, default=dict)
    tags = db.Column(db.JSON, nullable=False, default=list)
    content_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    release = db.relationship("DeckRelease", back_populates="note_checkpoints")
    source_deck = db.relationship("Deck", foreign_keys=[source_deck_id])

    __table_args__ = (
        UniqueConstraint(
            "release_id",
            "source_note_id",
            name="uq_deck_release_note_checkpoints_release_note",
        ),
        Index(
            "ix_deck_release_note_checkpoints_note_sequence",
            "source_note_id",
            "release_sequence_no",
            "id",
        ),
        Index(
            "ix_deck_release_note_checkpoints_release_deck",
            "release_id",
            "source_deck_id",
            "id",
        ),
    )
