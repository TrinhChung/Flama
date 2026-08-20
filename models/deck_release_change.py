from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db


class DeckReleaseChange(db.Model):
    __tablename__ = "deck_release_changes"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_deck_release_changes_release",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    release_sequence_no = db.Column(db.BigInteger, nullable=False)
    change_key = db.Column(db.String(191), nullable=False)
    entity_kind = db.Column(db.String(32), nullable=False)
    entity_id = db.Column(db.String(64), nullable=False)
    field_def_id = db.Column(db.String(36), nullable=True)
    property_key = db.Column(db.String(191), nullable=False)
    operation = db.Column(db.String(32), nullable=False)
    before_value = db.Column(db.JSON, nullable=True)
    after_value = db.Column(db.JSON, nullable=True)
    before_hash = db.Column(db.String(64), nullable=True)
    after_hash = db.Column(db.String(64), nullable=True)
    source_deck_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "decks.id",
            name="fk_deck_release_changes_source_deck",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    sort_key = db.Column(db.String(255), nullable=False, default="")
    source_change_request_item_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_change_request_items.id",
            name="fk_deck_release_changes_request_item",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    release = db.relationship("DeckRelease", back_populates="changes")
    source_deck = db.relationship("Deck", foreign_keys=[source_deck_id])
    source_change_request_item = db.relationship(
        "DeckChangeRequestItem",
        foreign_keys=[source_change_request_item_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "release_id",
            "change_key",
            name="uq_deck_release_changes_release_key",
        ),
        Index(
            "ix_deck_release_changes_diff_cursor",
            "release_id",
            "entity_kind",
            "source_deck_id",
            "sort_key",
            "id",
        ),
        Index(
            "ix_deck_release_changes_entity_history",
            "entity_kind",
            "entity_id",
            "property_key",
            "release_sequence_no",
            "id",
        ),
    )
