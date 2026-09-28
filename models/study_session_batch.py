"""Durable tracking and idempotency for asynchronous study review batches."""

from __future__ import annotations

from datetime import datetime

from models import db
from models.model_uuid import uuid_str


class StudySessionBatch(db.Model):
    __tablename__ = "study_session_batches"

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
    batch_id = db.Column(db.String(64), nullable=False, index=True)
    batch_sequence = db.Column(db.Integer, nullable=False, default=1)
    event_count = db.Column(db.Integer, nullable=False, default=0)
    attempt_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    status = db.Column(db.String(20), nullable=False, default="enqueued", index=True)
    commit_reason = db.Column(db.String(32), nullable=True)
    is_final = db.Column(db.Boolean, nullable=False, default=False)
    request_hash = db.Column(db.String(80), nullable=False)
    payload_json = db.Column(db.Text, nullable=True)
    response_json = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    enqueued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    session = db.relationship("StudySession", back_populates="batches")

    __table_args__ = (
        db.UniqueConstraint(
            "session_id",
            "batch_id",
            name="uq_study_session_batches_batch_id",
        ),
        db.Index(
            "ix_study_session_batches_status_enqueued",
            "status",
            "enqueued_at",
        ),
    )
