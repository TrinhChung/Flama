"""Integration tests for MCP access token generation and bearer auth."""

from __future__ import annotations

from datetime import datetime, timedelta
import unittest

from app import create_app
from app.services import mcp_access_token_service
from models import db
from models.deck import Deck
from models.mcp_access_token import McpAccessToken
from models.user import User


class McpAccessTokenTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        mcp_access_token_service.reset_rate_limit_state()

        with self.app.app_context():
            owner = User(
                username="token-owner",
                email="token-owner@example.com",
                timezone="UTC",
                is_admin=True,
            )
            owner.set_password("password")
            other = User(
                username="token-other",
                email="token-other@example.com",
                timezone="UTC",
                is_admin=False,
            )
            other.set_password("password")
            db.session.add_all([owner, other])
            db.session.flush()

            self.owner_id = owner.id
            self.other_user_id = other.id

            db.session.add_all(
                [
                    Deck(
                        name="Owner Deck",
                        owner_user_id=self.owner_id,
                        description="Owner only deck",
                        position=1,
                    ),
                    Deck(
                        name="Other Deck",
                        owner_user_id=self.other_user_id,
                        position=2,
                    ),
                ]
            )
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self):
        return self.client.post(
            "/login",
            data={"email": "token-owner@example.com", "password": "password"},
            follow_redirects=True,
        )

    def _login_regular(self):
        return self.client.post(
            "/login",
            data={"email": "token-other@example.com", "password": "password"},
            follow_redirects=True,
        )

    def _generate_token(self, name: str = "Test Token", expires_in_days: int | None = 180) -> str:
        self._login()
        response = self.client.post(
            "/api/mcp-tokens",
            json={"name": name, "expires_in_days": expires_in_days},
        )
        self.assertEqual(response.status_code, 201)
        return str((response.get_json() or {}).get("item", {}).get("token") or "")

    def _mcp_payload(self) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "list_my_decks",
                "arguments": {},
            },
        }

    def _mcp_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "MCP-Protocol-Version": "2025-11-25",
        }

    def test_generate_token_shows_plaintext_once(self):
        self._login()

        response = self.client.post("/api/mcp-tokens", json={"name": "My AI Agent"})
        self.assertEqual(response.status_code, 201)
        data = response.get_json() or {}
        item = data.get("item", {})
        token = str(item.get("token") or "")
        self.assertTrue(token.startswith("flama_mcp_"))
        self.assertEqual(item.get("name"), "My AI Agent")
        self.assertIsNotNone(item.get("expires_at"))

        list_response = self.client.get("/api/mcp-tokens")
        self.assertEqual(list_response.status_code, 200)
        self.assertNotIn(token, list_response.get_data(as_text=True))

    def test_custom_name_and_never_expires(self):
        self._login()

        response = self.client.post(
            "/api/mcp-tokens",
            json={"name": "Permanent Cursor", "expires_in_days": None},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json() or {}
        item = data.get("item", {})
        self.assertEqual(item.get("name"), "Permanent Cursor")
        self.assertIsNone(item.get("expires_at"))

        list_response = self.client.get("/api/mcp-tokens")
        self.assertEqual(list_response.status_code, 200)
        items = (list_response.get_json() or {}).get("items", [])
        created = next((x for x in items if x["name"] == "Permanent Cursor"), None)
        self.assertIsNotNone(created)
        self.assertIsNone(created["expires_at"])
        self.assertEqual(created["status"], "active")

    def test_mcp_token_page_is_available_from_separate_route(self):
        self._login()

        response = self.client.get("/settings/mcp-tokens")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', response.data)

    def test_regular_user_can_generate_and_list_tokens(self):
        self._login_regular()

        create_response = self.client.post(
            "/api/mcp-tokens",
            json={"name": "Regular User Token", "expires_in_days": 30},
        )
        self.assertEqual(create_response.status_code, 201)

        list_response = self.client.get("/api/mcp-tokens")
        self.assertEqual(list_response.status_code, 200)
        items = (list_response.get_json() or {}).get("items", [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "Regular User Token")

    def test_bearer_token_can_call_mcp_without_session(self):
        token = self._generate_token()

        external_client = self.app.test_client()
        response = external_client.post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(token),
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        decks = payload["result"]["structuredContent"]["decks"]
        self.assertEqual([deck["name"] for deck in decks], ["Owner Deck"])

    def test_invalid_bearer_does_not_fallback_to_session(self):
        self._login()

        response = self.client.post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers("not-a-real-token"),
        )

        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertEqual(payload["error"]["data"]["code"], "MCP_TOKEN_INVALID")

    def test_expired_token_is_rejected(self):
        token = self._generate_token()

        with self.app.app_context():
            row = McpAccessToken.query.filter_by(user_id=self.owner_id).order_by(McpAccessToken.id.desc()).first()
            self.assertIsNotNone(row)
            row.expires_at = datetime.utcnow() - timedelta(minutes=1)
            db.session.commit()

        response = self.app.test_client().post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(token),
        )

        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertEqual(payload["error"]["data"]["code"], "MCP_TOKEN_EXPIRED")

    def test_scope_is_enforced(self):
        token = self._generate_token()

        with self.app.app_context():
            row = McpAccessToken.query.filter_by(user_id=self.owner_id).order_by(McpAccessToken.id.desc()).first()
            self.assertIsNotNone(row)
            row.scopes = "[]"
            db.session.commit()

        response = self.app.test_client().post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(token),
        )

        self.assertEqual(response.status_code, 403)
        payload = response.get_json()
        self.assertEqual(payload["error"]["data"]["code"], "MCP_SCOPE_FORBIDDEN")

    def test_revoke_route_blocks_future_bearer_requests(self):
        token = self._generate_token()

        with self.app.app_context():
            row = McpAccessToken.query.filter_by(user_id=self.owner_id).order_by(McpAccessToken.id.desc()).first()
            self.assertIsNotNone(row)
            token_id = int(row.id)

        revoke_response = self.client.delete(f"/api/mcp-tokens/{token_id}")
        self.assertEqual(revoke_response.status_code, 204)

        response = self.app.test_client().post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(token),
        )

        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertEqual(payload["error"]["data"]["code"], "MCP_TOKEN_REVOKED")


if __name__ == "__main__":
    unittest.main()
