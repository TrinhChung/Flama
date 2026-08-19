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
from models.flashcard import FieldDef, NoteType, Template
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

            # Create NoteType
            note_type = NoteType(user_id=self.user_id, name="Japanese Vocabulary")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            db.session.add_all(
                [
                    FieldDef(
                        note_type_id=note_type.id,
                        name="word",
                        field_type="text",
                        position=0,
                    ),
                    FieldDef(
                        note_type_id=note_type.id,
                        name="meaning_vi",
                        field_type="text",
                        position=1,
                    ),
                    Template(
                        note_type_id=note_type.id,
                        name="Forward Card",
                        front_html="{{word}}",
                        back_html="{{FrontSide}}<hr>{{meaning_vi}}",
                        position=0,
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

    def test_authorize_redirects_to_spa_consent_when_logged_in(self):
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.get(
            f"/oauth/authorize?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&code_challenge={challenge}&code_challenge_method=S256&state=state123"
        )
        self.assertEqual(resp.status_code, 302)
        loc = resp.headers["Location"]
        self.assertIn("/oauth/consent?", loc)
        self.assertIn(f"client_id={self.client_id}", loc)
        self.assertIn("state=state123", loc)

    def test_consent_info_and_decision_api(self):
        self._login_user()
        verifier, challenge = self._generate_pkce()

        # 1. GET /api/oauth/consent-info
        info_resp = self.client.get(
            f"/api/oauth/consent-info?client_id={self.client_id}&scope=deck:read note:create"
        )
        self.assertEqual(info_resp.status_code, 200)
        info_data = info_resp.get_json()
        self.assertEqual(info_data["client"]["client_name"], "ChatGPT Assistant")
        self.assertEqual(len(info_data["scopes"]), 2)
        self.assertEqual(info_data["user"]["username"], "alice")

        # 2. POST /api/oauth/consent-decision with deny
        deny_resp = self.client.post(
            "/api/oauth/consent-decision",
            json={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read note:create",
                "state": "state_denied",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "deny",
            },
        )
        self.assertEqual(deny_resp.status_code, 200)
        deny_url = deny_resp.get_json()["redirect_url"]
        self.assertTrue(deny_url.startswith(self.redirect_uri))
        self.assertIn("error=access_denied", deny_url)

        # 3. POST /api/oauth/consent-decision with approve
        approve_resp = self.client.post(
            "/api/oauth/consent-decision",
            json={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read note:create",
                "state": "state_approved",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        self.assertEqual(approve_resp.status_code, 200)
        approve_url = approve_resp.get_json()["redirect_url"]
        self.assertTrue(approve_url.startswith(self.redirect_uri))
        self.assertIn("code=", approve_url)

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

    def test_endpoints_info_api(self):
        resp = self.client.get("/api/oauth/endpoints-info")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("auth_url", data)
        self.assertIn("token_url", data)
        self.assertIn("resource_url", data)
        self.assertIn("userinfo_url", data)
        self.assertIn("openid_config_url", data)
        self.assertIn("scopes", data)
        self.assertIn("deck:read", data["scopes_string"])

    def test_oauth_clients_crud_api(self):
        self._login_user()

        # 1. Create client via API
        create_resp = self.client.post(
            "/api/oauth/clients",
            json={
                "client_id": "claude_custom",
                "client_name": "Claude Desktop Custom",
                "client_secret": "secret_claude_999",
                "redirect_uris": ["https://claude.ai/callback", "https://localhost:8080"],
            },
        )
        self.assertEqual(create_resp.status_code, 201)
        created_client = create_resp.get_json()["client"]
        self.assertEqual(created_client["client_id"], "claude_custom")
        self.assertEqual(len(created_client["redirect_uris"]), 2)
        client_pk = created_client["id"]

        # 2. List clients
        list_resp = self.client.get("/api/oauth/clients")
        self.assertEqual(list_resp.status_code, 200)
        items = list_resp.get_json()["items"]
        client_ids = [c["client_id"] for c in items]
        self.assertIn("claude_custom", client_ids)

        # 3. Delete client
        del_resp = self.client.delete(f"/api/oauth/clients/{client_pk}")
        self.assertEqual(del_resp.status_code, 200)

        # 4. Verify deletion
        list_resp_2 = self.client.get("/api/oauth/clients")
        client_ids_2 = [c["client_id"] for c in list_resp_2.get_json()["items"]]
        self.assertNotIn("claude_custom", client_ids_2)

    def test_oidc_userinfo_endpoint(self):
        # 1. Obtain access token
        self._login_user()
        verifier, challenge = self._generate_pkce()
        self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read note:create",
                "state": "s1",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        auth_code = parse_qs(urlparse(self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read",
                "state": "s2",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        ).headers["Location"]).query)["code"][0]

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
        access_token = token_resp.get_json()["access_token"]

        # 2. Call userinfo with token
        uinfo_resp = self.client.get(
            "/oauth/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(uinfo_resp.status_code, 200)
        uinfo = uinfo_resp.get_json()
        self.assertEqual(uinfo["username"], "alice")
        self.assertEqual(uinfo["email"], "alice@example.com")
        self.assertEqual(uinfo["sub"], str(self.user_id))

        # 3. Call userinfo without token
        unauth_resp = self.client.get("/oauth/userinfo")
        self.assertEqual(unauth_resp.status_code, 401)

    def test_connected_apps_management_and_revoke(self):
        # 1. Authorize ChatGPT to create a connected app
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read",
                "state": "s_conn",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        auth_code = parse_qs(urlparse(resp.headers["Location"]).query)["code"][0]

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

        # 2. List connected apps
        apps_resp = self.client.get("/api/oauth/connected-apps")
        self.assertEqual(apps_resp.status_code, 200)
        items = apps_resp.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["client_id"], self.client_id)
        self.assertEqual(items[0]["client_name"], "ChatGPT Assistant")

        # 3. Revoke connected app
        rev_resp = self.client.post(f"/api/oauth/connected-apps/{self.client_id}/revoke")
        self.assertEqual(rev_resp.status_code, 200)
        self.assertTrue(rev_resp.get_json()["success"])

        # 4. Verify list is now empty
        apps_resp_2 = self.client.get("/api/oauth/connected-apps")
        self.assertEqual(len(apps_resp_2.get_json()["items"]), 0)

    def test_oauth_basic_auth_token_exchange(self):
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read",
                "state": "s_basic",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        auth_code = parse_qs(urlparse(resp.headers["Location"]).query)["code"][0]

        # Use HTTP Basic Auth header instead of form body for client credentials
        creds = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode("utf-8")).decode("ascii")
        token_resp = self.client.post(
            "/oauth/token",
            headers={"Authorization": f"Basic {creds}"},
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "code_verifier": verifier,
                "redirect_uri": self.redirect_uri,
            },
        )
        self.assertEqual(token_resp.status_code, 200)
        self.assertIn("access_token", token_resp.get_json())

    def test_public_client_pkce_without_secret(self):
        # Register public client
        public_client_id = "cursor_public_app"
        public_redirect = "http://localhost:8080/callback"
        with self.app.app_context():
            oauth_service.register_oauth_client(
                client_id=public_client_id,
                client_name="Cursor Public IDE",
                client_secret=None,
                redirect_uris=[public_redirect],
                is_confidential=False,
            )

        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": public_client_id,
                "redirect_uri": public_redirect,
                "scope": "deck:read",
                "state": "s_pub",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        auth_code = parse_qs(urlparse(resp.headers["Location"]).query)["code"][0]

        # Exchange token without client_secret
        token_resp = self.client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": public_client_id,
                "code": auth_code,
                "code_verifier": verifier,
                "redirect_uri": public_redirect,
            },
        )
        self.assertEqual(token_resp.status_code, 200)
        self.assertIn("access_token", token_resp.get_json())

    def test_wrong_client_secret_rejected(self):
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read",
                "state": "s_bad_sec",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        auth_code = parse_qs(urlparse(resp.headers["Location"]).query)["code"][0]

        token_resp = self.client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": "completely_wrong_secret",
                "code": auth_code,
                "code_verifier": verifier,
                "redirect_uri": self.redirect_uri,
            },
        )
        self.assertEqual(token_resp.status_code, 401)
        self.assertEqual(token_resp.get_json()["error"], "invalid_client")

    def test_create_note_mcp_tool_via_oauth(self):
        # 1. Authorize with note:create scope
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read note-type:read note:check note:create note:read",
                "state": "s_note",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        auth_code = parse_qs(urlparse(resp.headers["Location"]).query)["code"][0]

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
        access_token = token_resp.get_json()["access_token"]

        # 2. Call create_note MCP tool
        mcp_call = self.client.post(
            "/api/mcp",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "jsonrpc": "2.0",
                "id": "create-1",
                "method": "tools/call",
                "params": {
                    "name": "create_note",
                    "arguments": {
                        "deck_name": "Alice Japanese N1",
                        "note_type_name": "Japanese Vocabulary",
                        "fields": {
                            "word": "勉強",
                            "meaning_vi": "Học tập",
                        },
                    },
                },
            },
        )
        self.assertEqual(mcp_call.status_code, 200)
        res = mcp_call.get_json()
        self.assertIn("structuredContent", res["result"])
        note_res = res["result"]["structuredContent"]
        self.assertIn("note_id", note_res)
        self.assertEqual(note_res["deck_name"], "Alice Japanese N1")
        self.assertFalse(note_res["updated_existing"])
        self.assertGreaterEqual(len(note_res["cards"]), 1)



        # 3. Call find_notes MCP tool to verify search works
        find_call = self.client.post(
            "/api/mcp",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "jsonrpc": "2.0",
                "id": "find-1",
                "method": "tools/call",
                "params": {
                    "name": "find_notes",
                    "arguments": {
                        "query": "勉強",
                    },
                },
            },
        )
        self.assertEqual(find_call.status_code, 200)
        find_res = find_call.get_json()["result"]["structuredContent"]
        self.assertGreaterEqual(len(find_res["notes"]), 1)

    def test_mcp_tool_call_with_chatgpt_metadata(self):
        self._login_user()
        verifier, challenge = self._generate_pkce()
        resp = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "deck:read",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "action": "approve",
            },
        )
        auth_code = parse_qs(urlparse(resp.headers["Location"]).query)["code"][0]
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
        access_token = token_resp.get_json()["access_token"]

        # Call tools/call with ChatGPT-style metadata in params and empty arguments
        mcp_call = self.client.post(
            "/api/mcp",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "list_my_decks",
                    "arguments": {},
                    "_meta": {"progressToken": 12345, "context": "chatgpt_session"},
                },
            },
        )
        self.assertEqual(mcp_call.status_code, 200)
        result = mcp_call.get_json()["result"]
        self.assertIn("content", result)


