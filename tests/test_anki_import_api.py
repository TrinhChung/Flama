from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest

from app import create_app
from models import db
from models.connect_import_session import ConnectImportSession
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


class AnkiImportApiTests(unittest.TestCase):
    def setUp(self):
        self.upload_tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": self.upload_tmp.name,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            admin = User(
                username="anki-import-admin",
                email="anki-import-admin@example.com",
                is_admin=True,
            )
            admin.set_password("password")
            regular = User(
                username="anki-import-user",
                email="anki-import-user@example.com",
                is_admin=False,
            )
            regular.set_password("password")
            db.session.add_all([admin, regular])
            db.session.flush()
            self.admin_id = admin.id

            note_type = NoteType(user_id=admin.id, name="Anki Vocabulary")
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
                        name="Meaning",
                        field_type="richtext",
                        position=1,
                    ),
                    Template(
                        note_type_id=note_type.id,
                        name="Card 1",
                        front_html="{{Word}}",
                        back_html="{{Meaning}}",
                    ),
                ]
            )
            deck = Deck(owner_user_id=admin.id, name="Inbox")
            db.session.add(deck)
            db.session.commit()
            self.deck_id = deck.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.upload_tmp.cleanup()

    def _login(self, email: str = "anki-import-admin@example.com") -> None:
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "password"},
        )
        self.assertEqual(response.status_code, 200, response.get_json())

    def _session_payload(self) -> dict:
        return {
            # The server must ignore this and force the authenticated Anki source.
            "source": "untrusted-browser-value",
            "sourceKey": f"{self.admin_id}:http://127.0.0.1:8765",
            "sourceRootPath": "Inbox",
            "targetRootPath": "Inbox",
            "selectedDecks": ["Inbox"],
            "decks": [
                {
                    "sourceDeckId": "anki-inbox",
                    "sourcePath": "Inbox",
                    "targetPath": "Inbox",
                }
            ],
            "totalNotes": 1,
            "totalMedia": 0,
            "mode": "strict",
            "noteTypes": [
                {
                    "sourceModelId": "anki-model-1",
                    "sourceModelName": "Anki Vocabulary",
                    "targetNoteTypeId": self.note_type_id,
                    "fields": [
                        {"name": "Word", "fieldType": "text"},
                        {"name": "Meaning", "fieldType": "richtext"},
                    ],
                    "templates": [
                        {
                            "name": "Card 1",
                            "frontHtml": "{{Word}}",
                            "backHtml": "{{Meaning}}",
                            "sharedCss": "",
                        }
                    ],
                    "fieldMapping": {"Word": "Word", "Meaning": "Meaning"},
                }
            ],
            "planHash": "a" * 64,
        }

    def _create_session(self) -> dict:
        response = self.client.post(
            "/api/flashcards/import/anki/sessions",
            json=self._session_payload(),
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_admin_can_create_upload_complete_and_read_session(self):
        self._login()
        capabilities = self.client.get("/api/flashcards/import/anki/capabilities")
        self.assertEqual(capabilities.status_code, 200)
        self.assertEqual(capabilities.get_json()["formatVersion"], 1)

        created = self._create_session()
        self.assertEqual(created["status"], "note_types_ready")
        session_id = created["importSessionId"]
        with self.app.app_context():
            stored = db.session.get(ConnectImportSession, session_id)
            self.assertEqual(stored.source, "anki")
            self.assertEqual(stored.user_id, self.admin_id)

        record = {
            "ankiNoteId": 101,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "b" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "猫", "Meaning": "cat"},
                "tags": ["anki"],
                "options": {
                    "allowDuplicate": False,
                    "duplicateScope": "collection",
                    "duplicateScopeOptions": {
                        "deckName": None,
                        "checkChildren": False,
                        "checkAllModels": False,
                    },
                },
            },
        }
        package = gzip.compress((json.dumps(record) + "\n").encode("utf-8"), mtime=0)
        uploaded = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id}/packages/cards/0",
            data=package,
            content_type="application/x-ndjson",
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(package).hexdigest(),
            },
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.get_json())
        self.assertTrue(uploaded.get_json()["results"][0]["imported"])

        completed = self.client.post(
            f"/api/flashcards/import/anki/sessions/{session_id}/complete",
            json={},
        )
        self.assertEqual(completed.status_code, 200, completed.get_json())
        self.assertEqual(completed.get_json()["status"], "completed")
        status = self.client.get(
            f"/api/flashcards/import/anki/sessions/{session_id}"
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["processedNotes"], 1)
        with self.app.app_context():
            self.assertEqual(
                Note.query.filter_by(user_id=self.admin_id, deck_id=self.deck_id).count(),
                1,
            )

    def test_routes_require_admin_session_and_are_owner_scoped(self):
        anonymous = self.client.get("/api/flashcards/import/anki/capabilities")
        self.assertIn(anonymous.status_code, {302, 401})

        self._login("anki-import-user@example.com")
        forbidden = self.client.get("/api/flashcards/import/anki/capabilities")
        self.assertEqual(forbidden.status_code, 403)

        self.client.delete("/api/session")
        self._login()
        created = self._create_session()
        session_id = created["importSessionId"]
        with self.app.app_context():
            stored = db.session.get(ConnectImportSession, session_id)
            stored.user_id = self.admin_id + 999
            db.session.commit()
        hidden = self.client.get(
            f"/api/flashcards/import/anki/sessions/{session_id}"
        )
        self.assertEqual(hidden.status_code, 404)

    def test_cancel_removes_session_from_importable_state(self):
        self._login()
        created = self._create_session()
        response = self.client.delete(
            f"/api/flashcards/import/anki/sessions/{created['importSessionId']}"
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
