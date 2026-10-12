"""Unit and integration tests for distinct note counts by composition (GT-03)."""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import event

from app import create_app, db
from app.services.study_composition_service import (
    CONTEXT_INSTALLED_LOCAL,
    CONTEXT_INSTALLED_SOURCE,
    count_notes_by_composition,
    list_available_compositions_for_query,
    make_compatibility_composition_id,
    make_installed_composition_id,
)
from models.card import Card, card_id_clause
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from tests.study_note_fixtures import attach_template, create_note_user


class CompositionNoteCountTests(unittest.TestCase):
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
        self.user = create_note_user(db.session, username=f"user_{uid}", email=f"user_{uid}@example.com")
        self.user.set_password("pass")
        db.session.commit()

        self.note_type = NoteType(name="Test NoteType", user_id=self.user.id)
        db.session.add(self.note_type)
        db.session.commit()

        self.template_1 = attach_template(
            db.session,
            owner_user_id=self.user.id,
            note_type_id=self.note_type.id,
            name="Forward (Front -> Back)",
            front_html="<div>{{Front}}</div>",
            back_html="<div>{{Back}}</div>",
            position=0,
            is_default=True,
        )
        self.template_2 = attach_template(
            db.session,
            owner_user_id=self.user.id,
            note_type_id=self.note_type.id,
            name="Reverse (Back -> Front)",
            front_html="<div>{{Back}}</div>",
            back_html="<div>{{Front}}</div>",
            position=1,
            is_default=False,
        )
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
        # Cards are derived (ADR P11): only template_1 presents until a test
        # activates template_2's occurrence.
        self._set_template_2("RETIRED")
        db.session.commit()
        self.card_1 = Card.query.filter_by(note_id=self.note.id, template_id=self.template_1.id).one()

    def _set_template_2(self, status):
        from models.study_application import StudyApplication

        StudyApplication.query.filter_by(template_id=self.template_2.id).one().status_code = status
        db.session.flush()

    def tearDown(self):
        db.session.rollback()
        db.drop_all()
        self.app_ctx.pop()

    def test_owned_single_card(self):
        query = Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id == self.deck.id)
        compositions = list_available_compositions_for_query(query, clone_scope=None)
        counts = count_notes_by_composition(query, clone_scope=None, compositions=compositions)
        expected_id = make_compatibility_composition_id(self.note_type.id, self.template_1.id)
        self.assertEqual(counts, {expected_id: 1})

    def test_owned_two_templates_counts_notes(self):
        note2 = Note(
            user_id=self.user.id,
            deck_id=self.deck.id,
            note_type_id=self.note_type.id,
            field_values={"Front": "f2", "Back": "b2"},
        )
        note3 = Note(
            user_id=self.user.id,
            deck_id=self.deck.id,
            note_type_id=self.note_type.id,
            field_values={"Front": "f3", "Back": "b3"},
        )
        db.session.add_all([note2, note3])
        self._set_template_2("ACTIVE")
        db.session.commit()

        query = Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id == self.deck.id)
        compositions = list_available_compositions_for_query(query, clone_scope=None)
        counts = count_notes_by_composition(query, clone_scope=None, compositions=compositions)
        t1_id = make_compatibility_composition_id(self.note_type.id, self.template_1.id)
        t2_id = make_compatibility_composition_id(self.note_type.id, self.template_2.id)
        # Every Note presents both ACTIVE occurrences.
        self.assertEqual(counts, {t1_id: 3, t2_id: 3})

    def test_every_composition_has_key(self):
        note2 = Note(
            user_id=self.user.id,
            deck_id=self.deck.id,
            note_type_id=self.note_type.id,
            field_values={"Front": "f2", "Back": "b2"},
        )
        db.session.add(note2)
        self._set_template_2("ACTIVE")
        db.session.commit()

        query = Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id == self.deck.id)
        compositions = list_available_compositions_for_query(query, clone_scope=None)
        counts = count_notes_by_composition(query, clone_scope=None, compositions=compositions)
        self.assertEqual(set(counts.keys()), {c.composition_id for c in compositions})

    def test_empty_compositions(self):
        query = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == "missing")
        counts = count_notes_by_composition(query, clone_scope=None, compositions=[])
        self.assertEqual(counts, {})

    def test_installed_source_and_local_split(self):
        source_user = create_note_user(db.session, username=f"source_{uuid4().hex[:8]}", email=f"{uuid4().hex}@example.com")
        source_deck = Deck(name="Source", owner_user_id=source_user.id)
        db.session.add(source_deck)
        db.session.flush()
        source_note = Note(
            user_id=source_user.id,
            deck_id=source_deck.id,
            note_type_id=self.note_type.id,
            field_values={"Front": "source"},
        )
        foreign_note = Note(
            user_id=source_user.id,
            deck_id=self.deck.id,
            note_type_id=self.note_type.id,
            field_values={"Front": "foreign"},
        )
        db.session.add_all([source_note, foreign_note])
        self._set_template_2("ACTIVE")
        db.session.commit()
        source_card = Card.query.filter_by(note_id=source_note.id, template_id=self.template_1.id).one()
        foreign_card = Card.query.filter_by(note_id=foreign_note.id, template_id=self.template_2.id).one()

        clone_scope = SimpleNamespace(
            local_deck_ids=[self.deck.id],
            install=SimpleNamespace(user_id=self.user.id, id="test-install"),
        )
        cards = [self.card_1, source_card, foreign_card]
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            card_id_clause(db.session, [card.id for card in cards])
        )
        compositions = list_available_compositions_for_query(query, clone_scope=clone_scope)
        counts = count_notes_by_composition(query, clone_scope=clone_scope, compositions=compositions)
        local_t1 = make_installed_composition_id(
            install_id="test-install",
            context_kind=CONTEXT_INSTALLED_LOCAL,
            note_type_id=self.note_type.id,
            template_id=self.template_1.id,
        )
        source_t1 = make_installed_composition_id(
            install_id="test-install",
            context_kind=CONTEXT_INSTALLED_SOURCE,
            note_type_id=self.note_type.id,
            template_id=self.template_1.id,
        )
        source_t2 = make_installed_composition_id(
            install_id="test-install",
            context_kind=CONTEXT_INSTALLED_SOURCE,
            note_type_id=self.note_type.id,
            template_id=self.template_2.id,
        )
        self.assertEqual(counts, {local_t1: 1, source_t1: 1, source_t2: 1})

    def test_does_not_issue_per_composition_queries(self):
        note2 = Note(
            user_id=self.user.id,
            deck_id=self.deck.id,
            note_type_id=self.note_type.id,
            field_values={"Front": "f2", "Back": "b2"},
        )
        db.session.add(note2)
        self._set_template_2("ACTIVE")
        db.session.commit()

        query = Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id == self.deck.id)
        compositions = list_available_compositions_for_query(query, clone_scope=None)
        queries = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)

        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            count_notes_by_composition(query, clone_scope=None, compositions=compositions)
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)

        select_queries = [q for q in queries if q.strip().upper().startswith("SELECT")]
        self.assertEqual(len(select_queries), 1)


class CompositionNoteCountsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = create_note_user(db.session, username="admin", email="admin@example.com", is_admin=True)
            user.set_password("password")
            self.user_id = user.id

            deck = Deck(name="Deck A", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id

            nt = NoteType(name="Test NoteType", user_id=self.user_id)
            db.session.add(nt)
            db.session.flush()
            self.note_type_id = nt.id

            fd = FieldDef(note_type_id=nt.id, name="Front", field_type="text", position=0)
            db.session.add(fd)

            t1 = attach_template(
                db.session,
                owner_user_id=self.user_id,
                note_type_id=nt.id,
                name="T1",
                front_html="<div>{{Front}}</div>",
                back_html="<div>{{Front}}</div>",
                position=0,
                is_default=True,
            )
            t2 = attach_template(
                db.session,
                owner_user_id=self.user_id,
                note_type_id=nt.id,
                name="T2",
                front_html="<div>{{Front}} 2</div>",
                back_html="<div>{{Front}} 2</div>",
                position=1,
                is_default=False,
            )
            self.template_1_id = str(t1.id)
            self.template_2_id = str(t2.id)

            n1 = Note(
                user_id=self.user_id,
                deck_id=self.deck_id,
                note_type_id=nt.id,
                field_values={"Front": "card 1"},
            )
            n2 = Note(
                user_id=self.user_id,
                deck_id=self.deck_id,
                note_type_id=nt.id,
                field_values={"Front": "card 2"},
            )
            # Both Notes present both Templates (ADR P11).
            db.session.add_all([n1, n2])
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "admin@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_no_param_response_unchanged(self):
        response = self.client.get(f"/api/study/scopes/deck/{self.deck_id}/compositions")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertNotIn("note_counts", body)

    def test_include_counts_adds_only_note_counts(self):
        res_no_param = self.client.get(f"/api/study/scopes/deck/{self.deck_id}/compositions")
        res_with_counts = self.client.get(f"/api/study/scopes/deck/{self.deck_id}/compositions?include_counts=1")
        self.assertEqual(res_with_counts.status_code, 200)
        body_no = res_no_param.get_json()
        body_with = res_with_counts.get_json()

        self.assertIn("note_counts", body_with)
        counts = body_with.pop("note_counts")
        self.assertEqual(body_with, body_no)

        t1_comp_id = [c["composition_id"] for c in body_no["compositions"] if c["template_id"] == self.template_1_id][0]
        t2_comp_id = [c["composition_id"] for c in body_no["compositions"] if c["template_id"] == self.template_2_id][0]
        self.assertEqual(counts, {t1_comp_id: 2, t2_comp_id: 2})

    def test_include_counts_accepts_true_yes(self):
        for val in ("true", "YES", "1", "True"):
            res = self.client.get(f"/api/study/scopes/deck/{self.deck_id}/compositions?include_counts={val}")
            self.assertEqual(res.status_code, 200)
            self.assertIn("note_counts", res.get_json(), f"Failed for {val}")

    def test_include_counts_zero_ignored(self):
        for val in ("0", "false", "no", ""):
            res = self.client.get(f"/api/study/scopes/deck/{self.deck_id}/compositions?include_counts={val}")
            self.assertEqual(res.status_code, 200)
            self.assertNotIn("note_counts", res.get_json(), f"Should not include counts for {val}")


if __name__ == "__main__":
    unittest.main()
