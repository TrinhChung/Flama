"""P5-05 Study Session v4 NOTE authority pin behavior."""

from __future__ import annotations

from datetime import datetime
import unittest

import sqlalchemy as sa

from app import create_app
from app.repositories.study_authority_repository import (
    StudyAuthorityRoute,
    lock_study_authority_subject,
)
from app.services.study_session_authority_pin_service import (
    StudySessionAuthorityPinError,
    lock_study_session_authority_subjects,
    lock_study_session_authority_pins,
    serialize_study_session_authority_pin,
    stage_study_session_authority_pin,
)
from app.services.anki_scheduler import CardState
from app.services.study_consolidated_progress_service import (
    apply_note_availability,
    clear_note_progress,
    note_burial,
    project_subject_state,
)
from app.services.study_progress_shadow_codec import (
    algorithm_state_hash,
    serialize_card_state,
)
from models import db
from models.card import Card
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_session_authority_pin import StudySessionAuthorityPin
from models.study_session_card import StudySessionCard
from models.template import Template
from models.user import User


NOW = datetime(2026, 9, 21, 7, 0, 0)
STATE_HASH = b"\x77" * 32


class StudySessionAuthorityPinServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        user = User(username="pin-user", email="pin@example.test")
        db.session.add(user)
        db.session.flush()
        self.user_id = int(user.id)
        note_type = NoteType(user_id=self.user_id, name="Pin type")
        templates = (
            Template(note_type=note_type, name="Pin template A", position=0),
            Template(note_type=note_type, name="Pin template B", position=1),
        )
        deck = Deck(
            owner_user_id=self.user_id,
            note_type=note_type,
            name="Pin deck",
            created_at=NOW,
            updated_at=NOW,
        )
        note = Note(
            note_type=note_type,
            user_id=self.user_id,
            field_values={"Front": "pin"},
            tags=[],
            created_at=NOW,
            updated_at=NOW,
        )
        cards = (
            Card(note=note, template=templates[0], created_at=NOW, updated_at=NOW),
            Card(note=note, template=templates[1], created_at=NOW, updated_at=NOW),
        )
        db.session.add_all([note_type, *templates, deck, note, *cards])
        db.session.flush()
        note.deck_id = int(deck.id)
        subject = StudyProgressSubject(
            learner_user_id=self.user_id,
            logical_note_key=str(note.id).encode("utf-8"),
            live_note_id=str(note.id),
            subject_generation=1,
            mirror_revision=1,
            status_code="MIRRORED_EQUIVALENT_FANIN",
            contributor_count=2,
            created_at=NOW,
            updated_at=NOW,
        )
        db.session.add(subject)
        db.session.flush()
        initial_state = CardState(
            type="review",
            stepIndex=0,
            due=NOW,
            dueDay=1,
            intervalDays=3.0,
            ease=2.5,
            reps=2,
            lapses=0,
            lastReviewAt=NOW,
            reviewKind="review",
            schedulerMode="legacy",
            suspended=False,
            suspensionReason=None,
            leeched=False,
            memoryState=None,
        )
        state_document = serialize_card_state(initial_state)
        # The Note's one row holds its state (ADR P10).
        subject.algorithm_key = "legacy-anki"
        subject.algorithm_version = "1.0.0"
        subject.state_schema_version = "anki-card-state.v1"
        subject.storage_codec = "flama-canonical-state-json.v1"
        subject.state_payload = state_document.payload
        subject.state_payload_size = state_document.size
        subject.algorithm_state_hash = algorithm_state_hash(state_document.payload)
        subject.semantic_state_hash = STATE_HASH
        subject.history_completeness_code = "HISTORY_NATIVE_COMPLETE"
        subject.current_provenance_code = "UNKNOWN_LEGACY"
        apply_note_availability(
            subject, project_subject_state(state_document.payload, burial=note_burial(subject)), now_utc=NOW)
        study_session = StudySession(
            id="11111111-1111-4111-8111-111111111111",
            user_id=self.user_id,
            scope_type="deck",
            scope_id=str(deck.id),
            local_deck_id=int(deck.id),
            status="open",
            scheduler_algorithm="legacy-anki",
            algorithm_version="1.0.0",
            wire_schema_version="study-session.v4",
            timezone="UTC",
            day_boundary_hour_local=4,
            learn_ahead_seconds=1200,
            snapshot_hash="sha256-" + "1" * 64,
            token_hash="2" * 64,
            config_snapshot_json="{}",
            opened_at=NOW,
            expires_at=datetime(2026, 9, 22, 7, 0, 0),
            created_at=NOW,
            updated_at=NOW,
        )
        memberships = tuple(
            StudySessionCard(
                session=study_session,
                card_id=str(card.id),
                source_deck_id=int(deck.id),
                local_deck_id=int(deck.id),
                note_type_id=str(note_type.id),
                base_progress_revision=0,
                base_state_hash="sha256-" + "3" * 64,
                scheduler_config_hash="sha256-" + "4" * 64,
                initial_state_json="{}",
                ordinal=index,
                created_at=NOW,
            )
            for index, card in enumerate(cards)
        )
        db.session.add_all([study_session, *memberships])
        db.session.commit()
        self.session_id = str(study_session.id)
        self.subject_id = int(subject.id)
        self.membership_ids = tuple(int(row.id) for row in memberships)
        self.note_id = str(note.id)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _route(self, *, epoch: int = 3) -> StudyAuthorityRoute:
        return StudyAuthorityRoute(self.user_id, "NOTE", epoch, True)

    def _session_context(self):
        study_session = db.session.execute(
            sa.select(StudySession)
            .where(StudySession.id == self.session_id)
            .with_for_update()
        ).scalar_one()
        memberships = tuple(
            db.session.execute(
                sa.select(StudySessionCard)
                .where(StudySessionCard.session_id == self.session_id)
                .order_by(StudySessionCard.id.asc())
                .with_for_update()
            ).scalars()
        )
        subject = db.session.execute(
            sa.select(StudyProgressSubject)
            .where(StudyProgressSubject.id == self.subject_id)
            .with_for_update()
        ).scalar_one()
        locked = lock_study_authority_subject(
            db.session,
            route=self._route(),
            subject=subject,
            now_utc=NOW,
        )
        return study_session, memberships, locked

    def _stage_all(self):
        study_session, memberships, locked = self._session_context()
        for membership in memberships:
            stage_study_session_authority_pin(
                db.session,
                study_session=study_session,
                session_card=membership,
                route=self._route(),
                locked=locked,
                now_utc=NOW,
            )
        db.session.flush()
        return study_session, memberships

    def test_stage_and_lock_complete_note_pin_vector(self):
        study_session, memberships = self._stage_all()
        result = lock_study_session_authority_pins(
            db.session,
            study_session=study_session,
            session_cards=memberships,
            route=self._route(),
        )
        self.assertEqual(result.enrollment_epoch, 3)
        self.assertEqual(set(result.pin_by_session_card_id), set(self.membership_ids))
        identities = list(result.identity_by_session_card_id.values())
        self.assertEqual(len({item.logical_note_key for item in identities}), 1)
        self.assertTrue(
            all(item.base_authority_revision == "0" for item in identities)
        )
        self.assertTrue(
            all(
                item.base_authority_state_hash == STATE_HASH.hex()
                for item in identities
            )
        )
        serialized = serialize_study_session_authority_pin(
            result.pin_by_session_card_id[self.membership_ids[0]]
        )
        self.assertEqual(
            serialized,
            {
                "schema_version": "study-note-authority-pin.v1",
                "authority_mode": "NOTE",
                "enrollment_epoch": "3",
                "logical_note_key": identities[0].logical_note_key,
                "subject_generation": "1",
                "base_authority_revision": "0",
                "base_authority_state_hash": STATE_HASH.hex(),
            },
        )

    def test_lock_session_subjects_decodes_existing_note_state(self):
        result = lock_study_session_authority_subjects(
            db.session,
            route=self._route(),
            logical_note_keys=[self.note_id, self.note_id],
            now_utc=NOW,
        )
        self.assertEqual(result.enrollment_epoch, 3)
        self.assertEqual(set(result.locked_by_logical_note_key), {self.note_id})
        self.assertEqual(
            result.state_by_logical_note_key[self.note_id].type,
            "review",
        )

    def test_lock_session_subjects_fails_closed_for_missing_or_first_state(self):
        with self.assertRaises(StudySessionAuthorityPinError) as missing:
            lock_study_session_authority_subjects(
                db.session,
                route=self._route(),
                logical_note_keys=["22222222-2222-4222-8222-222222222222"],
                now_utc=NOW,
            )
        self.assertEqual(
            missing.exception.code,
            "INCOMPLETE_SESSION_AUTHORITY_SUBJECTS",
        )
        db.session.rollback()

        clear_note_progress(db.session.get(StudyProgressSubject, self.subject_id), now_utc=NOW)
        db.session.commit()
        with self.assertRaises(StudySessionAuthorityPinError) as first_state:
            lock_study_session_authority_subjects(
                db.session,
                route=self._route(),
                logical_note_keys=[self.note_id],
                now_utc=NOW,
            )
        self.assertEqual(first_state.exception.code, "AUTHORITY_STATE_REQUIRED")

    def test_lock_rejects_missing_or_divergent_sibling_pin(self):
        study_session, memberships = self._stage_all()
        db.session.delete(db.session.get(StudySessionAuthorityPin, self.membership_ids[-1]))
        db.session.flush()
        with self.assertRaises(StudySessionAuthorityPinError) as missing:
            lock_study_session_authority_pins(
                db.session,
                study_session=study_session,
                session_cards=memberships,
                route=self._route(),
            )
        self.assertEqual(missing.exception.code, "INCOMPLETE_SESSION_AUTHORITY_PINS")
        db.session.rollback()

        study_session, memberships = self._stage_all()
        pin = db.session.get(StudySessionAuthorityPin, self.membership_ids[-1])
        pin.base_authority_revision = 1
        db.session.flush()
        with self.assertRaises(StudySessionAuthorityPinError) as divergent:
            lock_study_session_authority_pins(
                db.session,
                study_session=study_session,
                session_cards=memberships,
                route=self._route(),
            )
        self.assertEqual(divergent.exception.code, "SESSION_AUTHORITY_SUBJECT_CONFLICT")
        db.session.rollback()

    def test_epoch_and_wire_mismatch_fail_closed(self):
        study_session, memberships = self._stage_all()
        with self.assertRaises(StudySessionAuthorityPinError) as epoch:
            lock_study_session_authority_pins(
                db.session,
                study_session=study_session,
                session_cards=memberships,
                route=self._route(epoch=4),
            )
        self.assertEqual(epoch.exception.code, "SESSION_AUTHORITY_EPOCH_CONFLICT")
        db.session.rollback()

        study_session, memberships, locked = self._session_context()
        study_session.wire_schema_version = "study-session.v3"
        with self.assertRaises(StudySessionAuthorityPinError) as wire:
            stage_study_session_authority_pin(
                db.session,
                study_session=study_session,
                session_card=memberships[0],
                route=self._route(),
                locked=locked,
                now_utc=NOW,
            )
        self.assertEqual(wire.exception.code, "WIRE_CONTRACT_MISMATCH")
        db.session.rollback()

    def test_pin_staging_is_outer_rollback_safe(self):
        self._stage_all()
        self.assertEqual(StudySessionAuthorityPin.query.count(), 2)
        db.session.rollback()
        self.assertEqual(StudySessionAuthorityPin.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
