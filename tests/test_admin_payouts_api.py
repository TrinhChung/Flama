"""Integration tests for admin payout batch APIs."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from payos import APIError
from payos.types import Payout, PayoutTransaction

from app import create_app
from models import db
from models.payout_batch import PayoutBatch
from models.payout_batch_item import PayoutBatchItem
from models.user import User
from models.user_role import UserRole


class AdminPayoutApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            admin_role = UserRole.query.filter_by(code="admin").first()
            regular_role = UserRole.query.filter_by(code="regular").first()
            assert admin_role is not None
            assert regular_role is not None

            admin = User(
                username="admin-payout",
                email="admin-payout@example.com",
                is_admin=True,
                role_id=admin_role.id,
                is_disabled=False,
            )
            admin.set_password("password")
            regular = User(
                username="regular-payout",
                email="regular-payout@example.com",
                is_admin=False,
                role_id=regular_role.id,
                is_disabled=False,
            )
            regular.set_password("password")
            db.session.add_all([admin, regular])
            db.session.commit()
            self.admin_id = admin.id
            self.regular_id = regular.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, email: str) -> None:
        self.client.post(
            "/login",
            data={"email": email, "password": "password"},
            follow_redirects=True,
        )

    def _valid_payload(self, *, reference_id: str = "salary-march-2026") -> dict:
        return {
            "reference_id": reference_id,
            "category": ["salary"],
            "validate_destination": True,
            "payouts": [
                {
                    "reference_id": "alice-salary",
                    "amount": 2500000,
                    "description": "Salary payout Alice",
                    "to_bin": "970422",
                    "to_account_number": "0123456789",
                },
                {
                    "reference_id": "bob-salary",
                    "amount": 3000000,
                    "description": "Salary payout Bob",
                    "to_bin": "970422",
                    "to_account_number": "0987654321",
                },
            ],
        }

    def _build_provider_response(self, batch_data) -> Payout:
        transactions = []
        for index, item in enumerate(batch_data.payouts, start=1):
            transactions.append(
                PayoutTransaction(
                    id=f"txn_{index}",
                    reference_id=item.reference_id,
                    amount=item.amount,
                    description=item.description,
                    to_bin=item.to_bin,
                    to_account_number=item.to_account_number,
                    to_account_name=None,
                    reference=f"bank_ref_{index}",
                    transaction_datetime="2026-03-27T12:00:00Z",
                    error_message=None,
                    error_code=None,
                    state="PROCESSING",
                )
            )
        return Payout(
            id="provider_batch_123",
            reference_id=batch_data.reference_id,
            transactions=transactions,
            category=batch_data.category,
            approval_state="SUBMITTED",
            created_at="2026-03-27T12:00:00Z",
        )

    def test_admin_can_create_payout_batch_and_persist_success_response(self):
        self._login("admin-payout@example.com")

        def _fake_create(*, batch_data, idempotency_key):
            self.assertEqual(idempotency_key, batch_data.reference_id)
            return self._build_provider_response(batch_data)

        with patch("app.services.payos_client.create_payout_batch", side_effect=_fake_create) as mocked:
            response = self.client.post("/admin/api/payouts", json=self._valid_payload())

        self.assertEqual(response.status_code, 201)
        payload = response.get_json() or {}
        self.assertFalse(payload.get("duplicate_reused"))
        batch_payload = payload.get("batch") or {}
        self.assertEqual(batch_payload.get("status"), "submitted")
        self.assertEqual(batch_payload.get("provider_approval_state"), "SUBMITTED")
        self.assertTrue(batch_payload.get("provider_payout_id"))
        self.assertEqual(mocked.call_count, 1)

        request_payload = batch_payload.get("request_payload") or {}
        payout_rows = request_payload.get("payouts") or []
        self.assertEqual(len(payout_rows), 2)
        self.assertTrue(str(payout_rows[0].get("toAccountNumber") or "").startswith("*"))

        batch_id = batch_payload.get("id")
        detail_response = self.client.get(f"/admin/api/payouts/{batch_id}")
        self.assertEqual(detail_response.status_code, 200)

        with self.app.app_context():
            batch = PayoutBatch.query.get(batch_id)
            self.assertIsNotNone(batch)
            self.assertEqual(batch.internal_status, "submitted")
            self.assertEqual(batch.provider_payout_id, "provider_batch_123")
            stored_request = json.loads(batch.request_payload_json)
            self.assertEqual(stored_request.get("validateDestination"), True)
            self.assertEqual(len(stored_request.get("payouts") or []), 2)

            items = PayoutBatchItem.query.filter_by(batch_id=batch_id).order_by(PayoutBatchItem.id.asc()).all()
            self.assertEqual(len(items), 2)
            self.assertTrue(all(item.internal_status == "submitted" for item in items))
            self.assertTrue(all(item.provider_state == "PROCESSING" for item in items))
            self.assertTrue(all(item.response_payload_json for item in items))

    def test_invalid_payout_payload_is_rejected(self):
        self._login("admin-payout@example.com")
        payload = self._valid_payload()
        payload["payouts"][0]["amount"] = 0

        response = self.client.post("/admin/api/payouts", json=payload)

        self.assertEqual(response.status_code, 400)
        body = response.get_json() or {}
        self.assertEqual(body.get("error"), "VALIDATION_ERROR")
        self.assertEqual(body.get("field"), "payouts[0].amount")

        with self.app.app_context():
            self.assertEqual(PayoutBatch.query.count(), 0)
            self.assertEqual(PayoutBatchItem.query.count(), 0)

    def test_duplicate_payout_request_reuses_existing_batch(self):
        self._login("admin-payout@example.com")

        def _fake_create(*, batch_data, idempotency_key):
            self.assertEqual(idempotency_key, batch_data.reference_id)
            return self._build_provider_response(batch_data)

        payload = self._valid_payload(reference_id="bonus-march-2026")
        with patch("app.services.payos_client.create_payout_batch", side_effect=_fake_create) as mocked:
            first_response = self.client.post("/admin/api/payouts", json=payload)
            second_response = self.client.post("/admin/api/payouts", json=payload)

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.get_json() or {}
        self.assertTrue(second_payload.get("duplicate_reused"))
        self.assertEqual(mocked.call_count, 1)

        with self.app.app_context():
            self.assertEqual(PayoutBatch.query.count(), 1)
            self.assertEqual(PayoutBatchItem.query.count(), 2)

    def test_provider_error_marks_batch_as_failed_and_persists_error_payload(self):
        self._login("admin-payout@example.com")

        with patch(
            "app.services.payos_client.create_payout_batch",
            side_effect=APIError(
                "Invalid payout request",
                status_code=400,
                error_code="PAYOUT_01",
                error_desc="Destination rejected",
            ),
        ):
            response = self.client.post("/admin/api/payouts", json=self._valid_payload(reference_id="failed-run"))

        self.assertEqual(response.status_code, 400)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("error"), "PAYOUT_PROVIDER_ERROR")
        self.assertTrue(payload.get("batch_id"))

        with self.app.app_context():
            batch = PayoutBatch.query.get(payload.get("batch_id"))
            self.assertIsNotNone(batch)
            self.assertEqual(batch.internal_status, "submission_failed")
            self.assertIsNone(batch.provider_payout_id)
            error_payload = json.loads(batch.error_payload_json)
            self.assertEqual(error_payload.get("error_code"), "PAYOUT_01")
            self.assertEqual(error_payload.get("status_code"), 400)

            items = PayoutBatchItem.query.filter_by(batch_id=batch.id).all()
            self.assertEqual(len(items), 2)
            self.assertTrue(all(item.internal_status == "submission_failed" for item in items))


if __name__ == "__main__":
    unittest.main()
