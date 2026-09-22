"""Integration coverage for frontend-driven study sessions."""

import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.repositories.study_authority_repository import StudyAuthorityFenceError
from app.services.anki_scheduler import _day_index, applyAnswer
from app.services.study_progress_contract import MAPPER_VERSION
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    map_card_progress,
)
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
from app.services.study_authority_enrollment_service import (
    StudyAuthorityEnrollmentError,
    stage_legacy_authority_enrollment,
    stage_note_authority_enrollment,
)
from app.services.study_session_config import (
    StudySessionConfigError,
    decode_study_session_config,
)
from app.validators.flashcard_input import RequestValidationError
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
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_session_authority_pin import StudySessionAuthorityPin
from models.study_session_batch import StudySessionBatch
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

    def _enable_existing_state_note_authority(self, *, epoch=1, enroll=True):
        with self.app.app_context():
            note = Note.query.filter_by(
                user_id=self.user_id,
                deck_id=self.deck_id,
            ).one()
            now = datetime(2026, 9, 21, 8, 0, 0)
            card = Card.query.filter_by(note_id=note.id).one()
            progress = CardProgress(
                    user_id=self.user_id,
                    card_id=str(card.id),
                    queue="new",
                    step_index=0,
                    interval_days=0,
                    interval_days_raw=0.0,
                    is_suspended=False,
                    is_buried=False,
                    review_kind="review",
                    scheduler_mode="legacy",
                    ease_factor=2.5,
                    last_leech_lapses=0,
                    reps=0,
                    lapses=0,
                    revision=0,
                    created_at=now,
                    updated_at=now,
                )
            db.session.add(progress)
            db.session.flush()
            mapped = map_card_progress(progress, card_created_at=card.created_at)
            self.assertIsInstance(mapped, MappedCardProgress)
            subject = StudyProgressSubject(
                learner_user_id=self.user_id,
                logical_note_key=str(note.id).encode("utf-8"),
                live_note_id=str(note.id),
                subject_generation=1,
                mirror_revision=1,
                status_code="MIRRORED_SINGLE",
                contributor_count=1,
                mapper_version=MAPPER_VERSION,
                created_at=now,
                updated_at=now,
            )
            db.session.add(subject)
            db.session.flush()
            contributor = StudyProgressContributor(
                subject_id=int(subject.id),
                subject_generation=1,
                source_progress_id=int(progress.id),
                live_card_progress_id=int(progress.id),
                logical_card_key=str(card.id).encode("utf-8"),
                live_card_id=str(card.id),
                card_progress_revision=0,
                raw_schema_version=mapped.raw_schema_version,
                storage_codec=mapped.storage_codec,
                raw_payload=mapped.raw.payload,
                raw_payload_size=mapped.raw.size,
                raw_progress_hash=mapped.raw.digest,
                pointer_status="ABSENT",
                history_completeness_code="HISTORY_NATIVE_COMPLETE",
                current_provenance_code="UNKNOWN_LEGACY",
                lineage_vector_hash=b"\x44" * 32,
                contributor_status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            db.session.add(contributor)
            db.session.flush()
            availability = mapped.availability
            db.session.add_all(
                [
                    StudyProgressState(
                        subject_id=int(subject.id),
                        subject_generation=1,
                        mirror_revision=1,
                        algorithm_key=mapped.algorithm_key,
                        algorithm_version=mapped.algorithm_version,
                        state_schema_version=mapped.state_schema_version,
                        storage_codec=mapped.storage_codec,
                        state_payload=mapped.state.payload,
                        state_payload_size=mapped.state.size,
                        algorithm_state_hash=mapped.algorithm_state_hash,
                        semantic_state_hash=mapped.semantic_state_hash,
                        created_at=now,
                        updated_at=now,
                    ),
                    StudyProgressAvailability(
                        contributor_id=int(contributor.id),
                        subject_id=int(subject.id),
                        subject_generation=1,
                        projection_version=availability.projection_version,
                        normalized_queue=availability.normalized_queue,
                        due_at=availability.due_at,
                        due_day=availability.due_day,
                        is_suspended=availability.is_suspended,
                        is_buried=availability.is_buried,
                        buried_until_day=availability.buried_until_day,
                        card_created_at=availability.card_created_at,
                        card_order_key=availability.card_order_key,
                        state_schema_version=availability.state_schema_version,
                        semantic_state_hash=availability.semantic_state_hash,
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            expected_hash = mapped.semantic_state_hash.hex()
            if enroll:
                db.session.add(
                    StudyAuthorityEnrollment(
                        learner_user_id=self.user_id,
                        mode_code="NOTE",
                        epoch=epoch,
                        created_at=now,
                        updated_at=now,
                    )
                )
            db.session.commit()
            return str(note.id), expected_hash

    def _open_session_v4(self):
        previous_v4 = self.app.config["STUDY_WIRE_V4_ENABLED"]
        self.app.config["STUDY_WIRE_V4_ENABLED"] = True
        try:
            response = self.client.post(
                "/api/study/sessions",
                json={
                    "scope": "deck",
                    "scope_id": self.deck_id,
                    "accepted_session_schema_versions": ["study-session.v4"],
                },
            )
        finally:
            self.app.config["STUDY_WIRE_V4_ENABLED"] = previous_v4
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_note_authority_deck_reset_reinitializes_state_and_invalidates_pin(self):
        self._enable_existing_state_note_authority(epoch=7)
        with self.app.app_context():
            card_id = str(Card.query.join(Note, Card.note_id == Note.id).one().id)
        reviewed = self.client.post(
            f"/api/study/{card_id}/answer",
            json={
                "rating": "good",
                "scope": "deck",
                "scope_id": self.deck_id,
                "operation_key": str(uuid4()),
            },
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.get_json())
        snapshot = self._open_session_v4()

        response = self.client.post(f"/api/decks/{self.deck_id}/progress-reset")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["deleted_progress_count"], 1)

        with self.app.app_context():
            self.assertEqual(CardProgress.query.count(), 1)
            self.assertEqual(StudyProgressState.query.count(), 1)
            self.assertEqual(StudyProgressAvailability.query.count(), 1)
            subject = StudyProgressSubject.query.one()
            token = StudyAuthoritySubjectToken.query.one()
            contributors = StudyProgressContributor.query.order_by(
                StudyProgressContributor.id.asc()
            ).all()
            lifecycle = StudyProgressLifecycleEvent.query.one()
            session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
            self.assertEqual(int(subject.subject_generation), 2)
            self.assertEqual(int(subject.mirror_revision), 3)
            self.assertEqual(int(subject.contributor_count), 1)
            self.assertEqual(int(token.subject_generation), 2)
            self.assertEqual(int(token.authority_revision), 2)
            self.assertEqual(
                bytes(token.semantic_state_hash),
                bytes(StudyProgressState.query.one().semantic_state_hash),
            )
            self.assertEqual(len(contributors), 2)
            self.assertEqual(contributors[0].contributor_status, "TOMBSTONED")
            self.assertIsNone(contributors[0].live_card_progress_id)
            self.assertEqual(contributors[1].contributor_status, "ACTIVE")
            self.assertEqual(lifecycle.transition_code, "TOMBSTONED_RESET")
            self.assertEqual(
                (int(lifecycle.old_generation), int(lifecycle.new_generation)),
                (1, 2),
            )
            self.assertEqual(session.status, "cancelled")

        fresh = self._open_session_v4()
        self.assertEqual(fresh["cards"][0]["state"]["type"], "new")
        self.assertEqual(
            fresh["cards"][0]["authority_pin"]["subject_generation"],
            "2",
        )

        repeated = self.client.post(f"/api/decks/{self.deck_id}/progress-reset")
        self.assertEqual(repeated.status_code, 200, repeated.get_json())
        self.assertEqual(repeated.get_json()["deleted_progress_count"], 0)
        with self.app.app_context():
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 1)

        after_repeat = self._open_session_v4()
        committed = self.client.post(
            f"/api/study/sessions/{after_repeat['session_id']}/commit",
            json=self._commit_payload(after_repeat),
        )
        self.assertEqual(committed.status_code, 200, committed.get_json())

    def test_note_authority_deck_reset_rolls_back_stale_projection(self):
        self._enable_existing_state_note_authority(epoch=7)
        with self.app.app_context():
            StudyProgressAvailability.query.one().normalized_queue = "review"
            db.session.commit()

        response = self.client.post(f"/api/decks/{self.deck_id}/progress-reset")
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "STALE_AUTHORITY_AVAILABILITY")

        with self.app.app_context():
            self.assertEqual(CardProgress.query.count(), 1)
            self.assertEqual(StudyProgressState.query.count(), 1)
            self.assertEqual(StudyProgressAvailability.query.count(), 1)
            subject = StudyProgressSubject.query.one()
            self.assertEqual(int(subject.subject_generation), 1)
            self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def test_note_authority_new_note_materializes_before_first_review(self):
        self._enable_existing_state_note_authority(epoch=8)

        created = self.client.post(
            "/api/notes",
            json={
                "note_type_id": self.note_type_id,
                "deck_id": self.deck_id,
                "field_values": {"Word": "犬"},
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        new_card_id = created.get_json()["first_card_id"]

        snapshot = self._open_session_v4()
        self.assertEqual(len(snapshot["cards"]), 2)
        new_card = next(
            card for card in snapshot["cards"] if card["card_id"] == new_card_id
        )
        self.assertEqual(new_card["state"]["type"], "new")
        self.assertEqual(new_card["authority_pin"]["base_authority_revision"], "0")

        reviewed = self.client.post(
            f"/api/study/{new_card_id}/answer",
            json={
                "rating": "good",
                "scope": "deck",
                "scope_id": self.deck_id,
                "operation_key": str(uuid4()),
            },
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.get_json())
        self.assertEqual(reviewed.get_json()["authority"]["authority_revision"], 1)

        with self.app.app_context():
            self.assertEqual(Note.query.count(), 2)
            self.assertEqual(CardProgress.query.count(), 2)
            self.assertEqual(StudyProgressSubject.query.count(), 2)
            self.assertEqual(StudyProgressState.query.count(), 2)
            self.assertEqual(StudyProgressContributor.query.count(), 2)
            self.assertEqual(StudyProgressAvailability.query.count(), 2)
            new_subject = StudyProgressSubject.query.filter_by(
                live_note_id=created.get_json()["id"]
            ).one()
            new_token = db.session.get(
                StudyAuthoritySubjectToken, int(new_subject.id)
            )
            self.assertEqual(int(new_subject.subject_generation), 1)
            self.assertEqual(int(new_subject.mirror_revision), 2)
            self.assertEqual(int(new_token.authority_revision), 1)
            self.assertEqual(ReviewEvent.query.count(), 1)

    def test_note_authority_mcp_note_create_and_delete_use_canonical_lifecycle(self):
        self._enable_existing_state_note_authority(epoch=9)
        with self.app.app_context():
            from app.services.mcp.note_tools import create_note, delete_note

            created = create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"Word": "é³¥"},
                },
            )
            new_note_id = created["note_id"]
            new_subject = StudyProgressSubject.query.filter_by(
                live_note_id=new_note_id
            ).one()
            new_contributor = StudyProgressContributor.query.filter_by(
                subject_id=int(new_subject.id),
                contributor_status="ACTIVE",
            ).one()
            self.assertEqual(
                new_contributor.current_provenance_code, "NATIVE_MCP"
            )
            self.assertEqual(
                new_contributor.history_completeness_code,
                "HISTORY_NATIVE_COMPLETE",
            )
            self.assertEqual(int(new_subject.subject_generation), 1)
            self.assertEqual(int(new_subject.mirror_revision), 1)

            deleted = delete_note(
                user_id=self.user_id,
                note_id=new_note_id,
                confirm=True,
            )
            self.assertTrue(deleted["success"])
            db.session.expire_all()
            tombstone = db.session.get(
                StudyProgressSubject, int(new_subject.id)
            )
            token = db.session.get(
                StudyAuthoritySubjectToken, int(new_subject.id)
            )
            self.assertIsNone(db.session.get(Note, new_note_id))
            self.assertEqual(
                tombstone.status_code, "TOMBSTONED_SUBJECT_DELETED"
            )
            self.assertEqual(int(tombstone.subject_generation), 2)
            self.assertEqual(int(token.subject_generation), 2)
            self.assertEqual(int(token.authority_revision), 1)

    def test_note_authority_mcp_template_bulk_fails_closed_and_note_batch_deletes(self):
        self._enable_existing_state_note_authority(epoch=10)
        with self.app.app_context():
            from app.services.mcp.note_tools import batch_delete_notes, create_note
            from app.services.mcp.note_type_tools import update_note_type

            with self.assertRaises(RequestValidationError) as failure:
                update_note_type(
                    user_id=self.user_id,
                    note_type_id=self.note_type_id,
                    templates={"added": [{"name": "Unsafe Card"}]},
                )
            self.assertEqual(
                failure.exception.code,
                "NOTE_AUTHORITY_UNAVAILABLE",
            )
            db.session.rollback()
            self.assertEqual(Template.query.count(), 1)
            self.assertEqual(Card.query.count(), 1)
            first_note_id = str(Note.query.one().id)
            second = create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"Word": "é­š"},
                },
            )
            deleted = batch_delete_notes(
                user_id=self.user_id,
                note_ids=[first_note_id, second["note_id"]],
                confirm=True,
            )
            self.assertEqual(deleted["deleted_count"], 2)
            self.assertEqual(deleted["deleted_cards_count"], 2)
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(Card.query.count(), 0)
            self.assertEqual(CardProgress.query.count(), 0)
            subjects = StudyProgressSubject.query.all()
            self.assertEqual(len(subjects), 2)
            self.assertTrue(
                all(
                    subject.status_code == "TOMBSTONED_SUBJECT_DELETED"
                    and int(subject.subject_generation) == 2
                    for subject in subjects
                )
            )
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 2)

    def test_note_authority_new_template_materializes_exact_sibling(self):
        _note_id, _state_hash = self._enable_existing_state_note_authority(epoch=11)
        with self.app.app_context():
            original_card_id = str(Card.query.one().id)
        reviewed = self.client.post(
            f"/api/study/{original_card_id}/answer",
            json={
                "rating": "good",
                "scope": "deck",
                "scope_id": self.deck_id,
                "operation_key": str(uuid4()),
            },
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.get_json())
        old_snapshot = self._open_session_v4()

        created = self.client.post(
            f"/api/note-types/{self.note_type_id}/templates",
            json={
                "name": "Card 2",
                "front_html": "Reverse {{Word}}",
                "back_html": "{{Word}}",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        template_id = created.get_json()["id"]
        self.assertEqual(created.get_json()["position"], 1)

        with self.app.app_context():
            cards = Card.query.order_by(Card.id.asc()).all()
            self.assertEqual(len(cards), 2)
            new_card = Card.query.filter_by(template_id=template_id).one()
            new_card_id = str(new_card.id)
            progress_rows = CardProgress.query.order_by(
                CardProgress.card_id.asc()
            ).all()
            self.assertEqual(len(progress_rows), 2)
            mapped = {
                str(row.card_id): map_card_progress(
                    row,
                    card_created_at=db.session.get(Card, row.card_id).created_at,
                )
                for row in progress_rows
            }
            self.assertTrue(
                all(isinstance(value, MappedCardProgress) for value in mapped.values())
            )
            self.assertEqual(
                len({value.semantic_state_hash for value in mapped.values()}),
                1,
            )
            subject = StudyProgressSubject.query.one()
            token = StudyAuthoritySubjectToken.query.one()
            state = StudyProgressState.query.one()
            old_session = db.session.get(
                StudySession, old_snapshot["session_id"]
            )
            self.assertEqual(int(subject.subject_generation), 2)
            self.assertEqual(int(subject.mirror_revision), 3)
            self.assertEqual(int(subject.contributor_count), 2)
            self.assertEqual(subject.status_code, "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE")
            self.assertEqual(int(token.subject_generation), 2)
            self.assertEqual(int(token.authority_revision), 1)
            self.assertEqual(
                bytes(token.semantic_state_hash),
                bytes(state.semantic_state_hash),
            )
            self.assertEqual(StudyProgressContributor.query.count(), 3)
            self.assertEqual(
                StudyProgressContributor.query.filter_by(
                    contributor_status="ACTIVE"
                ).count(),
                2,
            )
            self.assertEqual(
                StudyProgressContributor.query.filter_by(
                    contributor_status="DETACHED"
                ).count(),
                1,
            )
            new_contributor = StudyProgressContributor.query.filter_by(
                live_card_id=new_card_id,
                contributor_status="ACTIVE",
            ).one()
            self.assertEqual(
                new_contributor.current_provenance_code, "NATIVE_DIRECT"
            )
            self.assertEqual(
                new_contributor.history_completeness_code,
                "HISTORY_NATIVE_COMPLETE",
            )
            self.assertEqual(StudyProgressAvailability.query.count(), 2)
            self.assertEqual(old_session.status, "cancelled")

        previous_v4 = self.app.config["STUDY_WIRE_V4_ENABLED"]
        self.app.config["STUDY_WIRE_V4_ENABLED"] = True
        try:
            fresh_response = self.client.post(
                "/api/study/sessions",
                json={
                    "scope": "deck",
                    "scope_id": self.deck_id,
                    "composition_id": (
                        f"comp:notetype:{self.note_type_id}:template:{template_id}"
                    ),
                    "accepted_session_schema_versions": ["study-session.v4"],
                },
            )
        finally:
            self.app.config["STUDY_WIRE_V4_ENABLED"] = previous_v4
        self.assertEqual(
            fresh_response.status_code, 201, fresh_response.get_json()
        )
        fresh = fresh_response.get_json()
        self.assertEqual(fresh["cards"][0]["card_id"], new_card_id)
        self.assertEqual(
            fresh["cards"][0]["authority_pin"]["subject_generation"], "2"
        )
        self.assertEqual(
            fresh["cards"][0]["authority_pin"]["base_authority_revision"], "1"
        )
        committed = self.client.post(
            f"/api/study/sessions/{fresh['session_id']}/commit",
            json=self._commit_payload(fresh),
        )
        self.assertEqual(committed.status_code, 200, committed.get_json())

    def test_note_authority_new_template_rolls_back_stale_projection(self):
        self._enable_existing_state_note_authority(epoch=12)
        with self.app.app_context():
            template_count = Template.query.count()
            card_count = Card.query.count()
            StudyProgressAvailability.query.one().normalized_queue = "review"
            db.session.commit()

        response = self.client.post(
            f"/api/note-types/{self.note_type_id}/templates",
            json={
                "name": "Rejected Card",
                "front_html": "{{Word}}",
                "back_html": "{{Word}}",
            },
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "STALE_AUTHORITY_AVAILABILITY")

        with self.app.app_context():
            self.assertEqual(Template.query.count(), template_count)
            self.assertEqual(Card.query.count(), card_count)
            self.assertEqual(CardProgress.query.count(), 1)
            subject = StudyProgressSubject.query.one()
            self.assertEqual(int(subject.subject_generation), 1)
            self.assertEqual(int(subject.mirror_revision), 1)

    def test_note_authority_template_delete_detaches_sibling_and_fences_pin(self):
        self._enable_existing_state_note_authority(epoch=13)
        created = self.client.post(
            f"/api/note-types/{self.note_type_id}/templates",
            json={
                "name": "Disposable Card",
                "front_html": "{{Word}}",
                "back_html": "{{Word}}",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        template_id = created.get_json()["id"]
        with self.app.app_context():
            removed_card_id = str(
                Card.query.filter_by(template_id=template_id).one().id
            )

        previous_v4 = self.app.config["STUDY_WIRE_V4_ENABLED"]
        self.app.config["STUDY_WIRE_V4_ENABLED"] = True
        try:
            open_response = self.client.post(
                "/api/study/sessions",
                json={
                    "scope": "deck",
                    "scope_id": self.deck_id,
                    "composition_id": (
                        f"comp:notetype:{self.note_type_id}:template:{template_id}"
                    ),
                    "accepted_session_schema_versions": ["study-session.v4"],
                },
            )
        finally:
            self.app.config["STUDY_WIRE_V4_ENABLED"] = previous_v4
        self.assertEqual(open_response.status_code, 201, open_response.get_json())
        snapshot = open_response.get_json()

        deleted = self.client.delete(
            f"/api/note-types/{self.note_type_id}/templates/{template_id}"
        )
        self.assertEqual(deleted.status_code, 200, deleted.get_json())
        self.assertTrue(deleted.get_json()["success"])

        with self.app.app_context():
            self.assertIsNone(db.session.get(Template, template_id))
            self.assertIsNone(db.session.get(Card, removed_card_id))
            self.assertEqual(Template.query.count(), 1)
            self.assertEqual(Card.query.count(), 1)
            self.assertEqual(CardProgress.query.count(), 1)
            subject = StudyProgressSubject.query.one()
            token = StudyAuthoritySubjectToken.query.one()
            state = StudyProgressState.query.one()
            lifecycle = StudyProgressLifecycleEvent.query.one()
            old_session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
            self.assertEqual(int(subject.subject_generation), 3)
            self.assertEqual(int(subject.mirror_revision), 3)
            self.assertEqual(int(subject.contributor_count), 1)
            self.assertEqual(int(token.subject_generation), 3)
            self.assertEqual(int(token.authority_revision), 0)
            self.assertEqual(
                bytes(token.semantic_state_hash),
                bytes(state.semantic_state_hash),
            )
            self.assertEqual(
                StudyProgressContributor.query.filter_by(
                    contributor_status="ACTIVE"
                ).count(),
                1,
            )
            self.assertEqual(StudyProgressAvailability.query.count(), 1)
            self.assertEqual(
                lifecycle.transition_code,
                "DETACHED_CONTRIBUTOR_DELETED",
            )
            self.assertEqual(
                (int(lifecycle.old_generation), int(lifecycle.new_generation)),
                (2, 3),
            )
            self.assertEqual(old_session.status, "cancelled")
            remaining_card_id = str(Card.query.one().id)

        reviewed = self.client.post(
            f"/api/study/{remaining_card_id}/answer",
            json={
                "rating": "good",
                "scope": "deck",
                "scope_id": self.deck_id,
                "operation_key": str(uuid4()),
            },
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.get_json())
        self.assertEqual(reviewed.get_json()["authority"]["authority_revision"], 1)

    def test_note_authority_template_delete_rolls_back_stale_projection(self):
        self._enable_existing_state_note_authority(epoch=14)
        created = self.client.post(
            f"/api/note-types/{self.note_type_id}/templates",
            json={
                "name": "Retained Card",
                "front_html": "{{Word}}",
                "back_html": "{{Word}}",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        template_id = created.get_json()["id"]
        with self.app.app_context():
            StudyProgressAvailability.query.first().normalized_queue = "review"
            db.session.commit()

        response = self.client.delete(
            f"/api/note-types/{self.note_type_id}/templates/{template_id}"
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "STALE_AUTHORITY_AVAILABILITY")

        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Template, template_id))
            self.assertEqual(Template.query.count(), 2)
            self.assertEqual(Card.query.count(), 2)
            self.assertEqual(CardProgress.query.count(), 2)
            subject = StudyProgressSubject.query.one()
            self.assertEqual(int(subject.subject_generation), 2)
            self.assertEqual(int(subject.mirror_revision), 2)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def test_note_authority_new_template_expands_every_owned_note(self):
        self._enable_existing_state_note_authority(epoch=15)
        second_note = self.client.post(
            "/api/notes",
            json={
                "note_type_id": self.note_type_id,
                "deck_id": self.deck_id,
                "field_values": {"Word": "çŠ¬"},
            },
        )
        self.assertEqual(second_note.status_code, 201, second_note.get_json())

        created = self.client.post(
            f"/api/note-types/{self.note_type_id}/templates",
            json={
                "name": "Card 2",
                "front_html": "Reverse {{Word}}",
                "back_html": "{{Word}}",
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())

        with self.app.app_context():
            self.assertEqual(Note.query.count(), 2)
            self.assertEqual(Template.query.count(), 2)
            self.assertEqual(Card.query.count(), 4)
            self.assertEqual(CardProgress.query.count(), 4)
            subjects = StudyProgressSubject.query.order_by(
                StudyProgressSubject.logical_note_key.asc()
            ).all()
            self.assertEqual(len(subjects), 2)
            self.assertTrue(
                all(int(subject.subject_generation) == 2 for subject in subjects)
            )
            self.assertTrue(
                all(int(subject.mirror_revision) == 2 for subject in subjects)
            )
            self.assertTrue(
                all(int(subject.contributor_count) == 2 for subject in subjects)
            )
            tokens = StudyAuthoritySubjectToken.query.all()
            self.assertEqual(len(tokens), 2)
            self.assertTrue(
                all(int(token.subject_generation) == 2 for token in tokens)
            )
            self.assertTrue(
                all(int(token.authority_revision) == 0 for token in tokens)
            )
            self.assertEqual(
                StudyProgressContributor.query.filter_by(
                    contributor_status="ACTIVE"
                ).count(),
                4,
            )
            self.assertEqual(StudyProgressAvailability.query.count(), 4)

    def test_note_authority_owned_note_delete_tombstones_subject(self):
        note_id, _state_hash = self._enable_existing_state_note_authority(epoch=16)
        snapshot = self._open_session_v4()

        deleted = self.client.delete(f"/api/notes/{note_id}")
        self.assertEqual(deleted.status_code, 200, deleted.get_json())
        self.assertTrue(deleted.get_json()["success"])

        with self.app.app_context():
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(Card.query.count(), 0)
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(StudyProgressState.query.count(), 0)
            self.assertEqual(StudyProgressAvailability.query.count(), 0)
            subject = StudyProgressSubject.query.one()
            token = StudyAuthoritySubjectToken.query.one()
            contributor = StudyProgressContributor.query.one()
            lifecycle = StudyProgressLifecycleEvent.query.one()
            study_session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
            self.assertIsNone(subject.live_note_id)
            self.assertEqual(int(subject.subject_generation), 2)
            self.assertEqual(int(subject.mirror_revision), 2)
            self.assertEqual(int(subject.contributor_count), 0)
            self.assertEqual(int(token.subject_generation), 2)
            self.assertEqual(int(token.authority_revision), 1)
            self.assertIsNone(token.semantic_state_hash)
            self.assertEqual(contributor.contributor_status, "TOMBSTONED")
            self.assertIsNone(contributor.live_card_progress_id)
            self.assertIsNone(contributor.live_card_id)
            self.assertEqual(
                lifecycle.transition_code,
                "TOMBSTONED_SUBJECT_DELETED",
            )
            self.assertEqual(study_session.status, "cancelled")

    def test_note_authority_owned_deck_delete_tombstones_subject(self):
        self._enable_existing_state_note_authority(epoch=17)
        snapshot = self._open_session_v4()

        deleted = self.client.delete(f"/api/decks/{self.deck_id}")
        self.assertEqual(deleted.status_code, 200, deleted.get_json())
        self.assertEqual(
            deleted.get_json(),
            {"deleted": True, "id": self.deck_id, "mode": "deleted"},
        )

        with self.app.app_context():
            self.assertIsNone(db.session.get(Deck, self.deck_id))
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(Card.query.count(), 0)
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(StudyProgressState.query.count(), 0)
            self.assertEqual(StudyProgressAvailability.query.count(), 0)
            subject = StudyProgressSubject.query.one()
            token = StudyAuthoritySubjectToken.query.one()
            contributor = StudyProgressContributor.query.one()
            lifecycle = StudyProgressLifecycleEvent.query.one()
            study_session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
            self.assertIsNone(subject.live_note_id)
            self.assertEqual(int(subject.subject_generation), 2)
            self.assertEqual(int(subject.mirror_revision), 2)
            self.assertEqual(int(subject.contributor_count), 0)
            self.assertEqual(int(token.subject_generation), 2)
            self.assertEqual(int(token.authority_revision), 1)
            self.assertIsNone(token.semantic_state_hash)
            self.assertEqual(contributor.contributor_status, "TOMBSTONED")
            self.assertIsNone(contributor.live_card_progress_id)
            self.assertIsNone(contributor.live_card_id)
            self.assertEqual(
                lifecycle.transition_code,
                "TOMBSTONED_SUBJECT_DELETED",
            )
            self.assertEqual(lifecycle.source_path, "deck.delete")
            self.assertEqual(study_session.status, "cancelled")

    def test_note_authority_owned_deck_delete_rolls_back_stale_projection(self):
        self._enable_existing_state_note_authority(epoch=18)
        snapshot = self._open_session_v4()
        with self.app.app_context():
            StudyProgressAvailability.query.one().normalized_queue = "review"
            db.session.commit()

        deleted = self.client.delete(f"/api/decks/{self.deck_id}")
        self.assertEqual(deleted.status_code, 409, deleted.get_json())
        self.assertEqual(
            deleted.get_json()["error"],
            "STALE_AUTHORITY_AVAILABILITY",
        )

        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Deck, self.deck_id))
            self.assertEqual(Note.query.count(), 1)
            self.assertEqual(Card.query.count(), 1)
            self.assertEqual(CardProgress.query.count(), 1)
            self.assertEqual(StudyProgressState.query.count(), 1)
            self.assertEqual(StudyProgressAvailability.query.count(), 1)
            subject = StudyProgressSubject.query.one()
            study_session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
            self.assertEqual(int(subject.subject_generation), 1)
            self.assertEqual(int(subject.mirror_revision), 1)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)
            self.assertEqual(study_session.status, "open")

    @staticmethod
    def _commit_payload(snapshot, *, commit_id=None):
        card = snapshot["cards"][0]
        is_v3 = snapshot["schema_version"] == "study-session.v3"
        is_v4 = snapshot["schema_version"] == "study-session.v4"
        event_id = str(uuid4())
        event = {
            "event_id": event_id,
            "sequence": 1,
            "card_id": card["card_id"],
            "rating": "good",
            "policy_key": card["policy_key"],
            "scheduler_offset_ms": 1000,
            "duration_ms": 500,
        }
        if is_v3 or is_v4:
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
        if is_v4:
            pin = card["authority_pin"]
            event.update(
                {
                    "authority_mode": "NOTE",
                    "enrollment_epoch": pin["enrollment_epoch"],
                    "logical_note_key": pin["logical_note_key"],
                    "subject_generation": pin["subject_generation"],
                    "base_authority_revision": pin["base_authority_revision"],
                    "base_authority_state_hash": pin[
                        "base_authority_state_hash"
                    ],
                    "operation_key": event_id,
                }
            )
        return {
            "schema_version": (
                "study-commit.v3"
                if is_v4
                else "study-commit.v2" if is_v3 else "study-commit.v1"
            ),
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
        self.assertEqual(snapshot["selected_composition_id"], comp_id)
        self.assertEqual(snapshot["selected_composition"]["composition_id"], comp_id)
        self.assertEqual(
            snapshot["composition_binding"]["composition_id"],
            comp_id,
        )
        self.assertTrue(
            snapshot["composition_binding"]["binding_fingerprint"].startswith(
                "sha256-"
            )
        )
        self.assertEqual(card["base_revision"], 0)

        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            self.assertIsNotNone(session)
            self.assertEqual(session.status, "open")

    def test_session_config_accepts_valid_legacy_policy_map_only(self):
        snapshot = self._open_session()
        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            wrapped = json.loads(session.config_snapshot_json)

        legacy = decode_study_session_config(json.dumps(wrapped["policies"]))
        self.assertTrue(legacy.legacy)
        self.assertEqual(legacy.policies, wrapped["policies"])

        with self.assertRaises(StudySessionConfigError):
            decode_study_session_config(json.dumps({"policies": wrapped["policies"]}))
        with self.assertRaises(StudySessionConfigError):
            decode_study_session_config("{}")

    def test_unknown_or_tampered_versioned_session_config_fails_closed(self):
        snapshot = self._open_session()
        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            wrapped = json.loads(session.config_snapshot_json)

            unknown = {**wrapped, "schema_version": "study-session-config.v999"}
            session.config_snapshot_json = json.dumps(unknown)
            db.session.commit()

        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=self._commit_payload(snapshot),
        )
        self.assertEqual(response.status_code, 500, response.get_json())
        self.assertEqual(response.get_json()["error"], "INVALID_CONFIG_SNAPSHOT")

        wrapped["composition_binding"]["binding_fingerprint"] = (
            "sha256-" + "0" * 64
        )
        with self.assertRaises(StudySessionConfigError):
            decode_study_session_config(json.dumps(wrapped))

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

    def test_wire_v4_flag_keeps_legacy_enrollment_on_v3(self):
        previous_v3 = self.app.config["STUDY_WIRE_V3_ENABLED"]
        previous_v4 = self.app.config["STUDY_WIRE_V4_ENABLED"]
        self.app.config["STUDY_WIRE_V3_ENABLED"] = True
        self.app.config["STUDY_WIRE_V4_ENABLED"] = True
        try:
            response = self.client.post(
                "/api/study/sessions",
                json={
                    "scope": "deck",
                    "scope_id": self.deck_id,
                    "accepted_session_schema_versions": [
                        "study-session.v4",
                        "study-session.v3",
                        "study-session.v2",
                    ],
                },
            )
        finally:
            self.app.config["STUDY_WIRE_V3_ENABLED"] = previous_v3
            self.app.config["STUDY_WIRE_V4_ENABLED"] = previous_v4
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["schema_version"], "study-session.v3")
        with self.app.app_context():
            self.assertEqual(StudySession.query.count(), 1)
            self.assertEqual(StudySessionAuthorityPin.query.count(), 0)

    def test_wire_v4_note_enrollment_issues_frozen_authority_pin(self):
        note_id, expected_hash = self._enable_existing_state_note_authority(epoch=3)
        snapshot = self._open_session_v4()
        self.assertEqual(snapshot["schema_version"], "study-session.v4")
        self.assertEqual(snapshot["authority_mode"], "NOTE")
        self.assertEqual(snapshot["enrollment_epoch"], "3")
        self.assertEqual(len(snapshot["cards"]), 1)
        pin = snapshot["cards"][0]["authority_pin"]
        self.assertEqual(pin["logical_note_key"], note_id)
        self.assertEqual(pin["enrollment_epoch"], "3")
        self.assertEqual(pin["base_authority_revision"], "0")
        self.assertEqual(pin["base_authority_state_hash"], expected_hash)
        with self.app.app_context():
            persisted = StudySessionAuthorityPin.query.one()
            self.assertEqual(persisted.session_card.session_id, snapshot["session_id"])
            self.assertEqual(bytes(persisted.logical_note_key).decode(), note_id)

    def test_note_enrollment_switch_fences_and_cancels_legacy_lease(self):
        self._enable_existing_state_note_authority(enroll=False)
        legacy = self._open_session()
        with self.app.app_context():
            result = stage_note_authority_enrollment(
                db.session,
                learner_user_id=self.user_id,
                now_utc=datetime(2026, 9, 21, 9, 0, 0),
            )
            self.assertEqual(result.mode_code, "NOTE")
            self.assertEqual(result.epoch, 1)
            self.assertEqual(result.subject_count, 1)
            self.assertEqual(result.card_count, 1)
            self.assertEqual(result.cancelled_session_count, 1)
            db.session.commit()
            enrollment = db.session.get(StudyAuthorityEnrollment, self.user_id)
            self.assertEqual(enrollment.mode_code, "NOTE")
            self.assertEqual(enrollment.epoch, 1)
            self.assertEqual(
                db.session.get(StudySession, legacy["session_id"]).status,
                "cancelled",
            )
            self.assertEqual(StudyAuthoritySubjectToken.query.count(), 1)

    def test_note_enrollment_switch_materializes_pristine_owned_note(self):
        with self.app.app_context():
            result = stage_note_authority_enrollment(
                db.session,
                learner_user_id=self.user_id,
                now_utc=datetime(2026, 9, 21, 9, 0, 0),
            )
            self.assertEqual(result.mode_code, "NOTE")
            self.assertEqual(result.epoch, 1)
            self.assertEqual(result.subject_count, 1)
            self.assertEqual(result.card_count, 1)
            db.session.commit()

            enrollment = db.session.get(StudyAuthorityEnrollment, self.user_id)
            subject = StudyProgressSubject.query.one()
            token = StudyAuthoritySubjectToken.query.one()
            contributor = StudyProgressContributor.query.one()
            self.assertEqual(enrollment.mode_code, "NOTE")
            self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
            self.assertEqual(int(subject.subject_generation), 1)
            self.assertEqual(int(subject.mirror_revision), 1)
            self.assertEqual(int(token.authority_revision), 0)
            self.assertEqual(
                bytes(token.semantic_state_hash),
                bytes(StudyProgressState.query.one().semantic_state_hash),
            )
            self.assertEqual(contributor.current_provenance_code, "UNKNOWN_LEGACY")
            self.assertEqual(
                contributor.history_completeness_code,
                "HISTORY_NATIVE_COMPLETE",
            )

        snapshot = self._open_session_v4()
        self.assertEqual(snapshot["authority_mode"], "NOTE")
        self.assertEqual(snapshot["cards"][0]["state"]["type"], "new")
        self.assertEqual(
            snapshot["cards"][0]["authority_pin"]["base_authority_revision"],
            "0",
        )

    def test_note_enrollment_switch_reuses_pristine_empty_subject(self):
        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.user_id).one()
            now = datetime(2026, 9, 21, 8, 0, 0)
            subject = StudyProgressSubject(
                learner_user_id=self.user_id,
                logical_note_key=str(note.id).encode("utf-8"),
                live_note_id=str(note.id),
                subject_generation=1,
                mirror_revision=0,
                status_code="NO_CURRENT_PROGRESS",
                contributor_count=0,
                mapper_version=MAPPER_VERSION,
                created_at=now,
                updated_at=now,
            )
            db.session.add(subject)
            db.session.commit()
            subject_id = int(subject.id)

            result = stage_note_authority_enrollment(
                db.session,
                learner_user_id=self.user_id,
                now_utc=datetime(2026, 9, 21, 9, 0, 0),
            )
            db.session.commit()

            self.assertEqual(result.subject_count, 1)
            self.assertEqual(StudyProgressSubject.query.count(), 1)
            materialized = StudyProgressSubject.query.one()
            self.assertEqual(int(materialized.id), subject_id)
            self.assertEqual(materialized.status_code, "MIRRORED_SINGLE")
            self.assertEqual(CardProgress.query.count(), 1)
            self.assertEqual(StudyProgressState.query.count(), 1)
            self.assertEqual(StudyProgressContributor.query.count(), 1)
            self.assertEqual(StudyProgressAvailability.query.count(), 1)

    def test_note_enrollment_switch_rejects_partially_covered_siblings(self):
        self._enable_existing_state_note_authority(enroll=False)
        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.user_id).one()
            template = Template(
                note_type_id=self.note_type_id,
                name="Card 2",
                front_html="{{Word}}",
                back_html="{{Word}}",
                position=1,
            )
            db.session.add(template)
            db.session.flush()
            db.session.add(Card(note_id=note.id, template_id=template.id))
            db.session.commit()

            with self.assertRaises(StudyAuthorityEnrollmentError) as failure:
                stage_note_authority_enrollment(
                    db.session,
                    learner_user_id=self.user_id,
                    now_utc=datetime(2026, 9, 21, 9, 0, 0),
                )
            self.assertEqual(
                failure.exception.code,
                "INCOMPLETE_AUTHORITY_COVERAGE",
            )
            db.session.rollback()
            self.assertIsNone(
                db.session.get(StudyAuthorityEnrollment, self.user_id)
            )
            self.assertEqual(CardProgress.query.count(), 1)
            self.assertEqual(StudyProgressSubject.query.count(), 1)

    def test_note_enrollment_pristine_materialization_rolls_back_atomically(self):
        created = self.client.post(
            "/api/notes",
            json={
                "note_type_id": self.note_type_id,
                "deck_id": self.deck_id,
                "field_values": {"Word": "çŠ¬"},
            },
        )
        self.assertEqual(created.status_code, 201, created.get_json())

        with self.app.app_context():
            from app.services import study_progress_lifecycle_mirror_service

            original = (
                study_progress_lifecycle_mirror_service.materialize_new_note_authority
            )
            call_count = 0

            def fail_second_materialization(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise StudyAuthorityFenceError(
                        "INJECTED_ENROLLMENT_FAILURE",
                        "Injected second pristine Note failure.",
                    )
                return original(*args, **kwargs)

            with patch(
                "app.services.study_authority_enrollment_service."
                "study_progress_lifecycle_mirror_service."
                "materialize_new_note_authority",
                side_effect=fail_second_materialization,
            ):
                with self.assertRaises(StudyAuthorityEnrollmentError) as failure:
                    stage_note_authority_enrollment(
                        db.session,
                        learner_user_id=self.user_id,
                        now_utc=datetime(2026, 9, 21, 9, 0, 0),
                    )
            self.assertEqual(
                failure.exception.code,
                "INJECTED_ENROLLMENT_FAILURE",
            )
            db.session.rollback()
            self.assertIsNone(
                db.session.get(StudyAuthorityEnrollment, self.user_id)
            )
            self.assertEqual(Note.query.count(), 2)
            self.assertEqual(Card.query.count(), 2)
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(StudyProgressSubject.query.count(), 0)
            self.assertEqual(StudyAuthoritySubjectToken.query.count(), 0)
            self.assertEqual(StudyProgressState.query.count(), 0)
            self.assertEqual(StudyProgressContributor.query.count(), 0)
            self.assertEqual(StudyProgressAvailability.query.count(), 0)

    def test_note_enrollment_switch_rejects_in_flight_async_batch(self):
        self._enable_existing_state_note_authority(enroll=False)
        legacy = self._open_session()
        with self.app.app_context():
            db.session.add(
                StudySessionBatch(
                    session_id=legacy["session_id"],
                    user_id=self.user_id,
                    batch_id=str(uuid4()),
                    batch_sequence=1,
                    event_count=1,
                    status="processing",
                    commit_reason="manual_exit",
                    is_final=True,
                    request_hash="sha256-" + "1" * 64,
                    payload_json="{}",
                    enqueued_at=datetime(2026, 9, 21, 9, 0, 0),
                )
            )
            db.session.commit()

            with self.assertRaises(StudyAuthorityEnrollmentError) as failure:
                stage_note_authority_enrollment(
                    db.session,
                    learner_user_id=self.user_id,
                    now_utc=datetime(2026, 9, 21, 9, 30, 0),
                )
            self.assertEqual(failure.exception.code, "AUTHORITY_BATCH_IN_FLIGHT")
            db.session.rollback()
            self.assertIsNone(
                db.session.get(StudyAuthorityEnrollment, self.user_id)
            )
            self.assertEqual(
                db.session.get(StudySession, legacy["session_id"]).status,
                "open",
            )

    def test_authority_enrollment_cli_is_dry_run_by_default(self):
        self._enable_existing_state_note_authority(enroll=False)
        runner = self.app.test_cli_runner()

        dry_run = runner.invoke(
            args=[
                "study-authority-enrollment",
                "--user-id",
                str(self.user_id),
                "--mode",
                "NOTE",
            ]
        )
        self.assertEqual(dry_run.exit_code, 0, dry_run.output)
        dry_payload = json.loads(
            next(line for line in dry_run.output.splitlines() if line.startswith("{"))
        )
        self.assertFalse(dry_payload["applied"])
        with self.app.app_context():
            self.assertIsNone(
                db.session.get(StudyAuthorityEnrollment, self.user_id)
            )
            self.assertEqual(StudyAuthoritySubjectToken.query.count(), 0)

        blocked = runner.invoke(
            args=[
                "study-authority-enrollment",
                "--user-id",
                str(self.user_id),
                "--mode",
                "NOTE",
                "--apply",
            ]
        )
        self.assertNotEqual(blocked.exit_code, 0, blocked.output)
        self.assertIn("NOTE_ENROLLMENT_DISABLED", blocked.output)

        previous_v4 = self.app.config["STUDY_WIRE_V4_ENABLED"]
        self.app.config["STUDY_WIRE_V4_ENABLED"] = True
        try:
            applied = runner.invoke(
                args=[
                    "study-authority-enrollment",
                    "--user-id",
                    str(self.user_id),
                    "--mode",
                    "NOTE",
                    "--apply",
                ]
            )
        finally:
            self.app.config["STUDY_WIRE_V4_ENABLED"] = previous_v4
        self.assertEqual(applied.exit_code, 0, applied.output)
        payload = json.loads(
            next(line for line in applied.output.splitlines() if line.startswith("{"))
        )
        self.assertTrue(payload["applied"])
        self.assertEqual(payload["mode_code"], "NOTE")
        self.assertEqual(payload["epoch"], 1)
        with self.app.app_context():
            enrollment = db.session.get(StudyAuthorityEnrollment, self.user_id)
            self.assertEqual(enrollment.mode_code, "NOTE")
            self.assertEqual(enrollment.epoch, 1)

        audit = runner.invoke(
            args=[
                "study-authority-read-audit",
                "--user-id",
                str(self.user_id),
            ]
        )
        self.assertEqual(audit.exit_code, 0, audit.output)
        audit_payload = json.loads(
            next(line for line in audit.output.splitlines() if line.startswith("{"))
        )
        self.assertEqual(audit_payload["status"], "PASS")
        self.assertEqual(audit_payload["authority_mode"], "NOTE")
        self.assertEqual(audit_payload["mismatches"], [])

    def test_note_enrollment_rollback_proves_projection_and_fences_epoch(self):
        self._enable_existing_state_note_authority(epoch=4)
        snapshot = self._open_session_v4()
        with self.app.app_context():
            result = stage_legacy_authority_enrollment(
                db.session,
                learner_user_id=self.user_id,
                now_utc=datetime(2026, 9, 21, 9, 30, 0),
            )
            self.assertEqual(result.previous_mode, "NOTE")
            self.assertEqual(result.previous_epoch, 4)
            self.assertEqual(result.mode_code, "LEGACY")
            self.assertEqual(result.epoch, 5)
            self.assertEqual(result.subject_count, 1)
            self.assertEqual(result.card_count, 1)
            self.assertEqual(result.cancelled_session_count, 1)
            db.session.commit()

            enrollment = db.session.get(StudyAuthorityEnrollment, self.user_id)
            self.assertEqual(enrollment.mode_code, "LEGACY")
            self.assertEqual(enrollment.epoch, 5)
            self.assertEqual(
                db.session.get(StudySession, snapshot["session_id"]).status,
                "cancelled",
            )

        legacy = self._open_session()
        self.assertEqual(legacy["schema_version"], "study-session.v2")

    def test_note_enrollment_rollback_rejects_stale_availability(self):
        self._enable_existing_state_note_authority(epoch=7)
        with self.app.app_context():
            availability = StudyProgressAvailability.query.one()
            availability.semantic_state_hash = b"\x99" * 32
            db.session.commit()

            with self.assertRaises(StudyAuthorityEnrollmentError) as failure:
                stage_legacy_authority_enrollment(
                    db.session,
                    learner_user_id=self.user_id,
                    now_utc=datetime(2026, 9, 21, 9, 30, 0),
                )
            self.assertEqual(
                failure.exception.code,
                "STALE_AUTHORITY_AVAILABILITY",
            )
            db.session.rollback()
            enrollment = db.session.get(StudyAuthorityEnrollment, self.user_id)
            self.assertEqual(enrollment.mode_code, "NOTE")
            self.assertEqual(enrollment.epoch, 7)

    def test_wire_v4_commit_uses_note_authority_receipt_and_replays(self):
        _note_id, base_hash = self._enable_existing_state_note_authority(epoch=5)
        snapshot = self._open_session_v4()
        payload = self._commit_payload(snapshot, commit_id=str(uuid4()))
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        receipt = response.get_json()
        self.assertEqual(receipt["schema_version"], "study-commit-receipt.v2")
        self.assertEqual(receipt["authority_mode"], "NOTE")
        self.assertEqual(receipt["enrollment_epoch"], "5")
        self.assertEqual(receipt["applied_event_count"], 1)

        replay = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(replay.status_code, 200, replay.get_json())
        self.assertEqual(replay.get_json(), receipt)

        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)
            token = StudyAuthoritySubjectToken.query.one()
            self.assertEqual(int(token.authority_revision), 1)
            self.assertNotEqual(bytes(token.semantic_state_hash).hex(), base_hash)
            progress = CardProgress.query.one()
            self.assertEqual(int(progress.revision), 1)
            session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(session.status, "committed")

    def test_direct_rest_review_routes_through_note_authority(self):
        self._enable_existing_state_note_authority(epoch=8)
        with self.app.app_context():
            card_id = str(Card.query.join(Note, Card.note_id == Note.id).one().id)
        operation_key = str(uuid4())
        response = self.client.post(
            f"/api/study/{card_id}/answer",
            json={
                "rating": "good",
                "scope": "deck",
                "scope_id": self.deck_id,
                "operation_key": operation_key,
            },
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        authority = response.get_json()["authority"]
        self.assertEqual(authority["mode"], "NOTE")
        self.assertEqual(authority["operation_key"], operation_key)
        self.assertEqual(authority["authority_revision"], 1)
        self.assertEqual(authority["progress_revision"], 1)
        self.assertFalse(authority["replayed"])

        duplicate = self.client.post(
            f"/api/study/{card_id}/answer",
            json={
                "rating": "good",
                "scope": "deck",
                "scope_id": self.deck_id,
                "operation_key": operation_key,
            },
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.get_json())
        self.assertEqual(
            duplicate.get_json()["error"],
            "AUTHORITY_OPERATION_REUSED",
        )

        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)
            token = StudyAuthoritySubjectToken.query.one()
            self.assertEqual(int(token.authority_revision), 1)
            progress = CardProgress.query.one()
            self.assertEqual(int(progress.revision), 1)
            self.assertEqual(int(progress.reps), 1)

    def test_mcp_review_routes_through_note_authority(self):
        self._enable_existing_state_note_authority(epoch=9)
        with self.app.app_context():
            from app.services.mcp.study_tools import (
                get_card,
                get_deck_stats,
                get_study_queue,
                submit_review,
            )
            from app.services.mcp.deck_tools import get_deck_tree

            card_id = str(Card.query.join(Note, Card.note_id == Note.id).one().id)
            detail = get_card(user_id=self.user_id, card_id=card_id)
            self.assertEqual(detail["authority_mode"], "NOTE")
            self.assertEqual(detail["authority_revision"], 0)
            self.assertTrue(detail["review_state_version"].startswith("sha256-"))
            with patch(
                "app.services.mcp.study_tools.study_repository.query_study_queue_counts",
                side_effect=AssertionError("legacy counts must not serve NOTE"),
            ):
                queue = get_study_queue(
                    user_id=self.user_id,
                    deck_id=self.deck_id,
                    limit=10,
                )
            self.assertEqual(queue["queue_counts"]["authority_mode"], "NOTE")
            self.assertEqual(len(queue["cards"]), 1)
            self.assertEqual(queue["cards"][0]["authority_mode"], "NOTE")
            self.assertEqual(queue["cards"][0]["authority_revision"], 0)
            deck_stats = get_deck_stats(
                user_id=self.user_id,
                deck_id=self.deck_id,
            )
            self.assertEqual(deck_stats["authority_mode"], "NOTE")
            self.assertEqual(deck_stats["young_cards"], 0)
            self.assertEqual(deck_stats["mature_cards"], 0)
            deck_tree = get_deck_tree(user_id=self.user_id)
            self.assertEqual(deck_tree[0]["counts"]["new"], 1)
            self.assertEqual(deck_tree[0]["counts"]["due"], 0)
            response = submit_review(
                user_id=self.user_id,
                card_id=card_id,
                rating="good",
                duration_ms=250,
            )
            self.assertTrue(response["success"])
            self.assertEqual(response["authority"]["mode"], "NOTE")
            self.assertEqual(response["authority"]["authority_revision"], 1)
            self.assertEqual(response["authority"]["progress_revision"], 1)
            self.assertIsNotNone(response["authority"]["operation_key"])
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)

    def test_direct_manifest_and_intervals_read_canonical_note_token(self):
        self._enable_existing_state_note_authority(epoch=10)
        manifest_response = self.client.get(
            "/api/study/session/next",
            query_string={"scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(
            manifest_response.status_code,
            200,
            manifest_response.get_json(),
        )
        manifest = manifest_response.get_json()
        self.assertEqual(manifest["authority_mode"], "NOTE")
        self.assertEqual(manifest["authority_revision"], 0)
        state_version = manifest["review_state_version"]

        intervals = self.client.get(
            f"/api/study/cards/{manifest['card_id']}/intervals-preview",
            query_string={
                "selection_id": manifest["selection_id"],
                "review_state_version": state_version,
            },
        )
        self.assertEqual(intervals.status_code, 200, intervals.get_json())
        self.assertEqual(intervals.get_json()["authority_mode"], "NOTE")
        self.assertEqual(intervals.get_json()["authority_revision"], 0)
        self.assertEqual(intervals.get_json()["review_state_version"], state_version)

        answer = self.client.post(
            f"/api/study/cards/{manifest['card_id']}/answer",
            json={
                "rating": "good",
                "scope": "deck",
                "scope_id": self.deck_id,
                "render_contract": "client_v1",
                "review_state_version": state_version,
                "operation_key": str(uuid4()),
            },
        )
        self.assertEqual(answer.status_code, 200, answer.get_json())
        self.assertEqual(answer.get_json()["authority"]["authority_revision"], 1)

        stale = self.client.get(
            f"/api/study/cards/{manifest['card_id']}/intervals-preview",
            query_string={"review_state_version": state_version},
        )
        self.assertEqual(stale.status_code, 409, stale.get_json())
        self.assertEqual(stale.get_json()["error"], "STALE_REVIEW_STATE")

    def test_direct_note_queue_bypasses_legacy_sql_selection(self):
        self._enable_existing_state_note_authority(epoch=12)
        with (
            patch(
                "app.routes.flashcards.study._query_study_queue_counts",
                side_effect=AssertionError("legacy counts must not serve NOTE"),
            ),
            patch(
                "app.routes.flashcards.study._query_next_due_card_id",
                side_effect=AssertionError("legacy order must not serve NOTE"),
            ),
        ):
            response = self.client.get(
                "/api/study/session/next",
                query_string={"scope": "deck", "scope_id": self.deck_id},
            )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["authority_mode"], "NOTE")
        self.assertEqual(payload["new_count"], 1)
        self.assertEqual(payload["learn_count"], 0)
        self.assertEqual(payload["due_count"], 0)

    def test_dashboard_note_counts_are_rebuilt_from_canonical_availability(self):
        self._enable_existing_state_note_authority(epoch=14)
        with patch(
            "app.services.dashboard_service._classify_progress_fast",
            return_value=None,
        ):
            response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["summary"]["new"], 1)
        self.assertEqual(payload["summary"]["learning"], 0)
        self.assertEqual(payload["summary"]["due"], 0)
        self.assertEqual(payload["summary"]["total_due"], 1)

    def test_statistics_note_future_due_bypasses_legacy_progress_query(self):
        self._enable_existing_state_note_authority(epoch=15)
        with patch(
            "app.services.stats_overview.query_future_due_day_counts",
            side_effect=AssertionError("legacy future due must not serve NOTE"),
        ):
            response = self.client.get(
                "/api/statistics/overview",
                query_string={"year": 2026, "timezone": "Asia/Tokyo"},
            )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["year"], 2026)
        self.assertEqual(payload["timezone"], "Asia/Tokyo")
        self.assertEqual(len(payload["heatmap"]), 365)

    def test_today_future_note_analytics_bypass_legacy_progress_queries(self):
        self._enable_existing_state_note_authority(epoch=16)
        with (
            patch(
                "app.services.stats_today_future.query_due_progress_rows",
                side_effect=AssertionError("legacy due rows must not serve NOTE"),
            ),
            patch(
                "app.services.stats_today_future.query_interval_days_rows",
                side_effect=AssertionError("legacy daily load must not serve NOTE"),
            ),
        ):
            response = self.client.get(
                "/api/statistics/today-future",
                query_string={
                    "scope": "collection",
                    "future_range": "30",
                    "timezone": "Asia/Tokyo",
                },
            )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["timezone"], "Asia/Tokyo")
        self.assertEqual(payload["totals"]["total_reviews"], 0)
        self.assertEqual(payload["totals"]["daily_load"], 0.0)

    def test_browse_note_rows_and_detail_bypass_legacy_progress_reads(self):
        self._enable_existing_state_note_authority(epoch=17)
        with self.app.app_context():
            card_id = str(Card.query.join(Note, Card.note_id == Note.id).one().id)
        with (
            patch(
                "app.services.browse_card_service.load_card_progress_map",
                side_effect=AssertionError("legacy Browse rows must not serve NOTE"),
            ),
            patch(
                "app.repositories.browse_card_repository.load_browse_progress",
                side_effect=AssertionError("legacy Browse detail must not serve NOTE"),
            ),
        ):
            rows_response = self.client.get(
                "/api/browse/cards",
                query_string={"deck_id": self.deck_id, "sort_by": "due"},
            )
            detail_response = self.client.get(f"/api/browse/cards/{card_id}")
        self.assertEqual(rows_response.status_code, 200, rows_response.get_json())
        rows = rows_response.get_json()
        self.assertEqual(rows["total"], 1)
        self.assertEqual(rows["items"][0]["card_id"], card_id)
        self.assertEqual(rows["items"][0]["queue"], "new")
        self.assertEqual(detail_response.status_code, 200, detail_response.get_json())
        self.assertEqual(detail_response.get_json()["card"]["queue"], "new")

    def test_browse_note_deck_tree_rebuilds_canonical_counts(self):
        self._enable_existing_state_note_authority(epoch=18)
        legacy_tree = [
            {
                "id": self.deck_id,
                "name": "Session Deck",
                "path": "Session Deck",
                "parent_id": None,
                "note_type_id": self.note_type_id,
                "note_type_name": "Session Type",
                "note_type_ids": [self.note_type_id],
                "note_type_names": ["Session Type"],
                "has_mixed_note_types": False,
                "counts": {"total": 999, "new": 0, "learn": 0, "due": 999},
                "children": [],
            }
        ]
        with patch(
            "app.services.browse_card_service.vocabulary_ctrl.build_browse_deck_tree_payload",
            return_value=legacy_tree,
        ):
            response = self.client.get("/api/browse/decks/tree")
        self.assertEqual(response.status_code, 200, response.get_json())
        counts = response.get_json()["tree"][0]["counts"]
        self.assertEqual(
            counts,
            {"total": 1, "new": 1, "learn": 0, "due": 0},
        )

    def test_legacy_study_deck_page_uses_note_authority_queue(self):
        self._enable_existing_state_note_authority(epoch=19)
        with patch(
            "app.routes.vocabulary._load_card_progress_map",
            side_effect=AssertionError("legacy Study page must not serve NOTE"),
        ):
            response = self.client.get(f"/vocabulary/study/deck/{self.deck_id}")
        self.assertEqual(response.status_code, 200)

    def test_direct_note_read_fails_closed_on_stale_canonical_availability(self):
        self._enable_existing_state_note_authority(epoch=13)
        with self.app.app_context():
            availability = StudyProgressAvailability.query.one()
            availability.is_suspended = True
            db.session.commit()

        response = self.client.get(
            "/api/study/session/next",
            query_string={"scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(
            response.get_json()["error"],
            "AUTHORITY_READ_PARITY_DIVERGED",
        )

    def test_direct_note_read_fails_closed_on_projection_divergence(self):
        self._enable_existing_state_note_authority(epoch=11)
        with self.app.app_context():
            progress = CardProgress.query.one()
            progress.reps = 99
            db.session.commit()

        response = self.client.get(
            "/api/study/session/next",
            query_string={"scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(
            response.get_json()["error"],
            "AUTHORITY_READ_PARITY_DIVERGED",
        )

    def test_wire_v4_commit_chains_multiple_events_from_one_frozen_pin(self):
        self._enable_existing_state_note_authority(epoch=6)
        snapshot = self._open_session_v4()
        payload = self._commit_payload(snapshot, commit_id=str(uuid4()))
        second = json.loads(json.dumps(payload["events"][0]))
        second_id = str(uuid4())
        second.update(
            {
                "event_id": second_id,
                "operation_key": second_id,
                "sequence": 2,
                "scheduler_offset_ms": 2000,
            }
        )
        payload["events"].append(second)

        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["applied_event_count"], 2)
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 2)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 2)
            self.assertEqual(
                int(StudyAuthoritySubjectToken.query.one().authority_revision),
                2,
            )
            self.assertEqual(int(CardProgress.query.one().revision), 2)

    def test_wire_v4_commit_rejects_stale_pin_without_partial_writes(self):
        self._enable_existing_state_note_authority(epoch=7)
        snapshot = self._open_session_v4()
        with self.app.app_context():
            token = StudyAuthoritySubjectToken.query.one()
            token.authority_revision = int(token.authority_revision) + 1
            db.session.commit()

        status = self.client.get(
            f"/api/study/sessions/{snapshot['session_id']}"
        )
        self.assertEqual(status.status_code, 200, status.get_json())
        self.assertTrue(status.get_json()["stale"])

        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=self._commit_payload(snapshot, commit_id=str(uuid4())),
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "AUTHORITY_STATE_CONFLICT")
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 0)
            self.assertEqual(int(CardProgress.query.one().revision), 0)
            self.assertEqual(
                db.session.get(StudySession, snapshot["session_id"]).status,
                "open",
            )

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

        legacy_operation = self.client.post(
            f"/api/study/{card_id}/answer",
            json={**base_payload, "operation_key": str(uuid4())},
        )
        self.assertEqual(
            legacy_operation.status_code,
            422,
            legacy_operation.get_json(),
        )
        self.assertEqual(
            legacy_operation.get_json()["error"],
            "AUTHORITY_OPERATION_KEY_UNAVAILABLE",
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

    def test_empty_owned_deck_does_not_open_session(self):
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
        self.assertEqual(response.status_code, 404, response.get_json())
        self.assertEqual(response.get_json()["error"], "NO_STUDY_CARDS")
        with self.app.app_context():
            self.assertEqual(
                StudySession.query.filter_by(scope_id=str(empty_deck_id)).count(),
                0,
            )

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
        self.assertEqual(data["schema_version"], "study-scope-compositions.v2")
        self.assertEqual(data["scope_type"], "deck")
        self.assertEqual(data["scope_id"], str(self.deck_id))
        self.assertGreaterEqual(len(data["compositions"]), 1)
        self.assertEqual(data["cardinality"], "one")
        self.assertEqual(data["default_composition_id"], data["compositions"][0]["composition_id"])
        self.assertEqual(len(data["groups"]), 1)
        self.assertEqual(data["groups"][0]["note_type_id"], self.note_type_id)
        comp = data["compositions"][0]
        self.assertEqual(comp["mode_key"], "flashcard")
        self.assertEqual(comp["algorithm_key"], "legacy-anki")

    def test_scope_compositions_groups_recursive_mixed_note_types(self):
        with self.app.app_context():
            second_type = NoteType(name="Another Type", user_id=self.user_id)
            child = Deck(
                name="Mixed child",
                owner_user_id=self.user_id,
                parent_id=self.deck_id,
            )
            db.session.add_all([second_type, child])
            db.session.flush()
            template = Template(
                note_type_id=second_type.id,
                name="Another Card",
                front_html="front",
                back_html="back",
                position=0,
                is_default=True,
            )
            db.session.add(template)
            db.session.flush()
            note = Note(
                user_id=self.user_id,
                deck_id=child.id,
                note_type_id=second_type.id,
                field_values={},
            )
            db.session.add(note)
            db.session.flush()
            db.session.add(Card(note_id=note.id, template_id=template.id))
            db.session.commit()
            second_type_id = str(second_type.id)

        response = self.client.get(
            f"/api/study/scopes/deck/{self.deck_id}/compositions"
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["cardinality"], "many")
        self.assertIsNone(payload["default_composition_id"])
        self.assertEqual(
            {group["note_type_id"] for group in payload["groups"]},
            {self.note_type_id, second_type_id},
        )
        self.assertEqual(
            sum(len(group["compositions"]) for group in payload["groups"]),
            len(payload["compositions"]),
        )

    def _add_second_composition(self):
        with self.app.app_context():
            note = Note.query.filter_by(
                user_id=self.user_id,
                deck_id=self.deck_id,
            ).one()
            template = Template(
                note_type_id=self.note_type_id,
                name="Card 2",
                front_html="Reverse {{Word}}",
                back_html="{{Word}}",
                position=1,
                is_default=False,
            )
            db.session.add(template)
            db.session.flush()
            card = Card(note_id=note.id, template_id=template.id)
            db.session.add(card)
            db.session.commit()
            return str(template.id), str(card.id)

    def test_multiple_compositions_require_explicit_selection(self):
        self._add_second_composition()
        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(
            response.get_json()["error"],
            "COMPOSITION_SELECTION_REQUIRED",
        )
        self.assertEqual(
            response.get_json()["details"]["eligible_composition_count"],
            2,
        )
        with self.app.app_context():
            self.assertEqual(StudySession.query.count(), 0)

    def test_explicit_composition_opens_only_selected_cards(self):
        template_id, card_id = self._add_second_composition()
        composition_id = (
            f"comp:notetype:{self.note_type_id}:template:{template_id}"
        )
        response = self.client.post(
            "/api/study/sessions",
            json={
                "scope": "deck",
                "scope_id": self.deck_id,
                "composition_id": composition_id,
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        snapshot = response.get_json()
        self.assertEqual(snapshot["selected_composition_id"], composition_id)
        self.assertEqual(
            [item["card_id"] for item in snapshot["cards"]],
            [card_id],
        )

    def test_legacy_multiple_composition_ids_fail_closed(self):
        template_id, _card_id = self._add_second_composition()
        response = self.client.post(
            "/api/study/sessions",
            json={
                "scope": "deck",
                "scope_id": self.deck_id,
                "composition_ids": [
                    "comp:notetype:unused:template:unused",
                    f"comp:notetype:{self.note_type_id}:template:{template_id}",
                ],
            },
        )
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(
            response.get_json()["error"],
            "COMPOSITION_CARDINALITY_INVALID",
        )

    def test_out_of_scope_composition_is_rejected(self):
        with self.app.app_context():
            other_type = NoteType(name="Other Type", user_id=self.user_id)
            other_deck = Deck(name="Other Deck", owner_user_id=self.user_id)
            db.session.add_all([other_type, other_deck])
            db.session.flush()
            other_template = Template(
                note_type_id=other_type.id,
                name="Other Card",
                front_html="front",
                back_html="back",
                is_default=True,
            )
            db.session.add(other_template)
            db.session.flush()
            other_note = Note(
                user_id=self.user_id,
                deck_id=other_deck.id,
                note_type_id=other_type.id,
                field_values={},
            )
            db.session.add(other_note)
            db.session.flush()
            db.session.add(
                Card(note_id=other_note.id, template_id=other_template.id)
            )
            db.session.commit()
            composition_id = (
                f"comp:notetype:{other_type.id}:template:{other_template.id}"
            )
        response = self.client.post(
            "/api/study/sessions",
            json={
                "scope": "deck",
                "scope_id": self.deck_id,
                "composition_id": composition_id,
            },
        )
        self.assertEqual(response.status_code, 403, response.get_json())
        self.assertEqual(response.get_json()["error"], "COMPOSITION_OUT_OF_SCOPE")

    def test_composition_filter_is_applied_before_session_limit(self):
        template_id, card_id = self._add_second_composition()
        composition_id = (
            f"comp:notetype:{self.note_type_id}:template:{template_id}"
        )
        with patch("app.services.study_session_service.MAX_SESSION_CARDS", 1):
            response = self.client.post(
                "/api/study/sessions",
                json={
                    "scope": "deck",
                    "scope_id": self.deck_id,
                    "composition_id": composition_id,
                },
            )
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["cards"][0]["card_id"], card_id)

    def test_commit_rejects_composition_different_from_frozen_selection(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        payload["composition_id"] = "comp:notetype:other:template:other"
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=payload,
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(
            response.get_json()["error"],
            "COMPOSITION_SNAPSHOT_MISMATCH",
        )

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
