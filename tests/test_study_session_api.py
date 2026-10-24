"""Integration coverage for frontend-driven study sessions."""

import json
import unittest
from datetime import datetime, timedelta
from hashlib import sha256
from contextlib import contextmanager
from sqlalchemy import event as sql_event
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.repositories import template_library_repository
from tests.study_note_fixtures import attach_template, enroll_note_user, assert_retired_progress_absent, archive_wire_alias
from tests.note_progress_fixtures import stage_note_state
from app.repositories.study_authority_repository import StudyAuthorityFenceError
from app.services.anki_scheduler import _day_index, applyAnswer
from app.services.study_progress_contract import MAPPER_VERSION
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
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_authority_read_service import (
    StudyAuthorityReadError,
    load_study_authority_card_read,
)
from app.services.study_session_config import (
    StudySessionConfigError,
    decode_study_session_config,
)
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card, CardWireIdentity
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
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.study_application import StudyApplication
from models.study_session_commit import StudySessionCommit
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
                "STUDY_WIRE_V4_ENABLED": True,
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
            enroll_note_user(db.session, user)
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
            json={"scope": "deck", "scope_id": self.deck_id,
                  "accepted_session_schema_versions": ["study-session.v4"],
                  "accepted_note_storage_profiles": ["note-mysql-float-text.v1"]},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()


    def _enable_existing_state_note_authority(
        self, *, epoch=1, enroll=True, initial_progress=None, note_id=None, include_token=None
    ):
        """Stage exact canonical NOTE state; enrollment was explicit at signup."""
        with self.app.app_context():
            query = Note.query.filter_by(user_id=self.user_id, deck_id=self.deck_id)
            note = query.filter_by(id=note_id).one() if note_id else query.one()
            subject = stage_note_state(db.session, user_id=self.user_id,
                note_id=str(note.id), now=datetime(2026, 9, 21, 8), **(initial_progress or {}))
            subject.mapper_version = MAPPER_VERSION
            subject.mirror_revision = max(1, int(subject.mirror_revision or 0))
            subject.history_completeness_code = "HISTORY_NATIVE_COMPLETE"
            if enroll:
                db.session.get(StudyAuthorityEnrollment, self.user_id).epoch = epoch
            db.session.commit()
            return str(note.id), subject.semantic_state_hash.hex()


    @staticmethod
    def _live_rows():
        return StudyProgressSubject.query.filter(StudyProgressSubject.state_payload.isnot(None))

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

    @contextmanager
    def _record_study_sql(self):
        """Observe real queries after retirement, without patching canonical APIs."""
        with self.app.app_context():
            statements = []
            def record(conn, cursor, statement, parameters, context, executemany):
                statements.append(statement.lower())
            sql_event.listen(db.engine, "before_cursor_execute", record)
            try:
                yield statements
            finally:
                sql_event.remove(db.engine, "before_cursor_execute", record)
        self.assertFalse(any("card_progress" in statement for statement in statements), statements)

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
            assert_retired_progress_absent(self, db.session)
            subject = StudyProgressSubject.query.one()
            lifecycle = StudyProgressLifecycleEvent.query.one()
            session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
            self.assertEqual(int(subject.subject_generation), 2)
            self.assertEqual(int(subject.mirror_revision), 3)
            self.assertEqual(int(subject.authority_revision), 2)
            self.assertEqual(subject.normalized_queue, "new")
            self.assertIsNotNone(subject.semantic_state_hash)
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
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(StudyProgressSubject.query.count(), 2)
            self.assertEqual(self._live_rows().count(), 2)
            new_subject = StudyProgressSubject.query.filter_by(
                live_note_id=created.get_json()["id"]
            ).one()
            self.assertEqual(int(new_subject.subject_generation), 1)
            self.assertEqual(int(new_subject.mirror_revision), 2)
            self.assertEqual(int(new_subject.authority_revision), 1)
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
            self.assertEqual(new_subject.current_provenance_code, "NATIVE_MCP")
            self.assertEqual(
                new_subject.history_completeness_code,
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
            self.assertIsNone(db.session.get(Note, new_note_id))
            self.assertEqual(
                tombstone.status_code, "TOMBSTONED_SUBJECT_DELETED"
            )
            self.assertEqual(int(tombstone.subject_generation), 2)
            self.assertEqual(int(tombstone.authority_revision), 1)
            self.assertIsNone(tombstone.semantic_state_hash)

    def test_note_authority_mcp_template_bulk_expands_and_note_batch_deletes(self):
        self._enable_existing_state_note_authority(epoch=10)
        with self.app.app_context():
            from app.services.mcp.note_tools import batch_delete_notes, create_note
            from app.services.mcp.note_type_tools import update_note_type

            update_note_type(
                user_id=self.user_id,
                note_type_id=self.note_type_id,
                templates={"added": [{"name": "Additional Card"}]},
            )
            self.assertEqual(Template.query.count(), 2)
            self.assertEqual(Card.query.count(), 2)
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
            self.assertEqual(deleted["deleted_cards_count"], 4)
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(Card.query.count(), 0)
            assert_retired_progress_absent(self, db.session)
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
            # The new Card shares its Note's row; nothing is copied (ADR P10).
            assert_retired_progress_absent(self, db.session)
            subject = StudyProgressSubject.query.one()
            old_session = db.session.get(
                StudySession, old_snapshot["session_id"]
            )
            self.assertEqual(int(subject.subject_generation), 1)
            self.assertEqual(int(subject.mirror_revision), 2)
            self.assertEqual(int(subject.authority_revision), 1)
            self.assertEqual(subject.current_provenance_code, "NATIVE_DIRECT")
            self.assertEqual(subject.history_completeness_code, "HISTORY_NATIVE_COMPLETE")
            # Its pins stay valid: the open session keeps its own Cards.
            self.assertEqual(old_session.status, "open")

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
            fresh["cards"][0]["authority_pin"]["subject_generation"], "1"
        )
        self.assertEqual(
            fresh["cards"][0]["authority_pin"]["base_authority_revision"], "1"
        )
        committed = self.client.post(
            f"/api/study/sessions/{fresh['session_id']}/commit",
            json=self._commit_payload(fresh),
        )
        self.assertEqual(committed.status_code, 200, committed.get_json())

    def test_template_attachment_retirement_preserves_state_and_old_lease(self):
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
            self.assertIsNotNone(db.session.get(Template, template_id))
            retired = StudyApplication.query.filter_by(note_type_id=self.note_type_id, template_id=template_id).one()
            self.assertEqual(retired.status_code, "RETIRED")
            self.assertIsNone(db.session.get(Card, removed_card_id))
            self.assertEqual(Template.query.count(), 2)
            self.assertEqual(Card.query.count(), 1)
            assert_retired_progress_absent(self, db.session)
            subject = StudyProgressSubject.query.one()
            old_session = db.session.get(StudySession, snapshot["session_id"])
            # Losing a Template's Card changes neither the Note's state nor its row.
            self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
            self.assertEqual(int(subject.subject_generation), 1)
            self.assertEqual(int(subject.mirror_revision), 1)
            self.assertEqual(int(subject.authority_revision), 0)
            self.assertIsNotNone(subject.semantic_state_hash)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)
            self.assertEqual(old_session.status, "open")
            self.assertEqual(StudySessionCard.query.filter_by(session_id=snapshot["session_id"]).one().card_id, removed_card_id)
            self.assertEqual(StudySessionAuthorityPin.query.filter_by(session_card_id=StudySessionCard.query.filter_by(session_id=snapshot["session_id"]).one().id).count(), 1)
            remaining_card_id = str(Card.query.one().id)

        # The frozen lease still resolves its retired application explicitly.
        commit = self.client.post(f"/api/study/sessions/{snapshot['session_id']}/commit",
            json=self._commit_payload(snapshot))
        self.assertEqual(commit.status_code, 200, commit.get_json())
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.one().card_id, removed_card_id)
            self.assertIsNotNone(db.session.get(Template, template_id))
            self.assertEqual(StudyProgressSubject.query.one().authority_revision, 1)
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
        self.assertEqual(reviewed.get_json()["authority"]["authority_revision"], 2)

    def test_note_authority_new_template_expands_every_owned_note(self):
        self._enable_existing_state_note_authority(epoch=15, include_token=True)
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
            assert_retired_progress_absent(self, db.session)
            subjects = StudyProgressSubject.query.order_by(
                StudyProgressSubject.logical_note_key.asc()
            ).all()
            self.assertEqual(len(subjects), 2)
            # A new Template neither copies nor re-keys a Note's row (ADR P10).
            self.assertTrue(
                all(int(subject.subject_generation) == 1 for subject in subjects)
            )
            self.assertTrue(
                all(int(subject.mirror_revision) == 1 for subject in subjects)
            )
            self.assertTrue(
                all(int(subject.authority_revision) == 0 for subject in subjects)
            )
            self.assertEqual(self._live_rows().count(), 2)

    def test_note_authority_owned_note_delete_tombstones_subject(self):
        note_id, _state_hash = self._enable_existing_state_note_authority(epoch=16)
        snapshot = self._open_session_v4()

        deleted = self.client.delete(f"/api/notes/{note_id}")
        self.assertEqual(deleted.status_code, 200, deleted.get_json())
        self.assertTrue(deleted.get_json()["success"])

        with self.app.app_context():
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(Card.query.count(), 0)
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(self._live_rows().count(), 0)
            subject = StudyProgressSubject.query.one()
            lifecycle = StudyProgressLifecycleEvent.query.one()
            study_session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
            self.assertIsNone(subject.live_note_id)
            self.assertEqual(int(subject.subject_generation), 2)
            self.assertEqual(int(subject.mirror_revision), 2)
            self.assertEqual(int(subject.authority_revision), 1)
            self.assertIsNone(subject.semantic_state_hash)
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
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(self._live_rows().count(), 0)
            subject = StudyProgressSubject.query.one()
            lifecycle = StudyProgressLifecycleEvent.query.one()
            study_session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
            self.assertIsNone(subject.live_note_id)
            self.assertEqual(int(subject.subject_generation), 2)
            self.assertEqual(int(subject.mirror_revision), 2)
            self.assertEqual(int(subject.authority_revision), 1)
            self.assertIsNone(subject.semantic_state_hash)
            self.assertEqual(
                lifecycle.transition_code,
                "TOMBSTONED_SUBJECT_DELETED",
            )
            self.assertEqual(lifecycle.source_path, "deck.delete")
            self.assertEqual(study_session.status, "cancelled")

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

    def test_retiring_last_application_keeps_hidden_state_auditable(self):
        self._enable_existing_state_note_authority(initial_progress={"queue": "review",
            "due_day": 739000, "interval_days": 5, "reps": 3})
        with self.app.app_context():
            application = StudyApplication.query.filter_by(note_type_id=self.note_type_id).one()
            application.status_code = "RETIRED"
            db.session.commit()
            original = StudyProgressSubject.query.one().semantic_state_hash
            self.assertEqual(Card.query.count(), 0)
        runner = self.app.test_cli_runner()
        audit = runner.invoke(args=["study-authority-read-audit", "--user-id", str(self.user_id)])
        self.assertEqual(audit.exit_code, 0, audit.output)
        result = json.loads(audit.output)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["card_count"], 0)
        self.assertEqual(result["canonical"]["due"], 0)
        with self.app.app_context():
            self.assertEqual(StudyProgressSubject.query.one().semantic_state_hash, original)
            StudyProgressSubject.query.one().normalized_queue = "new"
            db.session.commit()
        corrupt = runner.invoke(args=["study-authority-read-audit", "--user-id", str(self.user_id)])
        self.assertNotEqual(corrupt.exit_code, 0)
        self.assertIn("AUTHORITY_READ_PARITY_DIVERGED", corrupt.output)
        with self.app.app_context():
            subject = StudyProgressSubject.query.one()
            subject.normalized_queue = "review"
            # Actual current payload must be audited even if a stale status
            # label no longer says MIRRORED after presentation retirement.
            subject.status_code = "NO_CURRENT_PROGRESS"
            subject.state_payload = {**subject.state_payload, "reps": "99"}
            db.session.commit()
        corrupt_hash = runner.invoke(args=["study-authority-read-audit", "--user-id", str(self.user_id)])
        self.assertNotEqual(corrupt_hash.exit_code, 0)
        self.assertIn("STATE_HASH_MISMATCH", corrupt_hash.output)

    def test_old_uuid_session_snapshot_pin_commit_and_replay_keep_exact_wire_id(self):
        old_uuid = str(uuid4())
        with self.app.app_context():
            card = Card.query.one()
            canonical_id = str(card.id)
            archive_wire_alias(db.session, card, old_uuid)
            db.session.commit()
        from app.services.study_composition_service import apply_composition_selection_to_query

        class HistoricalDiscovery:
            """Emulate the IDs issued pre-P11 while using the real issuer and query."""
            def __init__(self, query):
                self.query = query
            def options(self, *values):
                self.query = self.query.options(*values)
                return self
            def order_by(self, *values):
                self.query = self.query.order_by(*values)
                return self
            def limit(self, value):
                self.query = self.query.limit(value)
                return self
            def all(self):
                return [CardWireIdentity(card, old_uuid) if str(card.id) == canonical_id else card
                    for card in self.query.all()]

        def historical_discovery(*args, **kwargs):
            return HistoricalDiscovery(apply_composition_selection_to_query(*args, **kwargs))

        with patch("app.services.study_session_service.apply_composition_selection_to_query",
                   side_effect=historical_discovery):
            snapshot = self._open_session()
        self.assertEqual(snapshot["cards"][0]["card_id"], old_uuid)
        url = f"/api/study/sessions/{snapshot['session_id']}"
        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            membership = StudySessionCard.query.one()
            pin = StudySessionAuthorityPin.query.one()
            self.assertEqual(membership.card_id, old_uuid)
            before = (session.snapshot_hash, session.config_snapshot_json, membership.initial_state_json,
                tuple(getattr(pin, column.name) for column in pin.__table__.columns))
        status = self.client.get(url)
        self.assertEqual(status.status_code, 200, status.get_json())
        self.assertFalse(status.get_json()["stale"])
        payload = self._commit_payload(snapshot)
        changed = json.loads(json.dumps(payload))
        changed["events"][0]["card_id"] = canonical_id
        refused = self.client.post(url + "/commit", json=changed)
        self.assertEqual(refused.status_code, 422, refused.get_json())
        self.assertEqual(refused.get_json()["error"], "CARD_OUTSIDE_SESSION")
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(StudyProgressSubject.query.one().authority_revision, 0)
        committed = self.client.post(url + "/commit", json=payload)
        self.assertEqual(committed.status_code, 200, committed.get_json())
        receipt = committed.get_json()
        with self.app.app_context():
            event = ReviewEvent.query.one()
            authority_receipt = StudyAuthorityCommandReceipt.query.one()
            self.assertEqual(event.card_id, old_uuid)
            event_before = (event.payload_json, bytes(authority_receipt.request_fingerprint),
                authority_receipt.response_payload)
        with patch("app.services.study_session_service.study_service.execute_native_review_transition",
                   side_effect=AssertionError("old UUID session replay executed twice")):
            replay = self.client.post(url + "/commit", json=payload)
        self.assertEqual(replay.status_code, 200, replay.get_json())
        self.assertEqual(replay.get_json(), receipt)
        changed_retry = self.client.post(url + "/commit", json=changed)
        self.assertEqual(changed_retry.status_code, 409, changed_retry.get_json())
        self.assertEqual(changed_retry.get_json()["details"], receipt)
        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            membership = StudySessionCard.query.one()
            pin = StudySessionAuthorityPin.query.one()
            self.assertEqual(membership.card_id, old_uuid)
            self.assertEqual((session.snapshot_hash, session.config_snapshot_json, membership.initial_state_json,
                tuple(getattr(pin, column.name) for column in pin.__table__.columns)), before)
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)
            event = ReviewEvent.query.one()
            authority_receipt = StudyAuthorityCommandReceipt.query.one()
            self.assertEqual(event.card_id, old_uuid)
            self.assertEqual((event.payload_json, bytes(authority_receipt.request_fingerprint),
                authority_receipt.response_payload), event_before)
            self.assertEqual(StudyProgressSubject.query.one().authority_revision, 1)

    def test_open_returns_self_contained_snapshot(self):
        snapshot = self._open_session()
        self.assertEqual(snapshot["schema_version"], "study-session.v4")
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

    def test_note_session_requires_v4_capability_and_enabled_flag(self):
        for versions in ([], ["study-session.v2"], ["study-session.v3", "study-session.v2"]):
            with self.subTest(versions=versions):
                response = self.client.post("/api/study/sessions", json={"scope": "deck",
                    "scope_id": self.deck_id, "accepted_session_schema_versions": versions})
                expected_status, expected_code = (422, "UNSUPPORTED_SESSION_SCHEMA") if not versions else (409, "WIRE_CONTRACT_MISMATCH")
                self.assertEqual(response.status_code, expected_status, response.get_json())
                self.assertEqual(response.get_json()["error"], expected_code)
        previous = self.app.config["STUDY_WIRE_V4_ENABLED"]
        self.app.config["STUDY_WIRE_V4_ENABLED"] = False
        try:
            response = self.client.post("/api/study/sessions", json={"scope": "deck",
                "scope_id": self.deck_id, "accepted_session_schema_versions": ["study-session.v4"]})
        finally:
            self.app.config["STUDY_WIRE_V4_ENABLED"] = previous
        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(response.get_json()["error"], "UNSUPPORTED_SESSION_SCHEMA")
        with self.app.app_context():
            self.assertEqual(StudySession.query.count(), 0)
        self.assertEqual(self._open_session()["schema_version"], "study-session.v4")


    def test_legacy_enrollment_cannot_issue_any_new_session(self):
        with self.app.app_context():
            enrollment = db.session.get(StudyAuthorityEnrollment, self.user_id)
            enrollment.mode_code = "LEGACY"
            db.session.commit()
        response = self.client.post("/api/study/sessions", json={"scope": "deck",
            "scope_id": self.deck_id, "accepted_session_schema_versions": ["study-session.v4", "study-session.v3"]})
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "STUDY_AUTHORITY_MIGRATION_REQUIRED")
        with self.app.app_context():
            self.assertEqual(StudySession.query.count(), 0)
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

    def test_note_enrollment_retry_preserves_existing_note_lease(self):
        self._enable_existing_state_note_authority(epoch=5)
        snapshot = self._open_session()
        with self.app.app_context():
            before = StudyProgressSubject.query.one().semantic_state_hash
            result = stage_note_authority_enrollment(db.session, learner_user_id=self.user_id,
                now_utc=datetime(2026, 9, 21, 9))
            db.session.commit()
            self.assertEqual(result.mode_code, "NOTE")
            self.assertEqual(result.epoch, 5)
            self.assertEqual(result.cancelled_session_count, 0)
            self.assertEqual(StudyProgressSubject.query.one().semantic_state_hash, before)
            self.assertEqual(db.session.get(StudySession, snapshot["session_id"]).status, "open")


    def test_new_note_is_materialized_by_explicit_note_writer(self):
        with self.app.app_context():
            subject = StudyProgressSubject.query.one()
            self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
            self.assertEqual(int(subject.subject_generation), 1)
            self.assertEqual(int(subject.mirror_revision), 1)
            self.assertEqual(int(subject.authority_revision), 0)
            self.assertIsNotNone(subject.semantic_state_hash)
            self.assertEqual(subject.history_completeness_code, "HISTORY_NATIVE_COMPLETE")
            assert_retired_progress_absent(self, db.session)
        snapshot = self._open_session()
        self.assertEqual(snapshot["cards"][0]["state"]["type"], "new")
        self.assertEqual(snapshot["cards"][0]["authority_pin"]["base_authority_revision"], "0")


    def test_enrollment_retry_does_not_rematerialize_existing_subject(self):
        with self.app.app_context():
            subject = StudyProgressSubject.query.one()
            subject_id, state_hash = subject.id, subject.semantic_state_hash
            revision = int(subject.mirror_revision)
            result = stage_note_authority_enrollment(db.session, learner_user_id=self.user_id,
                now_utc=datetime(2026, 9, 21, 9))
            db.session.commit()
            self.assertEqual(result.subject_count, 0)
            self.assertEqual(StudyProgressSubject.query.count(), 1)
            current = StudyProgressSubject.query.one()
            self.assertEqual(current.id, subject_id)
            self.assertEqual(current.semantic_state_hash, state_hash)
            self.assertEqual(int(current.mirror_revision), revision)


    def test_existing_legacy_account_requires_offline_migration_without_state_writes(self):
        with self.app.app_context():
            enrollment = db.session.get(StudyAuthorityEnrollment, self.user_id)
            enrollment.mode_code = "LEGACY"
            original = StudyProgressSubject.query.one().semantic_state_hash
            db.session.commit()
            with self.assertRaises(StudyAuthorityEnrollmentError) as failure:
                stage_note_authority_enrollment(db.session, learner_user_id=self.user_id,
                    now_utc=datetime(2026, 9, 21, 9))
            self.assertEqual(failure.exception.code, "STUDY_AUTHORITY_MIGRATION_REQUIRED")
            db.session.rollback()
            self.assertEqual(db.session.get(StudyAuthorityEnrollment, self.user_id).mode_code, "LEGACY")
            self.assertEqual(StudyProgressSubject.query.one().semantic_state_hash, original)
            assert_retired_progress_absent(self, db.session)


    def test_new_note_materialization_failure_rolls_back_note_and_subject(self):
        with self.app.app_context():
            before = (Note.query.count(), Card.query.count(), StudyProgressSubject.query.count())
            state_hash = StudyProgressSubject.query.one().semantic_state_hash
        with patch("app.services.flashcard_content_service.study_progress_lifecycle_mirror_service.materialize_new_note_authority",
                   side_effect=StudyAuthorityFenceError("INJECTED_NOTE_FAILURE", "Injected failure.")):
            created = self.client.post("/api/notes", json={"note_type_id": self.note_type_id,
                "deck_id": self.deck_id, "field_values": {"Word": "rollback"}})
        self.assertEqual(created.status_code, 409, created.get_json())
        self.assertEqual(created.get_json()["error"], "INJECTED_NOTE_FAILURE")
        with self.app.app_context():
            self.assertEqual((Note.query.count(), Card.query.count(), StudyProgressSubject.query.count()), before)
            self.assertEqual(StudyProgressSubject.query.one().semantic_state_hash, state_hash)
            self.assertEqual(db.session.get(StudyAuthorityEnrollment, self.user_id).mode_code, "NOTE")


    def test_enrollment_retry_keeps_an_admitted_note_batch_untouched(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        with self.app.app_context():
            db.session.add(StudySessionBatch(session_id=snapshot["session_id"], user_id=self.user_id,
                batch_id=batch_id, batch_sequence=1, event_count=1, status="processing",
                commit_reason="manual_exit", is_final=True, request_hash="sha256-" + "1" * 64,
                payload_json="{}", enqueued_at=datetime(2026, 9, 21, 9)))
            db.session.commit()
            result = stage_note_authority_enrollment(db.session, learner_user_id=self.user_id,
                now_utc=datetime(2026, 9, 21, 9, 30))
            db.session.commit()
            self.assertEqual(result.cancelled_session_count, 0)
            self.assertEqual(StudySessionBatch.query.one().status, "processing")
            self.assertEqual(db.session.get(StudySession, snapshot["session_id"]).status, "open")


    def test_authority_enrollment_cli_is_dry_run_by_default(self):
        self._enable_existing_state_note_authority(epoch=4)
        runner = self.app.test_cli_runner()
        with self.app.app_context():
            before = StudyProgressSubject.query.one().semantic_state_hash
        dry_run = runner.invoke(args=["study-authority-enrollment", "--user-id", str(self.user_id), "--mode", "NOTE"])
        self.assertEqual(dry_run.exit_code, 0, dry_run.output)
        payload = json.loads(next(line for line in dry_run.output.splitlines() if line.startswith("{")))
        self.assertFalse(payload["applied"])
        self.assertEqual(payload["epoch"], 4)
        applied = runner.invoke(args=["study-authority-enrollment", "--user-id", str(self.user_id), "--mode", "NOTE", "--apply"])
        self.assertEqual(applied.exit_code, 0, applied.output)
        with self.app.app_context():
            self.assertEqual(db.session.get(StudyAuthorityEnrollment, self.user_id).epoch, 4)
            self.assertEqual(StudyProgressSubject.query.one().semantic_state_hash, before)
        for timezone_name in ("UTC", "Asia/Tokyo", "UTC+09:00"):
            audit = runner.invoke(args=["study-authority-read-audit", "--user-id", str(self.user_id),
                "--observed-at-utc", "2026-09-21T18:30:00+09:00", "--timezone-name", timezone_name])
            self.assertEqual(audit.exit_code, 0, audit.output)
            result = json.loads(audit.output)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["observed_at_utc"], "2026-09-21T09:30:00.000000Z")
            self.assertEqual(result["timezone"], timezone_name)
        for option, value, error_code in (("--observed-at-utc", "2026-09-21T09:30:00", "INVALID_AUDIT_TIME"),
            ("--observed-at-utc", "not-a-time", "INVALID_AUDIT_TIME"),
            ("--timezone-name", "Not/A_Timezone", "INVALID_AUDIT_TIMEZONE")):
            invalid = runner.invoke(args=["study-authority-read-audit", "--user-id", str(self.user_id), option, value])
            self.assertNotEqual(invalid.exit_code, 0)
            self.assertIn(error_code, invalid.output)

    def test_note_read_audit_tracks_tokyo_study_day_boundary(self):
        due_day = datetime(2026, 9, 23).date().toordinal()
        self._enable_existing_state_note_authority(
            initial_progress={
                "queue": "review",
                "due_day": due_day,
                "due_at": datetime(2026, 9, 22, 19, 0, 0),
                "interval_days": 1,
                "interval_days_raw": 1.0,
                "reps": 1,
            }
        )
        runner = self.app.test_cli_runner()
        for observed_at, timezone_name, expected_due in (
            ("2026-09-22T18:59:59Z", "Asia/Tokyo", 0),
            ("2026-09-22T19:00:01Z", "Asia/Tokyo", 1),
            ("2026-09-22T19:00:01Z", "UTC", 0),
        ):
            audit = runner.invoke(
                args=[
                    "study-authority-read-audit",
                    "--user-id", str(self.user_id),
                    "--observed-at-utc", observed_at,
                    "--timezone-name", timezone_name,
                ]
            )
            self.assertEqual(audit.exit_code, 0, audit.output)
            payload = json.loads(audit.output)
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["mismatches"], [])
            self.assertEqual(payload["canonical"]["due"], expected_due)
            self.assertEqual(
                payload["canonical"]["selected_card_id"] is not None,
                bool(expected_due),
            )

    def test_note_read_audit_excludes_notes_without_active_presentations(self):
        self._enable_existing_state_note_authority()
        with self.app.app_context():
            empty_type = NoteType(user_id=self.user_id, name="No active applications")
            db.session.add(empty_type)
            db.session.flush()
            db.session.add(Note(note_type_id=empty_type.id, user_id=self.user_id,
                deck_id=self.deck_id, field_values={}, tags=[]))
            db.session.commit()
        audit = self.app.test_cli_runner().invoke(args=["study-authority-read-audit", "--user-id", str(self.user_id)])
        self.assertEqual(audit.exit_code, 0, audit.output)
        payload = json.loads(audit.output)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["canonical"]["new"], 1)


    def test_note_read_audit_compares_learn_ahead_order(self):
        self._enable_existing_state_note_authority(
            initial_progress={
                "queue": "learning",
                "due_at": datetime(2026, 9, 23, 10, 0, 30),
                "step_index": 1,
            }
        )
        audit = self.app.test_cli_runner().invoke(
            args=[
                "study-authority-read-audit",
                "--user-id", str(self.user_id),
                "--observed-at-utc", "2026-09-23T10:00:00Z",
                "--timezone-name", "UTC",
            ]
        )
        self.assertEqual(audit.exit_code, 0, audit.output)
        payload = json.loads(audit.output)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["canonical"]["learn"], 1)
        self.assertIsNotNone(payload["canonical"]["selected_card_id"])

    def test_note_read_audit_orders_mixed_review_due_day_like_legacy_sql(self):
        with self.app.app_context():
            first_note_id = str(Note.query.filter_by(user_id=self.user_id).one().id)
            template = next(row.template for row in template_library_repository.applications(db.session, self.note_type_id))
            second_note = Note(
                note_type_id=self.note_type_id,
                user_id=self.user_id,
                deck_id=self.deck_id,
                field_values={"Word": "second"},
                tags=[],
            )
            db.session.add(second_note)
            db.session.flush()
            db.session.commit()
            second_note_id = str(second_note.id)

        self._enable_existing_state_note_authority(
            note_id=first_note_id,
            initial_progress={
                "queue": "review",
                "due_day": datetime(2026, 9, 22).date().toordinal(),
                "due_at": datetime(2026, 9, 22, 12, 0, 0),
                "interval_days": 1,
                "interval_days_raw": 1.0,
                "reps": 1,
            },
        )
        self._enable_existing_state_note_authority(
            enroll=False,
            include_token=True,
            note_id=second_note_id,
            initial_progress={
                "queue": "review",
                "due_day": None,
                "due_at": datetime(2026, 9, 21, 12, 0, 0),
                "interval_days": 1,
                "interval_days_raw": 1.0,
                "reps": 1,
            },
        )
        with self.app.app_context():
            first_card_id = str(Card.query.filter_by(note_id=first_note_id).one().id)

        audit = self.app.test_cli_runner().invoke(
            args=[
                "study-authority-read-audit",
                "--user-id", str(self.user_id),
                "--observed-at-utc", "2026-09-23T10:00:00Z",
                "--timezone-name", "UTC",
            ]
        )
        self.assertEqual(audit.exit_code, 0, audit.output)
        payload = json.loads(audit.output)
        self.assertEqual(payload["status"], "PASS")
        self.assertEqual(payload["canonical"]["due"], 2)
        self.assertEqual(payload["canonical"]["selected_card_id"], first_card_id)

    def test_note_single_card_read_rejects_divergent_unrequested_sibling(self):
        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.user_id).one()
            template = attach_template(db.session, note_type_id=self.note_type_id, owner_user_id=self.user_id, name="Second card", front_html="{{Word}}", back_html="{{Word}}", position=1)
            db.session.add(template)
            db.session.flush()
            db.session.commit()

            stage_note_authority_enrollment(
                db.session,
                learner_user_id=self.user_id,
                now_utc=datetime(2026, 9, 22, 8, 0, 0),
            )
            db.session.commit()
            cards = Card.query.filter_by(note_id=str(note.id)).order_by(Card.id).all()
            deck_options = resolve_deck_options(
                user_id=self.user_id, deck_id=self.deck_id
            )
            healthy_read = load_study_authority_card_read(
                db.session,
                learner_user_id=self.user_id,
                card=cards[0],
                now_utc=datetime(2026, 9, 22, 8, 0, 0),
                timezone_name="UTC",
                deck_options=deck_options,
            )
            self.assertEqual(healthy_read.state.type, "new")
            db.session.rollback()
            # Availability that disagrees with the row's state fails closed.
            StudyProgressSubject.query.one().normalized_queue = "review"
            db.session.commit()

            with self.assertRaises(StudyAuthorityReadError) as failure:
                load_study_authority_card_read(
                    db.session,
                    learner_user_id=self.user_id,
                    card=cards[0],
                    now_utc=datetime(2026, 9, 22, 8, 0, 0),
                    timezone_name="UTC",
                    deck_options=deck_options,
                )
            self.assertEqual(failure.exception.code, "AUTHORITY_READ_PARITY_DIVERGED")
            db.session.rollback()

    def test_note_enrollment_rollback_is_retired_and_keeps_the_note_lease(self):
        self._enable_existing_state_note_authority(epoch=4)
        snapshot = self._open_session_v4()
        with self.app.app_context():
            with self.assertRaises(StudyAuthorityEnrollmentError) as failure:
                stage_legacy_authority_enrollment(
                    db.session,
                    learner_user_id=self.user_id,
                    now_utc=datetime(2026, 9, 21, 9, 30, 0),
                )
            self.assertEqual(failure.exception.code, "LEGACY_ROLLBACK_RETIRED")
            db.session.rollback()
            enrollment = db.session.get(StudyAuthorityEnrollment, self.user_id)
            self.assertEqual((enrollment.mode_code, enrollment.epoch), ("NOTE", 4))
            self.assertEqual(
                db.session.get(StudySession, snapshot["session_id"]).status,
                "open",
            )

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
            subject = StudyProgressSubject.query.one()
            self.assertEqual(int(subject.authority_revision), 1)
            self.assertNotEqual(bytes(subject.semantic_state_hash).hex(), base_hash)
            assert_retired_progress_absent(self, db.session)
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
        self.assertEqual(duplicate.status_code, 200, duplicate.get_json())
        self.assertTrue(duplicate.get_json()["authority"]["replayed"])
        self.assertEqual(duplicate.get_json()["authority"]["authority_revision"], 1)
        self.assertEqual(duplicate.get_json()["applied_interval"], response.get_json()["applied_interval"])

        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)
            subject = StudyProgressSubject.query.one()
            self.assertEqual(int(subject.authority_revision), 1)
            self.assertEqual(subject.state_payload["reps"], "1")
            assert_retired_progress_absent(self, db.session)

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
        with self._record_study_sql():
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
        with self.app.app_context():
            assert_retired_progress_absent(self, db.session)
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["summary"]["new"], 1)
        self.assertEqual(payload["summary"]["learning"], 0)
        self.assertEqual(payload["summary"]["due"], 0)
        self.assertEqual(payload["summary"]["total_due"], 1)

    def test_statistics_note_future_due_bypasses_legacy_progress_query(self):
        self._enable_existing_state_note_authority(epoch=15)
        with self._record_study_sql():
            response = self.client.get(
                "/api/statistics/overview",
                query_string={"year": 2026, "timezone": "Asia/Tokyo"},
            )
        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        self.assertEqual(payload["year"], 2026)
        self.assertEqual(payload["timezone"], "Asia/Tokyo")
        self.assertEqual(len(payload["heatmap"]), 365)
        # The page reads only these; MCP keeps the builder's full shape.
        self.assertEqual(set(payload), {"year", "timezone", "today", "heatmap", "metrics"})
        self.assertEqual(set(payload["today"]), {"date", "cards", "minutes"})
        self.assertEqual(set(payload["heatmap"][0]), {"date", "cards", "minutes", "is_future"})
        self.assertEqual(set(payload["metrics"]), {
            "daily_average_cards", "days_learned_percent", "longest_streak_days", "current_streak_days",
        })

    def test_today_future_note_analytics_bypass_legacy_progress_queries(self):
        self._enable_existing_state_note_authority(epoch=16)
        with self._record_study_sql():
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
        with self._record_study_sql():
            card_id = str(Card.query.join(Note, Card.note_id == Note.id).one().id)
        with self._record_study_sql():
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

    def test_study_deck_page_serves_the_spa_without_reading_progress(self):
        self._enable_existing_state_note_authority(epoch=19)
        refuse = AssertionError("the Study page shell must not read progress")
        with self._record_study_sql():
            response = self.client.get(f"/vocabulary/study/deck/{self.deck_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn('<div id="root"></div>', response.get_data(as_text=True))

    def test_reused_commit_id_with_another_payload_settles_on_the_stored_receipt(self):
        # Production 2026-10-01: a browser lost the receipt of a commit and
        # resent the same commit id with another reason (auto_finish, then
        # manual_exit). It must get the stored receipt to settle, and nothing
        # may be applied twice.
        snapshot = self._open_session_v4()
        payload = {**self._commit_payload(snapshot), "commit_reason": "page_exit"}
        url = f"/api/study/sessions/{snapshot['session_id']}/commit"
        first = self.client.post(url, json=payload)
        self.assertEqual(first.status_code, 200, first.get_json())
        receipt = first.get_json()
        with self.app.app_context():
            events_before = ReviewEvent.query.count()

        resent = self.client.post(url, json={**payload, "commit_reason": "manual_exit"})
        self.assertEqual(resent.status_code, 409, resent.get_json())
        self.assertEqual(resent.get_json()["error"], "SESSION_ALREADY_COMMITTED")
        self.assertEqual(resent.get_json()["details"], receipt)
        self.assertEqual(self.client.post(url, json=payload).get_json(), receipt)
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), events_before)

    def test_historical_legacy_commit_receipt_replays_without_legacy_execution(self):
        # Seed a pre-cutover artifact directly, including its exact request hash.
        # Retirement must read this receipt without converting its old wire IDs.
        now = datetime.utcnow().replace(microsecond=0)
        raw_card_id, token = str(uuid4()), "historical-session-token"
        payload = {"schema_version": "study-commit.v2", "commit_id": str(uuid4()),
            "session_token": token, "snapshot_hash": "sha256-" + "7" * 64,
            "events": [{"card_id": raw_card_id, "event_id": str(uuid4()), "rating": "good", "sequence": 1}],
            "final_states": []}
        receipt = {"schema_version": "study-commit-receipt.v1", "applied_event_count": 1,
            "historical_card_id": raw_card_id}
        from app.services.study_session_service import _request_hash
        with self.app.app_context():
            row = StudySession(user_id=self.user_id, scope_id=str(self.deck_id), local_deck_id=self.deck_id,
                wire_schema_version="study-session.v3", status="committed", snapshot_hash=payload["snapshot_hash"],
                token_hash=sha256(token.encode()).hexdigest(), opened_at=now, expires_at=now + timedelta(hours=1),
                committed_at=now, config_snapshot_json="{}")
            db.session.add(row)
            db.session.flush()
            session_id = row.id
            card = Card.query.one()
            archive_wire_alias(db.session, card, raw_card_id)
            db.session.add(StudySessionCard(session_id=session_id, card_id=raw_card_id,
                base_state_hash="sha256-" + "8" * 64, scheduler_config_hash="sha256-" + "9" * 64,
                initial_state_json='{"type":"new","historical":"unchanged"}', ordinal=0))
            event = ReviewEvent(user_id=self.user_id, card_id=raw_card_id, note_id=card.note_id,
                deck_id=self.deck_id, study_session_id=session_id, reviewed_at=now,
                rating="good", mode="flashcard", sequence_no=1,
                payload_json='{"old_wire_id":"' + raw_card_id + '"}')
            db.session.add(event)
            db.session.add(StudySessionCommit(session_id=session_id, user_id=self.user_id,
                idempotency_key=payload["commit_id"], request_hash=_request_hash(payload),
                response_json=json.dumps(receipt)))
            open_lease = StudySession(user_id=self.user_id, scope_id=str(self.deck_id), local_deck_id=self.deck_id,
                wire_schema_version="study-session.v3", status="open", snapshot_hash=payload["snapshot_hash"],
                token_hash=sha256(token.encode()).hexdigest(), opened_at=now, expires_at=now + timedelta(hours=1),
                config_snapshot_json="{}")
            db.session.add(open_lease)
            db.session.commit()
            open_id = open_lease.id
            before = (_request_hash(payload), StudyProgressSubject.query.one().semantic_state_hash,
                StudySessionCard.query.one().initial_state_json, event.payload_json)
        url = f"/api/study/sessions/{session_id}/commit"
        replay = self.client.post(url, json=payload)
        self.assertEqual(replay.status_code, 200, replay.get_json())
        self.assertEqual(replay.get_json(), receipt)
        conflict = self.client.post(url, json={**payload, "commit_id": str(uuid4())})
        self.assertEqual(conflict.status_code, 409, conflict.get_json())
        self.assertEqual(conflict.get_json()["details"], receipt)
        refused = self.client.post(f"/api/study/sessions/{open_id}/commit", json=payload)
        self.assertEqual(refused.status_code, 409, refused.get_json())
        self.assertEqual(refused.get_json()["error"], "WIRE_CONTRACT_MISMATCH")
        with self.app.app_context():
            stored = StudySessionCommit.query.one()
            self.assertEqual(stored.request_hash, before[0])
            self.assertEqual(json.loads(stored.response_json), receipt)
            self.assertEqual(StudyProgressSubject.query.one().semantic_state_hash, before[1])
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(ReviewEvent.query.one().card_id, raw_card_id)
            self.assertEqual(ReviewEvent.query.one().payload_json, before[3])
            self.assertEqual(StudySessionCard.query.one().card_id, raw_card_id)
            self.assertEqual(StudySessionCard.query.one().initial_state_json, before[2])


    def test_direct_note_read_fails_closed_on_stale_canonical_availability(self):
        self._enable_existing_state_note_authority(epoch=13)
        with self.app.app_context():
            # The row's availability says due; its state says new.
            subject = StudyProgressSubject.query.one()
            subject.normalized_queue, subject.due_day = "review", 0
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

    def test_direct_note_read_uses_retired_schema_and_fails_closed_on_a_corrupt_row(self):
        self._enable_existing_state_note_authority(epoch=11)
        with self.app.app_context():
            assert_retired_progress_absent(self, db.session)

        response = self.client.get(
            "/api/study/session/next",
            query_string={"scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["new_count"], 1)

        with self.app.app_context():
            subject = StudyProgressSubject.query.one()
            subject.state_payload = {**subject.state_payload, "reps": "99"}
            db.session.commit()
        response = self.client.get(
            "/api/study/session/next",
            query_string={"scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "STATE_HASH_MISMATCH")

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
                int(StudyProgressSubject.query.one().authority_revision),
                2,
            )
            assert_retired_progress_absent(self, db.session)

    def test_wire_v4_commit_rejects_stale_pin_without_partial_writes(self):
        self._enable_existing_state_note_authority(epoch=7)
        snapshot = self._open_session_v4()
        with self.app.app_context():
            subject = StudyProgressSubject.query.one()
            subject.authority_revision = int(subject.authority_revision) + 1
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
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(
                db.session.get(StudySession, snapshot["session_id"]).status,
                "open",
            )

    def test_v4_commit_requires_exact_identity_and_paired_envelope(self):
        wrong_envelope_snapshot = self._open_session_v4()
        wrong_envelope = self._commit_payload(wrong_envelope_snapshot)
        wrong_envelope["schema_version"] = "study-commit.v1"
        response = self.client.post(
            f"/api/study/sessions/{wrong_envelope_snapshot['session_id']}/commit",
            json=wrong_envelope,
        )
        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(response.get_json()["error"], "UNSUPPORTED_COMMIT_SCHEMA")

        missing_snapshot = self._open_session_v4()
        missing = self._commit_payload(missing_snapshot)
        del missing["events"][0]["action_contract_version"]
        response = self.client.post(
            f"/api/study/sessions/{missing_snapshot['session_id']}/commit",
            json=missing,
        )
        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(response.get_json()["error"], "WIRE_CONTRACT_MISMATCH")

        mismatch_snapshot = self._open_session_v4()
        mismatch = self._commit_payload(mismatch_snapshot)
        mismatch["events"][0]["algorithm_version"] = "latest"
        response = self.client.post(
            f"/api/study/sessions/{mismatch_snapshot['session_id']}/commit",
            json=mismatch,
        )
        self.assertEqual(response.status_code, 422, response.get_json())
        self.assertEqual(response.get_json()["error"], "WIRE_CONTRACT_MISMATCH")

        valid_snapshot = self._open_session_v4()
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
                "study-session.v4",
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
            assert_retired_progress_absent(self, db.session)
        native_operation = self.client.post(
            f"/api/study/{card_id}/answer",
            json={**base_payload, "operation_key": str(uuid4())},
        )
        self.assertEqual(
            native_operation.status_code,
            200,
            native_operation.get_json(),
        )
        self.assertEqual(native_operation.get_json()["authority"]["mode"], "NOTE")

        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 1)
            assert_retired_progress_absent(self, db.session)

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
            assert_retired_progress_absent(self, db.session)

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
        from models.user_scheduler_settings import UserSchedulerSettings

        # Keep the day boundary 12 h away: a learning step that crosses it
        # becomes tomorrow's card, so auto_finish would be legitimately allowed.
        with self.app.app_context():
            db.session.add(UserSchedulerSettings(
                user_id=self.user_id,
                day_boundary_hour_local=(datetime.utcnow().hour + 12) % 24,
            ))
            db.session.commit()
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
        second_event["operation_key"] = second_event["event_id"]
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
            json={"scope": "deck", "scope_id": empty_deck_id, "accepted_session_schema_versions": ["study-session.v4"]},
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
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one()
            self.assertEqual(int(progress.state_payload["reps"]), 1)
            self.assertEqual(progress.authority_revision, 1)
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
        self.assertEqual(card["authority_pin"]["base_authority_revision"], "1")
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
        second_event["operation_key"] = second_event["event_id"]
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
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one()
            self.assertEqual(int(progress.state_payload["reps"]), 2)

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
            "AUTHORITY_STATE_CONFLICT",
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
            "AUTHORITY_STATE_CONFLICT",
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

    def test_v4_commit_rejects_client_supplied_final_state(self):
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
        self.assertEqual(response.get_json()["error"], "INVALID_FINAL_STATES")
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 0)
            self.assertEqual(StudyProgressSubject.query.one().authority_revision, 0)

    def test_note_commit_normalizes_event_clock_to_mysql_datetime_seconds(self):
        snapshot = self._open_session()
        payload = self._commit_payload(snapshot)
        card = snapshot["cards"][0]
        policy = snapshot["policies"][card["policy_key"]]
        opened_at = datetime.fromisoformat(snapshot["server_now_utc"].replace("Z", "+00:00")).replace(tzinfo=None)
        # The wire offset retains milliseconds, but replay uses the same
        # second precision as historical MySQL DATETIME review-event clocks.
        answer_at = (opened_at + timedelta(milliseconds=1289)).replace(microsecond=0)
        expected = applyAnswer(deserialize_card_state(card["state"]),
            deserialize_deck_options(policy["config"]), answer_at, "good", timezone_name=snapshot["timezone"])
        payload["events"][0]["scheduler_offset_ms"] = 1289
        self.assertEqual(payload["final_states"], [])
        response = self.client.post(f"/api/study/sessions/{snapshot['session_id']}/commit", json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["applied_event_count"], 1)
        fresh = self._open_session()
        self.assertEqual(fresh["cards"][0]["state"], serialize_card_state(expected))
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.one().reviewed_at, answer_at.replace(microsecond=0))
            self.assertEqual(StudyProgressSubject.query.one().authority_revision, 1)

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
            template = attach_template(db.session, note_type_id=note_type.id, owner_user_id=self.user_id, name="Card 1", front_html="{{Word}}", back_html="{{Word}}", is_default=True)
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
            card = Card.query.filter_by(note_id=note.id, template_id=template.id).one()
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
            stage_note_state(db.session, user_id=self.user_id, card_id=card.id,
                queue="review", due_day=_day_index(datetime.utcnow(), 4), interval_days=5,
                ease_factor=2.5, lapses=7, revision=0)
            db.session.commit()
            local_deck_id = local_deck.id
            source_card_id = card.id
            source_note_id = note.id

        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": local_deck_id, "accepted_session_schema_versions": ["study-session.v4"]},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        snapshot = response.get_json()
        self.assertEqual(snapshot["cards"][0]["card_id"], source_card_id)
        self.assertEqual(
            snapshot["cards"][0]["local_deck_id"],
            local_deck_id,
        )
        payload = self._commit_payload(snapshot)
        payload["events"][0].update(rating="again", action_key="review.again", trigger_key="scheduler.review.again")
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
            progress = StudyProgressSubject.query.filter_by(
                learner_user_id=self.user_id, live_note_id=source_note_id).one()
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
            template = attach_template(db.session, note_type_id=second_type.id, owner_user_id=self.user_id, name="Another Card", front_html="front", back_html="back", position=0, is_default=True)
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
            template = attach_template(db.session, note_type_id=self.note_type_id, owner_user_id=self.user_id, name="Card 2", front_html="Reverse {{Word}}", back_html="{{Word}}", position=1, is_default=False)
            db.session.add(template)
            db.session.flush()
            card = Card.query.filter_by(note_id=note.id, template_id=template.id).one()
            db.session.commit()
            return str(template.id), str(card.id)

    def test_multiple_compositions_require_explicit_selection(self):
        self._add_second_composition()
        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": self.deck_id, "accepted_session_schema_versions": ["study-session.v4"]},
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
                "composition_id": composition_id, "accepted_session_schema_versions": ["study-session.v4"]},
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
                ], "accepted_session_schema_versions": ["study-session.v4"]},
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
            other_template = attach_template(db.session, note_type_id=other_type.id, owner_user_id=self.user_id, name="Other Card", front_html="front", back_html="back", is_default=True)
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
            db.session.commit()
            composition_id = (
                f"comp:notetype:{other_type.id}:template:{other_template.id}"
            )
        response = self.client.post(
            "/api/study/sessions",
            json={
                "scope": "deck",
                "scope_id": self.deck_id,
                "composition_id": composition_id, "accepted_session_schema_versions": ["study-session.v4"]},
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
                    "composition_id": composition_id, "accepted_session_schema_versions": ["study-session.v4"]},
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
            json={"scope": "deck", "scope_id": 999999, "accepted_session_schema_versions": ["study-session.v4"]},
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
            json={"scope": "deck", "scope_id": other_deck_id, "accepted_session_schema_versions": ["study-session.v4"]},
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
