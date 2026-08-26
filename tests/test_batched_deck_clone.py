import unittest

from sqlalchemy import event

from app import create_app
from app.services import flashcards_share_service
from models import db
from models.deck import Deck
from models.user import User


class BatchedDeckCloneTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "SHARED_DECK_TREE_CLONE_MODE": "batched",
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        owner = User(username="owner", email="owner@example.com")
        owner.set_password("password")
        learner = User(username="learner", email="learner@example.com")
        learner.set_password("password")
        db.session.add_all([owner, learner])
        db.session.flush()
        root = Deck(name="Root", owner_user_id=owner.id, position=0)
        db.session.add(root)
        db.session.flush()
        for child_index in range(10):
            child = Deck(
                name=f"Child {child_index}",
                parent_id=root.id,
                owner_user_id=owner.id,
                position=child_index,
            )
            db.session.add(child)
            db.session.flush()
            for leaf_index in range(10):
                db.session.add(
                    Deck(
                        name=f"Leaf {child_index}-{leaf_index}",
                        parent_id=child.id,
                        owner_user_id=owner.id,
                        position=leaf_index,
                    )
                )
        db.session.commit()
        self.root_id = root.id
        self.learner_id = learner.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_clone_111_nodes_uses_depth_bounded_selects(self):
        db.session.expire_all()
        select_statements: list[str] = []

        def _capture_selects(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements.append(statement)

        event.listen(db.engine, "before_cursor_execute", _capture_selects)
        try:
            clone = flashcards_share_service.clone_deck_subtree(
                source_deck_id=self.root_id,
                parent_id=None,
                owner_user_id=self.learner_id,
            )
        finally:
            event.remove(db.engine, "before_cursor_execute", _capture_selects)

        self.assertEqual(clone.name, "Root")
        self.assertEqual(
            Deck.query.filter_by(owner_user_id=self.learner_id).count(),
            111,
        )
        self.assertLessEqual(len(select_statements), 5)


if __name__ == "__main__":
    unittest.main()
