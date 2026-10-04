import unittest
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import event

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
    group_available_compositions,
    list_available_compositions_for_query,
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
        self.assertEqual(len(comps), 1)
        comp_names = [c.template_name for c in comps]
        self.assertIn("Forward (Front -> Back)", comp_names)
        self.assertNotIn("Reverse (Back -> Front)", comp_names)

    def test_groups_only_card_backed_compositions(self):
        comps = list_available_compositions_for_scope("deck", self.deck.id, self.user.id)
        groups = group_available_compositions(comps)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].note_type_id, str(self.note_type.id))
        self.assertEqual(groups[0].note_type_name, "Test NoteType")
        self.assertEqual(
            [item.template_id for item in groups[0].compositions],
            [str(self.template_1.id)],
        )

    def test_discovery_batches_metadata_without_loading_card_content(self):
        templates = [self.template_1, self.template_2]
        for position in range(2, 20):
            templates.append(Template(
                note_type_id=self.note_type.id,
                name=f"Template {position}",
                front_html="{{Front}}", back_html="{{Back}}", position=position,
            ))
        db.session.add_all(templates)
        db.session.flush()
        db.session.add_all(Card(note_id=self.note.id, template_id=item.id)
                           for item in templates[1:])
        db.session.commit()
        note_id = str(self.note.id)
        expected_ids = [str(item.id) for item in templates]
        statements = []

        def capture(_connection, _cursor, statement, *_args):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            query = Card.query.join(Note, Card.note_id == Note.id).filter(Note.id == note_id)
            comps = list_available_compositions_for_query(query, clone_scope=None)
            self.assertEqual([item.template_id for item in comps], expected_ids)
            self.assertEqual(len(statements), 2)
            self.assertFalse(any("field_values" in statement for statement in statements))
            statements.clear()
            groups = group_available_compositions(comps[::-1])
            self.assertEqual([item.template_id for item in groups[0].compositions], expected_ids)
            self.assertEqual(len(statements), 1)
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)

    def test_discovery_preserves_installed_source_and_local_context(self):
        source_user = User(username=f"source_{uuid4().hex[:8]}", email=f"{uuid4().hex}@example.com")
        db.session.add(source_user)
        db.session.flush()
        source_deck = Deck(name="Source", owner_user_id=source_user.id)
        db.session.add(source_deck)
        db.session.flush()
        source_note = Note(user_id=source_user.id, deck_id=source_deck.id,
                           note_type_id=self.note_type.id, field_values={"Front": "source"})
        # Even a note in a local deck belongs to source context when its author
        # is not the installing learner.
        foreign_note = Note(user_id=source_user.id, deck_id=self.deck.id,
                            note_type_id=self.note_type.id, field_values={"Front": "foreign"})
        db.session.add_all([source_note, foreign_note])
        db.session.flush()
        source_card = Card(note_id=source_note.id, template_id=self.template_1.id)
        foreign_card = Card(note_id=foreign_note.id, template_id=self.template_2.id)
        db.session.add_all([source_card, foreign_card])
        db.session.commit()
        clone_scope = SimpleNamespace(
            local_deck_ids=[self.deck.id],
            install=SimpleNamespace(user_id=self.user.id, id="test-install"),
        )
        cards = [self.card_1, source_card, foreign_card]
        expected = {
            resolve_compatibility_composition_for_card(card, clone_scope).composition_id:
            resolve_compatibility_composition_for_card(card, clone_scope).to_dict()
            for card in cards
        }
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            Card.id.in_([card.id for card in cards])
        )
        comps = list_available_compositions_for_query(query, clone_scope=clone_scope)
        self.assertEqual({item.composition_id: item.to_dict() for item in comps}, expected)

    def test_empty_discovery_and_grouping(self):
        query = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == "missing")
        self.assertEqual(list_available_compositions_for_query(query, clone_scope=None), [])
        self.assertEqual(group_available_compositions([]), [])


if __name__ == "__main__":
    unittest.main()
