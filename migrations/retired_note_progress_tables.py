"""Frozen schema of the NOTE progress tables retired by P10 (for migrations only).

Migrations 39 and 40 created these tables from model classes. The models were
removed in P10-09 and migration 50 drops the tables; these copies keep a fresh
migration chain building the same historical schema. They live on a private
MetaData, so importing this module never registers them with the application.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import declarative_base

from app.services.study_progress_contract import (
    CONTRIBUTOR_STATUSES,
    EVIDENCE_KINDS,
    HISTORY_COMPLETENESS_CODES,
    LINEAGE_REF_KINDS,
    NORMALIZED_QUEUES,
    POINTER_STATUSES,
    PROVENANCE_CODES,
    contributor_evidence_check,
    sql_allowlist,
)
from models.study_progress_types import (
    MYSQL_TABLE_OPTIONS,
    ascii_string,
    bigint,
    bigint_pk,
    binary_hash,
    binary_string,
    datetime6,
    register_mysql_parent_collations,
)
from models.study_progress_subject import StudyProgressSubject
from migrations.retired_card_tables import Card, CardProgress

RETIRED_METADATA = sa.MetaData()
_RetiredBase = declarative_base(metadata=RETIRED_METADATA)

# Only current subject metadata is copied; it is never created from here.
StudyProgressSubject.__table__.to_metadata(RETIRED_METADATA)
# Frozen historical parents, copied without importing retired runtime modules.
for _parent in (Card.__table__, CardProgress.__table__):
    _parent.to_metadata(RETIRED_METADATA)


class StudyProgressState(_RetiredBase):
    __tablename__ = "study_progress_states"

    subject_id = sa.Column(
        bigint(),
        sa.ForeignKey("study_progress_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_generation = sa.Column(bigint(), nullable=False)
    mirror_revision = sa.Column(bigint(), nullable=False)
    algorithm_key = sa.Column(ascii_string(64), nullable=False)
    algorithm_version = sa.Column(ascii_string(32), nullable=False)
    state_schema_version = sa.Column(ascii_string(64), nullable=False)
    storage_codec = sa.Column(ascii_string(64), nullable=False)
    state_payload = sa.Column(sa.JSON, nullable=False)
    state_payload_size = sa.Column(sa.SmallInteger, nullable=False)
    algorithm_state_hash = sa.Column(binary_hash(), nullable=False)
    semantic_state_hash = sa.Column(binary_hash(), nullable=False)
    created_at = sa.Column(datetime6(), nullable=False)
    updated_at = sa.Column(datetime6(), nullable=False)


    __table_args__ = (
        sa.Index(
            "ix_sp_state_identity",
            "algorithm_key",
            "algorithm_version",
            "state_schema_version",
        ),
        sa.CheckConstraint("subject_generation >= 1", name="ck_sp_state_generation"),
        sa.CheckConstraint("mirror_revision >= 0", name="ck_sp_state_revision"),
        sa.CheckConstraint(
            "state_payload_size BETWEEN 0 AND 16384", name="ck_sp_state_payload_size"
        ),
        sa.CheckConstraint(
            "length(algorithm_state_hash) = 32", name="ck_sp_state_algorithm_hash"
        ),
        sa.CheckConstraint(
            "length(semantic_state_hash) = 32", name="ck_sp_state_semantic_hash"
        ),
        MYSQL_TABLE_OPTIONS,
    )


class StudyAuthoritySubjectToken(_RetiredBase):
    __tablename__ = "study_authority_subject_tokens"

    subject_id = sa.Column(
        bigint(),
        sa.ForeignKey("study_progress_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_generation = sa.Column(bigint(), nullable=False)
    authority_revision = sa.Column(
        bigint(), nullable=False, default=0, server_default=text("0")
    )
    semantic_state_hash = sa.Column(binary_hash(), nullable=True)
    created_at = sa.Column(datetime6(), nullable=False)
    updated_at = sa.Column(datetime6(), nullable=False)

    __table_args__ = (
        sa.CheckConstraint(
            "subject_generation >= 1", name="ck_study_authority_token_generation"
        ),
        sa.CheckConstraint(
            "authority_revision >= 0", name="ck_study_authority_token_revision"
        ),
        sa.CheckConstraint(
            "semantic_state_hash IS NULL OR length(semantic_state_hash) = 32",
            name="ck_study_authority_token_hash",
        ),
        MYSQL_TABLE_OPTIONS,
    )


class StudyProgressContributor(_RetiredBase):
    __tablename__ = "study_progress_contributors"

    id = sa.Column(bigint_pk(), primary_key=True, autoincrement=True)
    subject_id = sa.Column(
        bigint(),
        sa.ForeignKey("study_progress_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_generation = sa.Column(bigint(), nullable=False)
    evidence_kind = sa.Column(
        ascii_string(32),
        nullable=False,
        default="LEGACY_PROJECTION",
        server_default=text("'LEGACY_PROJECTION'"),
    )
    source_progress_id = sa.Column(sa.Integer, nullable=True)
    live_card_progress_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("card_progress.id", ondelete="SET NULL"),
        nullable=True,
    )
    logical_card_key = sa.Column(binary_string(144), nullable=False)
    live_card_id = sa.Column(
        sa.String(36),
        sa.ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
    )
    card_progress_revision = sa.Column(bigint(), nullable=True)
    raw_schema_version = sa.Column(ascii_string(64), nullable=True)
    storage_codec = sa.Column(ascii_string(64), nullable=True)
    raw_payload = sa.Column(sa.JSON(none_as_null=True), nullable=True)
    raw_payload_size = sa.Column(sa.SmallInteger, nullable=True)
    raw_progress_hash = sa.Column(binary_hash(), nullable=True)
    pointer_status = sa.Column(ascii_string(64), nullable=False)
    history_completeness_code = sa.Column(ascii_string(64), nullable=False)
    current_provenance_code = sa.Column(ascii_string(64), nullable=False)
    lineage_vector_hash = sa.Column(binary_hash(), nullable=False)
    contributor_status = sa.Column(ascii_string(32), nullable=False)
    detached_at = sa.Column(datetime6(), nullable=True)
    created_at = sa.Column(datetime6(), nullable=False)
    updated_at = sa.Column(datetime6(), nullable=False)


    __table_args__ = (
        sa.UniqueConstraint("id", "subject_id", name="uq_sp_contributor_id_subject"),
        sa.UniqueConstraint(
            "subject_id",
            "subject_generation",
            "source_progress_id",
            name="uq_sp_contributor_generation_source",
        ),
        sa.UniqueConstraint(
            "live_card_progress_id", name="uq_sp_contributor_live_progress"
        ),
        sa.UniqueConstraint(
            "subject_id",
            "subject_generation",
            "logical_card_key",
            name="uq_sp_contributor_generation_card",
        ),
        sa.Index(
            "ix_sp_contributor_subject_current",
            "subject_id",
            "subject_generation",
            "contributor_status",
            "id",
        ),
        sa.Index("ix_sp_contributor_live_card", "live_card_id", "subject_id"),
        sa.CheckConstraint(
            "subject_generation >= 1", name="ck_sp_contributor_generation"
        ),
        sa.CheckConstraint(
            "card_progress_revision >= 0", name="ck_sp_contributor_revision"
        ),
        sa.CheckConstraint(
            "raw_payload_size BETWEEN 0 AND 16384",
            name="ck_sp_contributor_payload_size",
        ),
        sa.CheckConstraint(
            "length(raw_progress_hash) = 32", name="ck_sp_contributor_raw_hash"
        ),
        sa.CheckConstraint(
            "length(lineage_vector_hash) = 32",
            name="ck_sp_contributor_lineage_hash",
        ),
        sa.CheckConstraint(
            sql_allowlist("pointer_status", POINTER_STATUSES),
            name="ck_sp_contributor_pointer_status",
        ),
        sa.CheckConstraint(
            sql_allowlist(
                "history_completeness_code", HISTORY_COMPLETENESS_CODES
            ),
            name="ck_sp_contributor_history_completeness",
        ),
        sa.CheckConstraint(
            sql_allowlist("current_provenance_code", PROVENANCE_CODES),
            name="ck_sp_contributor_provenance",
        ),
        sa.CheckConstraint(
            sql_allowlist("contributor_status", CONTRIBUTOR_STATUSES),
            name="ck_sp_contributor_status",
        ),
        sa.CheckConstraint(
            sql_allowlist("evidence_kind", EVIDENCE_KINDS),
            name="ck_sp_contributor_evidence_kind",
        ),
        sa.CheckConstraint(
            contributor_evidence_check(), name="ck_sp_contributor_evidence"
        ),
        MYSQL_TABLE_OPTIONS,
    )


register_mysql_parent_collations(
    StudyProgressContributor.__table__,
    {"live_card_id": ("cards", "id")},
)


class StudyProgressAvailability(_RetiredBase):
    __tablename__ = "study_progress_availability"

    contributor_id = sa.Column(bigint(), primary_key=True)
    subject_id = sa.Column(bigint(), nullable=False)
    subject_generation = sa.Column(bigint(), nullable=False)
    projection_version = sa.Column(ascii_string(32), nullable=False)
    normalized_queue = sa.Column(ascii_string(20), nullable=False)
    due_at = sa.Column(datetime6(), nullable=True)
    due_day = sa.Column(sa.Integer, nullable=True)
    is_suspended = sa.Column(
        sa.Boolean, nullable=False, default=False, server_default=text("0")
    )
    is_buried = sa.Column(
        sa.Boolean, nullable=False, default=False, server_default=text("0")
    )
    buried_until_day = sa.Column(sa.Integer, nullable=True)
    card_created_at = sa.Column(datetime6(), nullable=False)
    card_order_key = sa.Column(binary_string(144), nullable=False)
    state_schema_version = sa.Column(ascii_string(64), nullable=False)
    semantic_state_hash = sa.Column(binary_hash(), nullable=False)
    created_at = sa.Column(datetime6(), nullable=False)
    updated_at = sa.Column(datetime6(), nullable=False)


    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["contributor_id", "subject_id"],
            [
                "study_progress_contributors.id",
                "study_progress_contributors.subject_id",
            ],
            name="fk_sp_avail_contributor_subject",
            ondelete="CASCADE",
        ),
        sa.Index(
            "ix_sp_avail_subject_queue_day",
            "subject_id",
            "subject_generation",
            "normalized_queue",
            "is_suspended",
            "is_buried",
            "due_day",
            "due_at",
        ),
        sa.Index(
            "ix_sp_avail_queue_time",
            "normalized_queue",
            "is_suspended",
            "is_buried",
            "due_at",
            "contributor_id",
        ),
        sa.CheckConstraint(
            "subject_generation >= 1", name="ck_sp_avail_generation"
        ),
        sa.CheckConstraint(
            sql_allowlist("normalized_queue", NORMALIZED_QUEUES),
            name="ck_sp_avail_queue",
        ),
        sa.CheckConstraint(
            "length(semantic_state_hash) = 32", name="ck_sp_avail_semantic_hash"
        ),
        MYSQL_TABLE_OPTIONS,
    )


class StudyProgressLineageRef(_RetiredBase):
    __tablename__ = "study_progress_lineage_refs"

    id = sa.Column(bigint_pk(), primary_key=True, autoincrement=True)
    contributor_id = sa.Column(
        bigint(),
        sa.ForeignKey("study_progress_contributors.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_generation = sa.Column(bigint(), nullable=False)
    ref_kind = sa.Column(ascii_string(64), nullable=False)
    source_row_key = sa.Column(binary_string(144), nullable=False)
    source_key = sa.Column(binary_string(1020), nullable=True)
    external_card_id = sa.Column(binary_string(512), nullable=True)
    external_note_id = sa.Column(binary_string(512), nullable=True)
    source_snapshot_hash = sa.Column(binary_hash(), nullable=True)
    source_payload_hash = sa.Column(binary_hash(), nullable=True)
    ref_status = sa.Column(ascii_string(64), nullable=False)
    occurred_at = sa.Column(datetime6(), nullable=True)
    ingested_at = sa.Column(datetime6(), nullable=False)


    __table_args__ = (
        sa.UniqueConstraint(
            "contributor_id",
            "subject_generation",
            "ref_kind",
            "source_row_key",
            name="uq_sp_lineage_ref",
        ),
        sa.Index("ix_sp_lineage_source", "ref_kind", "source_row_key"),
        sa.Index(
            "ix_sp_lineage_contributor_status", "contributor_id", "ref_status", "id"
        ),
        sa.CheckConstraint(
            "subject_generation >= 1", name="ck_sp_lineage_generation"
        ),
        sa.CheckConstraint(
            sql_allowlist("ref_kind", LINEAGE_REF_KINDS),
            name="ck_sp_lineage_kind",
        ),
        sa.CheckConstraint(
            sql_allowlist("ref_status", POINTER_STATUSES),
            name="ck_sp_lineage_status",
        ),
        sa.CheckConstraint(
            "source_snapshot_hash IS NULL OR length(source_snapshot_hash) = 32",
            name="ck_sp_lineage_snapshot_hash",
        ),
        sa.CheckConstraint(
            "source_payload_hash IS NULL OR length(source_payload_hash) = 32",
            name="ck_sp_lineage_payload_hash",
        ),
        MYSQL_TABLE_OPTIONS,
    )
