"""Current usable Algorithm State for one shadow-progress subject."""

from __future__ import annotations

from models import db
from models.study_progress_types import (
    MYSQL_TABLE_OPTIONS,
    ascii_string,
    bigint,
    binary_hash,
    datetime6,
)


class StudyProgressState(db.Model):
    __tablename__ = "study_progress_states"

    subject_id = db.Column(
        bigint(),
        db.ForeignKey("study_progress_subjects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subject_generation = db.Column(bigint(), nullable=False)
    mirror_revision = db.Column(bigint(), nullable=False)
    algorithm_key = db.Column(ascii_string(64), nullable=False)
    algorithm_version = db.Column(ascii_string(32), nullable=False)
    state_schema_version = db.Column(ascii_string(64), nullable=False)
    storage_codec = db.Column(ascii_string(64), nullable=False)
    state_payload = db.Column(db.JSON, nullable=False)
    state_payload_size = db.Column(db.SmallInteger, nullable=False)
    algorithm_state_hash = db.Column(binary_hash(), nullable=False)
    semantic_state_hash = db.Column(binary_hash(), nullable=False)
    created_at = db.Column(datetime6(), nullable=False)
    updated_at = db.Column(datetime6(), nullable=False)

    subject = db.relationship("StudyProgressSubject", back_populates="state")

    __table_args__ = (
        db.Index(
            "ix_sp_state_identity",
            "algorithm_key",
            "algorithm_version",
            "state_schema_version",
        ),
        db.CheckConstraint("subject_generation >= 1", name="ck_sp_state_generation"),
        db.CheckConstraint("mirror_revision >= 0", name="ck_sp_state_revision"),
        db.CheckConstraint(
            "state_payload_size BETWEEN 0 AND 16384", name="ck_sp_state_payload_size"
        ),
        db.CheckConstraint(
            "length(algorithm_state_hash) = 32", name="ck_sp_state_algorithm_hash"
        ),
        db.CheckConstraint(
            "length(semantic_state_hash) = 32", name="ck_sp_state_semantic_hash"
        ),
        MYSQL_TABLE_OPTIONS,
    )
