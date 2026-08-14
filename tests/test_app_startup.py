"""Startup maintenance configuration tests."""

import os
import unittest
from unittest.mock import patch

from app import create_app


class AppStartupTests(unittest.TestCase):
    def _create_test_app(self, **overrides):
        config = {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
        config.update(overrides)
        return create_app(config)

    def test_startup_does_not_run_seeds_or_cutover_by_default(self):
        with (
            patch("app.startup.ensure_default_user_roles") as ensure_roles,
            patch("app.startup.ensure_default_tts_providers") as ensure_tts,
            patch("app.startup.flashcards_share.cutover_clone_model_to_overlay_only") as cutover,
        ):
            app = self._create_test_app(
                STARTUP_RUN_DEFAULT_USER_ROLE_SEED=False,
                STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED=False,
                STARTUP_RUN_CLONE_CUTOVER=False,
            )

        self.assertFalse(app.config["STARTUP_RUN_DEFAULT_USER_ROLE_SEED"])
        self.assertFalse(app.config["STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED"])
        self.assertFalse(app.config["STARTUP_RUN_CLONE_CUTOVER"])
        ensure_roles.assert_not_called()
        ensure_tts.assert_not_called()
        cutover.assert_not_called()

    def test_startup_maintenance_cli_forces_explicit_run_with_overrides(self):
        app = self._create_test_app(STARTUP_RUN_MAINTENANCE=False)
        runner = app.test_cli_runner()

        with patch("app.cli.run_startup_maintenance") as startup_maintenance:
            result = runner.invoke(
                args=[
                    "startup-maintenance",
                    "--skip-db-create-all",
                    "--skip-clone-cutover",
                    "--no-fail-on-mismatch",
                ]
            )

        self.assertEqual(result.exit_code, 0, msg=result.output)
        startup_maintenance.assert_called_once()
        kwargs = startup_maintenance.call_args.kwargs
        self.assertIn("config_overrides", kwargs)
        self.assertTrue(kwargs["config_overrides"]["STARTUP_RUN_MAINTENANCE"])
        self.assertFalse(kwargs["config_overrides"]["STARTUP_RUN_DB_CREATE_ALL"])
        self.assertFalse(kwargs["config_overrides"]["STARTUP_RUN_CLONE_CUTOVER"])
        self.assertFalse(kwargs["config_overrides"]["STARTUP_CUTOVER_FAIL_ON_MISMATCH"])


if __name__ == "__main__":
    unittest.main()
