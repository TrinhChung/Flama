"""Phase 9 readiness is a read-only report over old-usage evidence."""

from datetime import datetime, timedelta
import json
import unittest

from app import create_app
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from app.services.study_phase9_readiness_service import build_phase9_readiness
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_session import StudySession
from models.template import Template
from models.user import User


class StudyPhase9ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(username="phase9", email="phase9@example.test")
        db.session.add(user)
        db.session.flush()
        deck = Deck(name="P9", owner_user_id=user.id)
        note_type = NoteType(name="P9", user_id=user.id)
        db.session.add_all([deck, note_type])
        db.session.flush()
        db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
        template = Template(note_type_id=note_type.id, name="Card", front_html="{{Word}}", back_html="{{Word}}")
        note = Note(user_id=user.id, deck_id=deck.id, note_type_id=note_type.id, field_values={"Word": "w"})
        db.session.add_all([template, note])
        db.session.flush()
        db.session.add(Card(note_id=note.id, template_id=template.id))
        db.session.commit()
        self.user_id = int(user.id)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _session(self, wire, opened_at, status="committed"):
        db.session.add(StudySession(
            user_id=self.user_id, status=status, wire_schema_version=wire, opened_at=opened_at,
            expires_at=opened_at + timedelta(hours=24), scope_type="deck", scope_id="1",
            snapshot_hash="h", token_hash="t", config_snapshot_json="{}",
        ))
        db.session.commit()

    def test_gates_follow_the_evidence_window(self):
        now = datetime(2026, 9, 30, 12, 0, 0)
        report = build_phase9_readiness(now_utc=now)
        # The learner has no enrollment yet: the projection gate is still waiting.
        gate = report["gates"]["legacy_projection_writes"]
        self.assertEqual(gate["status"], "waiting")
        self.assertIn("UNENROLLED_USERS", gate["blocking_reasons"])
        self.assertEqual(report["gates"]["old_session_wire_versions"]["status"], "ready")
        self.assertEqual(report["gates"]["positional_anki_ordinals"]["status"], "ready")
        self.assertFalse(report["destructive_steps_allowed"])

        stage_note_authority_enrollment(db.session, learner_user_id=self.user_id, now_utc=now)
        db.session.commit()
        self._session("study-session.v2", now - timedelta(days=40))
        self._session("study-session.v4", now - timedelta(days=1))
        report = build_phase9_readiness(now_utc=now)
        # D9-02: no product decision blocks the gate, only the projection
        # dependency of NOTE readers/writers (P9-03..P9-05b).
        gate = report["gates"]["legacy_projection_writes"]
        self.assertEqual(gate["status"], "waiting")
        self.assertEqual(gate["blocking_reasons"], ["NOTE_STILL_DEPENDS_ON_PROJECTION"])
        self.assertEqual(report["gates"]["old_session_wire_versions"]["status"], "ready")

        self._session("study-session.v2", now - timedelta(days=3))
        report = build_phase9_readiness(now_utc=now)
        gate = report["gates"]["old_session_wire_versions"]
        self.assertEqual(gate["status"], "waiting")
        self.assertEqual(gate["evidence"]["sessions_in_window"]["study-session.v2"]["sessions"], 1)

    def test_projection_cutover_and_work_drain_gates(self):
        from models.card_progress import CardProgress

        now = datetime(2026, 9, 30, 12, 0, 0)
        report = build_phase9_readiness(now_utc=now)
        # Without T0 the cutover gate is unknown, never a silent zero.
        self.assertEqual(report["gates"]["projection_cutover"]["status"], "unknown")
        self.assertEqual(report["gates"]["work_drain"]["status"], "ready")

        card = Card.query.one()
        db.session.add(CardProgress(user_id=self.user_id, card_id=card.id, queue="new", ease_factor=2.5,
                                    revision=0, created_at=now - timedelta(hours=2),
                                    updated_at=now - timedelta(hours=2)))
        db.session.commit()
        t0 = now - timedelta(hours=1)
        report = build_phase9_readiness(now_utc=now, projection_since_utc=t0)
        self.assertEqual(report["gates"]["projection_cutover"]["status"], "ready")
        progress = CardProgress.query.one()
        progress.updated_at = now - timedelta(minutes=5)
        db.session.commit()
        gate = build_phase9_readiness(now_utc=now, projection_since_utc=t0)["gates"]["projection_cutover"]
        self.assertEqual((gate["status"], gate["evidence"]["card_progress_rows_written_since"]), ("waiting", 1))

        # An expired open lease does not block; a valid one does.
        self._session("study-session.v4", now - timedelta(days=2), status="open")
        self.assertEqual(build_phase9_readiness(now_utc=now)["gates"]["work_drain"]["status"], "ready")
        self._session("study-session.v4", now - timedelta(hours=1), status="open")
        drain = build_phase9_readiness(now_utc=now)["gates"]["work_drain"]
        self.assertEqual(drain["status"], "waiting")
        self.assertIn({"wire": "study-session.v4", "valid": True, "sessions": 1}, drain["evidence"]["open_leases"])

    def test_cli_prints_the_report(self):
        output = self.app.test_cli_runner().invoke(args=["study-phase9-readiness", "--window-days", "7"]).output
        report = json.loads(next(line for line in output.splitlines() if line.startswith("{")))
        self.assertEqual((report["schema_version"], report["window_days"]), ("study-phase9-readiness.v2", 7))


if __name__ == "__main__":
    unittest.main()
