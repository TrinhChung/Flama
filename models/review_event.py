from datetime import datetime

from sqlalchemy import event
from sqlalchemy.orm import Session

from models import db


class ReviewEvent(db.Model):
    __tablename__ = "review_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # The Card as named when answered: a presentation key, or a pre-P11 ID.
    card_id = db.Column(db.String(80), nullable=False, index=True)
    # Snapshot of the Card's Note when the event was written (no FK: history
    # survives Card and Note deletion). NULL on old events that could not be
    # resolved to a live Card when migration 46 backfilled them.
    note_id = db.Column(db.String(36), nullable=True)
    deck_id = db.Column(db.Integer, nullable=True, index=True)
    note_type_id = db.Column(db.String(36), nullable=True, index=True)
    scheduler_preset_id = db.Column(
        db.Integer,
        db.ForeignKey("scheduler_presets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    study_session_id = db.Column(
        db.String(36),
        db.ForeignKey("study_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    client_event_id = db.Column(db.String(36), nullable=True)
    sequence_no = db.Column(db.Integer, nullable=True)
    scheduler_algorithm = db.Column(db.String(64), nullable=True)
    algorithm_version = db.Column(db.String(32), nullable=True)
    scheduler_config_hash = db.Column(db.String(80), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=False, index=True)
    duration_ms = db.Column(db.Integer, nullable=True)
    rating = db.Column(db.String(20), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    scheduler_mode = db.Column(db.String(20), nullable=False, default="legacy")
    review_kind = db.Column(db.String(20), nullable=False, default="review")
    queue_before = db.Column(db.String(20), nullable=True)
    queue_after = db.Column(db.String(20), nullable=True)
    interval_days_before = db.Column(db.Float, nullable=True)
    interval_days_after = db.Column(db.Float, nullable=True)
    due_day_before = db.Column(db.Integer, nullable=True)
    due_day_after = db.Column(db.Integer, nullable=True)
    days_late = db.Column(db.Integer, nullable=True)
    ease_factor_before = db.Column(db.Float, nullable=True)
    ease_factor_after = db.Column(db.Float, nullable=True)
    memory_stability_before = db.Column(db.Float, nullable=True)
    memory_stability_after = db.Column(db.Float, nullable=True)
    memory_difficulty_before = db.Column(db.Float, nullable=True)
    memory_difficulty_after = db.Column(db.Float, nullable=True)
    leeched_after = db.Column(db.Boolean, nullable=False, default=False)
    suspended_after = db.Column(db.Boolean, nullable=False, default=False)
    payload_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "client_event_id",
            name="uq_review_events_user_client_event",
        ),
        db.UniqueConstraint(
            "study_session_id",
            "sequence_no",
            name="uq_review_events_session_sequence",
        ),
        db.Index("ix_review_events_user_reviewed_at", "user_id", "reviewed_at"),
        db.Index("ix_review_events_user_card_reviewed_at", "user_id", "card_id", "reviewed_at"),
        db.Index("ix_review_events_user_scheduler_reviewed_at", "user_id", "scheduler_mode", "reviewed_at"),
        db.Index("ix_review_events_user_kind_reviewed_at", "user_id", "review_kind", "reviewed_at"),
        db.Index("ix_review_events_user_note", "user_id", "note_id"),
    )

    scheduler_preset = db.relationship("SchedulerPreset", back_populates="review_events")


@event.listens_for(Session, "before_flush")
def _snapshot_review_event_notes(session: Session, _flush_context, _instances) -> None:
    """Stamp every new ReviewEvent with its Card's Note (Phase 6, D6-07).

    One set-wise lookup per flush covers every writer (study commit, direct
    answer, MCP, Connect revlog, import). An event whose Card cannot be
    resolved keeps ``note_id`` NULL, as migration 46 does for old rows.
    """

    from models.card import card_key_pairs

    pending = [
        item
        for item in session.new
        if isinstance(item, ReviewEvent) and item.note_id is None and item.card_id
    ]
    if not pending:
        return
    with session.no_autoflush:
        # A presentation key names its Note; a legacy ID resolves through the registry.
        note_by_card = {
            card_id: note_id
            for card_id, (note_id, _application_id) in card_key_pairs(
                session, {str(item.card_id) for item in pending}
            ).items()
        }
    for item in pending:
        note_id = note_by_card.get(str(item.card_id))
        if note_id:
            item.note_id = note_id
