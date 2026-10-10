from __future__ import annotations

import unittest

from app import create_app
from models import db
from models.user import User
from models.user_api_token import UserApiToken
from models.field_def import FieldDef
from models.note_type import NoteType


class IntegrationTokenApiTests(unittest.TestCase):
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
            user = User(username="regular-user", email="regular@example.com", is_admin=False)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
        self.client.post("/login", data={"email": "regular@example.com", "password": "password"})

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_regular_user_can_create_list_rotate_and_revoke_token(self):
        created = self.client.post(
            "/api/integration-tokens",
            json={"name": "Yomitan - PC", "expires_in_days": 90},
        )
        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        self.assertTrue(item["token"].startswith("flama_yt_"))
        token_id = item["id"]
        with self.app.app_context():
            stored = db.session.get(UserApiToken, token_id)
            self.assertNotEqual(stored.token_hash, item["token"])
            self.assertNotIn(item["token"], stored.token_prefix)

        listed = self.client.get("/api/integration-tokens").get_json()["items"]
        self.assertNotIn("token", listed[0])
        rotated = self.client.post(
            f"/api/integration-tokens/{token_id}/rotate",
            json={"expires_in_days": None},
        )
        self.assertEqual(rotated.status_code, 201)
        self.assertNotEqual(rotated.get_json()["item"]["token"], item["token"])
        new_id = rotated.get_json()["item"]["id"]
        self.assertEqual(self.client.delete(f"/api/integration-tokens/{new_id}").status_code, 204)

    def test_invalid_expiry_is_rejected(self):
        response = self.client.post(
            "/api/integration-tokens",
            json={"name": "PC", "expires_in_days": 7},
        )
        self.assertEqual(response.status_code, 400)

    def test_mining_token_rotation_and_setup(self):
        created = self.client.post("/api/integration-tokens", json={"name": "asbplayer", "preset": "mining-text"})
        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        self.assertNotIn("note:update", item["scopes"])
        self.assertNotIn("media:write", item["scopes"])
        rotated = self.client.post(f'/api/integration-tokens/{item["id"]}/rotate', json={}).get_json()["item"]
        self.assertEqual(rotated["scopes"], item["scopes"])
        for _ in range(2):
            setup = self.client.post("/api/integration-tokens/sentence-mining-setup", json={})
            self.assertEqual(setup.status_code, 200)
            self.assertEqual(setup.get_json()["modelName"], "Sentence Card")
        with self.app.app_context():
            self.assertEqual(NoteType.query.filter_by(user_id=self.user_id, name="Sentence Card").count(), 1)

    def test_unknown_token_scopes_are_rejected(self):
        for payload in ({"name": "bad", "preset": "unknown"}, {"name": "bad", "scopes": ["admin:write"]}, {"name": "bad", "scopes": []}):
            self.assertEqual(self.client.post("/api/integration-tokens", json=payload).status_code, 400)

    def test_identity_field_is_explicit_unique_required_text_and_delete_safe(self):
        with self.app.app_context():
            note_type = NoteType(user_id=self.user_id, name="Identity Test")
            db.session.add(note_type)
            db.session.flush()
            word = FieldDef(note_type_id=note_type.id, name="Word", field_type="text", required=True)
            meaning = FieldDef(note_type_id=note_type.id, name="Meaning", field_type="text", required=True)
            db.session.add_all([word, meaning])
            db.session.commit()
            note_type_id, word_id, meaning_id = note_type.id, word.id, meaning.id

        marked = self.client.patch(
            f"/api/note-types/{note_type_id}/fields/{word_id}",
            json={"identity_role": "primary", "field_type": "text", "required": True},
        )
        self.assertEqual(marked.status_code, 200)
        conflict = self.client.patch(
            f"/api/note-types/{note_type_id}/fields/{meaning_id}",
            json={"identity_role": "primary", "field_type": "text", "required": True},
        )
        self.assertEqual(conflict.status_code, 400)
        invalid = self.client.patch(
            f"/api/note-types/{note_type_id}/fields/{word_id}",
            json={"identity_role": "primary", "required": False},
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(
            self.client.delete(f"/api/note-types/{note_type_id}/fields/{word_id}").status_code,
            409,
        )
        cleared = self.client.patch(
            f"/api/note-types/{note_type_id}/fields/{word_id}",
            json={"identity_role": None},
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(
            self.client.delete(f"/api/note-types/{note_type_id}/fields/{word_id}").status_code,
            200,
        )


if __name__ == "__main__":
    unittest.main()
