from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class DeckRelease(db.Model):
    __tablename__ = "deck_releases"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    deck_item_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_marketplace_items.id",
            name="fk_deck_releases_deck_item",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    sequence_no = db.Column(db.BigInteger, nullable=False)
    version_label = db.Column(db.String(50), nullable=False)
    parent_release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_deck_releases_parent",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    status = db.Column(db.String(32), nullable=False, default="building", index=True)
    source_working_revision = db.Column(db.BigInteger, nullable=False, default=0)
    manifest_hash = db.Column(db.String(64), nullable=True)
    change_count = db.Column(db.Integer, nullable=False, default=0)
    entity_count = db.Column(db.Integer, nullable=False, default=0)
    added_count = db.Column(db.Integer, nullable=False, default=0)
    modified_count = db.Column(db.Integer, nullable=False, default=0)
    removed_count = db.Column(db.Integer, nullable=False, default=0)
    changelog = db.Column(db.Text, nullable=True)
    idempotency_key = db.Column(db.String(64), nullable=True)
    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "users.id",
            name="fk_deck_releases_created_by",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    published_at = db.Column(db.DateTime, nullable=True)
    failed_at = db.Column(db.DateTime, nullable=True)
    failure_message = db.Column(db.Text, nullable=True)

    deck_item = db.relationship(
        "DeckMarketplaceItem",
        back_populates="releases",
        foreign_keys=[deck_item_id],
    )
    parent_release = db.relationship(
        "DeckRelease",
        back_populates="child_releases",
        foreign_keys=[parent_release_id],
        remote_side=[id],
    )
    child_releases = db.relationship(
        "DeckRelease",
        back_populates="parent_release",
        foreign_keys=[parent_release_id],
    )
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])
    changes = db.relationship(
        "DeckReleaseChange",
        back_populates="release",
        cascade="all, delete-orphan",
        order_by="DeckReleaseChange.id",
    )
    note_checkpoints = db.relationship(
        "DeckReleaseNoteCheckpoint",
        back_populates="release",
        cascade="all, delete-orphan",
        order_by="DeckReleaseNoteCheckpoint.id",
    )

    __table_args__ = (
        UniqueConstraint(
            "deck_item_id",
            "sequence_no",
            name="uq_deck_releases_item_sequence",
        ),
        UniqueConstraint(
            "deck_item_id",
            "version_label",
            name="uq_deck_releases_item_version",
        ),
        UniqueConstraint(
            "deck_item_id",
            "idempotency_key",
            name="uq_deck_releases_item_idempotency",
        ),
        Index(
            "ix_deck_releases_item_status_published",
            "deck_item_id",
            "status",
            "published_at",
            "id",
        ),
    )
