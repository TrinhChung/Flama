"""Idempotency receipt for a completed study session batch."""

from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class StudySessionCommit(db.Model):
    __tablename__ = "study_session_commits"

    id = db.Column(db.String(36), primary_key=True, default=uuid_str)
    session_id = db.Column(
        db.String(36),
        db.ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idempotency_key = db.Column(db.String(64), nullable=False)
    request_hash = db.Column(db.String(80), nullable=False)
    response_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    session = db.relationship("StudySession", back_populates="commits")

    __table_args__ = (
        db.UniqueConstraint(
            "session_id",
            "idempotency_key",
            name="uq_study_session_commits_idempotency",
        ),
        db.UniqueConstraint(
            "session_id",
            name="uq_study_session_commits_single_success",
        ),
    )
