"""Independent Note authority revision, without repurposing Phase 4 counters."""

from __future__ import annotations

from sqlalchemy import text

from models import db
from models.study_progress_types import MYSQL_TABLE_OPTIONS, bigint, binary_hash, datetime6


class StudyAuthoritySubjectToken(db.Model):
    __tablename__ = "study_authority_subject_tokens"

    subject_id = db.Column(
        bigint(),
        db.ForeignKey("study_progress_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_generation = db.Column(bigint(), nullable=False)
    authority_revision = db.Column(
        bigint(), nullable=False, default=0, server_default=text("0")
    )
    semantic_state_hash = db.Column(binary_hash(), nullable=True)
    created_at = db.Column(datetime6(), nullable=False)
    updated_at = db.Column(datetime6(), nullable=False)

    __table_args__ = (
        db.CheckConstraint(
            "subject_generation >= 1", name="ck_study_authority_token_generation"
        ),
        db.CheckConstraint(
            "authority_revision >= 0", name="ck_study_authority_token_revision"
        ),
        db.CheckConstraint(
            "semantic_state_hash IS NULL OR length(semantic_state_hash) = 32",
            name="ck_study_authority_token_hash",
        ),
        MYSQL_TABLE_OPTIONS,
    )
