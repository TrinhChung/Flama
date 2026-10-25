from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db


class DeckReleaseEntityMembership(db.Model):
    __tablename__ = "deck_release_entity_memberships"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    deck_item_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_marketplace_items.id",
            name="fk_deck_release_memberships_deck_item",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    entity_kind = db.Column(db.String(32), nullable=False)
    entity_id = db.Column(db.String(64), nullable=False)
    source_deck_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "decks.id",
            name="fk_deck_release_memberships_source_deck",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    introduced_sequence = db.Column(db.BigInteger, nullable=False)
    removed_sequence = db.Column(db.BigInteger, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    deck_item = db.relationship(
        "DeckMarketplaceItem",
        back_populates="release_memberships",
    )
    source_deck = db.relationship("Deck", foreign_keys=[source_deck_id])

    __table_args__ = (
        UniqueConstraint(
            "deck_item_id",
            "entity_kind",
            "entity_id",
            "introduced_sequence",
            name="uq_deck_release_memberships_item_entity_start",
        ),
        Index(
            "ix_deck_release_memberships_visibility",
            "deck_item_id",
            "entity_kind",
            "introduced_sequence",
            "removed_sequence",
            "id",
        ),
        Index(
            "ix_deck_release_memberships_deck_visibility",
            "deck_item_id",
            "source_deck_id",
            "introduced_sequence",
            "removed_sequence",
            "id",
        ),
    )
