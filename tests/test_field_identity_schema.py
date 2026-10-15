"""Field identity expand preserves legacy typed data and guards rollback."""

from datetime import datetime
import importlib
import unittest
from unittest.mock import Mock, patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from app import create_audit_app  # Register application model contracts first.
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType


migration = importlib.import_module("migrations.versions.20261013_000063_expand_field_value_identity")
MODEL_TABLES = {model.__tablename__: model.__table__ for model in (Note, NoteType, MediaAsset)}
NOW = datetime(2026, 10, 13, 1, 2, 3)
VALUES = {"Word": "猫", "literal.dot": ["one", ["two", "<b>three</b>"]], "Null": None,
          "Empty": [], "Undeclared": "retained"}


class FieldIdentitySchemaTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.connection = self.engine.connect()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.connection.close)
        self.metadata = sa.MetaData()
        self.tables = {
            "note_types": sa.Table("note_types", self.metadata,
                sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(255))),
            "notes": sa.Table("notes", self.metadata,
                sa.Column("id", sa.String(36), primary_key=True), sa.Column("note_type_id", sa.String(36)),
                sa.Column("field_values", sa.JSON, nullable=False), sa.Column("updated_at", sa.DateTime)),
            "media_assets": sa.Table("media_assets", self.metadata,
                sa.Column("id", sa.String(36), primary_key=True), sa.Column("note_id", sa.String(36)),
                sa.Column("field_name", sa.String(255), nullable=False), sa.Column("sha256", sa.String(64)),
                sa.UniqueConstraint("note_id", "sha256", "field_name", name="uq_media_assets_note_sha_field")),
        }
        self.metadata.create_all(self.connection)
        self.connection.execute(self.tables["note_types"].insert().values(id="schema", name="Words"))
        self.connection.execute(self.tables["notes"].insert().values(
            id="note", note_type_id="schema", field_values=VALUES, updated_at=NOW))
        self.connection.execute(self.tables["media_assets"].insert().values(
            id="asset", note_id="note", field_name="Audio", sha256="a" * 64))
        self.connection.commit()

    def _run(self, step):
        with patch.object(migration, "op", Operations(MigrationContext.configure(self.connection))):
            getattr(migration, step)()
        self.connection.commit()

    def _legacy_rows(self):
        return {table: self.connection.execute(sa.select(columns)).all()
                for table, columns in self.tables.items()}

    def _assert_contract(self, connection):
        inspector = sa.inspect(connection)
        for table, columns in migration._columns().items():
            reflected = {column["name"]: column for column in inspector.get_columns(table)}
            for column in columns:
                with self.subTest(table=table, column=column.name):
                    actual = reflected[column.name]
                    # Revision63 is frozen historical expand schema; current
                    # models intentionally reflect contracted revision67.
                    declared = column
                    self.assertEqual(actual["type"].compile(dialect=connection.dialect),
                                     declared.type.compile(dialect=connection.dialect))
                    self.assertEqual(actual["nullable"], declared.nullable)
                    self.assertEqual(actual["default"], "'0'" if declared.server_default else None)

    def test_upgrade_preserves_raw_named_payload_and_timestamp_and_is_repeatable(self):
        before = self._legacy_rows()
        raw_before = self.connection.exec_driver_sql("SELECT field_values FROM notes").scalar_one()
        unique_before = sa.inspect(self.connection).get_unique_constraints("media_assets")
        self._run("upgrade")
        self._run("upgrade")
        self._assert_contract(self.connection)
        self.assertEqual(before, self._legacy_rows())
        self.assertEqual(raw_before, self.connection.exec_driver_sql("SELECT field_values FROM notes").scalar_one())
        self.assertEqual(unique_before, sa.inspect(self.connection).get_unique_constraints("media_assets"))
        self.assertEqual(self.connection.exec_driver_sql(
            "SELECT field_values_by_id, field_values_codec, field_values_extras, content_revision FROM notes"
        ).one(), (None, None, None, 0))
        self.assertEqual(self.connection.exec_driver_sql("SELECT field_schema_revision FROM note_types").scalar_one(), 0)
        self.assertIsNone(self.connection.exec_driver_sql("SELECT field_def_id FROM media_assets").scalar_one())

    def test_fresh_model_schema_is_canonical_and_keeps_typed_values(self):
        fresh_engine = sa.create_engine("sqlite:///:memory:")
        self.addCleanup(fresh_engine.dispose)
        metadata = sa.MetaData()
        sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table("decks", metadata, sa.Column("id", sa.Integer, primary_key=True))
        tables = {name: table.to_metadata(metadata) for name, table in MODEL_TABLES.items()}
        with fresh_engine.begin() as connection:
            metadata.create_all(connection)
            self.assertNotIn("field_values", tables["notes"].c)
            connection.execute(tables["note_types"].insert().values(id="schema", user_id=1, name="Words"))
            connection.execute(tables["notes"].insert().values(
                id="note", note_type_id="schema", user_id=1,
                field_values_by_id={"field-1": VALUES["literal.dot"]}, field_values_codec="field-id.v1",
                field_values_extras={"Undeclared": "retained"}))
            row = connection.execute(tables["notes"].select()).mappings().one()
            self.assertEqual(row["field_values_by_id"], {"field-1": VALUES["literal.dot"]})
            self.assertEqual(row["content_revision"], 0)
            self.assertEqual(connection.execute(sa.select(tables["note_types"].c.field_schema_revision)).scalar_one(), 0)
        self.assertFalse(MediaAsset.__table__.c.field_def_id.foreign_keys)

    def test_mysql_historical_expand_and_current_model_column_types_match(self):
        dialect = mysql.dialect()
        for table, columns in migration._columns().items():
            for column in columns:
                with self.subTest(table=table, column=column.name):
                    self.assertEqual(column.type.compile(dialect=dialect),
                                     MODEL_TABLES[table].c[column.name].type.compile(dialect=dialect))

    def test_schema_drift_is_refused_before_any_table_is_expanded(self):
        self.connection.exec_driver_sql("ALTER TABLE note_types ADD COLUMN field_schema_revision INTEGER NOT NULL DEFAULT 0")
        with self.assertRaisesRegex(RuntimeError, "differs"):
            self._run("upgrade")
        self.assertNotIn("content_revision", {column["name"] for column in sa.inspect(self.connection).get_columns("notes")})

    def test_mysql_inherited_collation_is_valid_but_unsigned_revision_is_drift(self):
        inspector = Mock()
        inspector.has_table.return_value = True
        reflected = {}
        for table, columns in migration._columns().items():
            reflected[table] = [
                {"name": column.name, "nullable": column.nullable,
                 "type": mysql.VARCHAR(column.type.length, collation="utf8mb4_unicode_ci")
                         if isinstance(column.type, sa.String) else column.type,
                 "default": "'0'" if column.server_default else None}
                for column in columns
            ]
        inspector.get_columns.side_effect = lambda table: reflected[table]
        bind = Mock(dialect=mysql.dialect())
        with patch.object(migration.sa, "inspect", return_value=inspector):
            migration._inspect_contract(bind)
            reflected["notes"][-1]["type"] = mysql.BIGINT(unsigned=True)
            with self.assertRaisesRegex(RuntimeError, "content_revision differs"):
                migration._inspect_contract(bind)

    def test_missing_table_is_refused_before_other_tables_are_expanded(self):
        self.tables["media_assets"].drop(self.connection)
        with self.assertRaisesRegex(RuntimeError, "requires existing media_assets"):
            self._run("upgrade")
        self.assertNotIn("content_revision", {column["name"] for column in sa.inspect(self.connection).get_columns("notes")})

    def test_unused_expansion_can_be_downgraded_without_changing_legacy_data(self):
        before = self._legacy_rows()
        self._run("upgrade")
        self._run("downgrade")
        self._run("downgrade")
        self.assertEqual(before, self._legacy_rows())
        for table, columns in migration._columns().items():
            existing = {column["name"] for column in sa.inspect(self.connection).get_columns(table)}
            self.assertFalse({column.name for column in columns} & existing)

    def test_downgrade_preserves_any_populated_identity_or_revision_evidence(self):
        self._run("upgrade")
        for table, column, value in (
            ("notes", "field_values_by_id", '{"field-1": []}'),
            ("notes", "field_values_extras", '{"orphan": null}'),
            ("notes", "field_values_codec", "field-id.v1"),
            ("notes", "content_revision", 1),
            ("note_types", "field_schema_revision", 1),
            ("media_assets", "field_def_id", "removed-field-id"),
        ):
            with self.subTest(table=table, column=column):
                self.connection.execute(sa.text(f"UPDATE {table} SET {column}=:value"), {"value": value})
                with self.assertRaisesRegex(RuntimeError, "populated values/revisions"):
                    self._run("downgrade")
                self._assert_contract(self.connection)
                self.connection.exec_driver_sql(f"UPDATE {table} SET {column}=" +
                                                ("0" if column.endswith("revision") else "NULL"))
                self.connection.commit()

    def test_mysql_ddl_is_instant_and_restores_metadata_lock_timeout_on_failure(self):
        inspector = Mock()
        inspector.has_table.return_value = True
        inspector.get_columns.return_value = []
        for fail in (False, True):
            with self.subTest(fail=fail):
                statements = []
                bind = Mock(dialect=mysql.dialect())

                def execute(statement):
                    sql = str(statement)
                    statements.append(sql)
                    if fail and sql.startswith("ALTER TABLE"):
                        raise RuntimeError("INSTANT is unavailable for this table")
                    result = Mock()
                    result.scalar_one.return_value = 123
                    return result

                bind.execute.side_effect = execute
                operations = Mock()
                operations.get_bind.return_value = bind
                with patch.object(migration, "op", operations), patch.object(migration.sa, "inspect", return_value=inspector):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, "INSTANT is unavailable"):
                            migration.upgrade()
                    else:
                        migration.upgrade()
                alters = [sql for sql in statements if sql.startswith("ALTER TABLE")]
                self.assertEqual(len(alters), 1 if fail else 3)
                self.assertTrue(all(sql.endswith("ALGORITHM=INSTANT, LOCK=DEFAULT") for sql in alters))
                self.assertFalse(any("INPLACE" in sql or "COPY" in sql or "UPDATE" in sql for sql in statements))
                self.assertEqual(statements[-1], "SET SESSION lock_wait_timeout = 123")

    def test_mysql_probe_refuses_remote_or_configured_schema_before_connecting(self):
        import os
        from scripts import probe_field_identity_mysql as probe

        token = "a" * 12
        generated = f"flama_field_identity_probe_{os.getpid()}_{token}"
        for host, configured, message in (
            ("db.example.test", "flama", "requires loopback"),
            ("127.0.0.1", generated, "overlaps"),
        ):
            with self.subTest(host=host), patch.object(probe, "load_dotenv"), \
                    patch.object(probe, "_connection_settings", return_value={"host": host}), \
                    patch.object(probe.secrets, "token_hex", return_value=token), \
                    patch.dict(os.environ, {"DB_NAME": configured}), \
                    patch.object(probe.pymysql, "connect") as connect:
                with self.assertRaisesRegex(RuntimeError, message):
                    probe.run()
                connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
