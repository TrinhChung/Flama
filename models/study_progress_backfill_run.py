"""Frozen contract and accounting for an explicit Phase 4 backfill run."""

from __future__ import annotations

from sqlalchemy import text

from app.services.study_progress_contract import (
    BACKFILL_RUN_KINDS,
    BACKFILL_STATUSES,
    sql_allowlist,
)
from models import db
from models.study_progress_types import (
    MYSQL_TABLE_OPTIONS,
    ascii_string,
    bigint,
    binary_hash,
    datetime6,
)


class StudyProgressBackfillRun(db.Model):
    __tablename__ = "study_progress_backfill_runs"

    id = db.Column(db.String(36), primary_key=True)
    run_kind = db.Column(ascii_string(32), nullable=False)
    status_code = db.Column(ascii_string(32), nullable=False)
    repository_commit = db.Column(ascii_string(40, fixed=True), nullable=False)
    database_head = db.Column(ascii_string(64), nullable=False)
    audit_schema_version = db.Column(ascii_string(64), nullable=False)
    mapper_version = db.Column(ascii_string(32), nullable=False)
    state_schema_version = db.Column(ascii_string(64), nullable=False)
    projection_version = db.Column(ascii_string(32), nullable=False)
    contract_hash = db.Column(binary_hash(), nullable=False)
    observed_at = db.Column(datetime6(), nullable=False)
    source_progress_high_water_id = db.Column(bigint(), nullable=True)
    source_event_high_water_id = db.Column(bigint(), nullable=True)
    source_count = db.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    mirrored_count = db.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    quarantined_count = db.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    unresolvable_count = db.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    retry_count = db.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    started_at = db.Column(datetime6(), nullable=False)
    updated_at = db.Column(datetime6(), nullable=False)
    completed_at = db.Column(datetime6(), nullable=True)
    error_summary = db.Column(db.Text, nullable=True)

    checkpoints = db.relationship(
        "StudyProgressBackfillCheckpoint",
        back_populates="run",
        passive_deletes="all",
    )
    dispositions = db.relationship(
        "StudyProgressBackfillDisposition",
        back_populates="run",
        passive_deletes="all",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "run_kind", "observed_at", "contract_hash", name="uq_sp_backfill_contract"
        ),
        db.Index("ix_sp_backfill_status_updated", "status_code", "updated_at", "id"),
        db.CheckConstraint(
            sql_allowlist("run_kind", BACKFILL_RUN_KINDS), name="ck_sp_backfill_run_kind"
        ),
        db.CheckConstraint(
            sql_allowlist("status_code", BACKFILL_STATUSES),
            name="ck_sp_backfill_run_status",
        ),
        db.CheckConstraint(
            "source_count >= 0 AND mirrored_count >= 0 AND quarantined_count >= 0 "
            "AND unresolvable_count >= 0 AND retry_count >= 0",
            name="ck_sp_backfill_run_counts",
        ),
        db.CheckConstraint(
            "source_progress_high_water_id IS NULL OR source_progress_high_water_id >= 0",
            name="ck_sp_backfill_progress_watermark",
        ),
        db.CheckConstraint(
            "source_event_high_water_id IS NULL OR source_event_high_water_id >= 0",
            name="ck_sp_backfill_event_watermark",
        ),
        db.CheckConstraint("length(contract_hash) = 32", name="ck_sp_backfill_contract_hash"),
        MYSQL_TABLE_OPTIONS,
    )
