"""Durability, ordering, rollback and backfill contracts for history counts."""

import importlib
from datetime import datetime
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import SessionTransaction

from app.services import review_analytics_outbox_service as outbox
from app.services.review_analytics_backfill_service import run_review_analytics_backfill
from app.services.review_analytics_projection_service import (
    ReviewAnalyticsFenceError, flush_review_analytics_deltas, invalidate_review_analytics,
)
from app.services import review_analytics_projection_service as projection
from models import db
from models.review_analytics import DIRTY, ReviewAnalyticsGeneration, ReviewAnalyticsHead
from models.review_analytics_outbox import ReviewAnalyticsOutbox
from models.review_event import ReviewEvent
from tests import test_review_analytics_projection as projection_fixture


class ReviewAnalyticsOutboxTests(unittest.TestCase):
    def setUp(self):
        self.fixture = projection_fixture.ReviewAnalyticsProjectionTests()
        self.fixture.setUp()
        self.app, self.user_id = self.fixture.app, self.fixture.user_id

    def tearDown(self):
        self.fixture.tearDown()

    def _append(self, **values):
        self.fixture._fence()
        event = self.fixture._event(**values)
        flush_review_analytics_deltas(db.session)
        event_id = int(event.id)
        db.session.commit()
        db.session.remove()
        return event_id

    def _drain(self, **values):
        db.session.remove()
        return outbox.process_review_analytics_outbox(user_id=self.user_id, **values)

    def _generation(self):
        return db.session.get(ReviewAnalyticsGeneration, (self.user_id, 1))

    def test_async_source_commit_has_durable_feed_without_bucket_or_generation_locks(self):
        statements = []
        def capture(_connection, _cursor, sql, _params, _context, _many):
            statements.append(sql.upper())
        sa.event.listen(db.engine, "before_cursor_execute", capture)
        try:
            self._append()
        finally:
            sa.event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(self.fixture._counts(), (0, 0, 0))
        self.assertEqual(db.session.get(ReviewAnalyticsHead, self.user_id).source_revision, 1)
        self.assertEqual(self._generation().applied_source_revision, 0)
        row = db.session.get(ReviewAnalyticsOutbox, (self.user_id, 1))
        self.assertIsNone(row.applied_at)
        self.assertEqual(row.event_count, 1)
        self.assertEqual(len(row.payload_hash), 32)
        self.assertFalse(any("DAILY_REVIEW_COUNTS" in sql or "REVIEW_ANALYTICS_GENERATIONS" in sql
                             for sql in statements))

    def test_canonical_insert_uses_frozen_values_without_reloading_raw_event(self):
        with patch.object(projection, "load_inserted_events", side_effect=AssertionError("redundant raw reload")):
            self._append(duration_ms=700, rating="good", deck_id=12)
        self._drain()
        self.assertEqual(self.fixture._counts(), (1, 700, 1))

    def test_exotic_rating_reloads_exact_sql_passed_semantics(self):
        original = projection.load_inserted_events
        with patch.object(projection, "load_inserted_events", wraps=original) as reload:
            self._append(rating="\tgood\n")
        self.assertEqual(reload.call_count, 1)
        self._drain()
        expected = 0 if db.engine.dialect.name == "mysql" else 1
        self.assertEqual(self.fixture._counts(), (1, 1000, expected))

    def test_fractional_timestamp_reloads_before_business_day_grouping(self):
        from app.repositories.review_analytics_backfill_repository import raw_grouped_counts, projected_grouped_counts
        original = projection.load_inserted_events
        with patch.object(projection, "load_inserted_events", wraps=original) as reload:
            self._append(reviewed_at=datetime(2026, 10, 5, 3, 59, 59, 800000))
        self.assertEqual(reload.call_count, 1)
        raw = raw_grouped_counts(db.session, user_id=self.user_id, policy=self.fixture.policy)
        self._drain()
        projected = projected_grouped_counts(db.session, user_id=self.user_id, generation=1)
        self.assertEqual(projected, raw)

    def test_correction_of_just_inserted_event_queues_dirty_without_stale_snapshot(self):
        self.fixture._fence()
        event = self.fixture._event(duration_ms=100)
        db.session.flush()
        event.duration_ms = 500
        db.session.flush()
        with patch.object(projection, "load_inserted_events", side_effect=AssertionError("dirty snapshots must not replay")):
            flush_review_analytics_deltas(db.session)
        db.session.commit()
        row = ReviewAnalyticsOutbox.query.one()
        self.assertTrue(row.is_dirty)
        self.assertEqual(row.events_payload, [])
        self._drain()
        self.assertEqual(self._generation().status, DIRTY)

    def test_feed_insert_failure_rolls_back_advanced_head_and_source_fact(self):
        self.fixture._fence()
        self.fixture._event()
        from app.repositories import review_analytics_outbox_repository as repository
        with patch.object(repository, "insert_outbox_revision", side_effect=RuntimeError("durable feed failed")):
            with self.assertRaisesRegex(RuntimeError, "durable feed failed"):
                flush_review_analytics_deltas(db.session)
        db.session.rollback()
        self.assertEqual(self.fixture._raw_count(), 0)
        self.assertEqual(ReviewAnalyticsOutbox.query.count(), 0)
        self.assertEqual(db.session.get(ReviewAnalyticsHead, self.user_id).source_revision, 0)

    def test_worker_applies_all_scopes_and_idempotent_retry_once(self):
        self._append(duration_ms=700, deck_id=12)
        self._append(duration_ms=-9, rating="hard")
        self._append(duration_ms=None, rating="\tgood\n")
        result = self._drain(limit=2)
        self.assertEqual(result["applied_revisions"], [1, 2])
        self.assertTrue(result["pending"])
        self.assertEqual(self._drain()["applied_revisions"], [3])
        self.assertEqual(self._drain()["applied_revisions"], [])
        # Fixed-offset MySQL raw readers preserve SQL collation semantics and
        # do not Python-strip the whitespace-bearing rating.
        passed = 1 if db.engine.dialect.name == "mysql" else 2
        self.assertEqual(self.fixture._counts(), (3, 700, passed))
        self.assertEqual(self._generation().applied_source_revision, 3)
        from models.review_analytics import DailyReviewCount
        deck = DailyReviewCount.query.filter_by(user_id=self.user_id, generation=1,
                                               scope_kind=1, scope_id=12).one()
        self.assertEqual((deck.review_event_count, deck.positive_duration_ms, deck.passed_review_count), (1, 700, 1))

    def test_inserted_facts_outbox_and_source_revision_rollback_together(self):
        self.fixture._fence()
        self.fixture._event()
        flush_review_analytics_deltas(db.session)
        db.session.rollback()
        self.assertEqual(ReviewAnalyticsOutbox.query.count(), 0)
        self.assertEqual(self.fixture._raw_count(), 0)
        self.assertEqual(db.session.get(ReviewAnalyticsHead, self.user_id).source_revision, 0)

    def test_duplicate_raw_uniqueness_does_not_enqueue_another_revision(self):
        self._append(client_event_id="same-async-client")
        self.fixture._fence()
        self.fixture._event(client_event_id="same-async-client")
        with self.assertRaises(IntegrityError):
            flush_review_analytics_deltas(db.session)
        db.session.rollback()
        self.assertEqual(ReviewAnalyticsOutbox.query.count(), 1)
        self.assertEqual(self._drain()["applied_revisions"], [1])
        self.assertEqual(self.fixture._counts(), (1, 1000, 1))

    def test_new_history_write_after_finalizer_is_refused_and_rolls_back_atomically(self):
        self.fixture._fence()
        self.fixture._event(duration_ms=100)
        flush_review_analytics_deltas(db.session)
        self.fixture._event(duration_ms=200)
        with self.assertRaisesRegex(ReviewAnalyticsFenceError, "cannot follow analytics finalization"):
            flush_review_analytics_deltas(db.session)
        db.session.rollback()
        self.assertEqual(ReviewAnalyticsOutbox.query.count(), 0)
        self.assertEqual(self.fixture._raw_count(), 0)
        self.assertEqual(db.session.get(ReviewAnalyticsHead, self.user_id).source_revision, 0)

    def test_dirty_bulk_marker_after_finalizer_is_refused(self):
        self.fixture._fence()
        self.fixture._event()
        flush_review_analytics_deltas(db.session)
        with self.assertRaisesRegex(ReviewAnalyticsFenceError, "cannot follow analytics finalization"):
            invalidate_review_analytics(db.session, [self.user_id])
        db.session.rollback()
        self.assertEqual(ReviewAnalyticsOutbox.query.count(), 0)

    def test_savepoint_rollback_after_finalizer_does_not_reopen_source_writes(self):
        self.fixture._fence()
        self.fixture._event()
        flush_review_analytics_deltas(db.session)
        savepoint = db.session.begin_nested()
        savepoint.rollback()
        flush_review_analytics_deltas(db.session)  # Remains an idempotent no-op.
        self.assertEqual(ReviewAnalyticsOutbox.query.count(), 1)
        self.fixture._event()
        with self.assertRaisesRegex(ReviewAnalyticsFenceError, "cannot follow analytics finalization"):
            flush_review_analytics_deltas(db.session)
        db.session.rollback()
        self.assertEqual(ReviewAnalyticsOutbox.query.count(), 0)

    def test_released_savepoint_descendant_rollback_discards_feed_events(self):
        self.fixture._fence()
        root = self.fixture._event(duration_ms=100)
        db.session.flush()
        outer = db.session.begin_nested()
        self.fixture._event(duration_ms=99999)
        db.session.flush()
        inner = db.session.begin_nested()
        self.fixture._event(duration_ms=99999)
        db.session.flush()
        inner.commit()
        outer.rollback()
        root_id = int(root.id)
        flush_review_analytics_deltas(db.session)
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self.assertEqual(ReviewAnalyticsOutbox.query.count(), 1)
        self.assertEqual(ReviewAnalyticsOutbox.query.one().events_payload[0]["id"], root_id)
        self.assertEqual(self._drain()["applied_revisions"], [1])
        self.assertEqual(self.fixture._counts(), (1, 100, 1))

    def test_worker_failure_rolls_back_delta_checkpoint_and_applied_marker(self):
        self._append()
        original = outbox.add_grouped_deltas
        def fail_after_delta(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("crash after deltas")
        with patch.object(outbox, "add_grouped_deltas", side_effect=fail_after_delta):
            with self.assertRaisesRegex(RuntimeError, "crash after deltas"):
                self._drain()
        self.assertEqual(self.fixture._counts(), (0, 0, 0))
        self.assertEqual(self._generation().applied_source_revision, 0)
        self.assertIsNone(ReviewAnalyticsOutbox.query.one().applied_at)
        self.assertEqual(self._drain()["applied_revisions"], [1])
        self.assertEqual(self.fixture._counts(), (1, 1000, 1))

    def test_lost_worker_commit_ack_retry_does_not_double_apply(self):
        self._append()
        original = SessionTransaction.commit
        def lost_ack(transaction, *args, **kwargs):
            result = original(transaction, *args, **kwargs)
            if transaction.parent is None:
                raise RuntimeError("lost worker acknowledgement")
            return result
        with patch.object(SessionTransaction, "commit", lost_ack):
            with self.assertRaisesRegex(RuntimeError, "lost worker acknowledgement"):
                self._drain()
        self.assertEqual(self._drain()["applied_revisions"], [])
        self.assertEqual(self.fixture._counts(), (1, 1000, 1))

    def test_missing_revision_fails_closed_dirty(self):
        self._append()
        self._append()
        db.session.delete(db.session.get(ReviewAnalyticsOutbox, (self.user_id, 1)))
        db.session.commit()
        result = self._drain()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "OUTBOX_REVISION_GAP")
        self.assertEqual(self._generation().status, DIRTY)
        self.assertEqual(self.fixture._counts(), (0, 0, 0))

    def test_missing_final_pending_row_does_not_leave_ready_generation(self):
        self._append()
        db.session.delete(ReviewAnalyticsOutbox.query.one())
        db.session.commit()
        self.assertEqual(self._drain()["error"], "OUTBOX_REVISION_GAP")
        self.assertEqual(self._generation().status, DIRTY)

    def test_payload_hash_corruption_fails_closed_dirty(self):
        self._append()
        ReviewAnalyticsOutbox.query.one().payload_hash = b"x" * 32
        db.session.commit()
        result = self._drain()
        self.assertEqual(result["error"], "OUTBOX_PAYLOAD_CORRUPT")
        self.assertEqual(self._generation().status, DIRTY)
        self.assertEqual(self.fixture._counts(), (0, 0, 0))

    def test_dirty_marker_tamper_is_covered_by_envelope_hash(self):
        self._append()
        self._drain()
        self.fixture._fence()
        invalidate_review_analytics(db.session, [self.user_id])
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        row = db.session.get(ReviewAnalyticsOutbox, (self.user_id, 2))
        row.is_dirty = False
        db.session.commit()
        self.assertEqual(self._drain()["error"], "OUTBOX_PAYLOAD_CORRUPT")
        self.assertEqual(self._generation().status, DIRTY)

    def test_commit_revision_applies_low_event_id_after_larger_baseline_id(self):
        self._generation().baseline_high_water_id = 999
        db.session.commit()
        event_id = self._append()
        self.assertLess(event_id, 999)
        self.assertTrue(self._drain()["ok"])
        self.assertEqual(self.fixture._counts(), (1, 1000, 1))

    def test_correction_and_delete_enqueue_dirty_markers(self):
        event_id = self._append()
        self._drain()
        self.fixture._fence()
        db.session.get(ReviewEvent, event_id).duration_ms = 12
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        marker = db.session.get(ReviewAnalyticsOutbox, (self.user_id, 2))
        self.assertTrue(marker.is_dirty)
        self.assertEqual(marker.event_count, 0)
        self.assertTrue(self._drain()["ok"])
        self.assertEqual(self._generation().status, DIRTY)
        self.fixture._fence()
        db.session.delete(db.session.get(ReviewEvent, event_id))
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self.assertTrue(db.session.get(ReviewAnalyticsOutbox, (self.user_id, 3)).is_dirty)

    def test_bulk_mutation_requires_fence_and_queues_dirty_marker(self):
        self._append()
        self.fixture._fence()
        invalidate_review_analytics(db.session, [self.user_id])
        db.session.execute(sa.update(ReviewEvent).where(ReviewEvent.user_id == self.user_id).values(duration_ms=5))
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self._drain()
        self.assertEqual(self._generation().status, DIRTY)

    def test_new_backfill_covers_pending_baseline_without_double_apply(self):
        self._append()
        self._append(duration_ms=2000)
        db.session.remove()
        report = run_review_analytics_backfill(user_id=self.user_id, writer_coverage_enabled=True)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["generation"], 2)
        self._drain()
        generation = db.session.get(ReviewAnalyticsGeneration, (self.user_id, 2))
        self.assertEqual(generation.applied_source_revision, 2)
        from models.review_analytics import DailyReviewCount
        rows = DailyReviewCount.query.filter_by(user_id=self.user_id, generation=2, scope_kind=0).all()
        self.assertEqual(sum(row.review_event_count for row in rows), 2)

    def test_every_source_commit_defers_projection_until_worker(self):
        self._append()
        self._drain()
        self._append()
        self.assertEqual(self._generation().status, 1)
        self.assertEqual(self._generation().applied_source_revision, 1)
        self.assertEqual(self.fixture._counts(), (1, 1000, 1))
        self._drain()
        self.assertEqual(self.fixture._counts(), (2, 2000, 2))

    def test_bounded_worker_user_discovery_and_invalid_arguments(self):
        self._append()
        db.session.remove()
        self.assertEqual(outbox.pending_review_analytics_outbox_users(limit=1), [self.user_id])
        self._drain()
        db.session.remove()
        self.assertEqual(outbox.pending_review_analytics_outbox_users(), [])
        for limit in (0, 101, True):
            with self.assertRaises(ValueError):
                self._drain(limit=limit)

    def test_pending_discovery_serves_oldest_age_before_user_id(self):
        from tests.study_note_fixtures import create_note_user
        from app.repositories.review_analytics_repository import lock_head
        from app.services.review_analytics_outbox_service import stage_review_analytics_outbox
        self._append()
        other = create_note_user(db.session, username="older-feed", email="older-feed@example.invalid")
        db.session.flush()
        other_id = int(other.id)
        head = lock_head(db.session(), other_id)
        head.source_revision = 1
        db.session.flush()
        stage_review_analytics_outbox(db.session(), user_id=other_id, source_revision=1,
            rows=[], dirty=True, now_utc=datetime(2026, 10, 5))
        db.session.commit()
        db.session.remove()
        self.assertGreater(other_id, self.user_id)
        self.assertEqual(outbox.pending_review_analytics_outbox_users(limit=1), [other_id])
        outbox.process_review_analytics_outbox(user_id=other_id)
        self.assertEqual(outbox.pending_review_analytics_outbox_users(limit=1), [self.user_id])

    def test_fairness_migration_accepts_metadata_and_can_restore_index(self):
        migration = importlib.import_module("migrations.versions.20261014_000068_add_review_outbox_fairness")
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        db.session.remove()
        with db.engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            with patch.object(migration, "op", operations):
                migration.upgrade()
                migration.downgrade()
                migration.upgrade()
            indexes = {item["name"]: item["column_names"] for item in sa.inspect(connection).get_indexes(migration.TABLE)}
            self.assertEqual(indexes[migration.INDEX], migration.COLUMNS)

    def test_migration_shape_and_populated_downgrade_guard(self):
        migration = importlib.import_module("migrations.versions.20261014_000065_add_review_analytics_outbox")
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        with db.engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            with patch.object(migration, "op", operations):
                migration.upgrade()  # Exact ORM-created schema is accepted.
        self._append()
        db.session.remove()
        with db.engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            with patch.object(migration, "op", operations), self.assertRaisesRegex(RuntimeError, "Retain populated"):
                migration.downgrade()


if __name__ == "__main__":
    unittest.main()
