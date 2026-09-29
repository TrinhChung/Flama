"""Schema and persistence checks for scheduler-domain models."""

import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import sqlalchemy as sa

from app import create_app
from app.startup_schema import ensure_backward_compatible_schema
from app.repositories.study_repository import (
    apply_card_state_to_progress,
    select_next_due_card_from_loaded,
    summarize_pending_learning_from_loaded,
)
from app.services.anki_scheduler import CardState, FsrsMemoryState
from app.services.scheduler_config_service import resolve_deck_options
from app.services.stats_overview import record_review_event
from models import db
from models.card_progress import CardProgress
from models.deck import Deck
from models.scheduler_preset import SchedulerPreset
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.user import User
from models.user_scheduler_settings import UserSchedulerSettings


class SchedulerSchemaTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )
        with self.app.app_context():
            db.create_all()
            user = User(username="schema-user", email="schema@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_scheduler_schema_tables_and_columns_exist(self):
        with self.app.app_context():
            inspector = sa.inspect(db.engine)

            self.assertTrue(inspector.has_table("scheduler_presets"))
            self.assertTrue(inspector.has_table("user_scheduler_settings"))

            card_progress_columns = {column["name"] for column in inspector.get_columns("card_progress")}
            self.assertTrue(
                {
                    "interval_days_raw",
                    "is_buried",
                    "buried_until_day",
                    "review_kind",
                    "scheduler_mode",
                    "memory_stability",
                    "memory_difficulty",
                    "suspension_reason",
                    "last_leech_at",
                    "last_leech_lapses",
                    "last_review_event_id",
                }.issubset(card_progress_columns)
            )

            review_event_columns = {column["name"] for column in inspector.get_columns("review_events")}
            self.assertTrue(
                {
                    "scheduler_preset_id",
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
                    "payload_json",
                }.issubset(review_event_columns)
            )

            deck_columns = {column["name"] for column in inspector.get_columns("decks")}
            self.assertIn("scheduler_preset_id", deck_columns)

    def test_card_progress_persists_extended_scheduler_state(self):
        with self.app.app_context():
            progress = CardProgress(user_id=self.user_id, card_id=None, queue="new")
            db.session.add(progress)
            db.session.commit()

            now = datetime(2026, 3, 27, 10, 0, 0)
            updated = CardState(
                type="review",
                due=now,
                dueDay=now.date().toordinal() + 5,
                intervalDays=5.75,
                ease=2.65,
                reps=12,
                lapses=3,
                lastReviewAt=now,
                reviewKind="filtered",
                schedulerMode="fsrs",
                suspended=True,
                suspensionReason="leech",
                leeched=True,
                memoryState=FsrsMemoryState(stability=9.5, difficulty=4.25),
            )

            apply_card_state_to_progress(progress, updated, now)
            db.session.commit()

            stored = CardProgress.query.get(progress.id)
            self.assertAlmostEqual(float(stored.interval_days_raw or 0), 5.75, delta=0.0001)
            self.assertEqual(stored.review_kind, "filtered")
            self.assertEqual(stored.scheduler_mode, "fsrs")
            self.assertTrue(stored.is_suspended)
            self.assertEqual(stored.suspension_reason, "leech")
            self.assertAlmostEqual(float(stored.memory_stability or 0), 9.5, delta=0.0001)
            self.assertAlmostEqual(float(stored.memory_difficulty or 0), 4.25, delta=0.0001)
            self.assertEqual(int(stored.last_leech_lapses or 0), 3)
            self.assertIsNotNone(stored.last_leech_at)

    def test_startup_compatibility_does_not_rewrite_existing_progress_raw_value(self):
        with self.app.app_context():
            progress = CardProgress(
                user_id=self.user_id,
                card_id=None,
                queue="review",
                interval_days=7,
                interval_days_raw=None,
            )
            db.session.add(progress)
            # Deliberately divergent NOTE projection: boot repair must not
            # mask it before the parity reader can reject the learner.
            recorded_at = datetime(2026, 9, 24, 0, 0, 0)
            db.session.add(StudyAuthorityEnrollment(
                learner_user_id=self.user_id,
                mode_code="NOTE",
                epoch=1,
                created_at=recorded_at,
                updated_at=recorded_at,
            ))
            db.session.commit()
            progress_id = progress.id

            ensure_backward_compatible_schema()
            db.session.expire_all()
            stored = db.session.get(CardProgress, progress_id)
            self.assertIsNone(stored.interval_days_raw)

    def test_startup_compatibility_initializes_raw_value_when_column_is_added(self):
        # A file-backed database keeps inspector connections separate from the
        # writer transaction; SQLite :memory: shares one connection and can
        # roll an in-flight repair UPDATE back during schema inspection.
        with TemporaryDirectory(prefix="flama-startup-schema-") as temporary_dir:
            database_path = (Path(temporary_dir) / "startup.sqlite").as_posix()
            app = create_app({
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            })
            with app.app_context():
                db.create_all()
                user = User(username="startup-raw-user", email="startup-raw@example.com")
                user.set_password("password")
                db.session.add(user)
                db.session.flush()
                progress = CardProgress(
                    user_id=user.id,
                    card_id=None,
                    queue="review",
                    interval_days=7,
                    interval_days_raw=7.0,
                )
                db.session.add(progress)
                db.session.commit()
                progress_id = progress.id

                db.session.execute(sa.text(
                    "ALTER TABLE card_progress DROP COLUMN interval_days_raw"
                ))
                db.session.commit()
                ensure_backward_compatible_schema()
                db.session.expire_all()
                stored = db.session.get(CardProgress, progress_id)
                self.assertEqual(stored.interval_days_raw, 7.0)
                db.session.remove()
                db.engine.dispose()

    def test_review_event_persists_extended_scheduler_metadata(self):
        with self.app.app_context():
            reviewed_at = datetime(2026, 3, 27, 10, 15, 0)
            event = record_review_event(
                user_id=self.user_id,
                card_id="card-1",
                deck_id=123,
                note_type_id="note-type-1",
                reviewed_at=reviewed_at,
                duration_ms=4321,
                rating="good",
                mode="review",
                scheduler_mode="fsrs",
                review_kind="filtered",
                queue_before="review",
                queue_after="review",
                interval_days_before=4.5,
                interval_days_after=12.25,
                due_day_before=10,
                due_day_after=22,
                days_late=-2,
                ease_factor_before=2.5,
                ease_factor_after=2.5,
                memory_stability_before=3.5,
                memory_stability_after=8.0,
                memory_difficulty_before=5.0,
                memory_difficulty_after=4.4,
                leeched_after=False,
                suspended_after=False,
                payload_json='{"source":"test"}',
            )
            db.session.commit()

            stored = event.__class__.query.get(event.id)
            self.assertEqual(stored.scheduler_mode, "fsrs")
            self.assertEqual(stored.review_kind, "filtered")
            self.assertEqual(stored.queue_before, "review")
            self.assertAlmostEqual(float(stored.interval_days_before or 0), 4.5, delta=0.0001)
            self.assertAlmostEqual(float(stored.interval_days_after or 0), 12.25, delta=0.0001)
            self.assertEqual(int(stored.days_late or 0), -2)
            self.assertAlmostEqual(float(stored.memory_stability_after or 0), 8.0, delta=0.0001)
            self.assertEqual(stored.payload_json, '{"source":"test"}')

    def test_resolve_deck_options_reads_user_settings_and_preset(self):
        with self.app.app_context():
            settings = UserSchedulerSettings(
                user_id=self.user_id,
                scheduler_mode="fsrs",
                day_boundary_hour_local=2,
                learn_ahead_seconds=45,
                fsrs_allow_short_term=True,
            )
            preset = SchedulerPreset(
                user_id=self.user_id,
                name="FSRS Deck",
                learning_steps_json="[30, 120]",
                relearning_steps_json="[90]",
                graduating_interval_days=3,
                easy_interval_days=8,
                hard_multiplier=1.15,
                easy_multiplier=1.4,
                interval_modifier=0.9,
                lapse_multiplier=0.2,
                minimum_lapse_interval_days=2,
                maximum_interval_days=500,
                leech_threshold=12,
                leech_action="tag_only",
                desired_retention=0.92,
            )
            deck = Deck(owner_user_id=self.user_id, name="Scheduler Deck")
            db.session.add_all([settings, preset, deck])
            db.session.flush()
            deck.scheduler_preset_id = preset.id
            db.session.commit()

            options = resolve_deck_options(user_id=self.user_id, deck_id=deck.id)

            self.assertEqual(options.schedulerMode, "fsrs")
            self.assertEqual(options.dayBoundaryHourLocal, 2)
            self.assertEqual(options.learnAheadSeconds, 45)
            self.assertEqual(int(options.learningSteps[0].total_seconds()), 30)
            self.assertEqual(int(options.learningSteps[1].total_seconds()), 120)
            self.assertEqual(int(options.relearningSteps[0].total_seconds()), 90)
            self.assertEqual(options.graduatingIntervalDays, 3)
            self.assertEqual(options.easyIntervalDays, 8)
            self.assertAlmostEqual(options.hardFactor, 1.15, delta=0.0001)
            self.assertAlmostEqual(options.easyBonus, 1.4, delta=0.0001)
            self.assertAlmostEqual(options.intervalModifier, 0.9, delta=0.0001)
            self.assertAlmostEqual(options.newIntervalFactor, 0.2, delta=0.0001)
            self.assertEqual(options.minimumIntervalDays, 2)
            self.assertEqual(options.maxIntervalDays, 500)
            self.assertEqual(options.leechThreshold, 12)
            self.assertFalse(options.leechSuspend)

    def test_loaded_selection_respects_user_learn_ahead_setting(self):
        with self.app.app_context():
            settings = UserSchedulerSettings(
                user_id=self.user_id,
                learn_ahead_seconds=60,
            )
            db.session.add(settings)
            db.session.commit()

            now = datetime(2026, 3, 27, 10, 0, 0)
            card = SimpleNamespace(id="learn-future", created_at=now)
            progress_map = {
                "learn-future": CardProgress(
                    user_id=self.user_id,
                    card_id="learn-future",
                    queue="learning",
                    due_at=now + timedelta(seconds=45),
                )
            }

            selected = select_next_due_card_from_loaded(
                [card],
                progress_map,
                now=now,
                user_id=self.user_id,
            )
            pending_count, next_due_at = summarize_pending_learning_from_loaded(
                [card],
                progress_map,
                now=now,
                user_id=self.user_id,
            )

            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, "learn-future")
            self.assertEqual(pending_count, 0)
            self.assertIsNone(next_due_at)


if __name__ == "__main__":
    unittest.main()
