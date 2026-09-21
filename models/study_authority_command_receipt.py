"""Durable idempotency receipt for one accepted NOTE authority command."""

from __future__ import annotations

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


class StudyAuthorityCommandReceipt(db.Model):
    __tablename__ = "study_authority_command_receipts"

    id = db.Column(bigint_pk(), primary_key=True, autoincrement=True)
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
    logical_note_key = db.Column(binary_string(144), nullable=False)
    subject_generation = db.Column(bigint(), nullable=False)
    enrollment_epoch = db.Column(bigint(), nullable=False)
    operation_key = db.Column(binary_string(512), nullable=False)
    operation_key_hash = db.Column(binary_hash(), nullable=False)
    request_fingerprint = db.Column(binary_hash(), nullable=False)
    authority_revision_before = db.Column(bigint(), nullable=False)
    authority_revision_after = db.Column(bigint(), nullable=False)
    before_state_hash = db.Column(binary_hash(), nullable=False)
    after_state_hash = db.Column(binary_hash(), nullable=False)
    review_event_id = db.Column(
        db.Integer,
        db.ForeignKey("review_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    history_fact_id = db.Column(
        bigint(),
        db.ForeignKey("study_progress_history_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    receipt_schema_version = db.Column(ascii_string(64), nullable=False)
    response_payload = db.Column(db.JSON, nullable=False)
    response_payload_size = db.Column(db.SmallInteger, nullable=False)
    response_payload_hash = db.Column(binary_hash(), nullable=False)
    created_at = db.Column(datetime6(), nullable=False)

    subject = db.relationship("StudyProgressSubject")
    review_event = db.relationship("ReviewEvent")
    history_fact = db.relationship("StudyProgressHistoryFact")

    __table_args__ = (
        db.UniqueConstraint(
            "learner_user_id",
            "operation_key_hash",
            name="uq_study_authority_receipt_operation",
        ),
        db.UniqueConstraint(
            "review_event_id",
            name="uq_study_authority_receipt_event",
        ),
        db.UniqueConstraint(
            "history_fact_id",
            name="uq_study_authority_receipt_history",
        ),
        db.Index(
            "ix_study_authority_receipt_subject_revision",
            "subject_id",
            "subject_generation",
            "authority_revision_after",
        ),
        db.CheckConstraint(
            "length(logical_note_key) BETWEEN 1 AND 144",
            name="ck_study_authority_receipt_note_key",
        ),
        db.CheckConstraint(
            "subject_generation >= 1",
            name="ck_study_authority_receipt_generation",
        ),
        db.CheckConstraint(
            "enrollment_epoch >= 0",
            name="ck_study_authority_receipt_epoch",
        ),
        db.CheckConstraint(
            "length(operation_key) BETWEEN 1 AND 512",
            name="ck_study_authority_receipt_operation_key",
        ),
        db.CheckConstraint(
            "length(operation_key_hash) = 32",
            name="ck_study_authority_receipt_operation_hash",
        ),
        db.CheckConstraint(
            "length(request_fingerprint) = 32",
            name="ck_study_authority_receipt_request_hash",
        ),
        db.CheckConstraint(
            "authority_revision_before >= 0",
            name="ck_study_authority_receipt_revision_before",
        ),
        db.CheckConstraint(
            "authority_revision_after = authority_revision_before + 1",
            name="ck_study_authority_receipt_revision_step",
        ),
        db.CheckConstraint(
            "length(before_state_hash) = 32 AND length(after_state_hash) = 32",
            name="ck_study_authority_receipt_state_hashes",
        ),
        db.CheckConstraint(
            "response_payload_size BETWEEN 0 AND 16384",
            name="ck_study_authority_receipt_payload_size",
        ),
        db.CheckConstraint(
            "length(response_payload_hash) = 32",
            name="ck_study_authority_receipt_payload_hash",
        ),
        MYSQL_TABLE_OPTIONS,
    )
