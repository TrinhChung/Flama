from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app import create_app
from models import db
from models.connect_import_session import ConnectImportSession
from models.connect_review_event_ref import ConnectReviewEventRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.card_progress import CardProgress
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.media_asset import MediaAsset
from models.template import Template
from models.review_event import ReviewEvent
from models.user import User
from models.user_role import UserRole


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
            creator_role = UserRole.query.filter_by(code="creator").one()
            creator = User(
                username="anki-import-creator",
                email="anki-import-creator@example.com",
                role_id=creator_role.id,
                is_admin=False,
            )
            creator.set_password("password")
            db.session.add_all([admin, regular, creator])
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

    def test_creator_can_read_capabilities(self):
        self._login("anki-import-creator@example.com")
        response = self.client.get("/api/flashcards/import/anki/capabilities")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["cardBatchMaxItems"], 50)
        self.assertEqual(response.get_json()["cardPackageTargetItems"], 500)
        self.assertEqual(response.get_json()["cardPackageMaxItems"], 1000)
        self.assertEqual(response.get_json()["cardPackageMaxBytes"], 16 * 1024 * 1024)

    def _obsolete_duplicate_create_session(self) -> dict:
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

    def _obsolete_duplicate_owner_scope_without_assertion(self):
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

    def _create_session(self) -> dict:
        response = self.client.post(
            "/api/flashcards/import/anki/sessions",
            json=self._session_payload(),
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _obsolete_duplicate_admin_flow(self):
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

    def test_anki_progress_migration(self):
        self._login()
        created = self._create_session()
        session_id = created["importSessionId"]

        # Note with several card progresses
        record = {
            "ankiNoteId": 201,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "c" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "犬", "Meaning": "dog"},
                "tags": ["anki-progress"],
            },
            "cardsProgress": [
                {
                    "ord": 0,
                    "type": 2, # review card
                    "queue": 2,
                    "relativeDue": 3,
                    "interval": 14,
                    "factor": 2500,
                    "reps": 8,
                    "lapses": 1,
                    "lastReviewAt": "2026-08-13T12:00:00Z"
                }
            ]
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

        from models.card import Card
        from models.card_progress import CardProgress

        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.admin_id).filter(Note.tags.contains("anki-progress")).one()
            self.assertEqual(len(note.cards), 1)
            card = note.cards[0]

            progress = CardProgress.query.filter_by(user_id=self.admin_id, card_id=card.id).one()
            self.assertEqual(progress.queue, "review")
            self.assertEqual(progress.interval_days, 14)
            self.assertEqual(progress.ease_factor, 2.5)
            self.assertEqual(progress.reps, 8)
            self.assertEqual(progress.lapses, 1)
            self.assertIsNotNone(progress.due_day)
            self.assertIsNotNone(progress.due_at)
            self.assertEqual(progress.is_suspended, False)
            self.assertEqual(progress.is_buried, False)

        # Let's test conflict resolution:
        # 1. Update with older progress: Flama progress should NOT be overwritten (newest wins)
        record2 = {
            "ankiNoteId": 201,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            # We change contentHash to trigger reload
            "contentHash": "d" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "犬", "Meaning": "dog"},
                "tags": ["anki-progress"],
            },
            "cardsProgress": [
                {
                    "ord": 0,
                    "type": 2,
                    "queue": 2,
                    "relativeDue": 3,
                    "interval": 10, # older interval is different
                    "factor": 2200,
                    "reps": 5,
                    "lapses": 0,
                    "lastReviewAt": "2026-08-11T12:00:00Z" # older review date
                }
            ]
        }

        created2 = self._create_session()
        session_id2 = created2["importSessionId"]
        package2 = gzip.compress((json.dumps(record2) + "\n").encode("utf-8"), mtime=0)
        uploaded2 = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id2}/packages/cards/0",
            data=package2,
            content_type="application/x-ndjson",
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(package2).hexdigest(),
            },
        )
        self.assertEqual(uploaded2.status_code, 200, uploaded2.get_json())

        with self.app.app_context():
            progress = CardProgress.query.filter_by(user_id=self.admin_id, card_id=card.id).one()
            # It should keep the newer progress from the first package (interval = 14)
            self.assertEqual(progress.interval_days, 14)

        # 2. Update with newer progress: Flama progress should be overwritten
        record3 = {
            "ankiNoteId": 201,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "e" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "犬", "Meaning": "dog"},
                "tags": ["anki-progress"],
            },
            "cardsProgress": [
                {
                    "ord": 0,
                    "type": 2,
                    "queue": 2,
                    "relativeDue": 1,
                    "interval": 20,
                    "factor": 2600,
                    "reps": 12,
                    "lapses": 2,
                    "lastReviewAt": "2026-08-15T12:00:00Z" # newer review date
                }
            ]
        }

        created3 = self._create_session()
        session_id3 = created3["importSessionId"]
        package3 = gzip.compress((json.dumps(record3) + "\n").encode("utf-8"), mtime=0)
        uploaded3 = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id3}/packages/cards/0",
            data=package3,
            content_type="application/x-ndjson",
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(package3).hexdigest(),
            },
        )
        self.assertEqual(uploaded3.status_code, 200, uploaded3.get_json())

        with self.app.app_context():
            progress = CardProgress.query.filter_by(user_id=self.admin_id, card_id=card.id).one()
            # It should update to the newer progress (interval = 20)
            self.assertEqual(progress.interval_days, 20)
            self.assertEqual(progress.ease_factor, 2.6)
            self.assertEqual(progress.reps, 12)
            self.assertEqual(progress.lapses, 2)

    def test_anki_progress_migration_suspended_and_learning(self):
        self._login()
        created = self._create_session()
        session_id = created["importSessionId"]

        record = {
            "ankiNoteId": 301,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "f" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "鳥", "Meaning": "bird"},
                "tags": ["anki-progress-extra"],
            },
            "cardsProgress": [
                {
                    "ord": 0,
                    "type": 1, # learning card
                    "queue": -1, # suspended
                    "dueAt": "2026-08-13T15:30:00Z",
                    "interval": 0,
                    "factor": 2500,
                    "reps": 3,
                    "lapses": 0,
                    "lastReviewAt": "2026-08-13T15:20:00Z"
                }
            ]
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

        from models.card import Card
        from models.card_progress import CardProgress

        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.admin_id).filter(Note.tags.contains("anki-progress-extra")).one()
            card = note.cards[0]
            progress = CardProgress.query.filter_by(user_id=self.admin_id, card_id=card.id).one()
            self.assertEqual(progress.queue, "learning")
            self.assertEqual(progress.is_suspended, True)
            self.assertEqual(progress.is_buried, False)
            self.assertEqual(progress.interval_days, 0)
            self.assertEqual(progress.due_day, None)
            self.assertIsNotNone(progress.due_at)

    def test_cancel_removes_session_from_importable_state(self):
        self._login()
        created = self._create_session()
        response = self.client.delete(
            f"/api/flashcards/import/anki/sessions/{created['importSessionId']}"
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["status"], "cancelled")

    def test_complete_rejects_missing_card_records(self):
        self._login()
        created = self._create_session()
        response = self.client.post(
            f"/api/flashcards/import/anki/sessions/{created['importSessionId']}/complete",
            json={"expectedNotes": 1},
        )
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertIn("incomplete", response.get_json()["message"])

    def test_complete_records_attempted_but_invalid_notes_as_partial_failed(self):
        self._login()
        created = self._create_session()
        session_id = created["importSessionId"]
        record = {
            "ankiNoteId": 601,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "6" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "line one<br>line two", "Meaning": "invalid plain text"},
                "tags": [],
            },
        }
        package = gzip.compress((json.dumps(record) + "\n").encode(), mtime=0)
        uploaded = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id}/packages/cards/0",
            data=package,
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(package).hexdigest(),
            },
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.get_json())
        self.assertFalse(uploaded.get_json()["results"][0]["imported"])

        completed = self.client.post(
            f"/api/flashcards/import/anki/sessions/{session_id}/complete",
            json={"expectedNotes": 1},
        )
        self.assertEqual(completed.status_code, 200, completed.get_json())
        self.assertEqual(completed.get_json()["status"], "partial_failed")
        self.assertEqual(completed.get_json()["attemptedNotes"], 1)
        self.assertEqual(completed.get_json()["processedNotes"], 0)

    def test_distinct_anki_notes_may_share_the_primary_field(self):
        self._login()
        payload = self._session_payload()
        payload["totalNotes"] = 2
        created_response = self.client.post(
            "/api/flashcards/import/anki/sessions",
            json=payload,
        )
        self.assertEqual(created_response.status_code, 201, created_response.get_json())
        session_id = created_response.get_json()["importSessionId"]
        records = []
        for note_id, meaning in ((701, "first"), (702, "second")):
            records.append(
                {
                    "ankiNoteId": note_id,
                    "sourceModelId": "anki-model-1",
                    "sourceDeckId": "anki-inbox",
                    "sourceDeckPath": "Inbox",
                    "contentHash": str(note_id % 10) * 64,
                    "note": {
                        "deckName": "Inbox",
                        "modelName": self.note_type_id,
                        "fields": {"Word": "same", "Meaning": meaning},
                        "tags": ["duplicate-primary"],
                    },
                }
            )
        package = gzip.compress(
            "".join(json.dumps(record) + "\n" for record in records).encode("utf-8"),
            mtime=0,
        )
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
        self.assertTrue(all(item["imported"] for item in uploaded.get_json()["results"]))
        with self.app.app_context():
            notes = Note.query.filter_by(user_id=self.admin_id, deck_id=self.deck_id).all()
            self.assertEqual(len(notes), 2)
            self.assertEqual(
                {note.field_values["Meaning"] for note in notes},
                {"first", "second"},
            )

    def test_one_card_package_can_cross_the_internal_fifty_note_chunk(self):
        self._login()
        payload = self._session_payload()
        payload["totalNotes"] = 51
        created = self.client.post(
            "/api/flashcards/import/anki/sessions",
            json=payload,
        )
        self.assertEqual(created.status_code, 201, created.get_json())
        session_id = created.get_json()["importSessionId"]
        records = [
            {
                "ankiNoteId": 10_000 + index,
                "sourceModelId": "anki-model-1",
                "sourceDeckId": "anki-inbox",
                "sourceDeckPath": "Inbox",
                "contentHash": f"{index + 1:064x}",
                "note": {
                    "deckName": "Inbox",
                    "modelName": self.note_type_id,
                    "fields": {
                        "Word": f"bulk-{index}",
                        "Meaning": f"meaning-{index}",
                    },
                    "tags": ["bulk"],
                },
            }
            for index in range(51)
        ]
        package = gzip.compress(
            "".join(json.dumps(record) + "\n" for record in records).encode("utf-8"),
            mtime=0,
        )
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
        self.assertEqual(uploaded.get_json()["itemCount"], 51)
        self.assertTrue(all(item["imported"] for item in uploaded.get_json()["results"]))

    def test_card_package_disk_failure_rolls_back_imported_notes(self):
        self._login()
        created = self._create_session()
        session_id = created["importSessionId"]
        record = {
            "ankiNoteId": 801,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "8" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "atomic", "Meaning": "rollback"},
                "tags": [],
            },
        }
        package = gzip.compress((json.dumps(record) + "\n").encode("utf-8"), mtime=0)
        with patch("pathlib.Path.write_bytes", side_effect=OSError("disk full")):
            uploaded = self.client.put(
                f"/api/flashcards/import/anki/sessions/{session_id}/packages/cards/0",
                data=package,
                content_type="application/x-ndjson",
                headers={
                    "Content-Encoding": "gzip",
                    "X-Package-SHA256": hashlib.sha256(package).hexdigest(),
                },
            )
        self.assertEqual(uploaded.status_code, 500)
        with self.app.app_context():
            self.assertEqual(
                Note.query.filter_by(user_id=self.admin_id, deck_id=self.deck_id).count(),
                0,
            )

    def test_note_status_uses_server_source_refs_as_the_incremental_authority(self):
        self._login()
        first = self._create_session()
        record = {
            "ankiNoteId": 901,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "9" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "incremental", "Meaning": "server-backed"},
                "tags": [],
            },
        }
        package = gzip.compress((json.dumps(record) + "\n").encode("utf-8"), mtime=0)
        uploaded = self.client.put(
            f"/api/flashcards/import/anki/sessions/{first['importSessionId']}/packages/cards/0",
            data=package,
            content_type="application/x-ndjson",
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(package).hexdigest(),
            },
        )
        self.assertEqual(uploaded.status_code, 200, uploaded.get_json())

        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.admin_id).one()
            db.session.add(
                MediaAsset(
                    note_id=note.id,
                    field_name="Meaning",
                    filename="known.png",
                    mime_type="image/png",
                    storage_path="test/known.png",
                    sha256="c" * 64,
                    size_bytes=10,
                )
            )
            db.session.commit()

        second = self._create_session()
        response = self.client.post(
            f"/api/flashcards/import/anki/sessions/{second['importSessionId']}/note-status",
            json={
                "notes": [
                    {"ankiNoteId": 901, "contentHash": "9" * 64},
                    {"ankiNoteId": 902, "contentHash": "a" * 64},
                ]
            },
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        states = {item["ankiNoteId"]: item["state"] for item in response.get_json()["notes"]}
        self.assertEqual(states, {901: "unchanged", 902: "new"})
        existing = next(item for item in response.get_json()["notes"] if item["ankiNoteId"] == 901)
        self.assertEqual(existing["mediaHashes"], ["c" * 64])

        changed = self.client.post(
            f"/api/flashcards/import/anki/sessions/{second['importSessionId']}/note-status",
            json={"notes": [{"ankiNoteId": 901, "contentHash": "b" * 64}]},
        )
        self.assertEqual(changed.status_code, 200, changed.get_json())
        self.assertEqual(changed.get_json()["notes"][0]["state"], "changed")

    def test_progress_and_full_revlog_are_separate_idempotent_sync_streams(self):
        from app.services.stats_overview import build_stats_overview

        self._login()
        created = self._create_session()
        session_id = created["importSessionId"]
        note_record = {
            "ankiNoteId": 1001,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "1" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "履歴", "Meaning": "history"},
                "tags": ["anki"],
            },
        }
        note_package = gzip.compress((json.dumps(note_record) + "\n").encode(), mtime=0)
        response = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id}/packages/cards/0",
            data=note_package,
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(note_package).hexdigest(),
            },
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        replay_note = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id}/packages/cards/0",
            data=note_package,
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(note_package).hexdigest(),
            },
        )
        self.assertEqual(replay_note.status_code, 200, replay_note.get_json())
        self.assertTrue(replay_note.get_json()["replayed"])
        self.assertTrue(replay_note.get_json()["results"][0]["imported"])

        progress_record = {
            "externalNoteId": 1001,
            "sourceCardId": 2001,
            "ord": 0,
            "snapshotHash": "2" * 64,
            "type": 2,
            "queue": 2,
            "due": 50003,
            "sourceToday": 50000,
            "interval": 14,
            "factor": 2500,
            "reps": 2,
            "lapses": 1,
            "left": 0,
            "mod": 1,
        }
        progress_package = gzip.compress((json.dumps(progress_record) + "\n").encode(), mtime=0)
        response = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id}/packages/progress/0",
            data=progress_package,
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(progress_package).hexdigest(),
            },
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["results"][0]["state"], "applied")

        first_ms = int(datetime(2026, 8, 12, 10, tzinfo=timezone.utc).timestamp() * 1000)
        second_ms = int(datetime(2026, 8, 13, 11, tzinfo=timezone.utc).timestamp() * 1000)
        reviews = [
            {"sourceReviewId": first_ms, "sourceCardId": 2001, "ease": 3, "type": 1, "ivl": 10, "lastIvl": 5, "factor": 2500, "time": 1200},
            {"sourceReviewId": second_ms, "sourceCardId": 2001, "ease": 2, "type": 1, "ivl": 14, "lastIvl": 10, "factor": 2450, "time": 2300},
        ]
        review_package = gzip.compress(
            ("\n".join(json.dumps(item) for item in reviews) + "\n").encode(),
            mtime=0,
        )
        review_url = f"/api/flashcards/import/anki/sessions/{session_id}/packages/reviews/0"
        headers = {
            "Content-Encoding": "gzip",
            "X-Package-SHA256": hashlib.sha256(review_package).hexdigest(),
        }
        response = self.client.put(review_url, data=review_package, headers=headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual([item["state"] for item in response.get_json()["results"]], ["imported", "imported"])
        replay = self.client.put(review_url, data=review_package, headers=headers)
        self.assertEqual(replay.status_code, 200, replay.get_json())
        self.assertTrue(replay.get_json()["replayed"])

        third_ms = second_ms + 1000
        mixed = [
            {**reviews[0], "sourceReviewId": first_ms - 1000, "sourceCardId": 999999},
            {**reviews[1], "sourceReviewId": third_ms},
        ]
        mixed_package = gzip.compress(
            ("\n".join(json.dumps(item) for item in mixed) + "\n").encode(),
            mtime=0,
        )
        mixed_response = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id}/packages/reviews/1",
            data=mixed_package,
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(mixed_package).hexdigest(),
            },
        )
        self.assertEqual(mixed_response.status_code, 200, mixed_response.get_json())
        self.assertEqual(mixed_response.get_json()["status"], "partial_failed")
        mixed_states = {item.get("sourceCardId"): item["state"] for item in mixed_response.get_json()["results"]}
        self.assertEqual(mixed_states[str(999999)], "failed")
        self.assertEqual(mixed_states[2001], "imported")

        conflicting = [
            {**reviews[0], "time": 9999},
            {**reviews[1], "sourceReviewId": third_ms + 1000},
        ]
        conflicting_package = gzip.compress(
            ("\n".join(json.dumps(item) for item in conflicting) + "\n").encode(),
            mtime=0,
        )
        conflict = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id}/packages/reviews/2",
            data=conflicting_package,
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(conflicting_package).hexdigest(),
            },
        )
        self.assertEqual(conflict.status_code, 200, conflict.get_json())
        self.assertEqual(conflict.get_json()["status"], "partial_failed")
        self.assertTrue(conflict.get_json()["results"][0]["cardAtomic"])

        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.filter_by(user_id=self.admin_id).count(), 3)
            self.assertEqual(ConnectReviewEventRef.query.filter_by(user_id=self.admin_id).count(), 3)
            source_card = ConnectSourceCardRef.query.filter_by(user_id=self.admin_id).one()
            self.assertEqual(source_card.review_cursor, third_ms)
            progress = CardProgress.query.filter_by(user_id=self.admin_id).one()
            self.assertEqual(progress.reps, 2)
            overview = build_stats_overview(
                user_id=self.admin_id,
                year=2026,
                timezone_name="UTC",
                now_utc=datetime(2026, 8, 14, 12),
            )
            points = {point["day"]: point for point in overview["heatmap"]}
            self.assertEqual(points["2026-08-12"]["cards"], 1)
            self.assertEqual(points["2026-08-13"]["cards"], 2)
            self.assertEqual(points["2026-08-12"]["study_time"], 1200)

        status = self.client.post(
            f"/api/flashcards/import/anki/sessions/{session_id}/note-status",
            json={"notes": [{
                "ankiNoteId": 1001,
                "contentHash": "1" * 64,
                "cards": [{"sourceCardId": 2001, "snapshotHash": "2" * 64}],
            }]},
        )
        self.assertEqual(status.status_code, 200, status.get_json())
        card_status = status.get_json()["notes"][0]["cards"][0]
        self.assertEqual(card_status["progressState"], "unchanged")
        self.assertEqual(card_status["reviewCursor"], str(third_ms))

        # Provenance is the durable identity. If an older purge removed the
        # analytics projection, note-status must invalidate the cursor so a
        # normal incremental sync can replay and repair the missing event.
        with self.app.app_context():
            first_ref = ConnectReviewEventRef.query.filter_by(
                user_id=self.admin_id,
                external_review_id=str(first_ms),
            ).one()
            first_event = db.session.get(ReviewEvent, first_ref.review_event_id)
            first_ref.review_event_id = None
            db.session.delete(first_event)
            db.session.commit()

        orphan_status = self.client.post(
            f"/api/flashcards/import/anki/sessions/{session_id}/note-status",
            json={"notes": [{
                "ankiNoteId": 1001,
                "contentHash": "1" * 64,
                "cards": [{"sourceCardId": 2001, "snapshotHash": "2" * 64}],
            }]},
        )
        self.assertEqual(orphan_status.status_code, 200, orphan_status.get_json())
        self.assertIsNone(orphan_status.get_json()["notes"][0]["cards"][0]["reviewCursor"])

        repair = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id}/packages/reviews/3",
            data=review_package,
            headers=headers,
        )
        self.assertEqual(repair.status_code, 200, repair.get_json())
        self.assertEqual(
            [item["state"] for item in repair.get_json()["results"]],
            ["repaired", "unchanged"],
        )
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.filter_by(user_id=self.admin_id).count(), 3)
            self.assertEqual(
                ConnectReviewEventRef.query.filter_by(user_id=self.admin_id)
                .filter(ConnectReviewEventRef.review_event_id.isnot(None))
                .count(),
                3,
            )

        repaired_status = self.client.post(
            f"/api/flashcards/import/anki/sessions/{session_id}/note-status",
            json={"notes": [{
                "ankiNoteId": 1001,
                "contentHash": "1" * 64,
                "cards": [{"sourceCardId": 2001, "snapshotHash": "2" * 64}],
            }]},
        )
        self.assertEqual(repaired_status.status_code, 200, repaired_status.get_json())
        self.assertEqual(
            repaired_status.get_json()["notes"][0]["cards"][0]["reviewCursor"],
            str(third_ms),
        )

if __name__ == "__main__":
    unittest.main()
