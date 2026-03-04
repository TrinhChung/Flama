"""Integration tests for default TTS provider seed behavior."""

import unittest

from app import create_app
from app.services.tts_provider_service import (
    VOICEVOX_AUDIO_BASE_URL,
    VOICEVOX_PROVIDER_TYPE,
    ensure_default_tts_providers,
    loads_json_map,
)
from models import db
from models.tts_provider_config import TtsProviderConfig


class TtsProviderSeedTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_create_app_seeds_default_voicevox_provider(self):
        with self.app.app_context():
            rows = (
                TtsProviderConfig.query.filter(
                    TtsProviderConfig.provider_type == VOICEVOX_PROVIDER_TYPE,
                )
                .order_by(TtsProviderConfig.id.asc())
                .all()
            )
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.base_url, VOICEVOX_AUDIO_BASE_URL)
            self.assertTrue(row.requires_api_key)
            self.assertTrue(row.is_active)

            shared_config = loads_json_map(row.shared_config_json)
            provider_config = loads_json_map(row.provider_config_json)
            default_settings = loads_json_map(row.default_settings_json)

            self.assertIn("audio_url", shared_config)
            self.assertIn("speakers_url", shared_config)
            self.assertIn("key_validation_url", provider_config)
            self.assertIn("character_id", default_settings)
            self.assertIn("pitch", default_settings)
            self.assertIn("intonation_scale", default_settings)
            self.assertIn("speed", default_settings)

    def test_seed_is_idempotent(self):
        with self.app.app_context():
            first_count = TtsProviderConfig.query.count()
            result = ensure_default_tts_providers(db.session)
            db.session.commit()
            second_count = TtsProviderConfig.query.count()

            self.assertEqual(first_count, 1)
            self.assertEqual(second_count, 1)
            self.assertEqual(result.get("created"), 0)

    def test_provider_model_does_not_store_api_key_fields(self):
        columns = set(TtsProviderConfig.__table__.columns.keys())
        self.assertNotIn("encrypted_api_key", columns)
        self.assertNotIn("key_status", columns)
        self.assertNotIn("last_validated_at", columns)


if __name__ == "__main__":
    unittest.main()
