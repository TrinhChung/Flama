"""Comprehensive integration and unit tests for Deck Resolution, Batch Ensure, and Note Sync MCP tools."""

from __future__ import annotations

import json
import unittest

from app.connect import create_connect_app
from app.services import mcp_access_token_service, mcp_tool_registry, mcp_tool_service, note_sync_service, user_api_token_service
from models import db
from models.card import Card
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from tests.study_note_fixtures import attach_template, create_note_user


class NoteSyncAndMcpTests(unittest.TestCase):
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
                username="sync_user",
                email="sync_user@example.com",
                timezone="Asia/Tokyo",
                is_admin=False,
            )
            user.set_password("password")

            other_user = create_note_user(
                db.session,
                username="other_user",
                email="other@example.com",
                timezone="UTC",
                is_admin=False,
            )
            other_user.set_password("password")
            db.session.flush()

            self.user_id = user.id
            self.other_user_id = other_user.id

            # Create UserApiToken
            issued_api_token = user_api_token_service.issue_token(
                user_id=user.id,
                name="MCP Sync Token",
            )
            self.api_token_str = issued_api_token.plaintext

            # NoteType with Vocabulary schema
            note_type = NoteType(user_id=user.id, name="English Vocabulary")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            db.session.add_all(
                [
                    FieldDef(
                        note_type_id=note_type.id,
                        name="Word",
                        field_type="text",
                        position=0,
                        required=True,
                        identity_role="primary",
                    ),
                    FieldDef(
                        note_type_id=note_type.id,
                        name="IPA",
                        field_type="text",
                        position=1,
                        required=False,
                    ),
                    FieldDef(
                        note_type_id=note_type.id,
                        name="Meaning",
                        field_type="text",
                        position=2,
                        required=True,
                    ),
                    FieldDef(
                        note_type_id=note_type.id,
                        name="Example",
                        field_type="text",
                        position=3,
                        required=False,
                    ),
                ]
            )
            attach_template(
                db.session,
                note_type_id=note_type.id,
                owner_user_id=user.id,
                name="Card 1: Recognition",
                front_html="<div>{{Word}}</div>",
                back_html="<div>{{IPA}}<br>{{Meaning}}<br>{{Example}}</div>",
                position=0,
            )

            # Create initial deck hierarchy: English -> Luyện Đề -> Bài 1
            root_deck = Deck(name="English", owner_user_id=user.id, position=0)
            db.session.add(root_deck)
            db.session.flush()

            sub_deck = Deck(name="Luyện Đề", parent_id=root_deck.id, owner_user_id=user.id, position=0)
            db.session.add(sub_deck)
            db.session.flush()

            bai1_deck = Deck(name="Bài 1", parent_id=sub_deck.id, owner_user_id=user.id, position=0)
            db.session.add(bai1_deck)
            db.session.flush()

            self.root_deck_id = root_deck.id
            self.sub_deck_id = sub_deck.id
            self.bai1_deck_id = bai1_deck.id

            db.session.commit()

    def _call_mcp(self, tool_name: str, arguments: dict):
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        headers = {
            "MCP-Protocol-Version": "2025-11-25",
            "Authorization": f"Bearer {self.api_token_str}",
        }
        response = self.client.post(
            "/v1/mcp",
            json=payload,
            headers=headers,
        )
        return response

    # -----------------------------------------------------------------------
    # 1. Tests for resolve_deck
    # -----------------------------------------------------------------------

    def test_resolve_deck_existing(self):
        """resolve_deck should locate existing deck without modifying database."""
        with self.app.app_context():
            res = mcp_tool_service.resolve_deck(
                user_id=self.user_id,
                path="English::Luyện Đề::Bài 1",
            )
            self.assertTrue(res["found"])
            self.assertEqual(res["deck_id"], self.bai1_deck_id)
            self.assertEqual(res["name"], "Bài 1")
            self.assertEqual(res["full_path"], "English::Luyện Đề::Bài 1")
            self.assertEqual(res["parent_id"], self.sub_deck_id)

    def test_resolve_deck_non_existent(self):
        """resolve_deck should return found=False for missing path and not create it."""
        with self.app.app_context():
            initial_count = Deck.query.filter_by(owner_user_id=self.user_id).count()
            res = mcp_tool_service.resolve_deck(
                user_id=self.user_id,
                path="English::Luyện Đề::Bài 99",
            )
            self.assertFalse(res["found"])
            self.assertIsNone(res["deck_id"])

            # Verify no deck was created
            after_count = Deck.query.filter_by(owner_user_id=self.user_id).count()
            self.assertEqual(initial_count, after_count)

    def test_resolve_deck_via_mcp_api(self):
        """Test resolve_deck via JSON-RPC endpoint."""
        resp = self._call_mcp("resolve_deck", {"path": "English::Luyện Đề::Bài 1"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertNotIn("error", data)
        result = data["result"]["structuredContent"]
        self.assertTrue(result["found"])
        self.assertEqual(result["deck_id"], self.bai1_deck_id)

    # -----------------------------------------------------------------------
    # 2. Tests for batch_ensure_decks
    # -----------------------------------------------------------------------

    def test_batch_ensure_decks_creates_missing_and_reuses_existing(self):
        """batch_ensure_decks should reuse existing decks and create missing subdecks."""
        with self.app.app_context():
            paths = [
                "English::Luyện Đề::Bài 1",  # Existing
                "English::Luyện Đề::Bài 2",  # New leaf
                "English::Luyện Đề::Bài 3",  # New leaf
                "Japanese::N5::Vocabulary",  # Completely new hierarchy
            ]
            res = mcp_tool_service.batch_ensure_decks(
                user_id=self.user_id,
                paths=paths,
            )
            self.assertEqual(res["total_requested"], 4)
            self.assertEqual(res["created_count"], 3)  # Bài 2, Bài 3, Japanese::N5::Vocabulary
            self.assertEqual(res["existing_count"], 1)

            results = res["results"]
            self.assertFalse(results["English::Luyện Đề::Bài 1"]["created"])
            self.assertEqual(results["English::Luyện Đề::Bài 1"]["deck_id"], self.bai1_deck_id)

            self.assertTrue(results["English::Luyện Đề::Bài 2"]["created"])
            bai2_id = results["English::Luyện Đề::Bài 2"]["deck_id"]
            self.assertEqual(results["English::Luyện Đề::Bài 2"]["parent_id"], self.sub_deck_id)

            # Idempotency check: run again with same paths
            res2 = mcp_tool_service.batch_ensure_decks(
                user_id=self.user_id,
                paths=paths,
            )
            self.assertEqual(res2["created_count"], 0)
            self.assertEqual(res2["existing_count"], 4)
            self.assertEqual(res2["results"]["English::Luyện Đề::Bài 2"]["deck_id"], bai2_id)

    # -----------------------------------------------------------------------
    # 3. Tests for preview_note_sync
    # -----------------------------------------------------------------------

    def test_preview_note_sync_actions(self):
        """preview_note_sync should categorize create, update, unchanged, invalid, conflict without mutating DB."""
        with self.app.app_context():
            # Seed 1 existing note with ConnectSourceNoteRef
            note1 = Note(
                user_id=self.user_id,
                deck_id=self.bai1_deck_id,
                note_type_id=self.note_type_id,
                field_values={"Word": "abandon", "IPA": "/əˈbændən/", "Meaning": "từ bỏ", "Example": ""},
                tags=["b1"],
            )
            db.session.add(note1)
            db.session.flush()

            ref1 = ConnectSourceNoteRef(
                user_id=self.user_id,
                source_key="google_sheets:test_sheet",
                external_note_id="row_1",
                source_model_id=str(self.note_type_id),
                source_deck_path="English::Luyện Đề::Bài 1",
                note_id=note1.id,
                content_hash=note_sync_service.compute_note_content_hash(
                    field_values=note1.field_values,
                    tags=note1.tags,
                    deck_id=note1.deck_id,
                ),
            )
            db.session.add(ref1)
            db.session.commit()

            initial_note_count = Note.query.count()

            # Prepare sync batch
            sync_payload = {
                "source_key": "google_sheets:test_sheet",
                "deck_id": self.bai1_deck_id,
                "note_type_id": self.note_type_id,
                "notes": [
                    # 1. Unchanged
                    {
                        "external_id": "row_1",
                        "fields": {"Word": "abandon", "IPA": "/əˈbændən/", "Meaning": "từ bỏ", "Example": ""},
                        "tags": ["b1"],
                    },
                    # 2. Update (Meaning modified)
                    {
                        "external_id": "row_1_modified",  # We will test update by matching existing note or creating new
                        "fields": {"Word": "ability", "IPA": "/əˈbɪləti/", "Meaning": "khả năng", "Example": "She has the ability"},
                        "tags": ["noun"],
                    },
                    # 3. Invalid (Missing required 'Meaning')
                    {
                        "external_id": "row_invalid",
                        "fields": {"Word": "abnormal", "IPA": "", "Meaning": "", "Example": ""},
                    },
                    # 4. Duplicate external_id in same payload (Conflict)
                    {
                        "external_id": "row_dup",
                        "fields": {"Word": "abroad", "IPA": "", "Meaning": "ở nước ngoài", "Example": ""},
                    },
                    {
                        "external_id": "row_dup",
                        "fields": {"Word": "abroad 2", "IPA": "", "Meaning": "ở nước ngoài 2", "Example": ""},
                    },
                ],
            }

            preview_res = mcp_tool_service.preview_note_sync(
                user_id=self.user_id,
                **sync_payload,
            )

            summary = preview_res["summary"]
            self.assertEqual(summary["total"], 5)
            self.assertEqual(summary["unchanged"], 1)
            self.assertEqual(summary["create"], 2)  # row_1_modified, and first row_dup
            self.assertEqual(summary["invalid"], 1)  # row_invalid
            self.assertEqual(summary["conflicts"], 1)  # second row_dup

            # Verify no data changed in DB
            self.assertEqual(Note.query.count(), initial_note_count)

    # -----------------------------------------------------------------------
    # 4. Tests for sync_notes (Idempotency, Upsert, Partial Failure)
    # -----------------------------------------------------------------------

    def test_sync_notes_lifecycle_and_idempotency(self):
        """sync_notes should create notes & cards, track external refs, and be completely idempotent."""
        with self.app.app_context():
            sync_payload = {
                "source_key": "google_sheets:doc_abc",
                "deck_path": "English::Luyện Đề::Bài 2",
                "note_type_name": "English Vocabulary",
                "notes": [
                    {
                        "external_id": "item_101",
                        "fields": {"Word": "accommodate", "IPA": "/əˈkɒmədeɪt/", "Meaning": "cung cấp chỗ ở", "Example": "The hotel can accommodate 500 guests."},
                        "tags": ["verb", "hotel"],
                    },
                    {
                        "external_id": "item_102",
                        "fields": {"Word": "accompany", "IPA": "/əˈkʌmpəni/", "Meaning": "đi cùng, hộ tống", "Example": "Children must be accompanied by an adult."},
                        "tags": ["verb"],
                    },
                ],
            }

            # 1. First sync -> Should CREATE 2 notes
            res1 = mcp_tool_service.sync_notes(
                user_id=self.user_id,
                **sync_payload,
            )
            self.assertTrue(res1["success"])
            self.assertEqual(res1["summary"]["created"], 2)
            self.assertEqual(res1["summary"]["updated"], 0)
            self.assertEqual(res1["summary"]["unchanged"], 0)
            self.assertEqual(res1["summary"]["failed"], 0)
            self.assertEqual(len(res1["created_note_ids"]), 2)

            # Check Notes and Cards in DB
            notes = Note.query.filter_by(user_id=self.user_id).all()
            self.assertEqual(len(notes), 2)
            for n in notes:
                self.assertEqual(len(n.cards), 1)  # 1 card generated per template

            # Check ConnectSourceNoteRefs in DB
            refs = ConnectSourceNoteRef.query.filter_by(user_id=self.user_id, source_key="google_sheets:doc_abc").all()
            self.assertEqual(len(refs), 2)

            # 2. Second sync with identical payload -> Should be 100% UNCHANGED
            res2 = mcp_tool_service.sync_notes(
                user_id=self.user_id,
                **sync_payload,
            )
            self.assertTrue(res2["success"])
            self.assertEqual(res2["summary"]["created"], 0)
            self.assertEqual(res2["summary"]["updated"], 0)
            self.assertEqual(res2["summary"]["unchanged"], 2)
            self.assertEqual(res2["summary"]["failed"], 0)
            self.assertEqual(Note.query.count(), 2)  # No duplicate notes created

            # 3. Third sync with 1 item modified and 1 new item -> 1 UPDATE, 1 UNCHANGED, 1 CREATE
            modified_payload = {
                "source_key": "google_sheets:doc_abc",
                "deck_path": "English::Luyện Đề::Bài 2",
                "note_type_name": "English Vocabulary",
                "notes": [
                    {
                        "external_id": "item_101",
                        "fields": {"Word": "accommodate", "IPA": "/əˈkɒmədeɪt/", "Meaning": "cung cấp chỗ ở, đáp ứng", "Example": "The hotel can accommodate 500 guests."},
                        "tags": ["verb", "hotel", "updated"],
                    },
                    {
                        "external_id": "item_102",  # identical
                        "fields": {"Word": "accompany", "IPA": "/əˈkʌmpəni/", "Meaning": "đi cùng, hộ tống", "Example": "Children must be accompanied by an adult."},
                        "tags": ["verb"],
                    },
                    {
                        "external_id": "item_103",  # new
                        "fields": {"Word": "accomplish", "IPA": "/əˈkʌmplɪʃ/", "Meaning": "hoàn thành", "Example": "Mission accomplished."},
                        "tags": ["verb"],
                    },
                ],
            }
            res3 = mcp_tool_service.sync_notes(
                user_id=self.user_id,
                **modified_payload,
            )
            self.assertTrue(res3["success"])
            self.assertEqual(res3["summary"]["created"], 1)
            self.assertEqual(res3["summary"]["updated"], 1)
            self.assertEqual(res3["summary"]["unchanged"], 1)
            self.assertEqual(res3["summary"]["failed"], 0)
            self.assertEqual(Note.query.count(), 3)

            # Verify updated note content
            updated_note = db.session.get(Note, res3["updated_note_ids"][0])
            self.assertIn("đáp ứng", updated_note.field_values["Meaning"])
            self.assertIn("updated", updated_note.tags)

    def test_sync_notes_partial_failure_handling(self):
        """sync_notes should handle partial failures gracefully when stop_on_error=False."""
        with self.app.app_context():
            payload = {
                "source_key": "csv:batch_test",
                "deck_id": self.bai1_deck_id,
                "note_type_id": self.note_type_id,
                "stop_on_error": False,
                "notes": [
                    {
                        "external_id": "valid_1",
                        "fields": {"Word": "accurate", "IPA": "/ˈækjərət/", "Meaning": "chính xác", "Example": ""},
                    },
                    {
                        "external_id": "invalid_2",
                        "fields": {"Word": "accuse", "IPA": "", "Meaning": "", "Example": ""},  # Missing Meaning
                    },
                    {
                        "external_id": "valid_3",
                        "fields": {"Word": "achieve", "IPA": "/əˈtʃiːv/", "Meaning": "đạt được", "Example": ""},
                    },
                ],
            }

            res = mcp_tool_service.sync_notes(
                user_id=self.user_id,
                **payload,
            )
            self.assertTrue(res["success"])
            self.assertEqual(res["summary"]["created"], 2)
            self.assertEqual(res["summary"]["failed"], 1)
            self.assertEqual(len(res["failed_items"]), 1)
            self.assertEqual(res["failed_items"][0]["external_id"], "invalid_2")

    def test_sync_notes_large_dataset_over_50_items(self):
        """sync_notes should comfortably process datasets larger than normal single batch limits (e.g. 80 items)."""
        with self.app.app_context():
            large_notes = []
            for i in range(80):
                large_notes.append(
                    {
                        "external_id": f"large_{i}",
                        "fields": {
                            "Word": f"word_{i}",
                            "IPA": f"/w_{i}/",
                            "Meaning": f"nghĩa số {i}",
                            "Example": f"Example sentence for word {i}",
                        },
                        "tags": ["large_batch", f"unit_{i % 5}"],
                    }
                )

            res = mcp_tool_service.sync_notes(
                user_id=self.user_id,
                source_key="google_sheets:large_sheet",
                deck_id=self.bai1_deck_id,
                note_type_id=self.note_type_id,
                notes=large_notes,
            )

            self.assertTrue(res["success"])
            self.assertEqual(res["summary"]["created"], 80)
            self.assertEqual(res["summary"]["failed"], 0)
            self.assertEqual(Note.query.count(), 80)
            self.assertEqual(Card.query.count(), 80)


if __name__ == "__main__":
    unittest.main()
