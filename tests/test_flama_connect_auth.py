from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta

from app.connect import create_connect_app
from app.services import user_api_token_service
from models import db
from models.user import User


class FlamaConnectAuthTests(unittest.TestCase):
    def setUp(self):
        self.upload_tmp = tempfile.TemporaryDirectory()
        self.app = create_connect_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "CONNECT_IP_RATE_LIMIT": 1000,
                "CONNECT_TOKEN_RATE_LIMIT": 1000,
                "CONNECT_USER_RATE_LIMIT": 1000,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": self.upload_tmp.name,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User(username="authtest", email="auth@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            issued = user_api_token_service.issue_token(user_id=user.id, name="Auth Token Test")
            db.session.commit()
            self.token = issued.plaintext

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.upload_tmp.cleanup()

    def test_bearer_header_authentication(self):
        res = self.client.post(
            "/v1/flama-connect",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"action": "validateKey", "version": 6},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "valid")
        self.assertEqual(data.get("userId"), self.user_id)

    def test_x_flama_connect_key_header(self):
        res = self.client.post(
            "/v1/flama-connect",
            headers={"X-Flama-Connect-Key": self.token},
            json={"action": "userInfo", "version": 6},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("username"), "authtest")
        self.assertEqual(data.get("userId"), self.user_id)

    def test_invalid_key_header_returns_401(self):
        res = self.client.post(
            "/v1/flama-connect",
            headers={"Authorization": "Bearer flama_yt_00000000_invalidtokenstringxxxxxxxxxxxxxxxxxxxxxxxxx"},
            json={"action": "validateKey", "version": 6},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("error"), "authentication failed")

    def test_revoked_key_returns_revoked_error(self):
        with self.app.app_context():
            token_rec = user_api_token_service.UserApiToken.query.filter_by(user_id=self.user_id).first()
            token_rec.revoked_at = datetime.utcnow()
            db.session.commit()

        res = self.client.post(
            "/v1/flama-connect",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"action": "validateKey", "version": 6},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("error"), "revoked key")

    def test_expired_key_returns_expired_error(self):
        with self.app.app_context():
            token_rec = user_api_token_service.UserApiToken.query.filter_by(user_id=self.user_id).first()
            token_rec.expires_at = datetime.utcnow() - timedelta(days=1)
            db.session.commit()

        res = self.client.post(
            "/v1/flama-connect",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"action": "validateKey", "version": 6},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("error"), "expired key")

    def test_import_session_creation(self):
        res = self.client.post(
            "/v1/flama-connect",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "action": "createImportSession",
                "version": 6,
                "params": {
                    "source": "Anki",
                    "totalNotes": 42,
                    "totalMedia": 5,
                },
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("importSessionId").startswith("import_session_"))
        self.assertEqual(data.get("totalNotes"), 42)


if __name__ == "__main__":
    unittest.main()
