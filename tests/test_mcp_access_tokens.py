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

    def test_regular_user_can_list_but_not_create_tokens_without_permission(self):
        self._login_regular()

        # Regular user can view their tokens (returns empty list)
        list_response = self.client.get("/api/mcp-tokens")
        self.assertEqual(list_response.status_code, 200)
        items = (list_response.get_json() or {}).get("items", [])
        self.assertEqual(len(items), 0)

        # But cannot self-create tokens
        create_response = self.client.post(
            "/api/mcp-tokens",
            json={"name": "Regular User Token", "expires_in_days": 30},
        )
        self.assertEqual(create_response.status_code, 403)
        self.assertEqual((create_response.get_json() or {}).get("error"), "MCP_MANAGEMENT_DENIED")

    def test_permitted_user_can_generate_and_list_tokens(self):
        with self.app.app_context():
            user = db.session.get(User, self.other_user_id)
            user.can_manage_mcp_tokens = True
            db.session.commit()

        self._login_regular()

        create_response = self.client.post(
            "/api/mcp-tokens",
            json={"name": "Permitted User Token", "expires_in_days": 30},
        )
        self.assertEqual(create_response.status_code, 201)

        list_response = self.client.get("/api/mcp-tokens")
        self.assertEqual(list_response.status_code, 200)
        items = (list_response.get_json() or {}).get("items", [])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "Permitted User Token")

    def test_regular_user_can_use_mcp_api_with_issued_token(self):
        # Admin issues token for regular user
        with self.app.app_context():
            issued = mcp_access_token_service.issue_token_and_commit(
                user_id=self.other_user_id,
                name="Admin Assigned Token",
                expires_in_days=90,
            )
            token = issued.token

        # Regular user can call MCP API with this token
        external_client = self.app.test_client()
        response = external_client.post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(token),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("result", payload)

    def test_token_rejected_when_revoked(self):
        with self.app.app_context():
            issued = mcp_access_token_service.issue_token_and_commit(
                user_id=self.other_user_id,
                name="Revocable Token",
            )
            token = issued.token
            row = McpAccessToken.query.filter_by(user_id=self.other_user_id, name="Revocable Token").first()
            token_id = row.id

        # Revoke the token
        with self.app.app_context():
            mcp_access_token_service.revoke_token_and_commit(
                user_id=self.other_user_id,
                token_id=token_id,
            )

        external_client = self.app.test_client()
        response = external_client.post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(token),
        )
        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertEqual(payload["error"]["data"]["code"], "MCP_TOKEN_REVOKED")

    def test_admin_mcp_management_endpoints(self):
        self._login()

        # 1. Summary
        res = self.client.get("/api/admin/mcp-tokens/summary")
        self.assertEqual(res.status_code, 200)
        summary = res.get_json()
        self.assertIn("total_tokens", summary)
        self.assertIn("permitted_users", summary)

        # 2. List users
        res = self.client.get("/api/admin/mcp-tokens/users")
        self.assertEqual(res.status_code, 200)
        users = res.get_json().get("items", [])
        self.assertTrue(len(users) >= 2)

        # 3. Grant permission to regular user
        res = self.client.post(
            f"/api/admin/mcp-tokens/users/{self.other_user_id}/permission",
            json={"can_manage_mcp_tokens": True},
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json().get("can_manage_mcp_tokens"))

        # Verify in DB
        with self.app.app_context():
            u = db.session.get(User, self.other_user_id)
            self.assertTrue(u.can_manage_mcp_tokens)

        # 4. Issue token for user via Admin
        res = self.client.post(
            "/api/admin/mcp-tokens/tokens",
            json={"user_id": self.other_user_id, "name": "Admin Issued Token"},
        )
        self.assertEqual(res.status_code, 201)

        # 5. List system tokens
        res = self.client.get("/api/admin/mcp-tokens/tokens")
        self.assertEqual(res.status_code, 200)
        tokens = res.get_json().get("items", [])
        self.assertTrue(any(t["name"] == "Admin Issued Token" for t in tokens))

        # 6. Revoke permission
        res = self.client.post(
            f"/api/admin/mcp-tokens/users/{self.other_user_id}/permission",
            json={"can_manage_mcp_tokens": False},
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json().get("can_manage_mcp_tokens"))

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

    def test_update_token(self):
        self._login()
        create_resp = self.client.post("/api/mcp-tokens", json={"name": "Old Name", "expires_in_days": 30})
        self.assertEqual(create_resp.status_code, 201)

        with self.app.app_context():
            row = McpAccessToken.query.filter_by(user_id=self.owner_id).order_by(McpAccessToken.id.desc()).first()
            token_id = row.id

        update_resp = self.client.patch(
            f"/api/mcp-tokens/{token_id}",
            json={"name": "New Name", "expires_in_days": 90, "scopes": ["deck:read"]},
        )
        self.assertEqual(update_resp.status_code, 200)
        item = update_resp.get_json()["item"]
        self.assertEqual(item["name"], "New Name")
        self.assertEqual(item["scopes"], ["deck:read"])

    def test_rotate_token(self):
        old_token = self._generate_token(name="Rotating Agent")

        with self.app.app_context():
            row = McpAccessToken.query.filter_by(user_id=self.owner_id).order_by(McpAccessToken.id.desc()).first()
            token_id = row.id
            count_before = McpAccessToken.query.count()

        rotate_resp = self.client.post(
            f"/api/mcp-tokens/{token_id}/rotate",
            json={"expires_in_days": 180},
        )
        self.assertEqual(rotate_resp.status_code, 200)
        new_token = rotate_resp.get_json()["item"]["token"]
        self.assertTrue(new_token.startswith("flama_mcp_"))
        self.assertNotEqual(old_token, new_token)

        # Confirm DB row count is unchanged (no duplicates created)
        with self.app.app_context():
            count_after = McpAccessToken.query.count()
            self.assertEqual(count_before, count_after)

        # Old token is rejected
        old_resp = self.app.test_client().post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(old_token),
        )
        self.assertEqual(old_resp.status_code, 401)

        # New token works
        new_resp = self.app.test_client().post(
            "/api/mcp",
            json=self._mcp_payload(),
            headers=self._mcp_headers(new_token),
        )
        self.assertEqual(new_resp.status_code, 200)

    def test_purge_token(self):
        self._login()
        self.client.post("/api/mcp-tokens", json={"name": "To Purge"})

        with self.app.app_context():
            row = McpAccessToken.query.filter_by(user_id=self.owner_id).order_by(McpAccessToken.id.desc()).first()
            token_id = row.id

        purge_resp = self.client.delete(f"/api/mcp-tokens/{token_id}/purge")
        self.assertEqual(purge_resp.status_code, 204)

        with self.app.app_context():
            row_after = McpAccessToken.query.filter_by(id=token_id).first()
            self.assertIsNone(row_after)

    def test_cleanup_tokens(self):
        self._login()
        # Create 1 active, 1 revoked, 1 expired
        self.client.post("/api/mcp-tokens", json={"name": "Active Token"})
        self.client.post("/api/mcp-tokens", json={"name": "Revoked Token"})
        self.client.post("/api/mcp-tokens", json={"name": "Expired Token"})

        with self.app.app_context():
            tokens = McpAccessToken.query.filter_by(user_id=self.owner_id).order_by(McpAccessToken.id.asc()).all()
            tokens[1].revoked = True
            tokens[2].expires_at = datetime.utcnow() - timedelta(days=1)
            db.session.commit()

        cleanup_resp = self.client.post("/api/mcp-tokens/cleanup")
        self.assertEqual(cleanup_resp.status_code, 200)
        data = cleanup_resp.get_json()
        self.assertEqual(data["purged_count"], 2)

        with self.app.app_context():
            remaining = McpAccessToken.query.filter_by(user_id=self.owner_id).all()
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0].name, "Active Token")


if __name__ == "__main__":
    unittest.main()

