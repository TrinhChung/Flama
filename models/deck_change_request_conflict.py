from datetime import datetime

from sqlalchemy import Index, UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class DeckChangeRequestConflict(db.Model):
    __tablename__ = "deck_change_request_conflicts"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    change_request_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_change_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_change_request_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conflict_type = db.Column(db.String(64), nullable=False, index=True)
    source_ref_id = db.Column(db.String(64), nullable=True, index=True)
    upstream_value = db.Column(db.JSON, nullable=True)
    local_value = db.Column(db.JSON, nullable=True)
    base_value = db.Column(db.JSON, nullable=True)
    resolution_mode = db.Column(db.String(32), nullable=True, index=True)
    resolved_value = db.Column(db.JSON, nullable=True)
    resolved_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    change_request = db.relationship("DeckChangeRequest", back_populates="conflicts")
    item = db.relationship("DeckChangeRequestItem", back_populates="conflicts")
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_user_id])

    __table_args__ = (
        UniqueConstraint("item_id", name="uq_deck_change_request_conflicts_item"),
        Index(
            "ix_deck_change_request_conflicts_request_resolved_at",
            "change_request_id",
            "resolved_at",
        ),
        Index(
            "ix_deck_change_request_conflicts_request_type",
            "change_request_id",
            "conflict_type",
        ),
    )
