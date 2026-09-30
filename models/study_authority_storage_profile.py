"""System-wide NOTE storage profile (ADR P9-03 §2.1, migration 47).

A single row (``id = 1``). ``PROJECTION_V1`` keeps writing the legacy
``card_progress`` projection; ``CANONICAL_V1`` stops it. Every NOTE route
fence reads this row with a shared lock, so the switch (exclusive lock, in a
write freeze) waits for writers that started under the old profile. No row
means ``PROJECTION_V1``: it is only absent before migration 47.
"""

from __future__ import annotations

from sqlalchemy import text

from app.services.study_progress_contract import (
    DEFAULT_STORAGE_PROFILE,
    STORAGE_PROFILES,
    sql_allowlist,
)
from models import db
from models.study_progress_types import MYSQL_TABLE_OPTIONS, ascii_string, bigint, datetime6


class StudyAuthorityStorageProfile(db.Model):
    __tablename__ = "study_authority_storage_profile"

    id = db.Column(db.SmallInteger, primary_key=True, autoincrement=False)
    profile_code = db.Column(
        ascii_string(32),
        nullable=False,
        default=DEFAULT_STORAGE_PROFILE,
        server_default=text(f"'{DEFAULT_STORAGE_PROFILE}'"),
    )
    epoch = db.Column(bigint(), nullable=False, default=1, server_default=text("1"))
    switched_at = db.Column(datetime6(), nullable=True)
    created_at = db.Column(datetime6(), nullable=False)
    updated_at = db.Column(datetime6(), nullable=False)

    __table_args__ = (
        db.CheckConstraint("id = 1", name="ck_study_storage_profile_singleton"),
        db.CheckConstraint(
            sql_allowlist("profile_code", STORAGE_PROFILES),
            name="ck_study_storage_profile_code",
        ),
        db.CheckConstraint("epoch >= 1", name="ck_study_storage_profile_epoch"),
        MYSQL_TABLE_OPTIONS,
    )
