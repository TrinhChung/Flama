from __future__ import annotations

import os
import unittest
from datetime import datetime
from unittest.mock import patch

from payos.types import PaymentLink

from app import create_app
from models import db
from models.payment_entitlement import PaymentEntitlement
from models.payment_order import PaymentOrder
from models.user import User


class SupportDonationPaymentFlowTests(unittest.TestCase):
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
                "PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED": True,
                "PAYMENTS_ORDER_EXPIRY_SECONDS": 3600,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            user = User(username="support-user", email="support-user@example.com", is_admin=False)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.env_patcher.stop()

    def _login(self):
        return self.client.post(
            "/login",
            data={"email": "support-user@example.com", "password": "password"},
            follow_redirects=True,
        )

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

    def _build_saved_success_webhook_payload(self, order_id: str, *, event_id: str) -> dict:
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

    def test_support_donation_result_page_renders_with_history_action_for_logged_in_user(self):
        self._login()

        response = self.client.get("/support-donation/result")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"support-donation-result-root", response.data)
        self.assertIn(b"supportDonationHistoryBtn", response.data)

    def test_anonymous_support_donation_does_not_require_login_or_create_order(self):
        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            response = self.client.post(
                "/api/support-donation/checkout",
                json={
                    "amount_minor": 120000,
                    "return_url": "http://localhost/support-donation",
                    "cancel_url": "http://localhost/support-donation",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("checkout_mode"), "anonymous")
        self.assertTrue(((payload.get("checkout") or {}).get("checkout_url")))

        with self.app.app_context():
            self.assertEqual(PaymentOrder.query.count(), 0)

    def test_v1_support_checkout_exposes_frontend_checkout_url(self):
        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            response = self.client.post(
                "/api/support-donation/checkout",
                json={"amount_minor": 120000},
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("checkout_mode"), "anonymous")
        self.assertTrue(payload.get("checkout_url"))
        self.assertEqual(
            payload.get("checkout_url"),
            ((payload.get("checkout") or {}).get("checkout_url")),
        )

    def test_anonymous_support_donation_defaults_to_result_page_when_return_urls_are_omitted(self):
        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            response = self.client.post(
                "/api/support-donation/checkout",
                json={"amount_minor": 125000},
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json() or {}
        provider_metadata = ((payload.get("checkout") or {}).get("provider_metadata") or {})
        self.assertIn("/support-donation/result", provider_metadata.get("return_url") or "")
        self.assertIn("/support-donation/result", provider_metadata.get("cancel_url") or "")

    def test_logged_in_user_can_force_anonymous_support_donation(self):
        self._login()

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            response = self.client.post(
                "/api/support-donation/checkout",
                json={
                    "amount_minor": 90000,
                    "anonymous": True,
                    "return_url": "http://localhost/support-donation",
                    "cancel_url": "http://localhost/support-donation",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("checkout_mode"), "anonymous")

        with self.app.app_context():
            self.assertEqual(PaymentOrder.query.count(), 0)

    def test_logged_in_support_donation_creates_saved_payment_order(self):
        self._login()

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            response = self.client.post(
                "/api/support-donation/checkout",
                json={
                    "amount_minor": 80000,
                    "anonymous": False,
                    "return_url": "http://localhost/support-donation",
                    "cancel_url": "http://localhost/support-donation",
                },
            )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("checkout_mode"), "saved")
        order_payload = payload.get("order") or {}
        self.assertTrue(order_payload.get("id"))
        self.assertTrue(((order_payload.get("active_attempt") or {}).get("checkout") or {}).get("checkout_url"))

        with self.app.app_context():
            order = PaymentOrder.query.get(order_payload.get("id"))
            self.assertIsNotNone(order)
            self.assertEqual(order.user_id, self.user_id)
            self.assertEqual(order.items[0].product_type, "support_donation")
            self.assertEqual(order.items[0].product_ref_id, "support_donation_80000")
            self.assertEqual(PaymentEntitlement.query.count(), 0)

    def test_anonymous_support_donation_status_sync_can_show_paid(self):
        with patch(
            "app.services.payment.provider.payos_provider.get_payment_link_state",
            return_value={
                "provider_code": "payos",
                "provider_payment_id": "plink-anon-1",
                "provider_order_code": "123456789",
                "status": "PAID",
                "amount_minor": 110000,
                "amount_paid_minor": 110000,
                "amount_remaining_minor": 0,
                "currency_code": "VND",
                "payment_reference": "DONATE123",
                "checkout_url": "https://pay.payos.vn/web/123456789",
                "created_at": datetime.utcnow().isoformat(),
                "raw_response": {"status": "PAID"},
            },
        ):
            response = self.client.get(
                "/api/support-donation/checkout-status",
                query_string={"provider_order_code": "123456789"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertTrue(payload.get("is_support_donation"))
        self.assertEqual(payload.get("status"), "paid")
        self.assertEqual(payload.get("grant_status"), "completed")
        self.assertIn("Cảm ơn", payload.get("headline", ""))
        self.assertIn("ghi nhận thành công", payload.get("message", ""))

    def test_anonymous_support_donation_status_sync_can_show_friendly_failed_message(self):
        with patch(
            "app.services.payment.provider.payos_provider.get_payment_link_state",
            return_value={
                "provider_code": "payos",
                "provider_payment_id": "plink-anon-2",
                "provider_order_code": "987654321",
                "status": "FAILED",
                "amount_minor": 90000,
                "amount_paid_minor": 0,
                "amount_remaining_minor": 90000,
                "currency_code": "VND",
                "payment_reference": "DONATE999",
                "checkout_url": "https://pay.payos.vn/web/987654321",
                "created_at": datetime.utcnow().isoformat(),
                "raw_response": {"status": "FAILED"},
            },
        ):
            response = self.client.get(
                "/api/support-donation/checkout-status",
                query_string={"provider_order_code": "987654321"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("status"), "failed")
        self.assertIn("Rất tiếc", payload.get("headline", ""))
        self.assertIn("chưa được ghi nhận", payload.get("message", ""))
        self.assertIn("phiên mới", payload.get("next_action", ""))

    def test_saved_support_donation_webhook_marks_order_paid_and_records_entitlement(self):
        self._login()

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            create_response = self.client.post(
                "/api/support-donation/checkout",
                json={
                    "amount_minor": 130000,
                    "anonymous": False,
                    "return_url": "http://localhost/support-donation",
                    "cancel_url": "http://localhost/support-donation",
                },
            )

        self.assertEqual(create_response.status_code, 201)
        order_id = (((create_response.get_json() or {}).get("order") or {}).get("id"))
        self.assertTrue(order_id)

        with patch(
            "app.services.payment.provider.payos_provider.verify_webhook_payload",
            return_value=self._build_saved_success_webhook_payload(order_id, event_id="evt-support-donation-1"),
        ):
            webhook_response = self.client.post(
                "/api/payments/providers/payos/webhook",
                data=b"{}",
                content_type="application/json",
            )

        self.assertEqual(webhook_response.status_code, 200)
        self.assertEqual((webhook_response.get_json() or {}).get("status"), "processed")

        with self.app.app_context():
            order = PaymentOrder.query.get(order_id)
            self.assertIsNotNone(order)
            self.assertEqual(order.status, "paid")
            self.assertEqual(order.grant_status, "completed")
            entitlement = PaymentEntitlement.query.filter_by(
                user_id=self.user_id,
                resource_type="support_donation",
                resource_ref_id="support_donation_130000",
            ).first()
            self.assertIsNotNone(entitlement)
            self.assertEqual(entitlement.status, "active")

        order_response = self.client.get(f"/api/payments/orders/{order_id}")
        self.assertEqual(order_response.status_code, 200)
        order_payload = order_response.get_json() or {}
        self.assertIn("Cảm ơn", order_payload.get("headline", ""))
        self.assertIn("ghi nhận thành công", order_payload.get("message", ""))

    def test_saved_support_donation_return_flow_handles_canceled_payment_link_without_optional_fields(self):
        self._login()

        with patch(
            "app.services.payment.provider.payos_provider.create_checkout_session",
            side_effect=self._fake_checkout_session,
        ):
            create_response = self.client.post(
                "/api/support-donation/checkout",
                json={
                    "amount_minor": 95000,
                    "anonymous": False,
                    "return_url": "http://localhost/support-donation",
                    "cancel_url": "http://localhost/support-donation",
                },
            )

        self.assertEqual(create_response.status_code, 201)
        order_id = (((create_response.get_json() or {}).get("order") or {}).get("id"))
        self.assertTrue(order_id)

        with self.app.app_context():
            order = PaymentOrder.query.get(order_id)
            self.assertIsNotNone(order)
            attempt = max(order.attempts, key=lambda row: row.created_at)
            provider_link = PaymentLink(
                id=str(attempt.provider_payment_id),
                order_code=int(attempt.provider_order_code),
                amount=int(attempt.amount_minor or 0),
                amount_paid=0,
                amount_remaining=int(attempt.amount_minor or 0),
                status="CANCELLED",
                created_at="2026-03-28T11:24:05Z",
                transactions=[],
                cancellation_reason="User cancelled payment",
                canceled_at="2026-03-28T11:24:05Z",
            )

        with patch(
            "app.services.payment.provider.payos_provider.assert_payos_provider_available",
            return_value=None,
        ), patch(
            "app.services.payment.provider.payos_provider.payos_client.get_payment_link",
            return_value=provider_link,
        ):
            order_response = self.client.get(f"/api/payments/orders/{order_id}")

        self.assertEqual(order_response.status_code, 200)
        order_payload = order_response.get_json() or {}
        self.assertEqual(order_payload.get("status"), "canceled")
        self.assertEqual((order_payload.get("status_display") or {}).get("code"), "canceled")
        self.assertIn("dừng", order_payload.get("headline", "").lower())
        self.assertIn("phiên mới", order_payload.get("next_action", "").lower())


if __name__ == "__main__":
    unittest.main()
