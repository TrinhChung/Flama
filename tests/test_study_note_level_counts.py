"""Phase 6 D6-04: NOTE learners count each Note once (STUDY_NOTE_COUNT_ENABLED)."""

from datetime import datetime
import unittest
from unittest.mock import patch

from app import create_app
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


class StudyNoteLevelCountTests(unittest.TestCase):
    NOTES = 3

    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
            "STUDY_WIRE_V4_ENABLED": True, "STUDY_ASYNC_BATCH_ENABLED": False,
        })

    def setUp(self):
        self.addCleanup(self._cleanup)
        with self.app.app_context():
            db.create_all()
            user = User(username="note-counts", email="note-counts@example.test")
            db.session.add(user)
            db.session.flush()
            deck = Deck(name="Two templates", owner_user_id=user.id)
            note_type = NoteType(name="Two templates", user_id=user.id)
            db.session.add_all([deck, note_type])
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
            templates = [Template(note_type_id=note_type.id, name=f"T{i}", front_html="{{Word}}",
                                  back_html="{{Word}}", position=i, is_default=i == 0) for i in range(2)]
            db.session.add_all(templates)
            notes = [Note(user_id=user.id, deck_id=deck.id, note_type_id=note_type.id,
                          field_values={"Word": f"w{i}"}) for i in range(self.NOTES)]
            db.session.add_all(notes)
            db.session.flush()
            db.session.add_all(Card(note_id=note.id, template_id=t.id) for note in notes for t in templates)
            db.session.commit()
            stage_note_authority_enrollment(db.session, learner_user_id=int(user.id), now_utc=datetime.utcnow())
            db.session.commit()
            self.user_id, self.deck_id = int(user.id), int(deck.id)
        self.client = self.app.test_client()
        with self.client.session_transaction() as login:
            login["_user_id"], login["_fresh"] = str(self.user_id), True

    def _cleanup(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _dashboard_new(self):
        from app.services.dashboard_service import build_dashboard_data

        with self.app.test_request_context():
            with self.app.app_context():
                user = db.session.get(User, self.user_id)
                rows, total_new, _learn, _due, _admin = build_dashboard_data(user)
        return total_new

    def _tree_counts(self):
        from app.services.browse_card_service import build_browse_deck_tree

        with self.app.app_context():
            tree = build_browse_deck_tree(user_id=self.user_id, admin_mode=False, timezone_name="UTC")["tree"]
        node = next(item for item in tree if int(item["id"]) == self.deck_id)
        return node["counts"]["total"], node["counts"]["new"]

    def _next_new(self):
        response = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        return int(response.get_json()["new_count"])

    def test_counts_per_card_while_the_flag_is_off(self):
        with patch.dict(self.app.config, STUDY_NOTE_COUNT_ENABLED=False):
            self.assertEqual(self._dashboard_new(), 2 * self.NOTES)
            self.assertEqual(self._tree_counts(), (2 * self.NOTES, 2 * self.NOTES))
            self.assertEqual(self._next_new(), 2 * self.NOTES)

    def test_counts_each_note_once_when_enabled(self):
        with patch.dict(self.app.config, STUDY_NOTE_COUNT_ENABLED=True):
            self.assertEqual(self._dashboard_new(), self.NOTES)
            self.assertEqual(self._tree_counts(), (self.NOTES, self.NOTES))
            self.assertEqual(self._next_new(), self.NOTES)


if __name__ == "__main__":
    unittest.main()
