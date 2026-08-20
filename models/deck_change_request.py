from datetime import datetime

from sqlalchemy import Index

from models import db
from models.model_uuid import uuid_str


class DeckChangeRequest(db.Model):
    __tablename__ = "deck_change_requests"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    deck_install_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_installs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    deck_item_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_marketplace_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    local_deck_id = db.Column(
        db.Integer,
        db.ForeignKey("decks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    requester_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewed_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = db.Column(db.String(255), nullable=False, default="Change Request")
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="needs_sync", index=True)
    install_snapshot_at = db.Column(db.DateTime, nullable=True)
    base_release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_deck_change_requests_base_release",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    revision = db.Column(db.BigInteger, nullable=False, default=0)
    overlay_fingerprint = db.Column(db.String(64), nullable=False)
    last_synced_overlay_fingerprint = db.Column(db.String(64), nullable=True)
    last_sync_status = db.Column(db.String(32), nullable=True, index=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    merged_at = db.Column(db.DateTime, nullable=True)
    review_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    deck_install = db.relationship("DeckInstall", back_populates="change_requests")
    deck_item = db.relationship("DeckMarketplaceItem", back_populates="change_requests")
    local_deck = db.relationship("Deck", foreign_keys=[local_deck_id])
    source_deck = db.relationship("Deck", foreign_keys=[source_deck_id])
    source_note_type = db.relationship("NoteType", foreign_keys=[source_note_type_id])
    base_release = db.relationship("DeckRelease", foreign_keys=[base_release_id])
    requester = db.relationship("User", foreign_keys=[requester_user_id])
    owner = db.relationship("User", foreign_keys=[owner_user_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_user_id])
    items = db.relationship(
        "DeckChangeRequestItem",
        back_populates="change_request",
        cascade="all, delete-orphan",
        order_by="DeckChangeRequestItem.sort_order",
    )
    conflicts = db.relationship(
        "DeckChangeRequestConflict",
        back_populates="change_request",
        cascade="all, delete-orphan",
        order_by="DeckChangeRequestConflict.created_at",
    )

    __table_args__ = (
        Index(
            "ix_deck_change_requests_owner_status_updated_at",
            "owner_user_id",
            "status",
            "updated_at",
        ),
        Index(
            "ix_deck_change_requests_requester_status_updated_at",
            "requester_user_id",
            "status",
            "updated_at",
        ),
    )
