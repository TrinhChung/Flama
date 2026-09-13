"""Keyset checkpoint and lease state for an explicit backfill run."""

from __future__ import annotations

from sqlalchemy import text

from app.services.study_progress_contract import BACKFILL_STATUSES, sql_allowlist
from models import db
from models.study_progress_types import (
    MYSQL_TABLE_OPTIONS,
    ascii_string,
    bigint,
    binary_hash,
    datetime6,
)


class StudyProgressBackfillCheckpoint(db.Model):
    __tablename__ = "study_progress_backfill_checkpoints"

    run_id = db.Column(
        db.String(36),
        db.ForeignKey("study_progress_backfill_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    shard_no = db.Column(db.SmallInteger, primary_key=True)
    status_code = db.Column(ascii_string(32), nullable=False)
    range_start_id = db.Column(bigint(), nullable=True)
    range_end_id = db.Column(bigint(), nullable=True)
    last_source_id = db.Column(bigint(), nullable=True)
    processed_count = db.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    retry_count = db.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    lease_token_hash = db.Column(binary_hash(), nullable=True)
    lease_expires_at = db.Column(datetime6(), nullable=True)
    updated_at = db.Column(datetime6(), nullable=False)

    run = db.relationship("StudyProgressBackfillRun", back_populates="checkpoints")

    __table_args__ = (
        db.Index(
            "ix_sp_checkpoint_lease",
            "status_code",
            "lease_expires_at",
            "run_id",
            "shard_no",
        ),
        db.CheckConstraint("shard_no >= 0", name="ck_sp_checkpoint_shard"),
        db.CheckConstraint(
            "processed_count >= 0 AND retry_count >= 0",
            name="ck_sp_checkpoint_counts",
        ),
        db.CheckConstraint(
            "range_start_id IS NULL OR range_start_id >= 0",
            name="ck_sp_checkpoint_range_start",
        ),
        db.CheckConstraint(
            "range_end_id IS NULL OR range_end_id >= 0",
            name="ck_sp_checkpoint_range_end",
        ),
        db.CheckConstraint(
            "last_source_id IS NULL OR last_source_id >= 0",
            name="ck_sp_checkpoint_last_source",
        ),
        db.CheckConstraint(
            "range_start_id IS NULL OR range_end_id IS NULL OR range_start_id <= range_end_id",
            name="ck_sp_checkpoint_range_order",
        ),
        db.CheckConstraint(
            "lease_token_hash IS NULL OR length(lease_token_hash) = 32",
            name="ck_sp_checkpoint_lease_hash",
        ),
        db.CheckConstraint(
            "(lease_token_hash IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_token_hash IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_sp_checkpoint_lease_pair",
        ),
        db.CheckConstraint(
            sql_allowlist("status_code", BACKFILL_STATUSES),
            name="ck_sp_checkpoint_status",
        ),
        MYSQL_TABLE_OPTIONS,
    )
