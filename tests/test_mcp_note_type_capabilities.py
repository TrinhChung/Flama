"""Unit & integration tests for Flama Note Type / Model capabilities and MCP tools."""

from __future__ import annotations

import json
import unittest

from app.connect import create_connect_app
from app.services import mcp_access_token_service, mcp_tool_service, user_api_token_service
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


class McpNoteTypeCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        self.app = create_connect_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "CONNECT_CORS_ALLOWED_ORIGINS": (),
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = User(
                username="test_mcp_user",
                email="mcp_user@example.com",
                timezone="UTC",
                is_admin=False,
            )
            user.set_password("password123")
            db.session.add(user)

            other_user = User(
                username="other_user",
                email="other@example.com",
                timezone="UTC",
                is_admin=False,
            )
            other_user.set_password("password123")
            db.session.add(other_user)
            db.session.flush()

            self.user_id = user.id
            self.other_user_id = other_user.id

            issued_token = user_api_token_service.issue_token(user_id=user.id, name="Test Integration Token")
            self.token = issued_token.plaintext

            # Setup a basic note type
            nt = NoteType(user_id=user.id, name="Vocabulary Standard")
            db.session.add(nt)
            db.session.flush()
            self.note_type_id = nt.id

            f1 = FieldDef(note_type_id=nt.id, name="Word", field_type="text", position=0, required=True, identity_role="primary")
            f2 = FieldDef(note_type_id=nt.id, name="Reading", field_type="text", position=1, required=False)
            f3 = FieldDef(note_type_id=nt.id, name="Meaning", field_type="richtext", position=2, required=True)
            db.session.add_all([f1, f2, f3])
            db.session.flush()

            t1 = Template(
                note_type_id=nt.id,
                name="Recognition",
                front_html="<div class='word'>{{Word}}</div>",
                back_html="{{FrontSide}}\n<hr>\n<div class='reading'>{{Reading}}</div>\n<div class='meaning'>{{Meaning}}</div>",
                shared_css=".word { font-size: 24px; }",
                position=0,
                is_default=True,
            )
            db.session.add(t1)
            db.session.commit()
            self.template_id = t1.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _rpc_call(self, method: str, params: dict, token: str | None = None) -> dict:
        auth_token = token or self.token
        headers = {
            "MCP-Protocol-Version": "2025-11-25",
            "Content-Type": "application/json",
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        response = self.client.post(
            "/v1/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": "test-req", "method": method, "params": params},
        )
        self.assertIn(response.status_code, (200, 400, 403, 404, 409))
        return response.get_json()

    def _call_tool(self, name: str, arguments: dict, token: str | None = None) -> dict:
        payload = self._rpc_call("tools/call", {"name": name, "arguments": arguments}, token=token)
        self.assertNotIn("error", payload, f"RPC error calling {name}: {payload.get('error')}")
        result = payload["result"]
        return result.get("structuredContent") or json.loads(result["content"][0]["text"])

    # -----------------------------------------------------------------------
    # 1. List and Get Schema
    # -----------------------------------------------------------------------

    def test_list_note_types(self):
        with self.app.app_context():
            res = self._call_tool("list_note_types", {})
            self.assertIn("note_types", res)
            types = res["note_types"]
            self.assertTrue(len(types) >= 1)
            nt_item = next(t for t in types if t["id"] == self.note_type_id)
            self.assertEqual(nt_item["name"], "Vocabulary Standard")
            self.assertEqual(nt_item["field_count"], 3)
            self.assertEqual(nt_item["template_count"], 1)
            self.assertTrue(nt_item["is_owner"])

    def test_get_note_type_schema_full_metadata(self):
        with self.app.app_context():
            schema = self._call_tool("get_note_type_schema", {"note_type_id": self.note_type_id})
            self.assertEqual(schema["id"], self.note_type_id)
            self.assertEqual(schema["name"], "Vocabulary Standard")
            self.assertTrue(schema["is_owner"])
            self.assertEqual(schema["field_names"], ["Word", "Reading", "Meaning"])

            # Fields metadata
            self.assertEqual(len(schema["fields"]), 3)
            word_f = schema["fields"][0]
            self.assertEqual(word_f["name"], "Word")
            self.assertEqual(word_f["field_type"], "text")
            self.assertTrue(word_f["required"])
            self.assertEqual(word_f["identity_role"], "primary")
            self.assertTrue(word_f["editable"])
            self.assertEqual(word_f["validation_constraints"]["is_primary_identity"], True)

            # Templates metadata
            self.assertEqual(len(schema["templates"]), 1)
            tmpl = schema["templates"][0]
            self.assertEqual(tmpl["name"], "Recognition")
            self.assertTrue(tmpl["is_default"])
            self.assertIn("{{Word}}", tmpl["front_html"])
            self.assertEqual(tmpl["shared_css"], ".word { font-size: 24px; }")

            # Sample note payload
            self.assertIn("sample_note_payload", schema)
            self.assertEqual(schema["sample_note_payload"]["fields"]["Word"], "<Word>")

    def test_get_note_type_schema_by_name(self):
        with self.app.app_context():
            schema = self._call_tool("get_note_type_schema", {"name": "Vocabulary Standard"})
            self.assertEqual(schema["id"], self.note_type_id)

    # -----------------------------------------------------------------------
    # 2. Deck Default Note Type & note_types_in_use
    # -----------------------------------------------------------------------

    def test_deck_with_default_note_type_and_in_use(self):
        with self.app.app_context():
            # Create deck with default_note_type_id
            deck_res = self._call_tool("create_deck", {
                "name": "JLPT N1 Deck",
                "default_note_type_id": self.note_type_id,
            })
            deck_id = deck_res["deck_id"]
            self.assertIsNotNone(deck_res.get("default_note_type"))
            self.assertEqual(deck_res["default_note_type"]["id"], self.note_type_id)

            # Add a note to the deck
            self._call_tool("create_note", {
                "deck_id": deck_id,
                "note_type_id": self.note_type_id,
                "fields": {"Word": "日本語", "Reading": "にほんご", "Meaning": "Japanese"},
            })

            # Check get_deck returns default_note_type and note_types_in_use
            deck_info = self._call_tool("get_deck", {"deck_id": deck_id})
            self.assertIsNotNone(deck_info["default_note_type"])
            self.assertEqual(deck_info["default_note_type"]["id"], self.note_type_id)
            self.assertEqual(deck_info["default_note_type"]["name"], "Vocabulary Standard")

            self.assertEqual(len(deck_info["note_types_in_use"]), 1)
            in_use = deck_info["note_types_in_use"][0]
            self.assertEqual(in_use["id"], self.note_type_id)
            self.assertEqual(in_use["notes_count"], 1)

    def test_deck_without_default_note_type(self):
        with self.app.app_context():
            deck_res = self._call_tool("create_deck", {"name": "Empty Deck"})
            deck_id = deck_res["deck_id"]

            deck_info = self._call_tool("get_deck", {"deck_id": deck_id})
            self.assertIsNone(deck_info["default_note_type"])
            self.assertEqual(deck_info["note_types_in_use"], [])

    def test_update_deck_default_note_type(self):
        with self.app.app_context():
            deck_res = self._call_tool("create_deck", {"name": "Custom Deck"})
            deck_id = deck_res["deck_id"]

            # Update default note type
            up_res = self._call_tool("update_deck", {
                "deck_id": deck_id,
                "default_note_type_id": self.note_type_id,
            })
            self.assertIsNotNone(up_res.get("default_note_type"))
            self.assertEqual(up_res["default_note_type"]["id"], self.note_type_id)

            # Clear default note type
            clear_res = self._call_tool("update_deck", {
                "deck_id": deck_id,
                "default_note_type_id": None,
            })
            self.assertIsNone(clear_res.get("default_note_type"))

    # -----------------------------------------------------------------------
    # 3. Create Note Type
    # -----------------------------------------------------------------------

    def test_create_valid_note_type(self):
        with self.app.app_context():
            created = self._call_tool("create_note_type", {
                "name": "Kanji Mastery",
                "description": "Note type for kanji radicals and stroke orders",
                "fields": [
                    {"name": "Kanji", "field_type": "text", "required": True, "identity_role": "primary"},
                    {"name": "Onyomi", "field_type": "text", "required": False},
                    {"name": "Kunyomi", "field_type": "text", "required": False},
                    {"name": "Meaning_VI", "field_type": "richtext", "required": True},
                ],
                "templates": [
                    {
                        "name": "Writing",
                        "front_html": "<h1>{{Kanji}}</h1>",
                        "back_html": "{{FrontSide}}<hr><p>{{Onyomi}}</p><p>{{Kunyomi}}</p><p>{{Meaning_VI}}</p>",
                        "shared_css": "h1 { color: red; }",
                    }
                ],
            })
            self.assertIsNotNone(created["id"])
            self.assertEqual(created["name"], "Kanji Mastery")
            self.assertEqual(len(created["fields"]), 4)
            self.assertEqual(len(created["templates"]), 1)

    def test_create_duplicate_note_type_name_fails(self):
        with self.app.app_context():
            payload = self._rpc_call("tools/call", {
                "name": "create_note_type",
                "arguments": {"name": "Vocabulary Standard"},
            })
            self.assertIn("error", payload)
            self.assertIn("đã tồn tại", payload["error"]["message"])

    def test_create_note_type_duplicate_fields_fails(self):
        with self.app.app_context():
            payload = self._rpc_call("tools/call", {
                "name": "create_note_type",
                "arguments": {
                    "name": "Grammar",
                    "fields": [
                        {"name": "Pattern", "field_type": "text"},
                        {"name": "pattern", "field_type": "text"},
                    ],
                },
            })
            self.assertIn("error", payload)
            self.assertIn("trùng lặp", payload["error"]["message"].lower())

    def test_create_note_type_invalid_template_syntax_fails(self):
        with self.app.app_context():
            payload = self._rpc_call("tools/call", {
                "name": "create_note_type",
                "arguments": {
                    "name": "Broken Template",
                    "fields": [{"name": "Front", "field_type": "text"}],
                    "templates": [
                        {
                            "name": "Broken",
                            "front_html": "{{#UnclosedTag}} Hello",
                            "back_html": "{{FrontSide}}",
                        }
                    ],
                },
            })
            self.assertIn("error", payload)
            self.assertIn("Lỗi cú pháp trong template", payload["error"]["message"])

    # -----------------------------------------------------------------------
    # 4. Preview & Update Note Type
    # -----------------------------------------------------------------------

    def test_preview_note_type_update_safe(self):
        with self.app.app_context():
            preview = self._call_tool("preview_note_type_update", {
                "note_type_id": self.note_type_id,
                "name": "Vocabulary Standard v2",
                "fields": {
                    "added": [{"name": "Audio", "field_type": "audio"}],
                },
            })
            self.assertIn("preview_id", preview)
            self.assertIn("resource_version", preview)
            self.assertFalse(preview["data_loss_possible"])
            self.assertEqual(len(preview["changes"]["added_fields"]), 1)
            self.assertEqual(preview["changes"]["name_change"]["new"], "Vocabulary Standard v2")

    def test_preview_note_type_update_destructive(self):
        with self.app.app_context():
            # Add a note with data in Reading and Meaning
            deck = Deck(name="Temp Deck", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.flush()

            note = Note(
                note_type_id=self.note_type_id,
                user_id=self.user_id,
                deck_id=deck.id,
                field_values={"Word": "本", "Reading": "ほん", "Meaning": "Book"},
            )
            db.session.add(note)
            db.session.flush()
            card = Card(note_id=note.id, template_id=self.template_id)
            db.session.add(card)
            db.session.commit()

            # Preview removing 'Meaning' and removing template
            preview = self._call_tool("preview_note_type_update", {
                "note_type_id": self.note_type_id,
                "fields": {
                    "removed": ["Meaning"],
                },
            })
            self.assertTrue(preview["data_loss_possible"])
            self.assertTrue(preview["requires_confirmation"])
            self.assertTrue(any("Meaning" in w for w in preview["warnings"]))

    def test_update_note_type_with_field_rename_preserves_data(self):
        with self.app.app_context():
            # Create a note
            deck = Deck(name="Learning Deck", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.flush()

            note = Note(
                note_type_id=self.note_type_id,
                user_id=self.user_id,
                deck_id=deck.id,
                field_values={"Word": "猫", "Reading": "ねこ", "Meaning": "Cat"},
            )
            db.session.add(note)
            db.session.commit()
            note_id = note.id

            # 1. Preview renaming Meaning -> Definition
            preview = self._call_tool("preview_note_type_update", {
                "note_type_id": self.note_type_id,
                "fields": {
                    "renamed": [{"old_name": "Meaning", "new_name": "Definition"}],
                },
            })
            preview_id = preview["preview_id"]

            # 2. Execute update
            updated = self._call_tool("update_note_type", {
                "note_type_id": self.note_type_id,
                "fields": {
                    "renamed": [{"old_name": "Meaning", "new_name": "Definition"}],
                },
                "preview_id": preview_id,
            })
            self.assertIn("Definition", updated["field_names"])
            self.assertNotIn("Meaning", updated["field_names"])

            # 3. Verify note data was migrated seamlessly
            reloaded_note = db.session.get(Note, note_id)
            self.assertEqual(reloaded_note.field_values.get("Definition"), "Cat")
            self.assertNotIn("Meaning", reloaded_note.field_values)

    def test_update_note_type_stale_preview_protection(self):
        with self.app.app_context():
            # 1. Generate preview
            preview = self._call_tool("preview_note_type_update", {
                "note_type_id": self.note_type_id,
                "fields": {"added": [{"name": "Example", "field_type": "text"}]},
            })
            preview_id = preview["preview_id"]

            # 2. Mutate state: Add a note
            deck = Deck(name="Test Deck", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.flush()
            note = Note(note_type_id=self.note_type_id, user_id=self.user_id, deck_id=deck.id, field_values={"Word": "犬"})
            db.session.add(note)
            db.session.commit()

            # 3. Attempt update with stale preview token
            payload = self._rpc_call("tools/call", {
                "name": "update_note_type",
                "arguments": {
                    "note_type_id": self.note_type_id,
                    "fields": {"added": [{"name": "Example", "field_type": "text"}]},
                    "preview_id": preview_id,
                },
            })
            self.assertIn("error", payload)
            self.assertEqual(payload["error"]["data"]["code"], "STALE_PREVIEW_ERROR")

    # -----------------------------------------------------------------------
    # 5. Delete Note Type
    # -----------------------------------------------------------------------

    def test_delete_unused_note_type(self):
        with self.app.app_context():
            # Create fresh unused note type
            created = self._call_tool("create_note_type", {"name": "Unused Note Type"})
            nt_id = created["id"]

            # 1. Preview without confirm
            prev = self._call_tool("delete_note_type", {"note_type_id": nt_id, "confirm": False})
            self.assertTrue(prev["requires_confirmation"])
            self.assertTrue(prev["can_delete"])
            self.assertEqual(prev["impact"]["notes_count"], 0)
            preview_id = prev["preview_id"]

            # 2. Delete with confirm
            del_res = self._call_tool("delete_note_type", {
                "note_type_id": nt_id,
                "confirm": True,
                "preview_id": preview_id,
            })
            self.assertTrue(del_res["success"])
            self.assertTrue(del_res["deleted"])

            # Verify deleted from DB
            self.assertIsNone(db.session.get(NoteType, nt_id))

    def test_delete_note_type_in_use_blocked(self):
        with self.app.app_context():
            # Add note using note type
            deck = Deck(name="Study Deck", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.flush()
            note = Note(note_type_id=self.note_type_id, user_id=self.user_id, deck_id=deck.id, field_values={"Word": "花"})
            db.session.add(note)
            db.session.commit()

            # 1. Preview shows can_delete: False
            prev = self._call_tool("delete_note_type", {"note_type_id": self.note_type_id, "confirm": False})
            self.assertFalse(prev["can_delete"])
            self.assertEqual(prev["impact"]["notes_count"], 1)

            # 2. Attempt deletion with confirm=True is rejected with 409
            payload = self._rpc_call("tools/call", {
                "name": "delete_note_type",
                "arguments": {
                    "note_type_id": self.note_type_id,
                    "confirm": True,
                    "preview_id": prev["preview_id"],
                },
            })
            self.assertIn("error", payload)
            self.assertEqual(payload["error"]["data"]["code"], "NOTE_TYPE_HAS_NOTES")

    # -----------------------------------------------------------------------
    # 6. End-to-End Note Mutation & Sync with Custom Note Type
    # -----------------------------------------------------------------------

    def test_create_update_batch_sync_notes_with_custom_note_type(self):
        with self.app.app_context():
            # 1. Create custom NoteType
            nt_info = self._call_tool("create_note_type", {
                "name": "English Phrasal Verbs",
                "fields": [
                    {"name": "Verb", "field_type": "text", "required": True, "identity_role": "primary"},
                    {"name": "Preposition", "field_type": "text", "required": True},
                    {"name": "Meaning", "field_type": "text", "required": True},
                ],
            })
            nt_id = nt_info["id"]

            deck_res = self._call_tool("create_deck", {"name": "Phrasal Verbs", "default_note_type_id": nt_id})
            deck_id = deck_res["deck_id"]

            # 2. Create single note
            created_note = self._call_tool("create_note", {
                "deck_id": deck_id,
                "note_type_id": nt_id,
                "fields": {"Verb": "give", "Preposition": "up", "Meaning": "quit"},
            })
            self.assertIsNotNone(created_note["note_id"])

            # 3. Batch create notes
            batch_res = self._call_tool("batch_create_notes", {
                "notes": [
                    {
                        "deck_id": deck_id,
                        "note_type_id": nt_id,
                        "fields": {"Verb": "look", "Preposition": "after", "Meaning": "take care of"},
                    },
                    {
                        "deck_id": deck_id,
                        "note_type_id": nt_id,
                        "fields": {"Verb": "run", "Preposition": "into", "Meaning": "meet by chance"},
                    },
                ]
            })
            self.assertEqual(batch_res["created_count"], 2)

            # 4. Sync external notes
            sync_res = self._call_tool("sync_notes", {
                "deck_id": deck_id,
                "note_type_id": nt_id,
                "notes": [
                    {
                        "external_id": "pv_1",
                        "fields": {"Verb": "carry", "Preposition": "on", "Meaning": "continue"},
                    }
                ],
            })
            self.assertEqual(sync_res["summary"]["created"], 1)
            self.assertEqual(len(sync_res["created_note_ids"]), 1)

            # 5. Check get_deck has accurate note counts
            deck_meta = self._call_tool("get_deck", {"deck_id": deck_id})
            self.assertEqual(deck_meta["note_count"], 4)
            self.assertEqual(deck_meta["note_types_in_use"][0]["notes_count"], 4)
