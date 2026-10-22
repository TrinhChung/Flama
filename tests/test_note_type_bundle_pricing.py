"""Pure commerce policy tests; no database fixture or payment provider."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import note_type_bundle_pricing_service as service
from app.services.note_type_release_service import NoteTypeReleaseError


class NoteTypeBundlePricingTests(unittest.TestCase):
    def setUp(self):
        self.note_type = SimpleNamespace(id="nt", user_id=1, pricing_mode="paid", price_amount_minor=10000)
        self.apps = [{"template_id": key, "template_release_id": f"r-{key}", "template_name": key}
            for key in ("own-a", "own-b", "foreign", "free", "foreign")]
        self.release = SimpleNamespace(id="nt-r", version_label="1.0.0",
            manifest_json={"metadata": {"name": "Bundle"}, "applications": self.apps})
        self.rows = {key: {"id": key, "name": key, "owner_user_id": owner,
            "username": f"author-{owner}", "pricing_mode": mode, "price_amount_minor": amount,
            "marketplace_status": "published", "archived_at": None, "origin": "authored",
            "source_template_id": None}
            for key, owner, mode, amount in (("own-a", 1, "paid", 30000),
                ("own-b", 1, "paid", 20000), ("foreign", 2, "paid", 15000), ("free", 3, "free", 0))}
        self.rights = set()
        patches = [patch.object(service.repository, "template_rows", side_effect=lambda *a: self.rows),
            patch.object(service.repository, "release_sources", side_effect=lambda *a: {f"r-{key}": key for key in self.rows}),
            patch.object(service.repository, "licensed_template_ids", side_effect=lambda *a, **kw: self.rights)]
        for mocked in patches:
            mocked.start()
            self.addCleanup(mocked.stop)

    def quote(self):
        return service.pricing_breakdown(None, note_type=self.note_type, user_id=9, release=self.release)

    def test_discount_only_applies_to_authors_own_bundle(self):
        result = self.quote()
        self.assertEqual((result["bundle_amount_minor"], result["template_amount_minor"], result["total_amount_minor"]),
            (10000, 15000, 25000))
        self.assertEqual(len(result["templates"]), 4)
        foreign = next(item for item in result["templates"] if item["template_id"] == "foreign")
        self.assertEqual((foreign["author"]["id"], foreign["charge_amount_minor"]), (2, 15000))

    def test_existing_foreign_license_is_not_charged_again(self):
        self.rights.add("foreign")
        result = self.quote()
        self.assertEqual((result["bundle_amount_minor"], result["total_amount_minor"]), (10000, 10000))

    def test_free_bundle_does_not_discount_foreign_template(self):
        self.note_type.pricing_mode = "free"
        result = self.quote()
        self.assertEqual(result["total_amount_minor"], 15000)
        self.assertTrue(result["payment_required"])

    def test_bundle_payment_permission_does_not_bypass_foreign_payment(self):
        with self.assertRaises(NoteTypeReleaseError) as caught:
            service.require_receipt_access(None, note_type=self.note_type, user_id=9,
                release=self.release, access_granted=True)
        self.assertEqual(caught.exception.code, "PAYMENT_REQUIRED")
        self.rights.add("foreign")
        service.require_receipt_access(None, note_type=self.note_type, user_id=9,
            release=self.release, access_granted=True)

    def test_delisted_foreign_definition_blocks_new_licenses_but_keeps_existing_rights(self):
        self.rows["foreign"]["marketplace_status"] = "private"
        with self.assertRaises(NoteTypeReleaseError):
            service.require_available(self.quote())
        self.rights.add("foreign")
        service.require_available(self.quote())

    def test_order_lines_freeze_owners_prices_and_published_releases(self):
        result = self.quote()
        lines = service.order_items_for_bundle(note_type=self.note_type, release=self.release, breakdown=result)
        positive = [(line["product_type"], line["product_ref_id"], line["amount_minor"]) for line in lines if line["amount_minor"]]
        self.assertEqual(positive, [("note_type", "nt", 10000), ("template", "foreign", 15000)])
        foreign = next(line for line in lines if line["product_ref_id"] == "foreign")
        self.assertEqual((foreign["product_snapshot"]["owner_user_id"], foreign["product_snapshot"]["release_id"]), (2, "r-foreign"))
        result["templates"][0]["name"] = "Draft changed"
        self.assertNotEqual(lines[0]["product_snapshot"]["pricing_breakdown"]["templates"][0]["name"], "Draft changed")


if __name__ == "__main__":
    unittest.main()
