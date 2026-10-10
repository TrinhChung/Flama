"""Standard wire contracts and mining transactions, alongside legacy callers."""

import base64
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import UUID

from tests import test_flama_connect as legacy_fixture
_MIN_MP3_BYTES = legacy_fixture._MIN_MP3_BYTES
_MIN_PNG_BYTES = legacy_fixture._MIN_PNG_BYTES
from app.services import user_api_token_service as tokens
from app.services.connect.mining_setup import prepare_sentence_mining
from app.connect.protocol import encode_result
from models import db
from models.card import Card
from models.connect_note_ref import ConnectNoteRef
from models.connect_pending_media import ConnectPendingMedia
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


class ConnectProtocolTests(unittest.TestCase):
    # Reuse the closest suite's database setup without inheriting its tests.
    setUpClass = classmethod(legacy_fixture.FlamaConnectTests.setUpClass.__func__)
    tearDownClass = classmethod(legacy_fixture.FlamaConnectTests.tearDownClass.__func__)
    tearDown = legacy_fixture.FlamaConnectTests.tearDown

    def setUp(self):
        legacy_fixture.FlamaConnectTests.setUp(self)
        self.app.config.update(CONNECT_ANKI_ADAPTER_ENABLED=True,
                               CONNECT_ANKI_MEDIA_ENABLED=True,
                               CONNECT_VERSIONED_PROTOCOL_ENABLED=False,
                               CONNECT_RATE_LIMIT_BACKEND="local",
                               CONNECT_ANKI_ALLOWED_ORIGINS=("https://killergerbah.github.io",),
                               CONNECT_ANKI_STORAGE_MAX_BYTES=512 * 1024 * 1024,
                               CONNECT_ANKI_MEDIA_MAX_BYTES=2 * 1024 * 1024,
                               CONNECT_ANKI_MAX_CONTENT_LENGTH=6 * 1024 * 1024)
        with self.app.app_context():
            prepare_sentence_mining(self.user_id)
            issued = tokens.issue_token(user_id=self.user_id, name="asbplayer", preset="mining-media")
            self.mining_key = issued.plaintext
            db.session.commit()

    def note(self, sentence="猫がいる。", **extra):
        return {"deckName": "Sentences", "modelName": "Sentence Card",
                "fields": {"Sentence": sentence, "Definition": "There is a cat."},
                "tags": ["asbplayer"], "options": {"allowDuplicate": True,
                "duplicateScope": "deck", "duplicateScopeOptions": {"deckName": "Sentences", "checkChildren": False}}, **extra}

    def rpc(self, action, params=None, *, version=6, key=None, headers=None, content_type="text/plain; charset=UTF-8"):
        payload = {"action": action, "key": self.mining_key if key is None else key}
        if version is not None:
            payload["version"] = version
        if params is not None:
            payload["params"] = params
        return self.client.post("/v1/anki-connect", data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                content_type=content_type, headers=headers or {})

    def issue_limited(self, preset="mining-text", scopes=None):
        with self.app.app_context():
            issued = tokens.issue_token(user_id=self.user_id, name="limited", preset=preset, scopes=scopes)
            db.session.commit()
            return issued.plaintext

    def files(self):
        return [path for path in Path(self.upload_tmp.name).rglob("*") if path.is_file()]

    def inline(self, kind="audio", filename="asbp_clip.mp3", content=_MIN_MP3_BYTES, field="Audio"):
        return {kind: {"filename": filename, "data": base64.b64encode(content).decode(), "fields": [field]}}

    def test_version_contract_matrix_and_default(self):
        for version in range(2, 7):
            with self.subTest(version=version):
                value = self.rpc("version", version=version).get_json()
                self.assertEqual(value, 6 if version < 5 else {"result": 6, "error": None})
        self.assertEqual(self.rpc("version", version=None).get_json(), 6)
        self.assertEqual(self.rpc("version", content_type=None).get_json(), {"result": 6, "error": None})
        for version in (True, 7, 1, "6"):
            self.assertIsNotNone(self.rpc("version", version=version).get_json()["error"])

    def test_result_shapes_and_error_envelopes_across_versions(self):
        for version in range(2, 7):
            for value in (None, 7, [], [1, 2], {"fields": ["Sentence"]}):
                expected = value if version < 5 else {"result": value, "error": None}
                self.assertEqual(encode_result(value, version=version), expected)
            self.assertEqual(encode_result(error="duplicate", version=version), {"result": None, "error": "duplicate"})

    def test_media_flag_and_expiry_are_enforced(self):
        self.app.config["CONNECT_ANKI_MEDIA_ENABLED"] = False
        self.assertIsNotNone(self.rpc("addNote", {"note": self.note(**self.inline())}).get_json()["error"])
        reflected = self.rpc("apiReflect", {"scopes": ["actions"]}).get_json()["result"]
        self.assertNotIn("storeMediaFile", reflected["actions"])
        self.app.config["CONNECT_ANKI_MEDIA_ENABLED"] = True
        params = self.inline()["audio"]
        params.pop("fields")
        self.rpc("storeMediaFile", params)
        with self.app.app_context():
            ConnectPendingMedia.query.one().expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.session.commit()
        note = self.note()
        note["fields"]["Audio"] = "[sound:asbp_clip.mp3]"
        self.assertIsNotNone(self.rpc("addNote", {"note": note}).get_json()["error"])

    def test_cleanup_reclaims_expiry_and_crash_leftovers_only(self):
        params = self.inline()["audio"]
        params.pop("fields")
        self.rpc("storeMediaFile", params)
        self.rpc("addNote", {"note": self.note(**self.inline())})
        with self.app.app_context():
            row = ConnectPendingMedia.query.one()
            expired_path = Path(self.upload_tmp.name) / row.storage_path
            row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            asset_path = Path(self.upload_tmp.name) / MediaAsset.query.one().storage_path
            db.session.commit()
        managed = Path(self.upload_tmp.name) / "connect_mined" / "crash"
        managed.mkdir(parents=True)
        orphan = managed / ("a" * 32 + "_" + "b" * 12 + ".mp3")
        orphan.write_bytes(_MIN_MP3_BYTES)
        os.utime(orphan, (1, 1))
        unrelated = Path(self.upload_tmp.name) / "other.mp3"
        unrelated.write_bytes(_MIN_MP3_BYTES)
        result = self.app.test_cli_runner().invoke(args=["cleanup-connect-media"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(orphan.exists())
        self.assertFalse(expired_path.exists())
        self.assertTrue(asset_path.exists())
        self.assertTrue(unrelated.exists())

    def test_parser_rejects_ambiguity_and_non_utf8(self):
        for raw in (b'{"action":"version","action":"addNote"}',
                    b'{"action":"version","params":null}',
                    b'{"action":"version","params":{"x":NaN}}',
                    b'{"action":"version","key":"\xff"}'):
            with self.subTest(raw=raw):
                result = self.client.post("/v1/anki-connect", data=raw, content_type="text/plain").get_json()
                self.assertIsNotNone(result["error"])
        self.assertIsNotNone(self.rpc("version", content_type="text/plain; charset=latin1").get_json()["error"])
        self.assertIsNotNone(self.rpc("version", headers={"Content-Encoding": "gzip"}).get_json()["error"])

    def test_auth_origin_and_feature_gate_prevent_writes(self):
        self.assertEqual(self.rpc("addNote", {"note": self.note()}, key="bad").status_code, 401)
        for origin in ("https://unapproved.example", "null"):
            response = self.rpc("addNote", {"note": self.note()}, headers={"Origin": origin})
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        response = self.rpc("version", headers={"Origin": "https://killergerbah.github.io"})
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "https://killergerbah.github.io")
        self.app.config["CONNECT_ANKI_ADAPTER_ENABLED"] = False
        self.assertEqual(self.rpc("addNote", {"note": self.note()}).status_code, 404)
        with self.app.app_context():
            self.assertEqual(Note.query.count(), 0)

    def test_conflicting_credentials_and_nested_scopes(self):
        other = self.issue_limited()
        self.assertEqual(self.rpc("version", headers={"Authorization": f"Bearer {other}"}).status_code, 401)
        self.assertEqual(self.rpc("version", key="é", headers={"Authorization": f"Bearer {other}"}).status_code, 401)
        limited = self.issue_limited(scopes=["note:check"])
        response = self.rpc("multi", {"actions": [{"action": "deckNames"}]}, key=limited)
        self.assertEqual(response.status_code, 403)

    def test_nested_version_encoding_and_mutation_rejection(self):
        response = self.rpc("multi", {"actions": [{"action": "version"}, {"action": "version", "version": 6}]}).get_json()
        self.assertEqual(response, {"result": [6, {"result": 6, "error": None}], "error": None})
        for item in ({"action": "multi", "params": {"actions": []}},
                     {"action": "addNote", "params": {"note": self.note()}},
                     {"action": "version", "key": "other"},
                     {"action": "version", "version": 7}):
            self.assertIsNotNone(self.rpc("multi", {"actions": [item]}).get_json()["error"])

    def test_sentence_add_without_word_and_stable_numeric_ref(self):
        result = self.rpc("addNote", {"note": self.note()}).get_json()
        self.assertIsNone(result["error"])
        self.assertIsInstance(result["result"], int)
        with self.app.app_context():
            note = Note.query.one()
            UUID(note.id)
            self.assertEqual(Card.query.filter_by(note_id=note.id).count(), 1)
            self.assertEqual(ConnectNoteRef.query.one().id, result["result"])
        query = '"deck:Sentences" "Sentence:猫がいる。"'
        self.assertEqual(self.rpc("findNotes", {"query": query}).get_json()["result"], [result["result"]])

    def test_standard_duplicates_create_or_reject_without_upsert(self):
        first = self.rpc("addNote", {"note": self.note()}).get_json()["result"]
        second = self.rpc("addNote", {"note": self.note()}).get_json()["result"]
        self.assertNotEqual(first, second)
        note = self.note()
        note["options"]["allowDuplicate"] = False
        note["fields"]["Definition"] = "do not overwrite"
        self.assertIn("duplicate", self.rpc("addNote", {"note": note}).get_json()["error"])
        with self.app.app_context():
            self.assertEqual(Note.query.count(), 2)
            self.assertTrue(all(row.field_values["Definition"] == "There is a cat." for row in Note.query.all()))

    def test_collection_duplicate_scope_and_unsupported_options(self):
        self.rpc("addNote", {"note": self.note()})
        note = self.note()
        note.update(deckName="Second", options={"allowDuplicate": False, "duplicateScope": "collection"})
        self.assertIn("duplicate", self.rpc("addNote", {"note": note}).get_json()["error"])
        note["options"] = {"allowDuplicate": False, "duplicateScope": "deck"}
        self.assertIsNone(self.rpc("addNote", {"note": note}).get_json()["error"])
        note["options"]["duplicateScopeOptions"] = {"checkChildren": True}
        self.assertIn("unsupported", self.rpc("addNote", {"note": note}).get_json()["error"])

    def test_legacy_wire_and_upsert_scope_remain_independent(self):
        payload = {"action": "addNote", "version": 6, "key": self.issue_limited(), "params": {"note": legacy_fixture.FlamaConnectTests._note(self)}}
        created = self.client.post("/v1/flama-connect", json=payload).get_json()
        self.assertIsInstance(created, int)
        payload["params"]["note"]["fields"]["Meaning"] = "new value"
        self.assertIn("note:update", self.client.post("/v1/flama-connect", json=payload).get_json()["error"])
        payload["key"] = self.token
        # The facade still supports old callers; protocol cutover changes only encoding.
        self.app.config["CONNECT_VERSIONED_PROTOCOL_ENABLED"] = True
        updated = self.client.post("/v1/flama-connect", json=payload).get_json()
        self.assertEqual(updated, {"result": created, "error": None})

    def test_inline_audio_and_image_use_owned_proxy_assets(self):
        note = self.note(**self.inline())
        note.update(self.inline("picture", "asbp_shot.png", _MIN_PNG_BYTES, "Image"))
        response = self.rpc("addNote", {"note": note}).get_json()
        self.assertIsNone(response["error"], response)
        with self.app.app_context():
            stored = Note.query.one()
            assets = {row.field_name: row for row in MediaAsset.query.all()}
            self.assertEqual(set(assets), {"Audio", "Image"})
            for name, asset in assets.items():
                self.assertEqual(stored.field_values[name], f"/media/proxy/{asset.id}")
                self.assertTrue((Path(self.upload_tmp.name) / asset.storage_path).exists())
            self.assertEqual(ConnectPendingMedia.query.count(), 0)

    def test_text_token_cannot_attach_or_stage_media(self):
        key = self.issue_limited()
        response = self.rpc("addNote", {"note": self.note(**self.inline())}, key=key)
        self.assertEqual(response.status_code, 403)
        stage = self.inline()["audio"]
        stage.pop("fields")
        self.assertEqual(self.rpc("storeMediaFile", stage, key=key).status_code, 403)
        self.assertEqual(self.files(), [])

    def test_staged_media_is_owned_typed_and_consumed(self):
        params = self.inline("picture", "asbp_img.png", _MIN_PNG_BYTES, "Image")["picture"]
        params.pop("fields")
        params["deleteExisting"] = False
        self.assertEqual(self.rpc("storeMediaFile", params).get_json()["result"], "asbp_img.png")
        with self.app.app_context():
            prepare_sentence_mining(self.other_user_id)
            other_key = tokens.issue_token(user_id=self.other_user_id, name="other", preset="mining-media").plaintext
            db.session.commit()
        other_note = self.note()
        other_note["fields"]["Image"] = "asbp_img.png"
        self.assertIn("not found", self.rpc("addNote", {"note": other_note}, key=other_key).get_json()["error"])
        note = self.note()
        note["fields"]["Audio"] = "[sound:asbp_img.png]"
        self.assertIsNotNone(self.rpc("addNote", {"note": note}).get_json()["error"])
        note["fields"].pop("Audio")
        note["fields"]["Image"] = '<img src="asbp_img.png">'
        self.assertIsNone(self.rpc("addNote", {"note": note}).get_json()["error"])
        with self.app.app_context():
            self.assertEqual(ConnectPendingMedia.query.count(), 0)
            self.assertEqual(MediaAsset.query.count(), 1)

    def test_standard_clone_addition_preserves_source(self):
        with self.app.app_context():
            source_type = NoteType(user_id=self.other_user_id, name="Source Sentence")
            db.session.add(source_type)
            db.session.flush()
            db.session.add(FieldDef(note_type_id=source_type.id, name="Sentence", field_type="text", required=True, identity_role="primary"))
            db.session.add(Template(note_type_id=source_type.id, name="Source", front_html="{{Sentence}}", back_html="{{Sentence}}"))
            own_type = NoteType.query.filter_by(user_id=self.user_id, name="Sentence Card").one()
            source_deck = Deck(owner_user_id=self.other_user_id, name="Source", note_type_id=source_type.id)
            local_deck = Deck(owner_user_id=self.user_id, name="Installed", note_type_id=own_type.id)
            db.session.add_all([source_deck, local_deck])
            db.session.flush()
            source = Note(user_id=self.other_user_id, note_type_id=source_type.id, deck_id=source_deck.id, field_values={"Sentence": "source sentence"})
            item = DeckMarketplaceItem(owner_user_id=self.other_user_id, source_deck_id=source_deck.id, source_note_type_id=source_type.id, title="Source")
            db.session.add_all([source, item])
            db.session.flush()
            install = DeckInstall(deck_item_id=item.id, user_id=self.user_id, local_deck_id=local_deck.id,
                                  clone_mode="logical_overlay", source_deck_id=source_deck.id,
                                  source_note_type_id=source_type.id, source_owner_user_id=self.other_user_id,
                                  base_snapshot_at=datetime.utcnow() + timedelta(seconds=1))
            db.session.add(install)
            db.session.flush()
            db.session.add(DeckCloneDeckMap(deck_install_id=install.id, local_deck_id=local_deck.id, source_deck_id=source_deck.id))
            db.session.commit()
            source_id, install_id, local_id = source.id, install.id, local_deck.id
        note = self.note("new clone sentence", **self.inline())
        note["deckName"] = "Installed"
        note["options"]["duplicateScopeOptions"]["deckName"] = "Installed"
        self.assertIsNone(self.rpc("addNote", {"note": note}).get_json()["error"])
        duplicate = self.note("source sentence")
        duplicate["deckName"] = "Installed"
        duplicate["options"] = {"allowDuplicate": False, "duplicateScope": "deck"}
        self.assertIn("duplicate", self.rpc("addNote", {"note": duplicate}).get_json()["error"])
        with self.app.app_context():
            added = DeckCloneAddedNote.query.filter_by(deck_install_id=install_id).one()
            self.assertEqual(added.note.deck_id, local_id)
            self.assertEqual(added.note.user_id, self.user_id)
            self.assertEqual(db.session.get(Note, source_id).field_values, {"Sentence": "source sentence"})
            self.assertEqual(MediaAsset.query.one().note_id, added.note_id)

    def test_media_payload_rejections_leave_no_files(self):
        for extra in (self.inline(filename="../clip.mp3"), self.inline(field="Sentence"),
                      self.inline(content=_MIN_PNG_BYTES),
                      {"audio": {"url": "https://example.com/a.mp3", "filename": "a.mp3", "fields": ["Audio"]}},
                      {"video": {"filename": "a.webm", "data": "AAAA", "fields": ["Image"]}}):
            with self.subTest(extra=extra):
                self.assertIsNotNone(self.rpc("addNote", {"note": self.note(**extra)}).get_json()["error"])
        self.assertEqual(self.files(), [])

    def test_media_commit_failure_compensates_files_and_rows(self):
        with patch.object(db.session, "commit", side_effect=RuntimeError("injected commit failure")):
            response = self.rpc("addNote", {"note": self.note(**self.inline())})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.files(), [])
        with self.app.app_context():
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(MediaAsset.query.count(), 0)
            self.assertEqual(ConnectNoteRef.query.count(), 0)

    def test_staging_failure_compensates_and_storage_limit_rejects(self):
        params = self.inline()["audio"]
        params.pop("fields")
        with patch.object(db.session, "commit", side_effect=RuntimeError("injected failure")):
            self.assertEqual(self.rpc("storeMediaFile", params).status_code, 500)
        self.assertEqual(self.files(), [])
        self.app.config["CONNECT_ANKI_STORAGE_MAX_BYTES"] = 1
        self.assertIsNotNone(self.rpc("addNote", {"note": self.note(**self.inline())}).get_json()["error"])
        self.assertEqual(self.files(), [])

    def test_size_rate_and_shared_backend_errors_are_json(self):
        self.app.config["CONNECT_ANKI_MAX_CONTENT_LENGTH"] = 10
        self.assertEqual(self.rpc("version").status_code, 413)
        self.app.config["CONNECT_ANKI_MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024
        with patch("app.connect.request_pipeline.rate_allowed", return_value=False):
            response = self.rpc("version")
            self.assertEqual(response.status_code, 429)
            self.assertIsNotNone(response.get_json()["error"])
            self.assertIn("Retry-After", response.headers)
        self.app.config["CONNECT_RATE_LIMIT_BACKEND"] = "redis"
        with patch("app.services.connect.rate_limit.shared.redis_client", side_effect=RuntimeError("offline")):
            self.assertEqual(self.rpc("version").status_code, 503)

    def test_setup_is_idempotent_and_rotation_preserves_scope(self):
        with self.app.app_context():
            self.assertEqual(prepare_sentence_mining(self.user_id), prepare_sentence_mining(self.user_id))
            token = tokens.authenticate_token(self.mining_key)[0]
            rotated = tokens.rotate_token(user_id=self.user_id, token_id=token.id)
            self.assertEqual(tokens.parse_scopes(rotated.record), frozenset(tokens.TOKEN_PRESETS["mining-media"]))


if __name__ == "__main__":
    unittest.main()
