import importlib
import unittest

from models.shared_image_asset import SharedImageAsset


class ImageLibrarySchemaTests(unittest.TestCase):
    def test_revision_contract(self):
        initial = importlib.import_module(
            "migrations.versions.20260726_000009_add_shared_image_assets"
        )
        self.assertEqual(initial.revision, "20260726_000009")
        self.assertEqual(initial.down_revision, "20260401_000008")

        tags_and_source = importlib.import_module(
            "migrations.versions.20260821_000020_add_shared_image_assets_tags_and_source_url"
        )
        self.assertEqual(tags_and_source.revision, "20260821_000020")
        self.assertEqual(tags_and_source.down_revision, "20260820_000019")

    def test_shared_image_assets_columns_and_indices(self):
        table = SharedImageAsset.__table__
        self.assertEqual(SharedImageAsset.__tablename__, "shared_image_assets")

        self.assertIn("id", table.c)
        self.assertIn("image_key", table.c)
        self.assertIn("description", table.c)
        self.assertIn("filename", table.c)
        self.assertIn("mime_type", table.c)
        self.assertIn("size_bytes", table.c)
        self.assertIn("sha256", table.c)
        self.assertIn("storage_path", table.c)
        self.assertIn("is_enabled", table.c)
        self.assertIn("source_url", table.c)
        self.assertIn("tags", table.c)

        index_names = {idx.name for idx in table.indexes}
        self.assertIn("ix_shared_image_assets_sha256", index_names)
        self.assertIn("ix_shared_image_assets_is_enabled", index_names)
        self.assertIn("ix_shared_image_assets_updated_at", index_names)
