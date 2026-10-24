"""Exact projected due buckets versus the canonical NOTE forecast oracle."""

from datetime import date, timedelta
import importlib
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app.services import forecast_snapshot_service as service
from app.services.stats_today_future import build_today_future_stats
from app.services.stats_overview import _canonical_future_due_day_counts
from models import db
from models.forecast_snapshot import StudyForecastSnapshot, StudyForecastDueBucket
from models.study_progress_subject import StudyProgressSubject
from models.user import User
from tests import test_note_stats_retirement as note_fixture

NOW, DAY = note_fixture.NOW, note_fixture.DAY


class ForecastSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.fixture = note_fixture.NoteStatsRetirementTests()
        self.fixture.setUp()
        self.app = self.fixture.app
        user = db.session.get(User, 1)
        user.timezone = "UTC"
        db.session.commit()
        self.app.config.update(DECK_COUNT_WRITE_ENABLED=True,
            FORECAST_SUMMARY_READ_MODE="summary", FORECAST_SUMMARY_READ_USER_IDS=[1])

    def tearDown(self):
        self.fixture.tearDown()

    def _prewarm(self, **kwargs):
        db.session.remove()
        return service.prewarm_forecast_summary(user_id=1, now_utc=NOW, **kwargs)

    def _payload(self, mode="summary", **kwargs):
        self.app.config["FORECAST_SUMMARY_READ_MODE"] = mode
        return build_today_future_stats(user_id=1, timezone_name="UTC", scope="collection",
            deck_id=None, history_range="12m", future_range=kwargs.get("future_range", "30"),
            backlog=kwargs.get("backlog", True), now_utc=NOW)

    def test_ready_payload_parity_and_no_note_progress_history_forecast_scan(self):
        raw = self._payload("raw")
        result = self._prewarm()
        self.assertTrue(result["published"])
        self.app.config["FORECAST_SUMMARY_READ_MODE"] = "summary"
        self.fixture.trace.clear()
        # Check the projection alone: the endpoint's today history is a
        # separate metric and keeps its own qualified history reader.
        summary = service.resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
            timezone_name="UTC", day_boundary_hour=4, now_utc=NOW, backlog=True, end_offset=29)
        self.assertIsNotNone(summary)
        sql = " ".join(self.fixture.trace).lower()
        self.assertNotIn("study_progress_subjects", sql)
        self.assertNotIn("review_events", sql)
        self.assertNotIn("from notes", sql)
        self.assertEqual(self._payload(), raw)

    def test_overlap_installs_and_pinned_retirement_are_collection_union(self):
        self.fixture._clone(local_deck=3)
        self.fixture._clone(local_deck=4, duplicate=True)
        db.session.commit()
        raw = self._payload("raw", future_range="all")
        self._prewarm()
        self.assertEqual(self._payload(future_range="all"), raw)

    def test_progress_interval_only_change_rejects_and_rebuilds(self):
        self._prewarm()
        subject = db.session.execute(sa.select(StudyProgressSubject).where(
            StudyProgressSubject.live_note_id == self.fixture.own_note)).scalar_one()
        payload = dict(subject.state_payload)
        payload["interval_days"] = "f:20.0"
        subject.state_payload = payload
        db.session.commit()
        self.assertIsNone(service.resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
            timezone_name="UTC", day_boundary_hour=4, now_utc=NOW, backlog=True, end_offset=29))

    def test_clock_policy_and_canary_changes_reject(self):
        self._prewarm()
        for moment, zone, boundary in ((NOW + timedelta(days=1), "UTC", 4),
                                       (NOW, "Asia/Tokyo", 4), (NOW, "UTC", 0)):
            self.assertIsNone(service.resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
                timezone_name=zone, day_boundary_hour=boundary, now_utc=moment,
                backlog=True, end_offset=29))
        self.app.config["FORECAST_SUMMARY_READ_USER_IDS"] = [2]
        self.assertIsNone(service.resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
            timezone_name="UTC", day_boundary_hour=4, now_utc=NOW, backlog=True, end_offset=29))

    def test_counting_unit_flip_rejects_the_snapshot_until_rebuilt(self):
        # Two more presentations give the Note three Cards, so the units differ.
        for _ in range(2):
            self.fixture._application(1, self.fixture.own_type)
        db.session.commit()
        args = dict(user_id=1, deck_ids=None, timezone_name="UTC", day_boundary_hour=4,
                    now_utc=NOW, backlog=True, end_offset=29)
        self.app.config["STUDY_NOTE_COUNT_ENABLED"] = False
        card_raw = self._payload("raw")
        self.assertTrue(self._prewarm()["published"])
        self.assertEqual(self._payload(), card_raw)
        self.app.config["STUDY_NOTE_COUNT_ENABLED"] = True
        self.assertIsNone(service.resolve_forecast_summary(db.session, **args))
        note_raw = self._payload("raw")
        self.assertNotEqual(note_raw["totals"], card_raw["totals"])
        self.assertTrue(self._prewarm()["published"])
        self.assertEqual(self._payload(), note_raw)

    def test_window_backlog_overdue_and_overview_fold_parity(self):
        subject = db.session.execute(sa.select(StudyProgressSubject)).scalar_one()
        subject.due_day = DAY - 3
        db.session.commit()
        raw = [self._payload("raw", backlog=value) for value in (False, True)]
        overview = _canonical_future_due_day_counts(user_id=1, timezone_name="UTC", timezone_obj=None,
            start_utc=NOW.replace(hour=4), end_utc=NOW.replace(hour=4) + timedelta(days=30),
            day_boundary_hour_local=4, now_utc=NOW)
        self._prewarm()
        self.assertEqual([self._payload(backlog=value) for value in (False, True)], raw)
        self.assertEqual(_canonical_future_due_day_counts(user_id=1, timezone_name="UTC", timezone_obj=None,
            start_utc=NOW.replace(hour=4), end_utc=NOW.replace(hour=4) + timedelta(days=30),
            day_boundary_hour_local=4, now_utc=NOW), overview)

    def test_worker_retry_empty_projection_and_bucket_budget(self):
        self.assertTrue(self._prewarm()["published"])
        self.assertTrue(self._prewarm()["cached"])
        self.assertTrue(self._prewarm(force=True)["published"])
        self.assertEqual(db.session.execute(sa.select(sa.func.count()).select_from(
            StudyForecastSnapshot)).scalar_one(), 1)
        empty = self._prewarm(deck_ids=[])
        self.assertEqual(empty["bucket_count"], 0)
        self.assertEqual(service.resolve_forecast_summary(db.session, user_id=1, deck_ids=[],
            timezone_name="UTC", day_boundary_hour=4, now_utc=NOW,
            backlog=True, end_offset=29), ({}, 0, 0.0))
        with self.assertRaises(ValueError):
            self._prewarm(max_buckets=0)

    def test_publication_race_retains_raw_recovery(self):
        original = service.repository.dependency_hash
        calls = []
        def race(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs) if len(calls) == 1 else bytes(32)
        with patch.object(service.repository, "dependency_hash", side_effect=race):
            result = self._prewarm()
        self.assertTrue(result["discarded"])
        self.assertEqual(db.session.execute(sa.select(sa.func.count()).select_from(
            StudyForecastSnapshot)).scalar_one(), 0)

    def test_identity_drift_publishes_what_the_raw_forecast_reads(self):
        subject = db.session.execute(sa.select(StudyProgressSubject)).scalar_one()
        subject.logical_note_key = b"damaged-key"
        db.session.commit()
        raw = self._payload("raw")
        self.assertTrue(self._prewarm()["published"])
        self.assertEqual(self._payload(), raw)

    def test_nullable_deck_content_lifecycle_invalidates_collection(self):
        self._prewarm()
        note_id = self.fixture._note(1, self.fixture.own_type, None)
        db.session.commit()
        self.assertIsNone(service.resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
            timezone_name="UTC", day_boundary_hour=4, now_utc=NOW, backlog=True, end_offset=29))

    def test_additive_migration_preserves_populated_projection_on_rollback(self):
        module = importlib.import_module("migrations.versions.20261013_000064_add_forecast_buckets")
        self._prewarm()
        db.session.remove()
        with db.engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            with patch.object(module, "op", operations):
                module.upgrade()
                with self.assertRaisesRegex(RuntimeError, "Retain populated"):
                    module.downgrade()
        self.assertEqual(db.session.execute(sa.select(sa.func.count()).select_from(
            StudyForecastSnapshot)).scalar_one(), 1)

    def test_failed_publication_keeps_prior_complete_snapshot(self):
        self._prewarm()
        before = db.session.execute(sa.select(StudyForecastDueBucket.__table__)).all()
        subject = db.session.execute(sa.select(StudyProgressSubject)).scalar_one()
        subject.due_day += 1
        db.session.commit()
        original = service.repository.publish_snapshot
        def crash(session, **kwargs):
            original(session, **kwargs)
            raise RuntimeError("crash before projection commit")
        with patch.object(service.repository, "publish_snapshot", side_effect=crash):
            with self.assertRaisesRegex(RuntimeError, "crash before"):
                self._prewarm()
        self.assertEqual(db.session.execute(sa.select(StudyForecastDueBucket.__table__)).all(), before)
        self.assertIsNone(service.resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
            timezone_name="UTC", day_boundary_hour=4, now_utc=NOW, backlog=True, end_offset=29))
        self.assertTrue(self._prewarm()["published"])
        self.assertEqual(self._payload(), self._payload("raw"))

    def test_bucket_budget_failure_publishes_nothing(self):
        note = self.fixture._note(1, self.fixture.own_type, 1)
        self.fixture._state(note, due_day=DAY + 1)
        db.session.commit()
        result = self._prewarm(max_buckets=1)
        self.assertEqual(result["error"], "BUCKET_BUDGET_EXCEEDED")
        self.assertEqual(db.session.execute(sa.select(sa.func.count()).select_from(
            StudyForecastSnapshot)).scalar_one(), 0)

    def test_legacy_installed_timestamp_mutation_invalidates_collection(self):
        from models.deck_install import DeckInstall
        self.fixture._clone(local_deck=3)
        install = db.session.execute(sa.select(DeckInstall)).scalar_one()
        install.version_mode = "legacy_snapshot"
        install.base_snapshot_at = None
        install.applied_release_id = None
        db.session.commit()
        self._prewarm()
        install = db.session.execute(sa.select(DeckInstall)).scalar_one()
        install.installed_at = NOW - timedelta(days=100)
        db.session.commit()
        self.assertIsNone(service.resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
            timezone_name="UTC", day_boundary_hour=4, now_utc=NOW, backlog=True, end_offset=29))


if __name__ == "__main__":
    unittest.main()
