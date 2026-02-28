from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.model_uuid import uuid_str


class DeckCloneDeckMap(db.Model):
    __tablename__ = "deck_clone_deck_maps"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    deck_install_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_installs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    local_deck_id = db.Column(
        db.Integer,
        db.ForeignKey("decks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_deck_id = db.Column(
        db.Integer,
        db.ForeignKey("decks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    deck_install = db.relationship("DeckInstall", back_populates="clone_deck_maps")
    local_deck = db.relationship("Deck", foreign_keys=[local_deck_id])
    source_deck = db.relationship("Deck", foreign_keys=[source_deck_id])

    __table_args__ = (
        UniqueConstraint("local_deck_id", name="uq_clone_map_local_deck"),
        UniqueConstraint("deck_install_id", "source_deck_id", name="uq_clone_map_install_source"),
    )
