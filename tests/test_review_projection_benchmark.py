"""Verify safe targets and the benchmark's real NOTE transaction evidence."""

import unittest
from unittest.mock import MagicMock, patch

from app import create_audit_app
from models import db
from scripts import bench_review_projection_mysql as benchmark


class ReviewProjectionBenchmarkContractTests(unittest.TestCase):
    def test_only_generated_loopback_schema_is_allowed(self):
        name = "flama_review_projection_probe_123_abcdef123456"
        benchmark._guard_target({"host": "127.0.0.1"}, name, "flama")
        for host, target, source in (("production.example", name, "flama"),
                ("127.0.0.1", "flama", "flama"), ("localhost", name, name),
                ("127.0.0.1", name + "`;DROP DATABASE flama;--", "flama")):
            with self.subTest(host=host, target=target), self.assertRaises(RuntimeError):
                benchmark._guard_target({"host": host}, target, source)

    def test_randomized_blocks_balance_every_execution_position(self):
        for block in range(10):
            rounds = [benchmark._round_order(block * 3 + index) for index in range(3)]
            for position in range(3):
                self.assertEqual({order[position] for order in rounds}, set(benchmark.CASES))
            self.assertEqual(benchmark._round_order(block * 3), rounds[0])
        self.assertNotEqual(benchmark._round_order(0), benchmark._round_order(6))

    def test_percentiles_interpolate_and_keep_signed_added_cost(self):
        self.assertEqual(benchmark._percentile([10, 20, 30, 40], 95), 38.5)
        self.assertEqual(benchmark._distribution([-2, -1, 1])["p50_ms"], -1)

    def test_failed_bootstrap_still_drops_only_captured_generated_schema(self):
        admin = MagicMock()
        cursor = admin.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [None, ("8.0.40", 134217728, "REPEATABLE-READ"), (0,)]
        name = "flama_review_projection_probe_987_abcdef123456"
        with patch.dict(benchmark.os.environ, {"DB_NAME": "flama_fixture_source"}), \
                patch.object(benchmark, "load_dotenv"), \
                patch.object(benchmark, "_connection_settings", return_value={"host": "127.0.0.1",
                    "port": 3306, "user": "fixture_user", "password": ""}), \
                patch.object(benchmark, "_source_database_collation", return_value="utf8mb4_0900_ai_ci"), \
                patch.object(benchmark.os, "getpid", return_value=987), \
                patch.object(benchmark.secrets, "token_hex", return_value="abcdef123456"), \
                patch.object(benchmark.pymysql, "connect", return_value=admin), \
                patch.object(benchmark, "create_audit_app", side_effect=RuntimeError("synthetic boot failure")):
            result = benchmark.run(samples=21, warmup=3)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["error"], "synthetic boot failure")
        self.assertEqual(result["generated_schema"], name)
        self.assertTrue(result["probe_database_dropped"])
        self.assertFalse(result["configured_database_modified"])
        destructive_sql = [call.args[0] for call in cursor.execute.call_args_list
                           if call.args[0].startswith(("CREATE DATABASE", "DROP DATABASE"))]
        self.assertEqual(destructive_sql, [
            f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci",
            f"DROP DATABASE `{name}`"])
        admin.close.assert_called_once()

    def test_real_note_api_keeps_facts_receipts_state_and_projection_parity(self):
        app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "REDIS_URL": "", "REVIEW_ANALYTICS_WRITE_ENABLED": False,
            "DECK_COUNT_WRITE_ENABLED": False, "DECK_COUNT_READ_MODE": "raw",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False})
        with app.app_context():
            db.create_all()
        try:
            result = benchmark._benchmark(app, samples=1, warmup=1)
            self.assertTrue(result["parity"]["exactly_once_and_projection_parity"])
            self.assertTrue(result["parity"]["semantic_hashes_equal_across_cases"])
            evidence = result["parity"]["cases"]
            self.assertEqual(evidence["both"]["collection_daily_totals"], [2, 200, 2])
            self.assertEqual(evidence["both"]["deck_learner_revision"], 2)
            self.assertEqual(evidence["disabled"]["collection_daily_totals"], [0, 0, 0])
            self.assertEqual(evidence["disabled"]["deck_learner_revision"], 0)
            for case in benchmark.CASES:
                metrics = result["metrics"][case]
                self.assertEqual(metrics["samples"], 1)
                sample = metrics["samples_detail"][0]
                self.assertGreater(sample["command_ms"], sample["session_commit_ms"])
                self.assertGreater(sample["api_ms"], sample["command_ms"])
                self.assertEqual(evidence[case]["events"], 2)
                self.assertEqual(evidence[case]["receipts"], 2)
                self.assertTrue(evidence[case]["fractional_native_input_normalized"])
            self.assertNotEqual(benchmark.NOW.microsecond, 0)
            self.assertTrue(result["clock_contract"]["native_command_normalizes_to_seconds"])
        finally:
            with app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()

    def test_real_async_note_summary_is_pending_until_worker_then_exact(self):
        app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "REDIS_URL": "", "REVIEW_ANALYTICS_WRITE_ENABLED": False,
            "DECK_COUNT_WRITE_ENABLED": False, "DECK_COUNT_READ_MODE": "raw"})
        with app.app_context():
            db.create_all()
        try:
            result = benchmark._benchmark(app, samples=1, warmup=1)
            for case in ("history_only", "both"):
                evidence = result["async_worker_evidence"][case]
                self.assertEqual(evidence["pending_rows_before_worker"], 2)
                self.assertEqual(evidence["strict_summary_before_worker_http"], 409)
                self.assertEqual(evidence["strict_summary_after_worker_http"], 200)
                self.assertTrue(evidence["post_worker_raw_summary_exact_parity"])
                self.assertEqual(evidence["worker_reports"][0]["applied_revisions"], [1, 2])
            self.assertTrue(result["parity"]["semantic_hashes_equal_across_cases"])
        finally:
            with app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
