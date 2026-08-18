"""Integration tests for hierarchical deck creation (e.g. SAA::deck10)."""

import unittest
from app import create_app
from models import db
from models.user import User
from models.user_role import UserRole
from models.deck import Deck


class HierarchicalDeckCreateTests(unittest.TestCase):
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
            user = User(
                username="testuser",
                email="test@example.com",
                is_admin=False,
                role_id=regular_role.id,
            )
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self):
        return self.client.post(
            "/login",
            data={"email": "test@example.com", "password": "password"},
            follow_redirects=True,
        )

    def test_create_hierarchical_deck_creates_parent_and_child(self):
        self._login()

        res = self.client.post(
            "/api/decks",
            json={"name": "SAA::deck10"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["created_count"], 2)
        self.assertEqual(data["path"], ["SAA", "deck10"])

        with self.app.app_context():
            parent = Deck.query.filter_by(name="SAA", parent_id=None).first()
            self.assertIsNotNone(parent)
            child = Deck.query.filter_by(name="deck10", parent_id=parent.id).first()
            self.assertIsNotNone(child)

    def test_create_hierarchical_deck_under_existing_parent(self):
        self._login()

        with self.app.app_context():
            parent = Deck(name="SAA", owner_user_id=self.user_id, position=1)
            db.session.add(parent)
            db.session.commit()
            parent_id = parent.id

        res = self.client.post(
            "/api/decks",
            json={"name": "SAA::deck10"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["created_count"], 1)
        self.assertEqual(data["path"], ["SAA", "deck10"])

        with self.app.app_context():
            child = Deck.query.filter_by(name="deck10", parent_id=parent_id).first()
            self.assertIsNotNone(child)

    def test_create_deeply_nested_hierarchy(self):
        self._login()

        res = self.client.post(
            "/api/decks",
            json={"name": "Japanese::N3::Vocabulary::Lesson 01"},
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["created_count"], 4)

        with self.app.app_context():
            r1 = Deck.query.filter_by(name="Japanese", parent_id=None).first()
            self.assertIsNotNone(r1)
            r2 = Deck.query.filter_by(name="N3", parent_id=r1.id).first()
            self.assertIsNotNone(r2)
            r3 = Deck.query.filter_by(name="Vocabulary", parent_id=r2.id).first()
            self.assertIsNotNone(r3)
            r4 = Deck.query.filter_by(name="Lesson 01", parent_id=r3.id).first()
            self.assertIsNotNone(r4)


if __name__ == "__main__":
    unittest.main()
