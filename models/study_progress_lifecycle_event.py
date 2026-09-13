"""Append-only topology and destructive-transition evidence."""

from __future__ import annotations

from app.services.study_progress_contract import (
    BACKFILL_DISPOSITIONS,
    LIFECYCLE_TRANSITIONS,
    sql_allowlist,
)
from models import db
from models.study_progress_types import (
    MYSQL_TABLE_OPTIONS,
    ascii_string,
    bigint,
    bigint_pk,
    binary_hash,
    datetime6,
)


class StudyProgressLifecycleEvent(db.Model):
    __tablename__ = "study_progress_lifecycle_events"

    id = db.Column(bigint_pk(), primary_key=True, autoincrement=True)
    subject_id = db.Column(
        bigint(),
        db.ForeignKey("study_progress_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    related_subject_id = db.Column(
        bigint(),
        db.ForeignKey("study_progress_subjects.id", ondelete="SET NULL"),
        nullable=True,
    )
    old_generation = db.Column(bigint(), nullable=False)
    new_generation = db.Column(bigint(), nullable=False)
    transition_code = db.Column(ascii_string(64), nullable=False)
    occurred_at = db.Column(datetime6(), nullable=False)
    source_path = db.Column(ascii_string(128), nullable=False)
    operation_key_hash = db.Column(binary_hash(), nullable=False)
    old_topology_hash = db.Column(binary_hash(), nullable=True)
    new_topology_hash = db.Column(binary_hash(), nullable=True)
    old_authority_hash = db.Column(binary_hash(), nullable=True)
    new_authority_hash = db.Column(binary_hash(), nullable=True)
    old_lineage_hash = db.Column(binary_hash(), nullable=True)
    new_lineage_hash = db.Column(binary_hash(), nullable=True)
    result_code = db.Column(ascii_string(64), nullable=False)
    reason_code = db.Column(ascii_string(64), nullable=True)
    evidence_schema_version = db.Column(ascii_string(64), nullable=False)
    evidence_payload = db.Column(db.JSON, nullable=False)
    evidence_payload_size = db.Column(db.SmallInteger, nullable=False)
    evidence_payload_hash = db.Column(binary_hash(), nullable=False)
    created_at = db.Column(datetime6(), nullable=False)

    subject = db.relationship(
        "StudyProgressSubject", foreign_keys=[subject_id]
    )
    related_subject = db.relationship(
        "StudyProgressSubject", foreign_keys=[related_subject_id]
    )

    __table_args__ = (
        db.UniqueConstraint(
            "subject_id",
            "new_generation",
            "transition_code",
            "operation_key_hash",
            name="uq_sp_lifecycle_operation",
        ),
        db.Index(
            "ix_sp_lifecycle_subject_order",
            "subject_id",
            "new_generation",
            "occurred_at",
            "id",
        ),
        db.Index(
            "ix_sp_lifecycle_related", "related_subject_id", "occurred_at", "id"
        ),
        db.CheckConstraint("old_generation >= 1", name="ck_sp_lifecycle_old_generation"),
        db.CheckConstraint(
            "new_generation > old_generation", name="ck_sp_lifecycle_generation_step"
        ),
        db.CheckConstraint(
            "evidence_payload_size BETWEEN 0 AND 16384",
            name="ck_sp_lifecycle_payload_size",
        ),
        db.CheckConstraint(
            "length(operation_key_hash) = 32",
            name="ck_sp_lifecycle_operation_hash",
        ),
        db.CheckConstraint(
            "length(evidence_payload_hash) = 32",
            name="ck_sp_lifecycle_payload_hash",
        ),
        db.CheckConstraint(
            sql_allowlist("transition_code", LIFECYCLE_TRANSITIONS),
            name="ck_sp_lifecycle_transition",
        ),
        db.CheckConstraint(
            sql_allowlist("result_code", BACKFILL_DISPOSITIONS),
            name="ck_sp_lifecycle_result",
        ),
        MYSQL_TABLE_OPTIONS,
    )
