import unittest
from uuid import uuid4

from app import create_app, db
from models.card import Card
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from app.services.study_composition_service import (
    AppliedComposition,
    build_compatibility_composition,
    list_available_compositions_for_scope,
    make_compatibility_composition_id,
    resolve_compatibility_composition_for_card,
    resolve_compatibility_compositions_for_note_type,
)


class StudyCompositionServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.app_ctx = self.app.app_context()
        self.app_ctx.push()
        db.create_all()

        uid = uuid4().hex[:8]
        self.user = User(username=f"user_{uid}", email=f"user_{uid}@example.com")
        self.user.set_password("pass")
        db.session.add(self.user)
        db.session.commit()

        self.note_type = NoteType(name="Test NoteType", user_id=self.user.id)
        db.session.add(self.note_type)
        db.session.commit()

        self.template_1 = Template(
            note_type_id=self.note_type.id,
            name="Forward (Front -> Back)",
            front_html="<div>{{Front}}</div>",
            back_html="<div>{{Back}}</div>",
            position=0,
            is_default=True,
        )
        self.template_2 = Template(
            note_type_id=self.note_type.id,
            name="Reverse (Back -> Front)",
            front_html="<div>{{Back}}</div>",
            back_html="<div>{{Front}}</div>",
            position=1,
            is_default=False,
        )
        db.session.add_all([self.template_1, self.template_2])
        db.session.commit()

        self.deck = Deck(
            name="Composition Deck",
            owner_user_id=self.user.id,
            note_type_id=self.note_type.id,
        )
        db.session.add(self.deck)
        db.session.commit()

        self.note = Note(
            user_id=self.user.id,
            deck_id=self.deck.id,
            note_type_id=self.note_type.id,
            field_values={"Front": "test front", "Back": "test back"},
        )
        db.session.add(self.note)
        db.session.commit()

        self.card_1 = Card(
            note_id=self.note.id,
            template_id=self.template_1.id,
        )
        db.session.add(self.card_1)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        db.drop_all()
        self.app_ctx.pop()

    def test_build_compatibility_composition(self):
        comp = build_compatibility_composition(self.template_1)
        self.assertEqual(
            comp.composition_id,
            make_compatibility_composition_id(self.note_type.id, self.template_1.id),
        )
        self.assertEqual(comp.mode_key, "flashcard")
        self.assertEqual(comp.template_name, "Forward (Front -> Back)")
        self.assertTrue(comp.is_default)
        self.assertEqual(comp.algorithm_key, "legacy-anki")
        self.assertEqual(comp.algorithm_version, "1.0.0")

    def test_resolve_compatibility_composition_for_card(self):
        comp = resolve_compatibility_composition_for_card(self.card_1)
        self.assertEqual(comp.template_id, self.template_1.id)
        self.assertEqual(comp.note_type_id, self.note_type.id)

    def test_resolve_compatibility_compositions_for_note_type(self):
        comps = resolve_compatibility_compositions_for_note_type(self.note_type.id)
        self.assertEqual(len(comps), 2)
        self.assertEqual(comps[0].template_id, self.template_1.id)
        self.assertEqual(comps[1].template_id, self.template_2.id)

    def test_list_available_compositions_for_deck_scope(self):
        comps = list_available_compositions_for_scope("deck", self.deck.id, self.user.id)
        self.assertEqual(len(comps), 2)
        comp_names = [c.template_name for c in comps]
        self.assertIn("Forward (Front -> Back)", comp_names)
        self.assertIn("Reverse (Back -> Front)", comp_names)


if __name__ == "__main__":
    unittest.main()
