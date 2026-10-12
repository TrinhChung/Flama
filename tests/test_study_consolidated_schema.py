"""P10-02: the consolidated NOTE progress columns on study_progress_subjects (migration 49)."""

from __future__ import annotations

from datetime import datetime
import importlib
import unittest

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.services.study_progress_contract import (
    STORAGE_PROFILES,
    SUBJECT_PROGRESS_COLUMNS,
    subject_progress_checks,
)
from models import db
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_progress_subject import StudyProgressSubject
from models.user import User

NOW = datetime(2026, 10, 3, 9, 0, 0)
FULL_PROGRESS = {
    "algorithm_key": "legacy-anki",
    "algorithm_version": "1.0.0",
    "state_schema_version": "anki-card-state.v1",
    "storage_codec": "flama-canonical-state-json.v1",
    "state_payload": {"type": "new"},
    "state_payload_size": 15,
    "algorithm_state_hash": b"a" * 32,
    "semantic_state_hash": b"s" * 32,
    "projection_version": "availability-anchor.v1",
    "normalized_queue": "new",
    "is_suspended": False,
    "is_buried": False,
    "history_completeness_code": "HISTORY_NATIVE_COMPLETE",
    "current_provenance_code": "NATIVE_SESSION",
}


class StudyConsolidatedSchemaTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        db.session.add(User(id=1, username="learner", email="learner@example.test"))
        db.session.commit()

    def tearDown(self):
        from alembic import op

        op._proxy = None
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _subject(self, key: bytes = b"note-1", **values) -> StudyProgressSubject:
        return StudyProgressSubject(learner_user_id=1, logical_note_key=key, created_at=NOW, updated_at=NOW, **values)

    def _run(self, step):
        from alembic import op
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        migration = importlib.import_module("migrations.versions.20261003_000049_consolidate_note_progress_row")
        db.session.remove()
        with db.engine.begin() as connection:
            op._proxy = Operations(MigrationContext.configure(connection))
            getattr(migration, step)()

    def _columns(self):
        return {column["name"] for column in sa.inspect(db.engine).get_columns("study_progress_subjects")}

    def test_profile_allowlist_names_the_consolidated_profile(self):
        self.assertEqual(STORAGE_PROFILES, ("PROJECTION_V1", "CANONICAL_V1", "CONSOLIDATED_V1"))
        db.session.add(StudyAuthorityStorageProfile(id=1, profile_code="CONSOLIDATED_V1", created_at=NOW, updated_at=NOW))
        db.session.commit()

    def test_a_row_holds_the_whole_progress_or_none_of_it(self):
        db.session.add(self._subject())
        db.session.add(self._subject(b"note-2", authority_revision=3, due_day=12, **FULL_PROGRESS))
        db.session.commit()
        for missing in SUBJECT_PROGRESS_COLUMNS:
            with self.subTest(missing=missing):
                partial = {key: value for key, value in FULL_PROGRESS.items() if key != missing}
                db.session.add(self._subject(b"partial", **partial))
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()
        db.session.add(self._subject(b"orphan-due", due_day=3))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    def test_value_checks(self):
        for name, values in (
            ("ck_sp_subject_queue", {"normalized_queue": "archived"}),
            ("ck_sp_subject_semantic_hash", {"semantic_state_hash": b"short"}),
            ("ck_sp_subject_history_code", {"history_completeness_code": "HISTORY_INVENTED"}),
            ("ck_sp_subject_provenance_code", {"current_provenance_code": "SOMEWHERE"}),
            ("ck_sp_subject_state_size", {"state_payload_size": 20000}),
        ):
            with self.subTest(check=name):
                db.session.add(self._subject(b"bad", **{**FULL_PROGRESS, **values}))
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()
        db.session.add(self._subject(b"negative", authority_revision=-1))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        self.assertEqual(
            set(subject_progress_checks()) - {
                c.name for c in StudyProgressSubject.__table__.constraints if isinstance(c, sa.CheckConstraint)
            },
            set(),
        )

    def test_upgrade_is_idempotent_and_downgrade_refuses_consolidated_progress(self):
        # Reverse the later due-index migration before exercising revision 49.
        # Its queue columns do not exist in the historical pre-49 schema.
        next(index for index in StudyProgressSubject.__table__.indexes
             if index.name == "ix_sp_subject_note_due").drop(db.engine)
        self._run("upgrade")
        self.assertTrue(set(SUBJECT_PROGRESS_COLUMNS) | {"authority_revision"} <= self._columns())
        db.session.add(self._subject(authority_revision=1, **FULL_PROGRESS))
        db.session.commit()
        with self.assertRaisesRegex(RuntimeError, "consolidated NOTE progress"):
            self._run("downgrade")
        db.session.execute(sa.delete(StudyProgressSubject))
        db.session.add(StudyAuthorityStorageProfile(id=1, profile_code="CONSOLIDATED_V1", created_at=NOW, updated_at=NOW))
        db.session.commit()
        with self.assertRaisesRegex(RuntimeError, "profile is CONSOLIDATED_V1"):
            self._run("downgrade")
        db.session.execute(sa.update(StudyAuthorityStorageProfile).values(profile_code="CANONICAL_V1"))
        db.session.commit()
        self._run("downgrade")
        self.assertFalse({"state_payload", "authority_revision", "normalized_queue"} & self._columns())
        self._run("upgrade")
        self.assertIn("current_provenance_code", self._columns())


if __name__ == "__main__":
    unittest.main()
