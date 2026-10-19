"""Standalone template marketplace: listing, discovery, free receipt and paid sale."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from app import create_app
from models import db
from models.payment_entitlement import PaymentEntitlement
from models.payment_order import PaymentOrder
from models.template import Template
from models.template_publication import TemplatePublication
from models.template_release import TemplateRelease
from models.template_subscription import TemplateSubscription
from models.user import User
from tests.study_note_fixtures import create_note_user

FRONT = "<div class='word'>{{word}}</div>"
BACK = "{{FrontSide}}<hr>{{meaning}}"
SCHEMA = [
    {"key": "word", "label": "Từ vựng", "type": "text", "required": True},
    {"key": "meaning", "label": "Nghĩa", "type": "text", "required": False},
]


class TemplateMarketplaceTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict(os.environ, {
            "PAYOS_CLIENT_ID": "test-client-id", "PAYOS_API_KEY": "test-api-key", "PAYOS_CHECKSUM_KEY": "test-checksum-key",
        })
        self.env_patcher.start()
        self.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False,
            "PAYMENTS_ENABLED": True, "PAYMENTS_PROVIDER": "payos", "PAYMENTS_PAID_INSTALL_REQUIRED": True,
            "PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED": True, "PAYMENTS_ORDER_EXPIRY_SECONDS": 3600,
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            ids = []
            for name in ("tpl-author", "tpl-buyer", "tpl-other"):
                user = create_note_user(db.session, username=name, email=f"{name}@example.com", is_admin=False)
                user.set_password("password123")
                ids.append(user.id)
            db.session.commit()
            self.author_id, self.buyer_id, self.other_id = ids
        self.login("tpl-author")
        response = self.client.post("/api/card-templates", json={
            "name": "Kanji Card", "description": "Thẻ kanji gọn đẹp", "primary_category": "Kanji / Hán tự",
            "front_html": FRONT, "back_html": BACK, "shared_css": ".word{font-size:32px}", "input_schema": SCHEMA,
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.template_id = response.get_json()["id"]

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.env_patcher.stop()

    def login(self, username):
        with self.client.session_transaction() as session:
            session.clear()
        response = self.client.post("/api/auth/login", json={"email": f"{username}@example.com", "password": "password123"})
        self.assertEqual(response.status_code, 200)

    def list_on_market(self, **values):
        return self.client.put(f"/api/card-templates/{self.template_id}/marketplace", json={"marketplace_status": "published", **values})

    def fake_checkout(self, **kwargs):
        code = kwargs["provider_order_code"]
        return {
            "provider_code": "payos", "provider_order_code": str(code), "provider_payment_id": f"plink-{code}",
            "checkout_url": f"https://pay.payos.vn/web/{code}", "amount_minor": int(kwargs["amount_minor"]),
            "currency_code": "VND", "expires_at": kwargs.get("expires_at"),
            "provider_metadata": {"payment_reference": kwargs["payment_reference"], "checkout_url": f"https://pay.payos.vn/web/{code}", "provider_status": "PENDING"},
            "raw_response": {},
        }

    def success_webhook(self, order_id):
        with self.app.app_context():
            attempt = max(db.session.get(PaymentOrder, order_id).attempts, key=lambda row: row.created_at)
            return {
                "provider_code": "payos", "event_key": f"evt-{order_id}", "event_type": "payment.succeeded",
                "provider_order_code": attempt.provider_order_code, "provider_payment_id": attempt.provider_payment_id,
                "provider_transaction_ref": f"txn-{order_id}", "payment_reference": attempt.expected_payment_reference,
                "amount_minor": int(attempt.amount_minor or 0), "currency_code": attempt.currency_code,
                "success": True, "status": "00", "raw_payload": {},
            }

    def test_listing_publishes_a_release_and_shows_in_catalog(self):
        self.assertEqual(self.client.get("/api/marketplace/templates").get_json()["items"], [])
        response = self.list_on_market()
        self.assertEqual(response.status_code, 200, response.get_json())
        listing = response.get_json()
        self.assertEqual(listing["marketplace_status"], "published")
        self.assertEqual(listing["current_release"]["version_label"], "1.0.0")
        self.assertFalse(listing["has_unpublished_changes"])
        # Listing again without edits must not mint another release.
        self.assertEqual(self.list_on_market().status_code, 200)
        with self.app.app_context():
            self.assertEqual(TemplateRelease.query.filter_by(template_id=self.template_id).count(), 1)

        self.login("tpl-buyer")
        catalog = self.client.get("/api/marketplace/templates").get_json()
        self.assertEqual([item["id"] for item in catalog["items"]], [self.template_id])
        item = catalog["items"][0]
        self.assertEqual(item["price_display"], "Miễn phí")
        self.assertEqual([entry["key"] for entry in item["inputs"]], ["word", "meaning"])
        self.assertEqual(item["author"]["username"], "tpl-author")
        self.assertEqual(catalog["categories"], [{"name": "Kanji / Hán tự", "count": 1}])
        for query, expected in (("kanji", 1), ("tpl-author", 1), ("gọn", 1), ("không-có", 0)):
            found = self.client.get("/api/marketplace/templates", query_string={"q": query}).get_json()["items"]
            self.assertEqual(len(found), expected, query)
        self.assertEqual(len(self.client.get("/api/marketplace/templates", query_string={"pricing_mode": "paid"}).get_json()["items"]), 0)

        preview = self.client.post(f"/api/marketplace/templates/{self.template_id}/preview")
        self.assertEqual(preview.status_code, 200, preview.get_json())
        self.assertIn("Từ vựng", preview.get_json()["front_html"])

    def test_listing_requires_description_and_category(self):
        self.client.patch(f"/api/card-templates/{self.template_id}", json={"description": ""})
        response = self.list_on_market()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["field"], "description")
        self.assertEqual(self.client.get(f"/api/card-templates/{self.template_id}/marketplace").get_json()["missing_requirements"], ["description"])

    def test_free_download_creates_market_copy_that_cannot_be_republished(self):
        self.assertEqual(self.list_on_market().status_code, 200)
        self.login("tpl-buyer")
        response = self.client.post(f"/api/marketplace/templates/{self.template_id}/install")
        self.assertEqual(response.status_code, 201, response.get_json())
        local_id = response.get_json()["local_template_id"]
        again = self.client.post(f"/api/marketplace/templates/{self.template_id}/install")
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.get_json()["already_installed"])
        detail = self.client.get(f"/api/marketplace/templates/{self.template_id}").get_json()
        self.assertTrue(detail["is_installed"])
        self.assertEqual(detail["installed_template_id"], local_id)
        self.assertEqual(detail["install_count"], 1)
        with self.app.app_context():
            copy = db.session.get(Template, local_id)
            self.assertEqual((copy.origin, copy.source_template_id), ("market_copy", self.template_id))

        # The old rule stays: a downloaded copy can never be listed or sold.
        listing = self.client.get(f"/api/card-templates/{local_id}/marketplace").get_json()
        self.assertFalse(listing["can_publish"])
        self.assertEqual(listing["block_code"], "MARKET_TEMPLATE_REPUBLISH_FORBIDDEN")
        for body in ({"marketplace_status": "published"}, {"marketplace_status": "published", "pricing_mode": "paid", "price_amount_minor": 20000}, {"pricing_mode": "paid", "price_amount_minor": 1}):
            blocked = self.client.put(f"/api/card-templates/{local_id}/marketplace", json=body)
            self.assertEqual(blocked.status_code, 403)
            self.assertEqual(blocked.get_json()["error"], "MARKET_TEMPLATE_REPUBLISH_FORBIDDEN")
        self.assertEqual(self.client.post(f"/api/marketplace/templates/{local_id}/install").status_code, 404)
        self.assertEqual(self.client.get(f"/api/marketplace/templates/{local_id}").status_code, 404)
        with self.app.app_context():
            self.assertIsNone(db.session.get(TemplatePublication, local_id))

    def test_owner_cannot_download_and_delisting_hides_new_downloads(self):
        self.assertEqual(self.list_on_market().status_code, 200)
        own = self.client.post(f"/api/marketplace/templates/{self.template_id}/install")
        self.assertEqual(own.status_code, 409)
        self.assertEqual(own.get_json()["error"], "OWN_TEMPLATE")
        self.login("tpl-buyer")
        self.assertEqual(self.client.post(f"/api/marketplace/templates/{self.template_id}/install").status_code, 201)
        self.login("tpl-author")
        delisted = self.client.put(f"/api/card-templates/{self.template_id}/marketplace", json={"marketplace_status": "private"})
        self.assertEqual(delisted.get_json()["marketplace_status"], "private")
        self.login("tpl-other")
        self.assertEqual(self.client.get("/api/marketplace/templates").get_json()["items"], [])
        self.assertEqual(self.client.get(f"/api/marketplace/templates/{self.template_id}").status_code, 404)
        refused = self.client.post(f"/api/marketplace/templates/{self.template_id}/install")
        self.assertEqual(refused.status_code, 409)
        self.assertEqual(refused.get_json()["error"], "TEMPLATE_NOT_LISTED")
        # Existing recipients still see what they downloaded.
        self.login("tpl-buyer")
        self.assertEqual(self.client.get(f"/api/marketplace/templates/{self.template_id}").status_code, 200)

    def test_archived_template_cannot_be_listed(self):
        self.client.patch(f"/api/card-templates/{self.template_id}/archive", json={"archived": True})
        response = self.list_on_market()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "TEMPLATE_ARCHIVED")

    def test_paid_template_requires_checkout_then_webhook_grants_copy_and_credits_author(self):
        bad = self.list_on_market(pricing_mode="paid")
        self.assertEqual(bad.status_code, 400)
        listing = self.list_on_market(pricing_mode="paid", price_amount_minor=25000).get_json()
        self.assertEqual((listing["pricing_mode"], listing["price_amount_minor"]), ("paid", 25000))
        self.login("tpl-buyer")
        item = self.client.get("/api/marketplace/templates").get_json()["items"][0]
        self.assertEqual(item["pricing_mode"], "paid")
        with patch("app.services.payment.provider.payos_provider.create_checkout_session", side_effect=self.fake_checkout):
            response = self.client.post(f"/api/marketplace/templates/{self.template_id}/install")
        self.assertEqual(response.status_code, 202, response.get_json())
        payload = response.get_json()
        self.assertTrue(payload["payment_required"])
        order_id = payload["order"]["id"]
        self.assertEqual(payload["order"]["items"][0]["product_type"], "template")
        with self.app.app_context():
            self.assertEqual(TemplateSubscription.query.filter_by(user_id=self.buyer_id).count(), 0)

        with patch("app.services.payment.provider.payos_provider.verify_webhook_payload", return_value=self.success_webhook(order_id)):
            webhook = self.client.post("/api/payments/providers/payos/webhook", data=b"{}", content_type="application/json")
        self.assertEqual(webhook.get_json().get("status"), "processed", webhook.get_json())
        with self.app.app_context():
            entitlement = PaymentEntitlement.query.filter_by(user_id=self.buyer_id, resource_type="template", resource_ref_id=self.template_id).one()
            self.assertEqual((entitlement.status, entitlement.entitlement_type), ("active", "shared_template_install"))
            local_id = entitlement.grant_data_json["local_template_id"]
            self.assertEqual(db.session.get(Template, local_id).origin, "market_copy")
            author = db.session.get(User, self.author_id)
            self.assertGreater(int(author.balance_amount_minor or 0), 0)
        detail = self.client.get(f"/api/marketplace/templates/{self.template_id}").get_json()
        self.assertTrue(detail["is_installed"] and detail["is_purchased"])

        # A buyer who deletes the copy downloads it again without paying twice.
        self.assertEqual(self.client.delete(f"/api/card-templates/{local_id}").status_code, 200)
        again = self.client.post(f"/api/marketplace/templates/{self.template_id}/install")
        self.assertEqual(again.status_code, 201, again.get_json())

    def test_paid_template_stranger_cannot_receive_without_purchase(self):
        self.list_on_market(pricing_mode="paid", price_amount_minor=25000)
        from app.services import template_release_service
        with self.app.app_context():
            with self.assertRaises(template_release_service.TemplateReleaseError) as caught:
                template_release_service.ensure_subscription(db.session, user_id=self.other_id, source_template_id=self.template_id)
            self.assertEqual(caught.exception.code, "TEMPLATE_ACCESS_DENIED")


if __name__ == "__main__":
    unittest.main()
