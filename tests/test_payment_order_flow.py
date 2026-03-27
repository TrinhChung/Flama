"""Integration tests for payment order creation and webhook fulfillment."""

from __future__ import annotations

import unittest

from app import create_app
from models import db
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.payment_entitlement import PaymentEntitlement
from models.payment_order import PaymentOrder
from models.payment_webhook_event import PaymentWebhookEvent
from models.template import Template
from models.user import User


class PaymentOrderFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "PAYMENTS_V1_ENABLED": True,
                "PAYMENTS_PAID_INSTALL_REQUIRED": True,
                "PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED": True,
                "PAYMENTS_VIETQR_ACCOUNT_NO": "123456789",
                "PAYMENTS_VIETQR_ACCOUNT_NAME": "Flama Test",
                "PAYMENTS_VIETQR_BANK_BIN": "970422",
                "PAYMENTS_VIETQR_TEMPLATE": "compact2",
                "PAYMENTS_VIETQR_WEBHOOK_SECRET": "test-secret",
                "PAYMENTS_ORDER_EXPIRY_SECONDS": 3600,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            owner = User(username="payment-owner", email="payment-owner@example.com", is_admin=False)
            owner.set_password("password")
            buyer = User(username="payment-buyer", email="payment-buyer@example.com", is_admin=False)
            buyer.set_password("password")
            db.session.add_all([owner, buyer])
            db.session.commit()
            self.owner_id = owner.id
            self.buyer_id = buyer.id

        self.client.post(
            "/login",
            data={"email": "payment-buyer@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_note_type(self, *, pricing_mode: str, price_cents: int) -> str:
        with self.app.app_context():
            note_type = NoteType(
                user_id=self.owner_id,
                name=f"NT-{pricing_mode}-{price_cents}",
                description="desc",
                primary_category="General",
                tags=[],
                preview_text="preview",
                pricing_mode=pricing_mode,
                price_cents=price_cents,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(note_type)
            db.session.flush()
            db.session.add(
                FieldDef(
                    note_type_id=note_type.id,
                    name="Word",
                    field_type="text",
                    position=0,
                    required=True,
                )
            )
            db.session.add(
                Template(
                    note_type_id=note_type.id,
                    name="Card 1",
                    front_html="{{Word}}",
                    back_html="{{Word}}",
                    shared_css="",
                    position=0,
                    is_default=True,
                )
            )
            db.session.commit()
            return note_type.id

    def _create_deck_item(self, *, pricing_mode: str, price_cents: int) -> str:
        with self.app.app_context():
            note_type_id = self._create_note_type(pricing_mode="free", price_cents=0)
            deck = Deck(
                name=f"Deck-{pricing_mode}-{price_cents}",
                owner_user_id=self.owner_id,
                note_type_id=note_type_id,
            )
            db.session.add(deck)
            db.session.flush()

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.owner_id,
                source_deck_id=deck.id,
                source_note_type_id=note_type_id,
                title=f"Deck Item {pricing_mode}",
                description="desc",
                primary_category="General",
                tags=[],
                preview_text="preview",
                pricing_mode=pricing_mode,
                price_cents=price_cents,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            return deck_item.id

    def _build_success_webhook_payload(self, order_id: str, *, event_id: str) -> dict:
        with self.app.app_context():
            order = PaymentOrder.query.get(order_id)
            self.assertIsNotNone(order)
            attempt = max(order.attempts, key=lambda row: row.created_at)
            return {
                "event_id": event_id,
                "event_type": "payment.succeeded",
                "provider_order_code": attempt.provider_order_code,
                "provider_payment_id": f"provider-{event_id}",
                "provider_transaction_ref": f"txn-{event_id}",
                "payment_reference": attempt.expected_payment_reference,
                "amount_minor": int(attempt.amount_minor or 0),
                "currency_code": attempt.currency_code,
                "status": "success",
            }

    def test_free_note_type_install_still_creates_install_row(self):
        note_type_id = self._create_note_type(pricing_mode="free", price_cents=0)

        response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")
        self.assertEqual(response.status_code, 201)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("source_note_type_id"), note_type_id)

        with self.app.app_context():
            install = NoteTypeInstall.query.filter_by(
                source_note_type_id=note_type_id,
                user_id=self.buyer_id,
            ).first()
            self.assertIsNotNone(install)
            self.assertEqual(PaymentOrder.query.count(), 0)

    def test_free_deck_install_still_creates_install_row(self):
        deck_item_id = self._create_deck_item(pricing_mode="free", price_cents=0)

        response = self.client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(response.status_code, 201)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("deck_item_id"), deck_item_id)

        with self.app.app_context():
            install = DeckInstall.query.filter_by(
                deck_item_id=deck_item_id,
                user_id=self.buyer_id,
            ).first()
            self.assertIsNotNone(install)
            self.assertEqual(PaymentOrder.query.count(), 0)

    def test_paid_note_type_install_returns_order_until_webhook_confirms(self):
        note_type_id = self._create_note_type(pricing_mode="paid", price_cents=50000)

        install_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")
        self.assertEqual(install_response.status_code, 202)
        install_payload = install_response.get_json() or {}
        self.assertTrue(install_payload.get("payment_required"))
        order_payload = install_payload.get("order") or {}
        order_id = order_payload.get("id")
        self.assertTrue(order_id)

        with self.app.app_context():
            self.assertIsNone(
                NoteTypeInstall.query.filter_by(
                    source_note_type_id=note_type_id,
                    user_id=self.buyer_id,
                ).first()
            )

        webhook_response = self.client.post(
            "/api/payments/providers/vietqr/webhook",
            json=self._build_success_webhook_payload(order_id, event_id="evt-note-type-1"),
            headers={"X-Flama-Vietqr-Webhook-Secret": "test-secret"},
        )
        self.assertEqual(webhook_response.status_code, 200)
        webhook_payload = webhook_response.get_json() or {}
        self.assertEqual(webhook_payload.get("status"), "processed")

        order_response = self.client.get(f"/api/payments/orders/{order_id}")
        self.assertEqual(order_response.status_code, 200)
        order_detail = order_response.get_json() or {}
        self.assertEqual(order_detail.get("status"), "paid")
        self.assertEqual(order_detail.get("grant_status"), "completed")

        with self.app.app_context():
            install = NoteTypeInstall.query.filter_by(
                source_note_type_id=note_type_id,
                user_id=self.buyer_id,
            ).first()
            self.assertIsNotNone(install)
            entitlement = PaymentEntitlement.query.filter_by(
                user_id=self.buyer_id,
                resource_type="note_type",
                resource_ref_id=note_type_id,
            ).first()
            self.assertIsNotNone(entitlement)
            self.assertEqual(entitlement.status, "active")

    def test_paid_deck_install_duplicate_webhook_does_not_duplicate_entitlement_or_install(self):
        deck_item_id = self._create_deck_item(pricing_mode="paid", price_cents=75000)

        install_response = self.client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_response.status_code, 202)
        install_payload = install_response.get_json() or {}
        order_id = ((install_payload.get("order") or {}).get("id"))
        self.assertTrue(order_id)

        with self.app.app_context():
            self.assertIsNone(
                DeckInstall.query.filter_by(
                    deck_item_id=deck_item_id,
                    user_id=self.buyer_id,
                ).first()
            )

        payload = self._build_success_webhook_payload(order_id, event_id="evt-deck-1")
        first_response = self.client.post(
            "/api/payments/providers/vietqr/webhook",
            json=payload,
            headers={"X-Flama-Vietqr-Webhook-Secret": "test-secret"},
        )
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual((first_response.get_json() or {}).get("status"), "processed")

        duplicate_response = self.client.post(
            "/api/payments/providers/vietqr/webhook",
            json=payload,
            headers={"X-Flama-Vietqr-Webhook-Secret": "test-secret"},
        )
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual((duplicate_response.get_json() or {}).get("status"), "duplicate")

        with self.app.app_context():
            self.assertEqual(
                DeckInstall.query.filter_by(deck_item_id=deck_item_id, user_id=self.buyer_id).count(),
                1,
            )
            self.assertEqual(
                PaymentEntitlement.query.filter_by(
                    user_id=self.buyer_id,
                    resource_type="deck_marketplace_item",
                    resource_ref_id=deck_item_id,
                ).count(),
                1,
            )
            self.assertEqual(PaymentWebhookEvent.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
