"""Distribution schema persists user copies and explicit immutable release pins."""

from datetime import datetime
import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from models.template_publication import TemplatePublication
from models.template_release import TemplateRelease
from models.template_subscription import TemplateSubscription
from models.study_template_preset import StudyTemplatePreset
from models.deck_release_template_pin import DeckReleaseTemplatePin

migration = importlib.import_module("migrations.versions.20261007_000055_add_template_distribution")
MODELS = (TemplatePublication, TemplateRelease, TemplateSubscription, StudyTemplatePreset, DeckReleaseTemplatePin)


class TemplateDistributionMigrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.connection = self.engine.connect()
        self.connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        self.original_op = getattr(op, "_proxy", None)
        op._proxy = Operations(MigrationContext.configure(self.connection))
        self.now = datetime(2026, 10, 7, 8, 9, 10)

    def tearDown(self):
        op._proxy = self.original_op
        self.connection.close()
        self.engine.dispose()

    def _schema(self, *, current=False):
        tables = migration._tables()
        metadata = sa.MetaData()
        for name in ("users", "decks", "templates", "template_versions", "deck_releases"):
            parent = tables[0].metadata.tables[name].to_metadata(metadata)
            if name == "deck_releases" and current:
                parent.append_column(sa.Column("template_pins_initialized", sa.Boolean, nullable=False, server_default="0"))
        if current:
            # Freeze revision 55 schema rather than revision 69 marketplace columns.
            for table in tables:
                table.to_metadata(metadata)
        metadata.create_all(self.connection)
        self.connection.execute(metadata.tables["users"].insert(), [{"id": 1}, {"id": 2}])
        self.connection.execute(metadata.tables["decks"].insert(), [{"id": 1}, {"id": 2}])
        self.connection.execute(metadata.tables["templates"].insert(), [{"id": "source"}, {"id": "copy-a"}, {"id": "copy-b"}])
        self.connection.execute(metadata.tables["template_versions"].insert(), [{"id": "version-1", "template_id": "source"}, {"id": "version-2", "template_id": "source"}])
        self.connection.execute(metadata.tables["deck_releases"].insert().values(id="deck-release"))
        return tables

    def _table(self, name):
        return sa.Table(name, sa.MetaData(), autoload_with=self.connection)

    def _release(self, *, id="release-1", version_id="version-1", sequence_no=1, version_label="1", **extras):
        values = dict(id=id, template_id="source", version_id=version_id, sequence_no=sequence_no, version_label=version_label, parent_release_id=None, idempotency_key=None, change_note=None, created_by_user_id=1, published_at=self.now)
        values.update(extras)
        self.connection.execute(self._table("template_releases").insert().values(**values))

    def test_upgrade_idempotent_leaves_legacy_releases_uninitialized_and_no_inferred_pins(self):
        self._schema()
        migration.upgrade()
        migration.upgrade()
        for name in migration.TABLE_NAMES:
            self.assertTrue(sa.inspect(self.connection).has_table(name))
            self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(self._table(name))).scalar_one(), 0)
        self.assertFalse(self.connection.execute(sa.select(self._table("deck_releases").c.template_pins_initialized)).scalar_one())
        self.assertEqual(self.connection.execute(sa.select(self._table("templates").c.id).order_by(self._table("templates").c.id)).scalars().all(), ["copy-a", "copy-b", "source"])
        self.assertEqual(self.connection.exec_driver_sql("PRAGMA foreign_key_check").all(), [])

    def test_runtime_create_all_schema_is_accepted(self):
        self._schema(current=True)
        migration.upgrade()
        migration.upgrade()

    def test_drift_refuses_before_deck_flag_or_other_table_mutation(self):
        self._schema()
        self.connection.exec_driver_sql("CREATE TABLE template_subscriptions (id VARCHAR(36) NOT NULL PRIMARY KEY)")
        with self.assertRaisesRegex(RuntimeError, "column set differs"):
            migration.upgrade()
        self.assertNotIn("template_pins_initialized", {row["name"] for row in sa.inspect(self.connection).get_columns("deck_releases")})
        self.assertFalse(sa.inspect(self.connection).has_table("template_publications"))

    def test_deck_pin_flag_drift_refuses_before_any_new_table(self):
        self._schema()
        self.connection.exec_driver_sql("ALTER TABLE deck_releases ADD COLUMN template_pins_initialized INTEGER NOT NULL DEFAULT 1")
        with self.assertRaisesRegex(RuntimeError, "template_pins_initialized type/nullability/default differs"):
            migration.upgrade()
        self.assertFalse(sa.inspect(self.connection).has_table("template_publications"))

    def test_dangling_publication_pointer_fails_before_missing_tables_are_created(self):
        tables = self._schema()
        tables[0].create(self.connection)
        self.connection.execute(tables[0].insert().values(template_id="source", current_release_id="missing-release", created_at=self.now, updated_at=self.now))
        with self.assertRaisesRegex(RuntimeError, "current publication pointer is missing"):
            migration.upgrade()
        self.assertFalse(sa.inspect(self.connection).has_table("template_releases"))
        self.assertNotIn("template_pins_initialized", {row["name"] for row in sa.inspect(self.connection).get_columns("deck_releases")})

    def test_cross_template_release_version_is_rejected_without_rewriting(self):
        self._schema()
        migration.upgrade()
        self.connection.execute(sa.text("UPDATE template_versions SET template_id='copy-a' WHERE id='version-1'"))
        self._release()
        with self.assertRaisesRegex(RuntimeError, "published version does not belong"):
            migration.upgrade()
        self.assertEqual(self.connection.execute(sa.select(self._table("template_releases").c.id)).scalar_one(), "release-1")

    def test_user_source_pair_has_one_local_copy_and_both_auto_flags_default_off(self):
        self._schema()
        migration.upgrade()
        self._release()
        publisher = self._table("template_publications")
        subscription = self._table("template_subscriptions")
        self.connection.execute(publisher.insert().values(template_id="source", created_at=self.now, updated_at=self.now))
        base = dict(id="subscription-1", user_id=2, source_template_id="source", local_template_id="copy-a", applied_release_id="release-1", created_at=self.now, updated_at=self.now)
        self.connection.execute(subscription.insert().values(**base))
        self.assertFalse(self.connection.execute(sa.select(publisher.c.auto_publish_enabled)).scalar_one())
        self.assertFalse(self.connection.execute(sa.select(subscription.c.auto_update_enabled)).scalar_one())
        with self.assertRaises(sa.exc.IntegrityError):
            self.connection.execute(subscription.insert().values(**{**base, "id": "subscription-2", "local_template_id": "copy-b"}))

    def test_template_release_sequence_version_and_idempotency_uniques_are_enforced(self):
        self._schema()
        migration.upgrade()
        self._release(idempotency_key="publish-once")
        with self.assertRaises(sa.exc.IntegrityError):
            self._release(id="other", version_id="version-2", sequence_no=2, version_label="2", idempotency_key="publish-once")
        with self.assertRaises(sa.exc.IntegrityError):
            self._release(id="other", version_id="version-1", sequence_no=2, version_label="2")
        with self.assertRaises(sa.exc.IntegrityError):
            self._release(id="other", version_id="version-2", sequence_no=0, version_label="0")

    def test_published_source_and_version_deletion_are_restricted(self):
        self._schema()
        migration.upgrade()
        self._release()
        with self.assertRaises(sa.exc.IntegrityError):
            self.connection.execute(sa.text("DELETE FROM templates WHERE id='source'"))
        with self.assertRaises(sa.exc.IntegrityError):
            self.connection.execute(sa.text("DELETE FROM template_versions WHERE id='version-1'"))

    def test_deck_pin_captures_bindings_and_protects_template_release(self):
        self._schema()
        migration.upgrade()
        self._release()
        pins = self._table("deck_release_template_pins")
        applications = {"application": {"note_type_id": "nt", "occurrence_key": "compat", "input_bindings": {"Word": "field-uuid"}, "is_default": True, "display_name": "Prompt"}}
        self.connection.execute(pins.insert().values(deck_release_id="deck-release", source_template_id="source", template_release_id="release-1", applications_json=applications))
        self.assertEqual(self.connection.execute(sa.select(pins.c.applications_json)).scalar_one(), applications)
        with self.assertRaises(sa.exc.IntegrityError):
            self.connection.execute(sa.text("DELETE FROM template_releases WHERE id='release-1'"))
        self.connection.execute(sa.text("DELETE FROM deck_releases WHERE id='deck-release'"))
        self.assertEqual(self.connection.execute(sa.select(sa.func.count()).select_from(pins)).scalar_one(), 0)

    def test_preset_user_deck_unique_and_permanent_json_overrides(self):
        self._schema()
        migration.upgrade()
        presets = self._table("study_template_presets")
        self.connection.execute(presets.insert().values(id="preset-1", user_id=1, deck_id=1, selected_compositions=["composition-1"], input_bindings={"application-1": {"Word": None}}, created_at=self.now, updated_at=self.now))
        row = self.connection.execute(sa.select(presets)).mappings().one()
        self.assertEqual(row["input_bindings"], {"application-1": {"Word": None}})
        self.assertTrue(row["ask_before_study"])
        with self.assertRaises(sa.exc.IntegrityError):
            self.connection.execute(presets.insert().values(**{**row, "id": "preset-2"}))

    def test_empty_downgrade_reupgrade_keeps_source_ids(self):
        self._schema()
        migration.upgrade()
        migration.downgrade()
        self.assertFalse(sa.inspect(self.connection).has_table("template_releases"))
        self.assertNotIn("template_pins_initialized", {row["name"] for row in sa.inspect(self.connection).get_columns("deck_releases")})
        migration.upgrade()
        self.assertEqual(self.connection.execute(sa.select(self._table("deck_releases").c.id)).scalar_one(), "deck-release")

    def test_populated_distribution_downgrade_refuses_before_any_ddl(self):
        self._schema()
        migration.upgrade()
        self._release()
        with self.assertRaisesRegex(RuntimeError, "downgrade refuses published/subscriber/preset history"):
            migration.downgrade()
        self.assertTrue(all(sa.inspect(self.connection).has_table(name) for name in migration.TABLE_NAMES))
        self.assertEqual(self.connection.execute(sa.select(self._table("template_releases").c.id)).scalar_one(), "release-1")

    def test_deliberately_empty_initialized_release_still_refuses_downgrade(self):
        self._schema()
        migration.upgrade()
        self.connection.execute(sa.text("UPDATE deck_releases SET template_pins_initialized=1"))
        with self.assertRaisesRegex(RuntimeError, "refuses initialized release pins"):
            migration.downgrade()

    def test_mysql_frozen_ddl_matches_model_contracts(self):
        frozen = migration._tables()
        metadata = frozen[0].metadata
        for model, table in zip(MODELS, frozen):
            with self.subTest(table=table.name):
                model_table = model.__table__.to_metadata(sa.MetaData())
                for parent in ("users", "decks", "templates", "template_versions", "deck_releases"):
                    metadata.tables[parent].to_metadata(model_table.metadata)
                for linked in ("template_releases",):
                    if linked != model_table.name:
                        metadata.tables[linked].to_metadata(model_table.metadata)
                model_ddl = CreateTable(model_table)
                if model_table.name == "template_publications":
                    added_in_69 = {"marketplace_status", "pricing_mode", "price_amount_minor", "marketplace_published_at"}
                    # Compare revision 55 columns while copying the table and
                    # its foreign keys once through SQLAlchemy's public API.
                    model_ddl.columns = [column for column in model_ddl.columns
                                         if column.element.name not in added_in_69]
                model_sql = str(model_ddl.compile(dialect=mysql.dialect()))
                frozen_sql = str(CreateTable(table).compile(dialect=mysql.dialect()))
                # Column order is identical; constraint order is a set in SA.
                self.assertEqual(sorted(line.strip().rstrip(",") for line in model_sql.splitlines()), sorted(line.strip().rstrip(",") for line in frozen_sql.splitlines()))
