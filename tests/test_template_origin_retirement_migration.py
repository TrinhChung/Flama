"""Template-origin contraction requires a verified restore and preserves evidence."""

from datetime import datetime
import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from migrations.retirement_archive import ARCHIVE_ENV, write_bundle, verify_restore

migration = importlib.import_module("migrations.versions.20261012_000060_retire_template_origin")
NOW = datetime(2026, 10, 1, 12)


class TemplateOriginRetirementMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.connection = self.engine.connect()
        metadata = sa.MetaData()
        self.users = sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
        self.note_types = sa.Table("note_types", metadata, sa.Column("id", sa.String(36), primary_key=True),
                                  sa.Column("user_id", sa.Integer, nullable=False))
        self.templates = sa.Table(
            "templates", metadata, sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("note_type_id", sa.String(36), sa.ForeignKey("note_types.id", name="fk_old_origin"), index=True),
            sa.Column("owner_user_id", sa.Integer, sa.ForeignKey("users.id", name="fk_owner")),
            sa.Column("front_html", sa.Text(), nullable=False), sa.Column("back_html", sa.Text(), nullable=False),
            sa.Column("shared_css", sa.Text(), nullable=False), sa.Column("input_schema", sa.JSON()),
            sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        self.applications = sa.Table("study_applications", metadata,
                                     sa.Column("id", sa.String(36), primary_key=True),
                                     sa.Column("note_type_id", sa.String(36), nullable=False),
                                     sa.Column("template_id", sa.String(36), nullable=False),
                                     sa.Column("input_bindings", sa.JSON()), sa.Column("position", sa.Integer))
        self.fields = sa.Table("field_defs", metadata, sa.Column("id", sa.String(36), primary_key=True),
                               sa.Column("note_type_id", sa.String(36)), sa.Column("name", sa.String(255)),
                               sa.Column("field_type", sa.String(30)), sa.Column("position", sa.Integer),
                               sa.Column("required", sa.Boolean))
        self.versions = sa.Table("template_versions", metadata, sa.Column("id", sa.String(36), primary_key=True),
                                 sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id")),
                                 sa.Column("source", sa.Text()))
        metadata.create_all(self.connection)
        self.connection.execute(sa.insert(self.users).values(id=7))
        self.connection.execute(sa.insert(self.note_types).values(id="origin-nt", user_id=7))
        self.connection.execute(sa.insert(self.templates).values(id="template", note_type_id="origin-nt", owner_user_id=None,
                                                                front_html="{{Photo}}", back_html="", shared_css="", input_schema=None,
                                                                created_at=NOW, updated_at=NOW))
        self.connection.execute(sa.insert(self.applications).values(id="app", note_type_id="origin-nt", template_id="template",
                                                                   input_bindings={"Photo": "photo-field"}, position=4))
        self.connection.execute(sa.insert(self.fields).values(id="photo-field", note_type_id="origin-nt", name="Photo",
                                                              field_type="image", position=0, required=False))
        self.connection.execute(sa.insert(self.versions).values(id="version", template_id="template", source="immutable"))
        self.connection.commit()
        self.bundle = Path(self.temp.name) / "origin-archive.json"

    def tearDown(self):
        self.connection.close()
        self.engine.dispose()
        self.temp.cleanup()

    def _archive(self):
        write_bundle(self.connection, self.bundle, ["templates"])
        restore = sa.create_engine("sqlite:///" + str(Path(self.temp.name) / "restore.db"))
        with restore.begin() as connection:
            verify_restore(connection, self.bundle)
        restore.dispose()

    def _upgrade(self, archive=True):
        environment = {ARCHIVE_ENV: str(self.bundle)} if archive else {ARCHIVE_ENV: ""}
        with patch.dict(os.environ, environment), patch.object(migration, "op", Operations(MigrationContext.configure(self.connection))):
            migration.upgrade()
        self.connection.commit()

    def _templates(self):
        table = sa.Table("templates", sa.MetaData(), autoload_with=self.connection, resolve_fks=False)
        return table, self.connection.execute(sa.select(table)).mappings().one()

    def test_missing_verified_archive_blocks_before_owner_or_schema_changes(self):
        with self.assertRaisesRegex(RuntimeError, "archive"):
            self._upgrade(archive=False)
        table, row = self._templates()
        self.assertIn("note_type_id", table.c)
        self.assertIsNone(row["owner_user_id"])
        self.assertIsNone(row["input_schema"])

    def test_verified_archive_backfills_owner_and_typed_metadata_without_changing_history_or_applications(self):
        self._archive()
        apps = self.connection.execute(sa.select(self.applications)).all()
        history = self.connection.execute(sa.select(self.versions)).all()
        self._upgrade()
        table, row = self._templates()
        self.assertNotIn("note_type_id", table.c)
        self.assertFalse(table.c.owner_user_id.nullable)
        self.assertEqual(row["owner_user_id"], 7)
        self.assertEqual(row["input_schema"][0]["type"], "image")
        self.assertEqual((row["front_html"], row["created_at"], row["updated_at"]), ("{{Photo}}", NOW, NOW))
        self.assertEqual(self.connection.execute(sa.select(self.applications)).all(), apps)
        self.assertEqual(self.connection.execute(sa.select(self.versions)).all(), history)
        self.assertEqual([fk["constrained_columns"] for fk in sa.inspect(self.connection).get_foreign_keys("templates")], [["owner_user_id"]])

    def test_rerun_is_idempotent_after_origin_column_is_gone(self):
        self._archive()
        self._upgrade()
        before = dict(self._templates()[1])
        self._upgrade(archive=False)
        self.assertEqual(dict(self._templates()[1]), before)

    def test_unknown_author_is_refused_without_guessing_from_unrelated_attachments(self):
        self.connection.execute(sa.update(self.templates).values(note_type_id=None, owner_user_id=None))
        self.connection.commit()
        self._archive()
        with self.assertRaisesRegex(RuntimeError, "verified author"):
            self._upgrade()
        self.assertIsNone(self._templates()[1]["owner_user_id"])

    def test_unconverted_origin_attachment_blocks_contraction(self):
        self.connection.execute(sa.delete(self.applications))
        self.connection.commit()
        self._archive()
        with self.assertRaisesRegex(RuntimeError, "unconverted origin attachment"):
            self._upgrade()
        self.assertIn("note_type_id", self._templates()[0].c)

    def test_downgrade_refuses_to_invent_single_origin_for_reused_definitions(self):
        self._archive()
        self._upgrade()
        before = dict(self._templates()[1])
        with self.assertRaisesRegex(RuntimeError, "verified archive"):
            migration.downgrade()
        self.assertEqual(dict(self._templates()[1]), before)


if __name__ == "__main__":
    unittest.main()
