"""P5-04 subject-token/state CAS contract remains inert and fail-closed."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import unittest

from sqlalchemy import select

from app import create_app
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    StudyAuthorityRoute,
    lock_study_authority_subject,
)
from app.services.study_authority_cas_service import (
    StudyAuthorityCASError,
    StudyAuthorityCASExpectation,
    verify_study_authority_cas,
)
from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress
from models import db
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.user import User


NOW = datetime(2026, 9, 21, 1, 2, 3, 456789)


def _mapped_state() -> MappedCardProgress:
    progress = SimpleNamespace(
        id=1,
        user_id=1,
        card_id="cas-card",
        queue="review",
        step_index=0,
        due_at=datetime(2026, 9, 30, 4, 0, 0),
        due_day=20726,
        interval_days=10,
        interval_days_raw=10.0,
        is_suspended=False,
        is_buried=False,
        buried_until_day=None,
        review_kind="review",
        scheduler_mode="legacy",
        ease_factor=2.5,
        memory_stability=None,
        memory_difficulty=None,
        suspension_reason=None,
        last_leech_at=None,
        last_leech_lapses=0,
        last_review_event_id=None,
        reps=4,
        lapses=0,
        last_reviewed_at=datetime(2026, 9, 20, 4, 0, 0),
        revision=3,
        created_at=NOW,
        updated_at=NOW,
    )
    mapped = map_card_progress(progress, card_created_at=NOW)
    assert isinstance(mapped, MappedCardProgress)
    return mapped


class StudyAuthorityCASTests(unittest.TestCase):
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
        user = User(email="cas@example.test", username="cas-user")
        db.session.add(user)
        db.session.flush()
        self.user_id = int(user.id)
        subject = StudyProgressSubject(
            learner_user_id=self.user_id,
            logical_note_key=b"cas-note",
            live_note_id=None,
            subject_generation=1,
            mirror_revision=3,
            status_code="MIRRORED_SINGLE",
            contributor_count=1,
            created_at=NOW,
            updated_at=NOW,
        )
        db.session.add(subject)
        db.session.commit()
        self.subject_id = int(subject.id)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _route(self, *, mode: str = "NOTE", epoch: int = 5) -> StudyAuthorityRoute:
        return StudyAuthorityRoute(
            learner_user_id=self.user_id,
            mode_code=mode,
            epoch=epoch,
            persisted=True,
        )

    def _subject(self) -> StudyProgressSubject:
        return db.session.execute(
            select(StudyProgressSubject)
            .where(StudyProgressSubject.id == self.subject_id)
            .with_for_update()
        ).scalar_one()

    def _add_state(self) -> MappedCardProgress:
        mapped = _mapped_state()
        db.session.add(
            StudyProgressState(
                subject_id=self.subject_id,
                subject_generation=1,
                mirror_revision=3,
                algorithm_key=mapped.algorithm_key,
                algorithm_version=mapped.algorithm_version,
                state_schema_version=mapped.state_schema_version,
                storage_codec=mapped.storage_codec,
                state_payload=mapped.state.payload,
                state_payload_size=mapped.state.size,
                algorithm_state_hash=mapped.algorithm_state_hash,
                semantic_state_hash=mapped.semantic_state_hash,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        db.session.commit()
        return mapped

    def _lock(self, route: StudyAuthorityRoute | None = None):
        return lock_study_authority_subject(
            db.session,
            route=route or self._route(),
            subject=self._subject(),
            now_utc=NOW,
        )

    @staticmethod
    def _expected(mapped: MappedCardProgress | None = None, **overrides: object):
        values: dict[str, object] = {
            "enrollment_epoch": 5,
            "subject_generation": 1,
            "authority_revision": 0,
            "semantic_state_hash": (
                mapped.semantic_state_hash if mapped is not None else None
            ),
        }
        values.update(overrides)
        return StudyAuthorityCASExpectation(**values)  # type: ignore[arg-type]

    def test_first_token_initializes_from_exact_existing_state(self):
        mapped = self._add_state()
        locked = self._lock()
        self.assertTrue(locked.token_created)
        self.assertEqual(locked.token.authority_revision, 0)
        self.assertEqual(locked.token.semantic_state_hash, mapped.semantic_state_hash)

        checked = verify_study_authority_cas(
            route=self._route(),
            locked=locked,
            expected=self._expected(mapped),
        )
        self.assertEqual(checked.subject_id, self.subject_id)
        self.assertTrue(checked.has_current_state)

    def test_first_token_without_state_has_null_hash(self):
        locked = self._lock()
        checked = verify_study_authority_cas(
            route=self._route(),
            locked=locked,
            expected=self._expected(),
        )
        self.assertTrue(locked.token_created)
        self.assertIsNone(locked.token.semantic_state_hash)
        self.assertFalse(checked.has_current_state)

    def test_existing_token_is_locked_without_resetting_revision(self):
        mapped = self._add_state()
        first = self._lock()
        first.token.authority_revision = 7
        db.session.commit()

        second = self._lock()
        self.assertFalse(second.token_created)
        self.assertEqual(second.token.authority_revision, 7)
        checked = verify_study_authority_cas(
            route=self._route(),
            locked=second,
            expected=self._expected(mapped, authority_revision=7),
        )
        self.assertEqual(checked.authority_revision, 7)

    def test_wrong_learner_and_generation_divergence_fail_closed(self):
        other_route = StudyAuthorityRoute(
            learner_user_id=self.user_id + 1,
            mode_code="NOTE",
            epoch=5,
            persisted=True,
        )
        with self.assertRaises(StudyAuthorityFenceError) as wrong_learner:
            self._lock(other_route)
        self.assertEqual(wrong_learner.exception.code, "WRONG_LEARNER")
        db.session.rollback()

        token = self._lock().token
        token.subject_generation = 2
        db.session.commit()
        with self.assertRaises(StudyAuthorityFenceError) as generation:
            self._lock()
        self.assertEqual(generation.exception.code, "AUTHORITY_GENERATION_DIVERGED")

    def test_state_token_and_mirror_divergence_fail_closed(self):
        self._add_state()
        locked = self._lock()
        locked.token.semantic_state_hash = b"x" * 32
        db.session.commit()
        with self.assertRaises(StudyAuthorityFenceError) as hash_failure:
            self._lock()
        self.assertEqual(hash_failure.exception.code, "AUTHORITY_STATE_DIVERGED")
        db.session.rollback()

        token = db.session.get(type(locked.token), self.subject_id)
        token.semantic_state_hash = _mapped_state().semantic_state_hash
        state = db.session.get(StudyProgressState, self.subject_id)
        state.mirror_revision = 2
        db.session.commit()
        with self.assertRaises(StudyAuthorityFenceError) as revision_failure:
            self._lock()
        self.assertEqual(revision_failure.exception.code, "AUTHORITY_STATE_DIVERGED")

    def test_each_cas_component_has_a_distinct_conflict(self):
        mapped = self._add_state()
        locked = self._lock()
        cases = (
            ({"enrollment_epoch": 4}, "AUTHORITY_EPOCH_CONFLICT"),
            ({"subject_generation": 2}, "SUBJECT_GENERATION_CONFLICT"),
            ({"authority_revision": 1}, "AUTHORITY_REVISION_CONFLICT"),
            ({"semantic_state_hash": b"z" * 32}, "AUTHORITY_STATE_CONFLICT"),
        )
        for overrides, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(StudyAuthorityCASError) as failure:
                    verify_study_authority_cas(
                        route=self._route(),
                        locked=locked,
                        expected=self._expected(mapped, **overrides),
                    )
                self.assertEqual(failure.exception.code, code)

    def test_mode_and_exact_decoder_fail_closed(self):
        mapped = self._add_state()
        locked = self._lock()
        with self.assertRaises(StudyAuthorityCASError) as mode_failure:
            verify_study_authority_cas(
                route=self._route(mode="LEGACY"),
                locked=locked,
                expected=self._expected(mapped),
            )
        self.assertEqual(mode_failure.exception.code, "AUTHORITY_MODE_CONFLICT")

        checked = verify_study_authority_cas(
            route=self._route(mode="LEGACY"),
            locked=locked,
            expected=self._expected(mapped),
            require_note_authority=False,
        )
        self.assertTrue(checked.has_current_state)

        locked.state.algorithm_version = "unregistered"
        with self.assertRaises(StudyAuthorityCASError) as decoder_failure:
            verify_study_authority_cas(
                route=self._route(),
                locked=locked,
                expected=self._expected(mapped),
            )
        self.assertEqual(decoder_failure.exception.code, "STATE_DECODER_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
