"""Lossless all-scope Field-ID preparation and irreversible legacy contraction."""
from datetime import datetime, timedelta
import importlib
import json
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from migrations.field_identity_contract import (
    ARCHIVE, CODEC, CUTOVERS, LEDGER, archive_root, extra_identity_key, reflected, verify_prepared,
)
from scripts.cutover_field_value_identity import prepare_cutover, restore_archived_note_values

EXPAND = importlib.import_module("migrations.versions.20261014_000066_expand_field_identity_cutover")
CONTRACT = importlib.import_module("migrations.versions.20261014_000067_contract_field_name_storage")
NOW = datetime(2026, 10, 14, 1, 2, 3)
VALUES = {"Word": "猫", "literal.dot": [True, 1, 1.0, None, ["same", "same"]], "MissingExtra": []}


def fixture_overrides(connection, *, with_data=False):
    metadata = sa.MetaData()
    installs = sa.Table("deck_installs", metadata, sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer), sa.Column("source_note_type_id", sa.String(36)),
        sa.Column("applied_release_id", sa.String(36)), sa.Column("overlay_revision", sa.BigInteger))
    overrides = sa.Table("deck_clone_note_field_overrides", metadata,
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("deck_install_id", sa.String(36)),
        sa.Column("source_note_id", sa.String(36)), sa.Column("source_field_def_id", sa.String(36)),
        sa.Column("base_release_id", sa.String(36)), sa.Column("field_name", sa.String(255)),
        sa.Column("operation", sa.String(16)), sa.Column("value", sa.JSON),
        sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime),
        sa.UniqueConstraint("deck_install_id", "source_note_id", "field_name", name="uq_clone_note_override_install_note_field"),
        sa.UniqueConstraint("deck_install_id", "source_note_id", "source_field_def_id", name="uq_clone_note_override_install_note_field_def"))
    metadata.create_all(connection)
    if with_data:
        connection.execute(installs.insert().values(id="install", user_id=2, source_note_type_id="schema", overlay_revision=0))
        added = reflected(connection, "deck_clone_added_field_defs")
        connection.execute(added.insert().values(id="added-id", deck_install_id="install", name="Added", properties={}, created_at=NOW-timedelta(seconds=1)))
        connection.execute(overrides.insert(), [dict(id="ov-source", deck_install_id="install", source_note_id="note",
            source_field_def_id="word-id", field_name="OldWord", operation="set", value=["source"], created_at=NOW, updated_at=NOW),
            dict(id="ov-added", deck_install_id="install", source_note_id="note", source_field_def_id=None,
            field_name="Added", operation="set", value=["added"], created_at=NOW, updated_at=NOW)])
    return installs, overrides


