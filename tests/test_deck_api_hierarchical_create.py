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

    def test_create_deck_with_explicit_note_type_id(self):
        from models.note_type import NoteType

        self._login()

        with self.app.app_context():
            nt = NoteType(name="Custom Vocab", user_id=self.user_id)
            db.session.add(nt)
            db.session.commit()
            nt_id = nt.id

        res = self.client.post(
            "/api/decks",
            json={"name": "Grammar N1", "note_type_id": nt_id},
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["item"]["note_type_id"], nt_id)

        with self.app.app_context():
            deck = Deck.query.filter_by(name="Grammar N1").first()
            self.assertIsNotNone(deck)
            self.assertEqual(deck.note_type_id, nt_id)

    def test_create_child_deck_inherits_parent_note_type_id(self):
        from models.note_type import NoteType

        self._login()

        with self.app.app_context():
            nt = NoteType(name="Inherited Model", user_id=self.user_id)
            db.session.add(nt)
            db.session.commit()
            parent = Deck(name="Parent Deck", owner_user_id=self.user_id, note_type_id=nt.id)
            db.session.add(parent)
            db.session.commit()
            parent_id = parent.id
            nt_id = nt.id

        res = self.client.post(
            "/api/decks",
            json={"name": "Child Deck", "parent_id": str(parent_id)},
        )
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["item"]["note_type_id"], nt_id)

        with self.app.app_context():
            child = Deck.query.filter_by(name="Child Deck", parent_id=parent_id).first()
            self.assertIsNotNone(child)
            self.assertEqual(child.note_type_id, nt_id)

    def test_dashboard_payload_includes_deck_note_type_id(self):
        from models.note_type import NoteType

        self._login()

        with self.app.app_context():
            nt = NoteType(name="Dashboard NT", user_id=self.user_id)
            db.session.add(nt)
            db.session.commit()
            deck = Deck(name="Root Deck For Dashboard", owner_user_id=self.user_id, note_type_id=nt.id)
            db.session.add(deck)
            db.session.commit()
            nt_id = nt.id
            deck_id = deck.id

        res = self.client.get("/api/dashboard")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        found = next((item for item in data["items"] if item["deck_id"] == deck_id), None)
        self.assertIsNotNone(found)
        self.assertEqual(found.get("note_type_id"), nt_id)


if __name__ == "__main__":
    unittest.main()
