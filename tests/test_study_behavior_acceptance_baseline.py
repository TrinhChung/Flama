"""Behavior acceptance characterization baseline tests for study architecture decoupling."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import date, datetime, time, timedelta, timezone
import unittest
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app import create_app
from app.services import (
    anki_import_service,
    flama_connect_package_service,
    flashcards_share_service,
    study_composition_service,
    study_service,
    study_session_service,
)
from app.services.anki_scheduler import _day_index
from app.services.connect.actions import add_note
from app.services.mcp import study_tools as mcp_study_tools
from app.services.study_architecture_audit_service import build_study_architecture_audit
from app.repositories.study_repository import (
    query_next_due_card_id,
    query_study_queue_counts,
)
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.flashcard import (
    DeckCloneAddedNote,
    FieldDef,
    Note,
    NoteType,
    ReviewEvent,
    Template,
)
from models.connect_note_ref import ConnectNoteRef
from models.connect_review_event_ref import ConnectReviewEventRef
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.study_session_commit import StudySessionCommit
from models.user import User


class StudyBehaviorAcceptanceBaselineTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # User 1 (Source author)
            author = User(
                username="author",
                email="author@example.com",
                timezone="Asia/Ho_Chi_Minh",
                is_admin=True,
            )
            author.set_password("password")

            # User 2 (Learner / Subscriber)
            learner = User(
                username="learner",
                email="learner@example.com",
                timezone="Asia/Ho_Chi_Minh",
                is_admin=False,
            )
            learner.set_password("password")

            db.session.add_all([author, learner])
            db.session.flush()

            self.author_id = author.id
            self.learner_id = learner.id

            # NoteType & Template
            note_type = NoteType(user_id=author.id, name="Vocabulary NoteType")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            field_word = FieldDef(
                note_type_id=note_type.id,
                name="Word",
                field_type="text",
                position=0,
                required=True,
                identity_role="primary",
            )
            field_meaning = FieldDef(
                note_type_id=note_type.id,
                name="Meaning",
                field_type="text",
                position=1,
                required=True,
            )
            template = Template(
                note_type_id=note_type.id,
                name="Recognition",
                position=0,
                is_default=True,
                front_html="{{Word}}",
                back_html="{{Meaning}}",
            )
            db.session.add_all([field_word, field_meaning, template])
            db.session.flush()
            self.template_id = template.id

            # Source Deck & Note & Card A
            deck = Deck(owner_user_id=author.id, name="JLPT N5 Vocab")
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id

            note_a = Note(
                user_id=author.id,
                note_type_id=note_type.id,
                deck_id=deck.id,
                field_values={"Word": "猫", "Meaning": "Cat"},
            )
            note_b = Note(
                user_id=author.id,
                note_type_id=note_type.id,
                deck_id=deck.id,
                field_values={"Word": "犬", "Meaning": "Dog"},
            )
            db.session.add_all([note_a, note_b])
            db.session.flush()
            self.note_a_id = note_a.id
            self.note_b_id = note_b.id

            card_a = Card(note_id=note_a.id, template_id=template.id)
            card_b = Card(note_id=note_b.id, template_id=template.id)
            db.session.add_all([card_a, card_b])
            db.session.commit()
            self.card_a_id = card_a.id
            self.card_b_id = card_b.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    # -------------------------------------------------------------------------
    # 1. Direct REST vs MCP vs durable session parity
    # -------------------------------------------------------------------------
    def test_direct_native_review_and_mcp_parity(self):
        """REST, MCP and durable sessions share state and event semantics."""
        from unittest.mock import patch

        fixed_now = datetime(2026, 8, 29, 10, 0, 0)
        today_day = _day_index(fixed_now, boundary_hour=4, timezone_name="Asia/Ho_Chi_Minh")
        expected_due_day_after = today_day + 13

        with self.app.app_context():
            note_c = Note(
                user_id=self.author_id,
                note_type_id=self.note_type_id,
                deck_id=self.deck_id,
                field_values={"Word": "bird", "Meaning": "Bird"},
            )
            db.session.add(note_c)
            db.session.flush()
            card_c = Card(note_id=note_c.id, template_id=self.template_id)
            db.session.add(card_c)
            db.session.flush()
            card_c_id = card_c.id

            # Initial identical state for all three transports.
            p_a = CardProgress(
                user_id=self.author_id,
                card_id=self.card_a_id,
                queue="review",
                interval_days=5,
                ease_factor=2.5,
                reps=3,
                lapses=0,
                due_day=today_day,
                step_index=0,
                revision=0,
            )
            p_b = CardProgress(
                user_id=self.author_id,
                card_id=self.card_b_id,
                queue="review",
                interval_days=5,
                ease_factor=2.5,
                reps=3,
                lapses=0,
                due_day=today_day,
                step_index=0,
                revision=0,
            )
            p_c = CardProgress(
                user_id=self.author_id,
                card_id=card_c_id,
                queue="review",
                interval_days=5,
                ease_factor=2.5,
                reps=3,
                lapses=0,
                due_day=today_day,
                step_index=0,
                revision=0,
            )
            db.session.add_all([p_a, p_b, p_c])
            db.session.commit()

        # 1. Execute review via direct REST endpoint for Card A with fixed reference time
        with patch("app.routes.flashcards.study.datetime") as mock_study_dt, \
             patch("app.services.study_service.datetime") as mock_srv_dt:
            mock_study_dt.utcnow.return_value = fixed_now
            mock_study_dt.fromisoformat = datetime.fromisoformat
            mock_study_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            mock_srv_dt.utcnow.return_value = fixed_now
            mock_srv_dt.fromisoformat = datetime.fromisoformat
            mock_srv_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            self.client.post(
                "/login",
                data={"email": "author@example.com", "password": "password"},
                follow_redirects=False,
            )
            rest_response = self.client.post(
                f"/api/study/{self.card_a_id}/answer",
                json={
                    "rating": "good",
                    "duration_ms": 2500,
                    "timezone": "Asia/Ho_Chi_Minh",
                },
            )
            self.assertEqual(rest_response.status_code, 200, rest_response.get_json())
            self.assertTrue(rest_response.get_json()["success"])

            # 2. Execute review via MCP tool for Card B with fixed reference time
            with self.app.app_context():
                mcp_result = mcp_study_tools.submit_review(
                    user_id=self.author_id,
                    card_id=self.card_b_id,
                    rating="good",
                    duration_ms=2500,
                )
                self.assertTrue(mcp_result["success"])
                self.assertEqual(mcp_result["rating"], "good")

                # 3. Execute the equivalent review through a durable session.
                author_user = db.session.get(User, self.author_id)
                snapshot = study_session_service.open_study_session(
                    user=author_user,
                    query=Card.query.filter(Card.id == card_c_id),
                    clone_scope=None,
                    scope_type="deck",
                    scope_id=str(self.deck_id),
                    timezone_name="Asia/Ho_Chi_Minh",
                    now=fixed_now,
                )
                session_card = snapshot["cards"][0]
                session_event_id = str(uuid4())
                session_result = study_session_service.commit_study_session(
                    user=author_user,
                    session_id=snapshot["session_id"],
                    payload={
                        "schema_version": "study-commit.v1",
                        "commit_id": "commit-transport-parity-01",
                        "session_token": snapshot["session_token"],
                        "snapshot_hash": snapshot["snapshot_hash"],
                        "commit_reason": "manual_exit",
                        "events": [
                            {
                                "event_id": session_event_id,
                                "sequence": 1,
                                "card_id": card_c_id,
                                "rating": "good",
                                "policy_key": session_card["policy_key"],
                                "scheduler_offset_ms": 0,
                                "duration_ms": 2500,
                            }
                        ],
                        "final_states": [],
                    },
                    now=fixed_now,
                )
                self.assertTrue(session_result["success"])

                # 4. Comprehensive parity across authoritative CardProgress fields.
                updated_pa = CardProgress.query.filter_by(
                    user_id=self.author_id, card_id=self.card_a_id
                ).one()
                updated_pb = CardProgress.query.filter_by(
                    user_id=self.author_id, card_id=self.card_b_id
                ).one()
                updated_pc = CardProgress.query.filter_by(
                    user_id=self.author_id, card_id=card_c_id
                ).one()

                progress_parity_fields = (
                    "reps",
                    "interval_days",
                    "interval_days_raw",
                    "ease_factor",
                    "lapses",
                    "queue",
                    "step_index",
                    "due_day",
                    "due_at",
                    "revision",
                    "is_suspended",
                    "is_buried",
                    "buried_until_day",
                    "review_kind",
                    "scheduler_mode",
                    "memory_stability",
                    "memory_difficulty",
                    "suspension_reason",
                    "last_leech_at",
                    "last_leech_lapses",
                    "last_reviewed_at",
                )
                for field_name in progress_parity_fields:
                    self.assertEqual(
                        getattr(updated_pa, field_name),
                        getattr(updated_pc, field_name),
                        field_name,
                    )

                self.assertEqual(updated_pa.reps, 4)
                self.assertEqual(updated_pb.reps, 4)
                self.assertEqual(updated_pa.interval_days, 13)
                self.assertEqual(updated_pb.interval_days, 13)
                self.assertEqual(updated_pa.interval_days_raw, 12.5)
                self.assertEqual(updated_pb.interval_days_raw, 12.5)
                self.assertEqual(updated_pa.ease_factor, 2.5)
                self.assertEqual(updated_pb.ease_factor, 2.5)
                self.assertEqual(updated_pa.lapses, 0)
                self.assertEqual(updated_pb.lapses, 0)
                self.assertEqual(updated_pa.queue, "review")
                self.assertEqual(updated_pb.queue, "review")
                self.assertEqual(updated_pa.step_index, 0)
                self.assertEqual(updated_pb.step_index, 0)
                self.assertEqual(updated_pa.due_day, expected_due_day_after)
                self.assertEqual(updated_pb.due_day, expected_due_day_after)
                self.assertEqual(updated_pa.due_at, updated_pb.due_at)
                self.assertEqual(updated_pa.revision, 1)
                self.assertEqual(updated_pb.revision, 1)
                self.assertEqual(updated_pa.is_suspended, False)
                self.assertEqual(updated_pb.is_suspended, False)
                self.assertEqual(updated_pa.is_buried, False)
                self.assertEqual(updated_pb.is_buried, False)
                self.assertIsNone(updated_pa.buried_until_day)
                self.assertIsNone(updated_pb.buried_until_day)
                self.assertEqual(updated_pa.review_kind, "review")
                self.assertEqual(updated_pb.review_kind, "review")
                self.assertEqual(updated_pa.scheduler_mode, "legacy")
                self.assertEqual(updated_pb.scheduler_mode, "legacy")
                self.assertIsNone(updated_pa.memory_stability)
                self.assertIsNone(updated_pb.memory_stability)
                self.assertIsNone(updated_pa.memory_difficulty)
                self.assertIsNone(updated_pb.memory_difficulty)
                self.assertIsNone(updated_pa.suspension_reason)
                self.assertIsNone(updated_pb.suspension_reason)
                self.assertIsNone(updated_pa.last_leech_at)
                self.assertIsNone(updated_pb.last_leech_at)
                self.assertEqual(updated_pa.last_leech_lapses, 0)
                self.assertEqual(updated_pb.last_leech_lapses, 0)
                self.assertEqual(updated_pa.last_reviewed_at, fixed_now)
                self.assertEqual(updated_pb.last_reviewed_at, fixed_now)
                self.assertLess(abs((updated_pa.last_reviewed_at - updated_pb.last_reviewed_at).total_seconds()), 1.0)

                # Documented Exclusions / Entity Pointers on CardProgress
                self.assertEqual(updated_pa.card_id, self.card_a_id)
                self.assertEqual(updated_pb.card_id, self.card_b_id)

                # 5. Comprehensive parity across authoritative ReviewEvent fields.
                event_a = ReviewEvent.query.filter_by(
                    user_id=self.author_id, card_id=self.card_a_id
                ).order_by(ReviewEvent.id.desc()).first()
                event_b = ReviewEvent.query.filter_by(
                    user_id=self.author_id, card_id=self.card_b_id
                ).order_by(ReviewEvent.id.desc()).first()
                event_c = ReviewEvent.query.filter_by(
                    user_id=self.author_id, card_id=card_c_id
                ).order_by(ReviewEvent.id.desc()).first()

                self.assertIsNotNone(event_a)
                self.assertIsNotNone(event_b)
                self.assertIsNotNone(event_c)
                self.assertEqual(updated_pa.last_review_event_id, event_a.id)
                self.assertEqual(updated_pb.last_review_event_id, event_b.id)
                self.assertEqual(updated_pc.last_review_event_id, event_c.id)

                event_parity_fields = (
                    "user_id",
                    "deck_id",
                    "note_type_id",
                    "scheduler_preset_id",
                    "scheduler_algorithm",
                    "algorithm_version",
                    "scheduler_config_hash",
                    "reviewed_at",
                    "duration_ms",
                    "rating",
                    "mode",
                    "scheduler_mode",
                    "review_kind",
                    "queue_before",
                    "queue_after",
                    "interval_days_before",
                    "interval_days_after",
                    "due_day_before",
                    "due_day_after",
                    "days_late",
                    "ease_factor_before",
                    "ease_factor_after",
                    "memory_stability_before",
                    "memory_stability_after",
                    "memory_difficulty_before",
                    "memory_difficulty_after",
                    "leeched_after",
                    "suspended_after",
                )
                for field_name in event_parity_fields:
                    self.assertEqual(
                        getattr(event_a, field_name),
                        getattr(event_c, field_name),
                        field_name,
                    )

                self.assertEqual(event_a.user_id, self.author_id)
                self.assertEqual(event_b.user_id, self.author_id)
                self.assertIsNone(event_a.scheduler_preset_id)
                self.assertIsNone(event_b.scheduler_preset_id)
                self.assertEqual(event_a.scheduler_algorithm, "legacy-anki")
                self.assertEqual(event_b.scheduler_algorithm, "legacy-anki")
                self.assertEqual(event_a.algorithm_version, "1.0.0")
                self.assertEqual(event_b.algorithm_version, "1.0.0")
                self.assertEqual(event_a.scheduler_config_hash, event_b.scheduler_config_hash)
                self.assertEqual(event_a.reviewed_at, fixed_now)
                self.assertEqual(event_b.reviewed_at, fixed_now)
                self.assertLess(abs((event_a.reviewed_at - event_b.reviewed_at).total_seconds()), 1.0)
                self.assertEqual(event_a.duration_ms, 2500)
                self.assertEqual(event_b.duration_ms, 2500)
                self.assertEqual(event_a.rating, "good")
                self.assertEqual(event_b.rating, "good")
                self.assertEqual(event_a.mode, "review")
                self.assertEqual(event_b.mode, "review")
                self.assertEqual(event_a.scheduler_mode, "legacy")
                self.assertEqual(event_b.scheduler_mode, "legacy")
                self.assertEqual(event_a.review_kind, "review")
                self.assertEqual(event_b.review_kind, "review")
                self.assertEqual(event_a.queue_before, "review")
                self.assertEqual(event_b.queue_before, "review")
                self.assertEqual(event_a.queue_after, "review")
                self.assertEqual(event_b.queue_after, "review")
                self.assertEqual(event_a.interval_days_before, 5.0)
                self.assertEqual(event_b.interval_days_before, 5.0)
                self.assertEqual(event_a.interval_days_after, 12.5)
                self.assertEqual(event_b.interval_days_after, 12.5)
                self.assertEqual(event_a.due_day_before, today_day)
                self.assertEqual(event_b.due_day_before, today_day)
                self.assertEqual(event_a.due_day_after, expected_due_day_after)
                self.assertEqual(event_b.due_day_after, expected_due_day_after)
                self.assertEqual(event_a.days_late, 0)
                self.assertEqual(event_b.days_late, 0)
                self.assertEqual(event_a.days_late, event_b.days_late)
                self.assertEqual(event_a.ease_factor_before, 2.5)
                self.assertEqual(event_b.ease_factor_before, 2.5)
                self.assertEqual(event_a.ease_factor_after, 2.5)
                self.assertEqual(event_b.ease_factor_after, 2.5)
                self.assertIsNone(event_a.memory_stability_before)
                self.assertIsNone(event_b.memory_stability_before)
                self.assertIsNone(event_a.memory_stability_after)
                self.assertIsNone(event_b.memory_stability_after)
                self.assertIsNone(event_a.memory_difficulty_before)
                self.assertIsNone(event_b.memory_difficulty_before)
                self.assertIsNone(event_a.memory_difficulty_after)
                self.assertIsNone(event_b.memory_difficulty_after)
                self.assertFalse(event_a.leeched_after)
                self.assertFalse(event_b.leeched_after)
                self.assertFalse(event_a.suspended_after)
                self.assertFalse(event_b.suspended_after)

                # 6. Only session transport carries session/sequence provenance.
                self.assertEqual(event_a.card_id, str(self.card_a_id))
                self.assertEqual(event_b.card_id, str(self.card_b_id))
                self.assertIsNone(event_a.client_event_id)
                self.assertIsNotNone(event_b.client_event_id)
                self.assertEqual(len(str(event_b.client_event_id)), 36)
                self.assertEqual(event_c.study_session_id, snapshot["session_id"])
                self.assertEqual(event_c.client_event_id, session_event_id)
                self.assertEqual(event_c.sequence_no, 1)
                self.assertIsNone(event_a.study_session_id)
                self.assertIsNone(event_a.sequence_no)
                self.assertIsNone(event_b.study_session_id)
                self.assertIsNone(event_b.sequence_no)

                payload_a = json.loads(event_a.payload_json)
                payload_b = json.loads(event_b.payload_json)
                payload_c = json.loads(event_c.payload_json)
                self.assertEqual(payload_a["schema_version"], "review-event-payload.v1")
                self.assertEqual(payload_b["schema_version"], "review-event-payload.v1")
                self.assertEqual(payload_c["schema_version"], "review-event-payload.v1")
                self.assertEqual(payload_a["provenance"]["source_path"], "native.rest")
                self.assertEqual(payload_b["provenance"]["source_path"], "native.mcp")
                self.assertEqual(
                    payload_c["provenance"]["source_path"],
                    "native.session.commit",
                )
                self.assertNotIn("source", payload_a)
                self.assertEqual(payload_b.get("source"), "mcp")
                self.assertEqual(payload_b.get("client_event_id"), str(event_b.client_event_id))

                # Shared semantic trigger metadata in runtime payload
                runtime_a = payload_a["_study_runtime"]
                runtime_b = payload_b["_study_runtime"]
                runtime_c = payload_c["_study_runtime"]
                self.assertEqual(runtime_a["action_key"], "review.good")
                self.assertEqual(runtime_b["action_key"], "review.good")
                self.assertEqual(runtime_a["trigger_key"], "scheduler.review.good")
                self.assertEqual(runtime_b["trigger_key"], "scheduler.review.good")
                self.assertEqual(runtime_a["trigger_contract_version"], "1")
                self.assertEqual(runtime_b["trigger_contract_version"], "1")
                self.assertEqual(runtime_a["action_contract_version"], "1")
                self.assertEqual(runtime_b["action_contract_version"], "1")
                self.assertEqual(runtime_a["algorithm_key"], "legacy-anki")
                self.assertEqual(runtime_b["algorithm_key"], "legacy-anki")
                self.assertEqual(runtime_a["algorithm_version"], "1.0.0")
                self.assertEqual(runtime_b["algorithm_version"], "1.0.0")
                self.assertEqual(runtime_a["state_schema_version"], "anki-card-state.v1")
                self.assertEqual(runtime_b["state_schema_version"], "anki-card-state.v1")
                self.assertEqual(runtime_a["scheduler_config_hash"], runtime_b["scheduler_config_hash"])
                self.assertEqual(runtime_a, runtime_c)

                # 7. Audit engine recognizes all native transports without conflict.
                audit = build_study_architecture_audit()
                rg = audit["review_event_gates"]
                self.assertEqual(rg["native_direct_events"], 1)
                self.assertEqual(rg["native_mcp_events"], 1)
                self.assertEqual(rg["native_session_events"], 1)
                self.assertEqual(rg["conflicting_provenance_events"], 0)
                self.assertEqual(rg["unknown_provenance_events"], 0)

    # -------------------------------------------------------------------------
    # 2. Batch Commit Idempotency, Atomic Rollback & Stale Revision Conflict
    # -------------------------------------------------------------------------
    def test_batch_commit_idempotency_and_atomic_rollback(self):
        """Batch session commit is idempotent on replay, rolls back atomically on pre-write validation and mid-write ORM failures, and detects stale conflicts."""
        from unittest.mock import patch

        with self.app.app_context():
            now = datetime(2026, 8, 29, 10, 0, 0)
            author_user = db.session.get(User, self.author_id)

            # Part A: Idempotency
            snapshot = study_session_service.open_study_session(
                user=author_user,
                query=Card.query.filter(Card.note_id == self.note_a_id),
                clone_scope=None,
                scope_type="deck",
                scope_id=str(self.deck_id),
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )
            card = snapshot["cards"][0]
            test_event_id = str(uuid4())
            commit_payload = {
                "schema_version": "study-commit.v1",
                "commit_id": "commit-idempotency-test-01",
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "commit_reason": "manual_exit",
                "events": [
                    {
                        "event_id": test_event_id,
                        "sequence": 1,
                        "card_id": card["card_id"],
                        "rating": "good",
                        "policy_key": card["policy_key"],
                        "scheduler_offset_ms": 1000,
                        "duration_ms": 500,
                    }
                ],
                "final_states": [],
            }

            # First commit delegates its authoritative mutation to the shared core.
            real_mutation = study_service.apply_native_review_mutation
            with patch(
                "app.services.study_service.apply_native_review_mutation",
                wraps=real_mutation,
            ) as mutation_spy:
                result1 = study_session_service.commit_study_session(
                    user=author_user,
                    session_id=snapshot["session_id"],
                    payload=commit_payload,
                    now=now,
                )
            self.assertEqual(mutation_spy.call_count, 1)
            delegated_input = mutation_spy.call_args.args[0]
            self.assertEqual(
                delegated_input.provenance.study_session_id,
                snapshot["session_id"],
            )
            self.assertTrue(result1.get("success"))
            self.assertEqual(result1.get("applied_event_count"), 1)

            events_count_first = ReviewEvent.query.filter_by(study_session_id=snapshot["session_id"]).count()
            self.assertEqual(events_count_first, 1)

            # Second commit replay with identical payload
            result2 = study_session_service.commit_study_session(
                user=author_user,
                session_id=snapshot["session_id"],
                payload=commit_payload,
                now=now,
            )
            self.assertTrue(result2.get("success"))
            self.assertEqual(result2.get("commit_id"), "commit-idempotency-test-01")

            events_count_second = ReviewEvent.query.filter_by(study_session_id=snapshot["session_id"]).count()
            self.assertEqual(events_count_first, events_count_second)

            # Part B1: Pre-Write Validation Rollback (Event 1 valid, Event 2 invalid rating -> ZERO partial writes)
            snapshot_err = study_session_service.open_study_session(
                user=author_user,
                query=Card.query.filter(Card.id.in_([self.card_a_id, self.card_b_id])),
                clone_scope=None,
                scope_type="deck",
                scope_id=str(self.deck_id),
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )
            cards_by_id = {c["card_id"]: c for c in snapshot_err["cards"]}
            card_a_info = cards_by_id[self.card_a_id]
            card_b_info = cards_by_id[self.card_b_id]

            # Record progress state prior to failed batch
            card_a_prog_before = CardProgress.query.filter_by(user_id=self.author_id, card_id=self.card_a_id).first()
            card_a_reps_before = card_a_prog_before.reps if card_a_prog_before else None

            err_commit_payload = {
                "schema_version": "study-commit.v1",
                "commit_id": "commit-rollback-test-02",
                "session_token": snapshot_err["session_token"],
                "snapshot_hash": snapshot_err["snapshot_hash"],
                "commit_reason": "manual_exit",
                "events": [
                    {
                        "event_id": str(uuid4()),
                        "sequence": 1,
                        "card_id": self.card_a_id,
                        "rating": "good",  # Event 1 is completely valid
                        "policy_key": card_a_info["policy_key"],
                        "scheduler_offset_ms": 1000,
                        "duration_ms": 500,
                    },
                    {
                        "event_id": str(uuid4()),
                        "sequence": 2,
                        "card_id": self.card_b_id,
                        "rating": "invalid_rating_value",  # Event 2 fails validation before write phase
                        "policy_key": card_b_info["policy_key"],
                        "scheduler_offset_ms": 2000,
                        "duration_ms": 500,
                    },
                ],
                "final_states": [],
            }

            with self.assertRaises(study_session_service.StudySessionError) as cm:
                study_session_service.commit_study_session(
                    user=author_user,
                    session_id=snapshot_err["session_id"],
                    payload=err_commit_payload,
                    now=now,
                )
            self.assertEqual(cm.exception.status, 422)

            # Assert ZERO partial writes across all entities
            err_session_events = ReviewEvent.query.filter_by(study_session_id=snapshot_err["session_id"]).count()
            self.assertEqual(err_session_events, 0, "No partial ReviewEvent should be written for either card")

            progress_a_after = CardProgress.query.filter_by(user_id=self.author_id, card_id=self.card_a_id).first()
            card_a_reps_after = progress_a_after.reps if progress_a_after else None
            self.assertEqual(card_a_reps_before, card_a_reps_after, "Card A progress must not be mutated by rolled back batch")

            progress_b = CardProgress.query.filter_by(user_id=self.author_id, card_id=self.card_b_id).first()
            self.assertIsNone(progress_b, "Card B progress must not be created")

            commit_receipt = StudySessionCommit.query.filter_by(session_id=snapshot_err["session_id"]).first()
            self.assertIsNone(commit_receipt, "No StudySessionCommit receipt should be created")

            session_row = db.session.get(StudySession, snapshot_err["session_id"])
            self.assertEqual(session_row.status, "open", "Session must remain open after rollback")
            self.assertIsNone(session_row.committed_at, "Session committed_at must remain None")

            # Part B2: Mid-Write Phase Failure & Transaction Atomicity (Exception raised during write phase after ORM mutation/flush)
            snapshot_write_err = study_session_service.open_study_session(
                user=author_user,
                query=Card.query.filter(Card.id.in_([self.card_a_id, self.card_b_id])),
                clone_scope=None,
                scope_type="deck",
                scope_id=str(self.deck_id),
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )
            cards_write_map = {c["card_id"]: c for c in snapshot_write_err["cards"]}

            # Card A initial progress before write-failure test
            prog_a_before_b2 = CardProgress.query.filter_by(user_id=self.author_id, card_id=self.card_a_id).first()
            reps_a_before_b2 = prog_a_before_b2.reps if prog_a_before_b2 else None

            # Valid batch payload with 2 events
            valid_two_event_payload = {
                "schema_version": "study-commit.v1",
                "commit_id": "commit-midwrite-rollback-test-03",
                "session_token": snapshot_write_err["session_token"],
                "snapshot_hash": snapshot_write_err["snapshot_hash"],
                "commit_reason": "manual_exit",
                "events": [
                    {
                        "event_id": str(uuid4()),
                        "sequence": 1,
                        "card_id": self.card_a_id,
                        "rating": "good",
                        "policy_key": cards_write_map[self.card_a_id]["policy_key"],
                        "scheduler_offset_ms": 1000,
                        "duration_ms": 500,
                    },
                    {
                        "event_id": str(uuid4()),
                        "sequence": 2,
                        "card_id": self.card_b_id,
                        "rating": "good",
                        "policy_key": cards_write_map[self.card_b_id]["policy_key"],
                        "scheduler_offset_ms": 2000,
                        "duration_ms": 500,
                    },
                ],
                "final_states": [],
            }

            # Inject failure after canonical event/progress/side-effect mutation.
            real_mutation = study_service.apply_native_review_mutation

            def _failing_mutation(command):
                result = real_mutation(command)
                command.card.note.tags = list(command.card.note.tags or []) + [
                    "rollback-sentinel"
                ]
                if command.card.id == self.card_b_id:
                    raise RuntimeError(
                        "Simulated mid-write database failure after canonical mutation"
                    )
                return result

            audit_count_before = AuditLog.query.count()
            with patch(
                "app.services.study_service.apply_native_review_mutation",
                side_effect=_failing_mutation,
            ):
                with self.assertRaises(RuntimeError) as cm_write_err:
                    study_session_service.commit_study_session(
                        user=author_user,
                        session_id=snapshot_write_err["session_id"],
                        payload=valid_two_event_payload,
                        now=now,
                    )
                self.assertIn("Simulated mid-write database failure", str(cm_write_err.exception))

            # Verify that service atomically rolled back all partial mutations from the write phase
            write_err_events = ReviewEvent.query.filter_by(study_session_id=snapshot_write_err["session_id"]).count()
            self.assertEqual(write_err_events, 0, "No partial ReviewEvent must remain after mid-write rollback")

            prog_a_after_b2 = CardProgress.query.filter_by(user_id=self.author_id, card_id=self.card_a_id).first()
            reps_a_after_b2 = prog_a_after_b2.reps if prog_a_after_b2 else None
            self.assertEqual(reps_a_before_b2, reps_a_after_b2, "Card A progress must not be mutated after mid-write rollback")

            prog_b_after_b2 = CardProgress.query.filter_by(user_id=self.author_id, card_id=self.card_b_id).first()
            self.assertIsNone(prog_b_after_b2, "Card B progress must not be created after mid-write rollback")

            commit_receipt_b2 = StudySessionCommit.query.filter_by(session_id=snapshot_write_err["session_id"]).first()
            self.assertIsNone(commit_receipt_b2, "No StudySessionCommit receipt should exist after mid-write rollback")

            session_row_b2 = db.session.get(StudySession, snapshot_write_err["session_id"])
            self.assertEqual(session_row_b2.status, "open", "Session must remain open after mid-write rollback")
            self.assertIsNone(session_row_b2.committed_at, "Session committed_at must remain None after mid-write rollback")
            self.assertEqual(AuditLog.query.count(), audit_count_before)
            db.session.expire_all()
            self.assertNotIn(
                "rollback-sentinel",
                db.session.get(Note, self.note_a_id).tags or [],
            )
            self.assertNotIn(
                "rollback-sentinel",
                db.session.get(Note, self.note_b_id).tags or [],
            )

            # Part C: Stale Revision Conflict
            # Open Session S1 and Session S2 on Card A
            s1 = study_session_service.open_study_session(
                user=author_user,
                query=Card.query.filter(Card.id == self.card_a_id),
                clone_scope=None,
                scope_type="deck",
                scope_id=str(self.deck_id),
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )
            s2 = study_session_service.open_study_session(
                user=author_user,
                query=Card.query.filter(Card.id == self.card_a_id),
                clone_scope=None,
                scope_type="deck",
                scope_id=str(self.deck_id),
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )

            # S1 commits successfully -> increments CardProgress revision
            s1_payload = {
                "schema_version": "study-commit.v1",
                "commit_id": "commit-s1-ok",
                "session_token": s1["session_token"],
                "snapshot_hash": s1["snapshot_hash"],
                "commit_reason": "manual_exit",
                "events": [
                    {
                        "event_id": str(uuid4()),
                        "sequence": 1,
                        "card_id": self.card_a_id,
                        "rating": "good",
                        "policy_key": s1["cards"][0]["policy_key"],
                        "scheduler_offset_ms": 1000,
                        "duration_ms": 500,
                    }
                ],
                "final_states": [],
            }
            res_s1 = study_session_service.commit_study_session(
                user=author_user,
                session_id=s1["session_id"],
                payload=s1_payload,
                now=now,
            )
            self.assertTrue(res_s1["success"])

            # S2 attempts to commit with stale base revision -> must fail with CARD_PROGRESS_CONFLICT
            s2_payload = {
                "schema_version": "study-commit.v1",
                "commit_id": "commit-s2-conflict",
                "session_token": s2["session_token"],
                "snapshot_hash": s2["snapshot_hash"],
                "commit_reason": "manual_exit",
                "events": [
                    {
                        "event_id": str(uuid4()),
                        "sequence": 1,
                        "card_id": self.card_a_id,
                        "rating": "easy",
                        "policy_key": s2["cards"][0]["policy_key"],
                        "scheduler_offset_ms": 1000,
                        "duration_ms": 500,
                    }
                ],
                "final_states": [],
            }
            with self.assertRaises(study_session_service.StudySessionError) as cm_conflict:
                study_session_service.commit_study_session(
                    user=author_user,
                    session_id=s2["session_id"],
                    payload=s2_payload,
                    now=now,
                )
            self.assertEqual(cm_conflict.exception.code, "CARD_PROGRESS_CONFLICT")
            self.assertEqual(cm_conflict.exception.status, 409)

            # Assert zero partial writes from S2
            s2_events = ReviewEvent.query.filter_by(study_session_id=s2["session_id"]).count()
            self.assertEqual(s2_events, 0)

    def test_first_progress_insert_races_return_typed_conflicts(self):
        """Direct and batch first-write races never leak raw IntegrityError."""
        from unittest.mock import patch

        with self.app.app_context():
            now = datetime(2026, 8, 29, 10, 0, 0)
            author = db.session.get(User, self.author_id)
            card_a = db.session.get(Card, self.card_a_id)
            duplicate_error = IntegrityError(
                "INSERT INTO card_progress",
                {},
                RuntimeError("duplicate progress row"),
            )

            with patch(
                "app.services.study_service.db.session.flush",
                side_effect=duplicate_error,
            ):
                with self.assertRaises(study_service.StudyReviewError) as direct_cm:
                    study_service.execute_native_review_command(
                        user=author,
                        card=card_a,
                        action="good",
                        payload={"duration_ms": 500},
                        clone_scope=None,
                        requested_scope_id=self.deck_id,
                        timezone_name="Asia/Ho_Chi_Minh",
                        now=now,
                    )
            self.assertEqual(direct_cm.exception.code, "CONCURRENT_REVIEW")
            self.assertEqual(direct_cm.exception.status, 409)
            self.assertIsNone(
                CardProgress.query.filter_by(
                    user_id=self.author_id,
                    card_id=self.card_a_id,
                ).first()
            )

            snapshot = study_session_service.open_study_session(
                user=author,
                query=Card.query.filter(Card.id == self.card_b_id),
                clone_scope=None,
                scope_type="deck",
                scope_id=str(self.deck_id),
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )
            session_card = snapshot["cards"][0]
            payload = {
                "schema_version": "study-commit.v1",
                "commit_id": "commit-first-progress-race-01",
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "commit_reason": "manual_exit",
                "events": [
                    {
                        "event_id": str(uuid4()),
                        "sequence": 1,
                        "card_id": self.card_b_id,
                        "rating": "good",
                        "policy_key": session_card["policy_key"],
                        "scheduler_offset_ms": 0,
                        "duration_ms": 500,
                    }
                ],
                "final_states": [],
            }
            batch_duplicate_error = IntegrityError(
                "INSERT INTO card_progress",
                {},
                RuntimeError("duplicate progress row"),
            )
            with patch(
                "app.services.study_session_service.db.session.flush",
                side_effect=batch_duplicate_error,
            ):
                with self.assertRaises(
                    study_session_service.StudySessionError
                ) as batch_cm:
                    study_session_service.commit_study_session(
                        user=author,
                        session_id=snapshot["session_id"],
                        payload=payload,
                        now=now,
                    )
            self.assertEqual(batch_cm.exception.code, "CARD_PROGRESS_CONFLICT")
            self.assertEqual(batch_cm.exception.status, 409)
            self.assertIsNone(
                CardProgress.query.filter_by(
                    user_id=self.author_id,
                    card_id=self.card_b_id,
                ).first()
            )
            self.assertEqual(
                ReviewEvent.query.filter_by(
                    study_session_id=snapshot["session_id"]
                ).count(),
                0,
            )

    # -------------------------------------------------------------------------
    # 3. Due Selection & Multi-Timezone Day Boundary Invariants
    # -------------------------------------------------------------------------
    def test_due_selection_queue_ordering_and_timezone_boundary(self):
        """Due selection respects queue ordering (learning -> review -> new), excludes suspended/buried, and enforces 4 AM local boundary."""
        with self.app.app_context():
            now = datetime(2026, 8, 29, 10, 0, 0)
            today_day = _day_index(now, boundary_hour=4, timezone_name="Asia/Ho_Chi_Minh")

            # 1. Queue Ordering Invariant: Learning (priority 0) > Review (priority 1) > New (priority 2)
            # Card A: Due Review Card
            p_rev = CardProgress(
                user_id=self.author_id,
                card_id=self.card_a_id,
                queue="review",
                due_day=today_day - 1,
                interval_days=5,
                is_suspended=False,
                is_buried=False,
            )
            # Card B: Learning Card due right now
            p_learn = CardProgress(
                user_id=self.author_id,
                card_id=self.card_b_id,
                queue="learning",
                due_at=now - timedelta(minutes=5),
                interval_days=0,
                is_suspended=False,
                is_buried=False,
            )
            # Card C: New Card
            note_c = Note(user_id=self.author_id, note_type_id=self.note_type_id, deck_id=self.deck_id, field_values={})
            db.session.add(note_c)
            db.session.flush()
            card_c = Card(note_id=note_c.id, template_id=self.template_id)
            db.session.add_all([p_rev, p_learn, card_c])
            db.session.commit()

            # Query queue ordering: learning card must be selected first
            next_card_id = query_next_due_card_id(
                Card.query.filter(Card.id.in_([self.card_a_id, self.card_b_id, card_c.id])),
                user_id=self.author_id,
                now=now,
                timezone_name="Asia/Ho_Chi_Minh",
            )
            self.assertEqual(next_card_id, self.card_b_id)  # Learning card first

            # 2. Suspended and Buried Exclusion Invariant
            # Card D: Suspended
            note_d = Note(user_id=self.author_id, note_type_id=self.note_type_id, deck_id=self.deck_id, field_values={})
            db.session.add(note_d)
            db.session.flush()
            card_d = Card(note_id=note_d.id, template_id=self.template_id)
            db.session.add(card_d)
            db.session.flush()
            p_susp = CardProgress(
                user_id=self.author_id,
                card_id=card_d.id,
                queue="review",
                due_day=today_day - 1,
                is_suspended=True,
                is_buried=False,
            )
            # Card E: Buried
            note_e = Note(user_id=self.author_id, note_type_id=self.note_type_id, deck_id=self.deck_id, field_values={})
            db.session.add(note_e)
            db.session.flush()
            card_e = Card(note_id=note_e.id, template_id=self.template_id)
            db.session.add(card_e)
            db.session.flush()
            p_buried = CardProgress(
                user_id=self.author_id,
                card_id=card_e.id,
                queue="review",
                due_day=today_day - 1,
                is_suspended=False,
                is_buried=True,
                buried_until_day=today_day,
            )
            db.session.add_all([p_susp, p_buried])
            db.session.commit()

            new_cnt, learn_cnt, due_cnt = query_study_queue_counts(
                Card.query.filter(Card.id.in_([self.card_a_id, self.card_b_id, card_c.id, card_d.id, card_e.id])),
                user_id=self.author_id,
                now=now,
                timezone_name="Asia/Ho_Chi_Minh",
            )
            self.assertEqual(new_cnt, 1)    # card_c
            self.assertEqual(learn_cnt, 1)  # card_b
            self.assertEqual(due_cnt, 1)    # only card_a (card_d suspended and card_e buried are excluded)

            # 3. 4 AM Day Boundary Invariant across Multiple Timezones with Independent Expected Values
            tz_test_cases = [
                # (timezone_name, utc_datetime_for_03_59_59_local, utc_datetime_for_04_00_00_local, target_date)
                (
                    "Asia/Ho_Chi_Minh",  # UTC+7
                    datetime(2026, 8, 28, 20, 59, 59),  # 03:59:59 on Aug 29 local
                    datetime(2026, 8, 28, 21, 0, 0),    # 04:00:00 on Aug 29 local
                    date(2026, 8, 29),
                ),
                (
                    "Asia/Tokyo",  # UTC+9
                    datetime(2026, 8, 28, 18, 59, 59),  # 03:59:59 on Aug 29 local
                    datetime(2026, 8, 28, 19, 0, 0),    # 04:00:00 on Aug 29 local
                    date(2026, 8, 29),
                ),
                (
                    "UTC-4",  # UTC-4 (Fixed offset EDT)
                    datetime(2026, 8, 29, 7, 59, 59),   # 03:59:59 on Aug 29 local
                    datetime(2026, 8, 29, 8, 0, 0),     # 04:00:00 on Aug 29 local
                    date(2026, 8, 29),
                ),
                (
                    "UTC+0",  # UTC+0 (Fixed offset GMT)
                    datetime(2026, 8, 29, 3, 59, 59),   # 03:59:59 on Aug 29 local
                    datetime(2026, 8, 29, 4, 0, 0),     # 04:00:00 on Aug 29 local
                    date(2026, 8, 29),
                ),
            ]

            for tz_name, utc_before, utc_after, target_d in tz_test_cases:
                expected_before_ordinal = (target_d - timedelta(days=1)).toordinal()
                expected_after_ordinal = target_d.toordinal()

                actual_before = _day_index(utc_before, boundary_hour=4, timezone_name=tz_name)
                actual_after = _day_index(utc_after, boundary_hour=4, timezone_name=tz_name)

                self.assertEqual(
                    actual_before,
                    expected_before_ordinal,
                    f"Timezone {tz_name} at {utc_before} UTC should resolve to yesterday's day index",
                )
                self.assertEqual(
                    actual_after,
                    expected_after_ordinal,
                    f"Timezone {tz_name} at {utc_after} UTC should resolve to today's day index",
                )

    # -------------------------------------------------------------------------
    # 4. Import & Connect Provenance via Real Entrypoint
    # -------------------------------------------------------------------------
    def test_import_and_connect_provenance_via_real_entrypoint(self):
        """ReviewEvents generated via Anki/Connect import entrypoints are marked with import provenance and external references."""
        with self.app.app_context():
            # 1. Create real import session for author
            session_info = anki_import_service.create_session(
                user_id=self.author_id,
                payload={
                    "source": "anki",
                    "sourceKey": f"{self.author_id}:http://127.0.0.1:8765",
                    "sourceRootPath": "JLPT N5 Vocab",
                    "targetRootPath": "JLPT N5 Vocab",
                    "selectedDecks": ["JLPT N5 Vocab"],
                    "decks": [
                        {
                            "sourceDeckId": "anki-vocab",
                            "sourcePath": "JLPT N5 Vocab",
                            "targetPath": "JLPT N5 Vocab",
                        }
                    ],
                    "totalNotes": 1,
                    "totalMedia": 0,
                    "mode": "strict",
                    "noteTypes": [
                        {
                            "sourceModelId": "anki-model-1",
                            "sourceModelName": "Vocabulary NoteType",
                            "targetNoteTypeId": self.note_type_id,
                            "fields": [
                                {"name": "Word", "fieldType": "text"},
                                {"name": "Meaning", "fieldType": "text"},
                            ],
                            "templates": [
                                {
                                    "name": "Recognition",
                                    "frontHtml": "{{Word}}",
                                    "backHtml": "{{Meaning}}",
                                }
                            ],
                        }
                    ],
                },
            )
            session_id = session_info["importSessionId"]

            # 2. Upload card package via real service entrypoint
            card_record = {
                "ankiNoteId": 88001,
                "sourceModelId": "anki-model-1",
                "sourceDeckId": "anki-vocab",
                "sourceDeckPath": "JLPT N5 Vocab",
                "contentHash": "1" * 64,
                "note": {
                    "deckName": "JLPT N5 Vocab",
                    "modelName": str(self.note_type_id),
                    "fields": {"Word": "猫", "Meaning": "Cat"},
                    "tags": ["anki"],
                },
            }
            card_pkg = gzip.compress((json.dumps(card_record) + "\n").encode(), mtime=0)
            card_res = flama_connect_package_service.receive_card_package(
                user_id=self.author_id,
                session_id=session_id,
                sequence=0,
                expected_sha256=hashlib.sha256(card_pkg).hexdigest(),
                content=card_pkg,
                content_encoding="gzip",
            )
            self.assertEqual(card_res["status"], "processed")

            # 3. Upload progress package
            progress_record = {
                "externalNoteId": 88001,
                "sourceCardId": 99001,
                "ord": 0,
                "snapshotHash": "2" * 64,
                "type": 2,
                "queue": 2,
                "due": 50003,
                "sourceToday": 50000,
                "interval": 14,
                "factor": 2500,
                "reps": 2,
                "lapses": 1,
                "left": 0,
                "mod": 1,
            }
            prog_pkg = gzip.compress((json.dumps(progress_record) + "\n").encode(), mtime=0)
            flama_connect_package_service.receive_sync_package(
                user_id=self.author_id,
                session_id=session_id,
                sequence=0,
                kind="progress",
                expected_sha256=hashlib.sha256(prog_pkg).hexdigest(),
                content=prog_pkg,
                content_encoding="gzip",
            )

            # 4. Upload review sync package via real service entrypoint
            rev_time_ms = int(datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
            review_item = {
                "sourceReviewId": rev_time_ms,
                "sourceCardId": 99001,
                "ease": 3,
                "type": 1,
                "ivl": 10,
                "lastIvl": 5,
                "factor": 2500,
                "time": 2500,
            }
            review_pkg = gzip.compress((json.dumps(review_item) + "\n").encode(), mtime=0)
            rev_res = flama_connect_package_service.receive_sync_package(
                user_id=self.author_id,
                session_id=session_id,
                sequence=1,
                kind="reviews",
                expected_sha256=hashlib.sha256(review_pkg).hexdigest(),
                content=review_pkg,
                content_encoding="gzip",
            )
            self.assertEqual(rev_res["status"], "processed")

            # 5. Verify ReviewEvent and ConnectReviewEventRef provenance
            imported_ref = ConnectReviewEventRef.query.filter_by(
                user_id=self.author_id,
                external_review_id=str(rev_time_ms),
            ).first()
            self.assertIsNotNone(imported_ref)

            imported_event = db.session.get(ReviewEvent, imported_ref.review_event_id)
            self.assertIsNotNone(imported_event)
            self.assertEqual(imported_event.scheduler_mode, "anki")
            self.assertEqual(imported_event.scheduler_algorithm, "anki")

            # 6. Verify Native Review maintains native legacy-anki metadata
            now = datetime(2026, 8, 29, 10, 0, 0)
            author_user = db.session.get(User, self.author_id)
            card_a_obj = db.session.get(Card, self.card_a_id)
            study_service.execute_native_review_command(
                user=author_user,
                card=card_a_obj,
                action="good",
                payload={"duration_ms": 1500},
                clone_scope=None,
                requested_scope_id=None,
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )
            native_event = ReviewEvent.query.filter_by(
                user_id=self.author_id, card_id=self.card_a_id
            ).order_by(ReviewEvent.id.desc()).first()
            self.assertEqual(native_event.scheduler_mode, "legacy")
            self.assertEqual(native_event.scheduler_algorithm, "legacy-anki")
            self.assertEqual(native_event.algorithm_version, "1.0.0")
            runtime_meta = json.loads(native_event.payload_json)["_study_runtime"]
            self.assertEqual(runtime_meta["trigger_key"], "scheduler.review.good")

            # 7. Audit Engine Verification
            audit = build_study_architecture_audit()
            rg = audit["review_event_gates"]
            self.assertEqual(rg["anki_import_events"], 1)
            self.assertEqual(rg["native_direct_events"], 1)
            self.assertEqual(rg["conflicting_provenance_events"], 0)
            self.assertEqual(rg["unknown_provenance_events"], 0)

    # -------------------------------------------------------------------------
    # 5. Shared Deck Logical Overlay via Real Service Path
    # -------------------------------------------------------------------------
    def test_shared_deck_logical_overlay_via_real_service_path(self):
        """Real install/query/review path proves zero source card duplication, zero source note mutation, real local-added content, and isolated learner progress."""
        with self.app.app_context():
            initial_notes = Note.query.count()
            initial_cards = Card.query.count()

            # 1. Author publishes marketplace deck item
            deck_item = DeckMarketplaceItem(
                source_deck_id=self.deck_id,
                source_note_type_id=self.note_type_id,
                owner_user_id=self.author_id,
                title="Published JLPT N5 Master Deck",
                publish_status="published",
                pricing_mode="free",
                price_amount_minor=0,
            )
            db.session.add(deck_item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

            # 2. Learner installs via real flashcards_share_service entrypoint
            install_res, err, field, status_code = flashcards_share_service.install_shared_deck_item(
                deck_item_id=deck_item_id,
                user_id=self.learner_id,
                publish_statuses_visible={"published"},
            )
            self.assertEqual(status_code, 201)
            self.assertIsNotNone(install_res)
            local_deck_id = install_res["installed_deck_id"]

            # 3. Resolve clone scope and query cards via real query path
            scope = flashcards_share_service.resolve_clone_scope_for_local_deck(
                user_id=self.learner_id,
                local_deck_id=local_deck_id,
            )
            self.assertIsNotNone(scope)
            installed_cards = flashcards_share_service.query_clone_scope_cards(scope).all()
            self.assertEqual(len(installed_cards), 2)

            # 4. Zero Physical Duplication Invariant
            self.assertEqual(Note.query.count(), initial_notes)
            self.assertEqual(Card.query.count(), initial_cards)

            # 5. Learner reviews source card A through clone scope
            now = datetime(2026, 8, 29, 10, 0, 0)
            learner_user = db.session.get(User, self.learner_id)
            source_card_a = db.session.get(Card, self.card_a_id)

            study_service.execute_native_review_command(
                user=learner_user,
                card=source_card_a,
                action="good",
                payload={"duration_ms": 2000},
                clone_scope=scope,
                requested_scope_id=local_deck_id,
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )

            # Learner progress is created on source card; author has no progress
            learner_prog = CardProgress.query.filter_by(user_id=self.learner_id, card_id=self.card_a_id).one()
            self.assertEqual(learner_prog.reps, 1)
            author_prog = CardProgress.query.filter_by(user_id=self.author_id, card_id=self.card_a_id).first()
            self.assertIsNone(author_prog)

            # Source Note field values remain completely untouched (Zero Mutation)
            source_note_a = db.session.get(Note, self.note_a_id)
            self.assertEqual(source_note_a.field_values, {"Word": "猫", "Meaning": "Cat"})
            self.assertEqual(source_note_a.user_id, self.author_id)

            # 6. Learner creates a local custom note via real service entrypoint (add_note)
            installed_deck = db.session.get(Deck, local_deck_id)
            note_type = db.session.get(NoteType, self.note_type_id)
            added_note_id = add_note(
                user_id=self.learner_id,
                raw_note={
                    "deckName": installed_deck.name,
                    "modelName": note_type.name,
                    "fields": {"Word": "鳥", "Meaning": "Bird"},
                },
            )
            self.assertIsNotNone(added_note_id)

            ref = db.session.get(ConnectNoteRef, added_note_id)
            self.assertIsNotNone(ref)
            actual_note_id = ref.note_id

            # Service entrypoint automatically created the DeckCloneAddedNote association
            added_record = DeckCloneAddedNote.query.filter_by(
                deck_install_id=scope.install.id,
                note_id=actual_note_id,
            ).first()
            self.assertIsNotNone(added_record)

            # Scope query now includes source cards + learner's added card (3 cards)
            all_scope_cards = flashcards_share_service.query_clone_scope_cards(scope).all()
            self.assertEqual(len(all_scope_cards), 3)

            # Composition discovery and session opening use this exact real
            # overlay query. Source and learner-local cards must remain
            # distinguishable without materializing a physical clone.
            effective_query = flashcards_share_service.query_clone_scope_cards(scope)
            compositions = study_composition_service.list_available_compositions_for_query(
                effective_query,
                clone_scope=scope,
            )
            self.assertEqual(
                {item.context_kind for item in compositions},
                {"installed_source", "installed_local"},
            )
            self.assertTrue(
                all(item.composition_id.startswith(f"comp:install:{scope.install.id}:") for item in compositions)
            )

            for composition in compositions:
                selection = study_composition_service.resolve_composition_selection(
                    effective_query,
                    clone_scope=scope,
                    requested_composition_id=composition.composition_id,
                    request_source="acceptance-real-overlay",
                )
                composition_snapshot = study_session_service.open_study_session(
                    user=learner_user,
                    query=effective_query,
                    clone_scope=scope,
                    scope_type="deck",
                    scope_id=str(local_deck_id),
                    timezone_name="Asia/Ho_Chi_Minh",
                    composition_selection=selection,
                    now=now,
                )
                self.assertEqual(
                    composition_snapshot["selected_composition_id"],
                    composition.composition_id,
                )
                self.assertTrue(composition_snapshot["cards"])
                self.assertEqual(
                    {card["composition_id"] for card in composition_snapshot["cards"]},
                    {composition.composition_id},
                )

            self.assertEqual(Note.query.count(), initial_notes + 1)
            self.assertEqual(Card.query.count(), initial_cards + 1)

            # 7. Learner reviews local-added card through clone scope
            custom_card = Card.query.filter_by(note_id=actual_note_id).first()
            self.assertIsNotNone(custom_card)

            study_service.execute_native_review_command(
                user=learner_user,
                card=custom_card,
                action="good",
                payload={"duration_ms": 1800},
                clone_scope=scope,
                requested_scope_id=local_deck_id,
                timezone_name="Asia/Ho_Chi_Minh",
                now=now,
            )

            # Progress created for learner on local added card
            custom_prog = CardProgress.query.filter_by(user_id=self.learner_id, card_id=custom_card.id).one()
            self.assertEqual(custom_prog.reps, 1)

            # Author's notes query still only contains original author notes (2 notes)
            author_notes = Note.query.filter_by(deck_id=self.deck_id, user_id=self.author_id).all()
            self.assertEqual(len(author_notes), 2)

    # -------------------------------------------------------------------------
    # 6. Study Action Runtime Validation & Unauthorized Action Rejection
    # -------------------------------------------------------------------------
    def test_study_action_runtime_validates_and_rejects_unauthorized_actions(self):
        """Study action runtime validates semantic review actions and rejects unauthorized/forged actions without progress side effects."""
        with self.app.app_context():
            # Initial progress
            initial_progress = CardProgress(
                user_id=self.author_id,
                card_id=self.card_a_id,
                queue="review",
                interval_days=1,
                reps=1,
            )
            db.session.add(initial_progress)
            db.session.commit()

            from app.services.study_action_runtime import (
                resolve_review_action,
                StudyActionValidationError,
            )

            # 1. Valid actions resolve to deterministic action & trigger keys
            for valid_rating in ["again", "hard", "good", "easy"]:
                action_contract = resolve_review_action(valid_rating)
                self.assertEqual(action_contract.rating, valid_rating)
                self.assertEqual(action_contract.action_key, f"review.{valid_rating}")
                self.assertEqual(action_contract.trigger_key, f"scheduler.review.{valid_rating}")

            # 2. Forged or arbitrary actions fail closed
            for invalid_action in ["untrusted_script_eval", "rate_10", "grant_admin", "", None]:
                with self.assertRaises(StudyActionValidationError):
                    resolve_review_action(invalid_action)  # type: ignore[arg-type]

            # 3. Ensure progress was NOT modified
            p = CardProgress.query.filter_by(user_id=self.author_id, card_id=self.card_a_id).one()
            self.assertEqual(p.reps, 1)
            self.assertEqual(p.interval_days, 1)


if __name__ == "__main__":
    unittest.main()
