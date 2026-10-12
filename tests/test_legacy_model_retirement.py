"""R1 contraction preserves archived backfill evidence and historical imports."""

from datetime import datetime
import importlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app.services.study_progress_contract import BACKFILL_RUN_KINDS, BACKFILL_STATUSES, BACKFILL_SOURCE_KINDS, BACKFILL_DISPOSITIONS
from migrations.retired_backfill_tables import RETIRED_BACKFILL_METADATA
from migrations.retirement_archive import ARCHIVE_ENV, DEAD_MODEL_TABLES, _column_descriptor, _restore_type, assert_archive_matches, load_bundle, verify_restore, write_bundle

migration = importlib.import_module("migrations.versions.20261012_000059_retire_unused_backfill_models")
NOW = datetime(2026, 10, 12, 1, 2, 3, 123456)


class LegacyModelRetirementTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.bundle = Path(self.temp.name) / "archive.json"
        self.engine = sa.create_engine("sqlite:///:memory:")
        sa.event.listen(self.engine, "connect", lambda connection, record: connection.execute("PRAGMA foreign_keys=ON"))
        metadata = sa.MetaData()
        for table in RETIRED_BACKFILL_METADATA.sorted_tables:
            table.to_metadata(metadata)
        sa.Table("vocabulary_column_preferences", metadata,
                 sa.Column("id", sa.Integer, primary_key=True),
                 sa.Column("user_id", sa.Integer, nullable=False),
                 sa.Column("column_key", sa.String(64), nullable=False),
                 sa.Column("width", sa.String(32), nullable=False),
                 sa.Column("updated_at", sa.DateTime, nullable=False))
        metadata.create_all(self.engine)
        self.tables = metadata.tables

    def tearDown(self):
        op._proxy = None
        self.engine.dispose()
        self.temp.cleanup()

    def _seed(self):
        run = self.tables["study_progress_backfill_runs"]
        data = {}
        for column in run.columns:
            if column.nullable:
                data[column.name] = None
            elif isinstance(column.type, sa.DateTime):
                data[column.name] = NOW
            elif isinstance(column.type, sa.LargeBinary):
                data[column.name] = b"h" * 32
            elif isinstance(column.type, sa.Integer):
                data[column.name] = 0
            else:
                data[column.name] = "v1"
        data.update(id="run-1", run_kind=next(iter(BACKFILL_RUN_KINDS)), status_code=next(iter(BACKFILL_STATUSES)), repository_commit="a" * 40)
        with self.engine.begin() as connection:
            connection.execute(run.insert(), data)
            connection.execute(self.tables["study_progress_backfill_checkpoints"].insert(), {
                "run_id": "run-1", "shard_no": 0, "status_code": next(iter(BACKFILL_STATUSES)), "updated_at": NOW})
            connection.execute(self.tables["study_progress_backfill_dispositions"].insert(), {
                "id": 1, "run_id": "run-1", "source_kind": next(iter(BACKFILL_SOURCE_KINDS)),
                "source_row_key": b"source-1", "source_hash": b"s" * 32,
                "disposition_code": next(iter(BACKFILL_DISPOSITIONS)),
                "evidence_payload": {"nested": ["\u65e5\u672c\u8a9e", {"kind": "bytes", "value": "unaltered-json"}]},
                "evidence_payload_size": 128, "evidence_payload_hash": b"e" * 32,
                "created_at": NOW, "updated_at": NOW})

    def _archive(self, verified=True):
        with self.engine.connect() as connection:
            write_bundle(connection, self.bundle)
        if verified:
            restore = sa.create_engine(sa.URL.create("sqlite", database=str(Path(self.temp.name) / "restore.sqlite")))
            with restore.connect() as connection:
                verify_restore(connection, self.bundle)
            restore.dispose()

    def _run(self, method="upgrade"):
        with self.engine.begin() as connection:
            op._proxy = Operations(MigrationContext.configure(connection))
            getattr(migration, method)()

    def _present(self):
        return set(sa.inspect(self.engine).get_table_names())

    def test_fresh_empty_chain_needs_no_archive_and_drop_is_idempotent(self):
        with patch.dict(os.environ, {}, clear=True):
            self._run()
            self._run()
        self.assertFalse(set(DEAD_MODEL_TABLES) & self._present())
        self.assertIn("study_progress_subjects", self._present())

    def test_nonempty_drop_requires_archive_before_any_table_is_dropped(self):
        self._seed()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "restore-verified archive"):
                self._run()
        self.assertTrue(set(DEAD_MODEL_TABLES) <= self._present())

    def test_archive_without_restore_verification_is_rejected(self):
        self._seed()
        self._archive(verified=False)
        with patch.dict(os.environ, {ARCHIVE_ENV: str(self.bundle)}):
            with self.assertRaisesRegex(RuntimeError, "no sqlite restore verification"):
                self._run()
        self.assertTrue(set(DEAD_MODEL_TABLES) <= self._present())

    def test_verified_archive_round_trips_binary_json_microseconds_and_drops_children_first(self):
        self._seed()
        self._archive()
        before = load_bundle(self.bundle)
        disposition = next(table for table in before["tables"] if table["name"] == "study_progress_backfill_dispositions")
        self.assertEqual(disposition["row_count"], 1)
        self.assertIn("123456", json.dumps(disposition["rows"]))
        trace = []
        sa.event.listen(self.engine, "before_cursor_execute", lambda c, cur, statement, p, ctx, many: trace.append(statement))
        with patch.dict(os.environ, {ARCHIVE_ENV: str(self.bundle)}):
            self._run()
        drops = [statement.strip().split()[-1] for statement in trace if statement.strip().startswith("DROP TABLE")]
        self.assertEqual(drops, list(migration.TABLES))
        self.assertFalse(set(DEAD_MODEL_TABLES) & self._present())
        self.assertEqual(load_bundle(self.bundle)["bundle_sha256"], before["bundle_sha256"])

    def test_source_changed_after_archive_refuses_all_drops(self):
        self._seed()
        self._archive()
        with self.engine.begin() as connection:
            connection.execute(self.tables["study_progress_backfill_dispositions"].update().values(attempt_count=2))
        with patch.dict(os.environ, {ARCHIVE_ENV: str(self.bundle)}):
            with self.assertRaisesRegex(RuntimeError, "changed since retirement archive"):
                self._run()
        self.assertTrue(set(DEAD_MODEL_TABLES) <= self._present())

    def test_populated_preference_also_requires_archive(self):
        with self.engine.begin() as connection:
            connection.execute(self.tables["vocabulary_column_preferences"].insert(), {
                "id": 1, "user_id": 1, "column_key": "word", "width": "100px", "updated_at": NOW})
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "restore-verified archive"):
                self._run()

    def test_unknown_inbound_foreign_key_blocks_before_first_drop(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE future_consumer (run_id TEXT REFERENCES study_progress_backfill_runs(id))")
        with self.assertRaisesRegex(RuntimeError, "external foreign-key consumers"):
            self._run()
        self.assertTrue(set(DEAD_MODEL_TABLES) <= self._present())

    def test_corrupted_archive_refuses_drop(self):
        self._seed()
        self._archive()
        data = json.loads(self.bundle.read_text(encoding="utf-8"))
        data["tables"][0]["row_count"] = 123
        self.bundle.write_text(json.dumps(data), encoding="utf-8")
        with patch.dict(os.environ, {ARCHIVE_ENV: str(self.bundle)}):
            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                self._run()

    def test_downgrade_does_not_pretend_to_restore_deleted_evidence(self):
        self._run()
        with self.assertRaisesRegex(RuntimeError, "restore the verified retirement archive first"):
            self._run("downgrade")

    def test_restore_rejects_same_database_or_existing_tables(self):
        self._seed()
        self._archive(verified=False)
        with self.engine.connect() as connection:
            with self.assertRaisesRegex(RuntimeError, "different from the source"):
                verify_restore(connection, self.bundle)
        collision = sa.create_engine(sa.URL.create("sqlite", database=str(Path(self.temp.name) / "collision.sqlite")))
        with collision.connect() as connection:
            connection.exec_driver_sql("CREATE TABLE study_progress_backfill_runs (id TEXT PRIMARY KEY)")
            with self.assertRaisesRegex(RuntimeError, "already contains archive tables"):
                verify_restore(connection, self.bundle)
        collision.dispose()

    def test_archive_does_not_overwrite_existing_evidence(self):
        self._archive(verified=False)
        with self.engine.connect() as connection:
            with self.assertRaisesRegex(RuntimeError, "overwrite archive"):
                write_bundle(connection, self.bundle)

    def test_mysql_float_restore_preserves_source_type_and_result_processor(self):
        from sqlalchemy.dialects import mysql
        dialect = mysql.dialect()
        for source in (mysql.FLOAT(), mysql.DOUBLE()):
            descriptor = _column_descriptor(sa.Column("value", source), dialect)
            restored = _restore_type(descriptor, dialect)
            self.assertEqual(str(restored.compile(dialect=dialect)), str(source.compile(dialect=dialect)))
            self.assertEqual(restored.asdecimal, source.asdecimal)

    def test_historical_migration_imports_do_not_register_retired_runtime_tables(self):
        from app import create_audit_app
        from models import db
        from migrations.retired_card_tables import Card, CardProgress, RETIRED_CARD_METADATA
        create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
        historical = importlib.import_module("migrations.versions.20260913_000039_add_study_progress_shadow_schema")
        self.assertTrue({table.name for table in historical.TARGET_TABLES} >= set(DEAD_MODEL_TABLES[1:]))
        self.assertFalse(set(DEAD_MODEL_TABLES) & set(db.metadata.tables))
        self.assertIs(Card.__table__.metadata, RETIRED_CARD_METADATA)
        self.assertIs(CardProgress.__table__.metadata, RETIRED_CARD_METADATA)
        self.assertEqual(CardProgress.__table__.c.card_id.type.length, 36)


if __name__ == "__main__":
    unittest.main()
