import json
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import run_phase4_preflight_bundle as bundle


class Phase4PreflightBundleTests(unittest.TestCase):
    def test_diff_paths_reports_nested_changes(self):
        left = {"a": {"b": [1, 2]}, "same": True}
        right = {"a": {"b": [1, 3], "c": 4}, "same": True}

        self.assertEqual(bundle._diff_paths(left, right), ["$.a.b[1]", "$.a.c"])

    def test_bundle_writes_redacted_repeatability_artifacts(self):
        report = {
            "schema_version": "study-architecture-audit.v5",
            "observed_at": "2026-09-10T03:04:05",
            "phase4_preflight": {
                "connection_safety": {"current_mysql_evidence": True},
                "gate": {
                    "status": "BLOCKED",
                    "blockers": ["study_session_batches_missing_repository_migration"],
                },
            },
            "verdicts": {"exit_code": 2, "overall_status": "BLOCK"},
        }
        secret_uri = "mysql+pymysql://audit:do-not-leak@example/flama"
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "bundle"
            with patch.dict(
                os.environ,
                {bundle.AUDIT_URI_ENV: secret_uri},
                clear=False,
            ), patch.object(
                bundle,
                "_run_once",
                side_effect=[(report, 2, 11), (report, 2, 12)],
            ):
                with redirect_stdout(io.StringIO()):
                    exit_code = bundle.main(
                        [
                            str(output_dir),
                            "--observed-at",
                            "2026-09-10T03:04:05",
                        ]
                    )

            self.assertEqual(exit_code, 2)
            self.assertEqual(
                {path.name for path in output_dir.iterdir()},
                {"run-1.json", "run-2.json", "comparison.json", "SHA256SUMS"},
            )
            comparison = json.loads(
                (output_dir / "comparison.json").read_text(encoding="utf-8")
            )
            self.assertTrue(comparison["deterministic_equal"])
            self.assertEqual(comparison["run_exit_codes"], [2, 2])
            self.assertEqual(comparison["phase4_gate_status"], ["BLOCKED", "BLOCKED"])
            for path in output_dir.iterdir():
                self.assertNotIn(secret_uri, path.read_text(encoding="utf-8"))

    def test_bundle_refuses_non_mysql_uri_before_running(self):
        with tempfile.TemporaryDirectory() as temporary_directory, patch.dict(
            os.environ,
            {bundle.AUDIT_URI_ENV: "sqlite:///:memory:"},
            clear=False,
        ), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            bundle.main([str(Path(temporary_directory) / "bundle")])

        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
