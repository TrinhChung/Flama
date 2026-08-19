"""Comprehensive tests for OAuth 2.1 PKCE Flow and Remote MCP authorization."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import unittest
from urllib.parse import parse_qs, urlparse

from app import create_app
from app.services import mcp_access_token_service, oauth_service
from models import db
from models.deck import Deck
from models.oauth_client import OAuthClient
from models.user import User


class OAuthRemoteMcpTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "SERVER_NAME": "localhost:4789",
            }
        )
        self.client = self.app.test_client()
        mcp_access_token_service.reset_rate_limit_state()

        with self.app.app_context():
            # Create users
            self.user = User(
                username="alice",
                email="alice@example.com",
                timezone="UTC",
            )
            self.user.set_password("password123")

            self.other_user = User(
                username="bob",
                email="bob@example.com",
                timezone="UTC",
            )
            self.other_user.set_password("password123")

            db.session.add_all([self.user, self.other_user])
            db.session.flush()

            self.user_id = self.user.id
            self.other_user_id = self.other_user.id

            # Create test decks
            db.session.add_all(
                [
                    Deck(
                        name="Alice Japanese N1",
                        owner_user_id=self.user_id,
                        description="N1 Vocab",
                        position=1,
                    ),
                    Deck(
                        name="Bob Japanese N5",
                        owner_user_id=self.other_user_id,
                        description="N5 Vocab",
                        position=1,
                    ),
                ]
            )

            # Register OAuth Client (ChatGPT)
            self.client_id = "chatgpt_flama"
            self.client_secret = "secret_openai_123"
            self.redirect_uri = "https://chatgpt.com/api/actions/callback"

            oauth_service.register_oauth_client(
                client_id=self.client_id,
                client_name="ChatGPT Assistant",
                client_secret=self.client_secret,
                redirect_uris=[self.redirect_uri],
                is_confidential=True,
            )
            db.session.commit()

    def _login_user(self):
        return self.client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "password123"},
        )

    def _generate_pkce(self) -> tuple[str, str]:
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return code_verifier, code_challenge

    def test_discovery_metadata_endpoints(self):
        # 1. Protected Resource Metadata (RFC 9728)
        resp = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("/api/mcp", data["resource"])
        self.assertIn("deck:read", data["scopes_supported"])

        # 2. Authorization Server Metadata (RFC 8414)
        resp_as = self.client.get("/.well-known/oauth-authorization-server")
        self.assertEqual(resp_as.status_code, 200)
        as_data = resp_as.get_json()
        self.assertIn("/oauth/authorize", as_data["authorization_endpoint"])
        self.assertIn("/oauth/token", as_data["token_endpoint"])
        self.assertIn("S256", as_data["code_challenge_methods_supported"])
        self.assertIn("authorization_code", as_data["grant_types_supported"])

    def test_authorize_redirects_unauthenticated_to_login(self):
        verifier, challenge = self._generate_pkce()
        resp = self.client.get(
            f"/oauth/authorize?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&code_challenge={challenge}&code_challenge_method=S256&state=state123"
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login?next=", resp.headers["Location"])

    def test_authorize_renders_consent_page_when_logged_in(self):
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.get(
            f"/oauth/authorize?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&code_challenge={challenge}&code_challenge_method=S256&state=state123"
        )
        self.assertEqual(resp.status_code, 200)
        html_text = resp.get_data(as_text=True)
        self.assertIn("Cấp quyền cho ChatGPT Assistant", html_text)
        self.assertIn("deck:read", html_text)
        self.assertIn("alice", html_text)

    def test_authorize_denial_redirects_with_access_denied(self):
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read note:create",
                "state": "state_denied",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "deny",
            },
        )
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers["Location"]
        self.assertTrue(loc.startswith(self.redirect_uri))
        parsed = parse_qs(urlparse(loc).query)
        self.assertEqual(parsed["error"][0], "access_denied")
        self.assertEqual(parsed["state"][0], "state_denied")

    def test_full_oauth_pkce_flow_and_mcp_call(self):
        # 1. User logs in and approves consent
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read note-type:read note:check note:create",
                "state": "my_state_999",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers["Location"]
        self.assertTrue(loc.startswith(self.redirect_uri))
        parsed = parse_qs(urlparse(loc).query)
        self.assertIn("code", parsed)
        self.assertEqual(parsed["state"][0], "my_state_999")
        auth_code = parsed["code"][0]

        # 2. Exchange code for access token with PKCE verifier
        token_resp = self.client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": auth_code,
                "code_verifier": verifier,
                "redirect_uri": self.redirect_uri,
            },
        )
        self.assertEqual(token_resp.status_code, 200)
        token_data = token_resp.get_json()
        self.assertIn("access_token", token_data)
        self.assertIn("refresh_token", token_data)
        self.assertEqual(token_data["token_type"], "Bearer")
        self.assertEqual(token_data["expires_in"], 86400)
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]

        # 3. Call Remote MCP endpoint using Bearer Token
        mcp_call_resp = self.client.post(
            "/api/mcp",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "jsonrpc": "2.0",
                "id": "req-1",
                "method": "tools/call",
                "params": {
                    "name": "list_my_decks",
                    "arguments": {},
                },
            },
        )
        self.assertEqual(mcp_call_resp.status_code, 200)
        mcp_res = mcp_call_resp.get_json()
        self.assertEqual(mcp_res["id"], "req-1")
        self.assertIn("result", mcp_res)
        self.assertIn("structuredContent", mcp_res["result"])
        decks = mcp_res["result"]["structuredContent"]["decks"]

        # Check data scoping: only Alice's deck is returned, not Bob's
        deck_names = [d["name"] for d in decks]
        self.assertIn("Alice Japanese N1", deck_names)
        self.assertNotIn("Bob Japanese N5", deck_names)

        # 4. Test Token Refresh
        ref_resp = self.client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
            },
        )
        self.assertEqual(ref_resp.status_code, 200)
        ref_data = ref_resp.get_json()
        self.assertIn("access_token", ref_data)
        new_access_token = ref_data["access_token"]

        # New token works for MCP call
        mcp_call_2 = self.client.post(
            "/api/mcp",
            headers={"Authorization": f"Bearer {new_access_token}"},
            json={
                "jsonrpc": "2.0",
                "id": "req-2",
                "method": "tools/call",
                "params": {
                    "name": "list_my_decks",
                    "arguments": {},
                },
            },
        )
        self.assertEqual(mcp_call_2.status_code, 200)

        # 5. Test Revocation
        rev_resp = self.client.post(
            "/oauth/revoke",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "token": new_access_token,
            },
        )
        self.assertEqual(rev_resp.status_code, 200)

        # Calling MCP after revocation fails with 401 and WWW-Authenticate header
        mcp_call_3 = self.client.post(
            "/api/mcp",
            headers={"Authorization": f"Bearer {new_access_token}"},
            json={
                "jsonrpc": "2.0",
                "id": "req-3",
                "method": "tools/call",
                "params": {"name": "list_my_decks", "arguments": {}},
            },
        )
        self.assertEqual(mcp_call_3.status_code, 401)
        self.assertIn("WWW-Authenticate", mcp_call_3.headers)

    def test_pkce_verification_failure(self):
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read",
                "state": "state_pkce_fail",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        parsed = parse_qs(urlparse(resp.headers["Location"]).query)
        auth_code = parsed["code"][0]

        # Exchange with wrong verifier
        token_resp = self.client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": auth_code,
                "code_verifier": "wrong_verifier_string_12345",
                "redirect_uri": self.redirect_uri,
            },
        )
        self.assertEqual(token_resp.status_code, 400)
        self.assertEqual(token_resp.get_json()["error"], "invalid_grant")

    def test_single_use_authorization_code(self):
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read",
                "state": "state_single_use",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        parsed = parse_qs(urlparse(resp.headers["Location"]).query)
        auth_code = parsed["code"][0]

        # First exchange succeeds
        token_resp = self.client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": auth_code,
                "code_verifier": verifier,
                "redirect_uri": self.redirect_uri,
            },
        )
        self.assertEqual(token_resp.status_code, 200)

        # Second exchange with the same code must fail
        replay_resp = self.client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": auth_code,
                "code_verifier": verifier,
                "redirect_uri": self.redirect_uri,
            },
        )
        self.assertEqual(replay_resp.status_code, 400)
        self.assertEqual(replay_resp.get_json()["error"], "invalid_grant")

    def test_unregistered_redirect_uri_rejected(self):
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.get(
            f"/oauth/authorize?client_id={self.client_id}&redirect_uri=https://evil.attacker.com/callback&response_type=code&code_challenge={challenge}&code_challenge_method=S256"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "invalid_request")
