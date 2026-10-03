"""Internal canonical NOTE batch command; transport stays production-gated."""

from datetime import datetime, timedelta
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import event as sql_event

from app import create_app
from app.services.study_artifact_service import canonical_digest
from app.services.study_authority_enrollment_service import (
    StudyAuthorityEnrollmentError,
    stage_legacy_authority_enrollment,
    stage_note_authority_enrollment,
)
from app.services.study_progress_shadow_codec import decode_datetime, decode_float
from app.services.study_composition_service import make_compatibility_composition_id
from app.services.study_note_batch_service import commit_note_study_session_batch
from app.services.study_session_service import StudySessionError
from app.services.study_worker_service import drain_study_queue, process_single_study_batch, recover_admitted_study_batches
from app.services.study_queue_service import clear_study_queue, enqueue_study_batch, pop_study_batch
from models import db
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
from models.study_session import StudySession
from models.study_session_authority_pin import StudySessionAuthorityPin
from models.study_session_batch import StudySessionBatch
from models.study_session_commit import StudySessionCommit
from models.template import Template
from models.user import User


class StudyNoteBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "STUDY_WIRE_V4_ENABLED": True,
            "STUDY_ASYNC_BATCH_ENABLED": False, "REDIS_URL": "",
            "STUDY_QUEUE_NAMESPACE": "",
        })

    def setUp(self):
        clear_study_queue()
        self.addCleanup(self._cleanup)
        self._seed()

    def _seed(self, *, note_count=1):
        with self.app.app_context():
            db.create_all()
            user = User(username="note-batch", email="note-batch@example.test")
            db.session.add(user)
            db.session.flush()
            deck = Deck(name="Note batches", owner_user_id=user.id)
            note_type = NoteType(name="Note batches", user_id=user.id)
            db.session.add_all([deck, note_type])
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
            notes = [
                Note(user_id=user.id, deck_id=deck.id, note_type_id=note_type.id, field_values={"Word": f"猫-{number}"})
                for number in range(note_count)
            ]
            db.session.add_all(notes)
            db.session.flush()
            for number in range(2):
                template = Template(
                    note_type_id=note_type.id, name=f"Card {number}",
                    front_html="{{Word}}", back_html="{{Word}}", is_default=number == 0,
                )
                db.session.add(template)
                db.session.flush()
                if number == 0:
                    self.composition_id = make_compatibility_composition_id(note_type.id, template.id)
                db.session.add_all(Card(note_id=note.id, template_id=template.id) for note in notes)
            self.user_id, self.deck_id = user.id, deck.id
            db.session.commit()
            stage_note_authority_enrollment(db.session, learner_user_id=self.user_id, now_utc=datetime.utcnow())
            db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as login:
            login["_user_id"] = str(self.user_id)
            login["_fresh"] = True
        opened = self.client.post("/api/study/sessions", json={
            "scope": "deck", "scope_id": self.deck_id,
            "composition_id": self.composition_id,
            "accepted_session_schema_versions": ["study-session.v4"],
            "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
        })
        self.assertEqual(opened.status_code, 201, opened.get_json())
        self.snapshot = opened.get_json()

    def _cleanup(self):
        clear_study_queue()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _event(self, sequence, *, card=None):
        snapshot = self.snapshot
        card = card or snapshot["cards"][0]
        policy = snapshot["policies"][card["policy_key"]]
        event_id = str(uuid4())
        return {
            "event_id": event_id, "sequence": sequence, "card_id": card["card_id"],
            "rating": "good", "action_key": "review.good", "action_contract_version": "1",
            "trigger_key": "scheduler.review.good", "trigger_contract_version": "1",
            "policy_key": card["policy_key"], "scheduler_offset_ms": sequence * 1000, "duration_ms": 500,
            "algorithm_key": snapshot["scheduler_algorithm"], "algorithm_version": snapshot["algorithm_version"],
            "config_schema_version": policy["config_schema_version"], "config_hash": policy["config_hash"],
            "study_session_id": snapshot["session_id"], "operation_key": event_id,
            **{key: value for key, value in card["authority_pin"].items() if key != "schema_version"},
        }

    def _batch_payload(self, sequence, events, *, final=False):
        return {
            "schema_version": "study-batch.v3", "batch_id": str(uuid4()),
            "batch_sequence": sequence, "session_token": self.snapshot["session_token"],
            "snapshot_hash": self.snapshot["snapshot_hash"], "commit_reason": "rollover",
            "is_final": final, "events": events, "final_states": [],
        }

    def _admit(self, sequence, events, *, final=False):
        # Direct durable fixture for canonical-command corruption/fault tests.
        payload = self._batch_payload(sequence, events, final=final)
        with self.app.app_context():
            db.session.add(StudySessionBatch(
                session_id=self.snapshot["session_id"], user_id=self.user_id,
                batch_id=payload["batch_id"], batch_sequence=sequence, event_count=len(events),
                is_final=final, commit_reason="rollover", status="enqueued",
                request_hash=canonical_digest(payload), payload_json=json.dumps(payload),
            ))
            db.session.commit()
        return payload["batch_id"]

    def _http_admit(self, payload, *, expected=202, path="batch"):
        with patch.dict(self.app.config, STUDY_ASYNC_BATCH_ENABLED=True):
            response = self.client.post(f"/api/study/sessions/{self.snapshot['session_id']}/{path}", json=payload)
        self.assertEqual(response.status_code, expected, response.get_json())
        return response.get_json()

    def _process(self, batch_id, **kwargs):
        with self.app.app_context():
            result = commit_note_study_session_batch(
                user=db.session.get(User, self.user_id),
                session_id=self.snapshot["session_id"], batch_id=batch_id, **kwargs,
            )
            self.assertFalse(db.session().in_transaction())
            return result

    @staticmethod
    def _state_value(name, decoder):
        return decoder(StudyProgressSubject.query.one().state_payload[name], field_name=name)

    def _assert_progress(self, revision, *, session_status="open"):
        with self.app.app_context():
            self.assertEqual(StudyProgressSubject.query.one().authority_revision, revision)
            self.assertEqual(ReviewEvent.query.count(), revision)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), revision)
            self.assertEqual(StudyProgressHistoryFact.query.filter(
                StudyProgressHistoryFact.review_event_id.isnot(None),
            ).count(), revision)
            # The Note's one row holds the state; no Card carries progress (ADR P10).
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(db.session.get(StudySession, self.snapshot["session_id"]).status, session_status)
            self.assertTrue(all(pin.base_authority_revision == 0 for pin in StudySessionAuthorityPin.query.all()))

    def test_continuous_consumer_recovers_admitted_notes_without_redis_or_new_admission(self):
        from app.services.study_consumer_service import StudyBatchConsumer, StudyConsumerOptions

        with patch.dict(self.app.config, STUDY_QUEUE_NAMESPACE="note-consumer-test"):
            first = self._batch_payload(1, [self._event(1)])
            second = self._batch_payload(2, [self._event(2)], final=True)
            self._http_admit(first)
            self._http_admit(second)
            with self.app.app_context():
                clear_study_queue()  # Simulate loss of every delivery hint.
                self.assertFalse(self.app.config["STUDY_ASYNC_BATCH_ENABLED"])
                consumer = StudyBatchConsumer(options=StudyConsumerOptions(recovery_page_size=1, jobs_per_pass=1))
                result = consumer.step()
                self.assertFalse(result["ready"])  # No local readiness fallback.
                self.assertEqual(result["processed_count"], 1)
                clear_study_queue()
                # A fresh consumer must recover the next durable admission.
                result = StudyBatchConsumer().step()
                self.assertEqual(result["processed_count"], 1)
                self.assertFalse(db.session().in_transaction())
                clear_study_queue()
            self._assert_progress(2, session_status="committed")

    def test_numeric_profile_is_negotiated_and_frozen_in_versioned_config(self):
        self.assertEqual(self.snapshot["storage_profile"], "note-mysql-float-text.v1")
        with self.app.app_context():
            config = json.loads(db.session.get(StudySession, self.snapshot["session_id"]).config_snapshot_json)
            self.assertEqual(config["schema_version"], "study-session-config.v3")
            self.assertEqual(config["storage_profile"], self.snapshot["storage_profile"])

    def test_unprofiled_v4_lease_retains_original_receipt_fingerprint(self):
        opened = self.client.post("/api/study/sessions", json={
            "scope": "deck", "scope_id": self.deck_id, "composition_id": self.composition_id,
            "accepted_session_schema_versions": ["study-session.v4"],
        })
        self.assertEqual(opened.status_code, 201, opened.get_json())
        self.snapshot = opened.get_json()
        self.assertNotIn("storage_profile", self.snapshot)
        with self.app.app_context():
            config = json.loads(db.session.get(StudySession, self.snapshot["session_id"]).config_snapshot_json)
            self.assertEqual(config["schema_version"], "study-session-config.v2")
            self.assertNotIn("storage_profile", config)
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)], final=True)
        receipt = self._process(first)
        final = self._process(second)
        self.assertEqual(self._process(first), receipt)
        self.assertEqual(self._process(second), final)
        with self.app.app_context():
            for event in ReviewEvent.query.all():
                self.assertNotIn("storage_profile", json.loads(event.payload_json)["_study_runtime"])

    def test_unknown_missing_or_downgraded_numeric_profile_cannot_execute(self):
        batch = self._admit(1, [self._event(1)], final=True)
        with self.app.app_context():
            base = json.loads(db.session.get(StudySession, self.snapshot["session_id"]).config_snapshot_json)
        for config in (
            {**base, "storage_profile": "unknown"},
            {key: value for key, value in base.items() if key != "storage_profile"},
            {**base, "schema_version": "study-session-config.v2"},
            {**base, "schema_version": ["study-session-config.v3"]},
            {**base, "storage_profile": {"unexpected": "object"}},
        ):
            with self.subTest(config=config):
                with self.app.app_context():
                    db.session.get(StudySession, self.snapshot["session_id"]).config_snapshot_json = json.dumps(config)
                    db.session.commit()
                with self.assertRaises(StudySessionError) as failure:
                    self._process(batch)
                self.assertEqual(failure.exception.code, "INVALID_CONFIG_SNAPSHOT")
                self._assert_progress(0)

    def _numeric_events(self):
        return [
            {**self._event(index), "rating": rating, "action_key": f"review.{rating}",
             "trigger_key": f"scheduler.review.{rating}"}
            for index, rating in enumerate(("easy", "hard", "hard", "hard", "again", "good", "easy", "good"), start=1)
        ]

    def _assert_numeric_state_and_rollback(self):
        with self.app.app_context():
            db.session.expire_all()
            self.assertEqual(self._state_value("ease", decode_float), 2.0)
            for row in ReviewEvent.query.all():
                self.assertEqual(json.loads(row.payload_json)["_study_runtime"]["storage_profile"], "note-mysql-float-text.v1")
            # The LEGACY rollback is retired with the mirror tables (P10-09).
            with self.assertRaises(StudyAuthorityEnrollmentError) as refused:
                stage_legacy_authority_enrollment(db.session, learner_user_id=self.user_id, now_utc=datetime.utcnow())
            self.assertEqual(refused.exception.code, "LEGACY_ROLLBACK_RETIRED")
            db.session.rollback()
            self.assertEqual(ReviewEvent.query.count(), 8)

    def test_all_ratings_across_batches_have_lossless_numeric_projection_and_retry(self):
        events = self._numeric_events()
        first = self._batch_payload(1, events[:2])
        last = self._batch_payload(2, events[2:], final=True)
        self._http_admit(first)
        receipt = self._process(first["batch_id"])
        with self.app.app_context():
            self.assertEqual(self._state_value("ease", decode_float), 2.35)
        self._http_admit(last)
        final = self._process(last["batch_id"])
        self.assertEqual(self._process(first["batch_id"]), receipt)
        self.assertEqual(self._process(last["batch_id"]), final)
        self._assert_progress(8, session_status="committed")
        self._assert_numeric_state_and_rollback()

    def test_sync_note_commit_uses_same_numeric_profile_for_all_ratings(self):
        payload = {
            "schema_version": "study-commit.v3", "commit_id": str(uuid4()),
            "session_token": self.snapshot["session_token"], "snapshot_hash": self.snapshot["snapshot_hash"],
            "events": self._numeric_events(), "final_states": [],
        }
        path = f"/api/study/sessions/{self.snapshot['session_id']}/commit"
        response = self.client.post(path, json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        repeated = self.client.post(path, json=payload)
        self.assertEqual(repeated.status_code, 200, repeated.get_json())
        self.assertEqual(repeated.get_json(), response.get_json())
        self._assert_progress(8, session_status="committed")
        self._assert_numeric_state_and_rollback()

    def test_direct_note_answers_use_same_numeric_profile_for_all_ratings(self):
        originals = []
        for event in self._numeric_events():
            payload = {"rating": event["rating"], "operation_key": event["operation_key"],
                       "scope": "deck", "scope_id": self.deck_id}
            path = f"/api/study/{event['card_id']}/answer"
            response = self.client.post(path, json=payload)
            self.assertEqual(response.status_code, 200, response.get_json())
            originals.append((path, payload, response.get_json()))
            repeated = self.client.post(path, json=payload)
            self.assertEqual(repeated.status_code, 200, repeated.get_json())
            self.assertTrue(repeated.get_json()["authority"]["replayed"])
            self.assertEqual(repeated.get_json()["applied_interval"], response.get_json()["applied_interval"])
        path, payload, original = originals[0]
        repeated = self.client.post(path, json=payload)
        self.assertEqual(repeated.status_code, 200, repeated.get_json())
        self.assertEqual(repeated.get_json()["authority"]["authority_revision"], original["authority"]["authority_revision"])
        self.assertEqual(repeated.get_json()["applied_interval"], original["applied_interval"])
        self._assert_progress(8)
        self._assert_numeric_state_and_rollback()

    def test_two_batches_continue_same_note_and_project_every_sibling(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)], final=True)
        receipt = self._process(first)
        self.assertEqual(receipt["applied_event_count"], 1)
        self.assertFalse(receipt["is_final"])
        self._assert_progress(1)
        self.assertEqual(self._process(first), receipt)
        final_receipt = self._process(second)
        self.assertEqual(final_receipt["applied_event_count"], 1)
        self.assertEqual(final_receipt["cumulative_event_count"], 2)
        self._assert_progress(2, session_status="committed")
        self.assertEqual(self._process(second), final_receipt)
        with self.app.app_context():
            self.assertEqual(StudySessionCommit.query.count(), 1)

    def test_fractional_browser_clock_uses_note_storage_precision_before_replay(self):
        first_event = {**self._event(1), "scheduler_offset_ms": 1283}
        second_event = {**self._event(2), "scheduler_offset_ms": 1999}
        first = self._batch_payload(1, [first_event])
        second = self._batch_payload(2, [second_event], final=True)
        self._http_admit(first)
        first_receipt = self._process(first["batch_id"])
        self._http_admit(second)
        final_receipt = self._process(second["batch_id"])
        self.assertEqual(self._process(first["batch_id"]), first_receipt)
        self.assertEqual(self._process(second["batch_id"]), final_receipt)
        self._assert_progress(2, session_status="committed")
        with self.app.app_context():
            session = db.session.get(StudySession, self.snapshot["session_id"])
            expected = session.opened_at + timedelta(seconds=1)
            self.assertTrue(all(row.reviewed_at == expected for row in ReviewEvent.query.all()))
            self.assertEqual(self._state_value("last_review_at", decode_datetime), expected)
            stored = StudySessionBatch.query.filter_by(batch_id=second["batch_id"]).one()
            self.assertEqual(json.loads(stored.payload_json)["events"][0]["scheduler_offset_ms"], 1999)

    def test_second_batch_cannot_run_before_first(self):
        self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)])
        with self.assertRaises(StudySessionError) as failure:
            self._process(second)
        self.assertEqual(failure.exception.code, "NOTE_BATCH_PREDECESSOR_PENDING")
        self._assert_progress(0)

    def test_final_empty_batch_finishes_without_repeating_actions(self):
        first = self._admit(1, [self._event(1)])
        final = self._admit(2, [], final=True)
        self._process(first)
        receipt = self._process(final)
        self.assertEqual(receipt["applied_event_count"], 0)
        self._assert_progress(1, session_status="committed")

    def test_later_fault_rolls_back_new_actions_but_preserves_prior_batch(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2), self._event(3)], final=True)
        self._process(first)
        from app.services import study_session_service
        original = study_session_service.apply_idempotent_existing_state_note_review
        calls = 0

        def fail_after_second_action(*args, **kwargs):
            nonlocal calls
            calls += 1
            result = original(*args, **kwargs)
            if calls == 2:
                raise RuntimeError("injected batch failure after writes")
            return result

        with patch.object(study_session_service, "apply_idempotent_existing_state_note_review", side_effect=fail_after_second_action):
            with self.assertRaisesRegex(RuntimeError, "injected batch failure"):
                self._process(second)
        self._assert_progress(1)
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.filter_by(batch_id=second).one().status, "enqueued")
        self._process(second)
        self._assert_progress(3, session_status="committed")

    def test_intervening_external_action_is_not_owned_by_the_batch_chain(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)])
        self._process(first)
        response = self.client.post(
            f"/api/study/{self.snapshot['cards'][0]['card_id']}/answer",
            json={"rating": "good", "scope": "deck", "scope_id": self.deck_id, "operation_key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.assertRaises(StudySessionError) as failure:
            self._process(second)
        self.assertEqual(failure.exception.code, "AUTHORITY_STATE_CONFLICT")
        self._assert_progress(2)

    def test_corrupt_prior_receipt_cannot_advance_another_batch(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)])
        self._process(first)
        with self.app.app_context():
            receipt = StudyAuthorityCommandReceipt.query.one()
            receipt.response_payload_hash = b"x" * 32
            db.session.commit()
        with self.assertRaises(StudySessionError) as failure:
            self._process(second)
        self.assertEqual(failure.exception.code, "AUTHORITY_RECEIPT_CORRUPT")
        self._assert_progress(1)

    def test_admitted_batch_can_finish_after_lease_expiry(self):
        first = self._admit(1, [self._event(1)], final=True)
        with self.app.app_context():
            expires_at = db.session.get(StudySession, self.snapshot["session_id"]).expires_at
        self._process(first, now=expires_at + timedelta(minutes=1))
        self._assert_progress(1, session_status="committed")

    def test_unknown_admission_does_not_create_progress(self):
        with self.assertRaises(StudySessionError) as failure:
            self._process(str(uuid4()))
        self.assertEqual(failure.exception.code, "BATCH_ADMISSION_REQUIRED")
        self._assert_progress(0)

    def test_missing_prior_command_receipt_cannot_be_reapplied(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)])
        self._process(first)
        with self.app.app_context():
            db.session.delete(StudyAuthorityCommandReceipt.query.one())
            db.session.commit()
        with self.assertRaises(StudySessionError) as failure:
            self._process(second)
        self.assertEqual(failure.exception.code, "NOTE_BATCH_EVIDENCE_INVALID")
        with self.app.app_context():
            self.assertEqual(StudyProgressSubject.query.one().authority_revision, 1)
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 0)

    def test_corrupt_batch_receipt_rejects_both_replay_and_continuation(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)])
        self._process(first)
        with self.app.app_context():
            batch = StudySessionBatch.query.filter_by(batch_id=first).one()
            response = json.loads(batch.response_json)
            response["updated_cards"] = []
            batch.response_json = json.dumps(response)
            db.session.commit()
        for batch_id in (first, second):
            with self.subTest(batch_id=batch_id), self.assertRaises(StudySessionError) as failure:
                self._process(batch_id)
            self.assertEqual(failure.exception.code, "NOTE_BATCH_EVIDENCE_INVALID")
        self._assert_progress(1)

    def test_rehashed_prior_payload_still_requires_original_command_fingerprint(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)])
        self._process(first)
        with self.app.app_context():
            batch = StudySessionBatch.query.filter_by(batch_id=first).one()
            payload = json.loads(batch.payload_json)
            payload["events"][0]["duration_ms"] += 1
            batch.payload_json = json.dumps(payload)
            batch.request_hash = canonical_digest(payload)
            response = json.loads(batch.response_json)
            response.pop("receipt_hash")
            response["request_hash"] = batch.request_hash
            response["receipt_hash"] = canonical_digest(response)
            batch.response_json = json.dumps(response)
            db.session.commit()
        with self.assertRaises(StudySessionError) as failure:
            self._process(second)
        self.assertEqual(failure.exception.code, "AUTHORITY_OPERATION_REUSED")
        self._assert_progress(1)

    def test_changed_epoch_rejects_continuation(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)])
        self._process(first)
        with self.app.app_context():
            enrollment = StudyAuthorityEnrollment.query.one()
            enrollment.epoch += 1
            db.session.commit()
        with self.assertRaises(StudySessionError) as failure:
            self._process(second)
        self.assertEqual(failure.exception.code, "SESSION_AUTHORITY_EPOCH_CONFLICT")
        self._assert_progress(1)

    def test_sequence_gap_or_duplicate_rejects_before_any_write(self):
        second = self._admit(2, [self._event(1)])
        with self.assertRaises(StudySessionError) as gap:
            self._process(second)
        self.assertEqual(gap.exception.code, "NOTE_BATCH_ORDER_CONFLICT")
        self._admit(1, [])
        self._admit(1, [])
        with self.assertRaises(StudySessionError) as duplicate:
            self._process(second)
        self.assertEqual(duplicate.exception.code, "NOTE_BATCH_ORDER_CONFLICT")
        self._assert_progress(0)

    def test_final_batch_cannot_abandon_a_later_admission(self):
        first = self._admit(1, [self._event(1)], final=True)
        self._admit(2, [self._event(2)])
        with self.assertRaises(StudySessionError) as failure:
            self._process(first)
        self.assertEqual(failure.exception.code, "BATCH_AFTER_FINAL")
        self._assert_progress(0)

    def test_payload_hash_and_late_admission_are_not_accepted(self):
        first = self._admit(1, [self._event(1)])
        with self.app.app_context():
            batch = StudySessionBatch.query.filter_by(batch_id=first).one()
            valid_hash = batch.request_hash
            batch.request_hash = "0" * 64
            db.session.commit()
        with self.assertRaises(StudySessionError) as corrupted:
            self._process(first)
        self.assertEqual(corrupted.exception.code, "NOTE_BATCH_EVIDENCE_INVALID")
        with self.app.app_context():
            batch = StudySessionBatch.query.filter_by(batch_id=first).one()
            batch.request_hash = valid_hash
            batch.enqueued_at = db.session.get(StudySession, self.snapshot["session_id"]).expires_at + timedelta(seconds=1)
            db.session.commit()
        with self.assertRaises(StudySessionError) as late:
            self._process(first)
        self.assertEqual(late.exception.code, "NOTE_BATCH_EVIDENCE_INVALID")
        self._assert_progress(0)

    def test_cancelled_session_is_not_resurrected_by_an_admitted_batch(self):
        first = self._admit(1, [self._event(1)])
        with self.app.app_context():
            db.session.get(StudySession, self.snapshot["session_id"]).status = "cancelled"
            db.session.commit()
        with self.assertRaises(StudySessionError) as failure:
            self._process(first)
        self.assertEqual(failure.exception.code, "SESSION_NOT_OPEN")
        self._assert_progress(0, session_status="cancelled")

    def test_cumulative_event_bound_is_enforced_before_writes(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)])
        self._process(first)
        with patch("app.services.study_session_service.MAX_COMMIT_EVENTS", 1):
            with self.assertRaises(StudySessionError) as failure:
                self._process(second)
        self.assertEqual(failure.exception.code, "COMMIT_TOO_LARGE")
        self._assert_progress(1)

    def test_uncertain_commit_retry_uses_completed_batch_receipt(self):
        first = self._admit(1, [self._event(1)], final=True)
        with self.app.app_context():
            commit = db.session.commit

            def committed_but_disconnected():
                commit()
                raise RuntimeError("acknowledgement lost")

            with patch.object(db.session, "commit", side_effect=committed_but_disconnected):
                with self.assertRaisesRegex(RuntimeError, "acknowledgement lost"):
                    commit_note_study_session_batch(
                        user=db.session.get(User, self.user_id),
                        session_id=self.snapshot["session_id"], batch_id=first,
                    )
            self.assertFalse(db.session().in_transaction())
        receipt = self._process(first)
        self.assertEqual(receipt["applied_event_count"], 1)
        self._assert_progress(1, session_status="committed")

    def test_production_async_admission_remains_fail_closed_without_consumer(self):
        payload = {"schema_version": "study-batch.v3", "events": [self._event(1)]}
        response = self.client.post(f"/api/study/sessions/{self.snapshot['session_id']}/batch", json=payload)
        self.assertEqual(response.status_code, 503, response.get_json())
        self.assertEqual(response.get_json()["error"], "ASYNC_BATCH_DISABLED")
        with patch.dict(self.app.config, STUDY_ASYNC_BATCH_ENABLED=True, TESTING=False):
            response = self.client.post(f"/api/study/sessions/{self.snapshot['session_id']}/batch", json=payload)
        self.assertEqual(response.status_code, 503, response.get_json())
        self.assertEqual(response.get_json()["error"], "ASYNC_BATCH_WORKER_UNAVAILABLE")
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.count(), 0)
        self._assert_progress(0)

    def test_interleaved_notes_keep_independent_cross_batch_revision_chains(self):
        self._cleanup()
        self._seed(note_count=2)
        first_card, second_card = self.snapshot["cards"]
        first = self._admit(1, [self._event(1, card=first_card), self._event(2, card=second_card)])
        second = self._admit(2, [self._event(3, card=second_card), self._event(4, card=first_card)], final=True)
        self._process(first)
        receipt = self._process(second)
        self.assertEqual(receipt["applied_event_count"], 2)
        self.assertEqual(receipt["cumulative_event_count"], 4)
        with self.app.app_context():
            self.assertEqual(
                [row.authority_revision for row in StudyProgressSubject.query.order_by(StudyProgressSubject.id)], [2, 2])
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(ReviewEvent.query.count(), 4)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 4)
            self.assertEqual(StudySessionCommit.query.count(), 1)

    def test_final_flag_must_be_a_boolean_even_with_matching_admission_hash(self):
        first = self._admit(1, [self._event(1)], final=True)
        with self.app.app_context():
            batch = StudySessionBatch.query.filter_by(batch_id=first).one()
            payload = json.loads(batch.payload_json)
            payload["is_final"] = "false"
            batch.payload_json = json.dumps(payload)
            batch.request_hash = canonical_digest(payload)
            db.session.commit()
        with self.assertRaises(StudySessionError) as failure:
            self._process(first)
        self.assertEqual(failure.exception.code, "NOTE_BATCH_EVIDENCE_INVALID")
        self._assert_progress(0)

    def test_failed_predecessor_is_a_terminal_conflict_not_pending_work(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)], final=True)
        with self.app.app_context():
            StudySessionBatch.query.filter_by(batch_id=first).one().status = "failed"
            db.session.commit()
        with self.assertRaises(StudySessionError) as failure:
            self._process(second)
        self.assertEqual(failure.exception.code, "BATCH_PREDECESSOR_FAILED")
        self._assert_progress(0)

    def test_http_admission_dispatches_two_note_batches_without_legacy_writer(self):
        first = self._batch_payload(1, [self._event(1)])
        second = self._batch_payload(2, [self._event(2)], final=True)
        self._http_admit(first)
        self._http_admit(second)
        with self.app.app_context(), patch(
            "app.services.study_worker_service.deserialize_card_state",
            side_effect=AssertionError("NOTE must not enter the legacy Card worker replay"),
        ):
            # The worker's imported replay helper is only used by its legacy
            # branch; canonical NOTE replay has its own session entry point.
            result = drain_study_queue()
            self.assertEqual(result["processed_count"], 2, result)
            self.assertFalse(db.session().in_transaction())
        self._assert_progress(2, session_status="committed")
        receipt = self._http_admit(second)
        self.assertEqual(receipt["status"], "already_processed")
        self.assertEqual(receipt["receipt"]["cumulative_event_count"], 2)

    def test_note_http_admission_rejects_order_overlap_and_storage_overflow(self):
        invalid = self._batch_payload(2, [self._event(1)])
        self.assertEqual(self._http_admit(invalid, expected=409)["error"], "NOTE_BATCH_ORDER_CONFLICT")
        first = self._batch_payload(1, [self._event(1)])
        self._http_admit(first)
        changed = {**first, "commit_reason": "manual_exit"}
        self.assertEqual(self._http_admit(changed, expected=409)["error"], "BATCH_IDEMPOTENCY_CONFLICT")
        duplicate = self._batch_payload(2, [{**first["events"][0], "sequence": 2}])
        self.assertEqual(self._http_admit(duplicate, expected=409)["error"], "DUPLICATE_EVENT_ID")
        large = self._batch_payload(2, [self._event(2)])
        large["padding"] = "x" * (61 * 1024)
        self.assertEqual(self._http_admit(large, expected=413)["error"], "BATCH_TOO_LARGE")
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.count(), 1)
        self._assert_progress(0)

    def test_note_queue_loss_recovers_and_missing_predecessor_hint_does_not_stall(self):
        self._http_admit(self._batch_payload(1, [self._event(1)]))
        self._http_admit(self._batch_payload(2, [self._event(2)], final=True))
        with self.app.app_context():
            lost_first = pop_study_batch(timeout=0)
            self.assertEqual(lost_first["schema_version"], "study-note-batch-job.v1")
            self.assertNotIn("events", lost_first)
            # Queue is nonempty: only the second hint remains, while the first
            # admission survives solely in MySQL.
            self.assertEqual(drain_study_queue()["retrying_count"], 1)
            self.assertEqual(drain_study_queue()["processed_count"], 2)
        self._assert_progress(2, session_status="committed")

    def test_note_worker_retry_budget_survives_queue_loss(self):
        self._http_admit(self._batch_payload(1, [self._event(1)], final=True))
        clear_study_queue()
        with self.app.app_context():
            self.assertEqual(recover_admitted_study_batches()["requeued_count"], 1)
            job = pop_study_batch(timeout=0)
            with patch("app.services.study_worker_service.commit_note_study_session_batch", side_effect=RuntimeError("temporary fault")):
                result = process_single_study_batch(job)
            self.assertEqual(result["status"], "retrying")
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(StudySessionBatch.query.one().attempt_count, 1)
            db.session.rollback()
            clear_study_queue()
            self.assertEqual(drain_study_queue()["processed_count"], 1)
            self.assertEqual(StudySessionBatch.query.one().attempt_count, 1)
        self._assert_progress(1, session_status="committed")

    def test_note_worker_rejects_forged_job_without_consuming_valid_admission(self):
        self._http_admit(self._batch_payload(1, [self._event(1)]))
        with self.app.app_context():
            job = pop_study_batch(timeout=0)
            forged = {**job, "events": []}
            result = process_single_study_batch(forged)
            self.assertEqual(result["error_code"], "BATCH_IDEMPOTENCY_CONFLICT")
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(process_single_study_batch(job)["status"], "completed")
        self._assert_progress(1)

    def test_async_commit_envelope_executes_via_note_dispatch(self):
        payload = self._batch_payload(1, [self._event(1)])
        payload["schema_version"] = "study-commit.v3"
        payload["commit_id"] = payload.pop("batch_id")
        payload.pop("batch_sequence")
        payload.pop("commit_reason")
        payload.pop("is_final")
        self._http_admit(payload, path="commit?async=1")
        with self.app.app_context():
            self.assertEqual(drain_study_queue()["processed_count"], 1)
        self._assert_progress(1, session_status="committed")

    def test_batch_status_reports_durable_completion_and_is_owner_scoped(self):
        payload = self._batch_payload(1, [self._event(1)], final=True)
        self._http_admit(payload)
        url = f"/api/study/sessions/{self.snapshot['session_id']}/batch/{payload['batch_id']}"
        pending = self.client.get(url)
        self.assertEqual(pending.status_code, 200)
        self.assertEqual(pending.get_json()["status"], "enqueued")
        self.assertNotIn("receipt", pending.get_json())
        self.assertIn("no-store", pending.headers["Cache-Control"])
        with self.app.app_context():
            self.assertEqual(drain_study_queue()["processed_count"], 1)
            other = User(username="other-batch", email="other-batch@example.test")
            db.session.add(other)
            db.session.commit()
            other_id = other.id
        completed = self.client.get(url).get_json()
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["receipt"]["applied_event_count"], 1)
        other_client = self.app.test_client()
        with other_client.session_transaction() as login:
            login["_user_id"] = str(other_id)
            login["_fresh"] = True
        self.assertEqual(other_client.get(url).status_code, 404)
        with self.app.app_context():
            batch = StudySessionBatch.query.one()
            batch.response_json = "{}"
            db.session.commit()
        broken = self.client.get(url)
        self.assertEqual(broken.status_code, 409)
        self.assertEqual(broken.get_json()["error"], "NOTE_BATCH_EVIDENCE_INVALID")

    def test_note_worker_permanent_conflict_is_durable_and_visible(self):
        payload = self._batch_payload(1, [self._event(1)], final=True)
        self._http_admit(payload)
        response = self.client.post(
            f"/api/study/{self.snapshot['cards'][0]['card_id']}/answer",
            json={"rating": "good", "scope": "deck", "scope_id": self.deck_id, "operation_key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(drain_study_queue()["failed_count"], 1)
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(recover_admitted_study_batches()["requeued_count"], 0)
        status = self.client.get(f"/api/study/sessions/{self.snapshot['session_id']}/batch/{payload['batch_id']}").get_json()
        self.assertEqual(status["status"], "failed")
        self.assertEqual(status["error_code"], "AUTHORITY_STATE_CONFLICT")
        self.assertEqual(status["attempt_count"], 0)
        self.assertNotIn("receipt", status)
        self._assert_progress(1)

    def test_note_worker_uncertain_commit_keeps_terminal_receipt(self):
        self._http_admit(self._batch_payload(1, [self._event(1)], final=True))
        with self.app.app_context():
            job = pop_study_batch(timeout=0)
            commit = db.session.commit

            def uncertain():
                commit()
                raise RuntimeError("lost acknowledgement")

            with patch.object(db.session, "commit", side_effect=uncertain):
                result = process_single_study_batch(job)
            self.assertEqual(result["status"], "already_processed")
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(StudySessionBatch.query.one().attempt_count, 0)
        self._assert_progress(1, session_status="committed")

    def test_note_admission_validates_wire_and_value_types_before_persisting(self):
        cases = [
            ("operation_key", "wrong-operation", 409, "WIRE_CONTRACT_MISMATCH"),
            ("base_authority_revision", "42", 422, "WIRE_CONTRACT_MISMATCH"),
            ("sequence", True, 422, "INVALID_REVIEW_EVENT_PAYLOAD"),
            ("scheduler_offset_ms", -1, 422, "INVALID_EVENT_TIME"),
            ("card_id", {}, 422, "INVALID_REVIEW_EVENT_PAYLOAD"),
            ("rating", [], 422, "INVALID_REVIEW_EVENT_PAYLOAD"),
        ]
        for field, value, status, code in cases:
            with self.subTest(field=field):
                event = {**self._event(1), field: value}
                response = self._http_admit(self._batch_payload(1, [event]), expected=status)
                self.assertEqual(response["error"], code)
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.count(), 0)
        self._assert_progress(0)

    def test_sync_commit_cannot_overtake_an_admitted_note_stream(self):
        batch = self._batch_payload(1, [self._event(1)], final=True)
        self._http_admit(batch)
        sync_payload = {
            **batch, "schema_version": "study-commit.v3", "commit_id": str(uuid4()),
        }
        response = self.client.post(f"/api/study/sessions/{self.snapshot['session_id']}/commit", json=sync_payload)
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "SESSION_HAS_ASYNC_BATCHES")
        self._assert_progress(0)
        with self.app.app_context():
            self.assertEqual(drain_study_queue()["processed_count"], 1)
        self._assert_progress(1, session_status="committed")

    def _session_status(self):
        response = self.client.get(f"/api/study/sessions/{self.snapshot['session_id']}")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn(self.snapshot["session_token"], response.get_data(as_text=True))
        return response.get_json()

    def test_session_status_accepts_own_completed_prefix_without_repinning(self):
        self.assertFalse(self._session_status()["stale"])
        first = self._admit(1, [self._event(1)])
        final = self._admit(2, [self._event(2)], final=True)
        pending = self._session_status()
        self.assertFalse(pending["stale"])
        self.assertEqual(pending["batch_stream"]["pending_batch_count"], 2)
        self._process(first)
        progress = self._session_status()
        self.assertFalse(progress["stale"], progress)
        self.assertEqual(progress["batch_stream"], {
            "schema_version": "study-note-batch-stream.v1", "admitted_batch_count": 2,
            "last_completed_batch_sequence": 1, "completed_event_count": 1,
            "pending_batch_count": 1, "failed_batch_id": None,
            "final_batch_id": final, "final_batch_status": "enqueued",
        })
        self._assert_progress(1)
        self._process(final)
        terminal = self._session_status()
        self.assertFalse(terminal["stale"])
        self.assertEqual(terminal["status"], "committed")
        self.assertEqual(terminal["batch_stream"]["final_batch_status"], "completed")

    def test_session_status_is_strictly_read_only_after_a_batch(self):
        self._process(self._admit(1, [self._event(1)]))
        writes = []

        def record_writes(_connection, _cursor, statement, _parameters, _context, _executemany):
            if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}:
                writes.append(statement)

        with self.app.app_context():
            engine = db.engine
        sql_event.listen(engine, "before_cursor_execute", record_writes)
        try:
            for _ in range(2):
                self.assertFalse(self._session_status()["stale"])
        finally:
            sql_event.remove(engine, "before_cursor_execute", record_writes)
        self.assertEqual(writes, [])
        self._assert_progress(1)

    def test_session_status_detects_external_review_after_own_batch(self):
        self._process(self._admit(1, [self._event(1)]))
        answer = self.client.post(
            f"/api/study/{self.snapshot['cards'][0]['card_id']}/answer",
            json={"rating": "good", "scope": "deck", "scope_id": self.deck_id, "operation_key": str(uuid4())},
        )
        self.assertEqual(answer.status_code, 200)
        status = self._session_status()
        self.assertTrue(status["stale"])
        self.assertEqual(status["stale_reason"], "AUTHORITY_STATE_CONFLICT")
        self._assert_progress(2)

    def test_session_status_checks_untouched_notes_in_the_lease(self):
        self._cleanup()
        self._seed(note_count=2)
        first_card, other_card = self.snapshot["cards"]
        self._process(self._admit(1, [self._event(1, card=first_card)]))
        self.assertFalse(self._session_status()["stale"])
        answer = self.client.post(
            f"/api/study/{other_card['card_id']}/answer",
            json={"rating": "good", "scope": "deck", "scope_id": self.deck_id, "operation_key": str(uuid4())},
        )
        self.assertEqual(answer.status_code, 200)
        status = self._session_status()
        self.assertTrue(status["stale"])
        self.assertEqual(status["stale_reason"], "AUTHORITY_STATE_CONFLICT")

    def test_session_status_does_not_repair_a_missing_row(self):
        with self.app.app_context():
            StudyProgressSubject.query.delete()
            db.session.commit()
        status = self._session_status()
        self.assertTrue(status["stale"])
        self.assertEqual(status["stale_reason"], "INCOMPLETE_SESSION_AUTHORITY_SUBJECTS")
        with self.app.app_context():
            self.assertEqual(StudyProgressSubject.query.count(), 0)

    def test_session_status_rejects_rehashed_prior_payload(self):
        self._process(self._admit(1, [self._event(1)]))
        with self.app.app_context():
            batch = StudySessionBatch.query.one()
            payload = json.loads(batch.payload_json)
            payload["events"][0]["duration_ms"] += 1
            batch.payload_json = json.dumps(payload)
            batch.request_hash = canonical_digest(payload)
            receipt = json.loads(batch.response_json)
            receipt.pop("receipt_hash")
            receipt["request_hash"] = batch.request_hash
            receipt["receipt_hash"] = canonical_digest(receipt)
            batch.response_json = json.dumps(receipt)
            db.session.commit()
        status = self._session_status()
        self.assertTrue(status["stale"])
        self.assertEqual(status["stale_reason"], "AUTHORITY_OPERATION_REUSED")
        self._assert_progress(1)

    def test_session_status_rejects_corrupted_canonical_receipt(self):
        self._process(self._admit(1, [self._event(1)]))
        with self.app.app_context():
            StudyAuthorityCommandReceipt.query.one().response_payload_hash = b"x" * 32
            db.session.commit()
        status = self._session_status()
        self.assertTrue(status["stale"])
        self.assertEqual(status["stale_reason"], "AUTHORITY_RECEIPT_CORRUPT")

    def test_session_status_reports_failed_batch_without_reapplying(self):
        first = self._admit(1, [self._event(1)])
        with self.app.app_context():
            StudySessionBatch.query.one().status = "failed"
            db.session.commit()
        status = self._session_status()
        self.assertTrue(status["stale"])
        self.assertEqual(status["stale_reason"], "BATCH_FAILED")
        self.assertEqual(status["batch_stream"]["failed_batch_id"], first)
        self._assert_progress(0)

    def test_session_status_rejects_a_gap_and_corrupted_receipt(self):
        batch_id = self._admit(2, [])
        self.assertEqual(self._session_status()["stale_reason"], "NOTE_BATCH_EVIDENCE_INVALID")
        with self.app.app_context():
            batch = StudySessionBatch.query.one()
            batch.batch_sequence = 1
            payload = json.loads(batch.payload_json)
            payload["batch_sequence"] = 1
            batch.payload_json = json.dumps(payload)
            batch.request_hash = canonical_digest(payload)
            db.session.commit()
        self._process(batch_id)
        self.assertFalse(self._session_status()["stale"])
        with self.app.app_context():
            StudySessionBatch.query.one().response_json = "{}"
            db.session.commit()
        self.assertEqual(self._session_status()["stale_reason"], "NOTE_BATCH_EVIDENCE_INVALID")

    def test_terminal_batch_status_remains_historical_after_external_review(self):
        self._process(self._admit(1, [self._event(1)], final=True))
        response = self.client.post(
            f"/api/study/{self.snapshot['cards'][0]['card_id']}/answer",
            json={"rating": "good", "scope": "deck", "scope_id": self.deck_id, "operation_key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 200)
        status = self._session_status()
        self.assertFalse(status["stale"])
        self.assertEqual(status["status"], "committed")
        self.assertEqual(status["batch_stream"]["completed_event_count"], 1)

    def test_live_production_worker_negotiates_before_learner_locks(self):
        from app.services import study_session_service

        order = []
        route_lock = study_session_service.lock_study_authority_route
        def ready(wire):
            self.assertEqual(wire, "study-session.v4")
            order.append("ready")
            return True
        def lock(*args, **kwargs):
            order.append("lock")
            return route_lock(*args, **kwargs)
        with patch.dict(self.app.config, TESTING=False, STUDY_ASYNC_BATCH_ENABLED=True), patch.object(
            study_session_service, "has_ready_study_worker", side_effect=ready,
        ), patch.object(study_session_service, "lock_study_authority_route", side_effect=lock):
            response = self.client.post("/api/study/sessions", json={
                "scope": "deck", "scope_id": self.deck_id, "composition_id": self.composition_id,
                "accepted_session_schema_versions": ["study-session.v4"],
                "accepted_batch_schema_versions": ["study-batch.v3"],
            })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["batch_transport"], "study-note-batch-transport.v1")
        self.assertEqual(order[:2], ["ready", "lock"])
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_admission_rechecks_readiness_and_leaves_pending_work_unmodified(self):
        payload = self._batch_payload(1, [self._event(1)], final=True)
        for path in ("batch", "commit?async=1"):
            with self.subTest(path=path), patch.dict(self.app.config, TESTING=False, STUDY_ASYNC_BATCH_ENABLED=True), patch(
                "app.services.study_session_service.has_ready_study_worker", return_value=False,
            ) as ready, patch("app.services.study_session_service.lock_study_authority_route") as lock:
                response = self.client.post(f"/api/study/sessions/{self.snapshot['session_id']}/{path}", json=payload)
                self.assertEqual(response.status_code, 503, response.get_json())
                self.assertEqual(response.get_json()["error"], "ASYNC_BATCH_WORKER_UNAVAILABLE")
                ready.assert_called_once_with("study-session.v4")
                lock.assert_not_called()
                self.assertIn("no-store", response.headers["Cache-Control"])
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.count(), 0)
            self.assertEqual(db.session.get(StudySession, self.snapshot["session_id"]).status, "open")
        self._assert_progress(0)

    def test_production_admission_commits_before_push_and_receipt_survives_worker_outage(self):
        from app.services.study_queue_service import enqueue_study_batch

        payload = self._batch_payload(1, [self._event(1)], final=True)
        def enqueue(job):
            self.assertFalse(db.session().in_transaction())
            return enqueue_study_batch(job)
        with patch.dict(self.app.config, TESTING=False, STUDY_ASYNC_BATCH_ENABLED=True), patch(
            "app.services.study_session_service.has_ready_study_worker", return_value=True,
        ), patch("app.services.study_queue_service.enqueue_study_batch", side_effect=enqueue):
            response = self.client.post(f"/api/study/sessions/{self.snapshot['session_id']}/batch", json=payload)
        self.assertEqual(response.status_code, 202, response.get_json())
        self.assertEqual(response.get_json()["status"], "enqueued")
        with patch.dict(self.app.config, TESTING=False, STUDY_ASYNC_BATCH_ENABLED=False), patch(
            "app.services.study_session_service.has_ready_study_worker", return_value=False,
        ) as ready:
            pending = self.client.get(f"/api/study/sessions/{self.snapshot['session_id']}/batch/{payload['batch_id']}")
            self.assertEqual(pending.status_code, 200)
            self.assertEqual(pending.get_json()["status"], "enqueued")
            receipt = self._process(payload["batch_id"])
            response = self.client.get(f"/api/study/sessions/{self.snapshot['session_id']}/batch/{payload['batch_id']}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["receipt"], receipt)
            self.assertIn("no-store", response.headers["Cache-Control"])
            ready.assert_not_called()
        self._assert_progress(1, session_status="committed")

    def test_production_redis_failure_is_typed_unavailable_without_admission(self):
        with patch.dict(self.app.config, TESTING=False, STUDY_ASYNC_BATCH_ENABLED=True), patch(
            "app.services.study_worker_readiness_service.redis_client", side_effect=ConnectionError("unreachable"),
        ):
            response = self.client.post(
                f"/api/study/sessions/{self.snapshot['session_id']}/batch",
                json=self._batch_payload(1, [self._event(1)]),
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"], "ASYNC_BATCH_WORKER_UNAVAILABLE")
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.count(), 0)

    def test_note_batch_transport_is_negotiated_only_when_admission_can_serve(self):
        payload = {
            "scope": "deck", "scope_id": self.deck_id, "composition_id": self.composition_id,
            "accepted_session_schema_versions": ["study-session.v4"],
            "accepted_batch_schema_versions": ["study-batch.v3"],
        }
        for testing, enabled, accepted, ready, advertised in (
            (True, True, ["study-batch.v3"], False, True),
            (True, False, ["study-batch.v3"], True, False),
            (True, True, ["study-batch.v1"], True, False),
            (True, True, "study-batch.v3", True, False),
            (False, True, ["study-batch.v3"], False, False),
            (False, True, ["study-batch.v3"], True, True),
            (False, False, ["study-batch.v3"], True, False),
            (False, True, [], True, False),
        ):
            with self.subTest(testing=testing, enabled=enabled, accepted=accepted):
                with patch.dict(self.app.config, TESTING=testing, STUDY_ASYNC_BATCH_ENABLED=enabled), patch(
                    "app.services.study_session_service.has_ready_study_worker", return_value=ready,
                ):
                    response = self.client.post("/api/study/sessions", json={
                        **payload, "accepted_batch_schema_versions": accepted,
                    })
                self.assertEqual(response.status_code, 201, response.get_json())
                self.assertEqual("batch_transport" in response.get_json(), advertised)
                if advertised:
                    self.assertEqual(response.get_json()["batch_transport"], "study-note-batch-transport.v1")


if __name__ == "__main__":
    unittest.main()
