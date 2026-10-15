from datetime import datetime

from sqlalchemy import UniqueConstraint, text
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
    applied_release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_deck_installs_applied_release",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    seen_release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_deck_installs_seen_release",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    overlay_revision = db.Column(
        db.BigInteger,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    version_mode = db.Column(
        db.String(32),
        nullable=False,
        default="legacy_snapshot",
        server_default="legacy_snapshot",
        index=True,
    )
    last_synced_at = db.Column(db.DateTime, nullable=True, index=True)
    last_sync_status = db.Column(db.String(32), nullable=True, index=True)
    auto_update_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        index=True,
    )
    sync_mode = db.Column(
        db.String(32),
        nullable=False,
        default="manual",
        server_default="manual",
        index=True,
    )
    last_auto_updated_at = db.Column(db.DateTime, nullable=True, index=True)
    pending_conflict_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
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
    __mapper_args__ = {"version_id_col": overlay_revision, "version_id_generator": False}

    deck_item = db.relationship("DeckMarketplaceItem", back_populates="installs")
    user = db.relationship("User", foreign_keys=[user_id])
    local_deck = db.relationship("Deck", foreign_keys=[local_deck_id])
    source_deck = db.relationship("Deck", foreign_keys=[source_deck_id])
    source_note_type = db.relationship("NoteType", foreign_keys=[source_note_type_id])
    source_owner = db.relationship("User", foreign_keys=[source_owner_user_id])
    applied_release = db.relationship("DeckRelease", foreign_keys=[applied_release_id])
    seen_release = db.relationship("DeckRelease", foreign_keys=[seen_release_id])
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
    clone_added_notes = db.relationship(
        "DeckCloneAddedNote",
        back_populates="deck_install",
        cascade="all, delete-orphan",
    )
    change_requests = db.relationship(
        "DeckChangeRequest",
        back_populates="deck_install",
        cascade="all, delete-orphan",
    )
    rebases = db.relationship(
        "DeckInstallRebase",
        back_populates="deck_install",
        cascade="all, delete-orphan",
        order_by="DeckInstallRebase.created_at",
    )

    __table_args__ = (
        UniqueConstraint("deck_item_id", "user_id", name="uq_deck_installs_item_user"),
        db.Index("ix_deck_installs_item_market_active", "deck_item_id", "market_active"),
    )
