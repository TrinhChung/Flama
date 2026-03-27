"""Global per-user scheduler settings."""

from datetime import datetime

from models import db


class UserSchedulerSettings(db.Model):
    __tablename__ = "user_scheduler_settings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    scheduler_mode = db.Column(db.String(20), nullable=False, default="legacy", index=True)
    day_boundary_hour_local = db.Column(db.Integer, nullable=False, default=4)
    learn_ahead_seconds = db.Column(db.Integer, nullable=False, default=20 * 60)
    fsrs_allow_short_term = db.Column(db.Boolean, nullable=False, default=False)
    extra_settings_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = db.relationship("User", back_populates="scheduler_settings")
