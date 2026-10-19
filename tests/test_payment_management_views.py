from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from app import create_app
from models import db
from models.note_type import NoteType
from models.payment_attempt import PaymentAttempt
from models.payment_entitlement import PaymentEntitlement
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.payment_webhook_event import PaymentWebhookEvent
from models.user import User
from models.user_role import UserRole


class PaymentManagementViewTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "PAYMENTS_ENABLED": True,
                "PAYMENTS_PROVIDER": "payos",
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            admin_role = UserRole.query.filter_by(code="admin").first()
            regular_role = UserRole.query.filter_by(code="regular").first()
            assert admin_role is not None
            assert regular_role is not None

            admin = User(
                username="admin-payments",
                email="admin-payments@example.com",
                is_admin=True,
                role_id=admin_role.id,
                is_disabled=False,
            )
            admin.set_password("password")
            creator = User(
                username="creator-one",
                email="creator-one@example.com",
                is_admin=False,
                role_id=regular_role.id,
                is_disabled=False,
            )
            creator.set_password("password")
            buyer = User(
                username="buyer-one",
                email="buyer-one@example.com",
                is_admin=False,
                role_id=regular_role.id,
                is_disabled=False,
            )
            buyer.set_password("password")
            other_buyer = User(
                username="buyer-two",
                email="buyer-two@example.com",
                is_admin=False,
                role_id=regular_role.id,
                is_disabled=False,
            )
            other_buyer.set_password("password")
            db.session.add_all([admin, creator, buyer, other_buyer])
            db.session.flush()

            product = NoteType(
                user_id=creator.id,
                name="Kana Pack",
                description="desc",
                pricing_mode="paid",
                price_amount_minor=50000,
                publish_status="published",
            )
            db.session.add(product)
            db.session.flush()

            now = datetime.utcnow()
            paid_order = PaymentOrder(
                user_id=buyer.id,
                merchant_order_code="ORD-PAID-001",
                status="paid",
                grant_status="completed",
                currency_code="VND",
                subtotal_amount_minor=50000,
                total_amount_minor=50000,
                paid_at=now - timedelta(hours=20),
                closed_at=now - timedelta(hours=20),
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(hours=20),
            )
            pending_order = PaymentOrder(
                user_id=buyer.id,
                merchant_order_code="ORD-PENDING-001",
                status="pending_payment",
                grant_status="pending",
                currency_code="VND",
                subtotal_amount_minor=75000,
                total_amount_minor=75000,
                created_at=now - timedelta(hours=6),
                updated_at=now - timedelta(hours=6),
            )
            failed_order = PaymentOrder(
                user_id=other_buyer.id,
                merchant_order_code="ORD-FAILED-001",
                status="failed",
                grant_status="pending",
                currency_code="VND",
                subtotal_amount_minor=65000,
                total_amount_minor=65000,
                closed_at=now - timedelta(hours=5),
                created_at=now - timedelta(hours=8),
                updated_at=now - timedelta(hours=5),
            )
            db.session.add_all([paid_order, pending_order, failed_order])
            db.session.flush()

            paid_item = PaymentOrderItem(
                order_id=paid_order.id,
                product_type="note_type",
                product_ref_id=product.id,
                quantity=1,
                unit_amount_minor=50000,
                line_total_amount_minor=50000,
                title_snapshot="Kana Pack",
                product_snapshot_json={"seller_name": "creator-one"},
            )
            pending_item = PaymentOrderItem(
                order_id=pending_order.id,
                product_type="note_type",
                product_ref_id=product.id,
                quantity=1,
                unit_amount_minor=75000,
                line_total_amount_minor=75000,
                title_snapshot="Kana Pack Premium",
                product_snapshot_json={"seller_name": "creator-one"},
            )
            failed_item = PaymentOrderItem(
                order_id=failed_order.id,
                product_type="note_type",
                product_ref_id=product.id,
                quantity=1,
                unit_amount_minor=65000,
                line_total_amount_minor=65000,
                title_snapshot="Kana Pack Failed",
                product_snapshot_json={"seller_name": "creator-one"},
            )
            db.session.add_all([paid_item, pending_item, failed_item])
            db.session.flush()

            paid_attempt = PaymentAttempt(
                order_id=paid_order.id,
                provider_code="payos",
                payment_method_code="payos_checkout",
                status="confirmed",
                amount_minor=50000,
                currency_code="VND",
                provider_payment_id="plink-paid-001",
                provider_order_code="10001",
                expected_payment_reference="FLAMA001",
                checkout_url="https://pay.payos.vn/web/10001",
                provider_metadata_json={"account_no": "123456789", "bank_bin": "970422"},
                confirmed_at=now - timedelta(hours=20),
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(hours=20),
            )
            pending_attempt = PaymentAttempt(
                order_id=pending_order.id,
                provider_code="payos",
                payment_method_code="payos_checkout",
                status="pending",
                amount_minor=75000,
                currency_code="VND",
                provider_payment_id="plink-pending-001",
                provider_order_code="10002",
                expected_payment_reference="FLAMA002",
                checkout_url="https://pay.payos.vn/web/10002",
                provider_metadata_json={"account_no": "222233334444", "bank_bin": "970422"},
                expires_at=now + timedelta(hours=2),
                created_at=now - timedelta(hours=6),
                updated_at=now - timedelta(hours=6),
            )
            failed_attempt = PaymentAttempt(
                order_id=failed_order.id,
                provider_code="payos",
                payment_method_code="payos_checkout",
                status="failed",
                amount_minor=65000,
                currency_code="VND",
                provider_payment_id="plink-failed-001",
                provider_order_code="10003",
                expected_payment_reference="FLAMA003",
                checkout_url="https://pay.payos.vn/web/10003",
                provider_metadata_json={"account_no": "999900001111", "bank_bin": "970422"},
                failed_at=now - timedelta(hours=5),
                failure_message="Provider rejected the payment.",
                created_at=now - timedelta(hours=8),
                updated_at=now - timedelta(hours=5),
            )
            db.session.add_all([paid_attempt, pending_attempt, failed_attempt])
            db.session.flush()

            db.session.add(
                PaymentWebhookEvent(
                    provider_code="payos",
                    event_key="evt-paid-1",
                    event_type="payment.succeeded",
                    payment_attempt_id=paid_attempt.id,
                    payment_order_id=paid_order.id,
                    signature_valid=True,
                    processing_status="processed",
                    payload_json={"id": "evt-paid-1"},
                    received_at=now - timedelta(hours=20),
                )
            )
            db.session.add(
                PaymentWebhookEvent(
                    provider_code="payos",
                    event_key="evt-failed-1",
                    event_type="payment.failed",
                    payment_attempt_id=failed_attempt.id,
                    payment_order_id=failed_order.id,
                    signature_valid=False,
                    processing_status="failed",
                    error_message="Signature invalid.",
                    payload_json={"id": "evt-failed-1"},
                    received_at=now - timedelta(hours=5),
                )
            )
            db.session.add(
                PaymentEntitlement(
                    user_id=buyer.id,
                    payment_order_id=paid_order.id,
                    payment_order_item_id=paid_item.id,
                    payment_attempt_id=paid_attempt.id,
                    entitlement_type="marketplace_note_type",
                    resource_type="note_type",
                    resource_ref_id=product.id,
                    status="active",
                    granted_at=now - timedelta(hours=20),
                    effective_from=now - timedelta(hours=20),
                    grant_data_json={},
                )
            )
            db.session.commit()

            self.admin_email = admin.email
            self.buyer_email = buyer.email
            self.other_buyer_email = other_buyer.email
            self.buyer_paid_order_id = paid_order.id
            self.buyer_pending_order_id = pending_order.id
            self.other_buyer_failed_order_id = failed_order.id
            self.paid_attempt_id = paid_attempt.id
            self.failed_attempt_id = failed_attempt.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, email: str):
        return self.client.post(
            "/login",
            data={"email": email, "password": "password"},
            follow_redirects=True,
        )

    def test_user_order_history_lists_only_current_user_orders(self):
        self._login(self.buyer_email)
        page_response = self.client.get("/orders", follow_redirects=False)
        self.assertEqual(page_response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', page_response.data)

        api_response = self.client.get("/api/orders")
        self.assertEqual(api_response.status_code, 200)
        order_codes = {
            row.get("merchant_order_code")
            for row in (api_response.get_json() or {}).get("items", [])
        }
        self.assertIn("ORD-PAID-001", order_codes)
        self.assertIn("ORD-PENDING-001", order_codes)
        self.assertNotIn("ORD-FAILED-001", order_codes)

    def test_user_cannot_open_other_user_order_detail(self):
        self._login(self.buyer_email)
        response = self.client.get(f"/api/orders/{self.other_buyer_failed_order_id}")
        self.assertEqual(response.status_code, 404)

    def test_admin_payment_pages_require_admin_access(self):
        self._login(self.buyer_email)
        response = self.client.get("/api/admin/payments/orders")
        self.assertEqual(response.status_code, 403)

    def test_admin_orders_page_supports_status_and_seller_filters(self):
        self._login(self.admin_email)
        response = self.client.get(
            "/api/admin/payments/orders?order_status=pending_payment&seller=creator-one",
        )
        self.assertEqual(response.status_code, 200)
        order_codes = {
            row.get("merchant_order_code")
            for row in (response.get_json() or {}).get("items", [])
        }
        self.assertIn("ORD-PENDING-001", order_codes)
        self.assertNotIn("ORD-PAID-001", order_codes)
        self.assertNotIn("ORD-FAILED-001", order_codes)

    def test_admin_transaction_detail_renders_provider_refs_and_webhook_section(self):
        self._login(self.admin_email)
        response = self.client.get(f"/api/admin/payments/transactions/{self.failed_attempt_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("provider_payment_id"), "plink-failed-001")
        serialized = str(payload)
        self.assertIn("payment.failed", serialized)
        self.assertIn("Signature invalid.", serialized)

    def test_admin_dashboard_renders_operational_sections(self):
        self._login(self.admin_email)
        page_response = self.client.get(
            "/admin/payments?period=30d",
            follow_redirects=False,
        )
        self.assertEqual(page_response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', page_response.data)

        api_response = self.client.get("/api/admin/payments?period=30d")
        self.assertEqual(api_response.status_code, 200)
        payload = api_response.get_json() or {}
        self.assertEqual(payload.get("period"), "30d")
        self.assertIn("cards", payload)
        self.assertIn("recent_orders", payload)
        self.assertIn("recent_webhook_failures", payload)

    def test_admin_update_order_status_success(self):
        self._login(self.admin_email)
        response = self.client.patch(
            f"/api/admin/payments/orders/{self.buyer_pending_order_id}/status",
            json={"status": "paid", "note": "Duyệt thủ công qua admin"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        self.assertIn("order", payload)
        order = payload["order"]
        self.assertEqual(order["status"], "paid")
        self.assertEqual(order["status_label"], "Thanh toán thành công")
        self.assertIn("order_detail_lines", order.get("serialized") or {})

    def test_admin_update_order_status_to_canceled(self):
        self._login(self.admin_email)
        response = self.client.patch(
            f"/api/admin/payments/orders/{self.buyer_pending_order_id}/status",
            json={"status": "canceled", "note": "Khách yêu cầu hủy"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        order = payload.get("order") or {}
        self.assertEqual(order.get("status"), "canceled")

    def test_admin_update_order_status_to_failed_persists_attempt_failure(self):
        self._login(self.admin_email)
        response = self.client.patch(
            f"/api/admin/payments/orders/{self.buyer_pending_order_id}/status",
            json={"status": "failed", "note": "Payment rejected after review"},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["order"]["status"], "failed")
        with self.app.app_context():
            order = db.session.get(PaymentOrder, self.buyer_pending_order_id)
            self.assertEqual(order.status, "failed")
            self.assertIsNotNone(order.closed_at)
            self.assertIsNone(order.paid_at)
            attempt = order.attempts[0]
            self.assertEqual(attempt.status, "failed")
            self.assertIsNotNone(attempt.failed_at)
            self.assertEqual(attempt.failure_code, "admin_failed")
            self.assertEqual(attempt.failure_message, "Payment rejected after review")
            self.assertEqual(
                PaymentEntitlement.query.filter_by(payment_order_id=order.id).count(), 0
            )

    def test_admin_update_order_status_errors_keep_the_api_contract(self):
        self._login(self.admin_email)
        invalid = self.client.patch(
            f"/api/admin/payments/orders/{self.buyer_pending_order_id}/status",
            json={"status": "unsupported"},
        )
        self.assertEqual(invalid.status_code, 400, invalid.get_json())
        self.assertEqual(invalid.get_json()["error"], "VALIDATION_ERROR")
        missing = self.client.patch(
            "/api/admin/payments/orders/missing-order/status", json={"status": "paid"}
        )
        self.assertEqual(missing.status_code, 404, missing.get_json())
        self.assertEqual(missing.get_json()["error"], "FIELD_NOT_FOUND")

    def test_admin_sync_order_success(self):
        self._login(self.admin_email)
        response = self.client.post(
            f"/api/admin/payments/orders/{self.buyer_paid_order_id}/sync",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json() or {}
        order = payload.get("order") or {}
        self.assertEqual(order.get("status"), "paid")
        self.assertEqual(order.get("status_label"), "Thanh toán thành công")


if __name__ == "__main__":
    unittest.main()

