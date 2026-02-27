from datetime import datetime

from models import db


class ReviewEvent(db.Model):
    __tablename__ = "review_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id = db.Column(db.String(64), nullable=False, index=True)
    deck_id = db.Column(db.Integer, nullable=True, index=True)
    note_type_id = db.Column(db.String(36), nullable=True, index=True)
    reviewed_at = db.Column(db.DateTime, nullable=False, index=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    rating = db.Column(db.String(20), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.Index("ix_review_events_user_reviewed_at", "user_id", "reviewed_at"),
        db.Index("ix_review_events_user_card_reviewed_at", "user_id", "card_id", "reviewed_at"),
    )
