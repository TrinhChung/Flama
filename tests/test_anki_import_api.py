from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app
from app.services.study_authority_enrollment_service import (
    stage_note_authority_enrollment,
)
from app.services.connect.import_session import prepare_import_batch_context
from models import db
from models.card import Card
from models.connect_import_session import ConnectImportSession
from models.connect_review_event_ref import ConnectReviewEventRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.media_asset import MediaAsset
from models.template import Template
from models.review_event import ReviewEvent
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_subject import StudyProgressSubject
from models.user import User
from tests.study_note_fixtures import create_note_user, attach_template, assert_retired_progress_absent
from tests.note_progress_fixtures import stage_note_state, subject_for_card, decode_note_state
from models.study_progress_subject import StudyProgressSubject
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
            admin = create_note_user(db.session,
                username="anki-import-admin",
                email="anki-import-admin@example.com",
                is_admin=True,
            )
            admin.set_password("password")
            regular = create_note_user(db.session,
                username="anki-import-user",
                email="anki-import-user@example.com",
                is_admin=False,
            )
            regular.set_password("password")
            creator_role = UserRole.query.filter_by(code="creator").one()
            creator = create_note_user(db.session,
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
                    attach_template(db.session, owner_user_id=db.session.get(NoteType, note_type.id).user_id,
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

    def _upload_package(
        self,
        session_id: str,
        kind: str,
        sequence: int,
        records: list[dict],
    ) -> dict:
        package = gzip.compress(
            ("\n".join(json.dumps(record) for record in records) + "\n").encode(),
            mtime=0,
        )
        response = self.client.put(
            f"/api/flashcards/import/anki/sessions/{session_id}/packages/{kind}/{sequence}",
            data=package,
            headers={
                "Content-Encoding": "gzip",
                "X-Package-SHA256": hashlib.sha256(package).hexdigest(),
            },
        )
        self.assertEqual(response.status_code, 200, response.get_json())
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

    def test_routes_require_login_session_and_are_owner_scoped(self):
        anonymous = self.client.get("/api/flashcards/import/anki/capabilities")
        self.assertIn(anonymous.status_code, {302, 401})

        self._login("anki-import-user@example.com")
        allowed = self.client.get("/api/flashcards/import/anki/capabilities")
        self.assertEqual(allowed.status_code, 200)

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

    def test_note_status_with_unimported_new_cards_returns_new_state(self):
        self._login()
        session = self._create_session()
        response = self.client.post(
            f"/api/flashcards/import/anki/sessions/{session['importSessionId']}/note-status",
            json={
                "notes": [
                    {
                        "ankiNoteId": 9991,
                        "contentHash": "e" * 64,
                        "cards": [
                            {"sourceCardId": 8881, "snapshotHash": "f" * 64},
                        ],
                    }
                ]
            },
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        card_data = response.get_json()["notes"][0]["cards"][0]
        self.assertEqual(card_data["sourceCardId"], "8881")
        self.assertEqual(card_data["progressState"], "new")
        self.assertIsNone(card_data["serverSnapshotHash"])
        self.assertIsNone(card_data["reviewCursor"])

    def test_note_authority_progress_snapshot_projects_all_siblings_atomically(self):
        self._login()
        session_id = self._create_session()["importSessionId"]
        note_record = {
            "ankiNoteId": 3101,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "3" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "authority", "Meaning": "snapshot"},
                "tags": ["note-authority-snapshot"],
            },
        }
        card_result = self._upload_package(session_id, "cards", 0, [note_record])
        self.assertTrue(card_result["results"][0]["imported"])

        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.admin_id).one()
            sibling_template = attach_template(db.session, owner_user_id=db.session.get(NoteType, note.note_type_id).user_id,
                note_type_id=note.note_type_id,
                name="Authority sibling",
                front_html="{{Meaning}}",
                back_html="{{Word}}",
                position=1,
            )
            db.session.add(sibling_template)
            # The sibling's occurrence presents the Note (ADR P11): no Card row.
            db.session.flush()
            enrollment = stage_note_authority_enrollment(
                db.session,
                learner_user_id=self.admin_id,
                now_utc=datetime(2026, 9, 23, 9, 0, 0),
            )
            self.assertEqual((enrollment.subject_count, enrollment.card_count), (0, 0))
            self.assertEqual(Card.query.count(), 2)
            db.session.commit()

        snapshot_a = {
            "externalNoteId": 3101,
            "sourceCardId": 4101,
            "ord": 0,
            "snapshotHash": "a" * 64,
            "baseSnapshotHash": None,
            "type": 2,
            "queue": 2,
            "due": 50003,
            "sourceToday": 50000,
            "interval": 14,
            "factor": 2500,
            "reps": 2,
            "lapses": 1,
            "left": 0,
        }
        first = self._upload_package(session_id, "progress", 0, [snapshot_a])["results"][0]
        self.assertEqual((first["state"], first["code"]), ("applied", "PROGRESS_APPLIED"))
        with self.app.app_context():
            # ADR P10: the Note's one row holds the snapshot; no Card carries progress.
            assert_retired_progress_absent(self, db.session)
            subject = StudyProgressSubject.query.one()
            self.assertEqual((subject.subject_generation, int(subject.authority_revision)), (1, 1))
            self.assertEqual(subject.state_payload["scheduler_mode"], "anki")
            self.assertEqual(subject.normalized_queue, "review")
            self.assertEqual(subject.current_provenance_code, "CONNECT_PROGRESS_SNAPSHOT")
            self.assertEqual(subject.history_completeness_code, "HISTORY_MIXED_PARTIAL")

        semantic_replay = self._upload_package(
            session_id,
            "progress",
            1,
            [
                {
                    **snapshot_a,
                    "snapshotHash": "e" * 64,
                    "baseSnapshotHash": "a" * 64,
                }
            ],
        )["results"][0]
        self.assertEqual(
            (semantic_replay["state"], semantic_replay["code"]),
            ("applied", "PROGRESS_APPLIED"),
        )
        with self.app.app_context():
            self.assertEqual(int(StudyProgressSubject.query.one().authority_revision), 1)
            source_a = ConnectSourceCardRef.query.filter_by(
                user_id=self.admin_id,
                external_card_id="4101",
            ).one()
            self.assertEqual(source_a.snapshot_hash, "e" * 64)

        snapshot_b = {
            **snapshot_a,
            "sourceCardId": 4102,
            "ord": 1,
            "snapshotHash": "b" * 64,
            "interval": 20,
        }
        second = self._upload_package(session_id, "progress", 2, [snapshot_b])["results"][0]
        self.assertEqual((second["state"], second["code"]), ("applied", "PROGRESS_APPLIED"))
        with self.app.app_context():
            subject = StudyProgressSubject.query.one()
            self.assertEqual(int(subject.authority_revision), 2)
            refs = ConnectSourceCardRef.query.filter_by(user_id=self.admin_id).all()
            self.assertEqual(len(refs), 2)
            # Both siblings' refs are fenced on the Note's revision.
            self.assertEqual({int(row.applied_authority_revision) for row in refs}, {2})

        with patch(
            "app.services.study_consolidated_progress_service.finalize_consolidated_external",
            side_effect=RuntimeError("NOTE external snapshot fault injection"),
        ):
            failed = self._upload_package(
                session_id,
                "progress",
                3,
                [
                    {
                        **snapshot_a,
                        "snapshotHash": "c" * 64,
                        "baseSnapshotHash": "e" * 64,
                        "interval": 30,
                    }
                ],
            )["results"][0]
        self.assertEqual(failed["code"], "PROGRESS_IMPORT_FAILED")
        with self.app.app_context():
            source_a = ConnectSourceCardRef.query.filter_by(
                user_id=self.admin_id,
                external_card_id="4101",
            ).one()
            self.assertEqual(source_a.snapshot_hash, "e" * 64)
            self.assertEqual(int(StudyProgressSubject.query.one().authority_revision), 2)

            from app.services import study_service

            reviewed_card = db.session.get(Card, source_a.card_id)
            study_service.execute_native_review_command(
                user=db.session.get(User, self.admin_id),
                card=reviewed_card,
                action="good",
                payload={"duration_ms": 100},
                clone_scope=None,
                requested_scope_id=int(reviewed_card.note.deck_id),
                timezone_name="UTC",
                now=datetime(2026, 9, 23, 10, 0, 0),
            )
            post_review_revision = int(StudyProgressSubject.query.one().authority_revision)

        local_conflict = self._upload_package(
            session_id,
            "progress",
            4,
            [
                {
                    **snapshot_a,
                    "snapshotHash": "d" * 64,
                    "baseSnapshotHash": "e" * 64,
                    "interval": 40,
                }
            ],
        )["results"][0]
        self.assertEqual(local_conflict["code"], "LOCAL_PROGRESS_CHANGED")
        with self.app.app_context():
            self.assertEqual(
                int(StudyProgressSubject.query.one().authority_revision),
                post_review_revision,
            )

        status_payload = {"notes": [{
            "ankiNoteId": 3101,
            "contentHash": "3" * 64,
            "cards": [{"sourceCardId": 4101, "snapshotHash": "e" * 64}],
        }]}
        healthy_status = self.client.post(
            f"/api/flashcards/import/anki/sessions/{session_id}/note-status",
            json=status_payload,
        )
        self.assertEqual(healthy_status.status_code, 200, healthy_status.get_json())
        self.assertEqual(
            healthy_status.get_json()["notes"][0]["cards"][0]["progressState"],
            "local_changed",
        )

        # A row whose availability disagrees with its state must still
        # invalidate the NOTE cursor before incremental sync.
        with self.app.app_context():
            subject = StudyProgressSubject.query.one()
            subject.normalized_queue = "new" if subject.normalized_queue != "new" else "review"
            db.session.commit()
        divergent_status = self.client.post(
            f"/api/flashcards/import/anki/sessions/{session_id}/note-status",
            json=status_payload,
        )
        self.assertEqual(divergent_status.status_code, 409, divergent_status.get_json())
        self.assertEqual(
            divergent_status.get_json()["error"], "AUTHORITY_READ_PARITY_DIVERGED"
        )

    def test_note_authority_revlog_is_history_only_and_card_atomic(self):
        self._login()
        session_id = self._create_session()["importSessionId"]
        note_record = {
            "ankiNoteId": 3201,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "4" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "authority", "Meaning": "revlog"},
                "tags": ["note-authority-revlog"],
            },
        }
        card_result = self._upload_package(session_id, "cards", 0, [note_record])
        self.assertTrue(card_result["results"][0]["imported"])
        with self.app.app_context():
            enrollment = stage_note_authority_enrollment(
                db.session,
                learner_user_id=self.admin_id,
                now_utc=datetime(2026, 9, 22, 8, 0, 0),
            )
            self.assertEqual((enrollment.subject_count, enrollment.card_count), (0, 0))
            self.assertEqual(Card.query.count(), 1)
            db.session.commit()

        snapshot = {
            "externalNoteId": 3201,
            "sourceCardId": 4201,
            "ord": 0,
            "snapshotHash": "f" * 64,
            "baseSnapshotHash": None,
            "type": 2,
            "queue": 2,
            "due": 50003,
            "sourceToday": 50000,
            "interval": 14,
            "factor": 2500,
            "reps": 2,
            "lapses": 1,
            "left": 0,
        }
        progress_result = self._upload_package(
            session_id,
            "progress",
            0,
            [snapshot],
        )["results"][0]
        self.assertEqual(progress_result["code"], "PROGRESS_APPLIED")
        with self.app.app_context():
            subject = StudyProgressSubject.query.one()
            baseline = {
                "authority_revision": int(subject.authority_revision),
                "semantic_hash": bytes(subject.semantic_state_hash),
                "state_payload": dict(subject.state_payload),
                "due_day": subject.due_day,
            }

        first_ms = int(datetime(2026, 9, 22, 9, tzinfo=timezone.utc).timestamp() * 1000)
        second_ms = int(datetime(2026, 9, 22, 10, tzinfo=timezone.utc).timestamp() * 1000)
        reviews = [
            {
                "sourceReviewId": first_ms,
                "sourceCardId": 4201,
                "ease": 3,
                "type": 1,
                "ivl": 10,
                "lastIvl": 5,
                "factor": 2500,
                "time": 1200,
            },
            {
                "sourceReviewId": second_ms,
                "sourceCardId": 4201,
                "ease": 2,
                "type": 1,
                "ivl": 14,
                "lastIvl": 10,
                "factor": 2450,
                "time": 2300,
            },
        ]
        imported = self._upload_package(session_id, "reviews", 0, reviews)
        self.assertEqual(
            [row["state"] for row in imported["results"]],
            ["imported", "imported"],
        )
        with self.app.app_context():
            # Imported revlog is history only: the row's state is unchanged.
            subject = StudyProgressSubject.query.one()
            self.assertEqual(int(subject.authority_revision), baseline["authority_revision"])
            self.assertEqual(bytes(subject.semantic_state_hash), baseline["semantic_hash"])
            self.assertEqual(dict(subject.state_payload), baseline["state_payload"])
            self.assertEqual(subject.due_day, baseline["due_day"])
            self.assertEqual(ReviewEvent.query.count(), 2)
            self.assertEqual(ConnectReviewEventRef.query.count(), 2)
            self.assertEqual(StudyProgressHistoryFact.query.count(), 2)
            self.assertEqual(
                {row.provenance_code for row in StudyProgressHistoryFact.query.all()},
                {"CONNECT_REVLOG"},
            )
            self.assertEqual(
                {row.contributor_id for row in StudyProgressHistoryFact.query.all()}, {None})
            self.assertEqual(subject.history_completeness_code, "HISTORY_MIXED_PARTIAL")
            self.assertEqual(
                ConnectSourceCardRef.query.one().review_cursor,
                second_ms,
            )

        replay = self._upload_package(session_id, "reviews", 1, reviews)
        self.assertEqual(
            [row["state"] for row in replay["results"]],
            ["unchanged", "unchanged"],
        )
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 2)
            self.assertEqual(StudyProgressHistoryFact.query.count(), 2)

        fault_review = [
            {
                **reviews[1],
                "sourceReviewId": second_ms + 1000,
            }
        ]
        with patch(
            "app.services.study_consolidated_progress_service.append_consolidated_external_history",
            side_effect=RuntimeError("NOTE revlog fault injection"),
        ):
            failed = self._upload_package(
                session_id,
                "reviews",
                2,
                fault_review,
            )["results"][0]
        self.assertEqual((failed["state"], failed["cardAtomic"]), ("failed", True))
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.count(), 2)
            self.assertEqual(ConnectReviewEventRef.query.count(), 2)
            self.assertEqual(StudyProgressHistoryFact.query.count(), 2)
            self.assertEqual(ConnectSourceCardRef.query.one().review_cursor, second_ms)
            self.assertEqual(
                int(StudyProgressSubject.query.one().authority_revision),
                baseline["authority_revision"],
            )

    def test_card_import_batch_context_fences_learner_before_deck_lookup(self):
        order = []

        def record_fence(*_args, **kwargs):
            self.assertEqual(kwargs["learner_user_id"], self.admin_id)
            self.assertTrue(kwargs["allow_note_authority"])
            order.append("learner")

        def record_decks(_user_id):
            order.append("decks")
            return []

        with self.app.app_context(), patch(
            "app.services.connect.import_session.lock_study_authority_route",
            side_effect=record_fence,
        ), patch(
            "app.services.connect.import_session._accessible_note_types",
            return_value=[],
        ), patch(
            "app.services.connect.import_session._owned_decks",
            side_effect=record_decks,
        ):
            prepare_import_batch_context(
                user_id=self.admin_id,
                session=SimpleNamespace(note_type_bindings={}),
                cards=[],
            )
        self.assertEqual(order, ["learner", "decks"])

    def test_note_authority_import_session_relocates_existing_deck_like_legacy(self):
        self._login()
        self._create_session()
        with self.app.app_context():
            stage_note_authority_enrollment(
                db.session,
                learner_user_id=self.admin_id,
                now_utc=datetime(2026, 9, 23, 3, 0, 0),
            )
            db.session.commit()
        payload = self._session_payload()
        payload["selectedDecks"] = ["Renamed"]
        payload["decks"][0]["targetPath"] = "Renamed"
        response = self.client.post(
            "/api/flashcards/import/anki/sessions", json=payload
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        with self.app.app_context():
            self.assertEqual(db.session.get(Deck, self.deck_id).name, "Renamed")

    def test_note_authority_card_import_updates_content_and_snapshot_starts_state(self):
        self._login()
        initial_session_id = self._create_session()["importSessionId"]
        original = {
            "ankiNoteId": 3301,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "5" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "before", "Meaning": "authority"},
                "tags": ["before-enrollment"],
            },
        }
        self.assertTrue(
            self._upload_package(initial_session_id, "cards", 0, [original])["results"][0]["imported"]
        )
        with self.app.app_context():
            stage_note_authority_enrollment(
                db.session,
                learner_user_id=self.admin_id,
                now_utc=datetime(2026, 9, 22, 12, 0, 0),
            )
            db.session.commit()
            revisions = {
                row.id: row.authority_revision
                for row in StudyProgressSubject.query.all()
            }

        session_id = self._create_session()["importSessionId"]
        imported = self._upload_package(
            session_id,
            "cards",
            0,
            [
                {
                    **original,
                    "contentHash": "6" * 64,
                    "note": {
                        **original["note"],
                        "fields": {"Word": "after", "Meaning": "updated"},
                        "tags": ["after-enrollment"],
                    },
                },
                {
                    **original,
                    "ankiNoteId": 3302,
                    "contentHash": "7" * 64,
                    "note": {**original["note"], "fields": {"Word": "new", "Meaning": "pristine"}},
                    "cardsProgress": [{"ord": 0, "type": 2, "queue": 2, "interval": 3,
                        "factor": 2500, "reps": 1, "lapses": 0}],
                },
            ],
        )
        self.assertEqual([row["imported"] for row in imported["results"]], [True, True])
        # Per-Card legacy progress is not applied under NOTE; it is typed.
        self.assertEqual(
            imported["results"][1]["progressResults"],
            [{"ord": 0, "state": "unsupported", "code": "NOTE_SNAPSHOT_REQUIRED"}],
        )
        with self.app.app_context():
            updated = ConnectSourceNoteRef.query.filter_by(
                user_id=self.admin_id, external_note_id="3301").one()
            self.assertEqual(db.session.get(Note, updated.note_id).field_values,
                {"Word": "after", "Meaning": "updated"})
            self.assertEqual(
                {
                    row.id: row.authority_revision
                    for row in StudyProgressSubject.query.all()
                    if row.id in revisions
                },
                revisions,
            )
            new_note_id = ConnectSourceNoteRef.query.filter_by(
                user_id=self.admin_id, external_note_id="3302").one().note_id
            new_card_ids = [card.id for card in Card.query.filter_by(note_id=new_note_id)]
            assert_retired_progress_absent(self, db.session)

        snapshot = {
            "externalNoteId": 3302,
            "sourceCardId": 4302,
            "ord": 0,
            "snapshotHash": "a" * 64,
            "baseSnapshotHash": None,
            "type": 2,
            "queue": 2,
            "due": 50003,
            "sourceToday": 50000,
            "interval": 14,
            "factor": 2500,
            "reps": 2,
            "lapses": 1,
            "left": 0,
        }
        applied = self._upload_package(session_id, "progress", 0, [snapshot])["results"][0]
        self.assertEqual((applied["state"], applied["code"]), ("applied", "PROGRESS_APPLIED"))
        with self.app.app_context():
            subject = StudyProgressSubject.query.filter_by(
                learner_user_id=self.admin_id, live_note_id=new_note_id).one()
            self.assertEqual(int(subject.authority_revision), 1)
            self.assertEqual(subject.state_payload["scheduler_mode"], "anki")
            self.assertEqual(subject.normalized_queue, "review")
            assert_retired_progress_absent(self, db.session)

    def test_progress_snapshot_conflict_and_idempotency_contract(self):
        self._login()
        session_id = self._create_session()["importSessionId"]
        note_record = {
            "ankiNoteId": 3001,
            "sourceModelId": "anki-model-1",
            "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox",
            "contentHash": "3" * 64,
            "note": {
                "deckName": "Inbox",
                "modelName": self.note_type_id,
                "fields": {"Word": "snapshot", "Meaning": "contract"},
                "tags": ["anki-snapshot-contract"],
            },
        }
        card_result = self._upload_package(session_id, "cards", 0, [note_record])
        self.assertTrue(card_result["results"][0]["imported"])

        snapshot_a = {
            "externalNoteId": 3001,
            "sourceCardId": 4001,
            "ord": 0,
            "snapshotHash": "a" * 64,
            "baseSnapshotHash": None,
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
        applied = self._upload_package(session_id, "progress", 0, [snapshot_a])["results"][0]
        self.assertEqual(applied["code"], "PROGRESS_APPLIED", applied)
        self.assertEqual(applied["serverSnapshotHash"], "a" * 64)
        self.assertNotIn("legacy_unversioned", applied)
        with self.app.app_context():
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            self.assertEqual(int(progress.authority_revision or 0), 1)
            self.assertEqual(decode_note_state(progress).schedulerMode, "anki")
            # Current snapshots update the one NOTE row; the frozen table is absent.
            self.assertEqual(StudyProgressSubject.query.count(), 1)

        unchanged = self._upload_package(
            session_id,
            "progress",
            1,
            [{**snapshot_a, "baseSnapshotHash": "a" * 64}],
        )["results"][0]
        self.assertEqual(unchanged["code"], "PROGRESS_UNCHANGED")
        self.assertEqual(unchanged["serverSnapshotHash"], "a" * 64)
        with self.app.app_context():
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            self.assertEqual(int(progress.authority_revision or 0), 1)
            stage_note_state(db.session, user_id=progress.learner_user_id, note_id=progress.live_note_id,
                             queue=progress.normalized_queue, due_day=progress.due_day, due_at=progress.due_at,
                             interval_days=99, scheduler_mode="anki", revision=2)
            db.session.commit()

        snapshot_b = {
            **snapshot_a,
            "snapshotHash": "b" * 64,
            "baseSnapshotHash": "a" * 64,
            "interval": 20,
        }
        local_conflict = self._upload_package(
            session_id,
            "progress",
            2,
            [snapshot_b],
        )["results"][0]
        self.assertEqual(local_conflict["code"], "LOCAL_PROGRESS_CHANGED")
        self.assertEqual(local_conflict["serverSnapshotHash"], "a" * 64)
        with self.app.app_context():
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            self.assertEqual((decode_note_state(progress).intervalDays, int(progress.authority_revision or 0)), (99, 2))

        forced = self._upload_package(
            session_id,
            "progress",
            3,
            [{**snapshot_b, "force": True}],
        )["results"][0]
        self.assertEqual(forced["code"], "FORCED_PROGRESS_APPLIED")
        self.assertEqual(forced["serverSnapshotHash"], "b" * 64)
        with self.app.app_context():
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            self.assertEqual((decode_note_state(progress).intervalDays, int(progress.authority_revision or 0)), (20, 3))

        source_conflict = self._upload_package(
            session_id,
            "progress",
            4,
            [{**snapshot_b, "snapshotHash": "c" * 64}],
        )["results"][0]
        self.assertEqual(source_conflict["code"], "SOURCE_SNAPSHOT_CHANGED")
        self.assertEqual(source_conflict["serverSnapshotHash"], "b" * 64)

        legacy_snapshot = {
            key: value
            for key, value in {**snapshot_b, "snapshotHash": "d" * 64}.items()
            if key != "baseSnapshotHash"
        }
        legacy_applied = self._upload_package(
            session_id,
            "progress",
            5,
            [legacy_snapshot],
        )["results"][0]
        self.assertEqual(legacy_applied["code"], "PROGRESS_APPLIED")
        self.assertTrue(legacy_applied["legacy_unversioned"])
        self.assertEqual(legacy_applied["serverSnapshotHash"], "d" * 64)
        with self.app.app_context():
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            self.assertEqual(int(progress.authority_revision or 0), 3)

        unresolved = {
            **snapshot_b,
            "snapshotHash": "e" * 64,
            "baseSnapshotHash": "d" * 64,
        }
        unresolved.pop("sourceToday")
        due_unresolved = self._upload_package(
            session_id,
            "progress",
            6,
            [unresolved],
        )["results"][0]
        self.assertEqual(due_unresolved["code"], "ANKI_DUE_UNRESOLVED")
        self.assertEqual(due_unresolved["serverSnapshotHash"], "d" * 64)
        with self.app.app_context():
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            source_card = ConnectSourceCardRef.query.filter_by(
                user_id=self.admin_id,
                external_card_id="4001",
            ).one()
            self.assertEqual(int(progress.authority_revision or 0), 3)
            self.assertEqual(source_card.snapshot_hash, "d" * 64)
            self.assertEqual(StudyProgressHistoryFact.query.count(), 0)

        with patch(
            "app.services.anki_sync_service._progress_snapshot_values",
            side_effect=RuntimeError("snapshot fault injection"),
        ):
            failed = self._upload_package(
                session_id,
                "progress",
                7,
                [
                    {
                        **snapshot_b,
                        "snapshotHash": "f" * 64,
                        "baseSnapshotHash": "d" * 64,
                        "force": True,
                    }
                ],
            )["results"][0]
        self.assertEqual(failed["code"], "PROGRESS_IMPORT_FAILED")
        with self.app.app_context():
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            source_card = ConnectSourceCardRef.query.filter_by(
                user_id=self.admin_id,
                external_card_id="4001",
            ).one()
            self.assertEqual(int(progress.authority_revision or 0), 3)
            self.assertEqual(source_card.snapshot_hash, "d" * 64)

            from app.services import study_service

            card = Card.query.filter_by(note_id=progress.live_note_id).one()
            study_service.execute_native_review_command(
                user=db.session.get(User, self.admin_id),
                card=card,
                action="good",
                payload={"duration_ms": 100},
                clone_scope=None,
                requested_scope_id=int(card.note.deck_id),
                timezone_name="UTC",
                now=datetime(2026, 8, 14, 12, 0, 0),
            )
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            self.assertEqual(int(progress.authority_revision or 0), 4)
            self.assertEqual(StudyProgressSubject.query.count(), 1)
            self.assertEqual(StudyProgressHistoryFact.query.count(), 1)

        # The native review moved card_progress past the applied revision.
        local_changed = self._upload_package(
            session_id,
            "progress",
            8,
            [
                {
                    **snapshot_b,
                    "snapshotHash": "9" * 64,
                    "baseSnapshotHash": "d" * 64,
                }
            ],
        )["results"][0]
        self.assertEqual(local_changed["code"], "LOCAL_PROGRESS_CHANGED")
        forced_again = self._upload_package(
            session_id,
            "progress",
            9,
            [
                {
                    **snapshot_b,
                    "snapshotHash": "9" * 64,
                    "baseSnapshotHash": "d" * 64,
                    "force": True,
                }
            ],
        )["results"][0]
        self.assertEqual(forced_again["code"], "FORCED_PROGRESS_APPLIED")
        with self.app.app_context():
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            self.assertEqual((decode_note_state(progress).intervalDays, int(progress.authority_revision or 0)), (20, 5))

    # The CP first-INSERT race primitive was retired. NOTE CAS, fault rollback
    # and import retry are covered by the canonical snapshot tests above and
    # test_study_consolidated_connect; no compatibility row can be inserted.

    def test_progress_and_full_revlog_are_separate_idempotent_sync_streams(self):
        from app.services.stats_overview import build_stats_overview

        self.app.config["STUDY_PROGRESS_SHADOW_COMPARE_ENABLED"] = True
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
        progress_result = response.get_json()["results"][0]
        self.assertEqual(progress_result["state"], "applied", progress_result)
        self.assertEqual(progress_result["code"], "PROGRESS_APPLIED")
        self.assertEqual(progress_result["serverSnapshotHash"], "2" * 64)
        self.assertTrue(progress_result["legacy_unversioned"])
        with self.app.app_context():
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            snapshot_revision = int(progress.authority_revision or 0)
            snapshot_last_reviewed_at = decode_note_state(progress).lastReviewAt
            snapshot_state_hash = bytes(progress.semantic_state_hash)

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
            progress = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id).one()
            self.assertEqual(decode_note_state(progress).reps, 2)
            self.assertEqual(int(progress.authority_revision or 0), snapshot_revision)
            self.assertEqual(decode_note_state(progress).lastReviewAt, snapshot_last_reviewed_at)
            self.assertEqual(bytes(progress.semantic_state_hash), snapshot_state_hash)
            # History facts are NOTE evidence; a LEGACY learner keeps ReviewEvents (P10-09).
            self.assertEqual(StudyProgressSubject.query.count(), 1)
            self.assertEqual(StudyProgressHistoryFact.query.count(), 3)
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

        fault_review = [{**reviews[1], "sourceReviewId": third_ms + 2000}]
        fault_package = gzip.compress(
            (json.dumps(fault_review[0]) + "\n").encode(),
            mtime=0,
        )
        with patch(
            "app.services.anki_sync_service.create_review_event_record",
            side_effect=RuntimeError("revlog fault injection"),
        ):
            fault_response = self.client.put(
                f"/api/flashcards/import/anki/sessions/{session_id}/packages/reviews/4",
                data=fault_package,
                headers={
                    "Content-Encoding": "gzip",
                    "X-Package-SHA256": hashlib.sha256(fault_package).hexdigest(),
                },
            )
        self.assertEqual(fault_response.status_code, 200, fault_response.get_json())
        self.assertEqual(fault_response.get_json()["results"][0]["state"], "failed")
        with self.app.app_context():
            self.assertEqual(ReviewEvent.query.filter_by(user_id=self.admin_id).count(), 3)
            self.assertEqual(ConnectReviewEventRef.query.filter_by(user_id=self.admin_id).count(), 3)
            self.assertEqual(StudyProgressHistoryFact.query.count(), 3)

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
