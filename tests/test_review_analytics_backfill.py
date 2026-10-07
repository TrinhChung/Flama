"""Backfill lifecycle, grouped parity, atomic chunks and publication guards."""

from datetime import datetime
import json
import unittest
from unittest.mock import patch

from sqlalchemy import delete, event, select
from sqlalchemy.orm import Session

from app import create_app
from app.repositories import review_analytics_backfill_repository as source
from app.repositories.review_analytics_repository import add_grouped_deltas, lock_generations, lock_head
from app.services import review_analytics_backfill_service as backfill
from app.services.review_analytics_policy import resolve_review_analytics_policy
from models import db
from models.review_analytics import BUILDING, DIRTY, READY, RETIRED, DailyReviewCount, ReviewAnalyticsGeneration, ReviewAnalyticsHead
from models.review_event import ReviewEvent
from models.user import User
from models.user_scheduler_settings import UserSchedulerSettings


class ReviewAnalyticsBackfillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
            "REVIEW_ANALYTICS_WRITE_ENABLED": False, "REDIS_URL": "",
            "REVIEW_ANALYTICS_TIMEZONE_RULES_VERSION": "fixture-rules",
        }, audit_mode=True)

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(username="backfill", email="backfill@example.test", timezone="Asia/Tokyo")
        other = User(username="other", email="other@example.test", timezone="UTC")
        db.session.add_all([user, other])
        db.session.commit()
        self.user_id, self.other_user_id = user.id, other.id
        self.factory = lambda: Session(bind=db.engine, expire_on_commit=False)
        self.args = {"user_id": self.user_id, "writer_coverage_enabled": True, "session_factory": self.factory}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _event(self, *, user_id=None, deck_id=42, when=None, duration_ms=30, rating="good"):
        item = ReviewEvent(user_id=user_id or self.user_id, card_id="historical-card", deck_id=deck_id,
            reviewed_at=when or datetime(2026, 10, 4, 19), duration_ms=duration_ms, rating=rating, mode="review")
        db.session.add(item)
        db.session.commit()
        return int(item.id)

    def _rows(self, generation):
        with self.factory() as session:
            return source.projected_grouped_counts(session, user_id=self.user_id, generation=generation)

    def _copy_all(self, *, chunk_size=500):
        result = backfill.admit_review_analytics_backfill(**self.args)
        while result["ok"] and not result["complete"]:
            result = backfill.copy_review_analytics_backfill_chunk(**self.args, chunk_size=chunk_size)
        return result

    def _tail(self, *, when=None, rating="easy"):
        # Simulate a covered insertion finalizer atomically with its raw row.
        # Real MySQL producer/concurrency tests validate the learner fence.
        with self.factory() as session, session.begin():
            source.lock_backfill_user(session, self.user_id)
            head = lock_head(session, self.user_id)
            generation = lock_generations(session, self.user_id, [head.building_generation])[0]
            item = ReviewEvent(user_id=self.user_id, card_id="tail-card", deck_id=99,
                reviewed_at=when or datetime(2025, 1, 1), duration_ms=12, rating=rating, mode="review")
            session.add(item)
            session.flush()
            rows = source.load_baseline_chunk(session, user_id=self.user_id, cursor=item.id - 1,
                high_water=item.id, limit=1)
            buckets = source.group_baseline_chunk(rows, policy=resolve_review_analytics_policy(session, self.user_id),
                dialect_name="sqlite")
            add_grouped_deltas(session, self.user_id, int(generation.generation), buckets)
            head.source_revision += 1
            generation.applied_source_revision = head.source_revision
            return item.id

    def test_empty_history_can_publish_ready_with_no_daily_rows(self):
        result = backfill.run_review_analytics_backfill(**self.args)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(self._rows(result["generation"]), {})
        json.dumps(result)

    def test_user_id_gaps_and_chunk_resume_count_each_event_once(self):
        self._event()
        self._event(user_id=self.other_user_id)
        self._event(deck_id=None, rating="again", duration_ms=-1)
        admitted = backfill.admit_review_analytics_backfill(**self.args)
        first = backfill.copy_review_analytics_backfill_chunk(**self.args, chunk_size=1)
        self.assertFalse(first["complete"])
        resumed = backfill.admit_review_analytics_backfill(**self.args)
        self.assertTrue(resumed["resumed"])
        self.assertEqual(resumed["generation"], admitted["generation"])
        result = backfill.run_review_analytics_backfill(**self.args, chunk_size=1)
        self.assertEqual(result["status"], "READY")
        collection = [values for key, values in self._rows(result["generation"]).items() if key[0] == 0]
        self.assertEqual(sum(item[0] for item in collection), 2)
        self.assertEqual(sum(item[1] for item in collection), 30)
        self.assertEqual(sum(item[2] for item in collection), 1)

    def test_baseline_and_backdated_live_tail_do_not_overlap(self):
        self._event()
        admitted = backfill.admit_review_analytics_backfill(**self.args)
        tail_id = self._tail()
        self.assertGreater(tail_id, admitted["baseline_high_water_id"])
        copied = self._copy_all(chunk_size=1)
        self.assertEqual(copied["backfill_cursor_id"], admitted["baseline_high_water_id"])
        verified = backfill.verify_review_analytics_backfill(user_id=self.user_id, session_factory=self.factory)
        self.assertTrue(verified["ok"], verified)
        self.assertEqual(sum(v[0] for k, v in self._rows(admitted["generation"]).items() if k[0] == 0), 2)

    def test_failed_chunk_rolls_back_counts_and_cursor_together(self):
        self._event()
        admitted = backfill.admit_review_analytics_backfill(**self.args)
        original = add_grouped_deltas
        def fail_after_deltas(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("lost chunk")
        with patch.object(backfill, "add_grouped_deltas", side_effect=fail_after_deltas):
            with self.assertRaises(RuntimeError):
                backfill.copy_review_analytics_backfill_chunk(**self.args)
        status = backfill.review_analytics_backfill_status(user_id=self.user_id, session_factory=self.factory)
        self.assertEqual(status["backfill_cursor_id"], 0)
        self.assertEqual(self._rows(admitted["generation"]), {})
        result = backfill.run_review_analytics_backfill(**self.args)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(sum(v[0] for k, v in self._rows(result["generation"]).items() if k[0] == 0), 1)

    def test_empty_remaining_baseline_advances_through_deleted_id_gap(self):
        event_id = self._event()
        admitted = backfill.admit_review_analytics_backfill(**self.args)
        db.session.execute(delete(ReviewEvent).where(ReviewEvent.id == event_id))
        db.session.commit()
        result = backfill.copy_review_analytics_backfill_chunk(**self.args)
        self.assertTrue(result["complete"])
        self.assertEqual(result["backfill_cursor_id"], admitted["baseline_high_water_id"])
        self.assertEqual(result["rows_copied"], 0)

    def test_incomplete_baseline_cannot_verify_or_publish(self):
        self._event()
        backfill.admit_review_analytics_backfill(**self.args)
        result = backfill.verify_and_publish_review_analytics_backfill(**self.args)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "BASELINE_INCOMPLETE")
        self.assertIsNone(result["active_generation"])

    def test_exact_oracle_finds_wrong_deck_bucket_with_correct_collection_total(self):
        self._event()
        copied = self._copy_all()
        with self.factory() as session, session.begin():
            row = session.execute(select(DailyReviewCount).where(DailyReviewCount.scope_kind == 1)).scalar_one()
            row.scope_id = 999
        result = backfill.verify_and_publish_review_analytics_backfill(**self.args)
        self.assertEqual(result["error"], "PARITY_MISMATCH")
        self.assertEqual(result["mismatch_count"], 2)
        self.assertEqual(backfill.review_analytics_backfill_status(user_id=self.user_id,
            session_factory=self.factory)["generation"], copied["generation"])
        self.assertIsNone(result["active_generation"])

    def test_oracle_includes_future_history_and_python_whitespace_ratings(self):
        self._event(when=datetime(2024, 2, 29), duration_ms=None, rating="\tgood\n")
        self._event(when=datetime(2035, 1, 1), duration_ms=100, rating="\u00a0 EASY\t")
        result = backfill.run_review_analytics_backfill(**self.args)
        self.assertTrue(result["ok"], result)
        rows = self._rows(result["generation"])
        collection = [v for k, v in rows.items() if k[0] == 0]
        self.assertEqual(sum(v[0] for v in collection), 2)
        self.assertEqual(sum(v[1] for v in collection), 100)
        self.assertEqual(sum(v[2] for v in collection), 2)

    def test_policy_change_marks_dirty_and_requires_new_generation(self):
        self._event()
        admitted = backfill.admit_review_analytics_backfill(**self.args)
        user = db.session.get(User, self.user_id)
        user.timezone = "UTC"
        db.session.commit()
        result = backfill.copy_review_analytics_backfill_chunk(**self.args)
        self.assertEqual(result["status"], "DIRTY")
        self.assertEqual(result["error"], "POLICY_CHANGED")
        self.assertFalse(backfill.admit_review_analytics_backfill(**self.args)["ok"])
        restarted = backfill.admit_review_analytics_backfill(**self.args, restart=True)
        self.assertGreater(restarted["generation"], admitted["generation"])

    def test_dirty_generation_is_never_revived(self):
        self._event()
        admitted = backfill.admit_review_analytics_backfill(**self.args)
        with self.factory() as session, session.begin():
            generation = session.get(ReviewAnalyticsGeneration, (self.user_id, admitted["generation"]))
            generation.status = DIRTY
        result = backfill.copy_review_analytics_backfill_chunk(**self.args)
        self.assertEqual(result["error"], "GENERATION_NOT_BUILDING")
        self.assertEqual(result["backfill_cursor_id"], 0)
        self.assertFalse(backfill.verify_and_publish_review_analytics_backfill(**self.args)["ok"])

    def test_verified_parity_survives_covered_insert_between_verify_and_publish(self):
        self._event()
        self._copy_all()
        original = backfill.verify_review_analytics_backfill
        def verify_then_insert(**kwargs):
            report = original(**kwargs)
            self._tail(when=datetime(2030, 1, 1))
            return report
        with patch.object(backfill, "verify_review_analytics_backfill", side_effect=verify_then_insert):
            result = backfill.verify_and_publish_review_analytics_backfill(**self.args)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["source_revision"], 1)
        self.assertEqual(result["verification"]["verified_source_revision"], 0)
        self.assertEqual(sum(v[0] for k, v in self._rows(result["generation"]).items() if k[0] == 0), 2)

    def test_projected_mutation_after_verification_blocks_publish(self):
        self._event()
        self._copy_all()
        original = backfill.verify_review_analytics_backfill
        def verify_then_invalidate(**kwargs):
            report = original(**kwargs)
            with self.factory() as session, session.begin():
                head = session.get(ReviewAnalyticsHead, self.user_id)
                generation = session.get(ReviewAnalyticsGeneration, (self.user_id, head.building_generation))
                head.source_revision += 1
                generation.status = DIRTY
                generation.verified_source_revision = None
            return report
        with patch.object(backfill, "verify_review_analytics_backfill", side_effect=verify_then_invalidate):
            result = backfill.verify_and_publish_review_analytics_backfill(**self.args)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "DIRTY")
        self.assertIsNone(result["active_generation"])

    def test_missing_live_projection_revision_blocks_verification(self):
        self._event()
        self._copy_all()
        with self.factory() as session, session.begin():
            session.get(ReviewAnalyticsHead, self.user_id).source_revision += 1
        result = backfill.verify_and_publish_review_analytics_backfill(**self.args)
        self.assertEqual(result["error"], "SOURCE_REVISION_NOT_APPLIED")

    def test_publish_replaces_active_pointer_and_retires_previous_generation(self):
        self._event()
        first = backfill.run_review_analytics_backfill(**self.args)
        second = backfill.run_review_analytics_backfill(**self.args, restart=True)
        self.assertGreater(second["generation"], first["generation"])
        with self.factory() as session:
            self.assertEqual(session.get(ReviewAnalyticsGeneration, (self.user_id, first["generation"])).status, RETIRED)
            ready = session.get(ReviewAnalyticsGeneration, (self.user_id, second["generation"]))
            self.assertEqual(ready.status, READY)
            self.assertEqual(ready.verification_contract_version, 1)
            self.assertIsNotNone(ready.verified_at)

    def test_verify_issues_only_reads_and_does_not_hold_user_exclusive(self):
        self._event()
        self._copy_all()
        statements = []
        def record(_conn, _cursor, statement, *_args):
            statements.append(statement)
        event.listen(db.engine, "before_cursor_execute", record)
        try:
            result = backfill.verify_review_analytics_backfill(user_id=self.user_id, session_factory=self.factory)
        finally:
            event.remove(db.engine, "before_cursor_execute", record)
        self.assertTrue(result["ok"], result)
        self.assertTrue(statements)
        self.assertTrue(all(statement.lstrip().upper().startswith("SELECT") for statement in statements), statements)

    def test_session_settings_and_missing_defaults_resolve_on_explicit_session(self):
        with self.factory() as session:
            self.assertEqual(resolve_review_analytics_policy(session, self.user_id).day_boundary_hour, 4)
        db.session.add(UserSchedulerSettings(user_id=self.user_id, day_boundary_hour_local=7))
        db.session.commit()
        with self.factory() as session:
            self.assertEqual(resolve_review_analytics_policy(session, self.user_id).day_boundary_hour, 7)

    def test_backfill_refuses_uncovered_writers_before_opening_session(self):
        with patch.object(backfill, "_fresh_session", side_effect=AssertionError("opened session")):
            with self.assertRaises(RuntimeError):
                backfill.admit_review_analytics_backfill(**{**self.args, "writer_coverage_enabled": False})

    def test_backfill_refuses_request_transaction_without_rolling_it_back(self):
        with self.factory() as session:
            session.begin()
            with self.assertRaises(RuntimeError):
                backfill.admit_review_analytics_backfill(**{**self.args, "session_factory": lambda: session})
            self.assertTrue(session.in_transaction())

    def test_unsupported_nonpositive_attribution_refuses_admission_without_head(self):
        self._event(deck_id=0)
        result = backfill.admit_review_analytics_backfill(**self.args)
        self.assertEqual(result["error"], "UNSUPPORTED_DECK_ATTRIBUTION")
        with self.factory() as session:
            self.assertIsNone(session.get(ReviewAnalyticsHead, self.user_id))

    def test_max_chunks_pauses_before_complete_then_resumes(self):
        for _ in range(3):
            self._event()
        paused = backfill.run_review_analytics_backfill(**self.args, chunk_size=1, max_chunks=1)
        self.assertEqual(paused["status"], "BUILDING")
        self.assertFalse(paused["complete"])
        self.assertEqual(paused["chunks_run"], 1)
        ready = backfill.run_review_analytics_backfill(**self.args, chunk_size=1)
        self.assertEqual(ready["status"], "READY")
        self.assertEqual(ready["generation"], paused["generation"])

    def test_old_verification_cannot_publish_restarted_generation(self):
        self._event()
        copied = self._copy_all()
        original = backfill.verify_review_analytics_backfill
        def verify_then_restart(**kwargs):
            report = original(**kwargs)
            backfill.admit_review_analytics_backfill(**self.args, restart=True)
            return report
        with patch.object(backfill, "verify_review_analytics_backfill", side_effect=verify_then_restart):
            result = backfill.verify_and_publish_review_analytics_backfill(**self.args)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "BUILDING_POINTER_CHANGED")
        self.assertGreater(result["building_generation"], copied["generation"])
        self.assertIsNone(result["active_generation"])

    def test_policy_change_after_verification_blocks_publication(self):
        self._event()
        self._copy_all()
        original = backfill.verify_review_analytics_backfill
        def verify_then_change_policy(**kwargs):
            report = original(**kwargs)
            db.session.get(User, self.user_id).timezone = "UTC"
            db.session.commit()
            return report
        with patch.object(backfill, "verify_review_analytics_backfill", side_effect=verify_then_change_policy):
            result = backfill.verify_and_publish_review_analytics_backfill(**self.args)
        self.assertEqual(result["error"], "POLICY_CHANGED")
        self.assertEqual(result["status"], "DIRTY")
        self.assertIsNone(result["active_generation"])

    def test_exact_oracle_checks_duration_and_passed_not_only_count(self):
        self._event()
        self._copy_all()
        with self.factory() as session, session.begin():
            row = session.execute(select(DailyReviewCount).where(DailyReviewCount.scope_kind == 0)).scalar_one()
            row.positive_duration_ms += 1
            row.passed_review_count = 0
        result = backfill.verify_and_publish_review_analytics_backfill(**self.args)
        self.assertEqual(result["error"], "PARITY_MISMATCH")
        self.assertEqual(result["mismatch_count"], 1)
        mismatch = result["mismatches"][0]
        self.assertEqual(mismatch["raw"][0], mismatch["projected"][0])
        self.assertNotEqual(mismatch["raw"][1:], mismatch["projected"][1:])

    def test_reconcile_checks_active_ready_generation_without_mutating_status(self):
        self._event()
        ready = backfill.run_review_analytics_backfill(**self.args)
        result = backfill.reconcile_review_analytics_counts(user_id=self.user_id, session_factory=self.factory)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["generation"], ready["generation"])

    def test_audit_cli_registers_only_readonly_review_commands(self):
        self.assertIn("review-analytics-status", self.app.cli.commands)
        self.assertIn("review-analytics-reconcile", self.app.cli.commands)
        self.assertNotIn("review-analytics-backfill", self.app.cli.commands)

    def _enable_cli_backfill(self):
        from app.cli import register_review_analytics_commands
        original = dict(self.app.cli.commands)
        self.addCleanup(setattr, self.app.cli, "commands", original)
        register_review_analytics_commands(self.app, allow_writes=True)
        return self.app.test_cli_runner()

    def test_cli_dryrun_is_readonly_and_apply_requires_covered_writers(self):
        runner = self._enable_cli_backfill()
        arguments = ["review-analytics-backfill", "--user-id", str(self.user_id)]
        result = runner.invoke(args=arguments)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(json.loads(result.output)["dry_run"])
        with self.factory() as session:
            self.assertIsNone(session.get(ReviewAnalyticsHead, self.user_id))
        rejected = runner.invoke(args=arguments + ["--apply"])
        self.assertNotEqual(rejected.exit_code, 0)
        self.assertIn("REVIEW_ANALYTICS_WRITE_ENABLED", rejected.output)

    def test_cli_can_resume_bounded_apply_then_readonly_reconcile(self):
        for _ in range(3):
            self._event()
        runner = self._enable_cli_backfill()
        self.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = True
        self.addCleanup(self.app.config.__setitem__, "REVIEW_ANALYTICS_WRITE_ENABLED", False)
        arguments = ["review-analytics-backfill", "--user-id", str(self.user_id), "--apply", "--chunk-size", "1"]
        paused = runner.invoke(args=arguments + ["--max-chunks", "1"])
        self.assertEqual(paused.exit_code, 0, paused.output)
        self.assertFalse(json.loads(paused.output)["complete"])
        ready = runner.invoke(args=arguments)
        self.assertEqual(ready.exit_code, 0, ready.output)
        self.assertEqual(json.loads(ready.output)["status"], "READY")
        reconciled = runner.invoke(args=["review-analytics-reconcile", "--user-id", str(self.user_id)])
        self.assertEqual(reconciled.exit_code, 0, reconciled.output)
        self.assertEqual(json.loads(reconciled.output)["mismatch_count"], 0)

    def _corrupt_ready_duration(self):
        ready = backfill.run_review_analytics_backfill(**self.args)
        with self.factory() as session, session.begin():
            row = session.execute(select(DailyReviewCount).where(DailyReviewCount.scope_kind == 0,
                DailyReviewCount.generation == ready["generation"])).scalar_one()
            row.positive_duration_ms += 1
        return ready

    def test_reconcile_drift_invalidation_forces_raw_without_source_revision_change(self):
        self._event()
        ready = self._corrupt_ready_duration()
        readonly = backfill.reconcile_review_analytics_counts(user_id=self.user_id, session_factory=self.factory)
        self.assertEqual(readonly["error"], "PARITY_MISMATCH")
        self.assertEqual(readonly["status"], "READY")
        with self.factory() as session:
            self.assertEqual(session.get(ReviewAnalyticsGeneration, (self.user_id, ready["generation"])).status, READY)
        dirty = backfill.reconcile_review_analytics_counts(**self.args, invalidate_on_drift=True)
        self.assertEqual(dirty["status"], "DIRTY")
        self.assertEqual(dirty["drift_invalidation"], "DIRTY")
        self.assertEqual(dirty["source_revision"], ready["source_revision"])
        with self.factory() as session:
            generation = session.get(ReviewAnalyticsGeneration, (self.user_id, ready["generation"]))
            self.assertIsNone(generation.verified_source_revision)
            self.assertIsNone(generation.verification_contract_version)
            self.assertIsNone(generation.verified_at)

    def test_drift_invalidation_does_not_dirty_a_newly_published_healthy_generation(self):
        self._event()
        original_ready = self._corrupt_ready_duration()
        original = backfill._verify_review_analytics_counts
        rebuilt = False
        def verify_then_rebuild(**kwargs):
            nonlocal rebuilt
            report = original(**kwargs)
            if not rebuilt:
                rebuilt = True
                backfill.run_review_analytics_backfill(**self.args, restart=True)
            return report
        with patch.object(backfill, "_verify_review_analytics_counts", side_effect=verify_then_rebuild):
            report = backfill.reconcile_review_analytics_counts(**self.args, invalidate_on_drift=True)
        self.assertEqual(report["drift_invalidation"], "SKIPPED")
        self.assertEqual(report["invalidation_error"], "STALE_DRIFT_REPORT")
        with self.factory() as session:
            head = session.get(ReviewAnalyticsHead, self.user_id)
            self.assertGreater(head.active_generation, original_ready["generation"])
            self.assertEqual(session.get(ReviewAnalyticsGeneration, (self.user_id, head.active_generation)).status, READY)

    def test_audit_cli_refuses_drift_write_option_even_with_writer_config_enabled(self):
        self.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = True
        self.addCleanup(self.app.config.__setitem__, "REVIEW_ANALYTICS_WRITE_ENABLED", False)
        result = self.app.test_cli_runner().invoke(args=["review-analytics-reconcile", "--user-id",
            str(self.user_id), "--invalidate-on-drift"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Audit apps cannot invalidate", result.output)


if __name__ == "__main__":
    unittest.main()
