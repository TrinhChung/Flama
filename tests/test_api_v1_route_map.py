"""Contract snapshot for the REST API V1 URL map."""

import unittest

from app import create_app
from models import db


EXPECTED_V1_RULES = {
    ("GET", "/api/v1/admin/image-library"),
    ("POST", "/api/v1/admin/image-library"),
    ("PATCH", "/api/v1/admin/image-library/<asset_id>"),
    ("GET", "/api/v1/admin/payments"),
    ("GET", "/api/v1/admin/payments/orders"),
    ("GET", "/api/v1/admin/payments/orders/<order_id>"),
    ("GET", "/api/v1/admin/payments/transactions"),
    ("GET", "/api/v1/admin/payments/transactions/<attempt_id>"),
    ("GET", "/api/v1/admin/support-donation"),
    ("PUT", "/api/v1/admin/support-donation"),
    ("GET", "/api/v1/admin/tts-providers"),
    ("POST", "/api/v1/admin/tts-providers"),
    ("DELETE", "/api/v1/admin/tts-providers/<int:provider_id>"),
    ("PUT", "/api/v1/admin/tts-providers/<int:provider_id>"),
    ("GET", "/api/v1/admin/users"),
    ("PATCH", "/api/v1/admin/users/<int:user_id>"),
    ("POST", "/api/v1/admin/users/roles/batch"),
    ("POST", "/api/v1/admin/users/status/batch"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/register"),
    ("GET", "/api/v1/browse/cards"),
    ("DELETE", "/api/v1/browse/cards/<card_id>"),
    ("GET", "/api/v1/browse/cards/<card_id>"),
    ("PATCH", "/api/v1/browse/cards/<card_id>"),
    ("GET", "/api/v1/browse/decks"),
    ("GET", "/api/v1/browse/decks/tree"),
    ("GET", "/api/v1/browse/notes"),
    ("PATCH", "/api/v1/browse/notes/<note_id>"),
    ("POST", "/api/v1/browse/voicevox/generate"),
    ("POST", "/api/v1/browse/voicevox/precheck"),
    ("POST", "/api/v1/browse/voicevox/preview"),
    ("GET", "/api/v1/dashboard"),
    ("POST", "/api/v1/decks"),
    ("DELETE", "/api/v1/decks/<int:deck_id>"),
    ("PATCH", "/api/v1/decks/<int:deck_id>"),
    ("POST", "/api/v1/decks/<int:deck_id>/progress-reset"),
    ("POST", "/api/v1/flashcards/import/estimate"),
    ("POST", "/api/v1/flashcards/import/execute"),
    ("GET", "/api/v1/flashcards/import/options"),
    ("POST", "/api/v1/flashcards/import/parse"),
    ("GET", "/api/v1/marketplace/installed-decks"),
    ("GET", "/api/v1/mcp-tokens"),
    ("POST", "/api/v1/mcp-tokens"),
    ("DELETE", "/api/v1/mcp-tokens/<int:token_id>"),
    ("DELETE", "/api/v1/media/<asset_id>"),
    ("GET", "/api/v1/note-types"),
    ("POST", "/api/v1/note-types"),
    ("GET", "/api/v1/note-types/<note_type_id>"),
    ("PATCH", "/api/v1/note-types/<note_type_id>"),
    ("DELETE", "/api/v1/note-types/<note_type_id>"),
    ("GET", "/api/v1/note-types/<note_type_id>/fields"),
    ("POST", "/api/v1/note-types/<note_type_id>/fields"),
    ("PATCH", "/api/v1/note-types/<note_type_id>/fields/<field_id>"),
    ("DELETE", "/api/v1/note-types/<note_type_id>/fields/<field_id>"),
    ("POST", "/api/v1/note-types/<note_type_id>/fields/reorder"),
    ("GET", "/api/v1/note-types/<note_type_id>/templates"),
    ("POST", "/api/v1/note-types/<note_type_id>/templates"),
    ("PATCH", "/api/v1/note-types/<note_type_id>/templates/<template_id>"),
    ("DELETE", "/api/v1/note-types/<note_type_id>/templates/<template_id>"),
    ("POST", "/api/v1/note-types/<note_type_id>/templates/<template_id>/preview"),
    ("POST", "/api/v1/note-types/<note_type_id>/templates/<template_id>/reset"),
    ("GET", "/api/v1/notes"),
    ("POST", "/api/v1/notes"),
    ("GET", "/api/v1/notes/<note_id>"),
    ("PATCH", "/api/v1/notes/<note_id>"),
    ("DELETE", "/api/v1/notes/<note_id>"),
    ("POST", "/api/v1/notes/<note_id>/markdown-media"),
    ("POST", "/api/v1/notes/<note_id>/media"),
    ("GET", "/api/v1/orders"),
    ("GET", "/api/v1/orders/<order_id>"),
    ("DELETE", "/api/v1/session"),
    ("GET", "/api/v1/session"),
    ("GET", "/api/v1/statistics"),
    ("GET", "/api/v1/statistics/overview"),
    ("GET", "/api/v1/statistics/today-future"),
    ("GET", "/api/v1/support-donation"),
    ("POST", "/api/v1/support-donation/checkout"),
}


class ApiV1RouteMapTests(unittest.TestCase):
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

    def test_v1_rule_and_method_contract_is_stable(self):
        actual = {
            (method, rule.rule)
            for rule in self.app.url_map.iter_rules()
            if rule.rule.startswith("/api/v1")
            for method in rule.methods - {"HEAD", "OPTIONS"}
        }
        self.assertEqual(actual, EXPECTED_V1_RULES)
        self.assertEqual(len(actual), 77)


if __name__ == "__main__":
    unittest.main()
