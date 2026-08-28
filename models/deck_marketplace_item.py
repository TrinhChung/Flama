from datetime import datetime

from sqlalchemy.orm import synonym

from models import db
from models.model_uuid import uuid_str


class DeckMarketplaceItem(db.Model):
    __tablename__ = "deck_marketplace_items"
    __table_args__ = (
        db.Index(
            "uq_deck_marketplace_items_source_deck",
            "source_deck_id",
            unique=True,
        ),
    )

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
    taxonomy_metadata = db.Column(db.JSON, nullable=False, default=dict)
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
    distribution_mode = db.Column(
        db.String(32),
        nullable=False,
        default="free",
        index=True,
    )
    course_title = db.Column(db.String(255), nullable=True)
    course_description = db.Column(db.Text, nullable=True)
    course_url = db.Column(db.String(500), nullable=True)
    course_instructions = db.Column(db.Text, nullable=True)
    student_offer_mode = db.Column(
        db.Enum("none", "free", "percent_discount", name="deck_marketplace_student_offer_mode_enum", native_enum=False),
        nullable=False,
        default="none",
        index=True,
    )
    student_discount_percent = db.Column(db.Integer, nullable=True)
    version = db.Column(db.String(50), nullable=False, default="1.0.0")
    changelog = db.Column(db.Text, nullable=True)
    current_release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_deck_marketplace_items_current_release",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
        index=True,
    )
    preview_samples_release_id = db.Column(
        db.String(36),
        db.ForeignKey(
            "deck_releases.id",
            name="fk_deck_marketplace_items_preview_samples_release",
            ondelete="SET NULL",
            use_alter=True,
        ),
        nullable=True,
        index=True,
    )
    preview_samples_schema_version = db.Column(db.SmallInteger, nullable=True)
    preview_samples_json = db.Column(db.JSON, nullable=True)
    working_revision = db.Column(db.BigInteger, nullable=False, default=0)
    # Highest working revision for which every source mutation was recorded in
    # deck_working_dirty_entities.  A mismatch makes release preview/publish
    # fall back to the full-deck comparison instead of trusting an incomplete
    # sparse change set.
    dirty_tracking_revision = db.Column(db.BigInteger, nullable=False, default=0)
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
    auto_publish_enabled = db.Column(db.Boolean, nullable=False, default=False, index=True)
    last_auto_published_at = db.Column(db.DateTime, nullable=True)
    last_auto_publish_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = db.relationship("User", foreign_keys=[owner_user_id])
    source_deck = db.relationship("Deck", foreign_keys=[source_deck_id])
    source_note_type = db.relationship("NoteType", foreign_keys=[source_note_type_id])
    current_release = db.relationship(
        "DeckRelease",
        foreign_keys=[current_release_id],
        post_update=True,
    )
    preview_samples_release = db.relationship(
        "DeckRelease",
        foreign_keys=[preview_samples_release_id],
        post_update=True,
    )
    releases = db.relationship(
        "DeckRelease",
        back_populates="deck_item",
        cascade="all, delete-orphan",
        foreign_keys="DeckRelease.deck_item_id",
        order_by="DeckRelease.sequence_no",
    )
    release_memberships = db.relationship(
        "DeckReleaseEntityMembership",
        back_populates="deck_item",
        cascade="all, delete-orphan",
    )
    working_dirty_entities = db.relationship(
        "DeckWorkingDirtyEntity",
        back_populates="deck_item",
        cascade="all, delete-orphan",
    )
    installs = db.relationship("DeckInstall", back_populates="deck_item", cascade="all, delete-orphan")
    access_keys = db.relationship("DeckAccessKey", back_populates="deck_item", cascade="all, delete-orphan")
    change_requests = db.relationship("DeckChangeRequest", back_populates="deck_item")
    reviews = db.relationship("DeckReview", back_populates="deck_item", cascade="all, delete-orphan")
