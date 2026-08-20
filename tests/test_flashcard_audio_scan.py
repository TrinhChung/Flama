"""Tests for flashcard deck audio scan service and API."""

from pathlib import Path
import tempfile
import unittest

from app import create_app
from app.services.flashcard_audio_scan_service import infer_auto_mappings, scan_deck_audio
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


class FlashcardAudioScanTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_root = Path(self.temp_dir.name)

        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": str(self.upload_root),
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            user = User(username="audiotester", email="audio@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            # Create Deck
            deck = Deck(name="Minna No Nihongo N5", owner_user_id=self.user_id, position=0)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id

            # Create NoteType with auto-detectable audio fields
            note_type = NoteType(name="Japanese Vocab", user_id=self.user_id)
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            f_front = FieldDef(note_type_id=self.note_type_id, name="Front", field_type="text", position=0)
            f_front_audio = FieldDef(note_type_id=self.note_type_id, name="FrontAudio", field_type="audio", position=1)
            f_reading = FieldDef(note_type_id=self.note_type_id, name="Reading", field_type="text", position=2)
            f_reading_audio = FieldDef(note_type_id=self.note_type_id, name="Reading_audio", field_type="audio", position=3)
            f_vi = FieldDef(note_type_id=self.note_type_id, name="Vietnamese", field_type="text", position=4)
            f_vi_audio = FieldDef(note_type_id=self.note_type_id, name="VietnameseAudio", field_type="audio", position=5)
            db.session.add_all([f_front, f_front_audio, f_reading, f_reading_audio, f_vi, f_vi_audio])

            tmpl = Template(note_type_id=self.note_type_id, name="Card 1", front_html="{{Front}}", back_html="{{Back}}")
            db.session.add(tmpl)
            db.session.flush()
            self.template_id = tmpl.id

            # Note 1: Missing audio
            n1 = Note(
                note_type_id=self.note_type_id,
                user_id=self.user_id,
                deck_id=self.deck_id,
                field_values={"Front": "食べる", "Reading": "たべる", "Vietnamese": "Ăn"},
            )
            db.session.add(n1)
            db.session.flush()
            c1 = Card(note_id=n1.id, template_id=self.template_id)
            db.session.add(c1)

            # Note 2: Valid audio file on disk
            n2 = Note(
                note_type_id=self.note_type_id,
                user_id=self.user_id,
                deck_id=self.deck_id,
                field_values={"Front": "飲む", "Reading": "のむ", "Vietnamese": "Uống", "FrontAudio": "valid_audio.wav"},
            )
            db.session.add(n2)
            db.session.flush()
            c2 = Card(note_id=n2.id, template_id=self.template_id)
            db.session.add(c2)

            media_file = self.upload_root / f"{self.user_id}" / n2.id / "valid_audio.wav"
            media_file.parent.mkdir(parents=True, exist_ok=True)
            media_file.write_bytes(b"RIFF....WAVEfmt ....")

            asset_valid = MediaAsset(
                note_id=n2.id,
                field_name="FrontAudio",
                filename="valid_audio.wav",
                mime_type="audio/wav",
                storage_path=f"{self.user_id}/{n2.id}/valid_audio.wav",
                sha256="dummy_sha256",
                size_bytes=len(b"RIFF....WAVEfmt ...."),
            )
            db.session.add(asset_valid)

            # Note 3: Broken audio (recorded in DB but missing on disk)
            n3 = Note(
                note_type_id=self.note_type_id,
                user_id=self.user_id,
                deck_id=self.deck_id,
                field_values={"Front": "行く", "Reading": "いく", "Vietnamese": "Đi", "FrontAudio": "broken.wav"},
            )
            db.session.add(n3)
            db.session.flush()
            c3 = Card(note_id=n3.id, template_id=self.template_id)
            db.session.add(c3)

            asset_broken = MediaAsset(
                note_id=n3.id,
                field_name="FrontAudio",
                filename="broken.wav",
                mime_type="audio/wav",
                storage_path=f"{self.user_id}/{n3.id}/broken.wav",
                sha256="broken_sha256",
                size_bytes=100,
            )
            db.session.add(asset_broken)

            db.session.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_infer_auto_mappings(self):
        with self.app.app_context():
            field_defs = FieldDef.query.filter_by(note_type_id=self.note_type_id).all()
            mappings = infer_auto_mappings(field_defs)

            mapping_dict = {m["destination_field"]: m["source_field"] for m in mappings}
            self.assertEqual(mapping_dict.get("FrontAudio"), "Front")
            self.assertEqual(mapping_dict.get("Reading_audio"), "Reading")
            self.assertEqual(mapping_dict.get("VietnameseAudio"), "Vietnamese")

    def test_scan_deck_audio_service(self):
        with self.app.app_context():
            result = scan_deck_audio(
                user_id=self.user_id,
                deck_id=self.deck_id,
                admin_mode=False,
                upload_root=self.upload_root,
            )

            self.assertEqual(result["total_notes"], 3)
            self.assertEqual(result["deck"]["name"], "Minna No Nihongo N5")
            self.assertGreaterEqual(len(result["auto_mappings"]), 3)

            # Check individual note statuses
            notes_by_word = {n["word"]: n for n in result["notes"]}
            self.assertIn("食べる", notes_by_word)
            self.assertIn("飲む", notes_by_word)
            self.assertIn("行く", notes_by_word)

            # Note 1: Missing audio
            n1_status = notes_by_word["食べる"]["audio_status"]["FrontAudio"]["status"]
            self.assertEqual(n1_status, "missing")
            self.assertTrue(notes_by_word["食べる"]["needs_audio"])

            # Note 2: Valid audio
            n2_status = notes_by_word["飲む"]["audio_status"]["FrontAudio"]["status"]
            self.assertEqual(n2_status, "valid")

            # Note 3: Broken audio
            n3_status = notes_by_word["行く"]["audio_status"]["FrontAudio"]["status"]
            self.assertEqual(n3_status, "broken")
            self.assertTrue(notes_by_word["行く"]["needs_audio"])

    def test_scan_deck_audio_api(self):
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess["_user_id"] = str(self.user_id)
                sess["_fresh"] = True

            resp = self.client.post(
                "/api/flashcards/audio/deck-scan",
                json={"deck_id": self.deck_id},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data["total_notes"], 3)
            self.assertEqual(data["deck"]["id"], self.deck_id)
            self.assertIn("auto_mappings", data)
            self.assertIn("summary", data)


if __name__ == "__main__":
    unittest.main()
