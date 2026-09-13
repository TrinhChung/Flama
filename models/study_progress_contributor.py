"""Detached-safe source CardProgress evidence for a learner/Note subject."""

from __future__ import annotations

from app.services.study_progress_contract import (
    CONTRIBUTOR_STATUSES,
    HISTORY_COMPLETENESS_CODES,
    POINTER_STATUSES,
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
    register_mysql_parent_collations,
)


class StudyProgressContributor(db.Model):
    __tablename__ = "study_progress_contributors"

    id = db.Column(bigint_pk(), primary_key=True, autoincrement=True)
    subject_id = db.Column(
        bigint(),
        db.ForeignKey("study_progress_subjects.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_generation = db.Column(bigint(), nullable=False)
    source_progress_id = db.Column(db.Integer, nullable=False)
    live_card_progress_id = db.Column(
        db.Integer,
        db.ForeignKey("card_progress.id", ondelete="SET NULL"),
        nullable=True,
    )
    logical_card_key = db.Column(binary_string(144), nullable=False)
    live_card_id = db.Column(
        db.String(36),
        db.ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
    )
    card_progress_revision = db.Column(bigint(), nullable=False)
    raw_schema_version = db.Column(ascii_string(64), nullable=False)
    storage_codec = db.Column(ascii_string(64), nullable=False)
    raw_payload = db.Column(db.JSON, nullable=False)
    raw_payload_size = db.Column(db.SmallInteger, nullable=False)
    raw_progress_hash = db.Column(binary_hash(), nullable=False)
    pointer_status = db.Column(ascii_string(64), nullable=False)
    history_completeness_code = db.Column(ascii_string(64), nullable=False)
    current_provenance_code = db.Column(ascii_string(64), nullable=False)
    lineage_vector_hash = db.Column(binary_hash(), nullable=False)
    contributor_status = db.Column(ascii_string(32), nullable=False)
    detached_at = db.Column(datetime6(), nullable=True)
    created_at = db.Column(datetime6(), nullable=False)
    updated_at = db.Column(datetime6(), nullable=False)

    subject = db.relationship("StudyProgressSubject", back_populates="contributors")
    availability = db.relationship(
        "StudyProgressAvailability",
        back_populates="contributor",
        uselist=False,
        passive_deletes="all",
    )
    lineage_refs = db.relationship(
        "StudyProgressLineageRef",
        back_populates="contributor",
        passive_deletes="all",
    )

    __table_args__ = (
        db.UniqueConstraint("id", "subject_id", name="uq_sp_contributor_id_subject"),
        db.UniqueConstraint(
            "subject_id",
            "subject_generation",
            "source_progress_id",
            name="uq_sp_contributor_generation_source",
        ),
        db.UniqueConstraint(
            "live_card_progress_id", name="uq_sp_contributor_live_progress"
        ),
        db.Index(
            "ix_sp_contributor_subject_current",
            "subject_id",
            "subject_generation",
            "contributor_status",
            "id",
        ),
        db.Index("ix_sp_contributor_live_card", "live_card_id", "subject_id"),
        db.CheckConstraint(
            "subject_generation >= 1", name="ck_sp_contributor_generation"
        ),
        db.CheckConstraint(
            "card_progress_revision >= 0", name="ck_sp_contributor_revision"
        ),
        db.CheckConstraint(
            "raw_payload_size BETWEEN 0 AND 16384",
            name="ck_sp_contributor_payload_size",
        ),
        db.CheckConstraint(
            "length(raw_progress_hash) = 32", name="ck_sp_contributor_raw_hash"
        ),
        db.CheckConstraint(
            "length(lineage_vector_hash) = 32",
            name="ck_sp_contributor_lineage_hash",
        ),
        db.CheckConstraint(
            sql_allowlist("pointer_status", POINTER_STATUSES),
            name="ck_sp_contributor_pointer_status",
        ),
        db.CheckConstraint(
            sql_allowlist(
                "history_completeness_code", HISTORY_COMPLETENESS_CODES
            ),
            name="ck_sp_contributor_history_completeness",
        ),
        db.CheckConstraint(
            sql_allowlist("current_provenance_code", PROVENANCE_CODES),
            name="ck_sp_contributor_provenance",
        ),
        db.CheckConstraint(
            sql_allowlist("contributor_status", CONTRIBUTOR_STATUSES),
            name="ck_sp_contributor_status",
        ),
        MYSQL_TABLE_OPTIONS,
    )


register_mysql_parent_collations(
    StudyProgressContributor.__table__,
    {"live_card_id": ("cards", "id")},
)
