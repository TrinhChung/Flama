"""Frozen NOTE authority identity for one session Card membership."""

from __future__ import annotations

from models import db
from models.study_progress_types import (
    MYSQL_TABLE_OPTIONS,
    ascii_string,
    bigint,
    binary_hash,
    binary_string,
    datetime6,
)


class StudySessionAuthorityPin(db.Model):
    __tablename__ = "study_session_authority_pins"

    session_card_id = db.Column(
        db.Integer,
        db.ForeignKey("study_session_cards.id", ondelete="CASCADE"),
        primary_key=True,
    )
    learner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id = db.Column(
        bigint(),
        db.ForeignKey("study_progress_subjects.id", ondelete="SET NULL"),
        nullable=True,
    )
    mode_code = db.Column(ascii_string(16), nullable=False)
    enrollment_epoch = db.Column(bigint(), nullable=False)
    logical_note_key = db.Column(binary_string(144), nullable=False)
    subject_generation = db.Column(bigint(), nullable=False)
    base_authority_revision = db.Column(bigint(), nullable=False)
    base_semantic_state_hash = db.Column(binary_hash(), nullable=False)
    wire_schema_version = db.Column(ascii_string(32), nullable=False)
    created_at = db.Column(datetime6(), nullable=False)

    session_card = db.relationship(
        "StudySessionCard",
        back_populates="authority_pin",
    )
    subject = db.relationship("StudyProgressSubject")

    __table_args__ = (
        db.Index(
            "ix_study_session_authority_pin_subject",
            "learner_user_id",
            "logical_note_key",
            "enrollment_epoch",
        ),
        db.CheckConstraint(
            "mode_code = 'NOTE'",
            name="ck_study_session_authority_pin_mode",
        ),
        db.CheckConstraint(
            "enrollment_epoch >= 1",
            name="ck_study_session_authority_pin_epoch",
        ),
        db.CheckConstraint(
            "length(logical_note_key) BETWEEN 1 AND 144",
            name="ck_study_session_authority_pin_note_key",
        ),
        db.CheckConstraint(
            "subject_generation >= 1",
            name="ck_study_session_authority_pin_generation",
        ),
        db.CheckConstraint(
            "base_authority_revision >= 0",
            name="ck_study_session_authority_pin_revision",
        ),
        db.CheckConstraint(
            "length(base_semantic_state_hash) = 32",
            name="ck_study_session_authority_pin_state_hash",
        ),
        db.CheckConstraint(
            "wire_schema_version = 'study-session.v4'",
            name="ck_study_session_authority_pin_wire",
        ),
        MYSQL_TABLE_OPTIONS,
    )
