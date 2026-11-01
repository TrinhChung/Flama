"""Tests for internal security incident webhook and automated attacker ban mechanism."""

from __future__ import annotations

import unittest
from datetime import datetime

from app import create_app
from models import db
from models.admin_security_alert import AdminSecurityAlert
from models.audit_log import AuditLog
from models.mcp_access_token import McpAccessToken
from models.user import User
from models.user_api_token import UserApiToken


class InternalSecurityIncidentTests(unittest.TestCase):
    def setUp(self):
        self.secret = "test_internal_secret_998877"
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "INTERNAL_SECURITY_SECRET": self.secret,
                "INTERNAL_TRUSTED_IPS": "203.0.113.0/24, 198.51.100.141",
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Create normal user
            self.normal_user = User(
                username="attacker_victim",
                email="victim@example.com",
                is_admin=False,
                is_disabled=False,
            )
            self.normal_user.set_password("pass123")
            db.session.add(self.normal_user)

            # Create admin user
            self.admin_user = User(
                username="site_admin",
                email="admin@example.com",
                is_admin=True,
                is_disabled=False,
            )
            self.admin_user.set_password("adminpass")
            db.session.add(self.admin_user)
            db.session.flush()

            # Create an active UserApiToken for normal user
            self.user_token = UserApiToken(
                user_id=self.normal_user.id,
                name="Normal Token",
                token_hash="hash_user_12345",
                token_prefix="fl_test",
                scopes="read,write",
                revoked_at=None,
            )
            db.session.add(self.user_token)

            # Create an active McpAccessToken for normal user
            self.mcp_token = McpAccessToken(
                user_id=self.normal_user.id,
                token_hash="hash_mcp_67890",
                scopes="[]",
                revoked=False,
            )
            db.session.add(self.mcp_token)

            db.session.commit()

            self.normal_user_id = self.normal_user.id
            self.admin_user_id = self.admin_user.id
            self.user_token_id = self.user_token.id
            self.mcp_token_id = self.mcp_token.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_missing_internal_secret_returns_403(self):
        resp = self.client.post(
            "/api/internal/security/incident",
            json={"incident_type": "ZIP_SLIP"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json.get("error"), "FORBIDDEN")

    def test_untrusted_remote_ip_rejected(self):
        # Even with the correct secret, requests from non-WireGuard public IPs are rejected
        from app.api.v1.internal.security import _is_trusted_remote_ip

        with self.app.app_context():
            self.assertTrue(_is_trusted_remote_ip("127.0.0.1"))
            self.assertTrue(_is_trusted_remote_ip("203.0.113.226")) # Worker 212 inside the configured mesh network
            self.assertTrue(_is_trusted_remote_ip("198.51.100.141")) # OV Gateway listed as a single IP
            self.assertFalse(_is_trusted_remote_ip("198.51.100.1")) # External public IP
            self.assertFalse(_is_trusted_remote_ip("not-an-ip"))
            self.assertFalse(_is_trusted_remote_ip("1.2.3.4"))
            self.assertFalse(_is_trusted_remote_ip(""))

    def test_invalid_internal_secret_returns_403(self):
        resp = self.client.post(
            "/api/internal/security/incident",
            headers={"X-Internal-Secret": "wrong_secret_value"},
            json={"incident_type": "ZIP_SLIP"},
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json.get("error"), "FORBIDDEN")

    def test_invalid_json_payload_returns_400(self):
        resp = self.client.post(
            "/api/internal/security/incident",
            headers={"X-Internal-Secret": self.secret},
            data="not-a-json",
            content_type="text/plain",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json.get("error"), "INVALID_PAYLOAD")

    def test_normal_user_auto_banned_on_attack(self):
        payload = {
            "user_id": self.normal_user_id,
            "incident_type": "ZIP_SLIP",
            "detail": "Path traversal attempt ../../evil.sh",
            "client_ip": "203.0.113.195",
            "timestamp": datetime.utcnow().isoformat(),
        }
        resp = self.client.post(
            "/api/internal/security/incident",
            headers={"X-Internal-Secret": self.secret},
            json=payload,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["user_banned"])
        self.assertFalse(data["admin_protected"])

        with self.app.app_context():
            # Verify user is disabled
            user = db.session.get(User, self.normal_user_id)
            self.assertTrue(user.is_disabled)
            self.assertFalse(user.is_active)

            # Verify API tokens revoked
            tok = db.session.get(UserApiToken, self.user_token_id)
            self.assertIsNotNone(tok.revoked_at)

            # Verify MCP tokens revoked
            mcp = db.session.get(McpAccessToken, self.mcp_token_id)
            self.assertTrue(mcp.revoked)

            # Verify AdminSecurityAlert recorded
            alert = AdminSecurityAlert.query.filter_by(user_id=self.normal_user_id).first()
            self.assertIsNotNone(alert)
            self.assertEqual(alert.threat_type, "zip_slip")
            self.assertEqual(alert.severity, "critical")
            self.assertEqual(alert.source_ip, "203.0.113.195")
            self.assertIn("evil.sh", alert.message)

            # Verify AuditLog recorded
            audit = AuditLog.query.filter_by(
                user_id=self.normal_user_id, action="security.user_auto_banned"
            ).first()
            self.assertIsNotNone(audit)
            self.assertEqual(audit.payload.get("reason"), "ZIP_SLIP")

    def test_admin_user_protected_from_auto_ban(self):
        payload = {
            "user_id": self.admin_user_id,
            "incident_type": "DECOMPRESSION_BOMB",
            "detail": "Pixel explosion 10000x10000",
            "client_ip": "198.51.100.5",
        }
        resp = self.client.post(
            "/api/internal/security/incident",
            headers={"X-Internal-Secret": self.secret},
            json=payload,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertEqual(data["status"], "ok")
        self.assertFalse(data["user_banned"])
        self.assertTrue(data["admin_protected"])

        with self.app.app_context():
            # Admin must NOT be disabled
            admin = db.session.get(User, self.admin_user_id)
            self.assertFalse(admin.is_disabled)
            self.assertTrue(admin.is_active)

            # But security alert is still created
            alert = AdminSecurityAlert.query.filter_by(user_id=self.admin_user_id).first()
            self.assertIsNotNone(alert)
            self.assertEqual(alert.threat_type, "decompression_bomb")

            # Audit log records admin bypass
            audit = AuditLog.query.filter_by(
                user_id=self.admin_user_id, action="security.incident_admin_bypassed"
            ).first()
            self.assertIsNotNone(audit)

    def test_incident_without_user_id_creates_alert_only(self):
        payload = {
            "incident_type": "FORGED_TOKEN",
            "detail": "Cryptographic signature tampered",
            "client_ip": "192.0.2.1",
        }
        resp = self.client.post(
            "/api/internal/security/incident",
            headers={"X-Internal-Secret": self.secret},
            json=payload,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json
        self.assertEqual(data["status"], "ok")
        self.assertFalse(data["user_banned"])
        self.assertIsNone(data["user_id"])

        with self.app.app_context():
            alert = AdminSecurityAlert.query.filter_by(source_ip="192.0.2.1").first()
            self.assertIsNotNone(alert)
            self.assertEqual(alert.threat_type, "forged_token")
            self.assertIsNone(alert.user_id)


if __name__ == "__main__":
    unittest.main()
