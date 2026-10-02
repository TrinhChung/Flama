"""P9-05d: Anki/Connect progress snapshots under CANONICAL_V1 fence on the authority revision."""

from __future__ import annotations

from datetime import datetime
import re
import unittest
from unittest import mock
from uuid import uuid4

from sqlalchemy import event

# Import the app (through the Anki tests) before any model module.
from tests import test_anki_import_api as anki_tests  # noqa: I001
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.connect_source_card_ref import ConnectSourceCardRef
from models.note import Note
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.template import Template

BOTH_PROFILES = frozenset({"PROJECTION_V1", "CANONICAL_V1"})
_TABLE = re.compile(r"\bcard_progress\b", re.IGNORECASE)
SNAPSHOT_A = {
    "externalNoteId": 3101, "sourceCardId": 4101, "ord": 0, "snapshotHash": "a" * 64,
    "baseSnapshotHash": None, "type": 2, "queue": 2, "due": 50003, "sourceToday": 50000,
    "interval": 14, "factor": 2500, "reps": 2, "lapses": 1, "left": 0,
}


class StudyCanonicalConnectTests(unittest.TestCase):
    setUp = anki_tests.AnkiImportApiTests.setUp
    tearDown = anki_tests.AnkiImportApiTests.tearDown
    _login = anki_tests.AnkiImportApiTests._login
    _session_payload = anki_tests.AnkiImportApiTests._session_payload
    _create_session = anki_tests.AnkiImportApiTests._create_session
    _upload_package = anki_tests.AnkiImportApiTests._upload_package

    def _prepare_note_learner(self):
        self.app.config["STUDY_PROGRESS_SHADOW_WRITE_ENABLED"] = True
        self._login()
        self.session_id = self._create_session()["importSessionId"]
        imported = self._upload_package(self.session_id, "cards", 0, [{
            "ankiNoteId": 3101, "sourceModelId": "anki-model-1", "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox", "contentHash": "3" * 64,
            "note": {"deckName": "Inbox", "modelName": self.note_type_id,
                     "fields": {"Word": "authority", "Meaning": "snapshot"}, "tags": []},
        }])
        self.assertTrue(imported["results"][0]["imported"])
        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.admin_id).one()
            template = Template(note_type_id=note.note_type_id, name="Authority sibling",
                                front_html="{{Meaning}}", back_html="{{Word}}", position=1)
            db.session.add(template)
            db.session.flush()
            db.session.add(Card(note_id=note.id, template_id=template.id))
            db.session.flush()
            stage_note_authority_enrollment(db.session, learner_user_id=self.admin_id,
                                            now_utc=datetime(2026, 9, 23, 9, 0, 0))
            # The switch: profile CANONICAL_V1, projection frozen (here: gone).
            db.session.add(StudyAuthorityStorageProfile(
                id=1, profile_code="CANONICAL_V1", created_at=datetime(2026, 10, 2), updated_at=datetime(2026, 10, 2)))
            db.session.execute(CardProgress.__table__.delete())
            db.session.commit()
            self.card_id = Card.query.order_by(Card.id).first().id
            self.deck_id = note.deck_id
            engine = db.engine
        self.statements = []

        def record(_conn, _cursor, statement, *_args):
            if _TABLE.search(statement) and not statement.lstrip().upper().startswith("DELETE"):
                self.statements.append(statement.split()[0].upper())

        event.listen(engine, "before_cursor_execute", record)
        self.addCleanup(lambda: event.remove(engine, "before_cursor_execute", record))

    def _sync(self, sequence, **changes):
        return self._upload_package(self.session_id, "progress", sequence, [{**SNAPSHOT_A, **changes}])["results"][0]

    def _ref(self):
        return ConnectSourceCardRef.query.filter_by(user_id=self.admin_id, external_card_id="4101").one()

    def test_snapshots_fence_on_the_authority_revision_without_card_progress(self):
        with mock.patch("app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", BOTH_PROFILES):
            self._prepare_note_learner()
            first = self._sync(0)
            self.assertEqual((first["state"], first["code"]), ("applied", "PROGRESS_APPLIED"))
            with self.app.app_context():
                token = StudyAuthoritySubjectToken.query.one()
                state = StudyProgressState.query.one()
                self.assertEqual(int(token.authority_revision), 1)
                self.assertEqual(state.state_payload["scheduler_mode"], "anki")
                self.assertEqual(bytes(token.semantic_state_hash), bytes(state.semantic_state_hash))
                active = StudyProgressContributor.query.filter_by(contributor_status="ACTIVE").all()
                self.assertEqual({row.current_provenance_code for row in active}, {"CONNECT_PROGRESS_SNAPSHOT"})
                self.assertEqual({row.history_completeness_code for row in active}, {"HISTORY_MIXED_PARTIAL"})
                ref = self._ref()
                self.assertEqual((ref.applied_local_revision_state, ref.applied_authority_revision), ("AUTHORITY", 1))

            # Same scheduling, new snapshot hash: confirmed, no material write.
            replay = self._sync(1, snapshotHash="e" * 64, baseSnapshotHash="a" * 64)
            self.assertEqual((replay["state"], replay["code"]), ("applied", "PROGRESS_APPLIED"))
            with self.app.app_context():
                self.assertEqual(int(StudyAuthoritySubjectToken.query.one().authority_revision), 1)

            # The learner studies in Flama: the next Anki change is a local conflict.
            answered = self.client.post(f"/api/study/{self.card_id}/answer", json={
                "rating": "good", "operation_key": str(uuid4()), "duration_ms": 500,
                "scope": "deck", "scope_id": self.deck_id})
            self.assertEqual(answered.status_code, 200, answered.get_json())
            conflict = self._sync(2, snapshotHash="c" * 64, baseSnapshotHash="e" * 64, interval=30)
            self.assertEqual((conflict["state"], conflict["code"]), ("local_conflict", "LOCAL_PROGRESS_CHANGED"))
            with self.app.app_context():
                self.assertEqual(int(StudyAuthoritySubjectToken.query.one().authority_revision), 2)

            forced = self._sync(3, snapshotHash="c" * 64, baseSnapshotHash="e" * 64, interval=30, force=True)
            self.assertEqual((forced["state"], forced["code"]), ("applied", "FORCED_PROGRESS_APPLIED"))
            with self.app.app_context():
                self.assertEqual(int(StudyAuthoritySubjectToken.query.one().authority_revision), 3)
                self.assertEqual(self._ref().applied_authority_revision, 3)

                # A projection-era ref the switch could not map.
                ref = self._ref()
                ref.applied_local_revision_state = "NEEDS_CONFIRMATION"
                ref.applied_authority_revision = None
                db.session.commit()
            different = self._sync(4, snapshotHash="d" * 64, baseSnapshotHash="c" * 64, interval=40)
            self.assertEqual((different["state"], different["code"]), ("local_conflict", "LOCAL_PROGRESS_CHANGED"))
            matching = self._sync(5, snapshotHash="f" * 64, baseSnapshotHash="c" * 64, interval=30)
            self.assertEqual((matching["state"], matching["code"]), ("applied", "PROGRESS_APPLIED"))
            with self.app.app_context():
                ref = self._ref()
                self.assertEqual((ref.applied_local_revision_state, ref.applied_authority_revision), ("AUTHORITY", 3))
                self.assertEqual(int(StudyAuthoritySubjectToken.query.one().authority_revision), 3)
                seen = list(self.statements)
                self.assertEqual(CardProgress.query.count(), 0)
        self.assertEqual(seen, [])


