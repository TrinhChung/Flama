"""Deployment cutover boundaries and old-binary rollback safety."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import sqlalchemy as sa

from deploy.check_field_code_rollback import check_field_code_rollback
from deploy.migrate_database import migrate_database


class FieldIdentityDeployTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")

    def tearDown(self):
        self.engine.dispose()

    def _schema(self, *, named):
        metadata = sa.MetaData()
        columns = [sa.Column("id", sa.String(36), primary_key=True),
                   sa.Column("field_values_by_id", sa.JSON())]
        if named:
            columns.append(sa.Column("field_values", sa.JSON()))
        sa.Table("notes", metadata, *columns)
        metadata.create_all(self.engine)

    def test_migration_refuses_unquiesced_writers_before_app_or_db_access(self):
        app = Mock()
        with self.assertRaisesRegex(ValueError, "Stop all"), \
                patch("flask_migrate.upgrade") as upgrade:
            migrate_database(app)
        app.app_context.assert_not_called()
        upgrade.assert_not_called()

    def test_pre_contract_schema_allows_old_binary_and_check_is_read_only(self):
        self._schema(named=True)
        self.assertTrue(check_field_code_rollback(self.engine)["ok"])
        self.assertIn("field_values", {item["name"] for item in sa.inspect(self.engine).get_columns("notes")})

    def test_contracted_schema_refuses_old_and_unknown_release(self):
        self._schema(named=False)
        self.assertFalse(check_field_code_rollback(self.engine)["ok"])
        with TemporaryDirectory() as temporary:
            release = Path(temporary)
            (release / "models").mkdir()
            (release / "models" / "note.py").write_text('field_values = "named storage"', encoding="utf-8")
            self.assertFalse(check_field_code_rollback(self.engine, previous_release=release)["ok"])

    def test_only_declared_canonical_release_can_run_after_contraction(self):
        self._schema(named=False)
        with TemporaryDirectory() as temporary:
            release = Path(temporary)
            (release / "models").mkdir()
            (release / "app" / "services").mkdir(parents=True)
            (release / "models" / "note.py").write_text('LIVE_FIELD_VALUE_CODEC = "field-id.v1"', encoding="utf-8")
            self.assertFalse(check_field_code_rollback(self.engine, previous_release=release)["ok"])
            (release / "app" / "services" / "field_value_runtime_service.py").write_text("# canonical resolver", encoding="utf-8")
            self.assertTrue(check_field_code_rollback(self.engine, previous_release=release)["ok"])


if __name__ == "__main__":
    unittest.main()
