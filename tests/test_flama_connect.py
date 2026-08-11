from __future__ import annotations

import base64
import hashlib
import gzip
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta

from app.connect import create_connect_app
from app.services.anki_content_normalizer import backfill_anki_note_entities
from app.services import user_api_token_service
from models import db
from models.card import Card
from models.connect_pending_media import ConnectPendingMedia
from models.connect_import_session import ConnectImportSession
from models.connect_import_media import ConnectImportMedia
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


_MIN_MP3_BYTES = b"ID3\x04\x00\x00\x00\x00\x00\x15" + (b"\x00" * 64)
_MIN_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


class FlamaConnectTests(unittest.TestCase):
    def setUp(self):
        self.upload_tmp = tempfile.TemporaryDirectory()
        self.app = create_connect_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "CONNECT_CORS_ALLOWED_ORIGINS": (),
                "CONNECT_LEGACY_WEB_ACTIONS_ENABLED": True,
                "CONNECT_IP_RATE_LIMIT": 1000,
                "CONNECT_TOKEN_RATE_LIMIT": 1000,
                "CONNECT_USER_RATE_LIMIT": 1000,
                "CONNECT_ADD_NOTE_RATE_LIMIT": 1000,
                "CONNECT_MEDIA_RATE_LIMIT": 1000,
                "CONNECT_MEDIA_MAX_BYTES": 1024,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": self.upload_tmp.name,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            owner = User(username="connect-owner", email="connect@example.com")
            owner.set_password("password")
            other = User(username="connect-other", email="other@example.com")
            other.set_password("password")
            db.session.add_all([owner, other])
            db.session.flush()
            self.user_id = owner.id
            self.other_user_id = other.id

            note_type = NoteType(user_id=owner.id, name="Yomitan Vocabulary")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id
            other_note_type = NoteType(user_id=other.id, name="Other private model")
            db.session.add(other_note_type)
            db.session.flush()
            self.other_note_type_id = other_note_type.id
            db.session.add_all(
                [
                    FieldDef(note_type_id=note_type.id, name="Meaning", field_type="text", position=0),
                    FieldDef(
                        note_type_id=note_type.id,
                        name="Word",
                        field_type="text",
                        position=1,
                        required=True,
                        identity_role="primary",
                    ),
                    Template(
                        note_type_id=note_type.id,
                        name="Card 1",
                        front_html="{{Word}}",
                        back_html="{{Meaning}}",
                    ),
                ]
            )
            inbox = Deck(owner_user_id=owner.id, name="Inbox")
            second = Deck(owner_user_id=owner.id, name="Second")
            private = Deck(owner_user_id=other.id, name="Other private")
            db.session.add_all([inbox, second, private])
            issued = user_api_token_service.issue_token(user_id=owner.id, name="Yomitan PC")
            db.session.commit()
            self.token = issued.plaintext
            self.inbox_id = inbox.id
            self.second_id = second.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.upload_tmp.cleanup()

    def _call(self, action: str, params: dict | None = None, *, key: str | None = None):
        return self.client.post(
            "/v1/flama-connect",
            json={
                "action": action,
                "params": params or {},
                "version": 2,
                "key": self.token if key is None else key,
            },
        )

    def _call_token_url(self, action: str, params: dict | None = None, *, body_key: str | None = None):
        payload = {"action": action, "params": params or {}, "version": 2}
        if body_key is not None:
            payload["key"] = body_key
        return self.client.post(f"/v1/flama-connect/{self.token}", json=payload)

    def _media_zip(self, files: dict[str, bytes]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            for filename, content in files.items():
                archive.writestr(filename, content)
        return buffer.getvalue()

    def _note(self, deck_name: str = "Inbox", word: str = "猫") -> dict:
        return {
            "deckName": deck_name,
            "modelName": "Yomitan Vocabulary",
            "fields": {"Meaning": "cat", "Word": word},
            "tags": ["yomitan"],
            "options": {
                "allowDuplicate": False,
                "duplicateScope": "collection",
                "duplicateScopeOptions": {
                    "deckName": None,
                    "checkChildren": False,
                    "checkAllModels": False,
                },
            },
        }

    def _create_import_session(
        self,
        *,
        selected_decks: list[str] | None = None,
        mode: str = "strict",
        target_note_type_id: str | None = None,
        source_model_id: str = "1001",
        source_model_name: str = "Yomitan Vocabulary",
    ):
        target_id = self.note_type_id if target_note_type_id is None else target_note_type_id
        plan = {
            "sourceModelId": source_model_id,
            "sourceModelName": source_model_name,
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
        if target_id:
            plan["targetNoteTypeId"] = target_id
        return self._call(
            "createImportSession",
            {
                "source": "anki",
                "sourceKey": "test-profile",
                "sourceRootPath": "Inbox",
                "targetRootPath": "Inbox",
                "selectedDecks": selected_decks or ["Inbox"],
                "totalNotes": 2,
                "totalMedia": 0,
                "mode": mode,
                "noteTypes": [plan],
                "planHash": "a" * 64,
            },
        )

    def test_yomitan_v2_success_values_are_returned_directly(self):
        self.assertEqual(self._call("version").get_json(), 6)
        self.assertEqual(self._call("modelFieldNames", {"modelName": "Yomitan Vocabulary"}).get_json(), ["Word", "Meaning"])
        self.assertEqual(self._call("deckNames").get_json(), ["Inbox", "Second"])
        reflected = self._call(
            "apiReflect",
            {"scopes": ["actions"], "actions": ["addNote", "storeMediaFile"]},
        ).get_json()
        self.assertEqual(
            reflected,
            {"scopes": ["actions"], "actions": ["addNote", "storeMediaFile"]},
        )

    def test_note_type_resolution_never_falls_back_to_another_user(self):
        for model_name in (self.other_note_type_id, "Other private model"):
            with self.subTest(model_name=model_name):
                response = self._call("modelFieldNames", {"modelName": model_name})
                self.assertEqual(
                    response.get_json(),
                    {"result": None, "error": "model was not found or is ambiguous"},
                )

    def test_import_cards_uses_owned_note_type_id_and_reports_each_card(self):
        valid_note = self._note()
        valid_note["modelName"] = self.note_type_id
        invalid_note = self._note(word="")
        invalid_note["modelName"] = self.note_type_id

        session = self._create_import_session().get_json()
        self.assertEqual(session["status"], "note_types_ready")
        response = self._call(
            "importCards",
            {
                "importSessionId": session["importSessionId"],
                "cards": [
                    {
                        "ankiNoteId": 101,
                        "sourceModelId": "1001",
                        "sourceDeckId": "1",
                        "sourceDeckPath": "Inbox",
                        "contentHash": "1" * 64,
                        "note": valid_note,
                    },
                    {
                        "ankiNoteId": 102,
                        "sourceModelId": "1001",
                        "sourceDeckId": "1",
                        "sourceDeckPath": "Inbox",
                        "contentHash": "2" * 64,
                        "note": invalid_note,
                    },
                ],
            },
        )
        results = response.get_json()["results"]
        self.assertEqual(results[0]["ankiNoteId"], 101)
        self.assertTrue(results[0]["imported"])
        self.assertEqual(results[1]["ankiNoteId"], 102)
        self.assertFalse(results[1]["imported"])
        self.assertTrue(results[1]["error"])

    def test_strict_preflight_blocks_missing_note_type_without_domain_writes(self):
        with self.app.app_context():
            before = (NoteType.query.count(), Deck.query.count(), Note.query.count(), Card.query.count())
        response = self._create_import_session(
            mode="strict",
            target_note_type_id="",
            source_model_id="missing-model",
            source_model_name="Missing Anki Model",
        )
        payload = response.get_json()
        self.assertEqual(payload["status"], "blocked_note_types")
        self.assertEqual(payload["blockers"][0]["code"], "NOTE_TYPE_MISSING")
        blocked_import = self._call(
            "importCards",
            {"importSessionId": payload["importSessionId"], "cards": []},
        )
        self.assertIn("NoteTypes must be ready", blocked_import.get_json()["error"])
        with self.app.app_context():
            self.assertEqual(
                (NoteType.query.count(), Deck.query.count(), Note.query.count(), Card.query.count()),
                before,
            )
            self.assertEqual(ConnectImportSession.query.count(), 1)

    def test_auto_preflight_creates_missing_note_type_before_any_deck_or_card(self):
        with self.app.app_context():
            before_decks = Deck.query.count()
        response = self._create_import_session(
            mode="auto_sync_missing",
            target_note_type_id="",
            source_model_id="new-model",
            source_model_name="New Anki Model",
        )
        payload = response.get_json()
        self.assertEqual(payload["status"], "note_types_ready")
        target_id = payload["noteTypeBindings"]["new-model"]["targetNoteTypeId"]
        with self.app.app_context():
            target = db.session.get(NoteType, target_id)
            self.assertIsNotNone(target)
            self.assertEqual([field.name for field in target.field_defs], ["Word", "Meaning"])
            self.assertEqual(len(target.templates), 1)
            self.assertEqual(Deck.query.count(), before_decks)
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(Card.query.count(), 0)

    def test_one_anki_deck_can_import_multiple_ready_note_types_without_flattening(self):
        with self.app.app_context():
            second_type = NoteType(user_id=self.user_id, name="Second Anki Model")
            db.session.add(second_type)
            db.session.flush()
            db.session.add_all(
                [
                    FieldDef(
                        note_type_id=second_type.id,
                        name="Word",
                        field_type="text",
                        position=0,
                        required=True,
                        identity_role="primary",
                    ),
                    FieldDef(note_type_id=second_type.id, name="Meaning", field_type="richtext", position=1),
                    Template(
                        note_type_id=second_type.id,
                        name="Card 1",
                        front_html="{{Word}}",
                        back_html="{{Meaning}}",
                    ),
                ]
            )
            db.session.commit()
            second_type_id = second_type.id

        def plan(model_id: str, model_name: str, target_id: str):
            return {
                "sourceModelId": model_id,
                "sourceModelName": model_name,
                "targetNoteTypeId": target_id,
                "fields": [
                    {"name": "Word", "fieldType": "text"},
                    {"name": "Meaning", "fieldType": "richtext"},
                ],
                "templates": [
                    {"name": "Card 1", "frontHtml": "{{Word}}", "backHtml": "{{Meaning}}", "sharedCss": ""}
                ],
                "fieldMapping": {"Word": "Word", "Meaning": "Meaning"},
            }

        session = self._call(
            "createImportSession",
            {
                "source": "anki",
                "sourceKey": "mixed-model-profile",
                "sourceRootPath": "Inbox",
                "targetRootPath": "Inbox",
                "selectedDecks": ["Inbox"],
                "totalNotes": 2,
                "totalMedia": 0,
                "mode": "strict",
                "noteTypes": [
                    plan("model-one", "Yomitan Vocabulary", self.note_type_id),
                    plan("model-two", "Second Anki Model", second_type_id),
                ],
                "planHash": "e" * 64,
            },
        ).get_json()
        self.assertEqual(session["status"], "note_types_ready")

        first_note = self._note(word="first-model")
        first_note["modelName"] = self.note_type_id
        second_note = self._note(word="second-model")
        second_note["modelName"] = second_type_id
        result = self._call(
            "importCards",
            {
                "importSessionId": session["importSessionId"],
                "cards": [
                    {
                        "ankiNoteId": 701,
                        "sourceModelId": "model-one",
                        "sourceDeckId": "inbox",
                        "sourceDeckPath": "Inbox",
                        "contentHash": "1" * 64,
                        "note": first_note,
                    },
                    {
                        "ankiNoteId": 702,
                        "sourceModelId": "model-two",
                        "sourceDeckId": "inbox",
                        "sourceDeckPath": "Inbox",
                        "contentHash": "2" * 64,
                        "note": second_note,
                    },
                ],
            },
        ).get_json()
        self.assertTrue(all(item["imported"] for item in result["results"]), result)
        with self.app.app_context():
            deck = db.session.get(Deck, self.inbox_id)
            self.assertIsNone(deck.note_type_id)
            self.assertEqual(Note.query.filter_by(user_id=self.user_id, deck_id=self.inbox_id).count(), 2)

    def test_import_preserves_nested_deck_path_and_attaches_audio_and_image(self):
        with self.app.app_context():
            db.session.add_all(
                [
                    FieldDef(note_type_id=self.note_type_id, name="Image", field_type="image", position=2),
                    FieldDef(note_type_id=self.note_type_id, name="Sound", field_type="audio", position=3),
                ]
            )
            db.session.commit()
        plan = {
            "sourceModelId": "media-model",
            "sourceModelName": "Yomitan Vocabulary",
            "targetNoteTypeId": self.note_type_id,
            "fields": [
                {"name": "Word", "fieldType": "text"},
                {"name": "Meaning", "fieldType": "richtext"},
                {"name": "Image", "fieldType": "image"},
                {"name": "Sound", "fieldType": "audio"},
            ],
            "templates": [{"name": "Card 1", "frontHtml": "{{Word}}", "backHtml": "{{Meaning}}", "sharedCss": ""}],
            "fieldMapping": {"Word": "Word", "Meaning": "Meaning", "Image": "Image", "Sound": "Sound"},
        }
        session = self._call(
            "createImportSession",
            {
                "source": "anki",
                "sourceKey": "media-profile",
                "sourceRootPath": "Source",
                "targetRootPath": "Imported",
                "selectedDecks": ["Imported", "Imported::Child"],
                "totalNotes": 1,
                "totalMedia": 2,
                "mode": "strict",
                "noteTypes": [plan],
                "planHash": "b" * 64,
            },
        ).get_json()
        self.assertEqual(session["status"], "note_types_ready")
        image_name = f"{'1' * 64}.png"
        audio_name = f"{'2' * 64}.mp3"
        image_upload = self._call(
            "storeMediaFile",
            {
                "importSessionId": session["importSessionId"],
                "mediaKind": "image",
                "filename": image_name,
                "data": base64.b64encode(_MIN_PNG_BYTES).decode("ascii"),
            },
        )
        audio_upload = self._call(
            "storeMediaFile",
            {
                "importSessionId": session["importSessionId"],
                "mediaKind": "audio",
                "filename": audio_name,
                "data": base64.b64encode(_MIN_MP3_BYTES).decode("ascii"),
            },
        )
        self.assertEqual(image_upload.get_json()["filename"], image_name)
        self.assertEqual(audio_upload.get_json()["filename"], audio_name)

        note = self._note("Imported::Child", "media-note")
        note["modelName"] = self.note_type_id
        note["fields"].update({"Image": image_name, "Sound": f"[sound:{audio_name}]"})
        imported = self._call(
            "importCards",
            {
                "importSessionId": session["importSessionId"],
                "cards": [
                    {
                        "ankiNoteId": 501,
                        "sourceModelId": "media-model",
                        "sourceDeckId": "source-child-id",
                        "sourceDeckPath": "Source::Child",
                        "contentHash": "c" * 64,
                        "note": note,
                    }
                ],
            },
        ).get_json()
        self.assertTrue(imported["results"][0]["imported"], imported)
        with self.app.app_context():
            child = Deck.query.filter_by(owner_user_id=self.user_id, name="Child").one()
            self.assertEqual(child.parent.name, "Imported")
            created = Note.query.filter_by(user_id=self.user_id, deck_id=child.id).one()
            self.assertEqual(created.field_values["Image"], image_name)
            self.assertEqual(created.field_values["Sound"], audio_name)
            self.assertEqual(MediaAsset.query.filter_by(note_id=created.id).count(), 2)
            self.assertEqual(ConnectImportMedia.query.count(), 2)

    def test_import_ignores_missing_media_and_imports_successfully(self):
        with self.app.app_context():
            db.session.add_all(
                [
                    FieldDef(note_type_id=self.note_type_id, name="Image", field_type="image", position=2),
                    FieldDef(note_type_id=self.note_type_id, name="Sound", field_type="audio", position=3),
                ]
            )
            db.session.commit()
        plan = {
            "sourceModelId": "media-model",
            "sourceModelName": "Yomitan Vocabulary",
            "targetNoteTypeId": self.note_type_id,
            "fields": [
                {"name": "Word", "fieldType": "text"},
                {"name": "Meaning", "fieldType": "richtext"},
                {"name": "Image", "fieldType": "image"},
                {"name": "Sound", "fieldType": "audio"},
            ],
            "templates": [{"name": "Card 1", "frontHtml": "{{Word}}", "backHtml": "{{Meaning}}", "sharedCss": ""}],
            "fieldMapping": {"Word": "Word", "Meaning": "Meaning", "Image": "Image", "Sound": "Sound"},
        }
        session = self._call(
            "createImportSession",
            {
                "source": "anki",
                "sourceKey": "media-profile",
                "sourceRootPath": "Source",
                "targetRootPath": "Imported",
                "selectedDecks": ["Imported", "Imported::Child"],
                "totalNotes": 1,
                "totalMedia": 2,
                "mode": "strict",
                "noteTypes": [plan],
                "planHash": "b" * 64,
            },
        ).get_json()
        self.assertEqual(session["status"], "note_types_ready")
        image_name = f"{'1' * 64}.png"
        audio_name = f"{'2' * 64}.mp3"
        image_upload = self._call(
            "storeMediaFile",
            {
                "importSessionId": session["importSessionId"],
                "mediaKind": "image",
                "filename": image_name,
                "data": base64.b64encode(_MIN_PNG_BYTES).decode("ascii"),
            },
        )
        self.assertEqual(image_upload.get_json()["filename"], image_name)

        note = self._note("Imported::Child", "media-note")
        note["modelName"] = self.note_type_id
        note["fields"].update({"Image": image_name, "Sound": f"[sound:{audio_name}]"})
        imported = self._call(
            "importCards",
            {
                "importSessionId": session["importSessionId"],
                "cards": [
                    {
                        "ankiNoteId": 501,
                        "sourceModelId": "media-model",
                        "sourceDeckId": "source-child-id",
                        "sourceDeckPath": "Source::Child",
                        "contentHash": "c" * 64,
                        "note": note,
                    }
                ],
            },
        ).get_json()
        self.assertTrue(imported["results"][0]["imported"], imported)
        with self.app.app_context():
            child = Deck.query.filter_by(owner_user_id=self.user_id, name="Child").one()
            self.assertEqual(child.parent.name, "Imported")
            created = Note.query.filter_by(user_id=self.user_id, deck_id=child.id).one()
            self.assertEqual(created.field_values["Image"], image_name)
            self.assertEqual(created.field_values["Sound"], f"[sound:{audio_name}]")
            self.assertEqual(MediaAsset.query.filter_by(note_id=created.id).count(), 1)
            self.assertEqual(ConnectImportMedia.query.count(), 1)

    def test_media_zip_package_is_checksum_verified_and_idempotent(self):
        session = self._create_import_session().get_json()
        package = self._media_zip({f"{'a' * 64}.mp3": _MIN_MP3_BYTES})
        digest = hashlib.sha256(package).hexdigest()
        url = f"/v1/import-sessions/{session['importSessionId']}/packages/media/0"
        first = self.client.put(
            url,
            data=package,
            content_type="application/zip",
            headers={"Authorization": f"Bearer {self.token}", "X-Package-SHA256": digest},
        )
        self.assertEqual(first.status_code, 200, first.get_json())
        self.assertEqual(first.get_json()["itemCount"], 1)
        self.assertFalse(first.get_json()["replayed"])
        replay = self.client.put(
            url,
            data=package,
            content_type="application/zip",
            headers={"Authorization": f"Bearer {self.token}", "X-Package-SHA256": digest},
        )
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.get_json()["replayed"])

        changed = self._media_zip({f"{'b' * 64}.mp3": _MIN_MP3_BYTES})
        conflict = self.client.put(
            url,
            data=changed,
            content_type="application/zip",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-Package-SHA256": hashlib.sha256(changed).hexdigest(),
            },
        )
        self.assertEqual(conflict.status_code, 409)

    def test_card_ndjson_package_replays_without_duplicate_notes(self):
        session = self._create_import_session().get_json()
        note = self._note()
        note["modelName"] = self.note_type_id
        record = {
            "ankiNoteId": 601,
            "sourceModelId": "1001",
            "sourceDeckId": "inbox-source",
            "sourceDeckPath": "Inbox",
            "contentHash": "d" * 64,
            "note": note,
        }
        package = gzip.compress((json.dumps(record) + "\n").encode("utf-8"), mtime=0)
        digest = hashlib.sha256(package).hexdigest()
        url = f"/v1/import-sessions/{session['importSessionId']}/packages/cards/0"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Package-SHA256": digest,
            "Content-Encoding": "gzip",
        }
        first = self.client.put(url, data=package, content_type="application/x-ndjson", headers=headers)
        self.assertEqual(first.status_code, 200, first.get_json())
        self.assertTrue(first.get_json()["results"][0]["imported"])
        replay = self.client.put(url, data=package, content_type="application/x-ndjson", headers=headers)
        self.assertEqual(replay.status_code, 200, replay.get_json())
        self.assertTrue(replay.get_json()["replayed"])
        self.assertTrue(replay.get_json()["results"][0]["imported"])
        with self.app.app_context():
            self.assertEqual(Note.query.filter_by(user_id=self.user_id, deck_id=self.inbox_id).count(), 1)

    def test_invalid_token_is_generic_and_does_not_accept_session_or_bearer(self):
        response = self._call("deckNames", key="not-a-token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["error"], "authentication failed")
        # Header authentication is supported when valid
        response = self.client.post(
            "/v1/flama-connect",
            json={"action": "deckNames", "params": {}, "version": 2},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), ["Inbox", "Second"])

    def test_tokenized_server_url_works_without_body_key(self):
        self.assertEqual(self._call_token_url("version").get_json(), 6)
        self.assertEqual(self._call_token_url("deckNames").get_json(), ["Inbox", "Second"])
        mismatch = self._call_token_url("version", body_key="not-the-url-token")
        self.assertEqual(mismatch.get_json()["error"], "authentication failed")

    def test_cors_is_not_opened_for_arbitrary_web_origins(self):
        response = self.client.post(
            "/v1/flama-connect",
            json={"action": "version", "params": {}, "version": 2, "key": self.token},
            headers={"Origin": "https://attacker.example"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_add_binds_empty_deck_and_duplicate_is_exact_target_deck(self):
        response = self._call("addNote", {"note": self._note()})
        self.assertIsInstance(response.get_json(), int)
        duplicate = self._call("canAddNotesWithErrorDetail", {"notes": [self._note()]})
        self.assertEqual(duplicate.get_json()[0]["canAdd"], False)
        other_deck = self._call("canAddNotesWithErrorDetail", {"notes": [self._note("Second")]})
        self.assertEqual(other_deck.get_json(), [{"canAdd": True, "error": None}])
        with self.app.app_context():
            self.assertEqual(db.session.get(Deck, self.inbox_id).note_type_id, self.note_type_id)
            self.assertEqual(Note.query.filter_by(user_id=self.user_id, deck_id=self.inbox_id).count(), 1)
            self.assertEqual(Card.query.count(), 1)

    def test_add_note_normalizes_anki_apostrophe_entities_only(self):
        note = self._note(word="entity-normalization")
        note["fields"]["Meaning"] = (
            "Open: &#x27;from...to...&#x27;; &#39;position&#39;; "
            "&apos;vacancy&apos; &lt;script&gt;"
        )

        response = self._call("addNote", {"note": note})
        self.assertIsInstance(response.get_json(), int)

        with self.app.app_context():
            created = Note.query.filter_by(user_id=self.user_id, deck_id=self.inbox_id).one()
            self.assertEqual(
                created.field_values["Meaning"],
                "Open: 'from...to...'; 'position'; 'vacancy' &lt;script&gt;",
            )

    def test_anki_entity_backfill_only_updates_tracked_anki_notes(self):
        with self.app.app_context():
            tracked = Note(
                note_type_id=self.note_type_id,
                user_id=self.user_id,
                deck_id=self.inbox_id,
                field_values={"Word": "tracked", "Meaning": "It&#x27;s tracked"},
                tags=[],
            )
            untracked = Note(
                note_type_id=self.note_type_id,
                user_id=self.user_id,
                deck_id=self.inbox_id,
                field_values={"Word": "untracked", "Meaning": "It&#x27;s local"},
                tags=[],
            )
            db.session.add_all([tracked, untracked])
            db.session.flush()
            db.session.add(
                ConnectSourceNoteRef(
                    user_id=self.user_id,
                    source_key="test-profile",
                    external_note_id="entity-note",
                    source_model_id="1001",
                    source_deck_path="Inbox",
                    note_id=tracked.id,
                    content_hash="f" * 64,
                )
            )
            db.session.commit()

            result = backfill_anki_note_entities(deck_id=self.inbox_id)
            db.session.commit()

            self.assertEqual((result.scanned, result.changed), (1, 1))
            self.assertEqual(db.session.get(Note, tracked.id).field_values["Meaning"], "It's tracked")
            self.assertEqual(db.session.get(Note, untracked.id).field_values["Meaning"], "It&#x27;s local")

    def test_duplicate_scope_deck_name_rejects_non_null_non_string_values(self):
        note = self._note()
        note["options"]["duplicateScopeOptions"]["deckName"] = 123
        response = self._call("canAddNotesWithErrorDetail", {"notes": [note]})
        self.assertEqual(
            response.get_json(),
            [{"canAdd": False, "error": "duplicateScopeOptions.deckName must be null or a valid string"}],
        )

    def test_missing_or_unowned_destination_deck_is_rejected_without_writes(self):
        invalid_cases = (
            (None, "Thiếu deckName. Vui lòng chọn deck đích trong Yomitan."),
            ("", "Thiếu deckName. Vui lòng chọn deck đích trong Yomitan."),
            ("Missing", "Không tìm thấy deck đích hoặc bạn không có quyền ghi vào deck này."),
            ("Other private", "Không tìm thấy deck đích hoặc bạn không có quyền ghi vào deck này."),
        )
        for deck_name, expected_error in invalid_cases:
            with self.subTest(deck_name=deck_name):
                note = self._note()
                if deck_name is None:
                    note.pop("deckName")
                else:
                    note["deckName"] = deck_name
                response = self._call("addNote", {"note": note})
                self.assertEqual(response.get_json(), {"result": None, "error": expected_error})

        missing_note = self._note()
        missing_note.pop("deckName")
        check_response = self._call("canAddNotesWithErrorDetail", {"notes": [missing_note]})
        self.assertEqual(
            check_response.get_json(),
            [{
                "canAdd": False,
                "error": "Thiếu deckName. Vui lòng chọn deck đích trong Yomitan.",
            }],
        )

        with self.app.app_context():
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(Card.query.count(), 0)
            self.assertIsNone(db.session.get(Deck, self.inbox_id).note_type_id)

    def test_find_notes_and_multi_return_numeric_refs(self):
        note_id = self._call("addNote", {"note": self._note()}).get_json()
        query = '"deck:Inbox" "word:猫"'
        self.assertEqual(self._call("findNotes", {"query": query}).get_json(), [note_id])
        multi = self._call(
            "multi",
            {"actions": [{"action": "findNotes", "params": {"query": query}, "key": self.token}]},
        )
        self.assertEqual(multi.get_json(), [[note_id]])
        token_url_multi = self._call_token_url(
            "multi",
            {"actions": [{"action": "findNotes", "params": {"query": query}}]},
        )
        self.assertEqual(token_url_multi.get_json(), [[note_id]])

    def test_media_and_unknown_properties_are_rejected_without_writing(self):
        note = self._note()
        note["audio"] = [{"filename": "voice.mp3", "data": "abc"}]
        response = self._call("addNote", {"note": note})
        self.assertIn("media import is not supported", response.get_json()["error"])
        malformed = self.client.post(
            "/v1/flama-connect",
            data='{"action":"version","action":"deckNames","version":2,"key":"x"}',
            content_type="application/json",
        )
        self.assertIn("duplicate JSON property", malformed.get_json()["error"])

    def test_store_mp3_then_add_note_attaches_media_asset(self):
        filename = "yomitan_audio_b7d03ad2a722daa5711db4a2d96aeefd2cd3a84e.mp3"
        encoded = base64.b64encode(_MIN_MP3_BYTES).decode("ascii")
        stored = self._call(
            "storeMediaFile",
            {"filename": filename, "data": encoded},
        )
        self.assertEqual(stored.get_json(), filename)

        with self.app.app_context():
            db.session.add(
                FieldDef(
                    note_type_id=self.note_type_id,
                    name="Sound",
                    field_type="audio",
                    position=2,
                )
            )
            db.session.commit()
            pending = ConnectPendingMedia.query.filter_by(
                user_id=self.user_id,
                filename=filename,
            ).one()
            pending_path = Path(self.upload_tmp.name, pending.storage_path)
            self.assertTrue(pending_path.is_file())

        note = self._note(word="audio-word")
        note["fields"]["Sound"] = f"[sound:{filename}]"
        added = self._call("addNote", {"note": note})
        self.assertIsInstance(added.get_json(), int)

        with self.app.app_context():
            created_note = Note.query.filter_by(user_id=self.user_id).one()
            asset = MediaAsset.query.filter_by(note_id=created_note.id, field_name="Sound").one()
            self.assertEqual(asset.filename, filename)
            self.assertEqual(asset.mime_type, "audio/mpeg")
            self.assertEqual(created_note.field_values["Sound"], filename)
            self.assertNotEqual(created_note.field_values["Sound"], f"[sound:{filename}]")
            self.assertEqual(ConnectPendingMedia.query.count(), 0)
            self.assertTrue(Path(self.upload_tmp.name, asset.storage_path).is_file())
            self.assertFalse(pending_path.exists())

    def test_store_media_rejects_unsafe_non_mp3_and_oversized_payloads(self):
        encoded = base64.b64encode(_MIN_MP3_BYTES).decode("ascii")
        unsafe = self._call(
            "storeMediaFile",
            {"filename": "../voice.mp3", "data": encoded},
        )
        self.assertIn("chỉ nhận file MP3", unsafe.get_json()["error"])

        wrong_signature = self._call(
            "storeMediaFile",
            {
                "filename": "yomitan_audio_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.mp3",
                "data": base64.b64encode(b"\x89PNG\r\n\x1a\ninvalid").decode("ascii"),
            },
        )
        self.assertIn("Audio MP3 không hợp lệ", wrong_signature.get_json()["error"])

        oversized = self._call(
            "storeMediaFile",
            {
                "filename": "yomitan_audio_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.mp3",
                "data": base64.b64encode(b"ID3" + (b"x" * 1024)).decode("ascii"),
            },
        )
        self.assertIn("vượt quá giới hạn", oversized.get_json()["error"])
        with self.app.app_context():
            self.assertEqual(ConnectPendingMedia.query.count(), 0)

    def test_add_note_rejects_audio_reference_that_was_not_staged(self):
        filename = "yomitan_audio_cccccccccccccccccccccccccccccccccccccccc.mp3"
        with self.app.app_context():
            db.session.add(
                FieldDef(
                    note_type_id=self.note_type_id,
                    name="Sound",
                    field_type="audio",
                    position=2,
                )
            )
            db.session.commit()
        note = self._note(word="missing-audio")
        note["fields"]["Sound"] = f"[sound:{filename}]"
        response = self._call("addNote", {"note": note})
        self.assertIn("Không tìm thấy audio", response.get_json()["error"])
        with self.app.app_context():
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(MediaAsset.query.count(), 0)

    def test_clone_duplicate_and_local_addition_preserve_overlay_model(self):
        with self.app.app_context():
            source_type = NoteType(user_id=self.other_user_id, name="Source Vocabulary")
            db.session.add(source_type)
            db.session.flush()
            source_field = FieldDef(
                note_type_id=source_type.id,
                name="Word",
                field_type="text",
                position=0,
                required=True,
                identity_role="primary",
            )
            source_template = Template(
                note_type_id=source_type.id,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{Word}}",
            )
            source_deck = Deck(
                owner_user_id=self.other_user_id,
                note_type_id=source_type.id,
                name="Source",
            )
            local_deck = Deck(
                owner_user_id=self.user_id,
                note_type_id=self.note_type_id,
                name="Installed Clone",
            )
            db.session.add_all([source_field, source_template, source_deck, local_deck])
            db.session.flush()
            source_note = Note(
                user_id=self.other_user_id,
                note_type_id=source_type.id,
                deck_id=source_deck.id,
                field_values={"Word": "既存"},
                tags=[],
            )
            db.session.add(source_note)
            db.session.flush()
            db.session.add(Card(note_id=source_note.id, template_id=source_template.id))
            item = DeckMarketplaceItem(
                owner_user_id=self.other_user_id,
                source_deck_id=source_deck.id,
                source_note_type_id=source_type.id,
                title="Source",
            )
            db.session.add(item)
            db.session.flush()
            snapshot = datetime.utcnow() + timedelta(seconds=1)
            install = DeckInstall(
                deck_item_id=item.id,
                user_id=self.user_id,
                local_deck_id=local_deck.id,
                clone_mode="logical_overlay",
                source_deck_id=source_deck.id,
                source_note_type_id=source_type.id,
                source_owner_user_id=self.other_user_id,
                base_snapshot_at=snapshot,
            )
            db.session.add(install)
            db.session.flush()
            db.session.add(
                DeckCloneDeckMap(
                    deck_install_id=install.id,
                    local_deck_id=local_deck.id,
                    source_deck_id=source_deck.id,
                )
            )
            db.session.commit()
            install_id = install.id
            local_deck_id = local_deck.id

        duplicate_note = self._note("Installed Clone", "既存")
        duplicate = self._call("canAddNotesWithErrorDetail", {"notes": [duplicate_note]}).get_json()[0]
        self.assertFalse(duplicate["canAdd"])
        added_id = self._call("addNote", {"note": self._note("Installed Clone", "追加")}).get_json()
        self.assertIsInstance(added_id, int)
        with self.app.app_context():
            addition = DeckCloneAddedNote.query.filter_by(deck_install_id=install_id).one()
            self.assertEqual(addition.note.deck_id, local_deck_id)
            self.assertEqual(db.session.get(DeckInstall, install_id).last_sync_status, "needs_sync")
            from app.services import flashcards_share_service
            scope = flashcards_share_service.resolve_clone_scope_for_local_deck(
                user_id=self.user_id,
                local_deck_id=local_deck_id,
            )
            self.assertIsNotNone(scope)
            self.assertEqual(flashcards_share_service.query_clone_scope_cards(scope).count(), 2)


if __name__ == "__main__":
    unittest.main()
