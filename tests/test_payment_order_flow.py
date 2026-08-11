"""Integration tests for payment order creation and webhook fulfillment."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

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
        self.env_patcher = patch.dict(
            os.environ,
            {
                "PAYOS_CLIENT_ID": "test-client-id",
                "PAYOS_API_KEY": "test-api-key",
                "PAYOS_CHECKSUM_KEY": "test-checksum-key",
            },
        )
        self.env_patcher.start()
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "PAYMENTS_ENABLED": True,
                "PAYMENTS_PROVIDER": "payos",
                "PAYMENTS_PAID_INSTALL_REQUIRED": True,
                "PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED": True,
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
        self.env_patcher.stop()

    def _create_note_type(self, *, pricing_mode: str, price_amount_minor: int) -> str:
        with self.app.app_context():
            note_type = NoteType(
                user_id=self.owner_id,
                name=f"NT-{pricing_mode}-{price_amount_minor}",
                description="desc",
                primary_category="General",
                tags=[],
                preview_text="preview",
                pricing_mode=pricing_mode,
                price_amount_minor=price_amount_minor,
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

    def _create_deck_item(self, *, pricing_mode: str, price_amount_minor: int) -> str:
        with self.app.app_context():
            note_type_id = self._create_note_type(pricing_mode="free", price_amount_minor=0)
            deck = Deck(
                name=f"Deck-{pricing_mode}-{price_amount_minor}",
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
                price_amount_minor=price_amount_minor,
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
                "provider_code": "payos",
                "event_key": event_id,
                "event_type": "payment.succeeded",
                "provider_order_code": attempt.provider_order_code,
                "provider_payment_id": attempt.provider_payment_id,
                "provider_transaction_ref": f"txn-{event_id}",
                "payment_reference": attempt.expected_payment_reference,
                "amount_minor": int(attempt.amount_minor or 0),
                "currency_code": attempt.currency_code,
                "success": True,
                "status": "00",
                "raw_payload": {"event_id": event_id},
            }

    def _fake_checkout_session(self, **kwargs) -> dict:
        provider_order_code = kwargs["provider_order_code"]
        amount_minor = int(kwargs["amount_minor"])
        payment_reference = kwargs["payment_reference"]
        expires_at = kwargs.get("expires_at")
        return {
            "provider_code": "payos",
            "provider_order_code": str(provider_order_code),
            "provider_payment_id": f"plink-{provider_order_code}",
            "checkout_url": f"https://pay.payos.vn/web/{provider_order_code}",
            "amount_minor": amount_minor,
            "currency_code": "VND",
            "expires_at": expires_at,
            "provider_metadata": {
                "bank_bin": "970422",
                "account_no": "123456789",
                "account_name": "Flama Test",
                "provider_status": "PENDING",
                "payment_reference": payment_reference,
                "checkout_url": f"https://pay.payos.vn/web/{provider_order_code}",
                "payment_link_id": f"plink-{provider_order_code}",
                "qr_code": "000201010212...",
            },
            "raw_response": {
                "paymentLinkId": f"plink-{provider_order_code}",
                "checkoutUrl": f"https://pay.payos.vn/web/{provider_order_code}",
            },
        }

    def _fake_payment_link_state(self, *, status: str) -> dict:
        normalized_status = str(status or "PENDING").upper()
        return {
            "provider_code": "payos",
            "provider_payment_id": "plink-existing",
            "provider_order_code": "123456789",
            "status": normalized_status,
            "amount_minor": 50000,
            "amount_paid_minor": 0 if normalized_status != "PAID" else 50000,
            "amount_remaining_minor": 50000 if normalized_status != "PAID" else 0,
            "cancellation_reason": "User left checkout" if normalized_status == "CANCELLED" else None,
            "canceled_at": "2026-03-27T12:00:00" if normalized_status == "CANCELLED" else None,
            "created_at": "2026-03-27T11:00:00",
            "raw_response": {"status": normalized_status},
        }

    def test_free_note_type_install_still_creates_install_row(self):
        note_type_id = self._create_note_type(pricing_mode="free", price_amount_minor=0)

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
        deck_item_id = self._create_deck_item(pricing_mode="free", price_amount_minor=0)

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
        note_type_id = self._create_note_type(pricing_mode="paid", price_amount_minor=50000)

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            install_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")
        self.assertEqual(install_response.status_code, 202)
        install_payload = install_response.get_json() or {}
        self.assertTrue(install_payload.get("payment_required"))
        order_payload = install_payload.get("order") or {}
        order_id = order_payload.get("id")
        self.assertTrue(order_id)
        provider_metadata = ((order_payload.get("active_attempt") or {}).get("provider_metadata") or {})
        self.assertIn("/payments/marketplace-result", provider_metadata.get("return_url") or "")
        self.assertIn("/payments/marketplace-result", provider_metadata.get("cancel_url") or "")
        self.assertEqual((order_payload.get("status_display") or {}).get("label"), "Đang chờ thanh toán")
        self.assertTrue(order_payload.get("order_detail_lines"))
        self.assertIn("Thanh toán đúng số tiền của đơn hàng.", order_payload.get("instructions") or [])

        with self.app.app_context():
            self.assertIsNone(
                NoteTypeInstall.query.filter_by(
                    source_note_type_id=note_type_id,
                    user_id=self.buyer_id,
                ).first()
            )

        with patch(
            "app.services.payment.provider.payos_provider.verify_webhook_payload",
            return_value=self._build_success_webhook_payload(order_id, event_id="evt-note-type-1"),
        ):
            webhook_response = self.client.post(
                "/api/payments/providers/payos/webhook",
                data=b"{}",
                content_type="application/json",
            )
        self.assertEqual(webhook_response.status_code, 200)
        webhook_payload = webhook_response.get_json() or {}
        self.assertEqual(webhook_payload.get("status"), "processed")

        order_response = self.client.get(f"/api/payments/orders/{order_id}")
        self.assertEqual(order_response.status_code, 200)
        order_detail = order_response.get_json() or {}
        self.assertEqual(order_detail.get("status"), "paid")
        self.assertEqual(order_detail.get("grant_status"), "completed")
        self.assertEqual((order_detail.get("status_display") or {}).get("label"), "Thanh toán thành công")
        self.assertIn("Quyền truy cập đã được cấp tự động.", order_detail.get("instructions") or [])

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
        deck_item_id = self._create_deck_item(pricing_mode="paid", price_amount_minor=75000)

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            install_response = self.client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_response.status_code, 202)
        install_payload = install_response.get_json() or {}
        order_id = ((install_payload.get("order") or {}).get("id"))
        self.assertTrue(order_id)
        provider_metadata = (((install_payload.get("order") or {}).get("active_attempt") or {}).get("provider_metadata") or {})
        self.assertIn("/payments/marketplace-result", provider_metadata.get("return_url") or "")
        self.assertIn("/payments/marketplace-result", provider_metadata.get("cancel_url") or "")

        with self.app.app_context():
            self.assertIsNone(
                DeckInstall.query.filter_by(
                    deck_item_id=deck_item_id,
                    user_id=self.buyer_id,
                ).first()
            )

        payload = self._build_success_webhook_payload(order_id, event_id="evt-deck-1")
        with patch(
            "app.services.payment.provider.payos_provider.verify_webhook_payload",
            return_value=payload,
        ):
            first_response = self.client.post(
                "/api/payments/providers/payos/webhook",
                data=b"{}",
                content_type="application/json",
            )
        self.assertEqual(first_response.status_code, 200)
        self.assertEqual((first_response.get_json() or {}).get("status"), "processed")

        with patch(
            "app.services.payment.provider.payos_provider.verify_webhook_payload",
            return_value=payload,
        ):
            duplicate_response = self.client.post(
                "/api/payments/providers/payos/webhook",
                data=b"{}",
                content_type="application/json",
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

    def test_paid_note_type_amount_mismatch_moves_order_to_manual_review_with_detail_message(self):
        note_type_id = self._create_note_type(pricing_mode="paid", price_amount_minor=65000)

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            install_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")
        self.assertEqual(install_response.status_code, 202)
        order_id = (((install_response.get_json() or {}).get("order") or {}).get("id"))
        self.assertTrue(order_id)

        mismatch_payload = self._build_success_webhook_payload(order_id, event_id="evt-note-type-mismatch-1")
        mismatch_payload["amount_minor"] = int(mismatch_payload["amount_minor"] or 0) + 5000

        with patch(
            "app.services.payment.provider.payos_provider.verify_webhook_payload",
            return_value=mismatch_payload,
        ):
            webhook_response = self.client.post(
                "/api/payments/providers/payos/webhook",
                data=b"{}",
                content_type="application/json",
            )
        self.assertEqual(webhook_response.status_code, 202)
        self.assertEqual((webhook_response.get_json() or {}).get("status"), "manual_review")

        order_response = self.client.get(f"/api/payments/orders/{order_id}")
        self.assertEqual(order_response.status_code, 200)
        order_detail = order_response.get_json() or {}
        self.assertEqual(order_detail.get("status"), "under_review")
        self.assertEqual((order_detail.get("status_display") or {}).get("label"), "Cần kiểm tra thủ công")
        self.assertIn("Không thanh toán lại ngay.", order_detail.get("next_action") or "")
        line_keys = {row.get("key") for row in (order_detail.get("order_detail_lines") or [])}
        self.assertIn("payment_reference", line_keys)
        self.assertIn(
            "Không thanh toán lại ngay để tránh bị trừ tiền nhiều lần.",
            order_detail.get("instructions") or [],
        )

    def test_paid_note_type_second_install_reuses_existing_pending_payos_attempt(self):
        note_type_id = self._create_note_type(pricing_mode="paid", price_amount_minor=45000)

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ) as create_mock:
            first_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")
            with patch(
                "app.services.payment.provider.payos_provider.get_payment_link_state",
                return_value=self._fake_payment_link_state(status="PENDING"),
            ) as lookup_mock:
                second_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")

        self.assertEqual(first_response.status_code, 202)
        self.assertEqual(second_response.status_code, 202)
        first_order = ((first_response.get_json() or {}).get("order") or {})
        second_payload = second_response.get_json() or {}
        second_order = second_payload.get("order") or {}

        self.assertEqual(first_order.get("id"), second_order.get("id"))
        self.assertFalse(second_payload.get("created"))
        self.assertEqual(create_mock.call_count, 1)
        lookup_mock.assert_called_once()

    def test_paid_note_type_second_install_creates_new_order_when_old_payos_attempt_expired(self):
        note_type_id = self._create_note_type(pricing_mode="paid", price_amount_minor=47000)

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ) as create_mock:
            first_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")
            with patch(
                "app.services.payment.provider.payos_provider.get_payment_link_state",
                return_value=self._fake_payment_link_state(status="EXPIRED"),
            ) as lookup_mock:
                second_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")

        self.assertEqual(first_response.status_code, 202)
        self.assertEqual(second_response.status_code, 202)
        first_order = ((first_response.get_json() or {}).get("order") or {})
        second_payload = second_response.get_json() or {}
        second_order = second_payload.get("order") or {}

        self.assertNotEqual(first_order.get("id"), second_order.get("id"))
        self.assertTrue(second_payload.get("created"))
        self.assertEqual(create_mock.call_count, 2)
        lookup_mock.assert_called_once()

        with self.app.app_context():
            expired_order = PaymentOrder.query.get(first_order.get("id"))
            self.assertIsNotNone(expired_order)
            self.assertEqual(expired_order.status, "expired")
            latest_attempt = max(expired_order.attempts, key=lambda row: row.created_at)
            self.assertEqual(latest_attempt.status, "expired")

    def test_paid_note_type_return_flow_auto_grants_when_payos_state_is_paid(self):
        note_type_id = self._create_note_type(pricing_mode="paid", price_amount_minor=50000)

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            install_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")

        self.assertEqual(install_response.status_code, 202)
        order_id = (((install_response.get_json() or {}).get("order") or {}).get("id"))
        self.assertTrue(order_id)

        with patch(
            "app.services.payment.provider.payos_provider.get_payment_link_state",
            return_value=self._fake_payment_link_state(status="PAID"),
        ):
            order_response = self.client.get(f"/api/payments/orders/{order_id}")

        self.assertEqual(order_response.status_code, 200)
        order_detail = order_response.get_json() or {}
        self.assertEqual(order_detail.get("status"), "paid")
        self.assertEqual(order_detail.get("grant_status"), "completed")
        self.assertEqual((order_detail.get("status_display") or {}).get("code"), "paid")

        with self.app.app_context():
            install = NoteTypeInstall.query.filter_by(
                source_note_type_id=note_type_id,
                user_id=self.buyer_id,
            ).first()
            self.assertIsNotNone(install)

    def test_paid_note_type_second_install_returns_already_installed_after_payos_paid_sync(self):
        note_type_id = self._create_note_type(pricing_mode="paid", price_amount_minor=50000)

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            first_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")

        self.assertEqual(first_response.status_code, 202)

        with patch(
            "app.services.payment.provider.payos_provider.get_payment_link_state",
            return_value=self._fake_payment_link_state(status="PAID"),
        ):
            second_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")

        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.get_json() or {}
        self.assertFalse(second_payload.get("payment_required"))
        self.assertTrue(second_payload.get("already_installed"))
        self.assertEqual(second_payload.get("source_note_type_id"), note_type_id)

    def test_marketplace_payment_result_page_renders(self):
        note_type_id = self._create_note_type(pricing_mode="paid", price_amount_minor=33000)

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            install_response = self.client.post(f"/api/shared/note-types/{note_type_id}/install")

        self.assertEqual(install_response.status_code, 202)
        order_id = (((install_response.get_json() or {}).get("order") or {}).get("id"))
        self.assertTrue(order_id)

        response = self.client.get(
            "/payments/marketplace-result",
            query_string={
                "payment_order_id": order_id,
                "payment_product_type": "note_type",
                "payment_product_ref_id": note_type_id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', response.data)


if __name__ == "__main__":
    unittest.main()
