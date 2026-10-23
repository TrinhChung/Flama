"""Pure publication-policy tests; no database or dialect emulation."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from app.services import note_type_bundle_publication_service as service
from app.services.template_release_service import TemplateReleaseError


class NoteTypeBundlePublicationTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.source = {"id": "original", "owner_user_id": 2, "origin": "authored",
            "source_template_id": None, "name": "Original", "archived_at": None}
        self.copy = {"id": "received", "owner_user_id": 1, "origin": "market_copy",
            "source_template_id": "original", "front_html": "PERSONAL EDIT"}
        self.publication = {"marketplace_status": "published", "current_release_id": "newest",
            "pricing_mode": "paid", "price_amount_minor": 30000}

    def _foreign(self, *, subscription=True, listed=True, access=True):
        publication = dict(self.publication)
        if not listed:
            publication["marketplace_status"] = "private"
        return (
            patch.object(service.releases, "template", return_value=self.source),
            patch.object(service.releases, "publication", return_value=publication),
            patch.object(service.repository, "subscription", return_value={"applied_release_id": "received-release"} if subscription else None),
            patch.object(service.releases, "release", return_value={"id": "received-release", "template_id": "original"}),
            patch("app.services.note_type_bundle_pricing_service.has_template_access", return_value=access),
        )

    def test_received_copy_uses_original_author_and_applied_release(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            mocks = [stack.enter_context(item) for item in self._foreign()]
            result = service._resolve(self.session, self.copy, actor_user_id=1)
        self.assertEqual(result["source"]["id"], "original")
        self.assertEqual(result["source"]["owner_user_id"], 2)
        self.assertEqual(result["release"]["id"], "received-release")
        self.assertFalse(result["is_owned"])
        self.assertFalse(result["requires_publication"])
        mocks[3].assert_called_once_with(self.session, "received-release", "original")

    def test_foreign_reference_requires_listing_receipt_and_unrevoked_access(self):
        from contextlib import ExitStack
        for options, code in [({"subscription": False}, "TEMPLATE_ACCESS_DENIED"),
                ({"listed": False}, "TEMPLATE_NOT_LISTED"),
                ({"access": False}, "TEMPLATE_ACCESS_DENIED")]:
            with self.subTest(options=options), ExitStack() as stack:
                for item in self._foreign(**options):
                    stack.enter_context(item)
                with self.assertRaises(TemplateReleaseError) as error:
                    service._resolve(self.session, self.copy, actor_user_id=1)
                self.assertEqual(error.exception.code, code)

    def test_owned_unlisted_release_still_requires_explicit_listing(self):
        source = {**self.source, "owner_user_id": 1}
        with patch.object(service.releases, "template", return_value=source), \
                patch.object(service.releases, "publication", return_value={"marketplace_status": "private", "current_release_id": "old"}), \
                patch.object(service.releases, "release", return_value={"id": "old"}):
            result = service._resolve(self.session, source, actor_user_id=1)
        self.assertTrue(result["requires_publication"])

    def test_foreign_listing_settings_and_unknown_ids_are_rejected(self):
        foreign = {"attached": self.copy, "source": self.source, "requires_publication": False}
        with patch.object(service, "references", return_value=[foreign]), \
                patch("app.services.template_marketplace_service.stage_listing") as stage:
            for template_id in ("received", "original", "injected"):
                with self.subTest(template_id=template_id), self.assertRaises(TemplateReleaseError):
                    service.stage_template_listings(self.session,
                        note_type=SimpleNamespace(id="note-type", user_id=1), actor_user_id=1,
                        payload={"template_listings": [{"template_id": template_id,
                            "pricing_mode": "free", "price_amount_minor": 0}]})
            stage.assert_not_called()
        self.session.commit.assert_not_called()

    def test_every_owned_unlisted_template_requires_explicit_price(self):
        item = {"attached": {"id": "mine"}, "source": {"id": "mine"}, "requires_publication": True}
        with patch.object(service, "references", return_value=[item]), \
                patch("app.services.template_marketplace_service.stage_listing") as stage:
            for payload in ({}, {"template_listings": [{"template_id": "mine"}]},
                    {"template_listings": [{"template_id": "mine", "pricing_mode": None, "price_amount_minor": 0}]}):
                with self.subTest(payload=payload), self.assertRaises(TemplateReleaseError):
                    service.stage_template_listings(self.session,
                        note_type=SimpleNamespace(id="note-type", user_id=1), actor_user_id=1, payload=payload)
            stage.assert_not_called()

    def test_own_template_reuses_standalone_listing_without_committing(self):
        item = {"attached": {"id": "mine"}, "source": {"id": "mine"}, "requires_publication": True}
        with patch.object(service, "references", return_value=[item]), \
                patch.object(service.releases, "update_row") as update, \
                patch("app.services.template_marketplace_service.stage_listing") as stage:
            service.stage_template_listings(self.session,
                note_type=SimpleNamespace(id="note-type", user_id=1), actor_user_id=1,
                payload={"template_listings": [{"template_id": "mine", "description": " Details ",
                    "primary_category": "Language", "pricing_mode": "paid", "price_amount_minor": 30000}]})
        self.assertEqual(update.call_args.args[-1], {"description": "Details", "primary_category": "Language"})
        stage.assert_called_once_with(self.session, user_id=1, template_id="mine",
            payload={"marketplace_status": "published", "pricing_mode": "paid", "price_amount_minor": 30000})
        self.session.commit.assert_not_called()
        self.session.rollback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
