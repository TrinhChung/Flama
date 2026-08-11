"""Contract snapshot for the canonical REST API URL map."""

import unittest

from app import create_app
from models import db


EXPECTED_API_RULES = {
    ("GET", "/api/admin/image-library"),
    ("POST", "/api/admin/image-library"),
    ("PATCH", "/api/admin/image-library/<asset_id>"),
    ("GET", "/api/admin/payments"),
    ("GET", "/api/admin/payments/orders"),
    ("GET", "/api/admin/payments/orders/<order_id>"),
    ("GET", "/api/admin/payments/transactions"),
    ("GET", "/api/admin/payments/transactions/<attempt_id>"),
    ("GET", "/api/admin/support-donation"),
    ("PUT", "/api/admin/support-donation"),
    ("GET", "/api/admin/tickets"),
    ("PATCH", "/api/admin/tickets/<ticket_id>"),
    ("GET", "/api/admin/tts-providers"),
    ("POST", "/api/admin/tts-providers"),
    ("DELETE", "/api/admin/tts-providers/<int:provider_id>"),
    ("PUT", "/api/admin/tts-providers/<int:provider_id>"),
    ("GET", "/api/admin/users"),
    ("PATCH", "/api/admin/users/<int:user_id>"),
    ("POST", "/api/admin/users/roles/batch"),
    ("POST", "/api/admin/users/status/batch"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/register"),
    ("GET", "/api/browse/cards"),
    ("DELETE", "/api/browse/cards/<card_id>"),
    ("GET", "/api/browse/cards/<card_id>"),
    ("PATCH", "/api/browse/cards/<card_id>"),
    ("GET", "/api/browse/decks"),
    ("GET", "/api/browse/decks/tree"),
    ("GET", "/api/browse/notes"),
    ("PATCH", "/api/browse/notes/<note_id>"),
    ("POST", "/api/browse/voicevox/generate"),
    ("POST", "/api/browse/voicevox/precheck"),
    ("POST", "/api/browse/voicevox/preview"),
    ("GET", "/api/dashboard"),
    ("GET", "/api/download/flama-audio"),
    ("GET", "/api/download/flama-audio.sha256"),
    ("POST", "/api/decks"),
    ("DELETE", "/api/decks/<int:deck_id>"),
    ("PATCH", "/api/decks/<int:deck_id>"),
    ("POST", "/api/decks/<int:deck_id>/progress-reset"),
    ("POST", "/api/flashcards/import/estimate"),
    ("POST", "/api/flashcards/import/execute"),
    ("GET", "/api/flashcards/import/anki/capabilities"),
    ("POST", "/api/flashcards/import/anki/sessions"),
    ("DELETE", "/api/flashcards/import/anki/sessions/<session_id>"),
    ("GET", "/api/flashcards/import/anki/sessions/<session_id>"),
    ("POST", "/api/flashcards/import/anki/sessions/<session_id>/complete"),
    ("PUT", "/api/flashcards/import/anki/sessions/<session_id>/packages/cards/<int:sequence>"),
    ("PUT", "/api/flashcards/import/anki/sessions/<session_id>/packages/media/<int:sequence>"),
    ("GET", "/api/flashcards/import/options"),
    ("POST", "/api/flashcards/import/parse"),
    ("GET", "/api/health"),
    ("GET", "/api/integration-tokens"),
    ("POST", "/api/integration-tokens"),
    ("DELETE", "/api/integration-tokens/<int:token_id>"),
    ("POST", "/api/integration-tokens/<int:token_id>/rotate"),
    ("GET", "/api/marketplace/installed-decks"),
    ("GET", "/api/marketplace/note-types"),
    ("GET", "/api/marketplace/note-types/hub"),
    ("GET", "/api/marketplace/note-types/recommendations"),
    ("GET", "/api/marketplace/note-types/<note_type_id>"),
    ("POST", "/api/marketplace/note-types/<note_type_id>/install"),
    ("POST", "/api/marketplace/note-types/<note_type_id>/publish"),
    ("POST", "/api/marketplace/note-types/<note_type_id>/rate"),
    ("DELETE", "/api/marketplace/note-types/<note_type_id>/save"),
    ("POST", "/api/marketplace/note-types/<note_type_id>/save"),
    ("POST", "/api/marketplace/note-types/<note_type_id>/templates/<template_id>/preview"),
    ("GET", "/api/mcp-tokens"),
    ("POST", "/api/mcp-tokens"),
    ("DELETE", "/api/mcp-tokens/<int:token_id>"),
    ("DELETE", "/api/media/<asset_id>"),
    ("GET", "/api/note-types"),
    ("POST", "/api/note-types"),
    ("GET", "/api/note-types/<note_type_id>"),
    ("PATCH", "/api/note-types/<note_type_id>"),
    ("DELETE", "/api/note-types/<note_type_id>"),
    ("POST", "/api/note-types/<note_type_id>/publish"),
    ("GET", "/api/note-types/<note_type_id>/fields"),

    ("POST", "/api/note-types/<note_type_id>/fields"),
    ("PATCH", "/api/note-types/<note_type_id>/fields/<field_id>"),
    ("DELETE", "/api/note-types/<note_type_id>/fields/<field_id>"),
    ("POST", "/api/note-types/<note_type_id>/fields/reorder"),
    ("GET", "/api/note-types/<note_type_id>/templates"),
    ("POST", "/api/note-types/<note_type_id>/templates"),
    ("PATCH", "/api/note-types/<note_type_id>/templates/<template_id>"),
    ("DELETE", "/api/note-types/<note_type_id>/templates/<template_id>"),
    ("POST", "/api/note-types/<note_type_id>/templates/<template_id>/preview"),
    ("POST", "/api/note-types/<note_type_id>/templates/<template_id>/reset"),
    ("GET", "/api/notes"),
    ("POST", "/api/notes"),
    ("GET", "/api/notes/<note_id>"),
    ("PATCH", "/api/notes/<note_id>"),
    ("DELETE", "/api/notes/<note_id>"),
    ("POST", "/api/notes/<note_id>/markdown-media"),
    ("POST", "/api/notes/<note_id>/media"),
    ("GET", "/api/orders"),
    ("GET", "/api/orders/<order_id>"),
    ("DELETE", "/api/session"),
    ("GET", "/api/session"),
    ("GET", "/api/shared/note-types"),
    ("GET", "/api/shared/note-types/hub"),
    ("GET", "/api/shared/note-types/recommendations"),
    ("GET", "/api/shared/note-types/<note_type_id>"),
    ("POST", "/api/shared/note-types/<note_type_id>/install"),
    ("POST", "/api/shared/note-types/<note_type_id>/rate"),
    ("DELETE", "/api/shared/note-types/<note_type_id>/save"),
    ("POST", "/api/shared/note-types/<note_type_id>/save"),
    ("POST", "/api/shared/note-types/<note_type_id>/templates/<template_id>/preview"),
    ("GET", "/api/statistics"),
    ("GET", "/api/statistics/overview"),
    ("GET", "/api/statistics/today-future"),
    ("GET", "/api/support-donation"),
    ("POST", "/api/support-donation/checkout"),
    ("POST", "/api/tickets"),
    ("GET", "/api/tickets/<ticket_id_or_code>"),
    ("POST", "/api/tickets/<ticket_id_or_code>/replies"),
    ("GET", "/api/tickets/attachments/<filename>"),
    ("GET", "/api/tickets/my"),
    ("POST", "/api/tickets/upload-image"),
}


class ApiRouteMapTests(unittest.TestCase):
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

    def test_rule_and_method_contract_is_stable(self):
        actual = {
            (method, rule.rule)
            for rule in self.app.url_map.iter_rules()
            if rule.endpoint.startswith("api_v1.")
            for method in rule.methods - {"HEAD", "OPTIONS"}
        }
        self.assertEqual(actual, EXPECTED_API_RULES)
        self.assertEqual(len(actual), 119)



        self.assertFalse(
            any(rule.rule.startswith("/api/v1") for rule in self.app.url_map.iter_rules())
        )


if __name__ == "__main__":
    unittest.main()
