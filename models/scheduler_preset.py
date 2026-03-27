"""Per-user scheduler preset definitions for legacy and FSRS options."""

from datetime import datetime

from models import db


class SchedulerPreset(db.Model):
    __tablename__ = "scheduler_presets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # JSON arrays stored as text to keep sqlite/mysql behavior aligned.
    learning_steps_json = db.Column(db.Text, nullable=False, default="[60, 600]")
    relearning_steps_json = db.Column(db.Text, nullable=False, default="[600]")
    fsrs_parameters_json = db.Column(db.Text, nullable=False, default="[]")
    extra_config_json = db.Column(db.Text, nullable=False, default="{}")

    graduating_interval_days = db.Column(db.Integer, nullable=False, default=1)
    easy_interval_days = db.Column(db.Integer, nullable=False, default=5)
    hard_multiplier = db.Column(db.Float, nullable=False, default=1.2)
    easy_multiplier = db.Column(db.Float, nullable=False, default=1.3)
    interval_modifier = db.Column(db.Float, nullable=False, default=1.0)
    lapse_multiplier = db.Column(db.Float, nullable=False, default=0.0)
    minimum_lapse_interval_days = db.Column(db.Integer, nullable=False, default=1)
    maximum_interval_days = db.Column(db.Integer, nullable=False, default=36500)
    leech_threshold = db.Column(db.Integer, nullable=False, default=8)
    leech_action = db.Column(db.String(32), nullable=False, default="suspend")

    desired_retention = db.Column(db.Float, nullable=False, default=0.9)
    historical_retention = db.Column(db.Float, nullable=True)
    ignore_reviews_before = db.Column(db.DateTime, nullable=True)
    fsrs_reschedule_on_change = db.Column(db.Boolean, nullable=False, default=False)
    fsrs_short_term_enabled = db.Column(db.Boolean, nullable=False, default=False)

    is_default = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = db.relationship("User", back_populates="scheduler_presets")
    decks = db.relationship("Deck", back_populates="scheduler_preset")
    review_events = db.relationship("ReviewEvent", back_populates="scheduler_preset")

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_scheduler_presets_user_name"),
        db.Index("ix_scheduler_presets_user_default", "user_id", "is_default"),
    )
