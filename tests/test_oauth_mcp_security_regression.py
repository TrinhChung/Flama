"""Regression test suite for OAuth permission correctness, MCP mutation safety, NoteType updates, and NoteSync consistency."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import unittest
from urllib.parse import parse_qs, urlparse

from app import create_app
from app.validators.flashcard_input import RequestValidationError
from app.services import (
    mcp_access_token_service,
    mcp_preview_service,
    mcp_scope_service,
    mcp_tool_service,
    note_sync_service,
    oauth_service,
)
from app.services.oauth_service import OAuthError
from models import db
from models.card import Card
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.flashcard import FieldDef, Note, NoteType, Template
from models.oauth_client import OAuthClient
from models.user import User


class OAuthMcpSecurityRegressionTests(unittest.TestCase):
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
            self.user = User(
                username="alice",
                email="alice@example.com",
                timezone="UTC",
                can_use_mcp=True,
            )
            self.user.set_password("password123")

            db.session.add(self.user)
            db.session.flush()
            self.user_id = self.user.id

            self.deck = Deck(
                name="Default Deck",
                owner_user_id=self.user_id,
            )
            db.session.add(self.deck)
            db.session.flush()
            self.deck_id = self.deck.id

            # Create default note type
            self.nt = NoteType(
                name="Basic Model",
                user_id=self.user_id,
            )
            db.session.add(self.nt)
            db.session.flush()
            self.nt_id = self.nt.id

            f1 = FieldDef(note_type_id=self.nt.id, name="Front", position=0, required=True, identity_role="primary")
            f2 = FieldDef(note_type_id=self.nt.id, name="Back", position=1, required=False)
            f3 = FieldDef(note_type_id=self.nt.id, name="Extra", position=2, required=False)
            db.session.add_all([f1, f2, f3])

            t1 = Template(
                note_type_id=self.nt.id,
                name="Card 1",
                front_html="{{Front}}",
                back_html="{{FrontSide}}<hr>{{Back}}",
                position=0,
            )
            db.session.add(t1)
            db.session.commit()

    def _login_session(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.user_id)
            sess["_fresh"] = True

    # -------------------------------------------------------------------------
    # 1. Scope Independence & Isolation
    # -------------------------------------------------------------------------
    def test_oauth_scope_independence(self):
        """Verify granular scopes do not grant permissions for unrelated mutations."""
        # note:create must not satisfy note:update or note:delete
        self.assertFalse(mcp_scope_service.has_scope(["note:create"], "note:update"))
        self.assertFalse(mcp_scope_service.has_scope(["note:create"], "note:delete"))
        self.assertFalse(mcp_scope_service.has_scope(["note:create"], "deck:write"))
        self.assertFalse(mcp_scope_service.has_scope(["note:create"], "study:write"))
        self.assertFalse(mcp_scope_service.has_scope(["note:create"], "note:sync"))

        # deck:write must not satisfy deck:read or note:create
        self.assertFalse(mcp_scope_service.has_scope(["deck:write"], "deck:read"))
        self.assertFalse(mcp_scope_service.has_scope(["deck:write"], "note:create"))

        # note:read satisfies note:check but not mutations
        self.assertTrue(mcp_scope_service.has_scope(["note:read"], "note:check"))
        self.assertFalse(mcp_scope_service.has_scope(["note:read"], "note:create"))
        self.assertFalse(mcp_scope_service.has_scope(["note:read"], "note:update"))

        # Legacy wildcards
        self.assertTrue(mcp_scope_service.has_scope(["write"], "note:create"))
        self.assertTrue(mcp_scope_service.has_scope(["write"], "note:sync"))
        self.assertTrue(mcp_scope_service.has_scope(["*"], "note:sync"))

    # -------------------------------------------------------------------------
    # 2. OAuth Rejection of Invalid Scope
    # -------------------------------------------------------------------------
    def test_oauth_rejects_invalid_scope(self):
        """Requesting unsupported/unknown scopes must raise invalid_scope error."""
        with self.app.app_context():
            with self.assertRaises(ValueError):
                mcp_scope_service.validate_and_normalize_oauth_scopes("unknown:permission")

            with self.assertRaises(ValueError):
                mcp_scope_service.validate_and_normalize_oauth_scopes(["deck:read", "invalid_scope_xyz"])

            # Default scope fallback is ONLY for empty/None scopes
            defaults = mcp_scope_service.validate_and_normalize_oauth_scopes(None)
            self.assertEqual(defaults, mcp_scope_service.DEFAULT_SCOPES)

            # Register client for HTTP endpoint test
            client = oauth_service.register_oauth_client(
                client_id="test_client_scope",
                client_name="Scope Test App",
                redirect_uris=["https://client.example.com/oauth/callback"],
                is_confidential=False,
            )

            # Test authorize endpoint with invalid_scope
            self._login_session()
            verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
            digest = hashlib.sha256(verifier.encode("ascii")).digest()
            challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

            resp = self.client.get(
                f"/oauth/authorize?response_type=code&client_id=test_client_scope&redirect_uri=https://client.example.com/oauth/callback&scope=unknown:permission&code_challenge={challenge}&code_challenge_method=S256"
            )
            self.assertEqual(resp.status_code, 302)
            loc = resp.headers.get("Location", "")
            parsed = urlparse(loc)
            params = parse_qs(parsed.query)
            self.assertEqual(params.get("error"), ["invalid_scope"])

            # Test consent-info endpoint with invalid_scope
            resp_info = self.client.get(
                "/api/oauth/consent-info?client_id=test_client_scope&scope=unknown:permission"
            )
            self.assertEqual(resp_info.status_code, 400)
            self.assertEqual(resp_info.json.get("error"), "invalid_scope")

    # -------------------------------------------------------------------------
    # 3. Destructive NoteType Update Enforces Preview & Confirmation
    # -------------------------------------------------------------------------
    def test_destructive_note_type_update_requires_preview_and_confirm(self):
        """Deleting a field or template with existing data requires preview_id and confirm=True."""
        with self.app.app_context():
            # Create a note
            note_res = mcp_tool_service.create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.nt_id,
                    "fields": {"Front": "Tokyo", "Back": "Capital", "Extra": "Important data"},
                },
            )
            self.assertIsNotNone(note_res.get("note_id"))

            # Attempt direct destructive update (removing field Extra) without preview_id -> PREVIEW_REQUIRED
            with self.assertRaises(RequestValidationError) as cm_preview:
                mcp_tool_service.update_note_type(
                    user_id=self.user_id,
                    note_type_id=self.nt_id,
                    fields={"removed": ["Extra"]},
                )
            self.assertEqual(cm_preview.exception.code, "PREVIEW_REQUIRED")

            # Generate preview token
            preview_res = mcp_tool_service.preview_note_type_update(
                user_id=self.user_id,
                note_type_id=self.nt_id,
                fields={"removed": ["Extra"]},
            )
            preview_id = preview_res["preview_id"]
            self.assertTrue(preview_res["data_loss_possible"])
            self.assertTrue(preview_res["requires_confirmation"])

            # Attempt update with preview_id but confirm=False -> CONFIRMATION_REQUIRED
            with self.assertRaises(RequestValidationError) as cm_confirm:
                mcp_tool_service.update_note_type(
                    user_id=self.user_id,
                    note_type_id=self.nt_id,
                    fields={"removed": ["Extra"]},
                    preview_id=preview_id,
                    confirm=False,
                )
            self.assertEqual(cm_confirm.exception.code, "CONFIRMATION_REQUIRED")

            # Execute update with preview_id and confirm=True -> Success
            update_res = mcp_tool_service.update_note_type(
                user_id=self.user_id,
                note_type_id=self.nt_id,
                fields={"removed": ["Extra"]},
                preview_id=preview_id,
                confirm=True,
            )
            self.assertNotIn("Extra", [f["name"] for f in update_res["fields"]])

    # -------------------------------------------------------------------------
    # 4. Stale Preview Detection
    # -------------------------------------------------------------------------
    def test_stale_preview_token_fails_with_409(self):
        """Executing an outdated preview token after state modification fails with STALE_PREVIEW_ERROR."""
        with self.app.app_context():
            # Create a note
            mcp_tool_service.create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.nt_id,
                    "fields": {"Front": "Kyoto", "Back": "Ancient Capital", "Extra": "Temple"},
                },
            )

            # Generate preview
            preview_res = mcp_tool_service.preview_note_type_update(
                user_id=self.user_id,
                note_type_id=self.nt_id,
                fields={"removed": ["Extra"]},
            )
            stale_preview_id = preview_res["preview_id"]

            # Modify the resource state in the interim (add another note, changing resource_version)
            mcp_tool_service.create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.nt_id,
                    "fields": {"Front": "Osaka", "Back": "Food City", "Extra": "Castle"},
                },
            )

            # Execute with original stale preview_id -> STALE_PREVIEW_ERROR (409)
            with self.assertRaises(RequestValidationError) as cm_stale:
                mcp_tool_service.update_note_type(
                    user_id=self.user_id,
                    note_type_id=self.nt_id,
                    fields={"removed": ["Extra"]},
                    preview_id=stale_preview_id,
                    confirm=True,
                )
            self.assertEqual(cm_stale.exception.code, "STALE_PREVIEW_ERROR")
            self.assertEqual(cm_stale.exception.status, 409)

    # -------------------------------------------------------------------------
    # 5. Note Sync Scope Enforcement
    # -------------------------------------------------------------------------
    def test_sync_notes_requires_note_sync_scope(self):
        """sync_notes requires 'note:sync' scope, not satisfied by 'note:create'."""
        with self.app.app_context():
            # Token with only note:create
            token_create = mcp_access_token_service.issue_token_and_commit(
                user_id=self.user_id,
                name="Create Only",
                scopes=["note:create"],
            )

            # Token with note:sync
            token_sync = mcp_access_token_service.issue_token_and_commit(
                user_id=self.user_id,
                name="Sync Token",
                scopes=["note:sync"],
            )

            payload = {
                "jsonrpc": "2.0",
                "id": "sync-1",
                "method": "tools/call",
                "params": {
                    "name": "sync_notes",
                    "arguments": {
                        "deck_id": self.deck_id,
                        "note_type_id": self.nt_id,
                        "source_key": "test_sheet",
                        "notes": [
                            {"external_id": "r1", "fields": {"Front": "Neko", "Back": "Cat"}}
                        ],
                    },
                },
            }

            # Call with create-only token -> Forbidden / permission denied (403, code -32003)
            resp_denied = self.client.post(
                "/api/mcp",
                data=json.dumps(payload),
                content_type="application/json",
                headers={"Authorization": f"Bearer {token_create.token}"},
            )
            self.assertEqual(resp_denied.status_code, 403)
            err_data = resp_denied.json.get("error") or {}
            self.assertEqual(err_data.get("code"), -32003)

            # Call with note:sync token -> Success
            resp_ok = self.client.post(
                "/api/mcp",
                data=json.dumps(payload),
                content_type="application/json",
                headers={"Authorization": f"Bearer {token_sync.token}"},
            )
            self.assertEqual(resp_ok.status_code, 200)
            res_data = resp_ok.json.get("result")
            self.assertIsNotNone(res_data)
            self.assertFalse(res_data.get("isError", False))

    # -------------------------------------------------------------------------
    # 6. NoteSync NoteType Mismatch Conflict Guardrail
    # -------------------------------------------------------------------------
    def test_sync_notes_mismatch_existing_note_type_conflict(self):
        """Syncing an existing external_id mapped to NoteType A using NoteType B reports conflict and does not overwrite."""
        with self.app.app_context():
            # Create second note type
            nt2 = NoteType(
                name="Second Model",
                user_id=self.user_id,
            )
            db.session.add(nt2)
            db.session.flush()
            f_a = FieldDef(note_type_id=nt2.id, name="Front", position=0, required=True, identity_role="primary")
            f_b = FieldDef(note_type_id=nt2.id, name="Back", position=1, required=False)
            t_a = Template(note_type_id=nt2.id, name="Card 1", front_html="{{Front}}", back_html="{{Back}}", position=0)
            db.session.add_all([f_a, f_b, t_a])
            db.session.commit()

            # Initial sync with NoteType 1
            exec_res1 = note_sync_service.execute_sync_notes(
                user_id=self.user_id,
                deck_id=self.deck_id,
                note_type_id=self.nt_id,
                source_key="sheet_a",
                notes=[{"external_id": "row_unique_100", "fields": {"Front": "Inu", "Back": "Dog"}}],
            )
            self.assertEqual(exec_res1["summary"]["created"], 1)

            # Check preview_sync_notes with NoteType 2 -> must report conflict
            prev_mismatch = note_sync_service.preview_sync_notes(
                user_id=self.user_id,
                deck_id=self.deck_id,
                note_type_id=nt2.id,
                source_key="sheet_a",
                notes=[{"external_id": "row_unique_100", "fields": {"Front": "Inu", "Back": "Canine"}}],
            )
            self.assertEqual(prev_mismatch["summary"]["conflicts"], 1)
            self.assertEqual(prev_mismatch["items"][0]["action"], "conflict")

            # Check execute_sync_notes with NoteType 2 -> must record failed NOTE_TYPE_MISMATCH
            exec_mismatch = note_sync_service.execute_sync_notes(
                user_id=self.user_id,
                deck_id=self.deck_id,
                note_type_id=nt2.id,
                source_key="sheet_a",
                notes=[{"external_id": "row_unique_100", "fields": {"Front": "Inu", "Back": "Canine"}}],
            )
            self.assertEqual(exec_mismatch["summary"]["failed"], 1)
            self.assertEqual(exec_mismatch["failed_items"][0]["code"], "NOTE_TYPE_MISMATCH")

            # Verify existing note's NoteType is preserved
            ref = ConnectSourceNoteRef.query.filter_by(
                user_id=self.user_id, source_key="sheet_a", external_note_id="row_unique_100"
            ).first()
            self.assertIsNotNone(ref)
            self.assertEqual(ref.note.note_type_id, self.nt_id)

    # -------------------------------------------------------------------------
    # 7. NoteType Template Invariant
    # -------------------------------------------------------------------------
    def test_note_type_without_templates_fails_deterministically(self):
        """NoteType without templates cannot create notes or be synced without explicit templates."""
        with self.app.app_context():
            # Create a NoteType with no templates
            nt_no_tmpl = NoteType(
                name="Empty Model",
                user_id=self.user_id,
            )
            db.session.add(nt_no_tmpl)
            db.session.flush()
            f1 = FieldDef(note_type_id=nt_no_tmpl.id, name="Front", position=0, required=True, identity_role="primary")
            f2 = FieldDef(note_type_id=nt_no_tmpl.id, name="Back", position=1, required=False)
            db.session.add_all([f1, f2])
            db.session.commit()

            # create_note must raise NOTE_TYPE_HAS_NO_TEMPLATE
            with self.assertRaises(RequestValidationError) as cm_create:
                mcp_tool_service.create_note(
                    user_id=self.user_id,
                    note_data={
                        "deck_id": self.deck_id,
                        "note_type_id": nt_no_tmpl.id,
                        "fields": {"Front": "Test", "Back": "Val"},
                    },
                )
            self.assertEqual(cm_create.exception.code, "NOTE_TYPE_HAS_NO_TEMPLATE")

            # preview_sync_notes must raise NOTE_TYPE_HAS_NO_TEMPLATE
            with self.assertRaises(RequestValidationError) as cm_prev:
                note_sync_service.preview_sync_notes(
                    user_id=self.user_id,
                    deck_id=self.deck_id,
                    note_type_id=nt_no_tmpl.id,
                    notes=[{"external_id": "x1", "fields": {"Front": "Test", "Back": "Val"}}],
                )
            self.assertEqual(cm_prev.exception.code, "NOTE_TYPE_HAS_NO_TEMPLATE")

            # execute_sync_notes must raise NOTE_TYPE_HAS_NO_TEMPLATE
            with self.assertRaises(RequestValidationError) as cm_sync:
                note_sync_service.execute_sync_notes(
                    user_id=self.user_id,
                    deck_id=self.deck_id,
                    note_type_id=nt_no_tmpl.id,
                    notes=[{"external_id": "x1", "fields": {"Front": "Test", "Back": "Val"}}],
                )
            self.assertEqual(cm_sync.exception.code, "NOTE_TYPE_HAS_NO_TEMPLATE")

            # create_note_type with empty templates=[] must raise NOTE_TYPE_MUST_HAVE_TEMPLATES
            with self.assertRaises(RequestValidationError) as cm_nt:
                mcp_tool_service.create_note_type(
                    user_id=self.user_id,
                    name="Invalid Model No Tmpl",
                    fields=[{"name": "Front"}, {"name": "Back"}],
                    templates=[],
                )
            self.assertEqual(cm_nt.exception.code, "NOTE_TYPE_MUST_HAVE_TEMPLATES")

    # -------------------------------------------------------------------------
    # 8. End-to-End OAuth Authorization Code to Remote MCP tools/call
    # -------------------------------------------------------------------------
    def test_end_to_end_oauth_authorization_code_to_mcp_tools_call(self):
        """Complete OAuth PKCE flow -> token exchange -> remote MCP JSON-RPC execution."""
        with self.app.app_context():
            client = oauth_service.register_oauth_client(
                client_id="chatgpt_assistant_e2e",
                client_name="ChatGPT Assistant E2E",
                redirect_uris=["https://chat.openai.com/aip/callback"],
                is_confidential=False,
            )

        self._login_session()
        verifier = "e2e_code_verifier_123456789012345678901234567890"
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

        # 1. Authorize with PKCE and specific scopes via POST approval
        resp_auth = self.client.post(
            "/oauth/authorize",
            data={
                "client_id": "chatgpt_assistant_e2e",
                "redirect_uri": "https://chat.openai.com/aip/callback",
                "scope": "deck:read note:create note:sync",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "state": "xyz123",
                "action": "approve",
            },
        )
        self.assertEqual(resp_auth.status_code, 302)
        loc = resp_auth.headers.get("Location", "")
        params = parse_qs(urlparse(loc).query)
        auth_code = params["code"][0]
        self.assertEqual(params["state"][0], "xyz123")

        # 2. Exchange code for access_token
        resp_token = self.client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "chatgpt_assistant_e2e",
                "code": auth_code,
                "redirect_uri": "https://chat.openai.com/aip/callback",
                "code_verifier": verifier,
            },
        )
        self.assertEqual(resp_token.status_code, 200)
        token_data = resp_token.json
        access_token = token_data["access_token"]
        granted_scope = token_data["scope"]
        self.assertIn("note:sync", granted_scope)
        self.assertIn("deck:read", granted_scope)
        self.assertIn("note:create", granted_scope)
        self.assertNotIn("note:update", granted_scope)

        # 3. Call Remote MCP tools/call for sync_notes (granted note:sync) -> 200 OK
        sync_payload = {
            "jsonrpc": "2.0",
            "id": "e2e-sync",
            "method": "tools/call",
            "params": {
                "name": "sync_notes",
                "arguments": {
                    "deck_id": self.deck_id,
                    "note_type_id": self.nt_id,
                    "source_key": "e2e_source",
                    "notes": [
                        {"external_id": "e2e_1", "fields": {"Front": "Hikari", "Back": "Light"}}
                    ],
                },
            },
        }
        resp_mcp_sync = self.client.post(
            "/api/mcp",
            data=json.dumps(sync_payload),
            content_type="application/json",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(resp_mcp_sync.status_code, 200)
        res_sync = resp_mcp_sync.json.get("result")
        self.assertIsNotNone(res_sync)
        self.assertFalse(res_sync.get("isError", False))

        # 4. Call Remote MCP tools/call for update_note (NOT granted) -> Permission Denied
        update_payload = {
            "jsonrpc": "2.0",
            "id": "e2e-update",
            "method": "tools/call",
            "params": {
                "name": "update_note",
                "arguments": {
                    "note_id": "1",
                    "fields": {"Front": "New Val"},
                },
            },
        }
        resp_mcp_update = self.client.post(
            "/api/mcp",
            data=json.dumps(update_payload),
            content_type="application/json",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        self.assertEqual(resp_mcp_update.status_code, 403)
        err_update = resp_mcp_update.json.get("error") or {}
        self.assertEqual(err_update.get("code"), -32003)


if __name__ == "__main__":
    unittest.main()
