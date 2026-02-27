from datetime import datetime

from sqlalchemy import UniqueConstraint

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
    purchase_price_cents = db.Column(db.Integer, nullable=False, default=0)
    installed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    purchased_at = db.Column(db.DateTime, nullable=True)
    first_use_at = db.Column(db.DateTime, nullable=True)
    last_activity_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    deck_item = db.relationship("DeckMarketplaceItem", back_populates="installs")
    user = db.relationship("User", foreign_keys=[user_id])
    local_deck = db.relationship("Deck", foreign_keys=[local_deck_id])

    __table_args__ = (
        UniqueConstraint("deck_item_id", "user_id", name="uq_deck_installs_item_user"),
    )
