"""Integration tests for per-user TTS key/settings management APIs."""

from datetime import datetime
import unittest
from unittest.mock import patch

from app import create_app
from app.services.tts_provider_service import ApiKeyValidationResult, VOICEVOX_PROVIDER_TYPE, loads_json_map
from models import db
from models.tts_provider_config import TtsProviderConfig
from models.tts_user_provider_profile import TtsUserProviderProfile
from models.user import User
from models.user_role import UserRole


class TtsUserProfileApiTests(unittest.TestCase):
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
            regular_role = UserRole.query.filter_by(code="regular").first()
            assert regular_role is not None

            user_a = User(
                username="user-a",
                email="user-a@example.com",
                is_admin=False,
                role_id=regular_role.id,
            )
            user_a.set_password("password")
            user_b = User(
                username="user-b",
                email="user-b@example.com",
                is_admin=False,
                role_id=regular_role.id,
            )
            user_b.set_password("password")
            db.session.add_all([user_a, user_b])
            db.session.commit()

            self.user_a_id = user_a.id
            self.user_b_id = user_b.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, email: str):
        return self.client.post(
            "/login",
            data={"email": email, "password": "password"},
            follow_redirects=True,
        )

    def test_user_can_save_own_voicevox_key_and_settings(self):
        self._login("user-a@example.com")

        get_response = self.client.get(f"/api/tts/providers/{VOICEVOX_PROVIDER_TYPE}/profile")
        self.assertEqual(get_response.status_code, 200)
        get_payload = get_response.get_json()
        self.assertFalse(get_payload["profile"]["has_api_key"])

        put_response = self.client.put(
            f"/api/tts/providers/{VOICEVOX_PROVIDER_TYPE}/profile",
            json={
                "api_key": "user-a-secret-key",
                "settings": {
                    "character_id": "101",
                    "source_field": "Word",
                    "destination_field": "Word_Audio",
                    "append_audio": True,
                    "use_opus": True,
                    "pitch": 0.35,
                    "intonation_scale": 0.45,
                    "speed": 0.65,
                },
            },
        )
        self.assertEqual(put_response.status_code, 200)
        put_payload = put_response.get_json()

        self.assertTrue(put_payload["profile"]["has_api_key"])
        self.assertEqual(put_payload["profile"]["settings"]["character_id"], "101")
        self.assertEqual(put_payload["profile"]["settings"]["source_field"], "Word")
        self.assertEqual(put_payload["profile"]["settings"]["destination_field"], "Word_Audio")
        self.assertTrue(put_payload["profile"]["settings"]["append_audio"])
        self.assertTrue(put_payload["profile"]["settings"]["use_opus"])
        self.assertEqual(put_payload["profile"]["settings"]["speed"], 0.65)

        with self.app.app_context():
            provider = (
                TtsProviderConfig.query.filter_by(provider_type=VOICEVOX_PROVIDER_TYPE)
                .order_by(TtsProviderConfig.id.asc())
                .first()
            )
            self.assertIsNotNone(provider)
            provider_columns = set(TtsProviderConfig.__table__.columns.keys())
            self.assertNotIn("encrypted_api_key", provider_columns)

            profile = TtsUserProviderProfile.query.filter_by(
                user_id=self.user_a_id,
                provider_id=provider.id,
            ).first()
            self.assertIsNotNone(profile)
            self.assertTrue(profile.encrypted_api_key)

            settings = loads_json_map(profile.settings_json)
            self.assertEqual(settings.get("character_id"), "101")
            self.assertEqual(settings.get("source_field"), "Word")
            self.assertEqual(settings.get("destination_field"), "Word_Audio")
            self.assertTrue(settings.get("append_audio"))
            self.assertTrue(settings.get("use_opus"))

        verify_response = self.client.get(f"/api/tts/providers/{VOICEVOX_PROVIDER_TYPE}/profile")
        self.assertEqual(verify_response.status_code, 200)
        verify_payload = verify_response.get_json()
        self.assertEqual(verify_payload["profile"]["settings"]["source_field"], "Word")
        self.assertEqual(verify_payload["profile"]["settings"]["destination_field"], "Word_Audio")
        self.assertTrue(verify_payload["profile"]["settings"]["append_audio"])
        self.assertTrue(verify_payload["profile"]["settings"]["use_opus"])

    def test_user_can_save_voicevox_settings_without_api_key(self):
        self._login("user-a@example.com")

        put_response = self.client.put(
            f"/api/tts/providers/{VOICEVOX_PROVIDER_TYPE}/profile",
            json={
                "settings": {
                    "character_id": "202",
                    "source_field": "Word",
                    "destination_field": "Word_Audio",
                    "append_audio": True,
                    "use_opus": False,
                    "speed": 1.25,
                },
            },
        )
        self.assertEqual(put_response.status_code, 200)
        payload = put_response.get_json()
        self.assertFalse(payload["profile"]["has_api_key"])
        self.assertEqual(payload["profile"]["settings"]["character_id"], "202")
        self.assertEqual(payload["profile"]["settings"]["source_field"], "Word")
        self.assertEqual(payload["profile"]["settings"]["destination_field"], "Word_Audio")
        self.assertTrue(payload["profile"]["settings"]["append_audio"])
        self.assertFalse(payload["profile"]["settings"]["use_opus"])

        with self.app.app_context():
            provider = (
                TtsProviderConfig.query.filter_by(provider_type=VOICEVOX_PROVIDER_TYPE)
                .order_by(TtsProviderConfig.id.asc())
                .first()
            )
            self.assertIsNotNone(provider)
            profile = TtsUserProviderProfile.query.filter_by(
                user_id=self.user_a_id,
                provider_id=provider.id,
            ).first()
            self.assertIsNotNone(profile)
            self.assertFalse(bool(profile.encrypted_api_key))

            settings = loads_json_map(profile.settings_json)
            self.assertEqual(settings.get("character_id"), "202")
            self.assertEqual(settings.get("source_field"), "Word")
            self.assertEqual(settings.get("destination_field"), "Word_Audio")
            self.assertTrue(settings.get("append_audio"))
            self.assertFalse(settings.get("use_opus"))

    def test_user_profiles_are_isolated(self):
        self._login("user-a@example.com")
        put_response = self.client.put(
            f"/api/tts/providers/{VOICEVOX_PROVIDER_TYPE}/profile",
            json={"api_key": "user-a-secret-key"},
        )
        self.assertEqual(put_response.status_code, 200)

        self.client.get("/logout", follow_redirects=True)
        self._login("user-b@example.com")

        get_response = self.client.get(f"/api/tts/providers/{VOICEVOX_PROVIDER_TYPE}/profile")
        self.assertEqual(get_response.status_code, 200)
        get_payload = get_response.get_json()
        self.assertFalse(get_payload["profile"]["has_api_key"])

    def test_validate_saved_key_updates_profile_status(self):
        self._login("user-a@example.com")

        put_response = self.client.put(
            f"/api/tts/providers/{VOICEVOX_PROVIDER_TYPE}/profile",
            json={"api_key": "user-a-secret-key"},
        )
        self.assertEqual(put_response.status_code, 200)

        fake_result = ApiKeyValidationResult(
            valid=True,
            status="valid",
            checked_at=datetime.utcnow(),
            message="OK",
        )
        with patch("app.services.tts_provider_service.validate_provider_api_key", return_value=fake_result):
            validate_response = self.client.post(
                f"/api/tts/providers/{VOICEVOX_PROVIDER_TYPE}/validate-key",
                json={},
            )

        self.assertEqual(validate_response.status_code, 200)
        validate_payload = validate_response.get_json()
        self.assertEqual(validate_payload["validation"]["status"], "valid")

        with self.app.app_context():
            provider = (
                TtsProviderConfig.query.filter_by(provider_type=VOICEVOX_PROVIDER_TYPE)
                .order_by(TtsProviderConfig.id.asc())
                .first()
            )
            self.assertIsNotNone(provider)

            profile = TtsUserProviderProfile.query.filter_by(
                user_id=self.user_a_id,
                provider_id=provider.id,
            ).first()
            self.assertIsNotNone(profile)
            self.assertEqual(profile.key_status, "valid")
            self.assertIsNotNone(profile.last_validated_at)

    def test_voice_list_endpoint_returns_items(self):
        self._login("user-a@example.com")

        mocked_items = [
            {"id": "101", "label": "Character A"},
            {"id": "102", "label": "Character B"},
        ]
        with patch(
            "app.services.tts_provider_service.list_provider_voices_for_user",
            return_value=(mocked_items, []),
        ) as mocked:
            response = self.client.post(
                f"/api/tts/providers/{VOICEVOX_PROVIDER_TYPE}/voices",
                json={"api_key": "temporary-key"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["items"], mocked_items)
        self.assertEqual(mocked.call_count, 1)

    def test_profile_payload_treats_undecryptable_saved_key_as_missing(self):
        self._login("user-a@example.com")

        with self.app.app_context():
            provider = (
                TtsProviderConfig.query.filter_by(provider_type=VOICEVOX_PROVIDER_TYPE)
                .order_by(TtsProviderConfig.id.asc())
                .first()
            )
            self.assertIsNotNone(provider)

            profile = TtsUserProviderProfile(
                user_id=self.user_a_id,
                provider_id=provider.id,
                encrypted_api_key="not-a-valid-fernet-token",
                key_status="valid",
                settings_json="{}",
            )
            db.session.add(profile)
            db.session.commit()

        response = self.client.get(f"/api/tts/providers/{VOICEVOX_PROVIDER_TYPE}/profile")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["profile"]["has_api_key"])
        self.assertEqual(payload["profile"]["masked_api_key"], "")
        self.assertEqual(payload["profile"]["key_status"], "unknown")


if __name__ == "__main__":
    unittest.main()
