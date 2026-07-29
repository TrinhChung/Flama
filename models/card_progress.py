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
    interval_days_raw = db.Column(db.Float, nullable=True)
    is_suspended = db.Column(db.Boolean, nullable=False, default=False, index=True)
    is_buried = db.Column(db.Boolean, nullable=False, default=False, index=True)
    buried_until_day = db.Column(db.Integer, nullable=True, index=True)
    review_kind = db.Column(db.String(20), nullable=False, default="review", index=True)
    scheduler_mode = db.Column(db.String(20), nullable=False, default="legacy", index=True)
    ease_factor = db.Column(db.Float, nullable=False, default=2.5)
    memory_stability = db.Column(db.Float, nullable=True)
    memory_difficulty = db.Column(db.Float, nullable=True)
    suspension_reason = db.Column(db.String(32), nullable=True)
    last_leech_at = db.Column(db.DateTime, nullable=True)
    last_leech_lapses = db.Column(db.Integer, nullable=False, default=0)
    last_review_event_id = db.Column(
        db.Integer,
        db.ForeignKey("review_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reps = db.Column(db.Integer, nullable=False, default=0)
    lapses = db.Column(db.Integer, nullable=False, default=0)
    last_reviewed_at = db.Column(db.DateTime, nullable=True)
    revision = db.Column(db.BigInteger, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "card_id", name="uq_card_progress_user_card"),
        db.Index("ix_card_progress_user_queue_due_day", "user_id", "queue", "due_day"),
        db.Index("ix_card_progress_user_queue_due_at", "user_id", "queue", "due_at"),
        db.Index("ix_card_progress_user_hidden_flags", "user_id", "is_suspended", "is_buried"),
    )

    user = db.relationship("User", back_populates="card_progress")
    card = db.relationship("Card", back_populates="progress_rows")
    last_review_event = db.relationship("ReviewEvent")
