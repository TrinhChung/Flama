"""Atomic daily projection and SAVEPOINT ancestry contracts."""

from datetime import datetime
import unittest
from unittest.mock import patch

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from app import create_audit_app
from app.repositories.review_analytics_repository import lock_head
from app.repositories.review_event_repository import create_review_event_record
from app.repositories.study_authority_repository import lock_study_authority_route
from app.services.review_analytics_policy import ReviewAnalyticsPolicy
from app.services.review_analytics_projection_service import (
    ReviewAnalyticsFenceError, flush_review_analytics_deltas, invalidate_review_analytics,
)
from models import db
from models.review_analytics import DailyReviewCount, ReviewAnalyticsGeneration
from models.review_event import ReviewEvent
from models.user import User


class ReviewAnalyticsProjectionTests(unittest.TestCase):
    def setUp(self):
        self.app = create_audit_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "REVIEW_ANALYTICS_WRITE_ENABLED": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(username="rollup-writer", email="rollup-writer@example.invalid", timezone="UTC")
        db.session.add(user)
        db.session.commit()
        self.user_id = user.id
        db.session.remove()
        self.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = True
        self.policy = ReviewAnalyticsPolicy("UTC", 4)
        self.counter = 0
        self._seed_generation()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _fence(self):
        lock_study_authority_route(db.session, learner_user_id=self.user_id,
                                   allow_note_authority=True)

    def _seed_generation(self):
        self._fence()
        head = lock_head(db.session(), self.user_id)
        head.active_generation = 1
        head.next_generation = 2
        db.session.add(ReviewAnalyticsGeneration(
            user_id=self.user_id, generation=1, policy_hash=self.policy.policy_hash,
            timezone_name=self.policy.timezone_name, day_boundary_hour=4,
            grouping_version=1, timezone_rules_version=self.policy.timezone_rules_version,
            status=1, baseline_high_water_id=0, backfill_cursor_id=0,
            applied_source_revision=0, verified_source_revision=0,
            verification_contract_version=1, verified_at=datetime(2026, 10, 5),
        ))
        flush_review_analytics_deltas(db.session)
        db.session.commit()

    def _event(self, **kwargs):
        self.counter += 1
        values = dict(user_id=self.user_id, card_id=f"test-card-{self.counter}",
                      rating="good", mode="review", reviewed_at=datetime(2026, 10, 5, 12),
                      duration_ms=1000, deck_id=None, note_type_id=None)
        values.update(kwargs)
        return create_review_event_record(**values)

    def _counts(self):
        rows = db.session.execute(select(DailyReviewCount).where(
            DailyReviewCount.user_id == self.user_id, DailyReviewCount.scope_kind == 0,
        )).scalars().all()
        return tuple(sum(int(getattr(row, name)) for row in rows) for name in (
            "review_event_count", "positive_duration_ms", "passed_review_count"))

    def _raw_count(self):
        return db.session.execute(select(func.count()).select_from(ReviewEvent).where(
            ReviewEvent.user_id == self.user_id)).scalar_one()

    def test_text_history_mutation_is_refused(self):
        with self.assertRaises(ReviewAnalyticsFenceError):
            db.session.execute(text("UPDATE review_events SET duration_ms=5 WHERE user_id=1"))
        db.session.rollback()

    def test_unloaded_old_owner_still_requires_its_fence(self):
        self._fence()
        row = self._event()
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        other = User(username="other-rollup", email="other-rollup@example.invalid", timezone="UTC")
        db.session.add(other)
        db.session.commit()
        other_id = other.id
        db.session.rollback()
        db.session.expire(row, ["user_id"])
        row.user_id = other_id
        lock_study_authority_route(db.session, learner_user_id=other_id, allow_note_authority=True)
        with self.assertRaises(ReviewAnalyticsFenceError):
            db.session.flush()
        db.session.rollback()

    def test_primary_key_changes_are_refused(self):
        self._fence()
        row = self._event()
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self._fence()
        row.id += 100
        with self.assertRaises(ReviewAnalyticsFenceError):
            db.session.flush()
        db.session.rollback()

    def test_grouped_measures_and_idempotent_finalization(self):
        self._fence()
        self._event(duration_ms=-9, rating="hard")
        self._event(duration_ms=None, rating="\tgood\n")
        self._event(duration_ms=6000, rating="4")
        flush_review_analytics_deltas(db.session)
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self.assertEqual(self._counts(), (3, 6000, 2))
        self.assertEqual(self._raw_count(), 3)

    def test_released_child_is_discarded_when_enclosing_savepoint_rolls_back(self):
        self._fence()
        self._event()
        # begin_nested flushes pending ROOT work before making the SAVEPOINT.
        outer = db.session.begin_nested()
        self._event(duration_ms=2000)
        db.session.flush()
        inner = db.session.begin_nested()
        self._event(duration_ms=3000)
        db.session.flush()
        inner.commit()
        outer.rollback()
        self._event(duration_ms=4000)
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self.assertEqual(self._raw_count(), 2)
        self.assertEqual(self._counts(), (2, 5000, 2))

    def test_child_rollback_preserves_root_and_retry_buffer(self):
        self._fence()
        self._event(duration_ms=1000)
        db.session.flush()
        child = db.session.begin_nested()
        self._event(duration_ms=99999)
        db.session.flush()
        child.rollback()
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self._fence()
        self._event(duration_ms=2000)
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self.assertEqual(self._counts(), (2, 3000, 2))

    def test_counter_failure_rolls_back_raw_and_generation_revision(self):
        self._fence()
        self._event()
        with patch("app.services.review_analytics_projection_service.add_grouped_deltas",
                   side_effect=RuntimeError("counter failed")):
            with self.assertRaisesRegex(RuntimeError, "counter failed"):
                flush_review_analytics_deltas(db.session)
        db.session.rollback()
        self.assertEqual(self._raw_count(), 0)
        self.assertEqual(self._counts(), (0, 0, 0))
        generation = db.session.get(ReviewAnalyticsGeneration, (self.user_id, 1))
        self.assertEqual(generation.applied_source_revision, 0)

    def test_duplicate_raw_uniqueness_does_not_increment_again(self):
        key = "same-client-event"
        self._fence()
        self._event(client_event_id=key)
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self._fence()
        self._event(client_event_id=key)
        with self.assertRaises(IntegrityError):
            flush_review_analytics_deltas(db.session)
        db.session.rollback()
        self.assertEqual(self._counts(), (1, 1000, 1))

    def test_raw_insert_requires_fence_before_flush(self):
        self._event()
        with self.assertRaisesRegex(ReviewAnalyticsFenceError, "learner fence"):
            db.session.flush()
        db.session.rollback()
        self.assertEqual(self._raw_count(), 0)

    def test_outer_commit_requires_explicit_finalizer(self):
        self._fence()
        self._event()
        db.session.flush()
        with self.assertRaisesRegex(ReviewAnalyticsFenceError, "not finalized"):
            db.session.commit()
        db.session.rollback()
        self.assertEqual(self._raw_count(), 0)

    def test_unflushed_projected_change_is_guarded_and_invalidated(self):
        self._fence()
        row = self._event()
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self._fence()
        row.duration_ms = 8000
        with self.assertRaises(ReviewAnalyticsFenceError):
            db.session.commit()
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        generation = db.session.get(ReviewAnalyticsGeneration, (self.user_id, 1))
        self.assertEqual(generation.status, 2)
        self.assertIsNone(generation.verified_at)

    def test_bulk_projected_mutation_requires_queued_invalidation(self):
        self._fence()
        self._event()
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self._fence()
        statement = update(ReviewEvent).where(ReviewEvent.user_id == self.user_id).values(deck_id=None)
        with self.assertRaisesRegex(ReviewAnalyticsFenceError, "queue generation invalidation"):
            db.session.execute(statement)
        invalidate_review_analytics(db.session, [self.user_id])
        db.session.execute(statement)
        flush_review_analytics_deltas(db.session)
        db.session.commit()
        self.assertEqual(db.session.get(ReviewAnalyticsGeneration, (self.user_id, 1)).status, 2)

    def test_finalizer_inside_savepoint_is_rejected(self):
        self._fence()
        with db.session.begin_nested():
            with self.assertRaisesRegex(ReviewAnalyticsFenceError, "inside a SAVEPOINT"):
                flush_review_analytics_deltas(db.session)


if __name__ == "__main__":
    unittest.main()
