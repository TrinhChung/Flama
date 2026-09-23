"""P5-04 inert compatibility-lock and native history append contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sqlalchemy as sa

from app import create_app
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    StudyAuthorityRoute,
    lock_study_authority_compatibility,
    lock_study_authority_siblings,
    lock_study_authority_subject,
)
from app.services.study_authority_cas_service import StudyAuthorityCASExpectation
from app.services.study_authority_command_service import (
    ExistingStateNoteReviewCommand,
    StudyAuthorityCommandError,
    apply_existing_state_note_review,
)
from app.services.study_authority_evidence_service import (
    StudyAuthorityEvidenceError,
    finalize_study_authority_evidence,
)
from app.services.study_authority_projection_encoder import (
    LegacyProjectionMetadata,
    LegacySiblingBaseline,
    encode_note_state_to_legacy_cards,
)
from app.services.study_authority_receipt_service import (
    IdempotentExistingStateNoteReviewCommand,
    StudyAuthorityReceiptError,
    apply_idempotent_existing_state_note_review,
)
from app.services.study_authority_write_service import (
    StudyAuthorityStateWrite,
    apply_study_authority_material_write,
)
from app.services.study_progress_contract import MAPPER_VERSION
from app.services.study_progress_shadow_codec import (
    STATE_DECODERS,
    serialize_raw_card_progress,
)
from app.services.study_progress_history_service import (
    NativeHistoryFactInput,
    StudyProgressHistoryError,
    append_native_history_fact,
)
from app.services.study_progress_reconciliation_service import (
    build_study_progress_reconciliation,
)
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    map_card_progress,
)
from app.services.study_service import (
    NativeReviewMutationInput,
    NativeReviewProgressInput,
    NativeReviewProvenance,
    NativeReviewTransitionInput,
    execute_native_review_transition,
)
from app.services.anki_scheduler import default_deck_options
from app.validators.review_event import build_native_review_event_payload
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lineage_ref import StudyProgressLineageRef
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User


CREATED_AT = datetime(2026, 9, 21, 1, 0, 0)
REVIEWED_AT = datetime(2026, 9, 21, 2, 0, 0)
INGESTED_AT = datetime(2026, 9, 21, 2, 0, 1)
CONFIG_HASH = "11" * 32
BEFORE_HASH = b"\x22" * 32
AFTER_HASH = b"\x33" * 32
TARGET_DUE_AT = datetime(2026, 9, 22, 2, 0, 0)


class StudyAuthorityHistoryTests(unittest.TestCase):
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

        user = User(email="authority-history@example.test", username="authority-history")
        db.session.add(user)
        db.session.flush()
        self.user_id = int(user.id)
        note_type = NoteType(user_id=self.user_id, name="Authority history")
        templates = (
            Template(note_type=note_type, name="Card A", position=0),
            Template(note_type=note_type, name="Card B", position=1),
        )
        deck = Deck(
            owner_user_id=self.user_id,
            note_type=note_type,
            name="Authority history",
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
        note = Note(
            note_type=note_type,
            user_id=self.user_id,
            field_values={"Front": "history"},
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
            CardProgress(
                user_id=self.user_id,
                card_id=str(card.id),
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
            for card in cards
        )
        db.session.add_all(progress_rows)
        db.session.flush()
        mapped_by_card_id = {}
        for card, progress in zip(cards, progress_rows, strict=True):
            mapped = map_card_progress(progress, card_created_at=card.created_at)
            assert isinstance(mapped, MappedCardProgress)
            mapped_by_card_id[str(card.id)] = mapped
        first_mapped = mapped_by_card_id[str(cards[0].id)]
        subject = StudyProgressSubject(
            learner_user_id=self.user_id,
            logical_note_key=str(note.id).encode("utf-8"),
            live_note_id=str(note.id),
            subject_generation=1,
            mirror_revision=1,
            status_code="MIRRORED_EQUIVALENT_FANIN",
            contributor_count=2,
            mapper_version=MAPPER_VERSION,
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )
        db.session.add(subject)
        db.session.flush()
        contributors = tuple(
            StudyProgressContributor(
                subject_id=int(subject.id),
                subject_generation=1,
                source_progress_id=int(progress.id),
                live_card_progress_id=int(progress.id),
                logical_card_key=str(card.id).encode("utf-8"),
                live_card_id=str(card.id),
                card_progress_revision=0,
                raw_schema_version=mapped_by_card_id[str(card.id)].raw_schema_version,
                storage_codec=mapped_by_card_id[str(card.id)].storage_codec,
                raw_payload=mapped_by_card_id[str(card.id)].raw.payload,
                raw_payload_size=mapped_by_card_id[str(card.id)].raw.size,
                raw_progress_hash=mapped_by_card_id[str(card.id)].raw.digest,
                pointer_status="ABSENT",
                history_completeness_code="HISTORY_NATIVE_COMPLETE",
                current_provenance_code="UNKNOWN_LEGACY",
                lineage_vector_hash=b"\x44" * 32,
                contributor_status="ACTIVE",
                created_at=CREATED_AT,
                updated_at=CREATED_AT,
            )
            for card, progress in zip(cards, progress_rows, strict=True)
        )
        db.session.add_all(contributors)
        db.session.flush()
        availability_rows = []
        for card, contributor in zip(cards, contributors, strict=True):
            availability = mapped_by_card_id[str(card.id)].availability
            availability_rows.append(
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
                    created_at=CREATED_AT,
                    updated_at=CREATED_AT,
                )
            )
        db.session.add_all(
            [
                StudyProgressState(
                    subject_id=int(subject.id),
                    subject_generation=1,
                    mirror_revision=1,
                    algorithm_key=first_mapped.algorithm_key,
                    algorithm_version=first_mapped.algorithm_version,
                    state_schema_version=first_mapped.state_schema_version,
                    storage_codec=first_mapped.storage_codec,
                    state_payload=first_mapped.state.payload,
                    state_payload_size=first_mapped.state.size,
                    algorithm_state_hash=first_mapped.algorithm_state_hash,
                    semantic_state_hash=first_mapped.semantic_state_hash,
                    created_at=CREATED_AT,
                    updated_at=CREATED_AT,
                ),
                *availability_rows,
            ]
        )
        db.session.commit()
        self.subject_id = int(subject.id)
        self.card_ids = tuple(sorted(str(card.id) for card in cards))
        self.card_id = self.card_ids[0]
        self.contributor_id_by_card = {
            str(card.id): int(contributor.id)
            for card, contributor in zip(cards, contributors, strict=True)
        }

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _route(self) -> StudyAuthorityRoute:
        return StudyAuthorityRoute(self.user_id, "NOTE", 7, True)

    def _locked_context(self):
        subject = db.session.execute(
            sa.select(StudyProgressSubject)
            .where(StudyProgressSubject.id == self.subject_id)
            .with_for_update()
        ).scalar_one()
        locked = lock_study_authority_subject(
            db.session,
            route=self._route(),
            subject=subject,
            now_utc=INGESTED_AT,
        )
        siblings = lock_study_authority_siblings(
            db.session,
            route=self._route(),
            locked=locked,
            requested_card_id=self.card_id,
        )
        compatibility = lock_study_authority_compatibility(
            db.session,
            route=self._route(),
            locked=locked,
            siblings=siblings,
        )
        return locked, siblings, compatibility

    def _event(self) -> ReviewEvent:
        payload_json = build_native_review_event_payload(
            source_path="native.rest",
            runtime={
                "action_key": "review.good",
                "action_contract_version": "1",
                "trigger_key": "scheduler.review.good",
                "trigger_contract_version": "1",
                "algorithm_key": "legacy-anki",
                "algorithm_version": "1.0.0",
                "state_schema_version": "anki-card-state.v1",
            },
            scheduler_config_hash=CONFIG_HASH,
            request_id="authority-history-request",
        )
        event = ReviewEvent(
            user_id=self.user_id,
            card_id=self.card_id,
            scheduler_algorithm="legacy-anki",
            algorithm_version="1.0.0",
            scheduler_config_hash=CONFIG_HASH,
            reviewed_at=REVIEWED_AT,
            rating="good",
            mode="deck",
            scheduler_mode="legacy",
            review_kind="review",
            queue_before="new",
            queue_after="review",
            interval_days_before=0.0,
            interval_days_after=1.0,
            ease_factor_before=2.5,
            ease_factor_after=2.5,
            leeched_after=False,
            suspended_after=False,
            payload_json=payload_json,
            created_at=REVIEWED_AT,
        )
        db.session.add(event)
        db.session.flush()
        return event

    def _target_state(self) -> MappedCardProgress:
        target = SimpleNamespace(
            id=999999,
            user_id=self.user_id,
            card_id="state-only",
            queue="review",
            step_index=0,
            due_at=TARGET_DUE_AT,
            due_day=20722,
            interval_days=1,
            interval_days_raw=1.0,
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
            last_reviewed_at=REVIEWED_AT,
            revision=1,
            created_at=CREATED_AT,
            updated_at=INGESTED_AT,
        )
        mapped = map_card_progress(target, card_created_at=CREATED_AT)
        assert isinstance(mapped, MappedCardProgress)
        return mapped

    def _existing_state_command(self) -> ExistingStateNoteReviewCommand:
        locked, siblings, compatibility = self._locked_context()
        state = locked.state
        assert state is not None
        current_state = STATE_DECODERS.decode(
            algorithm_key=str(state.algorithm_key),
            algorithm_version=str(state.algorithm_version),
            state_schema_version=str(state.state_schema_version),
            storage_codec=str(state.storage_codec),
            payload=state.state_payload,
            expected_size=int(state.state_payload_size),
            expected_hash=bytes(state.algorithm_state_hash),
        )
        options = default_deck_options()
        transition = execute_native_review_transition(
            NativeReviewTransitionInput(
                state=current_state,
                deck_options=options,
                reviewed_at=REVIEWED_AT,
                action="good",
                timezone_name="UTC",
            )
        )
        card = next(card for card in siblings.cards if str(card.id) == self.card_id)
        review = NativeReviewMutationInput(
            user_id=self.user_id,
            card=card,
            current_state=current_state,
            transition=transition,
            reviewed_at=REVIEWED_AT,
            duration_ms=420,
            payload=None,
            local_deck_id=int(card.note.deck_id),
            scheduler_preset_id=None,
            scheduler_config_hash=CONFIG_HASH,
            timezone_name="UTC",
            deck_options=options,
            review_mode="deck",
            provenance=NativeReviewProvenance(
                source_path="native.rest",
                request_id="authority-command-request",
            ),
        )
        return ExistingStateNoteReviewCommand(
            route=self._route(),
            locked=locked,
            expected=StudyAuthorityCASExpectation(
                enrollment_epoch=7,
                subject_generation=1,
                authority_revision=0,
                semantic_state_hash=bytes(locked.token.semantic_state_hash),
            ),
            siblings=siblings,
            compatibility=compatibility,
            review=review,
            now_utc=INGESTED_AT,
        )

    def _relock_existing_state_command(
        self,
        original: ExistingStateNoteReviewCommand,
    ) -> ExistingStateNoteReviewCommand:
        locked, siblings, compatibility = self._locked_context()
        card = next(
            card for card in siblings.cards if str(card.id) == self.card_id
        )
        return replace(
            original,
            locked=locked,
            siblings=siblings,
            compatibility=compatibility,
            review=replace(original.review, card=card),
        )

    def _material_write(self, *, point_reviewed_card: bool = True):
        locked, siblings, compatibility = self._locked_context()
        before_hash = bytes(locked.token.semantic_state_hash)
        event = self._event()
        target = self._target_state()
        card_created_at = {str(card.id): card.created_at for card in siblings.cards}
        baselines = []
        for card_id in siblings.card_ids:
            progress = siblings.progress_by_card_id[card_id]
            raw = serialize_raw_card_progress(progress)
            baselines.append(
                LegacySiblingBaseline(
                    card_id=card_id,
                    expected_base_revision=int(progress.revision),
                    card_created_at=card_created_at[card_id],
                    raw_payload=raw.payload,
                    raw_payload_size=raw.size,
                    raw_payload_hash=raw.digest,
                    projected_last_review_event_id=(
                        int(event.id)
                        if point_reviewed_card and card_id == self.card_id
                        else progress.last_review_event_id
                    ),
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
                interval_days_rounded=1,
                is_buried=False,
                buried_until_day=None,
                last_leech_at=None,
                last_leech_lapses=0,
                projected_at=INGESTED_AT,
            ),
            siblings=tuple(baselines),
        )
        write_result = apply_study_authority_material_write(
            db.session,
            route=self._route(),
            locked=locked,
            expected=StudyAuthorityCASExpectation(
                enrollment_epoch=7,
                subject_generation=1,
                authority_revision=0,
                semantic_state_hash=before_hash,
            ),
            next_state=StudyAuthorityStateWrite(
                algorithm_key=target.algorithm_key,
                algorithm_version=target.algorithm_version,
                state_schema_version=target.state_schema_version,
                storage_codec=target.storage_codec,
                state_payload=target.state.payload,
                state_payload_size=target.state.size,
                algorithm_state_hash=target.algorithm_state_hash,
            ),
            siblings=siblings,
            projection=projection,
            now_utc=INGESTED_AT,
        )
        return (
            locked,
            siblings,
            compatibility,
            event,
            target,
            write_result,
            before_hash,
        )

    def test_complete_compatibility_vector_and_exact_history_replay(self):
        _locked, _siblings, compatibility = self._locked_context()
        self.assertEqual(
            tuple(sorted(compatibility.contributor_by_card_id)), self.card_ids
        )
        event = self._event()
        command = NativeHistoryFactInput(
            learner_user_id=self.user_id,
            subject=db.session.get(StudyProgressSubject, self.subject_id),
            contributor=compatibility.contributor_by_card_id[self.card_id],
            review_event=event,
            history_completeness_code="HISTORY_NATIVE_COMPLETE",
            before_state_hash=BEFORE_HASH,
            after_state_hash=AFTER_HASH,
        )
        inserted = append_native_history_fact(
            db.session, command=command, now_utc=INGESTED_AT
        )
        self.assertTrue(inserted.inserted)
        db.session.flush()
        replayed = append_native_history_fact(
            db.session, command=command, now_utc=INGESTED_AT
        )
        self.assertFalse(replayed.inserted)
        self.assertEqual(replayed.fact.id, inserted.fact.id)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 1)
        self.assertEqual(bytes(inserted.fact.before_state_hash), BEFORE_HASH)
        self.assertEqual(bytes(inserted.fact.after_state_hash), AFTER_HASH)
        self.assertEqual(inserted.fact.provenance_code, "NATIVE_DIRECT")

    def test_history_replay_with_different_state_hash_fails_closed(self):
        _locked, _siblings, compatibility = self._locked_context()
        event = self._event()
        base = NativeHistoryFactInput(
            learner_user_id=self.user_id,
            subject=db.session.get(StudyProgressSubject, self.subject_id),
            contributor=compatibility.contributor_by_card_id[self.card_id],
            review_event=event,
            history_completeness_code="HISTORY_NATIVE_COMPLETE",
            before_state_hash=BEFORE_HASH,
            after_state_hash=AFTER_HASH,
        )
        append_native_history_fact(db.session, command=base, now_utc=INGESTED_AT)
        db.session.flush()
        divergent = NativeHistoryFactInput(
            **{
                **base.__dict__,
                "after_state_hash": b"\x55" * 32,
            }
        )
        with self.assertRaises(StudyProgressHistoryError) as conflict:
            append_native_history_fact(
                db.session, command=divergent, now_utc=INGESTED_AT
            )
        self.assertEqual(conflict.exception.code, "HISTORY_IDENTITY_REUSED")

    def test_history_replay_rejects_corrupt_persisted_payload(self):
        _locked, _siblings, compatibility = self._locked_context()
        event = self._event()
        command = NativeHistoryFactInput(
            learner_user_id=self.user_id,
            subject=db.session.get(StudyProgressSubject, self.subject_id),
            contributor=compatibility.contributor_by_card_id[self.card_id],
            review_event=event,
            history_completeness_code="HISTORY_NATIVE_COMPLETE",
            before_state_hash=BEFORE_HASH,
            after_state_hash=AFTER_HASH,
        )
        inserted = append_native_history_fact(
            db.session, command=command, now_utc=INGESTED_AT
        )
        db.session.flush()
        inserted.fact.fact_payload = {"rating": "tampered"}
        with self.assertRaises(StudyProgressHistoryError) as conflict:
            append_native_history_fact(
                db.session, command=command, now_utc=INGESTED_AT
            )
        self.assertEqual(conflict.exception.code, "CORRUPT_HISTORY_FACT")

    def test_note_authority_history_requires_scheduler_grade_hashes(self):
        _locked, _siblings, compatibility = self._locked_context()
        event = self._event()
        base = NativeHistoryFactInput(
            learner_user_id=self.user_id,
            subject=db.session.get(StudyProgressSubject, self.subject_id),
            contributor=compatibility.contributor_by_card_id[self.card_id],
            review_event=event,
            history_completeness_code="HISTORY_NATIVE_COMPLETE",
            before_state_hash=BEFORE_HASH,
            after_state_hash=AFTER_HASH,
            require_scheduler_grade=True,
        )
        with self.assertRaises(StudyProgressHistoryError) as missing:
            append_native_history_fact(
                db.session,
                command=replace(base, before_state_hash=None),
                now_utc=INGESTED_AT,
            )
        self.assertEqual(missing.exception.code, "INCOMPLETE_SCHEDULER_HISTORY")
        self.assertEqual(StudyProgressHistoryFact.query.count(), 0)

        result = append_native_history_fact(
            db.session, command=base, now_utc=INGESTED_AT
        )
        self.assertTrue(result.inserted)

    def test_missing_availability_fails_before_history_append(self):
        db.session.execute(
            sa.delete(StudyProgressAvailability).where(
                StudyProgressAvailability.contributor_id
                == self.contributor_id_by_card[self.card_id]
            )
        )
        db.session.commit()
        subject = db.session.execute(
            sa.select(StudyProgressSubject)
            .where(StudyProgressSubject.id == self.subject_id)
            .with_for_update()
        ).scalar_one()
        locked = lock_study_authority_subject(
            db.session,
            route=self._route(),
            subject=subject,
            now_utc=INGESTED_AT,
        )
        siblings = lock_study_authority_siblings(
            db.session,
            route=self._route(),
            locked=locked,
            requested_card_id=self.card_id,
        )
        with self.assertRaises(StudyAuthorityFenceError) as missing:
            lock_study_authority_compatibility(
                db.session,
                route=self._route(),
                locked=locked,
                siblings=siblings,
            )
        self.assertEqual(
            missing.exception.code, "INCOMPLETE_AUTHORITY_COMPATIBILITY"
        )
        self.assertEqual(StudyProgressHistoryFact.query.count(), 0)

    def test_stale_contributor_baseline_fails_before_material_write(self):
        contributor = db.session.get(
            StudyProgressContributor,
            self.contributor_id_by_card[self.card_id],
        )
        contributor.raw_progress_hash = b"\x77" * 32
        db.session.commit()
        subject = db.session.execute(
            sa.select(StudyProgressSubject)
            .where(StudyProgressSubject.id == self.subject_id)
            .with_for_update()
        ).scalar_one()
        locked = lock_study_authority_subject(
            db.session,
            route=self._route(),
            subject=subject,
            now_utc=INGESTED_AT,
        )
        siblings = lock_study_authority_siblings(
            db.session,
            route=self._route(),
            locked=locked,
            requested_card_id=self.card_id,
        )
        with self.assertRaises(StudyAuthorityFenceError) as stale:
            lock_study_authority_compatibility(
                db.session,
                route=self._route(),
                locked=locked,
                siblings=siblings,
            )
        self.assertEqual(stale.exception.code, "STALE_AUTHORITY_COMPATIBILITY")
        self.assertTrue(
            all(
                row.revision == 0
                for row in siblings.progress_by_card_id.values()
            )
        )

    def test_outer_rollback_removes_staged_history_fact(self):
        _locked, _siblings, compatibility = self._locked_context()
        event = self._event()
        append_native_history_fact(
            db.session,
            command=NativeHistoryFactInput(
                learner_user_id=self.user_id,
                subject=db.session.get(StudyProgressSubject, self.subject_id),
                contributor=compatibility.contributor_by_card_id[self.card_id],
                review_event=event,
                history_completeness_code="HISTORY_NATIVE_COMPLETE",
                before_state_hash=BEFORE_HASH,
                after_state_hash=AFTER_HASH,
            ),
            now_utc=INGESTED_AT,
        )
        db.session.flush()
        self.assertEqual(StudyProgressHistoryFact.query.count(), 1)
        db.session.rollback()
        self.assertEqual(StudyProgressHistoryFact.query.count(), 0)
        self.assertEqual(ReviewEvent.query.count(), 0)

    def test_material_write_evidence_and_history_stage_one_atomic_unit(self):
        (
            locked,
            siblings,
            compatibility,
            event,
            target,
            write_result,
            before_hash,
        ) = self._material_write()
        evidence = finalize_study_authority_evidence(
            db.session,
            route=self._route(),
            locked=locked,
            siblings=siblings,
            compatibility=compatibility,
            write_result=write_result,
            review_event=event,
            now_utc=INGESTED_AT,
        )
        history = append_native_history_fact(
            db.session,
            command=NativeHistoryFactInput(
                learner_user_id=self.user_id,
                subject=locked.subject,
                contributor=evidence.contributor_by_card_id[self.card_id],
                review_event=event,
                history_completeness_code="HISTORY_NATIVE_COMPLETE",
                before_state_hash=before_hash,
                after_state_hash=write_result.semantic_state_hash,
            ),
            now_utc=INGESTED_AT,
        )
        db.session.flush()

        self.assertEqual(write_result.authority_revision, 1)
        self.assertEqual(evidence.mirror_revision, 2)
        self.assertEqual(locked.subject.mirror_revision, 2)
        self.assertEqual(locked.state.mirror_revision, 2)
        self.assertEqual(locked.token.authority_revision, 1)
        self.assertEqual(
            evidence.subject_status,
            "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE",
        )
        self.assertTrue(history.inserted)
        self.assertEqual(history.fact.contributor_id, self.contributor_id_by_card[self.card_id])
        self.assertEqual(StudyProgressHistoryFact.query.count(), 1)
        self.assertEqual(StudyProgressLineageRef.query.count(), 1)
        for card_id in self.card_ids:
            progress = siblings.progress_by_card_id[card_id]
            contributor = evidence.contributor_by_card_id[card_id]
            availability = compatibility.availability_by_contributor_id[
                int(contributor.id)
            ]
            self.assertEqual(progress.revision, 1)
            self.assertEqual(contributor.card_progress_revision, 1)
            self.assertEqual(
                bytes(contributor.raw_progress_hash),
                serialize_raw_card_progress(progress).digest,
            )
            self.assertEqual(
                bytes(availability.semantic_state_hash), target.semantic_state_hash
            )
        self.assertEqual(
            evidence.contributor_by_card_id[self.card_id].current_provenance_code,
            "NATIVE_DIRECT",
        )
        other_card_id = next(card_id for card_id in self.card_ids if card_id != self.card_id)
        self.assertEqual(
            evidence.contributor_by_card_id[other_card_id].current_provenance_code,
            "UNKNOWN_LEGACY",
        )
        db.session.commit()
        reconciliation = build_study_progress_reconciliation(
            db.session,
            observed_at=INGESTED_AT,
        )
        self.assertEqual(reconciliation["unexplained"]["by_code"], {})

    def test_evidence_failure_requires_outer_rollback_of_material_write(self):
        (
            locked,
            siblings,
            compatibility,
            event,
            _target,
            write_result,
            _before_hash,
        ) = self._material_write(point_reviewed_card=False)
        with self.assertRaises(StudyAuthorityEvidenceError) as mismatch:
            finalize_study_authority_evidence(
                db.session,
                route=self._route(),
                locked=locked,
                siblings=siblings,
                compatibility=compatibility,
                write_result=write_result,
                review_event=event,
                now_utc=INGESTED_AT,
            )
        self.assertEqual(
            mismatch.exception.code, "AUTHORITY_EVENT_POINTER_MISMATCH"
        )
        self.assertEqual(locked.subject.mirror_revision, 1)
        self.assertEqual(locked.token.authority_revision, 1)

        db.session.rollback()
        subject = db.session.get(StudyProgressSubject, self.subject_id)
        self.assertEqual(subject.mirror_revision, 1)
        self.assertEqual(ReviewEvent.query.count(), 0)
        self.assertEqual(StudyProgressLineageRef.query.count(), 0)
        for progress in db.session.execute(
            sa.select(CardProgress).where(CardProgress.card_id.in_(self.card_ids))
        ).scalars():
            self.assertEqual(progress.revision, 0)
            self.assertEqual(progress.queue, "new")

    def test_evidence_finalizer_rejects_second_application(self):
        (
            locked,
            siblings,
            compatibility,
            event,
            _target,
            write_result,
            _before_hash,
        ) = self._material_write()
        finalize_study_authority_evidence(
            db.session,
            route=self._route(),
            locked=locked,
            siblings=siblings,
            compatibility=compatibility,
            write_result=write_result,
            review_event=event,
            now_utc=INGESTED_AT,
        )
        with self.assertRaises(StudyAuthorityEvidenceError) as repeated:
            finalize_study_authority_evidence(
                db.session,
                route=self._route(),
                locked=locked,
                siblings=siblings,
                compatibility=compatibility,
                write_result=write_result,
                review_event=event,
                now_utc=INGESTED_AT,
            )
        self.assertEqual(repeated.exception.code, "STALE_AUTHORITY_EVIDENCE")
        self.assertEqual(locked.subject.mirror_revision, 2)
        db.session.rollback()

    def test_successful_full_unit_outer_rollback_restores_all_evidence(self):
        (
            locked,
            siblings,
            compatibility,
            event,
            _target,
            write_result,
            before_hash,
        ) = self._material_write()
        evidence = finalize_study_authority_evidence(
            db.session,
            route=self._route(),
            locked=locked,
            siblings=siblings,
            compatibility=compatibility,
            write_result=write_result,
            review_event=event,
            now_utc=INGESTED_AT,
        )
        append_native_history_fact(
            db.session,
            command=NativeHistoryFactInput(
                learner_user_id=self.user_id,
                subject=locked.subject,
                contributor=evidence.contributor_by_card_id[self.card_id],
                review_event=event,
                history_completeness_code="HISTORY_NATIVE_COMPLETE",
                before_state_hash=before_hash,
                after_state_hash=write_result.semantic_state_hash,
            ),
            now_utc=INGESTED_AT,
        )
        db.session.flush()
        self.assertEqual(locked.subject.mirror_revision, 2)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 1)

        db.session.rollback()
        subject = db.session.get(StudyProgressSubject, self.subject_id)
        state = db.session.get(StudyProgressState, self.subject_id)
        self.assertEqual(subject.mirror_revision, 1)
        self.assertEqual(state.mirror_revision, 1)
        self.assertEqual(bytes(state.semantic_state_hash), before_hash)
        self.assertEqual(ReviewEvent.query.count(), 0)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 0)
        self.assertEqual(StudyProgressLineageRef.query.count(), 0)
        for progress in db.session.execute(
            sa.select(CardProgress).where(CardProgress.card_id.in_(self.card_ids))
        ).scalars():
            self.assertEqual(progress.revision, 0)
            self.assertEqual(progress.queue, "new")
        for contributor in db.session.execute(
            sa.select(StudyProgressContributor).where(
                StudyProgressContributor.subject_id == self.subject_id
            )
        ).scalars():
            self.assertEqual(contributor.card_progress_revision, 0)
            self.assertEqual(contributor.pointer_status, "ABSENT")

    def test_existing_state_command_stages_canonical_atomic_unit(self):
        command = self._existing_state_command()
        with patch(
            "app.services.study_service._apply_review_side_effects"
        ) as side_effects:
            result = apply_existing_state_note_review(
                db.session,
                command=command,
            )
        db.session.flush()

        side_effects.assert_not_called()
        self.assertEqual(result.review_event.card_id, self.card_id)
        self.assertEqual(result.review_event.rating, "good")
        self.assertEqual(result.write.authority_revision, 1)
        self.assertEqual(result.evidence.mirror_revision, 2)
        self.assertTrue(result.history.inserted)
        self.assertEqual(ReviewEvent.query.count(), 1)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 1)
        for card_id in self.card_ids:
            progress = command.siblings.progress_by_card_id[card_id]
            self.assertEqual(progress.revision, 1)
            self.assertEqual(
                progress.last_review_event_id,
                result.review_event.id if card_id == self.card_id else None,
            )

        db.session.commit()
        reconciliation = build_study_progress_reconciliation(
            db.session,
            observed_at=INGESTED_AT,
        )
        self.assertEqual(reconciliation["unexplained"]["by_code"], {})

    def test_existing_state_command_rejects_legacy_progress_mutation_before_event(self):
        command = self._existing_state_command()
        reviewed_progress = command.siblings.progress_by_card_id[self.card_id]
        invalid_review = replace(
            command.review,
            progress_input=NativeReviewProgressInput(
                progress=reviewed_progress,
                state=command.review.transition.state,
                last_reviewed_at=REVIEWED_AT,
                revision=1,
            ),
        )
        with self.assertRaises(StudyAuthorityCommandError) as rejected:
            apply_existing_state_note_review(
                db.session,
                command=replace(command, review=invalid_review),
            )
        self.assertEqual(
            rejected.exception.code, "LEGACY_PROGRESS_MUTATION_FORBIDDEN"
        )
        self.assertEqual(ReviewEvent.query.count(), 0)
        self.assertTrue(
            all(
                row.revision == 0
                for row in command.siblings.progress_by_card_id.values()
            )
        )
        db.session.rollback()

    def test_existing_state_command_history_failure_is_outer_rollback_safe(self):
        command = self._existing_state_command()
        with patch(
            "app.services.study_authority_command_service.append_native_history_fact",
            side_effect=StudyProgressHistoryError("INJECTED", "history fault"),
        ):
            with self.assertRaises(StudyProgressHistoryError) as fault:
                apply_existing_state_note_review(db.session, command=command)
        self.assertEqual(fault.exception.code, "INJECTED")
        self.assertEqual(command.locked.token.authority_revision, 1)

        db.session.rollback()
        subject = db.session.get(StudyProgressSubject, self.subject_id)
        state = db.session.get(StudyProgressState, self.subject_id)
        self.assertEqual(subject.mirror_revision, 1)
        self.assertEqual(state.mirror_revision, 1)
        self.assertEqual(ReviewEvent.query.count(), 0)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 0)
        self.assertEqual(StudyProgressLineageRef.query.count(), 0)
        for progress in db.session.execute(
            sa.select(CardProgress).where(CardProgress.card_id.in_(self.card_ids))
        ).scalars():
            self.assertEqual(progress.revision, 0)
            self.assertEqual(progress.queue, "new")

    def test_idempotent_command_commits_receipt_and_replays_exact_response(self):
        base = self._existing_state_command()
        first = apply_idempotent_existing_state_note_review(
            db.session,
            command=IdempotentExistingStateNoteReviewCommand(
                operation_key="authority-command-request",
                command=base,
            ),
        )
        self.assertFalse(first.replayed)
        self.assertIsNotNone(first.applied)
        self.assertIsNotNone(first.receipt.id)
        self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)
        response = dict(first.response_payload)
        db.session.commit()

        retry = self._relock_existing_state_command(base)
        replay = apply_idempotent_existing_state_note_review(
            db.session,
            command=IdempotentExistingStateNoteReviewCommand(
                operation_key="authority-command-request",
                command=retry,
            ),
        )
        self.assertTrue(replay.replayed)
        self.assertIsNone(replay.applied)
        self.assertEqual(dict(replay.response_payload), response)
        self.assertEqual(replay.receipt.id, first.receipt.id)
        self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)
        self.assertEqual(ReviewEvent.query.count(), 1)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 1)
        db.session.rollback()

    def test_idempotent_command_rejects_same_key_with_different_request(self):
        base = self._existing_state_command()
        apply_idempotent_existing_state_note_review(
            db.session,
            command=IdempotentExistingStateNoteReviewCommand(
                operation_key="authority-command-request",
                command=base,
            ),
        )
        db.session.commit()

        retry = self._relock_existing_state_command(base)
        divergent = replace(
            retry,
            review=replace(retry.review, duration_ms=421),
        )
        with self.assertRaises(StudyAuthorityReceiptError) as reused:
            apply_idempotent_existing_state_note_review(
                db.session,
                command=IdempotentExistingStateNoteReviewCommand(
                    operation_key="authority-command-request",
                    command=divergent,
                ),
            )
        self.assertEqual(reused.exception.code, "AUTHORITY_OPERATION_REUSED")
        self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)
        self.assertEqual(ReviewEvent.query.count(), 1)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 1)
        db.session.rollback()

    def test_idempotent_command_rejects_operation_provenance_mismatch_before_write(self):
        base = self._existing_state_command()
        with self.assertRaises(StudyAuthorityReceiptError) as mismatch:
            apply_idempotent_existing_state_note_review(
                db.session,
                command=IdempotentExistingStateNoteReviewCommand(
                    operation_key="another-operation",
                    command=base,
                ),
            )
        self.assertEqual(
            mismatch.exception.code,
            "AUTHORITY_OPERATION_PROVENANCE_MISMATCH",
        )
        self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 0)
        self.assertEqual(ReviewEvent.query.count(), 0)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 0)
        db.session.rollback()

    def test_idempotent_command_rejects_corrupt_stored_response(self):
        base = self._existing_state_command()
        first = apply_idempotent_existing_state_note_review(
            db.session,
            command=IdempotentExistingStateNoteReviewCommand(
                operation_key="authority-command-request",
                command=base,
            ),
        )
        first.receipt.response_payload_hash = b"\x00" * 32
        db.session.commit()

        retry = self._relock_existing_state_command(base)
        with self.assertRaises(StudyAuthorityReceiptError) as corrupt:
            apply_idempotent_existing_state_note_review(
                db.session,
                command=IdempotentExistingStateNoteReviewCommand(
                    operation_key="authority-command-request",
                    command=retry,
                ),
            )
        self.assertEqual(corrupt.exception.code, "AUTHORITY_RECEIPT_CORRUPT")
        self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)
        self.assertEqual(ReviewEvent.query.count(), 1)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 1)
        db.session.rollback()

    def test_receipt_failure_is_outer_rollback_safe(self):
        base = self._existing_state_command()
        with patch(
            "app.services.study_authority_receipt_service._stage_receipt",
            side_effect=StudyAuthorityReceiptError("INJECTED", "receipt fault"),
        ):
            with self.assertRaises(StudyAuthorityReceiptError) as fault:
                apply_idempotent_existing_state_note_review(
                    db.session,
                    command=IdempotentExistingStateNoteReviewCommand(
                        operation_key="authority-command-request",
                        command=base,
                    ),
                )
        self.assertEqual(fault.exception.code, "INJECTED")
        self.assertEqual(base.locked.token.authority_revision, 1)

        db.session.rollback()
        subject = db.session.get(StudyProgressSubject, self.subject_id)
        state = db.session.get(StudyProgressState, self.subject_id)
        self.assertEqual(subject.mirror_revision, 1)
        self.assertEqual(state.mirror_revision, 1)
        self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 0)
        self.assertEqual(ReviewEvent.query.count(), 0)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 0)
        self.assertEqual(StudyProgressLineageRef.query.count(), 0)
        for progress in db.session.execute(
            sa.select(CardProgress).where(CardProgress.card_id.in_(self.card_ids))
        ).scalars():
            self.assertEqual(progress.revision, 0)
            self.assertEqual(progress.queue, "new")


if __name__ == "__main__":
    unittest.main()
