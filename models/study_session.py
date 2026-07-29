"""Durable frontend-driven study session."""

from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class StudySession(db.Model):
    __tablename__ = "study_sessions"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope_type = db.Column(db.String(20), nullable=False, default="deck")
    scope_id = db.Column(db.String(64), nullable=False)
    local_deck_id = db.Column(
        db.Integer,
        db.ForeignKey("decks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    clone_install_id = db.Column(
        db.String(36),
        db.ForeignKey("deck_installs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    scheduler_algorithm = db.Column(
        db.String(64),
        nullable=False,
        default="legacy-anki",
    )
    algorithm_version = db.Column(db.String(32), nullable=False, default="1.0.0")
    wire_schema_version = db.Column(
        db.String(32),
        nullable=False,
        default="study-session.v2",
    )
    timezone = db.Column(db.String(64), nullable=False, default="UTC")
    day_boundary_hour_local = db.Column(db.Integer, nullable=False, default=4)
    learn_ahead_seconds = db.Column(db.Integer, nullable=False, default=1200)
    snapshot_hash = db.Column(db.String(80), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False)
    config_snapshot_json = db.Column(db.Text, nullable=False, default="{}")
    opened_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    committed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    cards = db.relationship(
        "StudySessionCard",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    commits = db.relationship(
        "StudySessionCommit",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.Index(
            "ix_study_sessions_user_status_expires",
            "user_id",
            "status",
            "expires_at",
        ),
    )
