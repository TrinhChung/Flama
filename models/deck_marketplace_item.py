from datetime import datetime

from sqlalchemy.orm import synonym

from models import db
from models.model_uuid import uuid_str


class DeckMarketplaceItem(db.Model):
    __tablename__ = "deck_marketplace_items"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
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
    title = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False, default="")
    primary_category = db.Column(db.String(120), nullable=False, default="General", index=True)
    tags = db.Column(db.JSON, nullable=False, default=list)
    preview_text = db.Column(db.Text, nullable=True)
    sample_cards_count = db.Column(db.Integer, nullable=False, default=0)
    pricing_mode = db.Column(
        db.Enum("free", "paid", name="deck_marketplace_pricing_mode_enum", native_enum=False),
        nullable=False,
        default="free",
        index=True,
    )
    price_amount_minor = db.Column(db.Integer, nullable=False, default=0)
    price_cents = synonym("price_amount_minor")
    version = db.Column(db.String(50), nullable=False, default="1.0.0")
    changelog = db.Column(db.Text, nullable=True)
    publish_status = db.Column(
        db.Enum("private", "published", "unlisted", "archived", name="deck_marketplace_publish_status_enum", native_enum=False),
        nullable=False,
        default="private",
        index=True,
    )
    is_official = db.Column(db.Boolean, nullable=False, default=False, index=True)
    published_at = db.Column(db.DateTime, nullable=True)
    archived_at = db.Column(db.DateTime, nullable=True)
    install_count = db.Column(db.Integer, nullable=False, default=0)
    active_usage_count = db.Column(db.Integer, nullable=False, default=0)
    rating_avg = db.Column(db.Float, nullable=False, default=0.0)
    rating_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = db.relationship("User", foreign_keys=[owner_user_id])
    source_deck = db.relationship("Deck", foreign_keys=[source_deck_id])
    source_note_type = db.relationship("NoteType", foreign_keys=[source_note_type_id])
    installs = db.relationship("DeckInstall", back_populates="deck_item", cascade="all, delete-orphan")
    reviews = db.relationship("DeckReview", back_populates="deck_item", cascade="all, delete-orphan")
