"""Durable, per-learner commit-ordered feed for history counts."""

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from models import db
from models.study_progress_types import MYSQL_TABLE_OPTIONS, ascii_string, binary_hash, datetime6


class ReviewAnalyticsOutbox(db.Model):
    __tablename__ = "review_analytics_outbox"

    user_id = db.Column(db.Integer, db.ForeignKey("review_analytics_heads.user_id", ondelete="CASCADE"),
                        primary_key=True, autoincrement=False)
    source_revision = db.Column(sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql"),
                                primary_key=True, autoincrement=False)
    payload_version = db.Column(ascii_string(32), nullable=False)
    events_payload = db.Column(db.JSON, nullable=False)
    payload_size = db.Column(db.Integer, nullable=False)
    payload_hash = db.Column(binary_hash(), nullable=False)
    event_count = db.Column(db.Integer, nullable=False)
    is_dirty = db.Column(db.Boolean, nullable=False, server_default=sa.text("0"))
    created_at = db.Column(datetime6(), nullable=False)
    applied_at = db.Column(datetime6(), nullable=True)
    last_error_code = db.Column(ascii_string(64), nullable=True)

    __table_args__ = (
        db.Index("ix_review_analytics_outbox_pending", "applied_at", "user_id", "source_revision"),
        db.Index("ix_review_analytics_outbox_pending_age", "applied_at", "user_id", "created_at"),
        db.CheckConstraint("source_revision > 0", name="ck_review_outbox_revision"),
        db.CheckConstraint("event_count >= 0", name="ck_review_outbox_event_count"),
        db.CheckConstraint("payload_size BETWEEN 2 AND 2097152", name="ck_review_outbox_payload_size"),
        db.CheckConstraint("length(payload_hash) = 32", name="ck_review_outbox_payload_hash"),
        MYSQL_TABLE_OPTIONS,
    )
