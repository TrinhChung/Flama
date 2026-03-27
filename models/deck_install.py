from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import synonym

from models import db
from models.model_uuid import uuid_str


class DeckInstall(db.Model):
    __tablename__ = "deck_installs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    deck_item_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_marketplace_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    local_deck_id = db.Column(
        db.Integer,
        db.ForeignKey("decks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    clone_mode = db.Column(db.String(32), nullable=False, default="logical_overlay", index=True)
    source_deck_id = db.Column(
        db.Integer,
        db.ForeignKey("decks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_note_type_id = db.Column(
        db.String(36),
        db.ForeignKey("note_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_owner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    base_snapshot_at = db.Column(db.DateTime, nullable=True, index=True)
    purchase_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    purchase_price_cents = synonym("purchase_amount_minor")
    installed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    purchased_at = db.Column(db.DateTime, nullable=True)
    first_use_at = db.Column(db.DateTime, nullable=True)
    last_activity_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    deck_item = db.relationship("DeckMarketplaceItem", back_populates="installs")
    user = db.relationship("User", foreign_keys=[user_id])
    local_deck = db.relationship("Deck", foreign_keys=[local_deck_id])
    source_deck = db.relationship("Deck", foreign_keys=[source_deck_id])
    source_note_type = db.relationship("NoteType", foreign_keys=[source_note_type_id])
    source_owner = db.relationship("User", foreign_keys=[source_owner_user_id])
    clone_deck_maps = db.relationship(
        "DeckCloneDeckMap",
        back_populates="deck_install",
        cascade="all, delete-orphan",
    )
    clone_field_overrides = db.relationship(
        "DeckCloneFieldDefOverride",
        back_populates="deck_install",
        cascade="all, delete-orphan",
    )
    clone_added_field_defs = db.relationship(
        "DeckCloneAddedFieldDef",
        back_populates="deck_install",
        cascade="all, delete-orphan",
    )
    clone_field_order_overrides = db.relationship(
        "DeckCloneFieldOrderOverride",
        back_populates="deck_install",
        cascade="all, delete-orphan",
    )
    clone_note_field_overrides = db.relationship(
        "DeckCloneNoteFieldOverride",
        back_populates="deck_install",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("deck_item_id", "user_id", name="uq_deck_installs_item_user"),
    )
