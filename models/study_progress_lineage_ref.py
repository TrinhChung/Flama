"""Detached-safe current lineage references for progress contributors."""

from __future__ import annotations

from app.services.study_progress_contract import (
    LINEAGE_REF_KINDS,
    POINTER_STATUSES,
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


class StudyProgressLineageRef(db.Model):
    __tablename__ = "study_progress_lineage_refs"

    id = db.Column(bigint_pk(), primary_key=True, autoincrement=True)
    contributor_id = db.Column(
        bigint(),
        db.ForeignKey("study_progress_contributors.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_generation = db.Column(bigint(), nullable=False)
    ref_kind = db.Column(ascii_string(64), nullable=False)
    source_row_key = db.Column(binary_string(144), nullable=False)
    source_key = db.Column(binary_string(1020), nullable=True)
    external_card_id = db.Column(binary_string(512), nullable=True)
    external_note_id = db.Column(binary_string(512), nullable=True)
    source_snapshot_hash = db.Column(binary_hash(), nullable=True)
    source_payload_hash = db.Column(binary_hash(), nullable=True)
    ref_status = db.Column(ascii_string(64), nullable=False)
    occurred_at = db.Column(datetime6(), nullable=True)
    ingested_at = db.Column(datetime6(), nullable=False)

    contributor = db.relationship(
        "StudyProgressContributor", back_populates="lineage_refs"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "contributor_id",
            "subject_generation",
            "ref_kind",
            "source_row_key",
            name="uq_sp_lineage_ref",
        ),
        db.Index("ix_sp_lineage_source", "ref_kind", "source_row_key"),
        db.Index(
            "ix_sp_lineage_contributor_status", "contributor_id", "ref_status", "id"
        ),
        db.CheckConstraint(
            "subject_generation >= 1", name="ck_sp_lineage_generation"
        ),
        db.CheckConstraint(
            sql_allowlist("ref_kind", LINEAGE_REF_KINDS),
            name="ck_sp_lineage_kind",
        ),
        db.CheckConstraint(
            sql_allowlist("ref_status", POINTER_STATUSES),
            name="ck_sp_lineage_status",
        ),
        db.CheckConstraint(
            "source_snapshot_hash IS NULL OR length(source_snapshot_hash) = 32",
            name="ck_sp_lineage_snapshot_hash",
        ),
        db.CheckConstraint(
            "source_payload_hash IS NULL OR length(source_payload_hash) = 32",
            name="ck_sp_lineage_payload_hash",
        ),
        MYSQL_TABLE_OPTIONS,
    )
