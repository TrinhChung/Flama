import unittest

from app import create_app
from app.services import deck_api_service
from models import db
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.note_type import NoteType
from models.user import User


class DeckNoteTypeGuardTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "DECK_SOURCE_NOTETYPE_GUARD_MODE": "strict",
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        user = User(username="owner", email="owner@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        expected = NoteType(user_id=user.id, name="Expected")
        other = NoteType(user_id=user.id, name="Other")
        listed_root = Deck(name="Listed root", owner_user_id=user.id)
        moving_root = Deck(name="Moving root", owner_user_id=user.id)
        db.session.add_all([expected, other, listed_root, moving_root])
        db.session.flush()
        db.session.add(
            Note(
                user_id=user.id,
                note_type_id=other.id,
                deck_id=moving_root.id,
                field_values={"Front": "mismatch"},
            )
        )
        db.session.add(
            DeckMarketplaceItem(
                owner_user_id=user.id,
                source_deck_id=listed_root.id,
                source_note_type_id=expected.id,
                title="Listed deck",
                publish_status="published",
            )
        )
        db.session.commit()
        self.user_id = user.id
        self.listed_root_id = listed_root.id
        self.moving_root_id = moving_root.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_strict_guard_rejects_mismatched_subtree_move_before_commit(self):
        with self.assertRaises(deck_api_service.DeckApiError) as context:
            deck_api_service.update_deck(
                deck_id=self.moving_root_id,
                payload={"parent_id": self.listed_root_id},
            )

        self.assertEqual(context.exception.status, 409)
        db.session.expire_all()
        moving = db.session.get(Deck, self.moving_root_id)
        self.assertIsNone(moving.parent_id)

    def test_shadow_guard_logs_but_allows_subtree_move(self):
        self.app.config["DECK_SOURCE_NOTETYPE_GUARD_MODE"] = "shadow"

        result = deck_api_service.update_deck(
            deck_id=self.moving_root_id,
            payload={"parent_id": self.listed_root_id},
        )

        self.assertTrue(result.changed)
        self.assertEqual(result.deck.parent_id, self.listed_root_id)


if __name__ == "__main__":
    unittest.main()
