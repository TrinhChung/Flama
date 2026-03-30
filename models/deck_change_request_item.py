from datetime import datetime

from sqlalchemy import Index

from models import db
from models.model_uuid import uuid_str


class DeckChangeRequestItem(db.Model):
    __tablename__ = "deck_change_request_items"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    change_request_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_change_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_type = db.Column(db.String(64), nullable=False, index=True)
    source_ref_id = db.Column(db.String(64), nullable=True, index=True)
    local_ref_id = db.Column(db.String(64), nullable=True, index=True)
    path_key = db.Column(db.String(255), nullable=True)
    path_label = db.Column(db.String(255), nullable=True)
    before_value = db.Column(db.JSON, nullable=True)
    after_value = db.Column(db.JSON, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_conflict = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    change_request = db.relationship("DeckChangeRequest", back_populates="items")
    conflicts = db.relationship(
        "DeckChangeRequestConflict",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="DeckChangeRequestConflict.created_at",
    )

    __table_args__ = (
        Index(
            "ix_deck_change_request_items_request_sort",
            "change_request_id",
            "sort_order",
        ),
        Index(
            "ix_deck_change_request_items_request_type",
            "change_request_id",
            "change_type",
        ),
    )
