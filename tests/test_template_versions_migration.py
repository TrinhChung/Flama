"""Template version expansion preserves legacy sources and refuses history loss."""

from datetime import datetime
import importlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from models.template import Template
from models.template_version import TemplateVersion
from models.user import User  # Register the FK target for ORM DDL compilation.


migration = importlib.import_module("migrations.versions.20261007_000053_add_template_versions")


class TemplateVersionsMigrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.connection = self.engine.connect()
        self.connection.exec_driver_sql("PRAGMA foreign_keys = ON")
        self.connection.commit()
        self._op_proxy = getattr(op, "_proxy", None)
        op._proxy = Operations(MigrationContext.configure(self.connection))
        self.now = datetime(2026, 10, 7, 3, 4, 5)

    def tearDown(self):
        op._proxy = self._op_proxy
        self.connection.close()
        self.engine.dispose()

    def _schema(self, *, precreated=False):
        users, note_types, expected_templates, expected_versions = migration._tables()
        metadata = sa.MetaData()
        users = users.to_metadata(metadata)
        note_types = note_types.to_metadata(metadata)
        if precreated:
            # Freeze revision 53 rather than today's newer attachment schema.
            # The actual create_all contract was rehearsed when 53 shipped.
            templates = expected_templates.to_metadata(metadata)
            versions = expected_versions.to_metadata(metadata)
        else:
            templates = sa.Table(
                "templates", metadata,
                *(column._copy() for column in expected_templates.c if column.name not in migration.ADDED_COLUMNS),
                sa.ForeignKeyConstraint(["note_type_id"], ["note_types.id"], ondelete="CASCADE"),
                sa.Index("ix_templates_note_type_id", "note_type_id"),
            )
            versions = None
        sa.Table(
            "cards", metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False),
        )
        metadata.create_all(self.connection)
        self.connection.execute(users.insert(), [{"id": 1}, {"id": 2}])
        self.connection.execute(note_types.insert(), [
            {"id": "note-type-1", "user_id": 1},
            {"id": "note-type-2", "user_id": 2},
        ])
        return templates, versions

    def _seed(self, templates, template_id="template-1", **values):
        payload = {
            "id": template_id, "note_type_id": "note-type-1", "name": "Original",
            "front_html": "\r\n  {{単語}}\n<div>café &amp; 漢字</div>  ",
            "back_html": "{{FrontSide}}\r\n{{意味}}", "shared_css": "\n.card { color: #123; }\n",
            "position": 4, "is_default": True, "created_at": self.now,
            "updated_at": self.now,
        }
        payload.update(values)
        self.connection.execute(templates.insert().values(**payload))
        return payload

    def _templates(self):
        return sa.Table("templates", sa.MetaData(), autoload_with=self.connection)

    def _versions(self):
        return sa.Table("template_versions", sa.MetaData(), autoload_with=self.connection)

    def test_upgrade_backfills_owner_initial_version_and_preserves_exact_sources_cards(self):
        templates, _ = self._schema()
        initial = self._seed(templates)
        self.connection.execute(sa.text("INSERT INTO cards (id, template_id) VALUES ('card-1', 'template-1')"))

        migration.upgrade()

        current = self.connection.execute(sa.select(self._templates())).mappings().one()
        version = self.connection.execute(sa.select(self._versions())).mappings().one()
        for key, value in initial.items():
            self.assertEqual(current[key], value, key)
        self.assertEqual(current["owner_user_id"], 1)
        self.assertIsNone(current["input_schema"])
        self.assertEqual(current["current_version_id"], migration._initial_version_id(initial["id"]))
        self.assertEqual(version["id"], current["current_version_id"])
        self.assertEqual(version["template_id"], initial["id"])
        self.assertEqual(version["version_no"], 1)
        self.assertEqual(version["origin"], "backfill")
        self.assertEqual(version["created_by_user_id"], 1)
        self.assertEqual(version["created_at"], self.now)
        self.assertEqual(version["input_schema"], [])
        for key in ("front_html", "back_html", "shared_css"):
            self.assertEqual(version[key], initial[key])
        self.assertEqual(version["content_hash"], migration._content_hash(initial["front_html"], initial["back_html"], initial["shared_css"]))
        self.assertEqual(self.connection.execute(sa.text("SELECT id FROM cards")).scalar_one(), "card-1")
        self.assertEqual(self.connection.exec_driver_sql("PRAGMA foreign_key_check").all(), [])
        fks = sa.inspect(self.connection).get_foreign_keys("templates")
        self.assertFalse(any(row["constrained_columns"] == ["current_version_id"] for row in fks))
        note_type = next(row for row in sa.inspect(self.connection).get_columns("templates") if row["name"] == "note_type_id")
        self.assertFalse(note_type["nullable"])

    def test_accepts_model_create_all_schema_and_preserves_existing_input_schema(self):
        templates, _ = self._schema(precreated=True)
        schema = [{"key": "単語", "label": "Word", "type": "text", "required": True}]
        self._seed(templates, input_schema=schema)
        migration.upgrade()
        migration.upgrade()
        version = self.connection.execute(sa.select(self._versions())).mappings().one()
        self.assertEqual(version["input_schema"], schema)
        self.assertEqual(self.connection.execute(sa.select(self._templates().c.input_schema)).scalar_one(), schema)

    def _current_bootstrap_schema(self):
        attachments = importlib.import_module("migrations.versions.20261007_000054_expand_template_attachments")
        templates, _, _ = attachments._tables()
        templates.metadata.create_all(self.connection)
        return templates

    def test_accepts_empty_current_bootstrap_before_attachment_revision(self):
        self._current_bootstrap_schema()
        before = set(sa.inspect(self.connection).get_table_names())
        migration.upgrade()
        migration.upgrade()
        attachments = importlib.import_module("migrations.versions.20261007_000054_expand_template_attachments")
        attachments.upgrade()
        self.assertEqual(set(sa.inspect(self.connection).get_table_names()), before)
        self.assertTrue(next(c for c in sa.inspect(self.connection).get_columns("templates") if c["name"] == "note_type_id")["nullable"])

    def test_refuses_populated_later_bootstrap_without_rewriting_sources(self):
        templates = self._current_bootstrap_schema()
        self.connection.execute(sa.text("INSERT INTO users (id) VALUES (1)"))
        self.connection.execute(sa.text("INSERT INTO note_types (id, user_id) VALUES ('note-type-1', 1)"))
        original = self._seed(templates)
        with self.assertRaisesRegex(RuntimeError, "populated later attachment schema"):
            migration.upgrade()
        row = self.connection.execute(sa.select(templates)).mappings().one()
        for key, value in original.items():
            self.assertEqual(row[key], value)
        self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(self._versions())).scalar_one(), 0)

    def test_refuses_incomplete_current_bootstrap(self):
        self._current_bootstrap_schema()
        self.connection.exec_driver_sql("DROP INDEX ix_templates_archived_at")
        with self.assertRaisesRegex(RuntimeError, "indexes differ"):
            migration.upgrade()

    def test_downgrade_refuses_later_bootstrap_without_dropping_schema(self):
        self._current_bootstrap_schema()
        with self.assertRaisesRegex(RuntimeError, "cannot downgrade later attachment schema"):
            migration.downgrade()
        self.assertTrue(sa.inspect(self.connection).has_table("template_versions"))
        self.assertIn("owner_user_id", self._templates().c)

    def test_backfill_is_idempotent_and_resumes_missing_pointer_without_duplicate(self):
        templates, _ = self._schema()
        self._seed(templates)
        migration.upgrade()
        self.connection.execute(sa.text("UPDATE templates SET current_version_id = NULL, owner_user_id = NULL"))
        migration.upgrade()
        migration.upgrade()
        self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(self._versions())).scalar_one(), 1)
        self.assertEqual(self.connection.execute(sa.select(self._templates().c.current_version_id)).scalar_one(), migration._initial_version_id("template-1"))

    def test_backfill_batches_across_cursor_boundary_and_uses_each_note_type_owner(self):
        templates, _ = self._schema()
        for number in range(7):
            self._seed(templates, f"template-{number:04}", note_type_id="note-type-2" if number % 2 else "note-type-1")
        with patch.object(migration, "BATCH_SIZE", 3):
            migration.upgrade()
            migration.upgrade()
        rows = self.connection.execute(sa.select(self._templates()).order_by(self._templates().c.id)).mappings().all()
        self.assertEqual(len(rows), 7)
        self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(self._versions())).scalar_one(), 7)
        for number, row in enumerate(rows):
            self.assertEqual(row["owner_user_id"], 2 if number % 2 else 1)

    def test_rejects_precreated_drift_before_adding_any_template_column(self):
        self._schema()
        self.connection.exec_driver_sql("CREATE TABLE template_versions (id VARCHAR(36) NOT NULL PRIMARY KEY)")
        with self.assertRaisesRegex(RuntimeError, "column set differs"):
            migration.upgrade()
        columns = {row["name"] for row in sa.inspect(self.connection).get_columns("templates")}
        self.assertTrue(columns.isdisjoint(migration.ADDED_COLUMNS))

    def test_rejects_malformed_added_column_before_version_table_creation(self):
        self._schema()
        self.connection.exec_driver_sql("ALTER TABLE templates ADD COLUMN current_version_id TEXT")
        with self.assertRaisesRegex(RuntimeError, "current_version_id type/nullability/default differs"):
            migration.upgrade()
        self.assertFalse(sa.inspect(self.connection).has_table("template_versions"))
        self.assertNotIn("owner_user_id", {row["name"] for row in sa.inspect(self.connection).get_columns("templates")})

    def test_rejects_missing_owner_before_any_ddl(self):
        templates, _ = self._schema()
        self._seed(templates)
        self.connection.execute(sa.text("UPDATE note_types SET user_id = 999 WHERE id = 'note-type-1'"))
        with self.assertRaisesRegex(RuntimeError, "has no existing NoteType owner"):
            migration.upgrade()
        self.assertFalse(sa.inspect(self.connection).has_table("template_versions"))
        self.assertTrue(set(migration.ADDED_COLUMNS).isdisjoint(self._templates().c.keys()))

    def test_rejects_extra_template_pointer_index_before_any_ddl(self):
        self._schema(precreated=True)
        self.connection.exec_driver_sql("CREATE INDEX unexpected_pointer_index ON templates(current_version_id)")
        with self.assertRaisesRegex(RuntimeError, "indexes/unique/CHECK constraints differ"):
            migration.upgrade()
        self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(self._versions())).scalar_one(), 0)

    def test_rejects_application_pointer_to_another_template_without_mutation(self):
        templates, _ = self._schema(precreated=True)
        self._seed(templates)
        self._seed(templates, "template-2")
        migration.upgrade()
        pointer = migration._initial_version_id("template-2")
        self.connection.execute(sa.text("UPDATE templates SET current_version_id = :pointer WHERE id = 'template-1'"), {"pointer": pointer})
        with self.assertRaisesRegex(RuntimeError, "current snapshot differs from source"):
            migration.upgrade()
        self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(self._versions())).scalar_one(), 2)

    def test_rejects_required_note_type_cutover_drift(self):
        self._schema()
        self.connection.exec_driver_sql("DROP TABLE cards")
        self.connection.exec_driver_sql("DROP TABLE templates")
        _, _, frozen, _ = migration._tables()
        metadata = sa.MetaData()
        sa.Table("note_types", metadata, sa.Column("id", sa.String(36), primary_key=True))
        altered = sa.Table(
            "templates", metadata,
            *(column._copy() for column in frozen.c if column.name not in migration.ADDED_COLUMNS),
            sa.ForeignKeyConstraint(["note_type_id"], ["note_types.id"], ondelete="CASCADE"),
        )
        altered.c.note_type_id.nullable = True
        altered.create(self.connection)
        with self.assertRaisesRegex(RuntimeError, "note_type_id type/nullability/default differs"):
            migration.upgrade()

    def test_rejects_precreated_wrong_fk_unique_check_and_index_contracts(self):
        for kind in ("foreign-key", "unique", "check", "index"):
            with self.subTest(kind=kind):
                # One isolated connection per drift case avoids contaminating
                # the remaining checks with the deliberately bad DDL.
                with sa.create_engine("sqlite:///:memory:").connect() as connection:
                    metadata = sa.MetaData()
                    _, _, _, version_table = migration._tables()
                    version_table = version_table.to_metadata(metadata)
                    sa.Table("templates", metadata, sa.Column("id", sa.String(36), primary_key=True))
                    sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
                    if kind == "foreign-key":
                        fk = next(constraint for constraint in version_table.foreign_key_constraints if constraint.column_keys == ["template_id"])
                        fk.ondelete = "SET NULL"
                    elif kind == "unique":
                        version_table.constraints.remove(next(c for c in version_table.constraints if isinstance(c, sa.UniqueConstraint)))
                    elif kind == "check":
                        version_table.constraints.remove(next(c for c in version_table.constraints if isinstance(c, sa.CheckConstraint)))
                    else:
                        version_table.indexes.clear()
                    metadata.create_all(connection)
                    with self.assertRaisesRegex(RuntimeError, "drift"):
                        migration._validate_versions(connection, migration._tables()[3])

    def test_downgrade_initial_rehearsal_preserves_sources_cards_then_reupgrade(self):
        templates, _ = self._schema()
        initial = self._seed(templates)
        self.connection.execute(sa.text("INSERT INTO cards (id, template_id) VALUES ('card-1', 'template-1')"))
        migration.upgrade()
        version_id = self.connection.execute(sa.select(self._versions().c.id)).scalar_one()
        migration.downgrade()
        self.assertFalse(sa.inspect(self.connection).has_table("template_versions"))
        self.assertEqual(self.connection.execute(sa.select(self._templates())).mappings().one(), initial)
        self.assertEqual(self.connection.execute(sa.text("SELECT id FROM cards")).scalar_one(), "card-1")
        migration.upgrade()
        self.assertEqual(self.connection.execute(sa.select(self._versions().c.id)).scalar_one(), version_id)

    def test_downgrade_empty_history_is_reversible(self):
        self._schema()
        migration.upgrade()
        migration.downgrade()
        migration.downgrade()
        self.assertFalse(sa.inspect(self.connection).has_table("template_versions"))
        self.assertTrue(set(migration.ADDED_COLUMNS).isdisjoint(self._templates().c.keys()))

    def test_downgrade_refuses_history_before_any_ddl(self):
        templates, _ = self._schema()
        self._seed(templates)
        migration.upgrade()
        versions = self._versions()
        initial = dict(self.connection.execute(sa.select(versions)).mappings().one())
        initial.update(id="version-2", version_no=2, origin="editor")
        self.connection.execute(versions.insert().values(**initial))
        self.connection.execute(sa.text("UPDATE templates SET current_version_id = 'version-2'"))
        with self.assertRaisesRegex(RuntimeError, "refuses version history"):
            migration.downgrade()
        self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(versions)).scalar_one(), 2)
        self.assertTrue(set(migration.ADDED_COLUMNS).issubset(self._templates().c.keys()))

    def test_downgrade_refuses_a_single_later_version_and_authored_history(self):
        templates, _ = self._schema()
        self._seed(templates)
        migration.upgrade()
        self.connection.execute(sa.text("UPDATE template_versions SET version_no = 3"))
        with self.assertRaisesRegex(RuntimeError, "refuses version history"):
            migration.downgrade()
        self.connection.execute(sa.text("UPDATE template_versions SET version_no = 1, origin = 'editor'"))
        with self.assertRaisesRegex(RuntimeError, "refuses authored history"):
            migration.downgrade()

    def test_preflight_rejects_source_snapshot_drift_without_rewriting_history(self):
        templates, _ = self._schema(precreated=True)
        self._seed(templates)
        migration.upgrade()
        self.connection.execute(sa.text("UPDATE templates SET front_html = 'changed externally'"))
        with self.assertRaisesRegex(RuntimeError, "current snapshot differs from source"):
            migration.upgrade()
        self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(self._versions())).scalar_one(), 1)

    def test_foreign_keys_cascade_versions_and_set_null_created_by(self):
        templates, _ = self._schema()
        self._seed(templates)
        migration.upgrade()
        self.connection.execute(sa.text("UPDATE template_versions SET created_by_user_id = 2"))
        self.connection.execute(sa.text("DELETE FROM users WHERE id = 2"))
        self.assertIsNone(self.connection.execute(sa.select(self._versions().c.created_by_user_id)).scalar_one())
        self.connection.execute(sa.text("DELETE FROM templates WHERE id = 'template-1'"))
        self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(self._versions())).scalar_one(), 0)

    def test_unique_sequence_and_positive_check_are_enforced(self):
        templates, _ = self._schema()
        self._seed(templates)
        migration.upgrade()
        version = dict(self.connection.execute(sa.select(self._versions())).mappings().one())
        version["id"] = "duplicate-sequence"
        with self.assertRaises(sa.exc.IntegrityError):
            self.connection.execute(self._versions().insert().values(**version))
        version.update(id="negative-sequence", version_no=0)
        with self.assertRaises(sa.exc.IntegrityError):
            self.connection.execute(self._versions().insert().values(**version))

    def test_frozen_hash_matches_gt08_known_vector_and_none_normalization(self):
        self.assertEqual(migration._content_hash("{{Word}}", "{{Word}}<hr>{{Meaning}}", ""), "7848287f04a3dc0ce90078c66bc73ee7f1e184d47f03e922a595baa6e1f7f698")
        self.assertEqual(migration._content_hash(None, None, None), migration._content_hash("", "", ""))
        self.assertNotEqual(migration._content_hash("a\r\n", "", ""), migration._content_hash("a\n", "", ""))

    def test_mysql_ddl_preserves_fk_types_and_has_no_version_pointer_fk(self):
        _, _, templates, versions = migration._tables()
        dialect = mysql.dialect()
        version_sql = str(CreateTable(versions).compile(dialect=dialect))
        template_sql = str(CreateTable(templates).compile(dialect=dialect))
        self.assertIn("template_id VARCHAR(36) NOT NULL", version_sql)
        self.assertIn("front_html TEXT NOT NULL", version_sql)
        self.assertIn("input_schema JSON NOT NULL", version_sql)
        self.assertIn("content_hash VARCHAR(64) NOT NULL", version_sql)
        self.assertIn("CONSTRAINT uq_template_versions_template_no UNIQUE (template_id, version_no)", version_sql)
        self.assertIn("CHECK (version_no > 0)", version_sql)
        self.assertIn("FOREIGN KEY(template_id) REFERENCES templates (id) ON DELETE CASCADE", version_sql)
        self.assertIn("FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL", version_sql)
        self.assertIn("note_type_id VARCHAR(36) NOT NULL", template_sql)
        self.assertNotIn("FOREIGN KEY(current_version_id)", template_sql)
        self.assertEqual(migration._type_sql(mysql.TINYINT(display_width=1), dialect), migration._type_sql(sa.Boolean(), dialect))
        self.assertEqual(str(CreateTable(TemplateVersion.__table__).compile(dialect=dialect)), version_sql)

    def test_accepts_mysql_unique_index_reflection_without_duplicate_marker(self):
        self._schema(precreated=True)
        original = sa.inspect(self.connection)
        bind = SimpleNamespace(dialect=mysql.dialect())
        indexes = original.get_indexes("template_versions") + [{
            "name": "uq_template_versions_template_no", "column_names": ["template_id", "version_no"], "unique": True,
        }]
        inspector = SimpleNamespace(
            bind=bind, get_columns=original.get_columns,
            get_pk_constraint=original.get_pk_constraint,
            get_foreign_keys=original.get_foreign_keys,
            get_unique_constraints=original.get_unique_constraints,
            get_check_constraints=original.get_check_constraints,
            get_indexes=lambda name: indexes,
            get_table_options=lambda name: {"mysql_engine": "InnoDB"},
        )
        with patch.object(migration.sa, "inspect", return_value=inspector):
            migration._validate_versions(bind, migration._tables()[3])


if __name__ == "__main__":
    unittest.main()
