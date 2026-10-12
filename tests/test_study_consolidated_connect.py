"""P10: Anki/Connect progress snapshots under CONSOLIDATED_V1 fence on the row's revision."""

from __future__ import annotations

from datetime import datetime
import unittest
from uuid import uuid4

from sqlalchemy import event

# Import the app (through the Anki tests) before any model module.
from tests import test_anki_import_api as anki_tests  # noqa: I001
from tests.test_study_consolidated_progress import OLD_TABLES
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from models import db
from models.card import Card
from models.connect_source_card_ref import ConnectSourceCardRef
from models.note import Note
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from tests.study_note_fixtures import attach_template
from models.user import User


SNAPSHOT_A = {
    "externalNoteId": 3101, "sourceCardId": 4101, "ord": 0, "snapshotHash": "a" * 64,
    "baseSnapshotHash": None, "type": 2, "queue": 2, "due": 50003, "sourceToday": 50000,
    "interval": 14, "factor": 2500, "reps": 2, "lapses": 1, "left": 0,
}


class StudyConsolidatedConnectTests(unittest.TestCase):
    setUp = anki_tests.AnkiImportApiTests.setUp
    tearDown = anki_tests.AnkiImportApiTests.tearDown
    _login = anki_tests.AnkiImportApiTests._login
    _session_payload = anki_tests.AnkiImportApiTests._session_payload
    _create_session = anki_tests.AnkiImportApiTests._create_session
    _upload_package = anki_tests.AnkiImportApiTests._upload_package

    def _sync(self, sequence, **changes):
        return self._upload_package(self.session_id, "progress", sequence, [{**SNAPSHOT_A, **changes}])["results"][0]

    def _ref(self):
        return ConnectSourceCardRef.query.filter_by(user_id=self.admin_id, external_card_id="4101").one()

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
            template = attach_template(db.session, note_type_id=note.note_type_id, owner_user_id=self.admin_id, name="Authority sibling",
                                front_html="{{Meaning}}", back_html="{{Word}}", position=1)
            db.session.add(template)
            db.session.flush()
            db.session.flush()
            # The P10 switch requires every account on NOTE authority, as in production.
            for user_id in sorted(user.id for user in User.query.all()):
                stage_note_authority_enrollment(db.session, learner_user_id=user_id,
                                                now_utc=datetime(2026, 9, 23, 9, 0, 0))
            db.session.commit()
            self.card_id = Card.query.order_by(Card.id).first().id
            self.deck_id = note.deck_id
            engine = db.engine
        self.statements = []

        def record(_conn, _cursor, statement, *_args):
            match = OLD_TABLES.search(statement)
            if match and not statement.lstrip().upper().startswith("DELETE"):
                self.statements.append(f"{statement.split()[0].upper()} {match.group(1)}")

        event.listen(engine, "before_cursor_execute", record)
        self.addCleanup(lambda: event.remove(engine, "before_cursor_execute", record))

    def _status(self):
        response = self.client.post(
            f"/api/flashcards/import/anki/sessions/{self.session_id}/note-status",
            json={"notes": [{"ankiNoteId": 3101, "contentHash": "3" * 64,
                             "cards": [{"sourceCardId": 4101, "snapshotHash": "c" * 64}]}]})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()["notes"][0]["cards"][0]["progressState"]

    def _row(self):
        db.session.expire_all()
        return StudyProgressSubject.query.one()

    def test_snapshots_fence_on_the_row_revision(self):
        self._prepare_note_learner()
        first = self._sync(0)
        self.assertEqual((first["state"], first["code"]), ("applied", "PROGRESS_APPLIED"))
        with self.app.app_context():
            row = self._row()
            self.assertEqual(int(row.authority_revision), 1)
            self.assertEqual(row.state_payload["scheduler_mode"], "anki")
            self.assertEqual(row.normalized_queue, "review")
            self.assertEqual(row.current_provenance_code, "CONNECT_PROGRESS_SNAPSHOT")
            self.assertEqual(row.history_completeness_code, "HISTORY_MIXED_PARTIAL")
            ref = self._ref()
            self.assertEqual((ref.applied_local_revision_state, ref.applied_authority_revision), ("AUTHORITY", 1))

        # Same scheduling, new snapshot hash: confirmed, no material write.
        replay = self._sync(1, snapshotHash="e" * 64, baseSnapshotHash="a" * 64)
        self.assertEqual((replay["state"], replay["code"]), ("applied", "PROGRESS_APPLIED"))
        with self.app.app_context():
            self.assertEqual(int(self._row().authority_revision), 1)

        # The learner studies in Flama: the next Anki change is a local conflict.
        answered = self.client.post(f"/api/study/{self.card_id}/answer", json={
            "rating": "good", "operation_key": str(uuid4()), "duration_ms": 500,
            "scope": "deck", "scope_id": self.deck_id})
        self.assertEqual(answered.status_code, 200, answered.get_json())
        conflict = self._sync(2, snapshotHash="c" * 64, baseSnapshotHash="e" * 64, interval=30)
        self.assertEqual((conflict["state"], conflict["code"]), ("local_conflict", "LOCAL_PROGRESS_CHANGED"))

        forced = self._sync(3, snapshotHash="c" * 64, baseSnapshotHash="e" * 64, interval=30, force=True)
        self.assertEqual((forced["state"], forced["code"]), ("applied", "FORCED_PROGRESS_APPLIED"))
        with self.app.app_context():
            self.assertEqual(int(self._row().authority_revision), 3)
            self.assertEqual(self._ref().applied_authority_revision, 3)

        # The add-on's status probe reports a local change against the row revision.
        self.assertEqual(self._status(), "unchanged")
        answered = self.client.post(f"/api/study/{self.card_id}/answer", json={
            "rating": "good", "operation_key": str(uuid4()), "duration_ms": 500,
            "scope": "deck", "scope_id": self.deck_id})
        self.assertEqual(answered.status_code, 200, answered.get_json())
        with self.app.app_context():
            self.assertEqual(int(self._row().authority_revision), 4)
        self.assertEqual(self._status(), "local_changed")
        self.assertEqual(self.statements, [])


if __name__ == "__main__":
    unittest.main()
