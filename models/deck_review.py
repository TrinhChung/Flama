from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class DeckReview(db.Model):
    __tablename__ = "deck_reviews"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    deck_item_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_marketplace_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    deck_item = db.relationship("DeckMarketplaceItem", back_populates="reviews")
    user = db.relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("deck_item_id", "user_id", name="uq_deck_reviews_item_user"),
    )

