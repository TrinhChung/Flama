"""Transactional writer coverage for the Phase 4 learner/Note shadow."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.services import (
    browse_card_service,
    deck_management_service,
    flashcard_content_service,
    study_progress_lifecycle_mirror_service,
    study_service,
    study_session_service,
)
from app.services.study_worker_service import process_single_study_batch
from app.services.study_progress_backfill_service import run_current_progress_backfill
from app.services.study_progress_reconciliation_service import (
    build_study_progress_reconciliation,
)
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lineage_ref import StudyProgressLineageRef
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User


class StudyProgressShadowMirrorTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
                "REDIS_URL": "",
                "STUDY_ASYNC_BATCH_ENABLED": True,
                "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": True,
                "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED": True,
                "STUDY_PROGRESS_SHADOW_COMPARE_ENABLED": True,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        user = User(
            username="shadow-learner",
            email="shadow@example.test",
            timezone="Asia/Tokyo",
        )
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        self.user_id = int(user.id)

        deck = Deck(name="Shadow deck", owner_user_id=user.id)
        note_type = NoteType(name="Shadow note type", user_id=user.id)
        db.session.add_all((deck, note_type))
        db.session.flush()
        field = FieldDef(
            note_type_id=note_type.id,
            name="Word",
            field_type="text",
            position=0,
            required=True,
        )
        first_template = Template(
            name="Recognition",
            note_type_id=note_type.id,
            position=0,
            is_default=True,
            front_html="{{Word}}",
            back_html="{{Word}}",
        )
        second_template = Template(
            name="Recall",
            note_type_id=note_type.id,
            position=1,
            is_default=False,
            front_html="{{Word}}",
            back_html="{{Word}}",
        )
        db.session.add_all((field, first_template, second_template))
        db.session.flush()
        note = Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={"Word": "猫"},
        )
        db.session.add(note)
        db.session.flush()
        first_card = Card(note_id=note.id, template_id=first_template.id)
        second_card = Card(note_id=note.id, template_id=second_template.id)
        db.session.add_all((first_card, second_card))
        db.session.commit()

        self.deck_id = int(deck.id)
        self.note_id = str(note.id)
        self.card_id = str(first_card.id)
        self.sibling_card_id = str(second_card.id)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _review(
        self,
        card_id: str,
        *,
        action: str = "good",
        source_path: str = "native.rest",
        client_event_id: str | None = None,
        now: datetime | None = None,
    ):
        return study_service.execute_native_review_command(
            user=db.session.get(User, self.user_id),
            card=db.session.get(Card, card_id),
            action=action,
            payload={"duration_ms": 300},
            clone_scope=None,
            requested_scope_id=self.deck_id,
            timezone_name="Asia/Tokyo",
            now=now or datetime(2026, 9, 13, 10, 0, 0),
            source_path=source_path,
            client_event_id=client_event_id,
        )

    def _open_session(self):
        return study_session_service.open_study_session(
            user=db.session.get(User, self.user_id),
            query=Card.query.filter(Card.id == self.card_id),
            clone_scope=None,
            scope_type="deck",
            scope_id=str(self.deck_id),
            timezone_name="Asia/Tokyo",
            now=datetime(2026, 9, 13, 10, 0, 0),
        )

    def _assert_reconciles(self):
        backfill = run_current_progress_backfill(db.session, apply=True)
        self.assertTrue(backfill.complete)
        report = build_study_progress_reconciliation(
            db.session,
            observed_at=datetime(2026, 9, 13, 10, 10, 0),
        )
        self.assertEqual(report["unexplained"]["by_code"], {})
        self.assertEqual(report["gate"]["status"], "PASS")
        return report

    @staticmethod
    def _events(snapshot, count: int = 2):
        card = snapshot["cards"][0]
        return [
            {
                "event_id": str(uuid4()),
                "sequence": index,
                "card_id": card["card_id"],
                "rating": "good" if index == 1 else "hard",
                "policy_key": card["policy_key"],
                "scheduler_offset_ms": index * 1000,
                "duration_ms": 300,
            }
            for index in range(1, count + 1)
        ]

    def test_flag_off_keeps_native_authority_without_shadow_rows(self):
        self.app.config["STUDY_PROGRESS_SHADOW_WRITE_ENABLED"] = False
        self._review(self.card_id)

        self.assertEqual(CardProgress.query.count(), 1)
        self.assertEqual(ReviewEvent.query.count(), 1)
        self.assertEqual(StudyProgressSubject.query.count(), 0)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 0)

    def test_direct_first_create_mirrors_state_pointer_and_history_atomically(self):
        self._review(self.card_id)

        progress = CardProgress.query.filter_by(
            user_id=self.user_id, card_id=self.card_id
        ).one()
        event = db.session.get(ReviewEvent, progress.last_review_event_id)
        subject = StudyProgressSubject.query.one()
        contributor = StudyProgressContributor.query.one()
        fact = StudyProgressHistoryFact.query.one()

        self.assertIsNotNone(event)
        self.assertEqual(subject.logical_note_key, self.note_id.encode("utf-8"))
        self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
        self.assertEqual(subject.subject_generation, 1)
        self.assertEqual(subject.mirror_revision, 1)
        self.assertEqual(subject.contributor_count, 1)
        self.assertEqual(contributor.live_card_progress_id, progress.id)
        self.assertEqual(contributor.card_progress_revision, progress.revision)
        self.assertEqual(contributor.pointer_status, "VALID")
        self.assertEqual(contributor.current_provenance_code, "NATIVE_DIRECT")
        self.assertEqual(
            contributor.history_completeness_code, "HISTORY_NATIVE_COMPLETE"
        )
        self.assertIsNotNone(db.session.get(StudyProgressState, subject.id))
        self.assertIsNotNone(db.session.get(StudyProgressAvailability, contributor.id))
        self.assertEqual(StudyProgressLineageRef.query.count(), 1)
        self.assertEqual(fact.review_event_id, event.id)
        self.assertEqual(fact.contributor_id, contributor.id)
        self.assertEqual(fact.provenance_code, "NATIVE_DIRECT")
        report = self._assert_reconciles()
        self.assertEqual(report["writer_coverage"]["matrix"]["NATIVE_DIRECT"]["status"], "PASS")
        self.assertEqual(report["writer_coverage"]["matrix"]["NATIVE_MCP"]["status"], "NOT_OBSERVED")

    def test_mcp_uses_the_same_mirror_with_distinct_provenance(self):
        self._review(
            self.card_id,
            source_path="native.mcp",
            client_event_id=str(uuid4()),
        )

        contributor = StudyProgressContributor.query.one()
        fact = StudyProgressHistoryFact.query.one()
        self.assertEqual(contributor.current_provenance_code, "NATIVE_MCP")
        self.assertEqual(fact.provenance_code, "NATIVE_MCP")
        report = self._assert_reconciles()
        self.assertEqual(report["writer_coverage"]["matrix"]["NATIVE_MCP"]["status"], "PASS")

    def test_sibling_card_add_advances_generation_and_quarantines_divergence(self):
        self._review(self.card_id, action="good")
        self._review(
            self.sibling_card_id,
            action="again",
            now=datetime(2026, 9, 13, 10, 1, 0),
        )

        subject = StudyProgressSubject.query.one()
        self.assertEqual(CardProgress.query.count(), 2)
        self.assertEqual(ReviewEvent.query.count(), 2)
        self.assertEqual(subject.subject_generation, 2)
        self.assertEqual(subject.mirror_revision, 2)
        self.assertEqual(subject.contributor_count, 2)
        self.assertEqual(subject.status_code, "QUARANTINED_STATE_DIVERGENCE")
        self.assertIsNone(db.session.get(StudyProgressState, subject.id))
        contributors = StudyProgressContributor.query.order_by(
            StudyProgressContributor.id.asc()
        ).all()
        self.assertEqual(len(contributors), 3)
        self.assertEqual(
            [(row.subject_generation, row.contributor_status) for row in contributors],
            [(1, "DETACHED"), (2, "ACTIVE"), (2, "ACTIVE")],
        )
        first_fact = StudyProgressHistoryFact.query.order_by(
            StudyProgressHistoryFact.id.asc()
        ).first()
        self.assertEqual(first_fact.subject_generation, 1)
        self.assertEqual(first_fact.contributor.subject_generation, 1)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 2)
        report = self._assert_reconciles()
        self.assertEqual(
            report["quarantines"]["by_code"],
            {"QUARANTINED_STATE_DIVERGENCE": 2},
        )
        self.assertEqual(report["query_parity"]["comparable_scope_count"], 0)

    def test_equivalent_sibling_fanin_reconciles_distinct_review_lineage(self):
        self._review(self.card_id, action="good")
        self._review(self.sibling_card_id, action="good")

        subject = StudyProgressSubject.query.one()
        self.assertEqual(
            subject.status_code,
            "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE",
        )
        report = self._assert_reconciles()
        self.assertEqual(report["quarantines"]["count"], 0)
        self.assertEqual(report["accounting"]["active_contributors"], 2)

    def test_session_finalizes_once_per_note_after_all_event_pointers(self):
        snapshot = self._open_session()
        events = self._events(snapshot, 2)
        commit_payload = {
            "schema_version": "study-commit.v1",
            "commit_id": str(uuid4()),
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "manual_exit",
            "events": events,
            "final_states": [],
        }
        response = study_session_service.commit_study_session(
            user=db.session.get(User, self.user_id),
            session_id=snapshot["session_id"],
            payload=commit_payload,
            now=datetime(2026, 9, 13, 10, 5, 0),
        )
        replayed = study_session_service.commit_study_session(
            user=db.session.get(User, self.user_id),
            session_id=snapshot["session_id"],
            payload=commit_payload,
            now=datetime(2026, 9, 13, 10, 5, 1),
        )

        subject = StudyProgressSubject.query.one()
        progress = CardProgress.query.one()
        self.assertEqual(response["applied_event_count"], 2)
        self.assertEqual(replayed, response)
        self.assertEqual(progress.revision, 1)
        self.assertEqual(subject.mirror_revision, 1)
        self.assertEqual(subject.contributor_count, 1)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 2)
        self.assertEqual(
            db.session.get(ReviewEvent, progress.last_review_event_id).sequence_no,
            2,
        )
        report = self._assert_reconciles()
        self.assertEqual(report["writer_coverage"]["matrix"]["NATIVE_SESSION"]["status"], "PASS")

    def test_worker_retry_is_idempotent_for_revision_and_history(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        job = {
            "schema_version": "study-batch-job.v1",
            "batch_id": batch_id,
            "session_id": snapshot["session_id"],
            "user_id": self.user_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": self._events(snapshot, 2),
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }

        first = process_single_study_batch(job)
        second = process_single_study_batch(job)

        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "already_processed")
        self.assertEqual(CardProgress.query.one().revision, 1)
        self.assertEqual(StudyProgressSubject.query.one().mirror_revision, 1)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 2)
        self.assertEqual(
            {row.provenance_code for row in StudyProgressHistoryFact.query.all()},
            {"NATIVE_ASYNC_BATCH"},
        )
        report = self._assert_reconciles()
        self.assertEqual(report["writer_coverage"]["matrix"]["NATIVE_ASYNC_BATCH"]["status"], "PASS")

    def test_unexpected_mirror_failure_rolls_back_authority_event_and_shadow(self):
        with patch(
            "app.services.study_progress_shadow_mirror_service._append_history_facts",
            side_effect=RuntimeError("fault injection"),
        ):
            with self.assertRaisesRegex(RuntimeError, "fault injection"):
                self._review(self.card_id)

        self.assertEqual(CardProgress.query.count(), 0)
        self.assertEqual(ReviewEvent.query.count(), 0)
        self.assertEqual(StudyProgressSubject.query.count(), 0)
        self.assertEqual(StudyProgressContributor.query.count(), 0)

    def test_card_delete_detaches_contributor_and_advances_generation(self):
        self._review(self.card_id)
        progress_id = CardProgress.query.one().id

        browse_card_service.delete_browse_card(
            user_id=self.user_id,
            admin_mode=False,
            card_id=self.card_id,
        )

        subject = StudyProgressSubject.query.one()
        contributor = StudyProgressContributor.query.one()
        lifecycle = StudyProgressLifecycleEvent.query.one()
        self.assertIsNone(db.session.get(Card, self.card_id))
        self.assertIsNone(db.session.get(CardProgress, progress_id))
        self.assertEqual(subject.status_code, "NO_CURRENT_PROGRESS")
        self.assertEqual((subject.subject_generation, subject.mirror_revision), (2, 2))
        self.assertEqual(contributor.contributor_status, "DETACHED")
        self.assertIsNone(contributor.live_card_progress_id)
        self.assertIsNone(contributor.live_card_id)
        self.assertEqual(lifecycle.transition_code, "DETACHED_CONTRIBUTOR_DELETED")
        self._assert_reconciles()

    def test_note_delete_tombstones_subject_without_deleting_history(self):
        self._review(self.card_id)
        event_id = ReviewEvent.query.one().id

        flashcard_content_service.delete_note(
            user_id=self.user_id,
            note_id=self.note_id,
        )

        subject = StudyProgressSubject.query.one()
        contributor = StudyProgressContributor.query.one()
        lifecycle = StudyProgressLifecycleEvent.query.one()
        self.assertIsNone(db.session.get(Note, self.note_id))
        self.assertIsNotNone(db.session.get(ReviewEvent, event_id))
        self.assertEqual(subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
        self.assertIsNone(subject.live_note_id)
        self.assertEqual(contributor.contributor_status, "TOMBSTONED")
        self.assertEqual(lifecycle.transition_code, "TOMBSTONED_SUBJECT_DELETED")
        self._assert_reconciles()

    def test_partial_card_delete_retains_closed_generation_and_reprojects_survivor(self):
        self._review(self.card_id, action="good")
        self._review(
            self.sibling_card_id,
            action="again",
            now=datetime(2026, 9, 13, 10, 1, 0),
        )

        browse_card_service.delete_browse_card(
            user_id=self.user_id,
            admin_mode=False,
            card_id=self.sibling_card_id,
        )

        subject = StudyProgressSubject.query.one()
        active = StudyProgressContributor.query.filter_by(
            contributor_status="ACTIVE"
        ).one()
        contributors = StudyProgressContributor.query.order_by(
            StudyProgressContributor.id.asc()
        ).all()
        lifecycle = StudyProgressLifecycleEvent.query.one()
        self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
        self.assertEqual((subject.subject_generation, subject.mirror_revision), (3, 3))
        self.assertEqual(subject.contributor_count, 1)
        self.assertEqual(active.subject_generation, 3)
        self.assertEqual(active.live_card_id, self.card_id)
        self.assertEqual(len(contributors), 4)
        self.assertEqual(
            [row.subject_generation for row in contributors],
            [1, 2, 2, 3],
        )
        self.assertEqual(lifecycle.transition_code, "DETACHED_CONTRIBUTOR_DELETED")
        self.assertEqual(lifecycle.evidence_payload["removed_card_count"], "1")
        self._assert_reconciles()

    def test_unexpected_lifecycle_failure_rolls_back_progress_and_card_delete(self):
        self._review(self.card_id)
        progress_id = CardProgress.query.one().id

        with patch(
            "app.services.study_progress_lifecycle_mirror_service.finalize_lifecycle_mirror",
            side_effect=RuntimeError("lifecycle fault injection"),
        ):
            with self.assertRaisesRegex(RuntimeError, "lifecycle fault injection"):
                browse_card_service.delete_browse_card(
                    user_id=self.user_id,
                    admin_mode=False,
                    card_id=self.card_id,
                )
        db.session.rollback()

        self.assertIsNotNone(db.session.get(Card, self.card_id))
        self.assertIsNotNone(db.session.get(CardProgress, progress_id))
        self.assertEqual(StudyProgressSubject.query.one().mirror_revision, 1)
        self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def test_lifecycle_fence_rejects_a_removed_card_with_live_authority(self):
        self._review(self.card_id)
        plan = study_progress_lifecycle_mirror_service.prepare_lifecycle_mirror(
            db.session,
            removed_card_ids=(self.card_id,),
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "left authoritative progress on a removed Card",
        ):
            study_progress_lifecycle_mirror_service.finalize_lifecycle_mirror(
                plan,
                transition_code="DETACHED_CONTRIBUTOR_DELETED",
                source_path="test.missing_authority_delete",
                operation_key="missing-authority-delete",
            )
        db.session.rollback()

        self.assertEqual(CardProgress.query.count(), 1)
        self.assertEqual(StudyProgressSubject.query.one().mirror_revision, 1)
        self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def test_reset_tombstone_separates_history_from_later_review_generation(self):
        self._review(self.card_id)
        first_event_id = ReviewEvent.query.one().id

        deleted = deck_management_service.reset_deck_progress(
            deck_obj=db.session.get(Deck, self.deck_id),
            user_id=self.user_id,
        )
        self.assertEqual(deleted, 1)
        subject = StudyProgressSubject.query.one()
        prior_contributor = StudyProgressContributor.query.one()
        self.assertEqual(subject.status_code, "TOMBSTONED_RESET")
        self.assertEqual((subject.subject_generation, subject.mirror_revision), (2, 2))
        self.assertEqual(prior_contributor.contributor_status, "TOMBSTONED")
        self.assertIsNotNone(db.session.get(ReviewEvent, first_event_id))
        self._assert_reconciles()

        self._review(
            self.card_id,
            now=datetime(2026, 9, 13, 10, 5, 0),
        )
        subject = StudyProgressSubject.query.one()
        self.assertEqual((subject.subject_generation, subject.mirror_revision), (3, 3))
        self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
        self.assertEqual(
            StudyProgressContributor.query.filter_by(contributor_status="ACTIVE").count(),
            1,
        )
        self.assertEqual(StudyProgressHistoryFact.query.count(), 2)
        self._assert_reconciles()


if __name__ == "__main__":
    unittest.main()
