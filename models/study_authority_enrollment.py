"""Persisted learner-level authority fence for the Phase 5 cutover.

Migration 40 initially permitted only LEGACY rows. Migration 43 admits NOTE
with a positive epoch; no row still means LEGACY, epoch zero.
"""

from __future__ import annotations

from sqlalchemy import text

from models import db
from models.study_progress_types import MYSQL_TABLE_OPTIONS, ascii_string, bigint, datetime6


class StudyAuthorityEnrollment(db.Model):
    __tablename__ = "study_authority_enrollments"

    learner_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    mode_code = db.Column(
        ascii_string(16), nullable=False, default="LEGACY", server_default=text("'LEGACY'")
    )
    epoch = db.Column(bigint(), nullable=False, default=0, server_default=text("0"))
    created_at = db.Column(datetime6(), nullable=False)
    updated_at = db.Column(datetime6(), nullable=False)

    __table_args__ = (
        db.CheckConstraint(
            "mode_code IN ('LEGACY','NOTE')",
            name="ck_study_authority_mode",
        ),
        db.CheckConstraint(
            "(mode_code = 'LEGACY' AND epoch >= 0) OR "
            "(mode_code = 'NOTE' AND epoch >= 1)",
            name="ck_study_authority_mode_epoch",
        ),
        MYSQL_TABLE_OPTIONS,
    )
