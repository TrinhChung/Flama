from datetime import datetime

from sqlalchemy import UniqueConstraint

from models import db
from models.flashcard_entries.common import uuid_str


class NoteTypeReview(db.Model):
    __tablename__ = "note_type_reviews"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    note_type_id = db.Column(
        db.String(36),
        db.ForeignKey("note_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    note_type = db.relationship("NoteType", back_populates="reviews", foreign_keys=[note_type_id])
    user = db.relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("note_type_id", "user_id", name="uq_note_type_reviews_item_user"),
    )

