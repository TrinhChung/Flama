from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class ConnectSourceDeckRef(db.Model):
    __tablename__ = "connect_source_deck_refs"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_key = db.Column(db.String(255), nullable=False)
    external_deck_id = db.Column(db.String(128), nullable=False)
    source_path = db.Column(db.String(2048), nullable=False)
    deck_id = db.Column(
        db.Integer,
        db.ForeignKey("decks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    deck = db.relationship("Deck", foreign_keys=[deck_id])

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_key",
            "external_deck_id",
            name="uq_connect_source_deck_refs_source_deck",
        ),
    )