if __name__ == "__main__":
    unittest.main()


class ConnectAuthorityFenceMigrationTests(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                               "STARTUP_RUN_MAINTENANCE": False})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        from alembic import op

        op._proxy = None
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _run(self, step):
        import importlib

        from alembic import op
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        migration = importlib.import_module("migrations.versions.20261002_000048_add_connect_authority_fence")
        db.session.remove()
        with db.engine.begin() as connection:
            op._proxy = Operations(MigrationContext.configure(connection))
            getattr(migration, step)()

    def _columns(self):
        import sqlalchemy as sa

        return {column["name"] for column in sa.inspect(db.engine).get_columns("connect_source_card_refs")}

    def test_upgrade_is_idempotent_and_downgrade_keeps_fences(self):
        import sqlalchemy as sa

        self._run("upgrade")
        self.assertIn("applied_authority_revision", self._columns())
        from models.user import User

        db.session.execute(sa.insert(User), [{"id": 1, "username": "u", "email": "u@example.test"}])
        db.session.execute(sa.text(
            "INSERT INTO connect_source_card_refs (id, user_id, source_key, external_card_id, external_note_id, "
            "source_ord, applied_authority_revision, applied_local_revision_state, created_at, updated_at) VALUES "
            "('r', 1, 's', '1', '1', 0, 2, 'AUTHORITY', '2026-10-02', '2026-10-02')"))
        db.session.commit()
        with self.assertRaisesRegex(RuntimeError, "Note authority fence"):
            self._run("downgrade")
        db.session.execute(sa.text("DELETE FROM connect_source_card_refs"))
        db.session.commit()
        self._run("downgrade")
        self.assertNotIn("applied_authority_revision", self._columns())
        self._run("upgrade")
        self.assertIn("applied_local_revision_state", self._columns())
