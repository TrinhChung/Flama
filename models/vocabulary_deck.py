"""Generic deck tree model (parent/child) for Anki-like hierarchy."""

from datetime import datetime

from models import db


class VocabularyDeck(db.Model):
    __tablename__ = "vocabulary_decks"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey("vocabulary_decks.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    owner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note_type_id = db.Column(
        db.String(36),
        db.ForeignKey("note_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    owner = db.relationship("User", foreign_keys=[owner_user_id])
    note_type = db.relationship("NoteType", foreign_keys=[note_type_id])
    parent = db.relationship(
        "VocabularyDeck",
        remote_side=[id],
        back_populates="children",
    )
    children = db.relationship(
        "VocabularyDeck",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="VocabularyDeck.position",
    )
    entries = db.relationship(
        "VocabularyEntry",
        back_populates="deck_rel",
    )
