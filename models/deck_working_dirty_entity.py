from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db


class DeckWorkingDirtyEntity(db.Model):
    __tablename__ = "deck_working_dirty_entities"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    deck_item_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_marketplace_items.id",
            name="fk_deck_working_dirty_deck_item",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    entity_kind = db.Column(db.String(32), nullable=False)
    entity_id = db.Column(db.String(64), nullable=False)
    field_def_id = db.Column(db.String(36), nullable=True)
    property_key = db.Column(db.String(191), nullable=False)
    operation = db.Column(db.String(32), nullable=False)
    base_hash = db.Column(db.String(64), nullable=True)
    current_hash = db.Column(db.String(64), nullable=True)
    source_deck_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "decks.id",
            name="fk_deck_working_dirty_source_deck",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    working_revision = db.Column(db.BigInteger, nullable=False, default=0)
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
        back_populates="working_dirty_entities",
    )
    source_deck = db.relationship("Deck", foreign_keys=[source_deck_id])

    __table_args__ = (
        UniqueConstraint(
            "deck_item_id",
            "entity_kind",
            "entity_id",
            "property_key",
            name="uq_deck_working_dirty_item_entity_property",
        ),
        Index(
            "ix_deck_working_dirty_publish",
            "deck_item_id",
            "working_revision",
            "id",
        ),
        Index(
            "ix_deck_working_dirty_entity_scope",
            "deck_item_id",
            "entity_kind",
            "source_deck_id",
            "id",
        ),
    )
