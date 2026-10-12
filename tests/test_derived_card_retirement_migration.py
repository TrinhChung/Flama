"""P11 contraction preserves frozen progress and every historical wire ID."""

from datetime import datetime
import importlib
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

migration = importlib.import_module("migrations.versions.20261012_000058_derive_cards_from_occurrences")
OLD = datetime(2026, 8, 1, 5, 0)
NEW = datetime(2026, 9, 30, 12, 0)


class DerivedCardRetirementMigrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine("sqlite:///:memory:")
        self.connection = self.engine.connect()
        metadata = sa.MetaData()
        self.notes = sa.Table("notes", metadata, sa.Column("id", sa.String(36), primary_key=True),
                              sa.Column("note_type_id", sa.String(36), nullable=False))
        self.apps = sa.Table("study_applications", metadata, sa.Column("id", sa.String(36), primary_key=True),
                            sa.Column("note_type_id", sa.String(36), nullable=False),
                            sa.Column("template_id", sa.String(36), nullable=False),
                            sa.Column("created_at", sa.DateTime(), nullable=False))
        self.cards = sa.Table(
            "cards", metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("note_id", sa.String(36), sa.ForeignKey("notes.id"), nullable=False),
            sa.Column("template_id", sa.String(36), nullable=False),
            sa.Column("application_id", sa.String(36), sa.ForeignKey("study_applications.id")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        self.refs = {}
        for name, nullable, length, ondelete in (
            ("card_progress", True, 36, "CASCADE"),
            ("study_session_cards", False, 36, "CASCADE"),
            ("connect_source_card_refs", True, 36, "SET NULL"),
            ("review_events", False, 64, None),
        ):
            foreign_key = [] if ondelete is None else [sa.ForeignKey("cards.id", ondelete=ondelete)]
            self.refs[name] = sa.Table(
                name, metadata, sa.Column("id", sa.Integer, primary_key=True),
                sa.Column("card_id", sa.String(length), *foreign_key, nullable=nullable),
                sa.Column("payload", sa.String(100), nullable=False),
            )
        metadata.create_all(self.connection)
        self.connection.execute(sa.insert(self.notes), [dict(id="n1", note_type_id="nt"), dict(id="n2", note_type_id="nt")])
        self.connection.execute(sa.insert(self.apps), [dict(id="a1", note_type_id="nt", template_id="t1", created_at=NEW),
                                                    dict(id="a2", note_type_id="nt", template_id="t2", created_at=NEW)])
        self.connection.execute(sa.insert(self.cards), [dict(id="old-1", note_id="n1", template_id="t1", application_id="a1", created_at=OLD, updated_at=OLD),
                                                       dict(id="old-2", note_id="n2", template_id="t1", application_id="a1", created_at=NEW, updated_at=NEW)])
        for name, table in self.refs.items():
            self.connection.execute(sa.insert(table).values(id=1, card_id="old-1", payload="frozen-" + name))
        self.connection.commit()

    def tearDown(self):
        self.connection.close()
        self.engine.dispose()

    def _upgrade(self):
        with patch.object(migration, "op", Operations(MigrationContext.configure(self.connection))):
            migration.upgrade()
        self.connection.commit()

    def _rows(self, name):
        table = sa.Table(name, sa.MetaData(), autoload_with=self.connection, resolve_fks=False)
        return self.connection.execute(sa.select(table).order_by(*table.primary_key.columns)).all()

    def test_upgrade_preserves_all_wire_ids_and_frozen_progress_exactly(self):
        before = {name: self._rows(name) for name in self.refs}
        cards = self._rows("cards")
        self._upgrade()
        self.assertFalse(sa.inspect(self.connection).has_table("cards"))
        self.assertEqual(self._rows(migration.ALIASES), cards)
        for name in self.refs:
            self.assertEqual(self._rows(name), before[name])
            self.assertFalse(sa.inspect(self.connection).get_foreign_keys(name))
        self.assertEqual(self.connection.execute(sa.select(self.apps.c.created_at)).scalars().all(), [NEW, NEW])

    def test_expands_live_wire_columns_but_keeps_frozen_progress_width(self):
        self._upgrade()
        for name, expected in (("card_progress", 36), ("study_session_cards", 80),
                               ("connect_source_card_refs", 80), ("review_events", 80)):
            column = next(c for c in sa.inspect(self.connection).get_columns(name) if c["name"] == "card_id")
            self.assertEqual(column["type"].length, expected)

    def test_baseline_preserves_original_entity_sets_including_absent_pairs(self):
        self._upgrade()
        self.assertEqual(self._rows(migration.NOTES), [("n1",), ("n2",)])
        self.assertEqual(self._rows(migration.APPLICATIONS), [("a1",), ("a2",)])
        self.assertEqual(len(self._rows(migration.ALIASES)), 2)

    def test_rerun_is_idempotent_and_does_not_capture_post_cutover_notes(self):
        self._upgrade()
        aliases = self._rows(migration.ALIASES)
        self.connection.execute(sa.insert(self.notes).values(id="later-note", note_type_id="nt"))
        self.connection.commit()
        self._upgrade()
        self.assertEqual(self._rows(migration.ALIASES), aliases)
        self.assertNotIn(("later-note",), self._rows(migration.NOTES))

    def test_unattributed_card_blocks_before_schema_change(self):
        self.connection.execute(sa.update(self.cards).where(self.cards.c.id == "old-1").values(application_id=None))
        self.connection.commit()
        with self.assertRaisesRegex(RuntimeError, "no application"):
            self._upgrade()
        self.assertTrue(sa.inspect(self.connection).has_table("cards"))
        self.assertFalse(sa.inspect(self.connection).has_table(migration.ALIASES))

    def test_unresolved_content_blocks_before_schema_change(self):
        self.connection.execute(sa.update(self.cards).where(self.cards.c.id == "old-1").values(note_id="missing"))
        self.connection.commit()
        with self.assertRaisesRegex(RuntimeError, "unresolved notes"):
            self._upgrade()
        self.assertTrue(sa.inspect(self.connection).has_table("cards"))

    def test_conflicting_alias_archive_refuses_contraction(self):
        metadata, aliases, *_ = migration._definitions()
        metadata.create_all(self.connection)
        self.connection.execute(sa.insert(aliases).values(id="old-1", note_id="n1", template_id="t1",
                                                        application_id="a1", created_at=NEW, updated_at=OLD))
        self.connection.commit()
        with self.assertRaisesRegex(RuntimeError, "differs"):
            self._upgrade()
        self.assertTrue(sa.inspect(self.connection).has_table("cards"))

    def test_incompatible_application_identity_blocks_before_schema_change(self):
        self.connection.execute(sa.update(self.apps).where(self.apps.c.id == "a1").values(note_type_id="another-type"))
        self.connection.commit()
        with self.assertRaisesRegex(RuntimeError, "incompatible application identity"):
            self._upgrade()
        self.assertTrue(sa.inspect(self.connection).has_table("cards"))
        self.assertFalse(sa.inspect(self.connection).has_table(migration.ALIASES))

    def test_unknown_card_foreign_key_blocks_drop(self):
        metadata = sa.MetaData()
        sa.Table("cards", metadata, autoload_with=self.connection, resolve_fks=False)
        unknown = sa.Table("unqualified_card_consumer", metadata, sa.Column("id", sa.Integer, primary_key=True),
                           sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id")))
        unknown.create(self.connection)
        self.connection.commit()
        with self.assertRaisesRegex(RuntimeError, "foreign keys remain"):
            self._upgrade()
        self.assertTrue(sa.inspect(self.connection).has_table("cards"))

    def test_downgrade_fails_without_mutating_historical_or_new_ids(self):
        self._upgrade()
        pair = "n1.a1"
        self.connection.execute(sa.insert(self.refs["review_events"]).values(id=2, card_id=pair, payload="new-history"))
        self.connection.commit()
        before = self._rows("review_events")
        with self.assertRaisesRegex(RuntimeError, "verified backup"):
            migration.downgrade()
        self.assertEqual(self._rows("review_events"), before)
        self.assertFalse(sa.inspect(self.connection).has_table("cards"))


if __name__ == "__main__":
    unittest.main()
