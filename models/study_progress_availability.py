"""Stable queue anchors projected from one shadow-progress contributor."""

from __future__ import annotations

from sqlalchemy import text

from app.services.study_progress_contract import NORMALIZED_QUEUES, sql_allowlist
from models import db
from models.study_progress_types import (
    MYSQL_TABLE_OPTIONS,
    ascii_string,
    bigint,
    binary_hash,
    binary_string,
    datetime6,
)


class StudyProgressAvailability(db.Model):
    __tablename__ = "study_progress_availability"

    contributor_id = db.Column(bigint(), primary_key=True)
    subject_id = db.Column(bigint(), nullable=False)
    subject_generation = db.Column(bigint(), nullable=False)
    projection_version = db.Column(ascii_string(32), nullable=False)
    normalized_queue = db.Column(ascii_string(20), nullable=False)
    due_at = db.Column(datetime6(), nullable=True)
    due_day = db.Column(db.Integer, nullable=True)
    is_suspended = db.Column(
        db.Boolean, nullable=False, default=False, server_default=text("0")
    )
    is_buried = db.Column(
        db.Boolean, nullable=False, default=False, server_default=text("0")
    )
    buried_until_day = db.Column(db.Integer, nullable=True)
    card_created_at = db.Column(datetime6(), nullable=False)
    card_order_key = db.Column(binary_string(144), nullable=False)
    state_schema_version = db.Column(ascii_string(64), nullable=False)
    semantic_state_hash = db.Column(binary_hash(), nullable=False)
    created_at = db.Column(datetime6(), nullable=False)
    updated_at = db.Column(datetime6(), nullable=False)

    contributor = db.relationship(
        "StudyProgressContributor", back_populates="availability"
    )

    __table_args__ = (
        db.ForeignKeyConstraint(
            ["contributor_id", "subject_id"],
            [
                "study_progress_contributors.id",
                "study_progress_contributors.subject_id",
            ],
            name="fk_sp_avail_contributor_subject",
            ondelete="CASCADE",
        ),
        db.Index(
            "ix_sp_avail_subject_queue_day",
            "subject_id",
            "subject_generation",
            "normalized_queue",
            "is_suspended",
            "is_buried",
            "due_day",
            "due_at",
        ),
        db.Index(
            "ix_sp_avail_queue_time",
            "normalized_queue",
            "is_suspended",
            "is_buried",
            "due_at",
            "contributor_id",
        ),
        db.CheckConstraint(
            "subject_generation >= 1", name="ck_sp_avail_generation"
        ),
        db.CheckConstraint(
            sql_allowlist("normalized_queue", NORMALIZED_QUEUES),
            name="ck_sp_avail_queue",
        ),
        db.CheckConstraint(
            "length(semantic_state_hash) = 32", name="ck_sp_avail_semantic_hash"
        ),
        MYSQL_TABLE_OPTIONS,
    )
