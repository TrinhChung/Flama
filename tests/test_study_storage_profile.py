"""P9-03b: NOTE storage profile fence (the contributor table it altered is retired, P10-09)."""

from __future__ import annotations

from datetime import datetime
import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
    read_study_authority_route,
    read_study_storage_profile,
)
from models import db
from models.study_authority_enrollment import StudyAuthorityEnrollment
from migrations.retired_note_progress_tables import StudyProgressContributor
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_progress_subject import StudyProgressSubject
from models.user import User


migration = importlib.import_module(
    "migrations.versions.20261001_000047_add_study_storage_profile"
)
NOW = datetime(2026, 10, 1, 1, 2, 3)
RAW = {
    "source_progress_id": 11,
    "card_progress_revision": 0,
    "raw_schema_version": "card-progress-raw.v1",
    "storage_codec": "canonical-json-v1",
    "raw_payload": {"id": 11},
    "raw_payload_size": 9,
    "raw_progress_hash": b"\x11" * 32,
}
NO_RAW = {name: None for name in RAW}


class StudyStorageProfileTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = User(username="profile-learner", email="profile@example.test")
        db.session.add(self.user)
        db.session.flush()
        self.subject = StudyProgressSubject(
            learner_user_id=self.user.id,
            logical_note_key=b"note-1",
            created_at=NOW,
            updated_at=NOW,
        )
        db.session.add(self.subject)
        db.session.commit()
        # Migration 47 altered the (since retired) contributor table.
        StudyProgressContributor.__table__.create(bind=db.engine)

    def tearDown(self):
        op._proxy = None
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _contributor(self, card_key: bytes = b"card-1", **values) -> StudyProgressContributor:
        fields = {
            "subject_id": self.subject.id,
            "subject_generation": 1,
            "logical_card_key": card_key,
            "pointer_status": "ABSENT",
            "history_completeness_code": "HISTORY_NATIVE_COMPLETE",
            "current_provenance_code": "UNKNOWN_LEGACY",
            "lineage_vector_hash": b"\x44" * 32,
            "contributor_status": "ACTIVE",
            "created_at": NOW,
            "updated_at": NOW,
            **RAW,
        }
        fields.update(values)
        return StudyProgressContributor(**fields)

    def _assert_rejected(self, row) -> None:
        db.session.add(row)
        with self.assertRaises(IntegrityError):
            db.session.flush()
        db.session.rollback()

    def _enroll_note(self) -> None:
        db.session.add(StudyAuthorityEnrollment(
            learner_user_id=self.user.id, mode_code="NOTE", epoch=1,
            created_at=NOW, updated_at=NOW,
        ))
        db.session.commit()

    def _set_profile(self, profile_code: str) -> None:
        row = db.session.get(StudyAuthorityStorageProfile, 1)
        if row is None:
            row = StudyAuthorityStorageProfile(id=1, created_at=NOW, updated_at=NOW)
            db.session.add(row)
        row.profile_code = profile_code
        db.session.commit()

    @staticmethod
    def _bind(connection):
        op._proxy = Operations(MigrationContext.configure(connection))

    def test_absent_profile_row_means_a_fresh_consolidated_install(self):
        self._enroll_note()
        self.assertEqual(read_study_storage_profile(db.session), "CONSOLIDATED_V1")
        route = lock_study_authority_route(
            db.session, learner_user_id=self.user.id, allow_note_authority=True
        )
        self.assertEqual((route.mode_code, route.storage_profile), ("NOTE", "CONSOLIDATED_V1"))
        db.session.rollback()

    def test_release_refuses_note_routes_under_an_unsupported_profile(self):
        self._enroll_note()
        # A database still on a profile retired by P10-09 fails closed.
        self._set_profile("CANONICAL_V1")
        for resolve in (
            lambda: lock_study_authority_route(
                db.session, learner_user_id=self.user.id, allow_note_authority=True
            ),
            lambda: read_study_authority_route(db.session, learner_user_id=self.user.id),
        ):
            with self.assertRaises(StudyAuthorityFenceError) as raised:
                resolve()
            self.assertEqual(raised.exception.code, "STORAGE_PROFILE_UNSUPPORTED")
            db.session.rollback()

    def test_missing_enrollment_requires_migration_even_under_an_old_profile(self):
        self._set_profile("CANONICAL_V1")
        with self.assertRaises(StudyAuthorityFenceError) as raised:
            lock_study_authority_route(db.session, learner_user_id=self.user.id)
        self.assertEqual(raised.exception.code, "STUDY_AUTHORITY_MIGRATION_REQUIRED")
        db.session.rollback()

    def test_profile_row_is_a_checked_singleton(self):
        self._set_profile("PROJECTION_V1")
        self._assert_rejected(StudyAuthorityStorageProfile(id=2, created_at=NOW, updated_at=NOW))
        row = db.session.get(StudyAuthorityStorageProfile, 1)
        row.profile_code = "LEGACY"
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_migration_seeds_projection_and_guards_downgrade(self):
        with db.engine.begin() as connection:
            self._bind(connection)
            migration.upgrade()
            migration.upgrade()
        self.assertEqual(
            db.session.execute(sa.text(
                "SELECT profile_code, epoch FROM study_authority_storage_profile"
            )).all(),
            [("PROJECTION_V1", 1)],
        )

        self._set_profile("CANONICAL_V1")
        with self.assertRaisesRegex(RuntimeError, "CANONICAL_V1"):
            with db.engine.begin() as connection:
                self._bind(connection)
                migration.downgrade()
        self._set_profile("PROJECTION_V1")

        db.session.add(self._contributor(evidence_kind="CANONICAL", **NO_RAW))
        db.session.commit()
        with self.assertRaisesRegex(RuntimeError, "no CardProgress evidence"):
            with db.engine.begin() as connection:
                self._bind(connection)
                migration.downgrade()
        db.session.execute(sa.text("DELETE FROM study_progress_contributors"))
        db.session.commit()

        db.session.remove()
        with db.engine.begin() as connection:
            self._bind(connection)
            migration.downgrade()
            migration.downgrade()
        self.assertFalse(sa.inspect(db.engine).has_table("study_authority_storage_profile"))
        with db.engine.begin() as connection:
            self._bind(connection)
            migration.upgrade()
        self.assertEqual(read_study_storage_profile(db.session), "PROJECTION_V1")


if __name__ == "__main__":
    unittest.main()
