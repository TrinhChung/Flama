"""Integration tests for Marketplace Taxonomy Alembic Migration & CLI."""

import importlib
import unittest
from alembic import op
import sqlalchemy as sa
from app import create_app
from models import db
from app.repositories import marketplace_taxonomy_repository

migration_module = importlib.import_module("migrations.versions.20260827_000022_add_marketplace_taxonomy_tables")
taxonomy_upgrade = migration_module.upgrade
taxonomy_downgrade = migration_module.downgrade


class MarketplaceTaxonomyMigrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
            }
        )
        self.runner = self.app.test_cli_runner()
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_taxonomy_migration_upgrade_and_downgrade(self):
        with self.app.app_context():
            # 1. Downgrade first to test clean creation
            with db.engine.begin() as conn:
                from alembic.migration import MigrationContext
                from alembic.operations import Operations

                ctx = MigrationContext.configure(conn)
                op._proxy = Operations(ctx)

                taxonomy_downgrade()

                inspector = sa.inspect(conn)
                tables_after_drop = inspector.get_table_names()
                self.assertNotIn("taxonomy_domains", tables_after_drop)
                self.assertNotIn("taxonomy_subject_option_maps", tables_after_drop)

                # 2. Upgrade to create tables
                taxonomy_upgrade()

                inspector = sa.inspect(conn)
                tables_after_upgrade = inspector.get_table_names()
                self.assertIn("taxonomy_domains", tables_after_upgrade)
                self.assertIn("taxonomy_subjects", tables_after_upgrade)
                self.assertIn("taxonomy_frameworks", tables_after_upgrade)
                self.assertIn("taxonomy_framework_levels", tables_after_upgrade)
                self.assertIn("taxonomy_options", tables_after_upgrade)
                self.assertIn("taxonomy_subject_option_maps", tables_after_upgrade)

            # 3. Test taxonomy-seed CLI
            res_seed = self.runner.invoke(args=["taxonomy-seed"])
            self.assertEqual(res_seed.exit_code, 0)
            self.assertIn("Taxonomy seeding complete", res_seed.output)

            # 4. Test taxonomy-verify CLI
            res_verify = self.runner.invoke(args=["taxonomy-verify"])
            self.assertEqual(res_verify.exit_code, 0)
            self.assertIn("Taxonomy verification", res_verify.output)

            # 5. Test idempotency (running upgrade again does not crash)
            with db.engine.begin() as conn:
                ctx = MigrationContext.configure(conn)
                op._proxy = Operations(ctx)
                taxonomy_upgrade()

            # 6. Verify data integrity after idempotent upgrade
            domains = marketplace_taxonomy_repository.list_domains()
            self.assertGreaterEqual(len(domains), 5)


if __name__ == "__main__":
    unittest.main()
