from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class ConnectSourceCardRef(db.Model):
    """Stable mapping and sync cursors for one external Anki card."""

    __tablename__ = "connect_source_card_refs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_key = db.Column(db.String(255), nullable=False)
    external_card_id = db.Column(db.String(128), nullable=False)
    external_note_id = db.Column(db.String(128), nullable=False)
    source_ord = db.Column(db.Integer, nullable=False)
    card_id = db.Column(
        db.String(36),
        db.ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_hash = db.Column(db.String(64), nullable=True)
    applied_local_revision = db.Column(db.BigInteger, nullable=True)
    review_cursor = db.Column(db.BigInteger, nullable=True)
    last_session_id = db.Column(
        db.String(36),
        db.ForeignKey("connect_import_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    card = db.relationship("Card", foreign_keys=[card_id])

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "source_key",
            "external_card_id",
            name="uq_connect_source_card_refs_source_card",
        ),
        db.Index(
            "ix_connect_source_card_refs_source_note",
            "user_id",
            "source_key",
            "external_note_id",
        ),
    )
