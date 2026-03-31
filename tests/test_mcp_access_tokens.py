"""Integration tests for MCP access token generation and bearer auth."""

from __future__ import annotations

from datetime import datetime, timedelta
import re
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
            owner = User(username="token-owner", email="token-owner@example.com", timezone="UTC")
            owner.set_password("password")
            other = User(username="token-other", email="token-other@example.com", timezone="UTC")
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

    def _extract_token(self, html: str) -> str:
        match = re.search(r"flama_mcp_[A-Za-z0-9_-]+", html)
        self.assertIsNotNone(match)
        return str(match.group(0))

    def _generate_token(self) -> str:
        self._login()
        response = self.client.post("/settings/mcp-tokens/generate")
        self.assertEqual(response.status_code, 200)
        return self._extract_token(response.get_data(as_text=True))

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

        response = self.client.post("/settings/mcp-tokens/generate")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        token = self._extract_token(html)

        self.assertIn("Copy token này ngay bây giờ", html)
        self.assertIn("Generate MCP token", html)
        self.assertIn("MCP Access Tokens", html)

        dashboard_response = self.client.get("/dashboard")
        self.assertEqual(dashboard_response.status_code, 200)
        dashboard_html = dashboard_response.get_data(as_text=True)
        self.assertNotIn(token, dashboard_html)
        self.assertNotIn("MCP Access Token", dashboard_html)

    def test_mcp_token_page_is_available_from_separate_route(self):
        self._login()

        response = self.client.get("/settings/mcp-tokens")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("MCP Access Tokens", html)
        self.assertIn("Generate MCP token", html)

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

    def test_request_limit_is_enforced(self):
        token = self._generate_token()

        with self.app.app_context():
            row = McpAccessToken.query.filter_by(user_id=self.owner_id).order_by(McpAccessToken.id.desc()).first()
            self.assertIsNotNone(row)
            row.max_requests = 1
            db.session.commit()

        external_client = self.app.test_client()
        first_response = external_client.post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(token),
        )
        second_response = external_client.post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(token),
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)
        payload = second_response.get_json()
        self.assertEqual(payload["error"]["data"]["code"], "MCP_TOKEN_REQUEST_LIMIT_EXCEEDED")

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

        revoke_response = self.client.post(f"/settings/mcp-tokens/{token_id}/revoke", follow_redirects=True)
        self.assertEqual(revoke_response.status_code, 200)

        response = self.app.test_client().post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(token),
        )

        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertEqual(payload["error"]["data"]["code"], "MCP_TOKEN_REVOKED")

    def test_token_rate_limit_returns_429(self):
        self.app.config["MCP_TOKEN_RATE_LIMIT_MAX_REQUESTS"] = 1
        token = self._generate_token()

        external_client = self.app.test_client()
        initialize_response = external_client.post(
            "/api/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "rate-limit-test", "version": "0.1.0"},
                },
            },
            headers=self._mcp_headers(token),
        )
        list_response = external_client.post(
            "/api/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
            headers=self._mcp_headers(token),
        )

        self.assertEqual(initialize_response.status_code, 200)
        self.assertEqual(list_response.status_code, 429)
        payload = list_response.get_json()
        self.assertEqual(payload["error"]["data"]["code"], "MCP_RATE_LIMIT_EXCEEDED")
