"""Startup maintenance configuration tests."""

import os
from pathlib import Path
import tempfile
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

    def test_testing_uses_isolated_media_root_instead_of_runtime_storage(self):
        with tempfile.TemporaryDirectory() as runtime_root, tempfile.TemporaryDirectory() as test_root:
            with patch.dict(
                os.environ,
                {
                    "FLASHCARD_MEDIA_UPLOAD_ROOT": runtime_root,
                    "FLAMA_TEST_MEDIA_UPLOAD_ROOT": test_root,
                },
            ):
                app = self._create_test_app()

        self.assertEqual(
            Path(app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve(),
            Path(test_root).resolve(),
        )
        self.assertNotEqual(
            Path(app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve(),
            Path(runtime_root).resolve(),
        )

    def test_testing_disables_daily_rate_limit_unless_explicitly_enabled(self):
        default_app = self._create_test_app()
        enabled_app = self._create_test_app(RATE_LIMIT_DAILY_ENABLED=True)

        self.assertFalse(default_app.config["RATE_LIMIT_DAILY_ENABLED"])
        self.assertTrue(enabled_app.config["RATE_LIMIT_DAILY_ENABLED"])

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

    def test_production_defaults_disable_startup_schema_mutation(self):
        with (
            patch("app.startup.ensure_backward_compatible_schema") as ensure_compat,
            patch("app.startup.ensure_user_management_schema") as ensure_user_mgmt,
            patch("app.startup.db.create_all") as create_all,
            patch("app.startup.db.session.execute") as execute_sql,
        ):
            app = create_app(
                {
                    "TESTING": False,
                    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                    "WTF_CSRF_ENABLED": False,
                }
            )

        self.assertFalse(app.config["STARTUP_RUN_MAINTENANCE"])
        self.assertFalse(app.config["STARTUP_RUN_DB_CREATE_ALL"])
        self.assertFalse(app.config["STARTUP_RUN_USER_MANAGEMENT_SCHEMA"])
        self.assertFalse(app.config["STARTUP_RUN_BACKWARD_COMPAT_SCHEMA"])
        self.assertTrue(app.config["STARTUP_CHECK_DB_CONNECTIVITY"])

        # Schema mutation functions must NOT be called on production boot
        ensure_compat.assert_not_called()
        ensure_user_mgmt.assert_not_called()
        create_all.assert_not_called()
        execute_sql.assert_called()


if __name__ == "__main__":
    unittest.main()
