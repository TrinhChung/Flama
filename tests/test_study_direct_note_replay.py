"""Direct NOTE transport retries preserve original results and exactly-once writes."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from app.services.study_progress_shadow_codec import canonical_document
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User


class StudyDirectNoteReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": ""})

    def setUp(self):
        self.addCleanup(self._cleanup)
        with self.app.app_context():
            db.create_all()
            user = User(username="direct-replay", email="direct-replay@example.test")
            db.session.add(user)
            db.session.flush()
            deck = Deck(name="Direct replay", owner_user_id=user.id)
            note_type = NoteType(name="Direct replay", user_id=user.id)
            db.session.add_all([deck, note_type])
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
            note = Note(user_id=user.id, note_type_id=note_type.id, deck_id=deck.id, field_values={"Word": "test"})
            db.session.add(note)
            db.session.flush()
            cards = []
            for index in range(2):
                template = Template(note_type_id=note_type.id, name=f"Card {index}",
                    front_html="{{Word}}", back_html="{{Word}}", is_default=index == 0)
                db.session.add(template)
                db.session.flush()
                card = Card(note_id=note.id, template_id=template.id)
                db.session.add(card)
                cards.append(card)
            db.session.flush()
            self.user_id, self.deck_id = user.id, deck.id
            self.card_ids = [card.id for card in cards]
            db.session.commit()
            stage_note_authority_enrollment(db.session, learner_user_id=self.user_id,
                now_utc=datetime.now(timezone.utc).replace(tzinfo=None))
            db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as login:
            login["_user_id"], login["_fresh"] = str(self.user_id), True
        self.payload = {"rating": "easy", "operation_key": str(uuid4()), "duration_ms": 500,
            "scope": "deck", "scope_id": self.deck_id}

    def _cleanup(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _answer(self, payload=None, *, card_id=None, expected=200):
        response = self.client.post(f"/api/study/{card_id or self.card_ids[0]}/answer",
            json=self.payload if payload is None else payload)
        self.assertEqual(response.status_code, expected, response.get_json())
        return response.get_json()

    def _counts(self, count=1):
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), count)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), count)
            self.assertEqual(StudyProgressHistoryFact.query.filter(StudyProgressHistoryFact.review_event_id.isnot(None)).count(), count)
            self.assertEqual(AuditLog.query.filter_by(action="study.answer").count(), count)
            self.assertEqual(StudyProgressSubject.query.one().authority_revision, count)
            # The Note's one row holds its state; no Card carries progress (ADR P10).
            self.assertEqual(CardProgress.query.count(), 0)

    def test_retry_returns_original_result_without_executing_scheduler_or_side_effects(self):
        original = self._answer()
        self._answer({**self.payload, "operation_key": str(uuid4()), "rating": "hard"})
        with patch("app.services.study_service.execute_native_review_transition", side_effect=AssertionError("re-evaluated")), patch(
            "app.services.study_service.compute_review_previews", side_effect=AssertionError("new previews")), patch(
            "app.services.study_service.stage_native_review_side_effects", side_effect=AssertionError("new side effects")):
            repeated = self._answer()
        self.assertEqual(repeated["authority"], {**original["authority"], "replayed": True})
        self.assertEqual(repeated["intervals_preview"], original["intervals_preview"])
        self._counts(2)

    def test_preview_preserves_exact_json_numbers_as_bounded_text(self):
        original = self._answer()
        with self.app.app_context():
            receipt = StudyAuthorityCommandReceipt.query.one()
            envelope = receipt.response_payload["direct_replay"]
            preview_json = envelope["intervals_preview_json"]
            self.assertIsInstance(preview_json, str)
            self.assertEqual(json.loads(preview_json), original["intervals_preview"])
            # MySQL JSON converts this raw double to 0.003819444444444444,
            # changing its hash. Text storage retains the exact f64 result.
            self.assertEqual(json.loads(preview_json)["hard"]["days"].hex(), (330 / 86400).hex())
            self.assertLessEqual(receipt.response_payload_size, 16384)
        repeated = self._answer()
        self.assertEqual(repeated["intervals_preview"], original["intervals_preview"])
        self._counts()

    def test_changed_body_or_card_cannot_reuse_operation_key(self):
        self._answer()
        for changed in ({"rating": "good"}, {"duration_ms": 501}, {"scope": "note_type"}):
            with self.subTest(changed=changed):
                result = self._answer({**self.payload, **changed}, expected=409)
                self.assertEqual(result["error"], "AUTHORITY_OPERATION_REUSED")
        result = self._answer(card_id=self.card_ids[1], expected=409)
        self.assertEqual(result["error"], "AUTHORITY_OPERATION_REUSED")
        self._counts()

    def test_uncertain_commit_replays_receipt_without_second_event(self):
        with self.app.app_context():
            commit = db.session.commit
            def lost_ack():
                commit()
                raise RuntimeError("lost acknowledgement")
            with patch.object(db.session, "commit", side_effect=lost_ack):
                self._answer(expected=500)
        self.assertTrue(self._answer()["authority"]["replayed"])
        self._counts()

    def test_manifest_retry_precedes_stale_version_but_new_operation_does_not(self):
        card_id = self.card_ids[0]
        preview = self.client.get(f"/api/study/cards/{card_id}/intervals-preview")
        self.assertEqual(preview.status_code, 200, preview.get_json())
        payload = {**self.payload, "render_contract": "client_v1",
            "review_state_version": preview.get_json()["review_state_version"]}
        path = f"/api/study/cards/{card_id}/answer"
        first = self.client.post(path, json=payload)
        self.assertEqual(first.status_code, 200, first.get_json())
        repeated = self.client.post(path, json=payload)
        self.assertEqual(repeated.status_code, 200, repeated.get_json())
        self.assertTrue(repeated.get_json()["authority"]["replayed"])
        stale = self.client.post(path, json={**payload, "operation_key": str(uuid4())})
        self.assertEqual(stale.status_code, 409, stale.get_json())
        self.assertEqual(stale.get_json()["error"], "STALE_REVIEW_STATE")
        self._counts()

    def test_missing_or_changed_history_evidence_cannot_replay(self):
        self._answer()
        with self.app.app_context():
            event = ReviewEvent.query.one()
            event.duration_ms = 999
            db.session.commit()
        result = self._answer(expected=409)
        self.assertEqual(result["error"], "AUTHORITY_RECEIPT_CORRUPT")
        with self.app.app_context():
            ReviewEvent.query.one().duration_ms = 500
            db.session.delete(StudyProgressHistoryFact.query.filter(StudyProgressHistoryFact.review_event_id.isnot(None)).one())
            db.session.commit()
        result = self._answer(expected=409)
        self.assertEqual(result["error"], "AUTHORITY_RECEIPT_CORRUPT")
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)

    def test_changed_epoch_and_reset_generation_fence_old_receipt(self):
        self._answer()
        with self.app.app_context():
            enrollment = db.session.get(StudyAuthorityEnrollment, self.user_id)
            enrollment.epoch += 1
            db.session.commit()
        result = self._answer(expected=409)
        self.assertEqual(result["error"], "AUTHORITY_RECEIPT_CONTEXT_CONFLICT")
        with self.app.app_context():
            db.session.get(StudyAuthorityEnrollment, self.user_id).epoch -= 1
            db.session.commit()
        reset = self.client.post(f"/api/decks/{self.deck_id}/progress-reset")
        self.assertEqual(reset.status_code, 200, reset.get_json())
        result = self._answer(expected=409)
        self.assertEqual(result["error"], "AUTHORITY_RECEIPT_CONTEXT_CONFLICT")
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)

    def test_corrupt_or_unavailable_receipt_never_becomes_a_new_operation(self):
        self._answer()
        with self.app.app_context():
            baseline = deepcopy(StudyAuthorityCommandReceipt.query.one().response_payload)
        for kind in ("missing", "unknown", "request", "preview", "response_hash"):
            with self.subTest(kind=kind), self.app.app_context():
                payload = deepcopy(baseline)
                if kind == "missing":
                    payload.pop("direct_replay")
                elif kind == "unknown":
                    payload["direct_replay"]["schema_version"] = "unknown"
                elif kind == "request":
                    payload["direct_replay"]["request"]["current_state"]["reps"] = "99"
                else:
                    previews = json.loads(payload["direct_replay"]["intervals_preview_json"])
                    previews["easy"]["label"] = "forged"
                    payload["direct_replay"]["intervals_preview_json"] = canonical_document(
                        previews, too_large_code="TOO_LARGE").encoded.decode("utf-8")
                document = canonical_document(payload, too_large_code="TOO_LARGE")
                receipt = StudyAuthorityCommandReceipt.query.one()
                receipt.response_payload = document.payload
                receipt.response_payload_size = document.size
                receipt.response_payload_hash = document.digest if kind != "response_hash" else b"x" * 32
                db.session.commit()
                result = self._answer(expected=409)
                expected = "AUTHORITY_DIRECT_REPLAY_UNAVAILABLE" if kind in {"missing", "unknown"} else "AUTHORITY_RECEIPT_CORRUPT"
                self.assertEqual(result["error"], expected)
        self._counts()

    def test_mcp_native_transport_preserves_result_across_clock_change(self):
        from app.services.study_service import execute_native_review_command

        with self.app.app_context():
            kwargs = dict(user=db.session.get(User, self.user_id), card=db.session.get(Card, self.card_ids[0]),
                action="easy", payload={"duration_ms": 1000, "timezone": "UTC"}, clone_scope=None,
                requested_scope_id=self.deck_id, timezone_name="UTC", client_event_id=str(uuid4()), source_path="native.mcp")
            now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
            original = execute_native_review_command(**kwargs, now=now)
            repeated = execute_native_review_command(**kwargs, now=now + timedelta(hours=2))
            self.assertTrue(repeated.replayed)
            self.assertEqual(repeated.transition, original.transition)
            self.assertEqual(repeated.current_state, original.current_state)
            self.assertEqual(repeated.intervals_preview, original.intervals_preview)
            self.assertFalse(db.session().in_transaction())
        self._counts()

    def test_mcp_adapter_preserves_longest_supported_key_and_original_policy(self):
        from app.services.mcp.study_tools import submit_review
        from app.validators.mcp import validate_submit_review_arguments

        arguments = validate_submit_review_arguments({"card_id": self.card_ids[0],
            "rating": "easy", "duration_ms": 500, "operation_key": "mcp-" + "a" * 32})
        with self.app.app_context():
            original = submit_review(user_id=self.user_id, **arguments)
            db.session.get(User, self.user_id).timezone = "Asia/Tokyo"
            db.session.commit()
            repeated = submit_review(user_id=self.user_id, **arguments)
            self.assertEqual(repeated, {**original, "authority": {**original["authority"], "replayed": True}})
            self.assertEqual(ReviewEvent.query.one().client_event_id, arguments["operation_key"])
        self._counts()


if __name__ == "__main__":
    unittest.main()
