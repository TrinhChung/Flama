"""Fresh upgrades use the actual frozen historical bootstrap, not current models."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from flask_migrate import upgrade
import sqlalchemy as sa

from app import create_audit_app
from migrations.historical_bootstrap_core import HISTORICAL_BOOTSTRAP_METADATA, bootstrap_empty_schema
from models import db


class RetirementFreshMigrationChainTests(unittest.TestCase):
    def test_ci_source_name_exception_is_limited_to_explicit_empty_service(self):
        from scripts.bootstrap_historical_schema import ci_empty_target_allowed
        settings = {"DB_NAME":"ci", "DB_HOST":"127.0.0.1"}
        with patch.dict("os.environ", {"CI":"true", "GITHUB_ACTIONS":"true"}):
            self.assertTrue(ci_empty_target_allowed("ci", settings, requested=True))
            self.assertFalse(ci_empty_target_allowed("ci", settings, requested=False))
            self.assertFalse(ci_empty_target_allowed("nihongo", settings, requested=True))
            self.assertFalse(ci_empty_target_allowed("ci", {**settings,"DB_HOST":"remote.example"}, requested=True))
            self.assertFalse(ci_empty_target_allowed("ci", {**settings,"DB_NAME":"nihongo"}, requested=True))
        with patch.dict("os.environ", {"CI":"true", "GITHUB_ACTIONS":"false"}):
            self.assertFalse(ci_empty_target_allowed("ci", settings, requested=True))

    def test_historical_metadata_is_private_and_keeps_original_card_schema(self):
        self.assertIsNot(HISTORICAL_BOOTSTRAP_METADATA, db.metadata)
        cards = HISTORICAL_BOOTSTRAP_METADATA.tables["cards"]
        self.assertNotIn("application_id", cards.c)
        self.assertEqual(HISTORICAL_BOOTSTRAP_METADATA.tables["card_progress"].c.card_id.type.length, 36)
        self.assertNotIn("study_progress_subjects", HISTORICAL_BOOTSTRAP_METADATA.tables)
        self.assertNotIn("card_presentation_aliases", HISTORICAL_BOOTSTRAP_METADATA.tables)
        self.assertNotIn("owner_user_id", HISTORICAL_BOOTSTRAP_METADATA.tables["templates"].c)

    def test_existing_schema_is_refused_without_mutation(self):
        engine = sa.create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE existing (id INTEGER PRIMARY KEY)")
            with self.assertRaisesRegex(RuntimeError, "entirely empty schema"):
                bootstrap_empty_schema(connection)
            self.assertEqual(sa.inspect(connection).get_table_names(), ["existing"])
        engine.dispose()

    def test_full_flask_migrate_chain_from_frozen_empty_baseline(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "fresh.sqlite"
            app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{path.as_posix()}",
                                    "REDIS_URL": "", "DECK_COUNT_WRITE_ENABLED": False,
                                    "REVIEW_ANALYTICS_WRITE_ENABLED": False})
            with app.app_context():
                try:
                    with db.engine.begin() as connection:
                        self.assertEqual(sa.inspect(connection).get_table_names(), [])
                        bootstrap_empty_schema(connection)
                    # Same migration entry point as `flask --app wsgi.py db upgrade`.
                    upgrade(directory=str(Path(__file__).resolve().parents[1] / "migrations"))
                    tables = set(sa.inspect(db.engine).get_table_names())
                    self.assertEqual(db.session.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one(), "20261012_000062")
                    self.assertEqual(set(db.metadata.tables) - tables, set())
                    self.assertEqual(tables - set(db.metadata.tables), {"alembic_version"})
                    self.assertFalse(tables & {"cards", "card_progress", "vocabulary_column_preferences",
                                              "study_progress_backfill_runs", "study_progress_backfill_checkpoints",
                                              "study_progress_backfill_dispositions"})
                    self.assertTrue({"users", "notes", "study_applications", "study_progress_subjects",
                                     "card_presentation_aliases"} <= tables)
                    self.assertEqual(db.session.execute(sa.text("SELECT COUNT(*) FROM study_progress_subjects")).scalar_one(), 0)
                finally:
                    db.session.remove()
                    db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
