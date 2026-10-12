"""Historical backfill schema, isolated from runtime metadata (migration 39)."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import declarative_base
from app.services.study_progress_contract import (
    BACKFILL_RUN_KINDS, BACKFILL_STATUSES, BACKFILL_DISPOSITIONS,
    BACKFILL_SOURCE_KINDS, sql_allowlist,
)
from models.study_progress_types import (
    MYSQL_TABLE_OPTIONS, ascii_string, bigint, bigint_pk, binary_hash,
    binary_string, datetime6,
)

RETIRED_BACKFILL_METADATA = sa.MetaData()
_BackfillBase = declarative_base(metadata=RETIRED_BACKFILL_METADATA)
# FK resolution only; these parents are never created by this module.
sa.Table("study_progress_subjects", RETIRED_BACKFILL_METADATA,
         sa.Column("id", bigint(), primary_key=True))

class StudyProgressBackfillRun(_BackfillBase):
    __tablename__ = "study_progress_backfill_runs"

    id = sa.Column(sa.String(36), primary_key=True)
    run_kind = sa.Column(ascii_string(32), nullable=False)
    status_code = sa.Column(ascii_string(32), nullable=False)
    repository_commit = sa.Column(ascii_string(40, fixed=True), nullable=False)
    database_head = sa.Column(ascii_string(64), nullable=False)
    audit_schema_version = sa.Column(ascii_string(64), nullable=False)
    mapper_version = sa.Column(ascii_string(32), nullable=False)
    state_schema_version = sa.Column(ascii_string(64), nullable=False)
    projection_version = sa.Column(ascii_string(32), nullable=False)
    contract_hash = sa.Column(binary_hash(), nullable=False)
    observed_at = sa.Column(datetime6(), nullable=False)
    source_progress_high_water_id = sa.Column(bigint(), nullable=True)
    source_event_high_water_id = sa.Column(bigint(), nullable=True)
    source_count = sa.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    mirrored_count = sa.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    quarantined_count = sa.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    unresolvable_count = sa.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    retry_count = sa.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    started_at = sa.Column(datetime6(), nullable=False)
    updated_at = sa.Column(datetime6(), nullable=False)
    completed_at = sa.Column(datetime6(), nullable=True)
    error_summary = sa.Column(sa.Text, nullable=True)

    __table_args__ = (
        sa.UniqueConstraint(
            "run_kind", "observed_at", "contract_hash", name="uq_sp_backfill_contract"
        ),
        sa.Index("ix_sp_backfill_status_updated", "status_code", "updated_at", "id"),
        sa.CheckConstraint(
            sql_allowlist("run_kind", BACKFILL_RUN_KINDS), name="ck_sp_backfill_run_kind"
        ),
        sa.CheckConstraint(
            sql_allowlist("status_code", BACKFILL_STATUSES),
            name="ck_sp_backfill_run_status",
        ),
        sa.CheckConstraint(
            "source_count >= 0 AND mirrored_count >= 0 AND quarantined_count >= 0 "
            "AND unresolvable_count >= 0 AND retry_count >= 0",
            name="ck_sp_backfill_run_counts",
        ),
        sa.CheckConstraint(
            "source_progress_high_water_id IS NULL OR source_progress_high_water_id >= 0",
            name="ck_sp_backfill_progress_watermark",
        ),
        sa.CheckConstraint(
            "source_event_high_water_id IS NULL OR source_event_high_water_id >= 0",
            name="ck_sp_backfill_event_watermark",
        ),
        sa.CheckConstraint("length(contract_hash) = 32", name="ck_sp_backfill_contract_hash"),
        MYSQL_TABLE_OPTIONS,
    )


class StudyProgressBackfillCheckpoint(_BackfillBase):
    __tablename__ = "study_progress_backfill_checkpoints"

    run_id = sa.Column(
        sa.String(36),
        sa.ForeignKey("study_progress_backfill_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    shard_no = sa.Column(sa.SmallInteger, primary_key=True)
    status_code = sa.Column(ascii_string(32), nullable=False)
    range_start_id = sa.Column(bigint(), nullable=True)
    range_end_id = sa.Column(bigint(), nullable=True)
    last_source_id = sa.Column(bigint(), nullable=True)
    processed_count = sa.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    retry_count = sa.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    lease_token_hash = sa.Column(binary_hash(), nullable=True)
    lease_expires_at = sa.Column(datetime6(), nullable=True)
    updated_at = sa.Column(datetime6(), nullable=False)


    __table_args__ = (
        sa.Index(
            "ix_sp_checkpoint_lease",
            "status_code",
            "lease_expires_at",
            "run_id",
            "shard_no",
        ),
        sa.CheckConstraint("shard_no >= 0", name="ck_sp_checkpoint_shard"),
        sa.CheckConstraint(
            "processed_count >= 0 AND retry_count >= 0",
            name="ck_sp_checkpoint_counts",
        ),
        sa.CheckConstraint(
            "range_start_id IS NULL OR range_start_id >= 0",
            name="ck_sp_checkpoint_range_start",
        ),
        sa.CheckConstraint(
            "range_end_id IS NULL OR range_end_id >= 0",
            name="ck_sp_checkpoint_range_end",
        ),
        sa.CheckConstraint(
            "last_source_id IS NULL OR last_source_id >= 0",
            name="ck_sp_checkpoint_last_source",
        ),
        sa.CheckConstraint(
            "range_start_id IS NULL OR range_end_id IS NULL OR range_start_id <= range_end_id",
            name="ck_sp_checkpoint_range_order",
        ),
        sa.CheckConstraint(
            "lease_token_hash IS NULL OR length(lease_token_hash) = 32",
            name="ck_sp_checkpoint_lease_hash",
        ),
        sa.CheckConstraint(
            "(lease_token_hash IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_token_hash IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_sp_checkpoint_lease_pair",
        ),
        sa.CheckConstraint(
            sql_allowlist("status_code", BACKFILL_STATUSES),
            name="ck_sp_checkpoint_status",
        ),
        MYSQL_TABLE_OPTIONS,
    )


class StudyProgressBackfillDisposition(_BackfillBase):
    __tablename__ = "study_progress_backfill_dispositions"

    id = sa.Column(bigint_pk(), primary_key=True, autoincrement=True)
    run_id = sa.Column(
        sa.String(36),
        sa.ForeignKey("study_progress_backfill_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_kind = sa.Column(ascii_string(32), nullable=False)
    source_row_key = sa.Column(binary_string(144), nullable=False)
    subject_id = sa.Column(
        bigint(),
        sa.ForeignKey("study_progress_subjects.id", ondelete="SET NULL"),
        nullable=True,
    )
    observed_generation = sa.Column(bigint(), nullable=True)
    observed_revision = sa.Column(bigint(), nullable=True)
    source_hash = sa.Column(binary_hash(), nullable=False)
    disposition_code = sa.Column(ascii_string(64), nullable=False)
    reason_code = sa.Column(ascii_string(64), nullable=True)
    result_hash = sa.Column(binary_hash(), nullable=True)
    attempt_count = sa.Column(
        sa.Integer, nullable=False, default=1, server_default=text("1")
    )
    evidence_payload = sa.Column(sa.JSON, nullable=False)
    evidence_payload_size = sa.Column(sa.SmallInteger, nullable=False)
    evidence_payload_hash = sa.Column(binary_hash(), nullable=False)
    created_at = sa.Column(datetime6(), nullable=False)
    updated_at = sa.Column(datetime6(), nullable=False)


    __table_args__ = (
        sa.UniqueConstraint(
            "run_id", "source_kind", "source_row_key", name="uq_sp_disposition_source"
        ),
        sa.Index(
            "ix_sp_disposition_result", "run_id", "disposition_code", "id"
        ),
        sa.Index(
            "ix_sp_disposition_subject", "subject_id", "observed_generation", "id"
        ),
        sa.CheckConstraint(
            "observed_generation IS NULL OR observed_generation >= 0",
            name="ck_sp_disposition_generation",
        ),
        sa.CheckConstraint(
            "observed_revision IS NULL OR observed_revision >= 0",
            name="ck_sp_disposition_revision",
        ),
        sa.CheckConstraint("attempt_count >= 1", name="ck_sp_disposition_attempt"),
        sa.CheckConstraint(
            "evidence_payload_size BETWEEN 0 AND 16384",
            name="ck_sp_disposition_payload_size",
        ),
        sa.CheckConstraint(
            "length(source_hash) = 32", name="ck_sp_disposition_source_hash"
        ),
        sa.CheckConstraint(
            "result_hash IS NULL OR length(result_hash) = 32",
            name="ck_sp_disposition_result_hash",
        ),
        sa.CheckConstraint(
            "length(evidence_payload_hash) = 32",
            name="ck_sp_disposition_payload_hash",
        ),
        sa.CheckConstraint(
            sql_allowlist("source_kind", BACKFILL_SOURCE_KINDS),
            name="ck_sp_disposition_source_kind",
        ),
        sa.CheckConstraint(
            sql_allowlist("disposition_code", BACKFILL_DISPOSITIONS),
            name="ck_sp_disposition_code",
        ),
        MYSQL_TABLE_OPTIONS,
    )
