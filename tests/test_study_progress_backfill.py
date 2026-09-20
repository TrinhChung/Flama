"""Crash/resume, accounting and CAS coverage for Phase 4 P4-09."""

from __future__ import annotations

from datetime import datetime
import json
import unittest
from unittest.mock import patch

from app import create_app
from app.services import deck_management_service
from app.services import study_progress_backfill_service as backfill_service
from app.services import study_progress_shadow_mirror_service as mirror
from app.services.study_progress_backfill_service import (
    BACKFILL_SERVICE_VERSION,
    StudyProgressBackfillError,
    run_current_progress_backfill,
)
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_backfill_checkpoint import StudyProgressBackfillCheckpoint
from models.study_progress_backfill_disposition import StudyProgressBackfillDisposition
from models.study_progress_backfill_run import StudyProgressBackfillRun
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lineage_ref import StudyProgressLineageRef
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User


class StudyProgressBackfillTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
                "REDIS_URL": "",
                "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": True,
                "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED": True,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        user = User(
            username="backfill-learner",
            email="backfill@example.test",
            timezone="Asia/Tokyo",
        )
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        deck = Deck(name="Backfill deck", owner_user_id=user.id)
        note_type = NoteType(name="Backfill type", user_id=user.id)
        db.session.add_all((deck, note_type))
        db.session.flush()
        db.session.add(
            FieldDef(
                note_type_id=note_type.id,
                name="Word",
                field_type="text",
                position=0,
                required=True,
            )
        )
        first_template = Template(
            note_type_id=note_type.id,
            name="Recognition",
            position=0,
            is_default=True,
            front_html="{{Word}}",
            back_html="{{Word}}",
        )
        second_template = Template(
            note_type_id=note_type.id,
            name="Recall",
            position=1,
            is_default=False,
            front_html="{{Word}}",
            back_html="{{Word}}",
        )
        db.session.add_all((first_template, second_template))
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

        self.user_id = int(user.id)
        self.deck_id = int(deck.id)
        self.note_id = str(note.id)
        self.card_id = str(first_card.id)
        self.sibling_card_id = str(second_card.id)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _add_progress(
        self,
        card_id: str | None = None,
        *,
        interval_days: int = 4,
        revision: int = 0,
    ) -> CardProgress:
        row = CardProgress(
            user_id=self.user_id,
            card_id=card_id,
            queue="review",
            step_index=0,
            due_day=22000,
            interval_days=interval_days,
            interval_days_raw=float(interval_days),
            is_suspended=False,
            is_buried=False,
            review_kind="review",
            scheduler_mode="legacy",
            ease_factor=2.5,
            reps=3,
            lapses=0,
            last_leech_lapses=0,
            revision=revision,
            created_at=datetime(2026, 9, 14, 8, 0, 0),
            updated_at=datetime(2026, 9, 14, 8, 0, 0),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _mirror_existing_progress(self, card_id: str) -> StudyProgressSubject:
        card = db.session.get(Card, card_id)
        plan = mirror.prepare_native_mirror(
            db.session,
            learner_user_id=self.user_id,
            cards=(card,),
            now_utc=datetime(2026, 9, 14, 8, 0, 0),
        )
        mirror.finalize_native_mirror(
            plan,
            review_events=(),
            now_utc=datetime(2026, 9, 14, 8, 0, 0),
        )
        db.session.commit()
        return StudyProgressSubject.query.one()

    def _clear_backfill_evidence(self) -> None:
        StudyProgressBackfillDisposition.query.delete(synchronize_session=False)
        StudyProgressBackfillCheckpoint.query.delete(synchronize_session=False)
        StudyProgressBackfillRun.query.delete(synchronize_session=False)
        StudyProgressHistoryFact.query.delete(synchronize_session=False)
        StudyProgressLifecycleEvent.query.delete(synchronize_session=False)
        StudyProgressLineageRef.query.delete(synchronize_session=False)
        StudyProgressAvailability.query.delete(synchronize_session=False)
        StudyProgressState.query.delete(synchronize_session=False)
        StudyProgressContributor.query.delete(synchronize_session=False)
        StudyProgressSubject.query.delete(synchronize_session=False)
        db.session.commit()

    def test_dry_run_is_default_and_writes_no_shadow_or_run_rows(self):
        progress = self._add_progress(self.card_id)

        result = run_current_progress_backfill(db.session)

        self.assertEqual(result.mode, "dry-run")
        self.assertTrue(result.complete)
        self.assertEqual(result.source_count, 1)
        self.assertEqual(result.mirrored_count, 1)
        self.assertEqual(result.disposition_counts, {"MIRRORED_SINGLE": 1})
        self.assertEqual(StudyProgressBackfillRun.query.count(), 0)
        self.assertEqual(StudyProgressSubject.query.count(), 0)
        self.assertEqual(CardProgress.query.one().id, progress.id)

    def test_apply_stops_resumes_and_completed_replay_is_idempotent(self):
        progress = self._add_progress(self.card_id, revision=3)

        partial = run_current_progress_backfill(
            db.session, apply=True, max_batches=1
        )
        self.assertEqual(partial.status, "RUNNING")
        self.assertFalse(partial.complete)
        self.assertIsNotNone(partial.run_id)
        run = db.session.get(StudyProgressBackfillRun, partial.run_id)
        checkpoint = db.session.get(
            StudyProgressBackfillCheckpoint, (partial.run_id, 0)
        )
        self.assertRegex(run.repository_commit, r"^[0-9a-f]{40}$")
        self.assertEqual(run.database_head, "create-all-test")
        self.assertEqual(len(run.contract_hash), 32)
        self.assertEqual(checkpoint.last_source_id, progress.id)
        self.assertEqual(checkpoint.processed_count, 1)

        completed = run_current_progress_backfill(
            db.session, apply=True, run_id=partial.run_id
        )
        self.assertTrue(completed.complete)
        self.assertEqual(completed.status, "COMPLETED")
        subject = StudyProgressSubject.query.one()
        completed_revision = int(subject.mirror_revision)
        self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
        self.assertEqual(StudyProgressBackfillDisposition.query.count(), 1)
        self.assertEqual(StudyProgressHistoryFact.query.count(), 0)

        replay = run_current_progress_backfill(
            db.session, apply=True, run_id=partial.run_id
        )
        self.assertTrue(replay.complete)
        self.assertEqual(StudyProgressBackfillDisposition.query.count(), 1)
        self.assertEqual(
            StudyProgressSubject.query.one().mirror_revision, completed_revision
        )
        self.assertEqual(CardProgress.query.one().revision, 3)

    def test_divergent_fanin_and_null_card_are_fully_accounted(self):
        self._add_progress(self.card_id, interval_days=4)
        self._add_progress(self.sibling_card_id, interval_days=9)
        null_card = self._add_progress(None, interval_days=1)

        result = run_current_progress_backfill(db.session, apply=True)

        self.assertTrue(result.complete)
        self.assertEqual(result.source_count, 3)
        self.assertEqual(result.quarantined_count, 2)
        self.assertEqual(result.unresolvable_count, 1)
        self.assertEqual(
            result.disposition_counts,
            {
                "QUARANTINED_STATE_DIVERGENCE": 2,
                "UNRESOLVABLE_NULL_CARD_ID": 1,
            },
        )
        subject = StudyProgressSubject.query.one()
        self.assertEqual(subject.status_code, "QUARANTINED_STATE_DIVERGENCE")
        self.assertEqual(subject.contributor_count, 2)
        self.assertIsNone(db.session.get(StudyProgressState, subject.id))
        disposition = StudyProgressBackfillDisposition.query.filter_by(
            source_row_key=str(null_card.id).encode("ascii")
        ).one()
        self.assertIsNone(disposition.subject_id)
        self.assertNotIn("猫", json.dumps(disposition.evidence_payload, ensure_ascii=False))

    def test_keyset_batches_resume_without_offset_or_duplicate_dispositions(self):
        first = self._add_progress(self.card_id)
        second = self._add_progress(None)

        with patch.object(backfill_service, "SOURCE_ROWS_PER_BATCH", 1):
            partial = run_current_progress_backfill(
                db.session, apply=True, max_batches=1
            )
            self.assertEqual(partial.last_source_id, first.id)
            self.assertEqual(StudyProgressBackfillDisposition.query.count(), 1)

            completed = run_current_progress_backfill(
                db.session, apply=True, run_id=partial.run_id
            )

        self.assertTrue(completed.complete)
        self.assertEqual(completed.batches, 1)
        self.assertEqual(completed.last_source_id, second.id)
        self.assertEqual(StudyProgressBackfillDisposition.query.count(), 2)
        self.assertEqual(
            StudyProgressBackfillCheckpoint.query.one().processed_count, 2
        )

    def test_unclassified_source_is_quarantined_then_logical_install_is_trusted(self):
        publisher = User(
            username="backfill-publisher",
            email="publisher@example.test",
            timezone="Asia/Tokyo",
        )
        publisher.set_password("password")
        db.session.add(publisher)
        db.session.flush()
        source_deck = Deck(name="Source deck", owner_user_id=publisher.id)
        local_deck = Deck(name="Installed shell", owner_user_id=self.user_id)
        source_type = NoteType(name="Source type", user_id=publisher.id)
        db.session.add_all((source_deck, local_deck, source_type))
        db.session.flush()
        db.session.add(
            FieldDef(
                note_type_id=source_type.id,
                name="Word",
                field_type="text",
                position=0,
                required=True,
            )
        )
        source_template = Template(
            note_type_id=source_type.id,
            name="Source template",
            position=0,
            is_default=True,
            front_html="{{Word}}",
            back_html="{{Word}}",
        )
        db.session.add(source_template)
        db.session.flush()
        source_note = Note(
            user_id=publisher.id,
            note_type_id=source_type.id,
            deck_id=source_deck.id,
            field_values={"Word": "不変"},
        )
        db.session.add(source_note)
        db.session.flush()
        source_card = Card(note_id=source_note.id, template_id=source_template.id)
        item = DeckMarketplaceItem(
            owner_user_id=publisher.id,
            source_deck_id=source_deck.id,
            source_note_type_id=source_type.id,
            title="Source listing",
            description="",
            primary_category="General",
            tags=[],
            taxonomy_metadata={},
        )
        db.session.add_all((source_card, item))
        db.session.commit()
        original_values = dict(source_note.field_values)
        self._add_progress(str(source_card.id))

        quarantined = run_current_progress_backfill(db.session, apply=True)
        self.assertEqual(
            quarantined.disposition_counts,
            {"QUARANTINED_UNCLASSIFIED_CONTEXT": 1},
        )
        subject = StudyProgressSubject.query.one()
        self.assertEqual(subject.status_code, "QUARANTINED_UNCLASSIFIED_CONTEXT")
        self.assertIsNone(db.session.get(StudyProgressState, subject.id))

        db.session.add(
            DeckInstall(
                deck_item_id=item.id,
                user_id=self.user_id,
                local_deck_id=local_deck.id,
                clone_mode="logical_overlay",
                source_deck_id=source_deck.id,
                source_note_type_id=source_type.id,
                source_owner_user_id=publisher.id,
            )
        )
        db.session.commit()
        trusted = run_current_progress_backfill(db.session, apply=True)

        self.assertEqual(trusted.disposition_counts, {"MIRRORED_SINGLE": 1})
        subject = StudyProgressSubject.query.one()
        self.assertEqual(subject.status_code, "MIRRORED_SINGLE")
        self.assertIsNotNone(db.session.get(StudyProgressState, subject.id))
        self.assertEqual(db.session.get(Note, source_note.id).field_values, original_values)

    def test_each_fault_boundary_rolls_back_batch_and_checkpoint(self):
        self._add_progress(self.card_id)

        for boundary in ("read", "lock", "upsert", "disposition", "checkpoint"):
            with self.subTest(boundary=boundary):
                def inject(point, _context):
                    if point == boundary:
                        raise RuntimeError(f"fault:{boundary}")

                with self.assertRaises(StudyProgressBackfillError):
                    run_current_progress_backfill(
                        db.session,
                        apply=True,
                        fault_injector=inject,
                    )
                run = StudyProgressBackfillRun.query.one()
                checkpoint = StudyProgressBackfillCheckpoint.query.one()
                self.assertEqual(run.status_code, "FAILED")
                self.assertEqual(checkpoint.status_code, "FAILED")
                self.assertIsNone(checkpoint.last_source_id)
                self.assertEqual(checkpoint.processed_count, 0)
                self.assertEqual(StudyProgressBackfillDisposition.query.count(), 0)
                self.assertEqual(StudyProgressSubject.query.count(), 0)
                self._clear_backfill_evidence()

    def test_stale_authority_retries_from_fresh_revision(self):
        progress = self._add_progress(self.card_id)
        injected = False

        def mutate_after_read(point, _context):
            nonlocal injected
            if point != "read" or injected:
                return
            injected = True
            row = db.session.get(CardProgress, progress.id)
            row.interval_days = 12
            row.interval_days_raw = 12.0
            row.revision = int(row.revision) + 1
            db.session.commit()

        result = run_current_progress_backfill(
            db.session,
            apply=True,
            fault_injector=mutate_after_read,
        )

        self.assertTrue(result.complete)
        self.assertEqual(result.retry_count, 1)
        contributor = StudyProgressContributor.query.one()
        disposition = StudyProgressBackfillDisposition.query.one()
        self.assertEqual(contributor.card_progress_revision, 1)
        self.assertEqual(disposition.attempt_count, 2)
        self.assertEqual(disposition.disposition_code, "MIRRORED_SINGLE")

    def test_new_contributor_race_advances_generation_without_loss(self):
        self._add_progress(self.card_id, interval_days=4)
        subject = self._mirror_existing_progress(self.card_id)
        self.assertEqual(subject.subject_generation, 1)
        injected = False

        def add_sibling_after_read(point, _context):
            nonlocal injected
            if point != "read" or injected:
                return
            injected = True
            sibling = db.session.get(Card, self.sibling_card_id)
            plan = mirror.prepare_native_mirror(
                db.session,
                learner_user_id=self.user_id,
                cards=(sibling,),
            )
            db.session.add(
                CardProgress(
                    user_id=self.user_id,
                    card_id=self.sibling_card_id,
                    queue="review",
                    step_index=0,
                    due_day=22000,
                    interval_days=9,
                    interval_days_raw=9.0,
                    is_suspended=False,
                    is_buried=False,
                    review_kind="review",
                    scheduler_mode="legacy",
                    ease_factor=2.5,
                    reps=3,
                    lapses=0,
                    last_leech_lapses=0,
                    revision=0,
                    created_at=datetime(2026, 9, 14, 8, 1, 0),
                    updated_at=datetime(2026, 9, 14, 8, 1, 0),
                )
            )
            mirror.finalize_native_mirror(plan, review_events=())
            db.session.commit()

        result = run_current_progress_backfill(
            db.session,
            apply=True,
            fault_injector=add_sibling_after_read,
        )

        self.assertTrue(result.complete)
        self.assertEqual(result.retry_count, 1)
        subject = StudyProgressSubject.query.one()
        self.assertEqual(subject.subject_generation, 2)
        self.assertEqual(subject.contributor_count, 2)
        self.assertEqual(subject.status_code, "QUARANTINED_STATE_DIVERGENCE")
        self.assertEqual(CardProgress.query.count(), 2)

    def test_reset_race_finishes_with_retained_tombstone_disposition(self):
        progress = self._add_progress(self.card_id)
        progress_id = int(progress.id)
        self._mirror_existing_progress(self.card_id)
        injected = False

        def reset_after_read(point, _context):
            nonlocal injected
            if point != "read" or injected:
                return
            injected = True
            deleted = deck_management_service.reset_deck_progress(
                deck_obj=db.session.get(Deck, self.deck_id),
                user_id=self.user_id,
            )
            self.assertEqual(deleted, 1)

        result = run_current_progress_backfill(
            db.session,
            apply=True,
            fault_injector=reset_after_read,
        )

        self.assertTrue(result.complete)
        self.assertEqual(result.retry_count, 1)
        self.assertEqual(result.unresolvable_count, 1)
        self.assertEqual(
            result.disposition_counts, {"TOMBSTONED_RESET": 1}
        )
        self.assertEqual(CardProgress.query.count(), 0)
        subject = StudyProgressSubject.query.one()
        self.assertEqual(subject.subject_generation, 2)
        self.assertEqual(subject.status_code, "TOMBSTONED_RESET")
        disposition = StudyProgressBackfillDisposition.query.one()
        self.assertEqual(
            bytes(disposition.source_row_key), str(progress_id).encode("ascii")
        )

    def test_cli_is_gated_and_dry_run_output_is_redacted_json(self):
        self._add_progress(self.card_id)
        runner = self.app.test_cli_runner()
        self.app.config["STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED"] = False
        blocked = runner.invoke(args=["study-progress-backfill"])
        self.assertNotEqual(blocked.exit_code, 0)
        self.assertIn("STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED", blocked.output)

        self.app.config["STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED"] = True
        dry_run = runner.invoke(args=["study-progress-backfill"])
        self.assertEqual(dry_run.exit_code, 0, dry_run.output)
        payload = json.loads(dry_run.output)
        self.assertEqual(payload["mode"], "dry-run")
        self.assertEqual(payload["backfill_service_version"], BACKFILL_SERVICE_VERSION)
        self.assertNotIn("猫", dry_run.output)
        self.assertEqual(StudyProgressBackfillRun.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
