"""Audio attached while Yomitan updates an existing Note, on disposable MySQL."""
import base64
from datetime import datetime
from pathlib import Path
import tempfile
from unittest.mock import patch

from app.services.connect.actions import add_note
from app.services.connect.base import ConnectError
from app.services.flama_connect_media_service import stage_mp3
from app.services.note_base_context import published_base_write
from models import db
from models.connect_note_ref import ConnectNoteRef
from models.connect_pending_media import ConnectPendingMedia
from models.deck import Deck
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_draft import NoteDraft
from models.note_type import NoteType
from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import attach_template, create_note_user


MP3 = b"ID3\x04\x00\x00\x00\x00\x00\x15" + b"\x00" * 64
FILENAME = "yomitan_audio_b7d03ad2a722daa5711db4a2d96aeefd2cd3a84e.mp3"


class ConnectDuplicateAudioTests(NoteBaseMySQLTestCase):
    APP_CONFIG = {"NOTE_PUBLISHED_BASE_ENABLED": True, "CONNECT_MEDIA_MAX_BYTES": 1024}

    def setUp(self):
        super().setUp()
        self.files = tempfile.TemporaryDirectory(dir=self.media_directory.name)
        self.addCleanup(self.files.cleanup)
        self.app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"] = self.files.name
        self.owner = create_note_user(db.session, username="miner", email="miner@example.invalid")
        self.nt = NoteType(user_id=self.owner.id, name="Mining")
        db.session.add(self.nt)
        db.session.flush()
        self.word = FieldDef(note_type_id=self.nt.id, name="Word", field_type="text", position=0,
                             required=True, identity_role="primary")
        self.sound = FieldDef(note_type_id=self.nt.id, name="Sound", field_type="audio", position=1)
        self.meaning = FieldDef(note_type_id=self.nt.id, name="Meaning", field_type="text", position=2)
        self.deck = Deck(owner_user_id=self.owner.id, note_type_id=self.nt.id, name="Inbox")
        db.session.add_all([self.word, self.sound, self.meaning, self.deck])
        attach_template(db.session, note_type_id=self.nt.id, owner_user_id=self.owner.id,
                        name="Card", front_html="{{Word}}", back_html="{{Meaning}}")
        db.session.flush()
        self.note = Note(user_id=self.owner.id, note_type_id=self.nt.id, deck_id=self.deck.id,
                         field_values={"Word": "犬", "Sound": "", "Meaning": "dog"})
        db.session.add(self.note)
        db.session.commit()

    def stage(self):
        stage_mp3(user_id=self.owner.id, filename=FILENAME, data=base64.b64encode(MP3).decode())
        pending = ConnectPendingMedia.query.one()
        path = Path(self.files.name, pending.storage_path)
        self.assertTrue(path.is_file())
        return path

    def payload(self, *, audio=True):
        return {"deckName": "Inbox", "modelName": "Mining", "options": {"allowDuplicate": False},
                "fields": {"Word": "犬", "Sound": f"[sound:{FILENAME}]" if audio else "", "Meaning": "hound"}}

    def test_duplicate_update_attaches_audio_to_existing_note_and_removes_staging(self):
        staged_path = self.stage()
        note_id = self.note.id
        ref_id = add_note(self.owner.id, self.payload())
        self.assertEqual(db.session.get(ConnectNoteRef, ref_id).note_id, note_id)
        self.assertEqual(Note.query.count(), 1)
        asset = MediaAsset.query.one()
        self.assertEqual(asset.note_id, note_id)
        self.assertEqual(asset.field_name, "Sound")
        self.assertEqual(self.note.field_values["Sound"], f"/media/proxy/{asset.id}")
        self.assertEqual(Path(self.files.name, asset.storage_path).read_bytes(), MP3)
        self.assertEqual(ConnectPendingMedia.query.count(), 0)
        self.assertFalse(staged_path.exists())

    def test_published_note_audio_update_stays_in_author_draft(self):
        with published_base_write():
            self.note.published_at = datetime.utcnow()
            db.session.flush()
        db.session.commit()
        base = dict(self.note.field_values_by_id)
        self.stage()
        add_note(self.owner.id, self.payload())
        asset = MediaAsset.query.one()
        self.assertEqual(self.note.field_values_by_id, base)
        draft = db.session.get(NoteDraft, self.note.id)
        self.assertIsNotNone(draft)
        self.assertEqual(self.note.field_values["Sound"], f"/media/proxy/{asset.id}")

    def test_later_failure_rolls_back_note_and_asset_and_keeps_staged_audio(self):
        staged_path = self.stage()
        with patch("app.services.connect.actions._ensure_note_ref", side_effect=ConnectError("ref failed")):
            with self.assertRaisesRegex(ConnectError, "ref failed"):
                add_note(self.owner.id, self.payload())
        self.assertEqual(self.note.field_values["Sound"], "")
        self.assertEqual(self.note.field_values["Meaning"], "dog")
        self.assertEqual(MediaAsset.query.count(), 0)
        self.assertEqual(ConnectPendingMedia.query.count(), 1)
        self.assertEqual({p for p in Path(self.files.name).rglob("*") if p.is_file()}, {staged_path})

    def test_text_only_duplicate_update_leaves_unreferenced_staged_audio_alone(self):
        staged_path = self.stage()
        add_note(self.owner.id, self.payload(audio=False))
        self.assertEqual(self.note.field_values["Meaning"], "hound")
        self.assertEqual(MediaAsset.query.count(), 0)
        self.assertEqual(ConnectPendingMedia.query.count(), 1)
        self.assertTrue(staged_path.is_file())
