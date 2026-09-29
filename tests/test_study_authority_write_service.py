"""P5-04 inert material-write contract for future NOTE authority."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
import unittest

import sqlalchemy as sa

from app import create_app
from app.repositories.study_authority_repository import (
    StudyAuthorityRoute,
    lock_study_authority_siblings,
    lock_study_authority_subject,
)
from app.services.study_authority_cas_service import StudyAuthorityCASExpectation
from app.services.study_authority_projection_encoder import (
    LegacyProjectionMetadata,
    LegacySiblingBaseline,
    encode_note_state_to_legacy_cards,
)
from app.services.study_authority_write_service import (
    StudyAuthorityStateWrite,
    StudyAuthorityWriteError,
    apply_study_authority_material_write,
)
from app.services.study_progress_shadow_codec import serialize_raw_card_progress
from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User


CREATED_AT = datetime(2026, 9, 21, 1, 0, 0)
PROJECTED_AT = datetime(2026, 9, 21, 3, 4, 5)
DUE_AT = datetime(2026, 9, 25, 4, 0, 0)
LAST_REVIEWED_AT = datetime(2026, 9, 21, 3, 0, 0)


def _new_progress(*, user_id: int, card_id: str) -> CardProgress:
    return CardProgress(
        user_id=user_id,
        card_id=card_id,
        queue="new",
        step_index=0,
        due_at=None,
        due_day=None,
        interval_days=0,
        interval_days_raw=0.0,
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
        reps=0,
        lapses=0,
        last_reviewed_at=None,
        revision=0,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _target_state(*, user_id: int) -> MappedCardProgress:
    target = SimpleNamespace(
        id=999999,
        user_id=user_id,
        card_id="state-only",
        queue="review",
        step_index=0,
        due_at=DUE_AT,
        due_day=20722,
        interval_days=4,
        interval_days_raw=4.0,
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
        reps=1,
        lapses=0,
        last_reviewed_at=LAST_REVIEWED_AT,
        revision=1,
        created_at=CREATED_AT,
        updated_at=PROJECTED_AT,
    )
    mapped = map_card_progress(target, card_created_at=CREATED_AT)
    assert isinstance(mapped, MappedCardProgress)
    return mapped


class StudyAuthorityWriteServiceTests(unittest.TestCase):
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

        user = User(email="authority-write@example.test", username="authority-write")
        db.session.add(user)
        db.session.flush()
        self.user_id = int(user.id)
        note_type = NoteType(user_id=self.user_id, name="Authority write")
        templates = (
            Template(note_type=note_type, name="A", position=0),
            Template(note_type=note_type, name="B", position=1),
        )
        deck = Deck(
            owner_user_id=self.user_id,
            note_type=note_type,
            name="Authority write",
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
        note = Note(
            note_type=note_type,
            user_id=self.user_id,
            field_values={"Front": "write"},
            tags=[],
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
        cards = (
            Card(
                note=note,
                template=templates[0],
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
            ),
            Card(
                note=note,
                template=templates[1],
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
            ),
        )
        db.session.add_all([note_type, *templates, deck, note, *cards])
        db.session.flush()
        note.deck_id = int(deck.id)
        progress_rows = tuple(
            _new_progress(user_id=self.user_id, card_id=str(card.id))
            for card in cards
        )
        db.session.add_all(progress_rows)
        db.session.flush()
        initial = map_card_progress(progress_rows[0], card_created_at=cards[0].created_at)
        assert isinstance(initial, MappedCardProgress)
        self.initial_semantic_hash = initial.semantic_state_hash
        subject = StudyProgressSubject(
            learner_user_id=self.user_id,
            logical_note_key=str(note.id).encode("utf-8"),
            live_note_id=str(note.id),
            subject_generation=1,
            mirror_revision=5,
            status_code="MIRRORED_EQUIVALENT_FANIN",
            contributor_count=2,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
        db.session.add(subject)
        db.session.flush()
        db.session.add(
            StudyProgressState(
                subject_id=int(subject.id),
                subject_generation=1,
                mirror_revision=5,
                algorithm_key=initial.algorithm_key,
                algorithm_version=initial.algorithm_version,
                state_schema_version=initial.state_schema_version,
                storage_codec=initial.storage_codec,
                state_payload=initial.state.payload,
                state_payload_size=initial.state.size,
                algorithm_state_hash=initial.algorithm_state_hash,
                semantic_state_hash=initial.semantic_state_hash,
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
            )
        )
        db.session.commit()
        self.subject_id = int(subject.id)
        self.card_ids = tuple(sorted(str(card.id) for card in cards))

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _route(self) -> StudyAuthorityRoute:
        return StudyAuthorityRoute(
            learner_user_id=self.user_id,
            mode_code="NOTE",
            epoch=3,
            persisted=True,
        )

    def _locked(self):
        subject = db.session.execute(
            sa.select(StudyProgressSubject)
            .where(StudyProgressSubject.id == self.subject_id)
            .with_for_update()
        ).scalar_one()
        return lock_study_authority_subject(
            db.session,
            route=self._route(),
            subject=subject,
            now_utc=PROJECTED_AT,
        )

    def _siblings(self, locked):
        return lock_study_authority_siblings(
            db.session,
            route=self._route(),
            locked=locked,
            requested_card_id=self.card_ids[0],
        )

    def _rows(self) -> dict[str, CardProgress]:
        rows = db.session.execute(
            sa.select(CardProgress).where(
                CardProgress.user_id == self.user_id,
                CardProgress.card_id.in_(self.card_ids),
            )
        ).scalars()
        return {str(row.card_id): row for row in rows}

    def _projection(self, rows: dict[str, CardProgress]):
        target = _target_state(user_id=self.user_id)
        card_created = {
            str(card.id): card.created_at
            for card in db.session.execute(
                sa.select(Card).where(Card.id.in_(self.card_ids))
            ).scalars()
        }
        baselines = []
        for card_id in self.card_ids:
            row = rows[card_id]
            raw = serialize_raw_card_progress(row)
            baselines.append(
                LegacySiblingBaseline(
                    card_id=card_id,
                    expected_base_revision=int(row.revision),
                    card_created_at=card_created[card_id],
                    raw_payload=raw.payload,
                    raw_payload_size=raw.size,
                    raw_payload_hash=raw.digest,
                    projected_last_review_event_id=row.last_review_event_id,
                )
            )
        projection = encode_note_state_to_legacy_cards(
            expected_learner_user_id=self.user_id,
            algorithm_key=target.algorithm_key,
            algorithm_version=target.algorithm_version,
            state_schema_version=target.state_schema_version,
            storage_codec=target.storage_codec,
            state_payload=target.state.payload,
            expected_state_payload_size=target.state.size,
            expected_algorithm_state_hash=target.algorithm_state_hash,
            metadata=LegacyProjectionMetadata(
                interval_days_rounded=4,
                is_buried=False,
                buried_until_day=None,
                last_leech_at=None,
                last_leech_lapses=0,
                projected_at=PROJECTED_AT,
            ),
            siblings=tuple(baselines),
        )
        state_write = StudyAuthorityStateWrite(
            algorithm_key=target.algorithm_key,
            algorithm_version=target.algorithm_version,
            state_schema_version=target.state_schema_version,
            storage_codec=target.storage_codec,
            state_payload=target.state.payload,
            state_payload_size=target.state.size,
            algorithm_state_hash=target.algorithm_state_hash,
        )
        return target, projection, state_write

    def _apply(self):
        locked = self._locked()
        siblings = self._siblings(locked)
        rows = dict(siblings.progress_by_card_id)
        target, projection, state_write = self._projection(rows)
        result = apply_study_authority_material_write(
            db.session,
            route=self._route(),
            locked=locked,
            expected=StudyAuthorityCASExpectation(
                enrollment_epoch=3,
                subject_generation=1,
                authority_revision=int(locked.token.authority_revision),
                semantic_state_hash=locked.token.semantic_state_hash,
            ),
            next_state=state_write,
            siblings=siblings,
            projection=projection,
            now_utc=PROJECTED_AT,
        )
        return target, projection, result

    def test_material_write_stages_all_rows_and_outer_rollback_restores_them(self):
        target, projection, result = self._apply()
        self.assertEqual(result.authority_revision, 1)
        self.assertEqual(result.semantic_state_hash, target.semantic_state_hash)
        self.assertEqual(len(result.projected_progress), 2)
        db.session.flush()
        for sibling in projection.siblings:
            self.assertEqual(
                serialize_raw_card_progress(
                    db.session.execute(
                        sa.select(CardProgress).where(
                            CardProgress.card_id == sibling.card_id
                        )
                    ).scalar_one()
                ).digest,
                sibling.raw.digest,
            )

        db.session.rollback()
        state = db.session.get(StudyProgressState, self.subject_id)
        self.assertEqual(state.semantic_state_hash, self.initial_semantic_hash)
        self.assertIsNone(db.session.get(StudyAuthoritySubjectToken, self.subject_id))
        for row in self._rows().values():
            self.assertEqual(row.revision, 0)
            self.assertEqual(row.queue, "new")

    def test_outer_commit_persists_exact_state_token_and_projection(self):
        target, projection, result = self._apply()
        db.session.commit()
        db.session.expire_all()

        state = db.session.get(StudyProgressState, self.subject_id)
        token = db.session.get(StudyAuthoritySubjectToken, self.subject_id)
        subject = db.session.get(StudyProgressSubject, self.subject_id)
        self.assertEqual(token.authority_revision, 1)
        self.assertEqual(token.semantic_state_hash, target.semantic_state_hash)
        self.assertEqual(state.algorithm_state_hash, target.algorithm_state_hash)
        self.assertEqual(state.semantic_state_hash, target.semantic_state_hash)
        self.assertEqual(state.mirror_revision, subject.mirror_revision)
        self.assertEqual(subject.mirror_revision, 5)
        self.assertEqual(result.authority_revision, 1)
        for sibling in projection.siblings:
            row = db.session.execute(
                sa.select(CardProgress).where(CardProgress.card_id == sibling.card_id)
            ).scalar_one()
            self.assertEqual(serialize_raw_card_progress(row).digest, sibling.raw.digest)

    def test_stale_or_incomplete_projection_fails_before_any_sibling_mutation(self):
        locked = self._locked()
        siblings = self._siblings(locked)
        rows = dict(siblings.progress_by_card_id)
        _target, projection, state_write = self._projection(rows)
        rows[self.card_ids[-1]].queue = "learning"
        with self.assertRaises(StudyAuthorityWriteError) as stale:
            apply_study_authority_material_write(
                db.session,
                route=self._route(),
                locked=locked,
                expected=StudyAuthorityCASExpectation(
                    3, 1, 0, locked.token.semantic_state_hash
                ),
                next_state=state_write,
                siblings=siblings,
                projection=projection,
                now_utc=PROJECTED_AT,
            )
        self.assertEqual(stale.exception.code, "STALE_LEGACY_BASELINE")
        self.assertEqual(rows[self.card_ids[0]].revision, 0)
        self.assertEqual(locked.token.authority_revision, 0)
        db.session.rollback()

        locked = self._locked()
        siblings = self._siblings(locked)
        rows = dict(siblings.progress_by_card_id)
        _target, projection, state_write = self._projection(rows)
        incomplete_projection = replace(
            projection,
            siblings=projection.siblings[:1],
        )
        with self.assertRaises(StudyAuthorityWriteError) as incomplete:
            apply_study_authority_material_write(
                db.session,
                route=self._route(),
                locked=locked,
                expected=StudyAuthorityCASExpectation(
                    3, 1, 0, locked.token.semantic_state_hash
                ),
                next_state=state_write,
                siblings=siblings,
                projection=incomplete_projection,
                now_utc=PROJECTED_AT,
            )
        self.assertEqual(incomplete.exception.code, "INCOMPLETE_LEGACY_PROJECTION")

    def test_same_semantic_state_is_a_noop_not_a_revision_advance(self):
        target, _projection, _result = self._apply()
        db.session.commit()

        locked = self._locked()
        siblings = self._siblings(locked)
        rows = dict(siblings.progress_by_card_id)
        _target, projection, state_write = self._projection(rows)
        with self.assertRaises(StudyAuthorityWriteError) as unchanged:
            apply_study_authority_material_write(
                db.session,
                route=self._route(),
                locked=locked,
                expected=StudyAuthorityCASExpectation(
                    3, 1, 1, target.semantic_state_hash
                ),
                next_state=state_write,
                siblings=siblings,
                projection=projection,
                now_utc=PROJECTED_AT,
            )
        self.assertEqual(unchanged.exception.code, "NON_MATERIAL_AUTHORITY_WRITE")
        self.assertEqual(locked.token.authority_revision, 1)
        self.assertTrue(all(row.revision == 1 for row in rows.values()))

    def test_first_state_is_rejected_until_contributor_command_exists(self):
        state = db.session.get(StudyProgressState, self.subject_id)
        db.session.delete(state)
        db.session.commit()

        locked = self._locked()
        siblings = self._siblings(locked)
        rows = dict(siblings.progress_by_card_id)
        _target, projection, state_write = self._projection(rows)
        with self.assertRaises(StudyAuthorityWriteError) as missing_state:
            apply_study_authority_material_write(
                db.session,
                route=self._route(),
                locked=locked,
                expected=StudyAuthorityCASExpectation(3, 1, 0, None),
                next_state=state_write,
                siblings=siblings,
                projection=projection,
                now_utc=PROJECTED_AT,
            )
        self.assertEqual(missing_state.exception.code, "AUTHORITY_STATE_REQUIRED")
        self.assertEqual(locked.token.authority_revision, 0)
        self.assertTrue(all(row.revision == 0 for row in rows.values()))


if __name__ == "__main__":
    unittest.main()
