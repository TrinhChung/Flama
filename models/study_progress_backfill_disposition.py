"""One latest disposition per frozen source identity and backfill run."""

from __future__ import annotations

from sqlalchemy import text

from app.services.study_progress_contract import (
    BACKFILL_DISPOSITIONS,
    BACKFILL_SOURCE_KINDS,
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


class StudyProgressBackfillDisposition(db.Model):
    __tablename__ = "study_progress_backfill_dispositions"

    id = db.Column(bigint_pk(), primary_key=True, autoincrement=True)
    run_id = db.Column(
        db.String(36),
        db.ForeignKey("study_progress_backfill_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_kind = db.Column(ascii_string(32), nullable=False)
    source_row_key = db.Column(binary_string(144), nullable=False)
    subject_id = db.Column(
        bigint(),
        db.ForeignKey("study_progress_subjects.id", ondelete="SET NULL"),
        nullable=True,
    )
    observed_generation = db.Column(bigint(), nullable=True)
    observed_revision = db.Column(bigint(), nullable=True)
    source_hash = db.Column(binary_hash(), nullable=False)
    disposition_code = db.Column(ascii_string(64), nullable=False)
    reason_code = db.Column(ascii_string(64), nullable=True)
    result_hash = db.Column(binary_hash(), nullable=True)
    attempt_count = db.Column(
        db.Integer, nullable=False, default=1, server_default=text("1")
    )
    evidence_payload = db.Column(db.JSON, nullable=False)
    evidence_payload_size = db.Column(db.SmallInteger, nullable=False)
    evidence_payload_hash = db.Column(binary_hash(), nullable=False)
    created_at = db.Column(datetime6(), nullable=False)
    updated_at = db.Column(datetime6(), nullable=False)

    run = db.relationship("StudyProgressBackfillRun", back_populates="dispositions")
    subject = db.relationship("StudyProgressSubject")

    __table_args__ = (
        db.UniqueConstraint(
            "run_id", "source_kind", "source_row_key", name="uq_sp_disposition_source"
        ),
        db.Index(
            "ix_sp_disposition_result", "run_id", "disposition_code", "id"
        ),
        db.Index(
            "ix_sp_disposition_subject", "subject_id", "observed_generation", "id"
        ),
        db.CheckConstraint(
            "observed_generation IS NULL OR observed_generation >= 0",
            name="ck_sp_disposition_generation",
        ),
        db.CheckConstraint(
            "observed_revision IS NULL OR observed_revision >= 0",
            name="ck_sp_disposition_revision",
        ),
        db.CheckConstraint("attempt_count >= 1", name="ck_sp_disposition_attempt"),
        db.CheckConstraint(
            "evidence_payload_size BETWEEN 0 AND 16384",
            name="ck_sp_disposition_payload_size",
        ),
        db.CheckConstraint(
            "length(source_hash) = 32", name="ck_sp_disposition_source_hash"
        ),
        db.CheckConstraint(
            "result_hash IS NULL OR length(result_hash) = 32",
            name="ck_sp_disposition_result_hash",
        ),
        db.CheckConstraint(
            "length(evidence_payload_hash) = 32",
            name="ck_sp_disposition_payload_hash",
        ),
        db.CheckConstraint(
            sql_allowlist("source_kind", BACKFILL_SOURCE_KINDS),
            name="ck_sp_disposition_source_kind",
        ),
        db.CheckConstraint(
            sql_allowlist("disposition_code", BACKFILL_DISPOSITIONS),
            name="ck_sp_disposition_code",
        ),
        MYSQL_TABLE_OPTIONS,
    )
