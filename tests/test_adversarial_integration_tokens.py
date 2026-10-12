"""Empirical adversarial test suite for integration tokens and sentence mining setup."""

from __future__ import annotations

import unittest

from app import create_app
from app.services import user_api_token_service
from models import db
from models.deck import Deck
from models.field_def import FieldDef
from models.note_type import NoteType
from models.template import Template
from models.user import User
from models.user_api_token import UserApiToken


class AdversarialIntegrationTokenTests(unittest.TestCase):
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
            user = User(username="test-user", email="test@example.com", is_admin=False)
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

        self.client.post("/login", data={"email": "test@example.com", "password": "password123"})

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_sentence_mining_setup_canonical_return_and_idempotence(self):
        """Verify POST /api/integration-tokens/sentence-mining-setup returns exact 7 canonical fields and is idempotent."""
        res1 = self.client.post("/api/integration-tokens/sentence-mining-setup", json={})
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        self.assertEqual(data1["deckName"], "Sentences")
        self.assertEqual(data1["modelName"], "Sentence Card")
        expected_fields = ["Sentence", "Word", "Definition", "Image", "Audio", "Source", "URL"]
        self.assertEqual(data1["fields"], expected_fields)

        # Verify underlying database entities
        with self.app.app_context():
            note_type = NoteType.query.filter_by(user_id=self.user_id, name="Sentence Card").first()
            self.assertIsNotNone(note_type)
            deck = Deck.query.filter_by(owner_user_id=self.user_id, name="Sentences").first()
            self.assertIsNotNone(deck)
            self.assertEqual(deck.note_type_id, note_type.id)

            field_names = [f.name for f in note_type.field_defs]
            self.assertEqual(field_names, expected_fields)

            # Check field types and primary role
            field_map = {f.name: f for f in note_type.field_defs}
            self.assertEqual(field_map["Sentence"].field_type, "text")
            self.assertEqual(field_map["Sentence"].identity_role, "primary")
            self.assertTrue(field_map["Sentence"].required)
            self.assertEqual(field_map["Image"].field_type, "image")
            self.assertFalse(field_map["Image"].required)
            self.assertEqual(field_map["Audio"].field_type, "audio")
            self.assertFalse(field_map["Audio"].required)

        # Call setup again - MUST be idempotent (status 200, no duplicates)
        res2 = self.client.post("/api/integration-tokens/sentence-mining-setup", json={})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2, data1)

        with self.app.app_context():
            self.assertEqual(NoteType.query.filter_by(user_id=self.user_id, name="Sentence Card").count(), 1)
            self.assertEqual(Deck.query.filter_by(owner_user_id=self.user_id, name="Sentences").count(), 1)

    def test_sentence_mining_setup_conflict_handling(self):
        """Verify setup fails cleanly (HTTP 400) if user has incompatible model or deck."""
        # Case 1: Corrupt Sentence Card model (missing required primary Sentence)
        with self.app.app_context():
            bad_nt = NoteType(user_id=self.user_id, name="Sentence Card")
            db.session.add(bad_nt)
            db.session.flush()
            # Wrong field type for Sentence
            db.session.add(FieldDef(note_type_id=bad_nt.id, name="Sentence", field_type="image", required=True))
            db.session.commit()

        res = self.client.post("/api/integration-tokens/sentence-mining-setup", json={})
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.get_json())

    def test_token_creation_presets_and_scopes(self):
        """Verify mining-text and mining-media preset creation and exact scopes."""
        # 1. mining-text
        res_text = self.client.post("/api/integration-tokens", json={"name": "asb-text", "preset": "mining-text"})
        self.assertEqual(res_text.status_code, 201)
        item_text = res_text.get_json()["item"]
        self.assertEqual(item_text["preset"], "mining-text")
        expected_text_scopes = sorted(["deck:read", "note-type:read", "note:check", "note:create"])
        self.assertEqual(sorted(item_text["scopes"]), expected_text_scopes)
        self.assertNotIn("media:write", item_text["scopes"])

        # 2. mining-media
        res_media = self.client.post("/api/integration-tokens", json={"name": "asb-media", "preset": "mining-media"})
        self.assertEqual(res_media.status_code, 201)
        item_media = res_media.get_json()["item"]
        self.assertEqual(item_media["preset"], "mining-media")
        expected_media_scopes = sorted(["deck:read", "note-type:read", "note:check", "note:create", "media:write"])
        self.assertEqual(sorted(item_media["scopes"]), expected_media_scopes)

        # 3. Verify scope enforcement during authentication
        raw_text_token = item_text["token"]
        raw_media_token = item_media["token"]

        with self.app.app_context():
            # mining-text token CAN create notes
            self.assertIsNotNone(user_api_token_service.authenticate_token(raw_text_token, required_scope="note:create"))
            # mining-text token CANNOT write media
            self.assertIsNone(user_api_token_service.authenticate_token(raw_text_token, required_scope="media:write"))
            # mining-media token CAN write media
            self.assertIsNotNone(user_api_token_service.authenticate_token(raw_media_token, required_scope="media:write"))

    def test_token_rotation_preserves_scopes_and_revokes_old(self):
        """Verify rotating a mining-media token preserves scopes and invalidates old token."""
        created = self.client.post("/api/integration-tokens", json={"name": "rot-test", "preset": "mining-media"}).get_json()["item"]
        old_token = created["token"]
        old_id = created["id"]

        rotated_res = self.client.post(f"/api/integration-tokens/{old_id}/rotate", json={})
        self.assertEqual(rotated_res.status_code, 201)
        rotated_item = rotated_res.get_json()["item"]
        new_token = rotated_item["token"]
        new_id = rotated_item["id"]

        self.assertNotEqual(old_token, new_token)
        self.assertNotEqual(old_id, new_id)
        self.assertEqual(rotated_item["preset"], "mining-media")
        self.assertEqual(sorted(rotated_item["scopes"]), sorted(created["scopes"]))

        # Verify old token is revoked and cannot be used
        with self.app.app_context():
            self.assertIsNone(user_api_token_service.authenticate_token(old_token))
            self.assertIsNotNone(user_api_token_service.authenticate_token(new_token))

    def test_token_revocation_lifecycle(self):
        """Verify token revocation stops authentication and sets revoked status."""
        created = self.client.post("/api/integration-tokens", json={"name": "rev-test", "preset": "mining-text"}).get_json()["item"]
        token_str = created["token"]
        token_id = created["id"]

        del_res = self.client.delete(f"/api/integration-tokens/{token_id}")
        self.assertEqual(del_res.status_code, 204)

        # Deleting non-existent token returns 404
        del_again = self.client.delete("/api/integration-tokens/999999")
        self.assertEqual(del_again.status_code, 404)

        # Listed token shows status revoked
        listed = self.client.get("/api/integration-tokens").get_json()["items"]
        rev_item = next(t for t in listed if t["id"] == token_id)
        self.assertEqual(rev_item["status"], "revoked")

        # Authenticate fails
        with self.app.app_context():
            self.assertIsNone(user_api_token_service.authenticate_token(token_str))

    def test_active_token_limit_enforcement(self):
        """Verify user cannot exceed MAX_ACTIVE_TOKENS_PER_USER (10)."""
        for i in range(10):
            res = self.client.post("/api/integration-tokens", json={"name": f"Token {i}", "preset": "mining-text"})
            self.assertEqual(res.status_code, 201)

        # 11th token should fail with 400
        res11 = self.client.post("/api/integration-tokens", json={"name": "Token 11", "preset": "mining-text"})
        self.assertEqual(res11.status_code, 400)
        self.assertIn("maximum number of active integration tokens", res11.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
