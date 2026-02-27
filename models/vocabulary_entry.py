from datetime import datetime

from models import db


class VocabularyEntry(db.Model):
    """Stored vocabulary rows attached directly to decks."""

    __tablename__ = "vocabulary_entries"

    id = db.Column(db.Integer, primary_key=True)
    deck_id = db.Column(db.Integer, db.ForeignKey("vocabulary_decks.id", ondelete="SET NULL"), index=True, nullable=True)
    deck = db.Column(db.String(255), nullable=False, index=True)
    word = db.Column(db.String(255), nullable=False, index=True)
    hanviet = db.Column(db.String(255))
    reading = db.Column(db.String(255))
    translation_vi = db.Column(db.Text)
    meaning_jp = db.Column(db.Text)
    meaning_vi = db.Column(db.Text)
    usage_jp = db.Column(db.Text)
    usage_vi = db.Column(db.Text)
    example_jp = db.Column(db.Text)
    example_vi = db.Column(db.Text)
    additional_note_jp = db.Column(db.Text)
    additional_note_vi = db.Column(db.Text)
    image = db.Column(db.String(512))
    diagram = db.Column(db.String(512))
    word_audio = db.Column(db.String(512))
    example_audio = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    deck_rel = db.relationship("VocabularyDeck", back_populates="entries")
    progress_records = db.relationship(
        "VocabularyProgress",
        back_populates="entry",
        cascade="all, delete-orphan",
    )
