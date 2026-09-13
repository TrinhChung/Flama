"""Learner/Note coordination envelope for Phase 4 shadow progress."""

from __future__ import annotations

from sqlalchemy import text

from app.services.study_progress_contract import SUBJECT_STATUSES, sql_allowlist
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


class StudyProgressSubject(db.Model):
    __tablename__ = "study_progress_subjects"

    id = db.Column(bigint_pk(), primary_key=True, autoincrement=True)
    learner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    logical_note_key = db.Column(binary_string(144), nullable=False)
    live_note_id = db.Column(
        db.String(36),
        db.ForeignKey("notes.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject_generation = db.Column(
        bigint(), nullable=False, default=1, server_default=text("1")
    )
    mirror_revision = db.Column(
        bigint(), nullable=False, default=0, server_default=text("0")
    )
    status_code = db.Column(
        ascii_string(64),
        nullable=False,
        default="NO_CURRENT_PROGRESS",
        server_default=text("'NO_CURRENT_PROGRESS'"),
    )
    contributor_count = db.Column(
        db.Integer, nullable=False, default=0, server_default=text("0")
    )
    authority_vector_hash = db.Column(binary_hash(), nullable=True)
    lineage_vector_hash = db.Column(binary_hash(), nullable=True)
    mapper_version = db.Column(ascii_string(32), nullable=True)
    last_mirrored_at = db.Column(datetime6(), nullable=True)
    created_at = db.Column(datetime6(), nullable=False)
    updated_at = db.Column(datetime6(), nullable=False)

    state = db.relationship(
        "StudyProgressState",
        back_populates="subject",
        uselist=False,
        passive_deletes="all",
    )
    contributors = db.relationship(
        "StudyProgressContributor",
        back_populates="subject",
        passive_deletes="all",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "learner_user_id", "logical_note_key", name="uq_sp_subject_user_note"
        ),
        db.Index("ix_sp_subject_live_note", "live_note_id"),
        db.Index("ix_sp_subject_status_updated", "status_code", "updated_at", "id"),
        db.CheckConstraint("subject_generation >= 1", name="ck_sp_subject_generation"),
        db.CheckConstraint("mirror_revision >= 0", name="ck_sp_subject_revision"),
        db.CheckConstraint("contributor_count >= 0", name="ck_sp_subject_count"),
        db.CheckConstraint(
            "authority_vector_hash IS NULL OR length(authority_vector_hash) = 32",
            name="ck_sp_subject_authority_hash",
        ),
        db.CheckConstraint(
            "lineage_vector_hash IS NULL OR length(lineage_vector_hash) = 32",
            name="ck_sp_subject_lineage_hash",
        ),
        db.CheckConstraint(
            sql_allowlist("status_code", SUBJECT_STATUSES),
            name="ck_sp_subject_status",
        ),
        MYSQL_TABLE_OPTIONS,
    )
