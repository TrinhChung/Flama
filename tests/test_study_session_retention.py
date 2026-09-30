"""Phase 7 session retention never changes learner data or statistics."""

from datetime import datetime, timedelta
import json
import unittest
from uuid import uuid4

from sqlalchemy import func, select

from app import create_app
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from app.services.study_composition_service import make_compatibility_composition_id
from app.services.study_session_retention_service import run_session_retention
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_progress_state import StudyProgressState
from models.study_session import StudySession
from models.study_session_authority_pin import StudySessionAuthorityPin
from models.study_session_card import StudySessionCard
from models.study_session_commit import StudySessionCommit
from models.template import Template
from models.user import User


class StudySessionRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
            "STUDY_WIRE_V4_ENABLED": True, "STUDY_ASYNC_BATCH_ENABLED": False,
        })

    def setUp(self):
        self.addCleanup(self._cleanup)
        with self.app.app_context():
            db.create_all()
            user = User(username="retention", email="retention@example.test")
            db.session.add(user)
            db.session.flush()
            deck = Deck(name="Retention", owner_user_id=user.id)
            note_type = NoteType(name="Retention", user_id=user.id)
            db.session.add_all([deck, note_type])
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
            template = Template(note_type_id=note_type.id, name="Card", front_html="{{Word}}",
                                back_html="{{Word}}", is_default=True)
            db.session.add(template)
            notes = [Note(user_id=user.id, deck_id=deck.id, note_type_id=note_type.id,
                          field_values={"Word": f"w{i}"}) for i in range(6)]
            db.session.add_all(notes)
            db.session.flush()
            db.session.add_all(Card(note_id=note.id, template_id=template.id) for note in notes)
            db.session.commit()
            stage_note_authority_enrollment(db.session, learner_user_id=int(user.id), now_utc=datetime.utcnow())
            db.session.commit()
            self.user_id, self.deck_id = int(user.id), int(deck.id)
            self.composition_id = make_compatibility_composition_id(note_type.id, template.id)
        self.client = self.app.test_client()
        with self.client.session_transaction() as login:
            login["_user_id"], login["_fresh"] = str(self.user_id), True

    def _cleanup(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _open(self):
        response = self.client.post("/api/study/sessions", json={
            "scope": "deck", "scope_id": self.deck_id, "composition_id": self.composition_id,
            "accepted_session_schema_versions": ["study-session.v4"],
            "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _commit_payload(self, snapshot, answers=2):
        events = []
        for sequence, card in enumerate(
            [c for c in snapshot["cards"] if c["state"].get("type") == "new"][:answers], start=1
        ):
            policy = snapshot["policies"][card["policy_key"]]
            event_id = str(uuid4())
            events.append({
                "event_id": event_id, "sequence": sequence, "card_id": card["card_id"], "rating": "good",
                "policy_key": card["policy_key"], "scheduler_offset_ms": 1000 * sequence, "duration_ms": 900,
                "action_key": "review.good", "action_contract_version": "1",
                "trigger_key": "scheduler.review.good", "trigger_contract_version": "1",
                "algorithm_key": snapshot["scheduler_algorithm"], "algorithm_version": snapshot["algorithm_version"],
                "config_schema_version": policy["config_schema_version"], "config_hash": policy["config_hash"],
                "study_session_id": snapshot["session_id"], "operation_key": event_id,
                **{k: v for k, v in card["authority_pin"].items() if k != "schema_version"},
            })
        return {"schema_version": "study-commit.v3", "commit_id": str(uuid4()),
                "session_token": snapshot["session_token"], "snapshot_hash": snapshot["snapshot_hash"],
                "commit_reason": "manual_exit", "events": events, "final_states": []}

    def _commit(self, snapshot, payload):
        response = self.client.post(f"/api/study/sessions/{snapshot['session_id']}/commit", json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def _age(self, session_id, days):
        with self.app.app_context():
            row = db.session.get(StudySession, session_id)
            row.opened_at = row.opened_at - timedelta(days=days)
            row.expires_at = row.expires_at - timedelta(days=days)
            db.session.commit()

    def _learner_view(self):
        stats = self.client.get("/api/statistics/overview?year=2026&timezone=UTC").get_json()
        dashboard = self.client.get("/api/dashboard").get_json()
        with self.app.app_context():
            events = sorted(
                (row.id, row.card_id, row.note_id, row.rating, row.study_session_id)
                for row in ReviewEvent.query.all()
            )
            states = sorted(
                (row.subject_id, bytes(row.semantic_state_hash).hex())
                for row in StudyProgressState.query.all()
            )
            sessions = db.session.execute(select(func.count()).select_from(StudySession)).scalar_one()
            commits = db.session.execute(select(func.count()).select_from(StudySessionCommit)).scalar_one()
        return json.dumps([stats, dashboard, events, states, sessions, commits], sort_keys=True, default=str)

    def _members(self, session_id):
        with self.app.app_context():
            return StudySessionCard.query.filter_by(session_id=session_id).count()

    def test_retention_keeps_every_learner_datum_and_statistic(self):
        old = self._open()
        old_payload = self._commit_payload(old)
        old_receipt = self._commit(old, old_payload)
        recent = self._open()
        self._commit(recent, self._commit_payload(recent, answers=1))
        stale_open = self._open()
        live_open = self._open()
        self._age(old["session_id"], 40)
        self._age(stale_open["session_id"], 3)
        with self.app.app_context():
            pins_before = StudySessionAuthorityPin.query.count()
        before = self._learner_view()

        with self.app.app_context():
            dry = run_session_retention(apply=False)
        self.assertEqual(dry.purge_candidate_sessions, 1)
        self.assertEqual(dry.expired_sessions, 1)
        self.assertGreater(self._members(old["session_id"]), 0)
        self.assertEqual(self._learner_view(), before)

        with self.app.app_context():
            applied = run_session_retention(apply=True)
            self.assertEqual(applied.expired_sessions, 1)
            self.assertEqual(applied.purged_sessions, 1)
            self.assertEqual(db.session.get(StudySession, stale_open["session_id"]).status, "expired")
            self.assertEqual(db.session.get(StudySession, live_open["session_id"]).status, "open")
            self.assertLess(StudySessionAuthorityPin.query.count(), pins_before)
        self.assertEqual(self._members(old["session_id"]), 0)
        for kept in (recent, stale_open, live_open):
            self.assertGreater(self._members(kept["session_id"]), 0)
        self.assertEqual(self._learner_view(), before)

        # A retried commit of the purged session still gets its original receipt.
        replay = self.client.post(f"/api/study/sessions/{old['session_id']}/commit", json=old_payload)
        self.assertEqual(replay.status_code, 200, replay.get_json())
        self.assertEqual(replay.get_json(), old_receipt)

        status = self.client.get(f"/api/study/sessions/{old['session_id']}")
        self.assertEqual(status.status_code, 200, status.get_json())
        self.assertEqual(status.get_json()["status"], "committed")

        # The still-open session keeps working.
        self._commit(live_open, self._commit_payload(live_open, answers=1))

        with self.app.app_context():
            again = run_session_retention(apply=True)
        self.assertEqual((again.expired_sessions, again.purged_sessions), (0, 0))

    def test_cli_is_a_dry_run_unless_applied(self):
        old = self._open()
        self._commit(old, self._commit_payload(old))
        self._age(old["session_id"], 40)
        runner = self.app.test_cli_runner()

        def report(args):
            output = runner.invoke(args=args).output
            return json.loads(next(line for line in output.splitlines() if line.startswith("{")))

        dry = report(["study-session-retention"])
        self.assertFalse(dry["applied"])
        self.assertEqual(dry["purge_candidate_sessions"], 1)
        self.assertGreater(self._members(old["session_id"]), 0)
        applied = report(["study-session-retention", "--apply"])
        self.assertTrue(applied["applied"])
        self.assertEqual(applied["purged_sessions"], 1)
        self.assertEqual(self._members(old["session_id"]), 0)
        refused = runner.invoke(args=["study-session-retention", "--older-than-days", "1"])
        self.assertNotEqual(refused.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
