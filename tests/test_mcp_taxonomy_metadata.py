"""Unit and integration tests for MCP taxonomy schema discovery and metadata/taxonomy editing on shared decks and note types."""

from __future__ import annotations

import json
import unittest

from app.connect import create_connect_app
from app.services import user_api_token_service
from models import db
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from tests.study_note_fixtures import attach_template, create_note_user


class McpTaxonomyMetadataTests(unittest.TestCase):
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
            user = create_note_user(
                db.session,
                username="test_taxonomy_user",
                email="taxonomy_user@example.com",
                timezone="UTC",
                is_admin=False,
            )
            user.set_password("password123")
            self.user_id = user.id
            issued_token = user_api_token_service.issue_token(user_id=user.id, name="Test Token")
            self.token = issued_token.plaintext

            # Create default note type & deck for tests
            nt = NoteType(user_id=user.id, name="Basic Vocab")
            db.session.add(nt)
            db.session.flush()
            self.note_type_id = nt.id

            f1 = FieldDef(note_type_id=nt.id, name="Front", field_type="text", position=0, required=True, identity_role="primary")
            f2 = FieldDef(note_type_id=nt.id, name="Back", field_type="text", position=1, required=True)
            db.session.add_all([f1, f2])

            t1 = attach_template(
                db.session,
                note_type_id=nt.id,
                owner_user_id=user.id,
                name="Card 1",
                front_html="{{Front}}",
                back_html="{{FrontSide}}<hr>{{Back}}",
                shared_css="",
                position=0,
                is_default=True,
            )

            deck = Deck(name="JLPT N3 Master", owner_user_id=user.id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id

            note = Note(
                deck_id=deck.id,
                note_type_id=nt.id,
                user_id=user.id,
                field_values={"Front": "食べる", "Back": "To eat"},
            )
            db.session.add(note)
            db.session.commit()

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

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        res = self.client.post("/v1/mcp", json=payload, headers=headers)
        return json.loads(res.data)


    def test_get_taxonomy_schema_tool(self):
        """Test get_taxonomy_schema discovery tool via MCP."""
        # Deck marketplace taxonomy schema
        resp = self._rpc_call("tools/call", {
            "name": "get_taxonomy_schema",
            "arguments": {"content_type": "deck_marketplace_item"},
        })
        self.assertNotIn("error", resp, f"Unexpected error: {resp.get('error')}")
        result = resp["result"]
        content_text = result["content"][0]["text"]
        schema_data = json.loads(content_text)
        self.assertIn("domains", schema_data)
        self.assertIn("subjects", schema_data)
        self.assertIn("difficulty_bands", schema_data)
        self.assertIn("subject_packs", schema_data)

        # Note type taxonomy schema
        resp_nt = self._rpc_call("tools/call", {
            "name": "get_taxonomy_schema",
            "arguments": {"content_type": "note_type"},
        })
        self.assertNotIn("error", resp_nt)
        nt_schema = json.loads(resp_nt["result"]["content"][0]["text"])
        self.assertIn("domains", nt_schema)
        self.assertIn("best_used_for", nt_schema)

    def test_share_deck_with_taxonomy_and_metadata(self):
        """Test sharing a deck with custom taxonomy and preview metadata."""
        resp = self._rpc_call("tools/call", {
            "name": "share_deck",
            "arguments": {
                "deck_id": self.deck_id,
                "title": "JLPT N3 Grammar and Vocab",
                "description": "Comprehensive N3 study deck",
                "primary_category": "japanese",
                "tags": ["jlpt", "n3", "grammar"],
                "pricing_mode": "free",
                "preview_text": "Sample 100 core vocabulary items with audio and context sentences.",
                "sample_cards_count": 5,
                "taxonomy_metadata": {
                    "domain": "language_learning",
                    "subject": "japanese",
                    "difficulty_band": "intermediate",
                    "framework": "jlpt",
                    "framework_level": "n3",
                    "learning_goals": ["grammar", "vocabulary"],
                    "format_features": ["cloze", "audio"],
                },
            },
        })
        self.assertNotIn("error", resp, f"Unexpected error: {resp.get('error')}")
        res_data = json.loads(resp["result"]["content"][0]["text"])
        deck_item_id = res_data["id"]

        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, deck_item_id)
            self.assertIsNotNone(item)
            self.assertEqual(item.title, "JLPT N3 Grammar and Vocab")
            self.assertEqual(item.preview_text, "Sample 100 core vocabulary items with audio and context sentences.")
            self.assertEqual(item.sample_cards_count, 5)
            self.assertIsInstance(item.taxonomy_metadata, dict)
            self.assertEqual(item.taxonomy_metadata.get("domain"), "language_learning")
            self.assertEqual(item.taxonomy_metadata.get("framework_level"), "n3")

    def test_update_shared_deck_taxonomy_and_metadata(self):
        """Test updating metadata and taxonomy on an existing shared deck."""
        # Share deck first
        share_resp = self._rpc_call("tools/call", {
            "name": "share_deck",
            "arguments": {
                "deck_id": self.deck_id,
                "title": "Initial Title",
                "primary_category": "japanese",
            },
        })
        self.assertNotIn("error", share_resp)
        deck_item_id = json.loads(share_resp["result"]["content"][0]["text"])["id"]

        # Update metadata and taxonomy
        update_resp = self._rpc_call("tools/call", {
            "name": "update_shared_deck",
            "arguments": {
                "deck_item_id": deck_item_id,
                "title": "Updated JLPT N2 Deck",
                "tags": ["n2", "intermediate"],
                "preview_text": "Updated preview text for N2 learners.",
                "sample_cards_count": 8,
                "domain": "language_learning",
                "subject": "japanese",
                "framework": "jlpt",
                "framework_level": "n2",
                "difficulty_band": "upper_intermediate",
            },
        })
        self.assertNotIn("error", update_resp, f"Update failed: {update_resp.get('error')}")

        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, deck_item_id)
            self.assertEqual(item.title, "Updated JLPT N2 Deck")
            self.assertEqual(item.preview_text, "Updated preview text for N2 learners.")
            self.assertEqual(item.sample_cards_count, 8)
            self.assertEqual(item.taxonomy_metadata.get("domain"), "language_learning")
            self.assertEqual(item.taxonomy_metadata.get("framework_level"), "n2")

    def test_create_and_update_note_type_with_taxonomy_and_metadata(self):
        """Test creating and updating note type with taxonomy and metadata."""
        # Create Note Type
        create_resp = self._rpc_call("tools/call", {
            "name": "create_note_type",
            "arguments": {
                "name": "Advanced Japanese Sentence Mining",
                "description": "Sentence mining with audio and pitch accent",
                "primary_category": "japanese",
                "tags": ["mining", "sentence", "pitch_accent"],
                "preview_text": "Sentence card format with highlight and pitch graphs.",
                "preview_image_url": "https://example.com/preview.png",
                "taxonomy_metadata": {
                    "domain": "language_learning",
                    "subject": "japanese",
                    "difficulty_band": "intermediate",
                    "best_used_for": "vocabulary",
                    "format_features": ["audio"],
                },
                "fields": [
                    {"name": "Sentence", "field_type": "text", "required": True, "identity_role": "primary"},
                    {"name": "Translation", "field_type": "text", "required": True},
                ],
                "templates": [
                    {
                        "name": "Card 1",
                        "front_html": "{{Sentence}}",
                        "back_html": "{{FrontSide}}<hr>{{Translation}}",
                    }
                ],
            },
        })
        self.assertNotIn("error", create_resp, f"Create note type error: {create_resp.get('error')}")
        nt_data = json.loads(create_resp["result"]["content"][0]["text"])
        nt_id = nt_data["id"]

        with self.app.app_context():
            nt = db.session.get(NoteType, nt_id)
            self.assertIsNotNone(nt)
            self.assertEqual(nt.primary_category, "japanese")
            self.assertEqual(nt.preview_text, "Sentence card format with highlight and pitch graphs.")
            self.assertEqual(nt.preview_image_url, "https://example.com/preview.png")
            self.assertIsInstance(nt.taxonomy_metadata, dict)
            self.assertEqual(nt.taxonomy_metadata.get("best_used_for"), "vocabulary")

        # Template listings must exist before MCP publishes the complete Note Type.
        from tests.note_type_publication_fixtures import stage_template_listings_for_note_type
        with self.app.app_context():
            stage_template_listings_for_note_type(db.session, db.session.get(NoteType, nt_id))
            db.session.commit()

        # Update Note Type with complete taxonomy for publication
        update_resp = self._rpc_call("tools/call", {
            "name": "update_note_type",
            "arguments": {
                "note_type_id": nt_id,
                "preview_text": "Updated sentence mining description.",
                "pricing_mode": "free",
                "publish_status": "published",
                "taxonomy_metadata": {
                    "domain": "language_learning",
                    "subject": "japanese",
                    "difficulty_band": "advanced",
                    "best_used_for": "grammar_drill",
                    "learning_goals": ["grammar"],
                    "primary_topics": ["sentence_patterns"],
                },
            },
        })
        self.assertNotIn("error", update_resp, f"Update note type error: {update_resp.get('error')}")

        with self.app.app_context():
            nt = db.session.get(NoteType, nt_id)
            self.assertEqual(nt.preview_text, "Updated sentence mining description.")
            self.assertEqual(nt.publish_status, "published")
            self.assertEqual(nt.taxonomy_metadata.get("difficulty_band"), "advanced")
            self.assertEqual(nt.taxonomy_metadata.get("best_used_for"), "grammar_drill")



    def test_validation_errors(self):
        """Test error responses for invalid taxonomy and metadata arguments."""
        # Invalid content_type for get_taxonomy_schema
        resp = self._rpc_call("tools/call", {
            "name": "get_taxonomy_schema",
            "arguments": {"content_type": "invalid_type"},
        })
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32602)

        # Invalid pricing_mode for update_note_type
        resp2 = self._rpc_call("tools/call", {
            "name": "update_note_type",
            "arguments": {
                "note_type_id": str(self.note_type_id),
                "pricing_mode": "invalid_mode",
            },
        })
        self.assertIn("error", resp2)
        self.assertEqual(resp2["error"]["code"], -32602)


if __name__ == "__main__":
    unittest.main()
