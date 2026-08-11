import importlib
import unittest

import sqlalchemy as sa
from sqlalchemy.dialects import mysql, sqlite

from models.deck_change_request import DeckChangeRequest
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_install_rebase import DeckInstallRebase
from models.deck_install_rebase_conflict import DeckInstallRebaseConflict
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.deck_working_dirty_entity import DeckWorkingDirtyEntity


class DeckReleaseSchemaTests(unittest.TestCase):
    def test_revision_contract(self):
        revision = importlib.import_module(
            "migrations.versions.20260812_000016_add_deck_release_foundation"
        )

        self.assertEqual(revision.revision, "20260812_000016")
        self.assertEqual(revision.down_revision, "20260811_000015")

    def test_release_foundation_tables_and_pointers_are_registered(self):
        self.assertEqual(DeckRelease.__tablename__, "deck_releases")
        self.assertEqual(DeckReleaseChange.__tablename__, "deck_release_changes")
        self.assertEqual(
            DeckReleaseNoteCheckpoint.__tablename__,
            "deck_release_note_checkpoints",
        )
        self.assertEqual(
            DeckReleaseEntityMembership.__tablename__,
            "deck_release_entity_memberships",
        )
        self.assertEqual(
            DeckWorkingDirtyEntity.__tablename__,
            "deck_working_dirty_entities",
        )
        self.assertEqual(DeckInstallRebase.__tablename__, "deck_install_rebases")
        self.assertEqual(
            DeckInstallRebaseConflict.__tablename__,
            "deck_install_rebase_conflicts",
        )

        self.assertIn("current_release_id", DeckMarketplaceItem.__table__.c)
        self.assertIn("working_revision", DeckMarketplaceItem.__table__.c)
        self.assertIn("applied_release_id", DeckInstall.__table__.c)
        self.assertIn("seen_release_id", DeckInstall.__table__.c)
        self.assertIn("overlay_revision", DeckInstall.__table__.c)
        self.assertIn("version_mode", DeckInstall.__table__.c)
        self.assertIn("source_field_def_id", DeckCloneNoteFieldOverride.__table__.c)
        self.assertIn("base_release_id", DeckCloneNoteFieldOverride.__table__.c)
        self.assertIn("base_release_id", DeckChangeRequest.__table__.c)
        self.assertIn("revision", DeckChangeRequest.__table__.c)

    def test_high_volume_primary_keys_use_sqlite_integer_variant(self):
        high_volume_models = (
            DeckReleaseChange,
            DeckReleaseNoteCheckpoint,
            DeckReleaseEntityMembership,
            DeckWorkingDirtyEntity,
            DeckInstallRebaseConflict,
        )

        for model in high_volume_models:
            column_type = model.__table__.c.id.type
            self.assertIsInstance(
                column_type.dialect_impl(sqlite.dialect()),
                sa.Integer,
            )
            self.assertIsInstance(
                column_type.dialect_impl(mysql.dialect()),
                sa.BigInteger,
            )

    def test_sparse_change_and_rebase_uniqueness_guards_are_named(self):
        release_constraint_names = {
            constraint.name
            for constraint in DeckRelease.__table__.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        }
        change_constraint_names = {
            constraint.name
            for constraint in DeckReleaseChange.__table__.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        }
        rebase_constraint_names = {
            constraint.name
            for constraint in DeckInstallRebase.__table__.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        }

        self.assertIn("uq_deck_releases_item_sequence", release_constraint_names)
        self.assertIn("uq_deck_releases_item_version", release_constraint_names)
        self.assertIn("uq_deck_releases_item_idempotency", release_constraint_names)
        self.assertIn("uq_deck_release_changes_release_key", change_constraint_names)
        self.assertIn(
            "uq_deck_install_rebases_install_idempotency",
            rebase_constraint_names,
        )


if __name__ == "__main__":
    unittest.main()
