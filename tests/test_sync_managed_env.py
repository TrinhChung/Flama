"""Tests for GitHub-managed production environment synchronization."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "deploy" / "sync_managed_env.py"
SPEC = importlib.util.spec_from_file_location("sync_managed_env", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
sync_managed_env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_managed_env)


class SyncManagedEnvironmentTests(unittest.TestCase):
    def _managed_values(self) -> dict[str, str]:
        return {
            "ADMIN_EMAIL": "admin@example.com",
            "ADMIN_PASSWORD": "password with spaces and \"quotes\"",
            "ADMIN_USER": "admin",
            "PAYOS_API_KEY": "payos-api-key",
            "PAYOS_CHECKSUM_KEY": "payos-checksum-key",
            "PAYOS_CLIENT_ID": "payos-client-id",
        }

    def test_build_and_apply_updates_only_managed_keys(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_path = Path(temporary_directory)
            payload_path = temp_path / "managed.json"
            environment_path = temp_path / "flama.env"
            environment_path.write_text(
                "DB_HOST=127.0.0.1\n"
                "ADMIN_EMAIL=old@example.com\n"
                "PAYOS_CLIENT_ID=old-client\n",
                encoding="utf-8",
            )
            os.chmod(environment_path, 0o640)

            with patch.dict(os.environ, self._managed_values(), clear=False):
                sync_managed_env.build_payload(payload_path)

            changed_keys = sync_managed_env.apply_payload(
                environment_path=environment_path,
                payload_path=payload_path,
            )
            content = environment_path.read_text(encoding="utf-8")

            self.assertEqual(set(changed_keys), set(sync_managed_env.MANAGED_ENV_KEYS))
            self.assertIn("DB_HOST=127.0.0.1\n", content)
            self.assertIn('ADMIN_EMAIL="admin@example.com"\n', content)
            self.assertIn('ADMIN_PASSWORD="password with spaces and \\"quotes\\""\n', content)
            self.assertIn('PAYOS_CLIENT_ID="payos-client-id"\n', content)
            if os.name != "nt":
                self.assertEqual(os.stat(environment_path).st_mode & 0o777, 0o640)

    def test_apply_is_idempotent_and_removes_duplicate_managed_keys(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_path = Path(temporary_directory)
            payload_path = temp_path / "managed.json"
            environment_path = temp_path / "flama.env"

            with patch.dict(os.environ, self._managed_values(), clear=False):
                sync_managed_env.build_payload(payload_path)

            environment_path.write_text("DB_NAME=flama\nADMIN_USER=old\nADMIN_USER=duplicate\n", encoding="utf-8")
            first_changed_keys = sync_managed_env.apply_payload(
                environment_path=environment_path,
                payload_path=payload_path,
            )
            first_content = environment_path.read_text(encoding="utf-8")
            second_changed_keys = sync_managed_env.apply_payload(
                environment_path=environment_path,
                payload_path=payload_path,
            )

            self.assertIn("ADMIN_USER", first_changed_keys)
            self.assertEqual(first_content.count("ADMIN_USER="), 1)
            self.assertEqual(second_changed_keys, [])
            self.assertEqual(environment_path.read_text(encoding="utf-8"), first_content)

    def test_build_rejects_missing_secret_without_writing_payload(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            payload_path = Path(temporary_directory) / "managed.json"
            values = self._managed_values()
            values["PAYOS_API_KEY"] = ""

            with patch.dict(os.environ, values, clear=False):
                with self.assertRaises(sync_managed_env.ManagedEnvironmentError):
                    sync_managed_env.build_payload(payload_path)

            self.assertFalse(payload_path.exists())


if __name__ == "__main__":
    unittest.main()
