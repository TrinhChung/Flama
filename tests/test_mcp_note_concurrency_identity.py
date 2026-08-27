"""Unit and integration tests for Issue #110: Note Creation Race Condition & Identity Collision Protection."""

from __future__ import annotations

import unittest

from app.connect import create_connect_app
from app.services import mcp_tool_service, user_api_token_service
from app.validators.mcp import RequestValidationError
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


class McpNoteConcurrencyIdentityTests(unittest.TestCase):
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
                username="incident_test_user",
                email="incident@example.com",
                timezone="UTC",
                is_admin=False,
            )
            user.set_password("password123")
            db.session.add(user)
            db.session.flush()

            self.user_id = user.id

            issued_token = user_api_token_service.issue_token(user_id=user.id, name="Test Token")
            self.token = issued_token.plaintext

            # Deck: English::Luyện Đề::Bài 20
            deck = Deck(owner_user_id=user.id, name="English::Luyện Đề::Bài 20")
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id

            # NoteType: En4Everyone with STT (primary) and Vocabulary
            nt = NoteType(user_id=user.id, name="En4Everyone")
            db.session.add(nt)
            db.session.flush()
            self.note_type_id = nt.id

            f_stt = FieldDef(note_type_id=nt.id, name="STT", field_type="text", position=0, required=True, identity_role="primary")
            f_voc = FieldDef(note_type_id=nt.id, name="Vocabulary", field_type="text", position=1, required=True)
            f_mean = FieldDef(note_type_id=nt.id, name="Meaning", field_type="text", position=2, required=False)
            db.session.add_all([f_stt, f_voc, f_mean])
            db.session.flush()

            tmpl = Template(
                note_type_id=nt.id,
                name="Vocabulary Card",
                front_html="<div>{{Vocabulary}}</div>",
                back_html="<div>{{Vocabulary}}</div><hr><div>{{Meaning}}</div>",
                shared_css="",
                position=0,
                is_default=True,
            )
            db.session.add(tmpl)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        headers = {
            "MCP-Protocol-Version": "2025-11-25",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        response = self.client.post(
            "/v1/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": "req-1",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        )
        data = response.get_json()
        if "error" in data:
            return {"_error": data["error"], "_http_status": response.status_code}
        return data.get("result", {}).get("structuredContent", {})

    def test_reproduce_incident_duplicate_stt_rejected_with_409(self):
        """Test reproducing Issue #110 incident:

        Batch 1 creates STT 22-26 (shred, aside, bright, plantar, sensor).
        Batch 2 attempts to create STT 22-26 (intricacy, compel...).
        Verify Batch 2 is rejected with NOTE_IDENTITY_CONFLICT (409) and Batch 1 notes are preserved!
        """
        with self.app.app_context():
            # Batch 1: Create STT 22-26
            batch1_words = ["shred", "aside", "bright", "plantar", "sensor"]
            batch1_notes = [
                {
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"STT": str(22 + i), "Vocabulary": word, "Meaning": f"Meaning of {word}"},
                }
                for i, word in enumerate(batch1_words)
            ]

            batch1_res = mcp_tool_service.batch_create_notes(user_id=self.user_id, notes=batch1_notes)
            self.assertEqual(batch1_res["created_count"], 5)
            batch1_note_ids = batch1_res["note_ids"]

            # Batch 2: Try to create notes with overlapping STT 22-26
            batch2_words = ["intricacy", "compel", "deliberately", "omit", "complicate"]
            batch2_notes = [
                {
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"STT": str(22 + i), "Vocabulary": word, "Meaning": f"Meaning of {word}"},
                }
                for i, word in enumerate(batch2_words)
            ]

            # Direct service call should raise RequestValidationError with code NOTE_IDENTITY_CONFLICT and status 409
            with self.assertRaises(RequestValidationError) as cm:
                mcp_tool_service.batch_create_notes(user_id=self.user_id, notes=batch2_notes)

            self.assertEqual(cm.exception.status, 409)
            self.assertEqual(cm.exception.code, "NOTE_IDENTITY_CONFLICT")

            # CRITICAL: Verify that the 5 original notes were NOT overwritten
            for note_id, expected_word in zip(batch1_note_ids, batch1_words):
                note = Note.query.get(note_id)
                self.assertIsNotNone(note)
                self.assertEqual(note.field_values.get("Vocabulary"), expected_word)

    def test_rpc_incident_conflict_response(self):
        """Verify the MCP JSON-RPC protocol returns error without crashing or overwriting."""
        # 1. Create first note
        res1 = self._call_tool(
            "create_note",
            {
                "deck_id": self.deck_id,
                "note_type_id": self.note_type_id,
                "fields": {"STT": "22", "Vocabulary": "shred"},
            },
        )
        self.assertIn("note_id", res1)
        original_note_id = res1["note_id"]

        # 2. Attempt duplicate create_note via RPC
        res2 = self._call_tool(
            "create_note",
            {
                "deck_id": self.deck_id,
                "note_type_id": self.note_type_id,
                "fields": {"STT": "22", "Vocabulary": "intricacy"},
            },
        )
        self.assertIn("_error", res2)
        self.assertIn("NOTE_IDENTITY_CONFLICT", str(res2["_error"]))

        # Verify database still has original vocabulary
        with self.app.app_context():
            note = Note.query.get(original_note_id)
            self.assertEqual(note.field_values.get("Vocabulary"), "shred")

    def test_allow_duplicate_true_creates_separate_notes(self):
        """When allow_duplicate is True, multiple notes with the same identity can be created."""
        with self.app.app_context():
            res1 = mcp_tool_service.create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"STT": "22", "Vocabulary": "shred"},
                    "allow_duplicate": True,
                },
            )
            res2 = mcp_tool_service.create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"STT": "22", "Vocabulary": "intricacy"},
                    "allow_duplicate": True,
                },
            )
            self.assertNotEqual(res1["note_id"], res2["note_id"])
            notes = Note.query.filter_by(user_id=self.user_id, deck_id=self.deck_id).all()
            self.assertEqual(len(notes), 2)
            vocabs = {n.field_values.get("Vocabulary") for n in notes}
            self.assertEqual(vocabs, {"shred", "intricacy"})

    def test_explicit_update_note_succeeds(self):
        """Explicit update_note must still work normally."""
        with self.app.app_context():
            created = mcp_tool_service.create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"STT": "22", "Vocabulary": "shred", "Meaning": "old meaning"},
                },
            )
            note_id = created["note_id"]

            updated = mcp_tool_service.update_note(
                user_id=self.user_id,
                note_id=note_id,
                fields={"Meaning": "new updated meaning"},
            )
            self.assertTrue(updated["success"])

            note = Note.query.get(note_id)
            self.assertEqual(note.field_values.get("Meaning"), "new updated meaning")
            self.assertEqual(note.field_values.get("Vocabulary"), "shred")

    def test_auto_assign_stt_when_omitted(self):
        """Server automatically allocates incremental STT (1, 2, 3...) when not provided by client."""
        with self.app.app_context():
            # Create single note without passing STT
            res1 = mcp_tool_service.create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"Vocabulary": "first word"},
                },
            )
            note1 = Note.query.get(res1["note_id"])
            self.assertEqual(note1.field_values.get("STT"), "1")

            # Create second single note without passing STT
            res2 = mcp_tool_service.create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"Vocabulary": "second word"},
                },
            )
            note2 = Note.query.get(res2["note_id"])
            self.assertEqual(note2.field_values.get("STT"), "2")

            # Batch create 3 notes without passing STT
            batch_res = mcp_tool_service.batch_create_notes(
                user_id=self.user_id,
                notes=[
                    {
                        "deck_id": self.deck_id,
                        "note_type_id": self.note_type_id,
                        "fields": {"Vocabulary": f"word {i}"},
                    }
                    for i in range(3, 6)
                ],
            )
            self.assertEqual(batch_res["created_count"], 3)

            for note_id, expected_stt in zip(batch_res["note_ids"], ["3", "4", "5"]):
                note = Note.query.get(note_id)
                self.assertEqual(note.field_values.get("STT"), expected_stt)

    def test_batch_create_atomic_rollback_on_conflict(self):
        """If one item in a batch collides with an existing note, entire batch is rolled back atomically."""
        with self.app.app_context():
            # Existing note with STT 10
            mcp_tool_service.create_note(
                user_id=self.user_id,
                note_data={
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"STT": "10", "Vocabulary": "existing_ten"},
                },
            )
            initial_count = Note.query.filter_by(user_id=self.user_id, deck_id=self.deck_id).count()
            self.assertEqual(initial_count, 1)

            # Attempt batch where item 1 is new (STT 11) but item 2 collides (STT 10)
            batch = [
                {
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"STT": "11", "Vocabulary": "new_eleven"},
                },
                {
                    "deck_id": self.deck_id,
                    "note_type_id": self.note_type_id,
                    "fields": {"STT": "10", "Vocabulary": "colliding_ten"},
                },
            ]

            with self.assertRaises(RequestValidationError) as cm:
                mcp_tool_service.batch_create_notes(user_id=self.user_id, notes=batch)

            self.assertEqual(cm.exception.status, 409)

            # Verify rollback: Note count is STILL 1, STT 11 was NOT left orphaned
            after_count = Note.query.filter_by(user_id=self.user_id, deck_id=self.deck_id).count()
            self.assertEqual(after_count, 1)
            eleven = Note.query.filter_by(user_id=self.user_id, deck_id=self.deck_id).all()
            self.assertEqual(eleven[0].field_values.get("Vocabulary"), "existing_ten")


if __name__ == "__main__":
    unittest.main()
