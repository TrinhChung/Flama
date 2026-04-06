"""Tests for bootstrap admin credential resolution."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app.utils.bootstrap_admin import (
    MissingBootstrapAdminCredentials,
    resolve_bootstrap_admin_credentials,
)


class BootstrapAdminCredentialsTests(unittest.TestCase):
    def test_missing_env_raises_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(MissingBootstrapAdminCredentials):
                resolve_bootstrap_admin_credentials()

    def test_explicit_env_values_are_preserved(self):
        with patch.dict(
            os.environ,
            {
                "ADMIN_EMAIL": "owner@example.com",
                "ADMIN_USERNAME": "owner",
                "ADMIN_PASSWORD": "super-secret",
            },
            clear=True,
        ):
            resolved = resolve_bootstrap_admin_credentials()

        self.assertEqual(resolved.email, "owner@example.com")
        self.assertEqual(resolved.username, "owner")
        self.assertEqual(resolved.password, "super-secret")

    def test_username_can_fall_back_to_email_local_part(self):
        with patch.dict(
            os.environ,
            {
                "ADMIN_EMAIL": "owner@example.com",
                "ADMIN_PASSWORD": "super-secret",
            },
            clear=True,
        ):
            resolved = resolve_bootstrap_admin_credentials()

        self.assertEqual(resolved.email, "owner@example.com")
        self.assertEqual(resolved.username, "owner")
        self.assertEqual(resolved.password, "super-secret")


if __name__ == "__main__":
    unittest.main()
