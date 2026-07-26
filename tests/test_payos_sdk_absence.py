"""Regression tests for environments without the payOS SDK installed."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app
from app.services import payos_client, payout_service
from app.services.payment.provider import payos_provider
from models import db
from models.user import User
from models.user_role import UserRole


class PayOSSdkAbsenceTests(unittest.TestCase):
    def setUp(self):
        for module in (payos_client, payout_service):
            sdk_available_patcher = patch.object(module, "_PAYOS_SDK_AVAILABLE", False)
            sdk_available_patcher.start()
            self.addCleanup(sdk_available_patcher.stop)

        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "PAYOS_CLIENT_ID": "test-client-id",
                "PAYOS_API_KEY": "test-api-key",
                "PAYOS_CHECKSUM_KEY": "test-checksum-key",
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            admin_role = UserRole.query.filter_by(code="admin").first()
            assert admin_role is not None
            admin = User(
                username="admin-payos-sdk-missing",
                email="admin-payos-sdk-missing@example.com",
                is_admin=True,
                role_id=admin_role.id,
                is_disabled=False,
            )
            admin.set_password("password")
            db.session.add(admin)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self) -> None:
        self.client.post(
            "/login",
            data={"email": "admin-payos-sdk-missing@example.com", "password": "password"},
            follow_redirects=True,
        )

    def test_provider_reports_not_configured_when_sdk_is_missing(self):
        with self.app.app_context():
            with self.assertRaises(payos_provider.PayOSProviderError) as ctx:
                payos_provider.create_checkout_session(
                    provider_order_code=123456789,
                    amount_minor=1000,
                    title_snapshot="Test checkout",
                    payment_reference="REF123",
                    return_url="https://example.com/return",
                    cancel_url="https://example.com/cancel",
                    expires_at=datetime.utcnow() + timedelta(minutes=30),
                )

        self.assertEqual(ctx.exception.code, "PAYMENT_PROVIDER_NOT_CONFIGURED")
        self.assertEqual(ctx.exception.status, 503)

    def test_admin_payout_api_returns_json_503_when_sdk_is_missing(self):
        self._login()

        response = self.client.post(
            "/admin/api/payouts",
            json={
                "reference_id": "sdk-missing-2026",
                "category": ["salary"],
                "validate_destination": True,
                "payouts": [
                    {
                        "reference_id": "alice-salary",
                        "amount": 2500000,
                        "description": "Salary payout Alice",
                        "to_bin": "970422",
                        "to_account_number": "0123456789",
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 503)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("error"), "PAYOUT_UNAVAILABLE")
        self.assertTrue(payload.get("batch_id"))


if __name__ == "__main__":
    unittest.main()
