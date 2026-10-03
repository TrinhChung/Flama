"""Phase 9 readiness is a read-only report over old-usage evidence."""

from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import patch

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
from app.services.study_retirement_telemetry_service import ENTRYPOINTS, OBSERVATION_SCHEMA, SCHEMA_VERSION


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

    def _observation(self, now, events=None):
        return {"schema_version": OBSERVATION_SCHEMA, "start_utc": (now - timedelta(days=31)).isoformat() + "Z",
                "end_utc": now.isoformat() + "Z", "continuous": True, "gaps": [],
                "covered_entrypoints": sorted(set().union(*ENTRYPOINTS.values())), "events": events or []}

    def test_gates_follow_the_evidence_window(self):
        now = datetime(2026, 9, 30, 12, 0, 0)
        report = build_phase9_readiness(now_utc=now)
        # The learner has no enrollment yet: the projection gate is still waiting.
        gate = report["gates"]["legacy_projection_writes"]
        self.assertEqual(gate["status"], "waiting")
        self.assertIn("UNENROLLED_USERS", gate["blocking_reasons"])
        self.assertEqual(report["gates"]["old_session_wire_versions"]["status"], "unknown")
        self.assertEqual(report["gates"]["positional_anki_ordinals"]["status"], "unknown")
        self.assertFalse(report["destructive_steps_allowed"])

        stage_note_authority_enrollment(db.session, learner_user_id=self.user_id, now_utc=now)
        db.session.commit()
        self._session("study-session.v2", now - timedelta(days=40))
        self._session("study-session.v4", now - timedelta(days=1))
        # D9-02: no product decision blocks the gate. A release without
        # CANONICAL_V1 support still depends on the projection.
        with patch("app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES",
                   frozenset({"PROJECTION_V1"})):
            gate = build_phase9_readiness(now_utc=now)["gates"]["legacy_projection_writes"]
        self.assertEqual(gate["status"], "waiting")
        self.assertEqual(gate["blocking_reasons"], ["NOTE_STILL_DEPENDS_ON_PROJECTION"])
        report = build_phase9_readiness(now_utc=now, retirement_observation=self._observation(now))
        gate = report["gates"]["legacy_projection_writes"]
        self.assertEqual((gate["status"], gate["blocking_reasons"]), ("ready", []))
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
        self.assertEqual(report["gates"]["projection_cutover"]["status"], "waiting")
        from models.study_authority_storage_profile import StudyAuthorityStorageProfile

        db.session.add(StudyAuthorityStorageProfile(id=1, profile_code="CANONICAL_V1", epoch=2,
                                                   switched_at=t0, created_at=t0, updated_at=t0))
        db.session.commit()
        # No caller-supplied T0 is required once the persisted profile switched.
        report = build_phase9_readiness(now_utc=now)
        self.assertEqual(report["gates"]["projection_cutover"]["status"], "ready")
        # The P10 profile is reached from CANONICAL_V1 and stays projection-free.
        profile = db.session.get(StudyAuthorityStorageProfile, 1)
        profile.profile_code = "CONSOLIDATED_V1"
        db.session.commit()
        report = build_phase9_readiness(now_utc=now)
        self.assertEqual(report["gates"]["projection_cutover"]["status"], "ready")
        self.assertNotIn("UNKNOWN_STORAGE_PROFILE", report["gates"]["legacy_projection_writes"]["blocking_reasons"])
        profile.profile_code = "CANONICAL_V1"
        db.session.commit()
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
        output = self.app.test_cli_runner().invoke(args=["study-phase9-readiness", "--window-days", "30"]).output
        report = json.loads(next(line for line in output.splitlines() if line.startswith("{")))
        self.assertEqual((report["schema_version"], report["window_days"]), ("study-phase9-readiness.v3", 30))

    def test_late_retry_coverage_gap_and_short_window_cannot_retire_wire(self):
        now = datetime(2026, 10, 2, 12)
        self._session("study-session.v2", now - timedelta(days=40))
        observation = self._observation(now, [{"schema_version": SCHEMA_VERSION, "entrypoint": "session.commit",
                                             "observed_at_utc": (now - timedelta(hours=1)).isoformat() + "Z"}])
        gate = build_phase9_readiness(now_utc=now, retirement_observation=observation)["gates"]["old_session_wire_versions"]
        self.assertEqual(gate["status"], "waiting")
        self.assertEqual(gate["runtime_observation"]["counts"], {"session.commit": 1})
        observation["events"] = []
        observation["gaps"] = ["rotated journal segment missing"]
        self.assertEqual(build_phase9_readiness(now_utc=now, retirement_observation=observation)["gates"]["old_session_wire_versions"]["status"], "unknown")
        observation["gaps"] = []
        observation["start_utc"] = (now - timedelta(days=29)).isoformat() + "Z"
        self.assertEqual(build_phase9_readiness(now_utc=now, retirement_observation=observation)["gates"]["old_session_wire_versions"]["status"], "unknown")
        with self.assertRaises(ValueError):
            build_phase9_readiness(now_utc=now, window_days=7)

    def test_external_detached_ref_blocks_but_native_ordinal_is_optional(self):
        from models.connect_source_card_ref import ConnectSourceCardRef
        from models.study_application import StudyApplication

        now = datetime(2026, 10, 2, 12)
        StudyApplication.query.one().source_ord = None
        db.session.commit()
        gate = build_phase9_readiness(now_utc=now, retirement_observation=self._observation(now))["gates"]["positional_anki_ordinals"]
        self.assertEqual(gate["status"], "ready")
        db.session.add(ConnectSourceCardRef(user_id=self.user_id, source_key="source", external_card_id="card",
                                           external_note_id="note", source_ord=0, card_id=None))
        db.session.commit()
        gate = build_phase9_readiness(now_utc=now, retirement_observation=self._observation(now))["gates"]["positional_anki_ordinals"]
        self.assertEqual((gate["status"], gate["evidence"]["connect_refs_without_card"]), ("waiting", 1))

    def test_unknown_batch_status_blocks_work_drain(self):
        from models.study_session_batch import StudySessionBatch

        now = datetime(2026, 10, 2, 12)
        self._session("study-session.v4", now - timedelta(days=40))
        db.session.add(StudySessionBatch(user_id=self.user_id, session_id=StudySession.query.one().id,
                                        batch_id="unknown", request_hash="h", status="recoverable"))
        db.session.commit()
        self.assertEqual(build_phase9_readiness(now_utc=now)["gates"]["work_drain"]["status"], "waiting")


if __name__ == "__main__":
    unittest.main()
