"""Dry-run boundaries and bounded projection jobs through the real CLI."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app import create_app, create_audit_app


class ScalabilityCliTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
            "REDIS_URL": "", "DECK_COUNT_WRITE_ENABLED": False,
            "DECK_COUNT_PREWARM_USER_IDS": [1, 2]})
        self.runner = self.app.test_cli_runner()

    def test_canary_dry_run_never_calls_writers(self):
        with (patch("app.services.deck_count_snapshot_service.prewarm_owned_deck_counts") as deck,
              patch("app.services.forecast_snapshot_service.prewarm_forecast_summary") as forecast):
            result = self.runner.invoke(args=["analytics-counts-prewarm", "--configured"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output)["user_ids"], [1, 2])
        deck.assert_not_called()
        forecast.assert_not_called()

    def test_writer_coverage_is_required_and_learner_scope_is_bounded(self):
        result = self.runner.invoke(args=["analytics-counts-prewarm", "--configured", "--apply"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("covered DECK_COUNT_WRITE_ENABLED", result.output)
        self.app.config["DECK_COUNT_PREWARM_USER_IDS"] = list(range(1, 102))
        result = self.runner.invoke(args=["analytics-counts-prewarm", "--configured"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("1 to 100", result.output)

    def test_applied_job_passes_explicit_budgets_and_reports_failure(self):
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = True
        with patch("app.services.deck_count_snapshot_service.prewarm_owned_deck_counts",
                   return_value={"ok": True, "published": 1}) as deck, \
             patch("app.services.forecast_snapshot_service.prewarm_forecast_summary",
                   return_value={"ok": False, "error": "BUCKET_BUDGET_EXCEEDED"}) as forecast:
            result = self.runner.invoke(args=["analytics-counts-prewarm", "--user-id", "1",
                "--apply", "--max-decks", "7", "--max-buckets", "12"])
        self.assertEqual(result.exit_code, 1)
        deck.assert_called_once_with(user_id=1, force=False, max_decks=7)
        forecast.assert_called_once_with(user_id=1, force=False, max_buckets=12)
        self.assertIn("BUCKET_BUDGET_EXCEEDED", result.output)

    def test_audit_factory_exposes_only_projection_status(self):
        app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "REDIS_URL": ""})
        result = app.test_cli_runner().invoke(args=["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("forecast-summary-status", result.output)
        self.assertNotIn("forecast-summary-prewarm", result.output)
        self.assertNotIn("analytics-counts-prewarm", result.output)
        self.assertIn("review-analytics-outbox-status", result.output)
        self.assertNotIn("review-analytics-drain", result.output)

    def test_history_drain_dry_run_and_rollback_gate(self):
        with patch("app.services.review_analytics_outbox_service.process_review_analytics_outbox") as worker:
            result = self.runner.invoke(args=["review-analytics-drain", "--user-id", "1"])
        self.assertEqual(result.exit_code, 0, result.output)
        worker.assert_not_called()
        with patch("app.services.review_analytics_outbox_service.pending_review_analytics_outbox_users",
                   return_value=[1]):
            blocked = self.runner.invoke(args=["review-analytics-rollback-check", "--writers-quiesced"])
        self.assertEqual(blocked.exit_code, 1)
        self.assertEqual(json.loads(blocked.output)["error"], "ASYNC_HISTORY_PENDING")
        with patch("app.services.review_analytics_outbox_service.pending_review_analytics_outbox_users",
                   return_value=[]):
            ready = self.runner.invoke(args=["review-analytics-rollback-check", "--writers-quiesced"])
        self.assertEqual(ready.exit_code, 0, ready.output)

    def test_history_drain_preserves_oldest_pending_order(self):
        self.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = True
        with patch("app.services.review_analytics_outbox_service.pending_review_analytics_outbox_users",
                   return_value=[8, 3, 5]), \
                patch("app.services.review_analytics_outbox_service.process_review_analytics_outbox",
                      return_value={"ok": True}) as worker:
            result = self.runner.invoke(args=["review-analytics-drain", "--pending", "--apply"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual([call.kwargs["user_id"] for call in worker.call_args_list], [8, 3, 5])

    def test_wsgi_real_entrypoint_boots_without_backfill_or_runtime_db(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="flama-wsgi-scalability-") as temporary:
            env = {**os.environ, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "STARTUP_RUN_MAINTENANCE": "0", "STARTUP_CHECK_DB_CONNECTIVITY": "0",
                "FLASHCARD_MEDIA_UPLOAD_ROOT": temporary,
                "REDIS_URL": "",
                "DECK_COUNT_WRITE_ENABLED": "0", "FORECAST_SUMMARY_READ_MODE": "raw"}
            code = (
                "import wsgi; from sqlalchemy import inspect; from models import db; "
                "context=wsgi.app.app_context(); context.push(); "
                "assert inspect(db.engine).get_table_names()==[]; "
                "assert 'analytics-counts-prewarm' in wsgi.app.cli.commands; "
                "assert wsgi.app.config['FORECAST_SUMMARY_READ_MODE']=='raw'; "
                "db.session.remove(); db.engine.dispose(); context.pop(); print('WSGI_PASS')"
            )
            result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WSGI_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
