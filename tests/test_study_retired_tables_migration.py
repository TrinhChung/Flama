"""P10-09: migration 50 drops the five retired NOTE progress tables, keeping history."""

from __future__ import annotations

from datetime import datetime
import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app import create_app
from migrations.retired_note_progress_tables import RETIRED_METADATA
from models import db
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_progress_subject import StudyProgressSubject
from models.user import User

migration = importlib.import_module("migrations.versions.20261003_000050_drop_retired_note_progress_tables")
NOW = datetime(2026, 10, 3, 12, 0, 0)


class RetiredNoteProgressTablesMigrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self._create_retired_tables()
        db.session.add(User(id=1, username="learner", email="learner@example.test"))
        db.session.flush()
        subject = StudyProgressSubject(learner_user_id=1, logical_note_key=b"note-1", created_at=NOW, updated_at=NOW)
        db.session.add(subject)
        db.session.flush()
        self.subject_id = int(subject.id)
        db.session.execute(sa.text(
            "INSERT INTO study_authority_subject_tokens (subject_id, subject_generation, authority_revision, "
            "created_at, updated_at) VALUES (:subject, 1, 3, :now, :now)"), {"subject": self.subject_id, "now": NOW})
        # A pre-P10 fact keeps the id of the contributor it was written for.
        db.session.execute(sa.text(
            "INSERT INTO study_progress_history_facts (learner_user_id, subject_id, contributor_id, "
            "logical_card_key, fact_identity_hash, history_schema_version, storage_codec, occurred_at, "
            "ingested_at, provenance_code, history_completeness_code, fact_payload, fact_payload_size, "
            "fact_payload_hash, created_at) VALUES (1, :subject, 7, 'card-1', :hash, 'v1', 'c', :now, :now, "
            "'NATIVE_DIRECT', 'HISTORY_NATIVE_COMPLETE', '{}', 2, :hash, :now)"),
            {"subject": self.subject_id, "hash": b"h" * 32, "now": NOW})
        db.session.commit()

    def tearDown(self):
        op._proxy = None
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @staticmethod
    def _create_retired_tables():
        RETIRED_METADATA.create_all(bind=db.engine, tables=[
            RETIRED_METADATA.tables[name] for name in reversed(migration.TABLES)])

    @staticmethod
    def _run(step):
        db.session.remove()
        with db.engine.begin() as connection:
            op._proxy = Operations(MigrationContext.configure(connection))
            getattr(migration, step)()

    @staticmethod
    def _tables():
        return set(sa.inspect(db.engine).get_table_names())

    def _set_profile(self, code):
        db.session.add(StudyAuthorityStorageProfile(id=1, profile_code=code, epoch=3, created_at=NOW, updated_at=NOW))
        db.session.commit()

    def test_upgrade_drops_the_retired_tables_and_keeps_history_and_rows(self):
        self._set_profile("CONSOLIDATED_V1")
        self._run("upgrade")
        self.assertFalse(self._tables() & set(migration.TABLES))
        self.assertEqual(db.session.execute(sa.text(
            "SELECT contributor_id FROM study_progress_history_facts")).scalar_one(), 7)
        self.assertEqual(StudyProgressSubject.query.count(), 1)
        self._run("upgrade")  # idempotent

    def test_a_fresh_install_without_a_profile_row_drops_them_too(self):
        self._run("upgrade")
        self.assertFalse(self._tables() & set(migration.TABLES))

    def test_upgrade_refuses_an_older_profile_whose_tables_hold_rows(self):
        for code in ("PROJECTION_V1", "CANONICAL_V1"):
            with self.subTest(profile=code):
                db.session.query(StudyAuthorityStorageProfile).delete()
                db.session.commit()
                self._set_profile(code)
                # The token row is progress the older profile still owns.
                with self.assertRaisesRegex(RuntimeError, f"{code} and they hold 1 rows"):
                    self._run("upgrade")
                self.assertTrue(set(migration.TABLES) <= self._tables())
                self.assertEqual(db.session.get(StudyAuthorityStorageProfile, 1).profile_code, code)

    def test_a_fresh_chain_seeded_on_projection_with_empty_tables_is_promoted(self):
        # Migration 47 seeds PROJECTION_V1 on every fresh chain; nothing was ever stored.
        db.session.execute(sa.text("DELETE FROM study_authority_subject_tokens"))
        db.session.commit()
        self._set_profile("PROJECTION_V1")
        self._run("upgrade")
        self.assertFalse(self._tables() & set(migration.TABLES))
        profile = db.session.get(StudyAuthorityStorageProfile, 1)
        self.assertEqual((profile.profile_code, profile.epoch), ("CONSOLIDATED_V1", 4))
        self.assertIsNotNone(profile.switched_at)

    def test_downgrade_requires_the_dump_to_be_restored_first(self):
        self._set_profile("CONSOLIDATED_V1")
        self._run("upgrade")
        with self.assertRaisesRegex(RuntimeError, "restore the P10-09 dump"):
            self._run("downgrade")
        # Restoring the dump recreates the tables; downgrade then succeeds.
        self._create_retired_tables()
        self._run("downgrade")
        self.assertTrue(set(migration.TABLES) <= self._tables())


if __name__ == "__main__":
    unittest.main()