def fixture(connection):
    metadata = sa.MetaData()
    schemas = sa.Table("note_types", metadata, sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False), sa.Column("field_schema_revision", sa.BigInteger, nullable=False, server_default="0"))
    fields = sa.Table("field_defs", metadata, sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_type_id", sa.String(36), nullable=False), sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, default=NOW-timedelta(seconds=1)))
    notes = sa.Table("notes", metadata, sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_type_id", sa.String(36), nullable=False), sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("deck_id", sa.Integer), sa.Column("field_values", sa.JSON, nullable=False),
        sa.Column("field_values_by_id", sa.JSON), sa.Column("field_values_codec", sa.String(32)),
        sa.Column("field_values_extras", sa.JSON), sa.Column("content_revision", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime, nullable=False))
    media = sa.Table("media_assets", metadata, sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_id", sa.String(36), nullable=False), sa.Column("field_name", sa.String(255), nullable=False),
        sa.Column("field_def_id", sa.String(36)), sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("note_id", "sha256", "field_name", name="uq_media_assets_note_sha_field"))
    jobs = sa.Table("field_rename_jobs", metadata, sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("old_name", sa.String(255)),
        sa.Column("new_name", sa.String(255)), sa.Column("created_at", sa.DateTime, nullable=False))
    added_notes = sa.Table("deck_clone_added_notes", metadata, sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deck_install_id", sa.String(36)), sa.Column("note_id", sa.String(36)))
    added_fields = sa.Table("deck_clone_added_field_defs", metadata, sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("deck_install_id", sa.String(36)), sa.Column("name", sa.String(255)), sa.Column("properties", sa.JSON),
        sa.Column("created_at", sa.DateTime, nullable=False, default=NOW-timedelta(seconds=1)))
    metadata.create_all(connection)
    connection.execute(schemas.insert().values(id="schema", user_id=1))
    connection.execute(fields.insert(), [{"id": "word-id", "note_type_id": "schema", "name": "Word"},
        {"id": "dot-id", "note_type_id": "schema", "name": "literal.dot"}])
    connection.execute(notes.insert().values(id="note", note_type_id="schema", user_id=1, field_values=VALUES, updated_at=NOW))
    connection.execute(media.insert(), [{"id": "media", "note_id": "note", "field_name": "Word", "sha256": "a"*64,
        "storage_path": "synthetic/media", "created_at": NOW}, {"id": "extra-media", "note_id": "note",
        "field_name": "MissingExtra", "sha256": "b"*64, "storage_path": "synthetic/extra", "created_at": NOW}])
    connection.execute(jobs.insert().values(id="job", status="completed", old_name="Old", new_name="Word", created_at=NOW))
    return notes, media, fields, schemas, jobs, added_notes, added_fields


class FieldIdentityCutoverTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            self.notes, self.media, self.fields, self.schemas, self.jobs, self.added_notes, self.added_fields = fixture(connection)
            self.run_migration(connection, EXPAND)

    @staticmethod
    def run_migration(connection, migration, step="upgrade"):
        with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
            getattr(migration, step)()

    def prepare(self, **kwargs):
        return prepare_cutover(self.engine, apply=True, writers_quiesced=True, **kwargs)

    def test_dry_run_preserves_every_live_byte_and_creates_no_archive(self):
        with self.engine.connect() as connection:
            before = connection.exec_driver_sql("SELECT field_values FROM notes").scalar_one()
        result = prepare_cutover(self.engine)
        self.assertEqual((result["notes"], result["media"], result["rename_jobs"]), (1, 2, 1))
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT field_values FROM notes").scalar_one(), before)
            self.assertEqual(connection.exec_driver_sql(f"SELECT COUNT(*) FROM {ARCHIVE}").scalar_one(), 0)
            self.assertIsNone(connection.exec_driver_sql("SELECT field_values_by_id FROM notes").scalar_one())

    def test_apply_requires_quiescence_and_contract_requires_preparation(self):
        with self.assertRaisesRegex(ValueError, "quiesced"):
            prepare_cutover(self.engine, apply=True)
        with self.engine.begin() as connection:
            with self.assertRaisesRegex(RuntimeError, "quiesced"):
                self.run_migration(connection, CONTRACT)
            self.assertIn("field_values", reflected(connection, "notes").c)

    def test_bounded_resume_commits_archive_and_canonical_values_together(self):
        result = self.prepare(batch_size=1, max_batches=1)
        self.assertEqual(result["state"], "preparing")
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql(f"SELECT COUNT(*) FROM {ARCHIVE}").scalar_one(), 1)
            self.assertEqual(connection.exec_driver_sql("SELECT field_values_codec FROM notes").scalar_one(), CODEC)
        result = self.prepare(batch_size=1)
        self.assertEqual(result["state"], "verified")
        self.assertEqual((result["total_notes"], result["total_media"], result["total_rename_jobs"]), (1, 2, 1))

    def test_contract_keeps_typed_values_extras_media_and_immutable_history(self):
        self.prepare()
        with self.engine.begin() as connection:
            self.run_migration(connection, CONTRACT)
            notes = reflected(connection, "notes")
            self.assertNotIn("field_values", notes.c)
            row = connection.execute(notes.select()).mappings().one()
            self.assertEqual(row["field_values_by_id"], {"word-id": VALUES["Word"], "dot-id": VALUES["literal.dot"]})
            self.assertEqual(row["field_values_extras"], {"MissingExtra": []})
            self.assertEqual(row["updated_at"], NOW)
            self.assertFalse(sa.inspect(connection).has_table("field_rename_jobs"))
            self.assertEqual(connection.exec_driver_sql(f"SELECT state FROM {CUTOVERS}").scalar_one(), "contracted")
            extra = connection.exec_driver_sql("SELECT field_identity_key FROM media_assets WHERE id='extra-media'").scalar_one()
            self.assertEqual(extra, extra_identity_key("schema", "MissingExtra"))
            self.assertEqual(connection.exec_driver_sql(f"SELECT COUNT(*) FROM {ARCHIVE}").scalar_one(), 4)

    def test_archive_has_exact_named_bytes_and_original_shadow_for_restore(self):
        with self.engine.connect() as connection:
            raw = connection.exec_driver_sql("SELECT field_values FROM notes").scalar_one()
        self.prepare()
        with self.engine.connect() as connection:
            archive = reflected(connection, ARCHIVE)
            row = connection.execute(archive.select().where(archive.c.object_kind == "note")).mappings().one()
            self.assertEqual(row["source_raw"], raw)
            self.assertEqual(json.loads(row["source_raw"]), VALUES)
            self.assertIsNone(row["captured_schema"]["legacy_identity_state"]["field_values_by_id"])
            self.assertEqual(row["captured_schema"]["legacy_note_row"]["updated_at"], NOW.isoformat())
            archive_root(connection)

    def test_real_restore_rehearsal_restores_named_bytes_into_separate_legacy_database(self):
        self.prepare()
        target = sa.create_engine("sqlite:///:memory:")
        self.addCleanup(target.dispose)
        with target.begin() as connection:
            fixture(connection)
            connection.exec_driver_sql("UPDATE notes SET field_values='{}'")
        with self.engine.connect() as source, target.begin() as destination:
            result = restore_archived_note_values(source, destination)
            self.assertEqual(result["restored_notes"], 1)
            self.assertEqual(json.loads(destination.exec_driver_sql("SELECT field_values FROM notes").scalar_one()), VALUES)
            self.assertIsNone(destination.exec_driver_sql("SELECT field_values_by_id FROM notes").scalar_one())
        with self.engine.connect() as connection:
            with self.assertRaisesRegex(RuntimeError, "separate isolated"):
                restore_archived_note_values(connection, connection)

    def test_post_cutover_snapshot_allows_live_edits_but_keeps_archive_integrity(self):
        from scripts.qualify_progress_scalability_mysql import verify_canonical_field_snapshot
        self.prepare()
        with self.engine.begin() as connection:
            self.run_migration(connection, CONTRACT)
            notes = reflected(connection, "notes")
            connection.execute(notes.update().where(notes.c.id == "note").values(
                field_values_by_id={"word-id": ["changed", None]}, content_revision=1))
            connection.execute(notes.insert().values(id="new-note", note_type_id="schema", user_id=1,
                field_values_codec=CODEC, field_values_by_id={}, field_values_extras={}, updated_at=NOW))
            result = verify_canonical_field_snapshot(connection)
            self.assertEqual((result["counts"]["note"], result["archived_counts"]["note"]), (2, 1))
            archive = reflected(connection, ARCHIVE)
            connection.execute(archive.update().where(archive.c.object_kind == "note").values(source_raw="tampered"))
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                verify_canonical_field_snapshot(connection)

    def test_restore_distinguishes_json_null_from_sql_null_shadow_state(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE notes SET field_values_by_id='null',field_values_extras='null'")
        self.prepare()
        target = sa.create_engine("sqlite:///:memory:")
        self.addCleanup(target.dispose)
        with target.begin() as connection:
            fixture(connection)
        with self.engine.connect() as source, target.begin() as destination:
            restore_archived_note_values(source, destination)
            self.assertEqual(destination.exec_driver_sql("SELECT field_values_by_id,field_values_extras FROM notes").one(), ("null", "null"))
            self.assertIsNone(destination.exec_driver_sql("SELECT field_values_codec FROM notes").scalar_one())

    def test_partial_nontransactional_contraction_can_resume_without_reintroducing_names(self):
        self.prepare()
        with self.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE notes DROP COLUMN field_values")
            self.run_migration(connection, CONTRACT)
            self.assertNotIn("field_values", reflected(connection, "notes").c)
            self.assertFalse(sa.inspect(connection).has_table("field_rename_jobs"))
            self.run_migration(connection, CONTRACT)
            self.assertEqual(connection.exec_driver_sql(f"SELECT state FROM {CUTOVERS}").scalar_one(), "contracted")

    def test_all_scope_local_added_note_uses_local_ids_and_namespaced_added_ids(self):
        with self.engine.begin() as connection:
            connection.execute(self.added_notes.insert().values(id="local-note-link", deck_install_id="install", note_id="note"))
            connection.execute(self.added_fields.insert().values(id="extra-id", deck_install_id="install", name="Extra", properties={}))
            connection.execute(self.notes.update().values(field_values=dict(VALUES, Extra=["local", None])))
        self.prepare()
        with self.engine.connect() as connection:
            note = connection.execute(reflected(connection, "notes").select()).mappings().one()
            self.assertEqual(note["field_values_by_id"]["added:install:extra-id"], ["local", None])
            self.assertEqual(note["field_values_by_id"]["word-id"], VALUES["Word"])

    def test_clone_label_collision_refuses_without_any_note_archive(self):
        with self.engine.begin() as connection:
            connection.execute(self.added_notes.insert().values(id="link", deck_install_id="install", note_id="note"))
            connection.execute(self.added_fields.insert().values(id="extra-id", deck_install_id="install", name="Word", properties={}))
        with self.assertRaisesRegex(RuntimeError, "collide"):
            self.prepare()
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql(f"SELECT COUNT(*) FROM {ARCHIVE}").scalar_one(), 0)

    def test_source_and_added_overrides_contract_to_scoped_identity_uniqueness(self):
        with self.engine.begin() as connection:
            metadata = sa.MetaData()
            installs = sa.Table("deck_installs", metadata, sa.Column("id", sa.String(36), primary_key=True),
                sa.Column("user_id", sa.Integer), sa.Column("source_note_type_id", sa.String(36)),
                sa.Column("applied_release_id", sa.String(36)), sa.Column("overlay_revision", sa.BigInteger))
            overrides = sa.Table("deck_clone_note_field_overrides", metadata,
                sa.Column("id", sa.String(36), primary_key=True), sa.Column("deck_install_id", sa.String(36)),
                sa.Column("source_note_id", sa.String(36)), sa.Column("source_field_def_id", sa.String(36)),
                sa.Column("base_release_id", sa.String(36)), sa.Column("field_name", sa.String(255)),
                sa.Column("operation", sa.String(16)), sa.Column("value", sa.JSON),
                sa.Column("created_at", sa.DateTime), sa.Column("updated_at", sa.DateTime),
                sa.UniqueConstraint("deck_install_id", "source_note_id", "field_name", name="uq_clone_note_override_install_note_field"),
                sa.UniqueConstraint("deck_install_id", "source_note_id", "source_field_def_id", name="uq_clone_note_override_install_note_field_def"))
            metadata.create_all(connection)
            self.run_migration(connection, EXPAND)
            connection.execute(installs.insert().values(id="install", user_id=2, source_note_type_id="schema", overlay_revision=0))
            connection.execute(self.added_fields.insert().values(id="added-id", deck_install_id="install", name="Added", properties={}))
            connection.execute(overrides.insert(), [dict(id="ov-source", deck_install_id="install", source_note_id="note",
                source_field_def_id="word-id", field_name="OldWord", operation="set", value=["source"], created_at=NOW, updated_at=NOW),
                dict(id="ov-added", deck_install_id="install", source_note_id="note", source_field_def_id=None,
                field_name="Added", operation="set", value=["added"], created_at=NOW, updated_at=NOW)])
        result = self.prepare()
        self.assertEqual(result["total_overrides"], 2)
        with self.engine.begin() as connection:
            self.run_migration(connection, CONTRACT)
            rows = connection.exec_driver_sql("SELECT id,field_identity_key FROM deck_clone_note_field_overrides ORDER BY id").all()
            self.assertEqual(rows, [("ov-added", "added:install:added-id"), ("ov-source", "word-id")])
            constraints = sa.inspect(connection).get_unique_constraints("deck_clone_note_field_overrides")
            self.assertEqual([constraint["column_names"] for constraint in constraints], [["deck_install_id", "source_note_id", "field_identity_key"]])

    def _legacy_name_override(self, *, field_name="Word", pin=None):
        with self.engine.begin() as connection:
            _installs, overrides = fixture_overrides(connection, with_data=True)
            connection.execute(overrides.update().where(overrides.c.id == "ov-added").values(field_name=field_name, base_release_id=pin))
            self.run_migration(connection, EXPAND)

    def test_null_source_override_uses_only_definition_predating_the_override(self):
        self._legacy_name_override()
        self.prepare()
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT field_identity_key FROM deck_clone_note_field_overrides WHERE id='ov-added'").scalar_one(), "word-id")

    def test_null_source_override_does_not_retarget_later_same_name_field(self):
        self._legacy_name_override()
        with self.engine.begin() as connection:
            connection.execute(self.fields.update().where(self.fields.c.id == "word-id").values(created_at=NOW+timedelta(seconds=1)))
        self.prepare()
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT field_identity_key FROM deck_clone_note_field_overrides WHERE id='ov-added'").scalar_one(),
                extra_identity_key("schema", "Word"))

    def test_null_source_override_does_not_retarget_later_added_same_name_field(self):
        self._legacy_name_override(field_name="Added")
        with self.engine.begin() as connection:
            connection.execute(self.added_fields.update().values(created_at=NOW+timedelta(seconds=1)))
        self.prepare()
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT field_identity_key FROM deck_clone_note_field_overrides WHERE id='ov-added'").scalar_one(),
                extra_identity_key("schema", "Added"))

    def test_explicit_pinned_empty_schema_never_falls_back_to_current_same_label(self):
        self._legacy_name_override(pin="empty-release")
        with self.engine.begin() as connection:
            metadata = sa.MetaData()
            releases = sa.Table("deck_releases", metadata, sa.Column("id", sa.String(36), primary_key=True),
                sa.Column("deck_item_id", sa.String(36)), sa.Column("sequence_no", sa.Integer), sa.Column("status", sa.String(16)))
            sa.Table("deck_release_changes", metadata, sa.Column("id", sa.Integer, primary_key=True),
                sa.Column("release_id", sa.String(36)), sa.Column("release_sequence_no", sa.Integer),
                sa.Column("entity_kind", sa.String(16)), sa.Column("entity_id", sa.String(36)), sa.Column("field_def_id", sa.String(36)),
                sa.Column("property_key", sa.String(32)), sa.Column("operation", sa.String(16)), sa.Column("after_value", sa.JSON))
            metadata.create_all(connection)
            connection.execute(releases.insert().values(id="empty-release", deck_item_id="item", sequence_no=1, status="published"))
        self.prepare()
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT field_identity_key FROM deck_clone_note_field_overrides WHERE id='ov-added'").scalar_one(),
                extra_identity_key("schema", "Word"))

    def test_unfinished_job_requires_explicit_archived_disposition(self):
        with self.engine.begin() as connection:
            connection.execute(self.jobs.update().values(status="failed"))
        with self.assertRaisesRegex(RuntimeError, "archive_as_abandoned"):
            self.prepare()
        result = self.prepare(rename_job_dispositions={"job": "archive_as_abandoned"})
        self.assertEqual(result["state"], "verified")
        with self.engine.connect() as connection:
            archive = reflected(connection, ARCHIVE)
            row = connection.execute(archive.select().where(archive.c.object_kind == "rename_job")).mappings().one()
            self.assertEqual(json.loads(row["source_raw"])["status"], "failed")
            self.assertEqual(row["captured_schema"]["disposition"], "archive_as_abandoned")

    def test_rename_job_label_history_survives_job_table_retirement(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE field_rename_jobs ADD COLUMN field_def_id VARCHAR(36)")
            connection.exec_driver_sql("ALTER TABLE field_rename_jobs ADD COLUMN note_type_id VARCHAR(36)")
            connection.exec_driver_sql("UPDATE field_rename_jobs SET field_def_id='word-id',note_type_id='schema'")
        self.prepare()
        with self.engine.begin() as connection:
            self.run_migration(connection, CONTRACT)
            ledger = reflected(connection, LEDGER)
            definition = connection.execute(ledger.select().where(ledger.c.identity_key == "word-id")).mappings().one()
            self.assertIn("Old", definition["label_history"])
            self.assertIn("Word", definition["label_history"])
            self.assertFalse(sa.inspect(connection).has_table("field_rename_jobs"))

    def test_historical_media_label_resolves_exact_rename_evidence_not_extra_or_new_identity(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE field_rename_jobs ADD COLUMN field_def_id VARCHAR(36)")
            connection.exec_driver_sql("ALTER TABLE field_rename_jobs ADD COLUMN note_type_id VARCHAR(36)")
            connection.exec_driver_sql("UPDATE field_rename_jobs SET field_def_id='word-id',note_type_id='schema'")
            connection.execute(self.media.update().where(self.media.c.id == "media").values(field_name="Old"))
        self.prepare()
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql("SELECT field_identity_key FROM media_assets WHERE id='media'").scalar_one(), "word-id")

    def test_reused_historical_media_label_is_not_guessed_from_current_schema(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE field_rename_jobs ADD COLUMN field_def_id VARCHAR(36)")
            connection.exec_driver_sql("ALTER TABLE field_rename_jobs ADD COLUMN note_type_id VARCHAR(36)")
            connection.exec_driver_sql("UPDATE field_rename_jobs SET field_def_id='retired-word-id',note_type_id='schema',old_name='Word'")
        with self.assertRaisesRegex(RuntimeError, "ambiguous reused"):
            self.prepare()

    def test_verification_uses_bounded_archive_joins_instead_of_per_note_reads(self):
        with self.engine.begin() as connection:
            connection.execute(self.notes.insert(), [dict(id=f"batch-{index:04d}", note_type_id="schema", user_id=1,
                field_values=VALUES, updated_at=NOW) for index in range(401)])
        self.prepare(batch_size=200)
        statements = []
        def capture(_connection, _cursor, sql, _params, _context, _many):
            statements.append(" ".join(sql.lower().split()))
        sa.event.listen(self.engine, "before_cursor_execute", capture)
        try:
            with self.engine.connect() as connection:
                verify_prepared(connection)
        finally:
            sa.event.remove(self.engine, "before_cursor_execute", capture)
        note_reads = [sql for sql in statements if "from notes" in sql and "join field_value_identity_archive" in sql]
        self.assertEqual(len(note_reads), 4)  # Three bounded batches + terminal keyset read.
        self.assertFalse(any("from field_value_identity_archive where" in sql for sql in statements))

    def test_changed_note_blocks_contraction_before_column_drop(self):
        self.prepare()
        with self.engine.begin() as connection:
            connection.execute(self.notes.update().values(field_values={"Word": "changed"}))
            with self.assertRaisesRegex(RuntimeError, "Note changed"):
                self.run_migration(connection, CONTRACT)
            self.assertIn("field_values", reflected(connection, "notes").c)

    def test_changed_schema_blocks_contraction_before_column_drop(self):
        self.prepare()
        with self.engine.begin() as connection:
            connection.execute(self.fields.update().where(self.fields.c.id == "word-id").values(name="Renamed"))
            with self.assertRaisesRegex(RuntimeError, "scope/schema changed"):
                self.run_migration(connection, CONTRACT)

    def test_corrupt_archive_blocks_contraction(self):
        self.prepare()
        with self.engine.begin() as connection:
            archive = reflected(connection, ARCHIVE)
            connection.execute(archive.update().where(archive.c.object_kind == "note").values(source_raw="{}"))
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                self.run_migration(connection, CONTRACT)

    def test_changed_retained_identity_ledger_blocks_contraction(self):
        self.prepare()
        with self.engine.begin() as connection:
            ledger = reflected(connection, LEDGER)
            connection.execute(ledger.delete().where(ledger.c.identity_key == "word-id"))
            with self.assertRaisesRegex(RuntimeError, "provenance changed"):
                self.run_migration(connection, CONTRACT)
            self.assertIn("field_values", reflected(connection, "notes").c)

    def test_mismatched_existing_shadow_is_not_overwritten(self):
        with self.engine.begin() as connection:
            connection.execute(self.notes.update().values(field_values_by_id={"word-id": "different"},
                field_values_codec=CODEC, field_values_extras={"MissingExtra": []}))
        with self.assertRaisesRegex(RuntimeError, "shadow differs"):
            self.prepare()
        with self.engine.connect() as connection:
            self.assertEqual(connection.exec_driver_sql(f"SELECT COUNT(*) FROM {ARCHIVE}").scalar_one(), 0)

    def test_retired_media_id_never_retargets_same_name_recreated_field(self):
        with self.engine.begin() as connection:
            connection.execute(self.media.update().where(self.media.c.id == "media").values(field_def_id="old-deleted-id"))
        self.prepare()
        with self.engine.begin() as connection:
            self.run_migration(connection, CONTRACT)
            media = reflected(connection, "media_assets")
            retired = connection.execute(media.select().where(media.c.id == "media")).mappings().one()
            self.assertEqual(retired["field_identity_key"], "old-deleted-id")
            ledger = reflected(connection, LEDGER)
            definition = connection.execute(ledger.select().where(ledger.c.identity_key == "old-deleted-id")).mappings().one()
            self.assertTrue(definition["is_retired"])
            # Same bytes and label can coexist for a newly declared ID;
            # canonical identity uniqueness keeps both associations intact.
            connection.execute(media.insert().values(id="new-media", note_id="note", field_name="Word",
                field_def_id="word-id", field_identity_key="word-id", sha256=retired["sha256"],
                storage_path="synthetic/new-media", created_at=NOW))

    def test_media_id_in_another_live_notetype_blocks_ambiguous_scope(self):
        with self.engine.begin() as connection:
            connection.execute(self.fields.insert().values(id="other-field", note_type_id="other-schema", name="Word"))
            connection.execute(self.media.update().where(self.media.c.id == "media").values(field_def_id="other-field"))
        with self.assertRaisesRegex(RuntimeError, "another NoteType"):
            self.prepare()

    def test_pinned_schema_overlay_survives_upstream_field_deletion_after_fk_detachment(self):
        with self.engine.begin() as connection:
            metadata = sa.MetaData()
            self.fields.to_metadata(metadata)
            overrides = sa.Table("deck_clone_field_def_overrides", metadata,
                sa.Column("id", sa.String(36), primary_key=True), sa.Column("deck_install_id", sa.String(36)),
                sa.Column("source_field_def_id", sa.String(36), sa.ForeignKey("field_defs.id", ondelete="CASCADE"), nullable=False),
                sa.Column("is_disabled", sa.Boolean), sa.Column("properties", sa.JSON))
            metadata.create_all(connection)
            connection.execute(overrides.insert().values(id="schema-overlay", deck_install_id="install",
                source_field_def_id="word-id", is_disabled=False, properties={"name": "Learner label"}))
        self.prepare()
        with self.engine.begin() as connection:
            self.run_migration(connection, CONTRACT)
            self.assertFalse(sa.inspect(connection).get_foreign_keys("deck_clone_field_def_overrides"))
            connection.execute(self.fields.delete().where(self.fields.c.id == "word-id"))
            row = connection.execute(reflected(connection, "deck_clone_field_def_overrides").select()).mappings().one()
            self.assertEqual(row["source_field_def_id"], "word-id")
            self.assertEqual(row["properties"], {"name": "Learner label"})

    def test_populated_archive_cannot_be_downgraded_or_fake_empty_restored(self):
        self.prepare()
        with self.engine.begin() as connection:
            with self.assertRaisesRegex(RuntimeError, "Retain populated"):
                self.run_migration(connection, EXPAND, "downgrade")
            with self.assertRaisesRegex(RuntimeError, "cannot recreate"):
                self.run_migration(connection, CONTRACT, "downgrade")

    def test_empty_fresh_chain_contracts_without_background_backfill(self):
        with self.engine.begin() as connection:
            for table in (self.media, self.notes, self.jobs):
                connection.execute(table.delete())
            self.run_migration(connection, CONTRACT)
            self.assertNotIn("field_values", reflected(connection, "notes").c)
            self.assertEqual(connection.exec_driver_sql(f"SELECT COUNT(*) FROM {ARCHIVE}").scalar_one(), 0)


if __name__ == "__main__":
    unittest.main()
