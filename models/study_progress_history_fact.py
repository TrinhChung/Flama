"""Normalized scheduler-grade history evidence for Phase 4 comparison."""

from __future__ import annotations

from app.services.study_progress_contract import (
    HISTORY_COMPLETENESS_CODES,
    PROVENANCE_CODES,
    sql_allowlist,
)
from models import db
from models.study_progress_types import (
    MYSQL_TABLE_OPTIONS,
    ascii_string,
    bigint,
    bigint_pk,
    binary_hash,
    binary_string,
    datetime6,
)


class StudyProgressHistoryFact(db.Model):
    __tablename__ = "study_progress_history_facts"

    id = db.Column(bigint_pk(), primary_key=True, autoincrement=True)
    learner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id = db.Column(
        bigint(),
        db.ForeignKey("study_progress_subjects.id", ondelete="SET NULL"),
        nullable=True,
    )
    logical_note_key = db.Column(binary_string(144), nullable=True)
    subject_generation = db.Column(bigint(), nullable=True)
    # The retired per-Card contributor of a pre-P10 fact; no table since migration 50.
    contributor_id = db.Column(bigint(), nullable=True)
    logical_card_key = db.Column(binary_string(256), nullable=False)
    review_event_id = db.Column(
        db.Integer,
        db.ForeignKey("review_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    fact_identity_hash = db.Column(binary_hash(), nullable=False)
    history_schema_version = db.Column(ascii_string(64), nullable=False)
    storage_codec = db.Column(ascii_string(64), nullable=False)
    occurred_at = db.Column(datetime6(), nullable=False)
    ingested_at = db.Column(datetime6(), nullable=False)
    provenance_code = db.Column(ascii_string(64), nullable=False)
    source_operation_key = db.Column(binary_string(512), nullable=True)
    action_key = db.Column(ascii_string(64), nullable=True)
    action_version = db.Column(ascii_string(32), nullable=True)
    review_kind = db.Column(ascii_string(20), nullable=True)
    algorithm_key = db.Column(ascii_string(64), nullable=True)
    algorithm_version = db.Column(ascii_string(32), nullable=True)
    state_schema_version = db.Column(ascii_string(64), nullable=True)
    scheduler_config_hash = db.Column(binary_hash(), nullable=True)
    before_state_hash = db.Column(binary_hash(), nullable=True)
    after_state_hash = db.Column(binary_hash(), nullable=True)
    history_completeness_code = db.Column(ascii_string(64), nullable=False)
    gap_reason_code = db.Column(ascii_string(64), nullable=True)
    fact_payload = db.Column(db.JSON, nullable=False)
    fact_payload_size = db.Column(db.SmallInteger, nullable=False)
    fact_payload_hash = db.Column(binary_hash(), nullable=False)
    created_at = db.Column(datetime6(), nullable=False)

    subject = db.relationship("StudyProgressSubject")
    review_event = db.relationship("ReviewEvent")

    __table_args__ = (
        db.UniqueConstraint(
            "learner_user_id",
            "fact_identity_hash",
            name="uq_sp_history_learner_fact",
        ),
        db.Index(
            "ix_sp_history_subject_order",
            "subject_id",
            "subject_generation",
            "occurred_at",
            "id",
        ),
        db.Index(
            "ix_sp_history_learner_order", "learner_user_id", "occurred_at", "id"
        ),
        db.Index(
            "ix_sp_history_learner_note_order",
            "learner_user_id",
            "logical_note_key",
            "occurred_at",
            "id",
        ),
        db.Index("ix_sp_history_ingested", "ingested_at", "id"),
        db.Index("ix_sp_history_review_event", "review_event_id"),
        db.CheckConstraint(
            "subject_generation IS NULL OR subject_generation >= 1",
            name="ck_sp_history_generation",
        ),
        db.CheckConstraint(
            "fact_payload_size BETWEEN 0 AND 16384",
            name="ck_sp_history_payload_size",
        ),
        db.CheckConstraint(
            "length(fact_identity_hash) = 32", name="ck_sp_history_identity_hash"
        ),
        db.CheckConstraint(
            "length(fact_payload_hash) = 32", name="ck_sp_history_payload_hash"
        ),
        db.CheckConstraint(
            sql_allowlist("provenance_code", PROVENANCE_CODES),
            name="ck_sp_history_provenance",
        ),
        db.CheckConstraint(
            sql_allowlist(
                "history_completeness_code", HISTORY_COMPLETENESS_CODES
            ),
            name="ck_sp_history_completeness",
        ),
        MYSQL_TABLE_OPTIONS,
    )
