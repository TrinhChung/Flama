import gzip
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.probe_p9_backup_restore_mysql import inspect_dump, validate_target, _option


class StudyBackupRestoreProbeTests(unittest.TestCase):
    def test_probe_refuses_remote_and_configured_database_targets(self):
        with self.assertRaises(ValueError):
            validate_target({"host": "production.example"}, "flama_p9_restore_123_abcdef01")
        with self.assertRaises(ValueError):
            validate_target({"host": "localhost"}, "flama")
        with mock.patch.dict("os.environ", {"DB_NAME": "flama_p9_restore_123_abcdef01"}):
            with self.assertRaises(ValueError):
                validate_target({"host": "localhost"}, "flama_p9_restore_123_abcdef01")

    def test_dump_validation_refuses_schema_switch_and_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dump.sql.gz"
            for command in (b"USE flama;\n", b"CREATE DATABASE flama;\n", b"/*!32312 CREATE DATABASE flama */;\n"):
                with gzip.open(path, "wb") as output:
                    output.write(command + b"-- Dump completed on 2026-10-02\n")
                with self.assertRaises(ValueError):
                    inspect_dump(path)
            with gzip.open(path, "wb") as output:
                output.write(b"CREATE TABLE example(id int);\n")
            with self.assertRaises(ValueError):
                inspect_dump(path)
            with gzip.open(path, "wb") as output:
                output.write(b"-- CHANGE REPLICATION SOURCE TO SOURCE_LOG_FILE='binlog.001', SOURCE_LOG_POS=99;\n-- Dump completed on 2026-10-02\n")
            report = inspect_dump(path)
            self.assertEqual(len(report["backup_sha256"]), 64)
            self.assertIn("SOURCE_LOG_POS=99", report["binlog_watermark"])

    def test_credentials_are_escaped_as_options_without_shell_interpolation(self):
        self.assertEqual(_option('p"a\\ss\nword'), '"p\\"a\\\\ss\\nword"')
