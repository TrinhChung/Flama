"""Integration coverage for frontend-driven study sessions."""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.services.anki_scheduler import _day_index, applyAnswer
from app.services.study_algorithm_registry import (
    AlgorithmLifecycleState,
    AlgorithmResolutionPurpose,
    StudyAlgorithmNotFoundError,
    resolve_study_algorithm,
)
from app.services.study_session_service import (
    deserialize_card_state,
    deserialize_deck_options,
    serialize_card_state,
)
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_session import StudySession
from models.template import Template
from models.user import User


class StudySessionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User(username="student", email="student@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id
            deck = Deck(name="Session Deck", owner_user_id=user.id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "student@example.com", "password": "password"},
            follow_redirects=False,
        )
        note_type_response = self.client.post(
            "/api/note-types",
            json={
                "name": "Session Type",
                "field_defs": [
                    {
                        "name": "Word",
                        "field_type": "text",
                        "position": 0,
                        "required": True,
                    }
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "{{Word}}",
                    "back_html": "{{Word}}",
                },
            },
        )
        self.assertEqual(note_type_response.status_code, 201)
        self.note_type_id = note_type_response.get_json()["id"]
        note_response = self.client.post(
            "/api/notes",
            json={
                "note_type_id": self.note_type_id,
                "deck_id": self.deck_id,
                "field_values": {"Word": "猫"},
            },
        )
        self.assertEqual(note_response.status_code, 201)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _open_session(self):
        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _open_session_v3(self):
        previous = self.app.config["STUDY_WIRE_V3_ENABLED"]
        self.app.config["STUDY_WIRE_V3_ENABLED"] = True
        try:
            response = self.client.post(
                "/api/study/sessions",
                json={
                    "scope": "deck",
                    "scope_id": self.deck_id,
                    "accepted_session_schema_versions": [
                        "study-session.v3",
                        "study-session.v2",
                    ],
                },
            )
        finally:
            self.app.config["STUDY_WIRE_V3_ENABLED"] = previous
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    @staticmethod
    def _commit_payload(snapshot, *, commit_id=None):
        card = snapshot["cards"][0]
        is_v3 = snapshot["schema_version"] == "study-session.v3"
        event = {
            "event_id": str(uuid4()),
            "sequence": 1,
            "card_id": card["card_id"],
            "rating": "good",
            "policy_key": card["policy_key"],
            "scheduler_offset_ms": 1000,
            "duration_ms": 500,
        }
        if is_v3:
            policy = snapshot["policies"][card["policy_key"]]
            event.update(
                {
                    "action_key": "review.good",
                    "action_contract_version": "1",
                    "trigger_key": "scheduler.review.good",
                    "trigger_contract_version": "1",
                    "algorithm_key": snapshot["scheduler_algorithm"],
                    "algorithm_version": snapshot["algorithm_version"],
                    "config_schema_version": policy["config_schema_version"],
                    "config_hash": policy["config_hash"],
                    "study_session_id": snapshot["session_id"],
                }
            )
        return {
            "schema_version": "study-commit.v2" if is_v3 else "study-commit.v1",
            "commit_id": commit_id or str(uuid4()),
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "events": [event],
            "final_states": [],
        }

    def test_open_returns_self_contained_snapshot(self):
        snapshot = self._open_session()
        self.assertEqual(snapshot["schema_version"], "study-session.v2")
        self.assertTrue(snapshot["server_now_utc"].endswith(".000Z"))
        self.assertEqual(snapshot["scope"]["id"], str(self.deck_id))
        self.assertEqual(len(snapshot["cards"]), 1)
        card = snapshot["cards"][0]
        self.assertIn(card["policy_key"], snapshot["policies"])
        self.assertIn(card["template_key"], snapshot["templates"])
        self.assertIn(card["content_key"], snapshot["contents"])
        self.assertIn("compositions", snapshot)
        self.assertIn("composition_id", card)
        comp_id = card["composition_id"]
        self.assertIn(comp_id, snapshot["compositions"])
        self.assertEqual(snapshot["compositions"][comp_id]["mode_key"], "flashcard")
        self.assertEqual(card["base_revision"], 0)

        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            self.assertIsNotNone(session)
            self.assertEqual(session.status, "open")

    def test_wire_v3_is_capability_negotiated_and_flag_gated(self):
        previous = self.app.config["STUDY_WIRE_V3_ENABLED"]
        self.app.config["STUDY_WIRE_V3_ENABLED"] = True
        try:
            old_client = self._open_session()
        finally:
            self.app.config["STUDY_WIRE_V3_ENABLED"] = previous
        self.assertEqual(old_client["schema_version"], "study-session.v2")

        flag_off = self.client.post(
            "/api/study/sessions",
            json={
                "scope": "deck",
                "scope_id": self.deck_id,
                "accepted_session_schema_versions": [
                    "study-session.v3",
                    "study-session.v2",
                ],
            },
        )
        self.assertEqual(flag_off.status_code, 201, flag_off.get_json())
        self.assertEqual(flag_off.get_json()["schema_version"], "study-session.v2")

        v3 = self._open_session_v3()
        self.assertEqual(v3["schema_version"], "study-session.v3")
        with self.app.app_context():
            row = db.session.get(StudySession, v3["session_id"])
            self.assertEqual(row.wire_schema_version, "study-session.v3")

    def test_v3_commit_requires_exact_identity_and_paired_envelope(self):
        wrong_envelope_snapshot = self._open_session_v3()
        wrong_envelope = self._commit_payload(wrong_envelope_snapshot)
        wrong_envelope["schema_version"] = "study-commit.v1"
        response = self.client.post(
            f"/api/study/sessions/{wrong_envelope_snapshot['session_id']}/commit",
            json=wrong_envelope,
        )
        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(response.get_json()["error"], "UNSUPPORTED_COMMIT_SCHEMA")

        missing_snapshot = self._open_session_v3()
        missing = self._commit_payload(missing_snapshot)
        del missing["events"][0]["action_contract_version"]
        response = self.client.post(
            f"/api/study/sessions/{missing_snapshot['session_id']}/commit",
            json=missing,
        )
        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(response.get_json()["error"], "WIRE_CONTRACT_MISMATCH")

        mismatch_snapshot = self._open_session_v3()
        mismatch = self._commit_payload(mismatch_snapshot)
        mismatch["events"][0]["algorithm_version"] = "latest"
        response = self.client.post(
            f"/api/study/sessions/{mismatch_snapshot['session_id']}/commit",
            json=mismatch,
        )
        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(response.get_json()["error"], "WIRE_CONTRACT_MISMATCH")

        valid_snapshot = self._open_session_v3()
        response = self.client.post(
            f"/api/study/sessions/{valid_snapshot['session_id']}/commit",
            json=self._commit_payload(valid_snapshot),
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            event = ReviewEvent.query.filter_by(
                study_session_id=valid_snapshot["session_id"]
            ).one()
            payload = json.loads(event.payload_json)
            self.assertEqual(
                payload["provenance"]["wire_schema_version"],
                "study-session.v3",
            )
            self.assertEqual(
                payload["_study_runtime"]["action_contract_version"],
                "1",
            )

    def test_session_boundaries_resolve_algorithm_for_the_exact_purpose(self):
        with patch(
            "app.services.study_session_service.resolve_study_algorithm",
            wraps=resolve_study_algorithm,
        ) as resolver:
            snapshot = self._open_session()
        resolver.assert_called_once_with(
            "legacy-anki",
            "1.0.0",
            purpose=AlgorithmResolutionPurpose.NEW_SESSION,
        )

        with patch(
            "app.services.study_session_service.resolve_study_algorithm",
            wraps=resolve_study_algorithm,
        ) as resolver:
            status = self.client.get(
                f"/api/study/sessions/{snapshot['session_id']}"
            )
        self.assertEqual(status.status_code, 200, status.get_json())
        resolver.assert_called_once_with(
            "legacy-anki",
            "1.0.0",
            purpose=AlgorithmResolutionPurpose.EXISTING_LEASE,
        )

        with patch(
            "app.services.study_session_service.resolve_study_algorithm",
            wraps=resolve_study_algorithm,
        ) as resolver:
            committed = self.client.post(
                f"/api/study/sessions/{snapshot['session_id']}/commit",
                json=self._commit_payload(snapshot),
            )
        self.assertEqual(committed.status_code, 200, committed.get_json())
        resolver.assert_called_once_with(
            "legacy-anki",
            "1.0.0",
            purpose=AlgorithmResolutionPurpose.EXISTING_LEASE,
        )

    def test_retired_algorithm_commit_fails_before_any_review_write(self):
        snapshot = self._open_session()
        unavailable = StudyAlgorithmNotFoundError(
            "legacy-anki",
            "1.0.0",
            purpose=AlgorithmResolutionPurpose.EXISTING_LEASE,
            lifecycle_state=AlgorithmLifecycleState.RETIRED,
            reason="RETIRED",
        )

        with patch(
            "app.services.study_session_service.resolve_study_algorithm",
            side_effect=unavailable,
        ):
            response = self.client.post(
                f"/api/study/sessions/{snapshot['session_id']}/commit",
                json=self._commit_payload(snapshot),
            )

        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "ALGORITHM_UNAVAILABLE")
        self.assertEqual(response.get_json()["details"]["reason"], "RETIRED")
        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(session.status, "open")
            self.assertEqual(
                ReviewEvent.query.filter_by(
                    study_session_id=snapshot["session_id"],
                ).count(),
                0,
            )

    def test_retired_algorithm_status_fails_restore_closed(self):
        snapshot = self._open_session()
        unavailable = StudyAlgorithmNotFoundError(
            "legacy-anki",
            "1.0.0",
            purpose=AlgorithmResolutionPurpose.EXISTING_LEASE,
            lifecycle_state=AlgorithmLifecycleState.RETIRED,
            reason="RETIRED",
        )

        with patch(
            "app.services.study_session_service.resolve_study_algorithm",
            side_effect=unavailable,
        ):
            response = self.client.get(
                f"/api/study/sessions/{snapshot['session_id']}"
            )

        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "ALGORITHM_UNAVAILABLE")
        self.assertEqual(response.get_json()["details"]["reason"], "RETIRED")
        self.assertEqual(
            response.get_json()["details"]["purpose"],
            "existing-lease",
        )

    def test_commit_accepts_action_contract_and_rejects_mismatch(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        event = payload["events"][0]
        event.update(
            {
                "action_key": "review.good",
                "trigger_key": "scheduler.review.good",
                "trigger_contract_version": "1",
            }
        )
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.get_json())

        mismatch_snapshot = self._open_session()
        mismatch_payload = self._commit_payload(mismatch_snapshot)
        mismatch_payload["events"][0]["action_key"] = "review.easy"
        mismatch = self.client.post(
            f"/api/study/sessions/{mismatch_snapshot['session_id']}/commit",
            json=mismatch_payload,
        )
        self.assertEqual(mismatch.status_code, 422, mismatch.get_json())
        self.assertEqual(
            mismatch.get_json()["error"],
            "ACTION_CONTRACT_MISMATCH",
        )

    def test_review_payload_spoof_and_oversize_fail_without_partial_write(self):
        with self.app.app_context():
            card_id = Card.query.join(Note, Card.note_id == Note.id).one().id

        base_payload = {
            "rating": "good",
            "scope": "deck",
            "scope_id": self.deck_id,
        }
        spoofed = self.client.post(
            f"/api/study/{card_id}/answer",
            json={**base_payload, "source": "mcp"},
        )
        self.assertEqual(spoofed.status_code, 422, spoofed.get_json())
        self.assertEqual(
            spoofed.get_json()["error"],
            "REVIEW_EVENT_PAYLOAD_FIELD_NOT_ALLOWED",
        )

        oversized = self.client.post(
            f"/api/study/{card_id}/answer",
            json={**base_payload, "selection_id": "x" * 513},
        )
        self.assertEqual(oversized.status_code, 413, oversized.get_json())
        self.assertEqual(
            oversized.get_json()["error"],
            "REVIEW_EVENT_PAYLOAD_STRING_TOO_LONG",
        )

        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(CardProgress.query.count(), 0)

    def test_session_event_allowlist_failure_has_no_partial_write(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        payload["events"][0]["source_path"] = "native.mcp"
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(
            response.get_json()["error"],
            "REVIEW_EVENT_PAYLOAD_FIELD_NOT_ALLOWED",
        )
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(CardProgress.query.count(), 0)

    def test_status_reports_open_committed_and_expired_sessions(self):
        committed_snapshot = self._open_session()
        open_status = self.client.get(
            f"/api/study/sessions/{committed_snapshot['session_id']}"
        )
        self.assertEqual(open_status.status_code, 200, open_status.get_json())
        self.assertEqual(open_status.get_json()["status"], "open")

        commit = self.client.post(
            f"/api/study/sessions/{committed_snapshot['session_id']}/commit",
            json=self._commit_payload(committed_snapshot),
        )
        self.assertEqual(commit.status_code, 200, commit.get_json())
        committed_status = self.client.get(
            f"/api/study/sessions/{committed_snapshot['session_id']}"
        )
        self.assertEqual(committed_status.status_code, 200)
        self.assertEqual(committed_status.get_json()["status"], "committed")
        self.assertIsNotNone(committed_status.get_json()["committed_at"])

        expired_snapshot = self._open_session()
        with self.app.app_context():
            expired = db.session.get(StudySession, expired_snapshot["session_id"])
            expired.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.session.commit()
        expired_status = self.client.get(
            f"/api/study/sessions/{expired_snapshot['session_id']}"
        )
        self.assertEqual(expired_status.status_code, 200)
        self.assertEqual(expired_status.get_json()["status"], "expired")

    def test_status_reports_stale_when_note_or_template_updated(self):
        snapshot = self._open_session()
        status_res = self.client.get(
            f"/api/study/sessions/{snapshot['session_id']}"
        )
        self.assertEqual(status_res.status_code, 200)
        self.assertFalse(status_res.get_json()["stale"])

        with self.app.app_context():
            note = Note.query.first()
            note.updated_at = datetime.utcnow() + timedelta(seconds=10)
            db.session.commit()

        status_res = self.client.get(
            f"/api/study/sessions/{snapshot['session_id']}"
        )
        self.assertEqual(status_res.status_code, 200)
        self.assertTrue(status_res.get_json()["stale"])

        snapshot2 = self._open_session()
        with self.app.app_context():
            tmpl = Template.query.first()
            tmpl.updated_at = datetime.utcnow() + timedelta(seconds=10)
            db.session.commit()

        status_res2 = self.client.get(
            f"/api/study/sessions/{snapshot2['session_id']}"
        )
        self.assertEqual(status_res2.status_code, 200)
        self.assertTrue(status_res2.get_json()["stale"])

    def test_auto_finish_rejects_actionable_learning_card(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        payload["commit_reason"] = "auto_finish"

        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )

        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "SESSION_NOT_COMPLETE")
        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(session.status, "open")
            self.assertEqual(
                ReviewEvent.query.filter_by(
                    study_session_id=snapshot["session_id"],
                ).count(),
                0,
            )

    def test_auto_finish_accepts_card_graduated_from_final_learning_step(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        payload["commit_reason"] = "auto_finish"
        second_event = dict(payload["events"][0])
        second_event.update(
            {
                "event_id": str(uuid4()),
                "sequence": 2,
                "scheduler_offset_ms": 2000,
            }
        )
        payload["events"].append(second_event)

        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        result = response.get_json()
        self.assertEqual(result["commit_reason"], "auto_finish")
        self.assertEqual(result["updated_cards"][0]["state"]["type"], "review")

    def test_empty_owned_deck_can_open_and_commit(self):
        with self.app.app_context():
            empty_deck = Deck(
                name="Empty Deck",
                owner_user_id=self.user_id,
            )
            db.session.add(empty_deck)
            db.session.commit()
            empty_deck_id = empty_deck.id
        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": empty_deck_id},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        snapshot = response.get_json()
        self.assertEqual(snapshot["cards"], [])
        commit = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json={
                "schema_version": "study-commit.v1",
                "commit_id": str(uuid4()),
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": [],
                "final_states": [],
            },
        )
        self.assertEqual(commit.status_code, 200, commit.get_json())
        self.assertEqual(commit.get_json()["applied_event_count"], 0)
        self.assertEqual(commit.get_json()["commit_reason"], "manual_exit")

    def test_commit_replays_events_and_is_idempotent(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        receipt = response.get_json()
        self.assertEqual(receipt["applied_event_count"], 1)

        retry = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(retry.status_code, 200, retry.get_json())
        self.assertEqual(retry.get_json(), receipt)

        different_commit = dict(payload)
        different_commit["commit_id"] = str(uuid4())
        already_committed = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=different_commit,
        )
        self.assertEqual(already_committed.status_code, 409)
        self.assertEqual(
            already_committed.get_json()["error"],
            "SESSION_ALREADY_COMMITTED",
        )
        self.assertEqual(already_committed.get_json()["details"], receipt)

        card_id = snapshot["cards"][0]["card_id"]
        with self.app.app_context():
            progress = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=card_id,
            ).one()
            self.assertEqual(progress.reps, 1)
            self.assertEqual(progress.revision, 1)
            events = ReviewEvent.query.filter_by(
                user_id=self.user_id,
                card_id=card_id,
            ).all()
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].study_session_id, snapshot["session_id"])
            self.assertEqual(events[0].sequence_no, 1)
            self.assertEqual(events[0].scheduler_algorithm, "legacy-anki")
            self.assertEqual(events[0].algorithm_version, "1.0.0")
            runtime_metadata = json.loads(events[0].payload_json)["_study_runtime"]
            self.assertEqual(runtime_metadata["action_key"], "review.good")
            self.assertEqual(
                runtime_metadata["trigger_key"],
                "scheduler.review.good",
            )
            self.assertEqual(runtime_metadata["state_schema_version"], "anki-card-state.v1")

    def test_committed_batch_can_roll_into_fresh_session(self):
        first = self._open_session()
        response = self.client.post(
            f"/api/study/sessions/{first['session_id']}/commit",
            json=self._commit_payload(first),
        )
        self.assertEqual(response.status_code, 200, response.get_json())

        second = self._open_session()

        self.assertNotEqual(second["session_id"], first["session_id"])
        card = second["cards"][0]
        self.assertEqual(card["base_revision"], 1)
        self.assertEqual(card["state"]["reps"], 1)

    def test_commit_preserves_repeated_answers_for_one_card(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        second_event = dict(payload["events"][0])
        second_event.update(
            {
                "event_id": str(uuid4()),
                "sequence": 2,
                "rating": "good",
                "scheduler_offset_ms": 2000,
            }
        )
        payload["events"].append(second_event)
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["applied_event_count"], 2)

        card_id = snapshot["cards"][0]["card_id"]
        with self.app.app_context():
            events = (
                ReviewEvent.query.filter_by(
                    study_session_id=snapshot["session_id"],
                    card_id=card_id,
                )
                .order_by(ReviewEvent.sequence_no.asc())
                .all()
            )
            self.assertEqual([row.sequence_no for row in events], [1, 2])
            progress = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=card_id,
            ).one()
            self.assertEqual(progress.reps, 2)

    def test_second_session_detects_progress_conflict(self):
        first = self._open_session()
        second = self._open_session()
        first_commit = self.client.post(
            f"/api/study/sessions/{first['session_id']}/commit",
            json=self._commit_payload(first),
        )
        self.assertEqual(first_commit.status_code, 200)

        second_commit = self.client.post(
            f"/api/study/sessions/{second['session_id']}/commit",
            json=self._commit_payload(second),
        )
        self.assertEqual(second_commit.status_code, 409)
        self.assertEqual(
            second_commit.get_json()["error"],
            "CARD_PROGRESS_CONFLICT",
        )

    def test_legacy_answer_invalidates_open_batch_session(self):
        snapshot = self._open_session()
        card_id = snapshot["cards"][0]["card_id"]
        legacy = self.client.post(
            f"/api/study/{card_id}/answer",
            json={"rating": "good"},
        )
        self.assertEqual(legacy.status_code, 200, legacy.get_json())
        with self.app.app_context():
            event = ReviewEvent.query.filter_by(
                user_id=self.user_id,
                card_id=card_id,
            ).one()
            self.assertEqual(event.scheduler_algorithm, "legacy-anki")
            self.assertEqual(event.algorithm_version, "1.0.0")
            self.assertEqual(
                json.loads(event.payload_json)["_study_runtime"]["action_key"],
                "review.good",
            )
        batch = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=self._commit_payload(snapshot),
        )
        self.assertEqual(batch.status_code, 409)
        self.assertEqual(
            batch.get_json()["error"],
            "CARD_PROGRESS_CONFLICT",
        )

    def test_commit_rejects_unavailable_pinned_algorithm_version(self):
        snapshot = self._open_session()
        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            session.algorithm_version = "missing"
            db.session.commit()

        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=self._commit_payload(snapshot),
        )

        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "ALGORITHM_UNAVAILABLE")

    def test_commit_rejects_tampered_final_state(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        card = snapshot["cards"][0]
        payload["final_states"] = [
            {
                "card_id": card["card_id"],
                "base_revision": card["base_revision"],
                "state": card["state"],
            }
        ]
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"], "FINAL_STATE_MISMATCH")

    def test_commit_tolerates_mysql_datetime_precision_in_final_state(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        card = snapshot["cards"][0]
        policy = snapshot["policies"][card["policy_key"]]
        opened_at = datetime.fromisoformat(
            snapshot["server_now_utc"].replace("Z", "+00:00")
        ).replace(tzinfo=None)
        # Reproduce a session opened before the precision fix: the browser
        # retained milliseconds while MySQL DATETIME replayed from .000.
        browser_answer_at = opened_at + timedelta(milliseconds=1289)
        browser_state = applyAnswer(
            deserialize_card_state(card["state"]),
            deserialize_deck_options(policy["config"]),
            browser_answer_at,
            "good",
            timezone_name=snapshot["timezone"],
        )
        payload["events"][0]["scheduler_offset_ms"] = 500
        payload["final_states"] = [
            {
                "card_id": card["card_id"],
                "base_revision": card["base_revision"],
                "state": serialize_card_state(browser_state),
            }
        ]

        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["applied_event_count"], 1)

    def test_clone_session_uses_local_scope_without_mutating_source_note(self):
        with self.app.app_context():
            source_user = User(
                username="source-owner",
                email="source@example.com",
            )
            source_user.set_password("password")
            db.session.add(source_user)
            db.session.flush()
            source_deck = Deck(
                name="Source Deck",
                owner_user_id=source_user.id,
            )
            local_deck = Deck(
                name="Installed Deck",
                owner_user_id=self.user_id,
            )
            note_type = NoteType(
                user_id=source_user.id,
                name="Shared Type",
            )
            db.session.add_all([source_deck, local_deck, note_type])
            db.session.flush()
            field = FieldDef(
                note_type_id=note_type.id,
                name="Word",
                field_type="text",
                position=0,
            )
            template = Template(
                note_type_id=note_type.id,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{Word}}",
                is_default=True,
            )
            db.session.add_all([field, template])
            db.session.flush()
            note = Note(
                note_type_id=note_type.id,
                user_id=source_user.id,
                deck_id=source_deck.id,
                field_values={"Word": "共有"},
                tags=[],
            )
            db.session.add(note)
            db.session.flush()
            card = Card(note_id=note.id, template_id=template.id)
            db.session.add(card)
            db.session.flush()
            marketplace_item = DeckMarketplaceItem(
                owner_user_id=source_user.id,
                source_deck_id=source_deck.id,
                source_note_type_id=note_type.id,
                title="Shared Deck",
                publish_status="published",
                pricing_mode="free",
            )
            db.session.add(marketplace_item)
            db.session.flush()
            install = DeckInstall(
                deck_item_id=marketplace_item.id,
                user_id=self.user_id,
                local_deck_id=local_deck.id,
                clone_mode="logical_overlay",
                source_deck_id=source_deck.id,
                source_note_type_id=note_type.id,
                source_owner_user_id=source_user.id,
                base_snapshot_at=datetime.utcnow() + timedelta(seconds=1),
            )
            db.session.add(install)
            db.session.flush()
            db.session.add(
                DeckCloneDeckMap(
                    deck_install_id=install.id,
                    local_deck_id=local_deck.id,
                    source_deck_id=source_deck.id,
                )
            )
            db.session.add(
                CardProgress(
                    user_id=self.user_id,
                    card_id=card.id,
                    queue="review",
                    due_day=_day_index(datetime.utcnow(), 4),
                    interval_days=5,
                    ease_factor=2.5,
                    lapses=7,
                    revision=0,
                )
            )
            db.session.commit()
            local_deck_id = local_deck.id
            source_card_id = card.id
            source_note_id = note.id

        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": local_deck_id},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        snapshot = response.get_json()
        self.assertEqual(snapshot["cards"][0]["card_id"], source_card_id)
        self.assertEqual(
            snapshot["cards"][0]["local_deck_id"],
            local_deck_id,
        )
        payload = self._commit_payload(snapshot)
        payload["events"][0]["rating"] = "again"
        commit = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(commit.status_code, 200, commit.get_json())

        with self.app.app_context():
            source_note = db.session.get(Note, source_note_id)
            self.assertEqual(source_note.tags, [])
            event = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).one()
            self.assertEqual(event.deck_id, local_deck_id)
            progress = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=source_card_id,
            ).one()
            self.assertTrue(progress.is_suspended)

    def test_scope_compositions_endpoint(self):
        response = self.client.get(f"/api/study/scopes/deck/{self.deck_id}/compositions")
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertEqual(data["schema_version"], "study-scope-compositions.v1")
        self.assertEqual(data["scope_type"], "deck")
        self.assertEqual(data["scope_id"], str(self.deck_id))
        self.assertGreaterEqual(len(data["compositions"]), 1)
        comp = data["compositions"][0]
        self.assertEqual(comp["mode_key"], "flashcard")
        self.assertEqual(comp["algorithm_key"], "legacy-anki")

    def test_open_session_non_existent_deck_returns_404_deck_not_found(self):
        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": 999999},
        )
        self.assertEqual(response.status_code, 404)
        payload = response.get_json()
        self.assertEqual(payload.get("error"), "DECK_NOT_FOUND")
        self.assertIn("không tồn tại", payload.get("message", ""))

    def test_open_session_unauthorized_deck_returns_403_with_marketplace_details(self):
        with self.app.app_context():
            other_user = User(username="other_author", email="author@example.com")
            other_user.set_password("password")
            db.session.add(other_user)
            db.session.flush()

            other_deck = Deck(name="Published Deck", owner_user_id=other_user.id)
            db.session.add(other_deck)
            db.session.flush()

            marketplace_item = DeckMarketplaceItem(
                id="market-item-456",
                owner_user_id=other_user.id,
                source_deck_id=other_deck.id,
                title="Published Deck Market Item",
                description="Sample description",
                primary_category="JLPT N5",
            )
            db.session.add(marketplace_item)
            db.session.commit()
            other_deck_id = other_deck.id

        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": other_deck_id},
        )
        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload.get("error"), "DECK_ACCESS_DENIED")
        self.assertIn("không thể truy cập", payload.get("message", ""))
        self.assertIsNotNone(payload.get("details"))
        self.assertEqual(payload["details"]["deck_name"], "Published Deck")
        self.assertEqual(payload["details"]["marketplace_url"], "/marketplace/decks/market-item-456")

    def test_study_next_empty_deck_returns_no_cards_payload(self):
        with self.app.app_context():
            empty_deck = Deck(name="Empty Deck", owner_user_id=self.user_id)
            db.session.add(empty_deck)
            db.session.commit()
            empty_deck_id = empty_deck.id

        response = self.client.get(
            f"/api/study/next?scope=deck&scope_id={empty_deck_id}",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNone(payload.get("card_id"))
        self.assertEqual(payload.get("error"), "NO_STUDY_CARDS")


if __name__ == "__main__":
    unittest.main()
