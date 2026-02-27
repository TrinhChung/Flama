"""Per-user spaced-repetition progress for flashcard cards."""

from datetime import datetime

from models import db


class CardProgress(db.Model):
    __tablename__ = "card_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    card_id = db.Column(
        db.String(36),
        db.ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    queue = db.Column(db.String(20), nullable=False, default="new", index=True)
    step_index = db.Column(db.Integer, nullable=False, default=0)
    due_at = db.Column(db.DateTime, nullable=True, index=True)
    due_day = db.Column(db.Integer, nullable=True, index=True)
    interval_days = db.Column(db.Integer, nullable=False, default=0)
    is_suspended = db.Column(db.Boolean, nullable=False, default=False, index=True)
    ease_factor = db.Column(db.Float, nullable=False, default=2.5)
    reps = db.Column(db.Integer, nullable=False, default=0)
    lapses = db.Column(db.Integer, nullable=False, default=0)
    last_reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "card_id", name="uq_card_progress_user_card"),
    )

    user = db.relationship("User", back_populates="card_progress")
    card = db.relationship("Card", back_populates="progress_rows")
