"""Safety gates for the opt-in local MySQL qualification runner."""

import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from sqlalchemy.engine import URL

from scripts import qualify_progress_scalability_mysql as qualification
from scripts import bench_analytics_counts_mysql as benchmark_runner
from scripts.probe_review_analytics_mysql import local_url


class ScalabilityQualificationTests(unittest.TestCase):
    def setUp(self):
        self.url = URL.create("mysql+pymysql", username="fixture_user",
            password="secret${hostile}@:/\\'", host="127.0.0.1", port=3306,
            database="nihongo", query={"charset": "utf8mb4"})

    def test_default_dry_run_opens_no_database_or_subprocess(self):
        arguments = qualification.parser().parse_args([])
        self.assertFalse(arguments.run)
        self.assertGreaterEqual(arguments.repetitions, 10)
        with patch.object(qualification, "local_url", return_value=self.url), \
                patch.object(qualification, "create_engine") as connect, \
                patch.object(qualification.subprocess, "run") as client, \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            self.assertTrue(qualification.run(arguments))
        connect.assert_not_called()
        client.assert_not_called()
        self.assertIn('"status": "DRY_RUN"', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["migration_head"], qualification.HEAD)
        self.assertNotIn("secret", output.getvalue())

    def test_cli_help_is_bounded_and_limits_remain_enforced(self):
        command = qualification.parser()
        self.assertLess(len(command.format_help()), 5000)
        bounds = {"--repetitions": (10, 50), "--prewarm-max-decks": (1, 1000),
                  "--prewarm-max-batches": (1, 100), "--forecast-max-buckets": (1, 65536),
                  "--dashboard-owned-limit": (0, 100)}
        for option, (minimum, maximum) in bounds.items():
            for value in (minimum, maximum):
                with self.subTest(option=option, value=value):
                    command.parse_args([option, str(value)])
            for value in (minimum - 1, maximum + 1, "invalid"):
                with self.subTest(option=option, value=value), \
                        patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
                    command.parse_args([option, str(value)])

    def test_benchmark_cli_keeps_compact_help_and_bounded_work(self):
        command = benchmark_runner.parser()
        self.assertLess(len(command.format_help()), 5000)
        arguments = command.parse_args(["--env-file", "fixture.env", "--forecast-max-buckets", "65536"])
        self.assertEqual(arguments.forecast_max_buckets, 65536)
        for option, value in (("--forecast-max-buckets", "65537"), ("--prewarm-max-decks", "0"),
                              ("--repetitions", "21"), ("--dashboard-owned-limit", "101")):
            with self.subTest(option=option), patch("sys.stderr", new_callable=io.StringIO), \
                    self.assertRaises(SystemExit):
                command.parse_args(["--env-file", "fixture.env", option, value])

    def test_cleanup_requires_exact_generated_name_created_by_this_run(self):
        target = qualification.generated_target()
        qualification.assert_owned_target(target=target, source="nihongo", created_target=target)
        for label, candidate, source, created in (
                ("source_database", "nihongo", "nihongo", "nihongo"),
                ("target_is_source", target, target, target),
                ("not_created", target, "nihongo", None),
                ("another_run", target, "nihongo", qualification.generated_target()),
                ("sql_injection", target + ";DROP DATABASE nihongo", "nihongo", target)):
            with self.subTest(case=label), self.assertRaises(RuntimeError):
                qualification.assert_owned_target(target=candidate, source=source, created_target=created)

    def test_clients_use_env_password_and_lock_free_copy_flags(self):
        dump = qualification.mysql_command(Path("mysqldump.exe"), self.url, dump=True)
        load = qualification.mysql_command(Path("mysql.exe"), self.url, database="fixture")
        self.assertEqual(dump[1], "--no-defaults")
        for flag in ("--single-transaction", "--skip-lock-tables", "--no-tablespaces", "--skip-triggers"):
            self.assertIn(flag, dump)
        self.assertNotIn("--databases", dump)
        self.assertEqual(dump[-1], "nihongo")
        self.assertEqual(load[-1], "fixture")
        self.assertIn("--local-infile=0", load)
        self.assertNotIn(self.url.password, " ".join(dump + load))
        self.assertEqual(qualification._client_environment(self.url)["MYSQL_PWD"], self.url.password)

    def test_private_env_preserves_password_without_dotenv_interpolation(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.env"
            target_url = self.url.set(database=qualification.generated_target())
            with patch.dict("os.environ", {"hostile": "wrong password"}):
                qualification._private_env(path, target_url)
                recovered = local_url(path)
            self.assertEqual(recovered, target_url)

    def test_failed_client_suppresses_sensitive_stderr(self):
        failed = Mock(returncode=1, stderr=b"secret mysql+pymysql://credentials/source")
        with patch.object(qualification.subprocess, "run", return_value=failed), \
                self.assertRaisesRegex(RuntimeError, "exit code 1") as caught:
            qualification._run_client(["mysql.exe"], environment={"MYSQL_PWD": "secret"})
        self.assertNotIn("secret", str(caught.exception))
        self.assertNotIn("credentials", str(caught.exception))

    def test_copy_ddl_normalization_preserves_collation_and_real_schema_changes(self):
        inherited = "id varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL"
        explicit = "id varchar(36) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL"
        self.assertEqual(qualification.canonical_copy_ddl(inherited), qualification.canonical_copy_ddl(explicit))
        self.assertNotEqual(qualification.canonical_copy_ddl(explicit),
            qualification.canonical_copy_ddl(explicit.replace("unicode_ci", "bin")))
        self.assertNotEqual(qualification.canonical_copy_ddl(explicit),
            qualification.canonical_copy_ddl(explicit.replace("varchar(36)", "varchar(255)")))

    def test_copy_parity_rejects_row_or_semantic_ddl_changes(self):
        original = {"mysql_version": "8.0.40", "alembic_revisions": ["62"], "tables": {"notes": {
            "rows": 2, "checksum_sum": 123, "checksum_xor": 19,
            "schema_sha256": "inherited spelling", "copy_schema_sha256": "schema"}}}
        fixture = {**original, "tables": {"notes": {**original["tables"]["notes"],
            "schema_sha256": "explicit spelling"}}}
        self.assertTrue(qualification.copy_matches(original, fixture))
        for field in ("rows", "checksum_sum", "checksum_xor", "copy_schema_sha256"):
            changed = {**fixture, "tables": {"notes": {**fixture["tables"]["notes"], field: "changed"}}}
            self.assertFalse(qualification.copy_matches(original, changed))

    def test_remote_source_is_rejected_before_any_operation(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "remote.env"
            qualification._private_env(path, self.url.set(host="production.example"))
            with self.assertRaisesRegex(ValueError, "loopback"):
                local_url(path)

    def test_read_gates_require_ready_hits_and_keep_scope_and_rollout_limits(self):
        mode = {"dml_statements": 0, "locking_selects": 0, "raw_history_selects": 0,
                "p95_ms": 10, "forecast_cache_coverage": [{"outcome": "hit"}],
                "deck_cache_coverage": [{"hits": 20, "misses": 0}]}
        benchmark = {"source_preserved": True, "metrics": {
            name: {"summary": dict(mode), "exact_payload_parity": True}
            for name in ("overview", "today_future", "study_time_all", "dashboard_compact")}}
        gates = qualification.local_read_gates(benchmark, {"decks": 101})
        self.assertTrue(gates["correctness_passed"])
        self.assertFalse(gates["latency_slos"]["dashboard"]["scope_applicable"])
        self.assertFalse(gates["production_qualified"])
        benchmark["metrics"]["today_future"]["summary"]["forecast_cache_coverage"] = [{"outcome": "miss"}]
        self.assertFalse(qualification.local_read_gates(benchmark, {"decks": 50})["correctness_passed"])

    def test_prewarm_confirms_full_coverage_and_requeues_discarded_publications(self):
        worker = Mock(side_effect=[
            {"ok": True, "eligible": 200, "cached": 0, "computed": 100, "published": 100,
             "has_more": True, "next_after_deck_id": 100},
            {"ok": True, "eligible": 200, "cached": 100, "computed": 100, "published": 0,
             "has_more": False, "next_after_deck_id": 200},
            {"ok": True, "eligible": 200, "cached": 100, "computed": 100, "published": 100,
             "has_more": False, "next_after_deck_id": 200},
            {"ok": True, "eligible": 200, "cached": 200, "computed": 0, "published": 0,
             "has_more": False, "next_after_deck_id": 0},
        ])
        result = benchmark_runner.drain_deck_prewarm(worker, now="clock", max_decks=100, max_batches=20)
        self.assertTrue(result["ready"])
        self.assertEqual(result["cached"], 200)
        self.assertEqual([call.kwargs["after_deck_id"] for call in worker.call_args_list], [0, 100, 0, 0])
        self.assertTrue(all(call.kwargs["max_decks"] == 100 for call in worker.call_args_list))

    def test_prewarm_never_unboundedly_retries_an_invalidated_workload(self):
        worker = Mock(return_value={"ok": True, "eligible": 100, "cached": 0,
            "computed": 100, "published": 0, "has_more": False, "next_after_deck_id": 100})
        result = benchmark_runner.drain_deck_prewarm(worker, now="clock", max_decks=100, max_batches=20)
        self.assertFalse(result["ready"])
        self.assertEqual(worker.call_count, 4)

    def test_bounded_visibility_is_parent_closed_and_rejects_missing_ancestors_and_cycles(self):
        parents = {1: None, 2: 1, 3: 2, 4: 9, 5: 6, 6: 5, 7: None}
        selected = benchmark_runner.parent_closed_selection(parents, set(parents), [4, 5, 3], 3)
        self.assertEqual(selected, [1, 2, 3])
        self.assertTrue(all(parents[node] is None or parents[node] in selected for node in selected))
        self.assertEqual(benchmark_runner.dashboard_node_count({"items": [
            {"children": [{"children": [{"children": []}]}]}]}), 3)


if __name__ == "__main__":
    unittest.main()
