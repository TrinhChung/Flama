"""Regression tests for CSV/file import media validation (Issue #139).

Verifies that typed media fields (image, audio, diagram) reject legacy media
representations (bare filenames, [sound:...], legacy HTML, unresolved raw UUIDs)
and accept canonical URLs (/media/proxy/..., /media/library/..., /static/strokes/..., https://...).
Verifies non-media fields (text, richtext, markdown) remain unaffected.
"""

from __future__ import annotations

import io
import unittest

from app import create_app
from models import db
from models.deck import Deck
from models.field_def import FieldDef
from models.flashcard import Note, NoteType, Template
from models.media_asset import MediaAsset
from models.shared_image_asset import SharedImageAsset
from models.user import User
from tests.study_note_fixtures import attach_template, create_note_user


class FlashcardImportMediaValidationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = create_note_user(db.session, username="import_user", email="import_user@example.com", is_admin=True)
            user.set_password("password")
            self.user_id = user.id

            deck = Deck(name="Test Deck", owner_user_id=self.user_id, position=0)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id

            # Media note type with text, audio, image, diagram fields
            note_type = NoteType(name="Media Deck Note Type", user_id=self.user_id)
            db.session.add(note_type)
            db.session.flush()
            self.media_note_type_id = note_type.id

            f_word = FieldDef(note_type_id=note_type.id, name="Word", required=True, field_type="text", position=0)
            f_audio = FieldDef(note_type_id=note_type.id, name="Audio", required=False, field_type="audio", position=1)
            f_image = FieldDef(note_type_id=note_type.id, name="Image", required=False, field_type="image", position=2)
            f_diagram = FieldDef(note_type_id=note_type.id, name="Diagram", required=False, field_type="diagram", position=3)
            db.session.add_all([f_word, f_audio, f_image, f_diagram])
            db.session.flush()

            t = attach_template(
                db.session,
                owner_user_id=self.user_id,
                note_type_id=note_type.id,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{FrontSide}}<hr>{{Audio}}<br>{{Image}}<br>{{Diagram}}",
                position=0,
            )

            # Non-media note type
            nm_note_type = NoteType(name="Non-Media Note Type", user_id=self.user_id)
            db.session.add(nm_note_type)
            db.session.flush()
            self.nm_note_type_id = nm_note_type.id

            f_nm_word = FieldDef(note_type_id=nm_note_type.id, name="Word", required=True, field_type="text", position=0)
            f_nm_rich = FieldDef(note_type_id=nm_note_type.id, name="Description", required=False, field_type="richtext", position=1)
            f_nm_md = FieldDef(note_type_id=nm_note_type.id, name="Notes", required=False, field_type="markdown", position=2)
            db.session.add_all([f_nm_word, f_nm_rich, f_nm_md])

            t_nm = attach_template(
                db.session,
                owner_user_id=self.user_id,
                note_type_id=nm_note_type.id,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{FrontSide}}<hr>{{Description}}<br>{{Notes}}",
                position=0,
            )

            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "import_user@example.com", "password": "password"},
            follow_redirects=True,
        )

    def _parse_csv(self, note_type_id: str, csv_content: str, filename: str = "import.csv") -> dict:
        resp = self.client.post(
            "/api/flashcards/import/parse",
            data={
                "note_type_id": note_type_id,
                "delimiter_mode": "csv",
                "has_header": "1",
                "file": (io.BytesIO(csv_content.encode("utf-8")), filename),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        return resp.get_json()

    def _execute_import(
        self,
        token: str,
        note_type_id: str,
        mapping: dict,
        mode: str = "upsert",
        uniqueness_fields: list[str] | None = None,
        dont_overwrite_empty: bool = True,
    ) -> dict:
        resp = self.client.post(
            "/api/flashcards/import/execute",
            json={
                "token": token,
                "note_type_id": note_type_id,
                "target_deck_id": self.deck_id,
                "import_mode": mode,
                "uniqueness_fields": uniqueness_fields or ["Word"],
                "mapping": mapping,
                "dont_overwrite_empty": dont_overwrite_empty,
                "confirm_column_mismatch": True,
            },
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        return resp.get_json()

    def test_bare_filename_rejected_in_media_fields(self):
        csv_data = "Word,Audio,Image,Diagram\n猫,cat.mp3,cat.png,diagram.svg\n"
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        summary = result["summary"]
        self.assertEqual(summary["inserted"], 0)
        self.assertEqual(summary["errors"], 1)

        issues = result["issues"]
        self.assertTrue(any(
            issue["kind"] == "error"
            and issue["row"] == 1
            and "Audio" in issue["message"]
            and "cat.mp3" in issue["message"]
            for issue in issues
        ))

        with self.app.app_context():
            notes = Note.query.filter_by(note_type_id=self.media_note_type_id).all()
            self.assertEqual(len(notes), 0)

    def test_anki_sound_syntax_rejected(self):
        csv_data = "Word,Audio\n犬,[sound:dog.mp3]\n"
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 0)
        self.assertEqual(result["summary"]["errors"], 1)
        self.assertTrue(any(
            issue["kind"] == "error"
            and "Audio" in issue["message"]
            and "[sound:dog.mp3]" in issue["message"]
            for issue in result["issues"]
        ))

        with self.app.app_context():
            notes = Note.query.filter_by(note_type_id=self.media_note_type_id).all()
            self.assertEqual(len(notes), 0)

    def test_legacy_html_rejected_in_media_fields(self):
        # HTML with missing/unresolvable files or non-media HTML must be rejected
        csv_data = 'Word,Audio,Image\n鳥,,<img src="bird.png">\n魚,<audio src="fish.mp3"></audio>,\n草,,<p>not a media url</p>\n'
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 0)
        self.assertEqual(result["summary"]["errors"], 3)
        reasons = [issue.get("reason") for issue in result["issues"]]
        self.assertIn("legacy_html", reasons)
        self.assertIn("unresolved_legacy_reference", reasons)

        with self.app.app_context():
            notes = Note.query.filter_by(note_type_id=self.media_note_type_id).all()
            self.assertEqual(len(notes), 0)

    def test_html_with_canonical_urls_converts_to_canonical_urls(self):
        csv_data = (
            'Word,Audio,Image\n'
            '猫,<audio src="https://cdn.example.com/cat.mp3"></audio>,<img src="https://cdn.example.com/cat.png">\n'
            '犬,<audio controls><source src="https://cdn.example.com/dog.mp3" type="audio/mpeg"></audio>,<a href="https://cdn.example.com/dog.png">dog</a>\n'
            '鳥,<p>[sound:https://cdn.example.com/bird.mp3]</p>,<img src="https://cdn.example.com/b1.png"><img src="https://cdn.example.com/b2.png">\n'
        )
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 3)
        self.assertEqual(result["summary"]["errors"], 0)

        with self.app.app_context():
            notes = Note.query.filter_by(note_type_id=self.media_note_type_id).all()
            notes_by_word = {n.field_values.get("Word"): n for n in notes if isinstance(n.field_values, dict)}

            note_cat = notes_by_word.get("猫")
            self.assertIsNotNone(note_cat)
            self.assertEqual(note_cat.field_values["Audio"], "https://cdn.example.com/cat.mp3")
            self.assertEqual(note_cat.field_values["Image"], "https://cdn.example.com/cat.png")

            note_dog = notes_by_word.get("犬")
            self.assertIsNotNone(note_dog)
            self.assertEqual(note_dog.field_values["Audio"], "https://cdn.example.com/dog.mp3")
            self.assertEqual(note_dog.field_values["Image"], "https://cdn.example.com/dog.png")

            note_bird = notes_by_word.get("鳥")
            self.assertIsNotNone(note_bird)
            self.assertEqual(note_bird.field_values["Audio"], "https://cdn.example.com/bird.mp3")
            self.assertEqual(note_bird.field_values["Image"], "https://cdn.example.com/b1.png\nhttps://cdn.example.com/b2.png")

    def test_html_and_sound_with_existing_system_files_converts_to_canonical_urls(self):
        with self.app.app_context():
            shared = SharedImageAsset(
                image_key="cat_photo",
                filename="cat_photo.png",
                is_enabled=True,
            )
            db.session.add(shared)

            existing_note = Note(
                note_type_id=self.media_note_type_id,
                user_id=self.user_id,
                deck_id=self.deck_id,
                field_values={"Word": "既存", "Audio": "", "Image": "", "Diagram": ""},
            )
            db.session.add(existing_note)
            db.session.flush()

            media_asset = MediaAsset(
                note_id=existing_note.id,
                field_name="Audio",
                filename="meow.mp3",
                mime_type="audio/mpeg",
                storage_path="/storage/meow.mp3",
                sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            )
            db.session.add(media_asset)
            db.session.commit()
            asset_id = media_asset.id

        csv_data = (
            'Word,Audio,Image\n'
            '猫,<audio src="meow.mp3"></audio>,<img src="cat_photo.png">\n'
            '子猫,[sound:meow.mp3],<img src="cat_photo">\n'
            '子猫2,<p>[sound:meow.mp3]</p>,cat_photo.png\n'
        )
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 3)
        self.assertEqual(result["summary"]["errors"], 0)

        with self.app.app_context():
            notes = Note.query.filter_by(note_type_id=self.media_note_type_id).all()
            notes_by_word = {n.field_values.get("Word"): n for n in notes if isinstance(n.field_values, dict)}

            note1 = notes_by_word.get("猫")
            self.assertIsNotNone(note1)
            self.assertEqual(note1.field_values["Audio"], f"/media/proxy/{asset_id}")
            self.assertEqual(note1.field_values["Image"], "/media/library/cat_photo")

            note2 = notes_by_word.get("子猫")
            self.assertIsNotNone(note2)
            self.assertEqual(note2.field_values["Audio"], f"/media/proxy/{asset_id}")
            self.assertEqual(note2.field_values["Image"], "/media/library/cat_photo")

            note3 = notes_by_word.get("子猫2")
            self.assertIsNotNone(note3)
            self.assertEqual(note3.field_values["Audio"], f"/media/proxy/{asset_id}")
            self.assertEqual(note3.field_values["Image"], "/media/library/cat_photo")

    def test_raw_asset_uuid_rejected(self):
        csv_data = "Word,Audio\n猫,955b645f-e9c7-4e74-a5c4-c3a55f0f1bd7\n"
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 0)
        self.assertEqual(result["summary"]["errors"], 1)
        self.assertTrue(any(
            issue["kind"] == "error"
            and "955b645f-e9c7-4e74-a5c4-c3a55f0f1bd7" in issue["message"]
            for issue in result["issues"]
        ))

        with self.app.app_context():
            notes = Note.query.filter_by(note_type_id=self.media_note_type_id).all()
            self.assertEqual(len(notes), 0)

    def test_canonical_proxy_and_external_urls_accepted(self):
        csv_data = (
            "Word,Audio,Image,Diagram\n"
            "猫,/media/proxy/955b645f-e9c7-4e74-a5c4-c3a55f0f1bd7,"
            "https://cdn.example.com/cat.png,/media/library/cat_diag.png\n"
        )
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 1)
        self.assertEqual(result["summary"]["errors"], 0)

        with self.app.app_context():
            note = Note.query.filter_by(note_type_id=self.media_note_type_id).first()
            self.assertIsNotNone(note)
            self.assertEqual(note.field_values["Audio"], "/media/proxy/955b645f-e9c7-4e74-a5c4-c3a55f0f1bd7")
            self.assertEqual(note.field_values["Image"], "https://cdn.example.com/cat.png")
            self.assertEqual(note.field_values["Diagram"], "/media/library/cat_diag.png")

    def test_static_strokes_accepted_for_image_and_diagram(self):
        csv_data = "Word,Audio,Image,Diagram\n水,,,/static/strokes/kanji/6c34.svg\n"
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 1)
        self.assertEqual(result["summary"]["errors"], 0)

        with self.app.app_context():
            note = Note.query.filter_by(note_type_id=self.media_note_type_id).first()
            self.assertEqual(note.field_values["Diagram"], "/static/strokes/kanji/6c34.svg")

    def test_wrong_media_kind_rejected(self):
        # Audio field should reject image library URL
        csv_data = "Word,Audio\n猫,/media/library/cat.png\n"
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 0)
        self.assertEqual(result["summary"]["errors"], 1)
        self.assertTrue(any(
            issue.get("reason") == "wrong_media_kind" for issue in result["issues"]
        ))

    def test_non_media_fields_unaffected(self):
        # Bare filenames, sound syntax, or HTML in text/richtext/markdown fields should be accepted as plain/rich text
        csv_data = (
            "Word,Description,Notes\n"
            "cat.mp3,<b>[sound:cat.mp3]</b>,<img src=\"cat.png\">\n"
        )
        parsed = self._parse_csv(self.nm_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.nm_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 1)
        self.assertEqual(result["summary"]["errors"], 0)

        with self.app.app_context():
            note = Note.query.filter_by(note_type_id=self.nm_note_type_id).first()
            self.assertIsNotNone(note)
            self.assertEqual(note.field_values["Word"], "cat.mp3")
            self.assertIn("cat.mp3", note.field_values["Description"])
            self.assertIn("cat.png", note.field_values["Notes"])

    def test_empty_optional_media_fields_allowed(self):
        csv_data = "Word,Audio,Image,Diagram\n犬,,,\n"
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 1)
        self.assertEqual(result["summary"]["errors"], 0)

        with self.app.app_context():
            note = Note.query.filter_by(note_type_id=self.media_note_type_id).first()
            self.assertEqual(note.field_values["Audio"], "")
            self.assertEqual(note.field_values["Image"], "")
            self.assertEqual(note.field_values["Diagram"], "")

    def test_multiline_media_field_handling(self):
        # Multiline with all valid canonical URLs
        csv_data = (
            'Word,Audio\n'
            '鳥,"https://cdn.example.com/bird1.mp3\nhttps://cdn.example.com/bird2.mp3"\n'
        )
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(parsed["token"], self.media_note_type_id, parsed["suggested_mapping"])

        self.assertEqual(result["summary"]["inserted"], 1)
        with self.app.app_context():
            note = Note.query.filter_by(note_type_id=self.media_note_type_id).first()
            self.assertEqual(
                note.field_values["Audio"],
                "https://cdn.example.com/bird1.mp3\nhttps://cdn.example.com/bird2.mp3",
            )

        # Multiline where one item is invalid
        csv_data_invalid = (
            'Word,Audio\n'
            '鳥,"https://cdn.example.com/bird1.mp3\nbird2.mp3"\n'
        )
        parsed2 = self._parse_csv(self.media_note_type_id, csv_data_invalid)
        result2 = self._execute_import(parsed2["token"], self.media_note_type_id, parsed2["suggested_mapping"])
        self.assertEqual(result2["summary"]["errors"], 1)

    def test_constant_value_mapping_validation(self):
        csv_data = "Word\n犬\n"
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        token = parsed["token"]

        # Mapping with invalid constant audio value
        invalid_mapping = {
            "Word": {"source_type": "column", "column_index": 0},
            "Audio": {"source_type": "constant", "constant_value": "dog.mp3"},
            "Image": {"source_type": "ignore"},
            "Diagram": {"source_type": "ignore"},
        }
        resp = self.client.post(
            "/api/flashcards/import/execute",
            json={
                "token": token,
                "note_type_id": self.media_note_type_id,
                "target_deck_id": self.deck_id,
                "import_mode": "upsert",
                "uniqueness_fields": ["Word"],
                "mapping": invalid_mapping,
                "confirm_column_mismatch": True,
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Audio", str(resp.get_json()))

        # Mapping with valid canonical constant audio value
        valid_mapping = {
            "Word": {"source_type": "column", "column_index": 0},
            "Audio": {"source_type": "constant", "constant_value": "https://cdn.example.com/default.mp3"},
            "Image": {"source_type": "ignore"},
            "Diagram": {"source_type": "ignore"},
        }
        resp_valid = self.client.post(
            "/api/flashcards/import/execute",
            json={
                "token": token,
                "note_type_id": self.media_note_type_id,
                "target_deck_id": self.deck_id,
                "import_mode": "upsert",
                "uniqueness_fields": ["Word"],
                "mapping": valid_mapping,
                "confirm_column_mismatch": True,
            },
        )
        self.assertEqual(resp_valid.status_code, 200)
        with self.app.app_context():
            note = Note.query.filter_by(note_type_id=self.media_note_type_id).first()
            self.assertEqual(note.field_values["Audio"], "https://cdn.example.com/default.mp3")

    def test_update_mode_prevents_legacy_media_corruption(self):
        # Create existing note with valid canonical media
        with self.app.app_context():
            note = Note(
                note_type_id=self.media_note_type_id,
                user_id=self.user_id,
                deck_id=self.deck_id,
                field_values={
                    "Word": "猫",
                    "Audio": "/media/proxy/original-audio-id",
                    "Image": "/media/proxy/original-image-id",
                    "Diagram": "",
                },
            )
            db.session.add(note)
            db.session.commit()
            note_id = note.id

        # Attempt to update Audio with legacy bare filename
        csv_data = "Word,Audio\n猫,cat-new.mp3\n"
        parsed = self._parse_csv(self.media_note_type_id, csv_data)
        result = self._execute_import(
            parsed["token"],
            self.media_note_type_id,
            parsed["suggested_mapping"],
            mode="update_only",
        )

        self.assertEqual(result["summary"]["updated"], 0)
        self.assertEqual(result["summary"]["errors"], 1)

        # Verify existing note was NOT corrupted
        with self.app.app_context():
            persisted = db.session.get(Note, note_id)
            self.assertEqual(persisted.field_values["Audio"], "/media/proxy/original-audio-id")

        # Now update with valid canonical URL
        csv_valid_update = "Word,Audio\n猫,https://cdn.example.com/cat-new.mp3\n"
        parsed_valid = self._parse_csv(self.media_note_type_id, csv_valid_update)
        result_valid = self._execute_import(
            parsed_valid["token"],
            self.media_note_type_id,
            parsed_valid["suggested_mapping"],
            mode="update_only",
        )
        self.assertEqual(result_valid["summary"]["updated"], 1)

        with self.app.app_context():
            persisted = db.session.get(Note, note_id)
            self.assertEqual(persisted.field_values["Audio"], "https://cdn.example.com/cat-new.mp3")

    def test_batch_import_rejects_legacy_media(self):
        file1 = (
            io.BytesIO("Word,Audio\n猫,cat.mp3\n".encode("utf-8")),
            "batch1.csv",
        )
        resp = self.client.post(
            "/api/flashcards/import/batch/parse",
            data={
                "note_type_id": self.media_note_type_id,
                "parent_deck_id": str(self.deck_id),
                "delimiter_mode": "csv",
                "has_header": "1",
                "files": [file1],
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        parsed = resp.get_json()
        token = parsed["token"]
        file_id = parsed["files"][0]["file_id"]

        exec_resp = self.client.post(
            "/api/flashcards/import/batch/execute",
            json={
                "token": token,
                "note_type_id": self.media_note_type_id,
                "parent_deck_id": self.deck_id,
                "import_mode": "upsert",
                "uniqueness_fields": ["Word"],
                "mapping": parsed["suggested_mapping"],
                "file_configs": [
                    {
                        "file_id": file_id,
                        "action": "create_new",
                        "target_deck_name": "Batch Deck",
                    }
                ],
            },
        )
        self.assertEqual(exec_resp.status_code, 200)
        report = exec_resp.get_json()
        self.assertEqual(report["overall_summary"]["inserted"], 0)
        self.assertEqual(report["overall_summary"]["errors"], 1)
