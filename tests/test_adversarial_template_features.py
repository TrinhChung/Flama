"""Adversarial stress tests and boundary edge cases for GT-01, GT-02, and GT-03.

Executed by challenger_m1_1 to empirically stress-test:
- GT-01: Unicode/special chars in field names, duplicate/negative/sparse positions,
  whitespace/empty fallbacks, REST creation with unconventional inputs.
- GT-02: Template note count cardinality stress (0 cards, multiple cards pointing
  to same note, 50+ distinct notes), cross-user isolation, and detail endpoint isolation.
- GT-03: Scope composition note counts truthy/falsy query string variations,
  empty deck (0 notes/cards), subdeck hierarchy note distinctness, multi-card
  deduplication, and single SQL SELECT assertion under high cardinality.
"""

import unittest
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import event

from app import create_app, db
from app.services.flashcards_share_service import default_template_sources
from app.services.study_composition_service import (
    CONTEXT_INSTALLED_LOCAL,
    CONTEXT_INSTALLED_SOURCE,
    count_notes_by_composition,
    list_available_compositions_for_query,
    make_compatibility_composition_id,
    make_installed_composition_id,
)
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from tests.study_note_fixtures import attach_template, create_note_user


class AdversarialGT01DefaultTemplateSourcesTests(unittest.TestCase):
    """Adversarial stress testing for GT-01 dynamic default template content."""

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
        self.app.config["STUDY_PROGRESS_SHADOW_COMPARE_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = create_note_user(db.session, username="admin_gt01", email="admin_gt01@example.com", is_admin=True)
            user.set_password("password")
            self.user_id = user.id

            deck = Deck(name="Deck GT01", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "admin_gt01@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_unicode_japanese_and_special_chars_in_field_names(self):
        """Verify helper preserves complex Unicode, Japanese IME, slashes, and braces."""
        field_rows = [
            (0, "漢字（Kanji）"),
            (1, "Audio / 発音 / 音声"),
            (2, "例文 (Example & Notes)"),
        ]
        front, back = default_template_sources(field_rows)
        self.assertEqual(front, "{{漢字（Kanji）}}")
        self.assertEqual(back, "{{漢字（Kanji）}}<hr>{{Audio / 発音 / 音声}}")

    def test_duplicate_positions_tie_breaker(self):
        """Verify stable alphabetical tie-breaking when fields share identical position."""
        # Both at pos 0: 'B_Field' and 'A_Field'
        field_rows = [(0, "B_Field"), (0, "A_Field"), (1, "C_Field")]
        front, back = default_template_sources(field_rows)
        self.assertEqual(front, "{{A_Field}}")
        self.assertEqual(back, "{{A_Field}}<hr>{{B_Field}}")

    def test_negative_and_sparse_positions(self):
        """Verify integer ordering with negative, zero, and huge sparse positions."""
        field_rows = [
            (1000, "HugePositive"),
            (-99, "LowestNegative"),
            (0, "ZeroPos"),
            (-1, "MinorNegative"),
        ]
        front, back = default_template_sources(field_rows)
        self.assertEqual(front, "{{LowestNegative}}")
        self.assertEqual(back, "{{LowestNegative}}<hr>{{MinorNegative}}")

    def test_whitespace_and_empty_filtering_fallbacks(self):
        """Verify all varieties of whitespace/empty names are stripped or fallen back to {{Word}}."""
        # Only whitespace/empty names
        field_rows_empty = [(0, "   "), (1, "\t\n\r"), (2, ""), (3, None)]
        front, back = default_template_sources(field_rows_empty)
        self.assertEqual(front, "{{Word}}")
        self.assertEqual(back, "{{Word}}")

        # Mixed: valid fields surrounded by empty/whitespace ones
        field_rows_mixed = [
            (0, "   "),
            (1, "  ValidPrimary  "),
            (2, ""),
            (3, "\nValidSecondary\t"),
            (4, "   "),
        ]
        front, back = default_template_sources(field_rows_mixed)
        self.assertEqual(front, "{{ValidPrimary}}")
        self.assertEqual(back, "{{ValidPrimary}}<hr>{{ValidSecondary}}")

    def test_rest_api_create_notetype_with_negative_positions_and_unicode(self):
        """Verify POST /api/note-types correctly propagates negative positions and Unicode fields."""
        payload = {
            "name": "Unicode & Sparse NT",
            "field_defs": [
                {"name": "意味 (Meaning)", "field_type": "text", "position": 10},
                {"name": "単語 [Word]", "field_type": "text", "position": -5, "required": True},
            ],
        }
        response = self.client.post("/api/note-types", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data.get("templates"))
        first_tpl = data["templates"][0]
        self.assertEqual(first_tpl["front_html"], "{{単語 [Word]}}")
        self.assertEqual(first_tpl["back_html"], "{{単語 [Word]}}<hr>{{意味 (Meaning)}}")

    def test_rest_api_create_template_with_empty_payload_uses_existing_fields(self):
        """Verify POST /api/note-types/<id>/templates with {} adopts note-type field structure."""
        # First create note type
        nt_resp = self.client.post(
            "/api/note-types",
            json={
                "name": "NT For New Template",
                "field_defs": [
                    {"name": "FrontField", "field_type": "text", "position": 0},
                    {"name": "BackField", "field_type": "text", "position": 1},
                ],
            },
        )
        self.assertEqual(nt_resp.status_code, 201)
        nt_id = nt_resp.get_json()["id"]

        # Now create new template without specifying front_html or back_html
        tpl_resp = self.client.post(f"/api/note-types/{nt_id}/templates", json={})
        self.assertEqual(tpl_resp.status_code, 201)
        tpl_data = tpl_resp.get_json()
        self.assertEqual(tpl_data["front_html"], "{{FrontField}}")
        self.assertEqual(tpl_data["back_html"], "{{FrontField}}<hr>{{BackField}}")


class AdversarialGT02TemplateNoteCountTests(unittest.TestCase):
    """Adversarial stress testing for GT-02 template note count."""

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
        self.app.config["STUDY_PROGRESS_SHADOW_COMPARE_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            self.user_a = create_note_user(db.session, username="user_a", email="user_a@example.com")
            self.user_a.set_password("pass_a")
            self.user_b = create_note_user(db.session, username="user_b", email="user_b@example.com")
            self.user_b.set_password("pass_b")
            self.user_a_id = self.user_a.id
            self.user_b_id = self.user_b.id

            self.deck_a = Deck(name="Deck User A", owner_user_id=self.user_a_id)
            self.deck_b = Deck(name="Deck User B", owner_user_id=self.user_b_id)
            db.session.add_all([self.deck_a, self.deck_b])
            db.session.flush()
            self.deck_a_id = self.deck_a.id
            self.deck_b_id = self.deck_b.id
            db.session.commit()

        # Login as User A by default
        self.client.post(
            "/login",
            data={"email": "user_a@example.com", "password": "pass_a"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_multi_cards_same_note_does_not_inflate_count(self):
        """Stress: multiple cards pointing to the same (note_id, template_id) count as 1 note."""
        with self.app.app_context():
            nt = NoteType(name="NT Multi Card", user_id=self.user_a_id)
            db.session.add(nt)
            db.session.flush()
            nt_id = nt.id

            t1 = attach_template(
                db.session,
                note_type_id=nt_id,
                owner_user_id=self.user_a_id,
                name="T1",
                front_html="{{Front}}",
                back_html="{{Back}}",
                position=0,
                is_default=True,
            )
            t1_id = t1.id

            n1 = Note(user_id=self.user_a_id, deck_id=self.deck_a_id, note_type_id=nt_id, field_values={"Front": "val"})
            db.session.add(n1)
            db.session.flush()

            from models.study_application import StudyApplication

            # Create 5 distinct StudyApplication occurrences for the same template:
            # the Note presents one derived Card per occurrence (ADR P11).
            apps = [
                StudyApplication(note_type_id=nt_id, template_id=t1_id, occurrence_key=f"occ_{i}")
                for i in range(5)
            ]
            db.session.add_all(apps)
            db.session.commit()
            self.assertEqual(Card.query.filter_by(note_id=n1.id).count(), 6)

        response = self.client.get(f"/api/note-types/{nt_id}/templates")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], t1_id)
        self.assertEqual(items[0]["note_count"], 1)

    def test_high_cardinality_and_unbalanced_distribution(self):
        """Stress: 50 distinct notes on T1 and T2; T3 retired presents none (ADR P11)."""
        with self.app.app_context():
            nt = NoteType(name="NT High Card", user_id=self.user_a_id)
            db.session.add(nt)
            db.session.flush()
            nt_id = nt.id

            t1 = attach_template(db.session, note_type_id=nt_id, owner_user_id=self.user_a_id, name="T1", front_html="1", back_html="1", position=0, is_default=True)
            t2 = attach_template(db.session, note_type_id=nt_id, owner_user_id=self.user_a_id, name="T2", front_html="2", back_html="2", position=1, is_default=False)
            t3 = attach_template(db.session, note_type_id=nt_id, owner_user_id=self.user_a_id, name="T3", front_html="3", back_html="3", position=2, is_default=False)
            t1_id, t2_id, t3_id = t1.id, t2.id, t3.id

            notes = [
                Note(user_id=self.user_a_id, deck_id=self.deck_a_id, note_type_id=nt_id, field_values={"F": f"n_{i}"})
                for i in range(50)
            ]
            db.session.add_all(notes)
            db.session.flush()

            # Every Note presents every ACTIVE occurrence; T3's is retired.
            from models.study_application import StudyApplication

            StudyApplication.query.filter_by(template_id=t3_id).one().status_code = "RETIRED"
            db.session.commit()

        response = self.client.get(f"/api/note-types/{nt_id}/templates")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        self.assertEqual(len(items), 2)

        counts_by_id = {item["id"]: item["note_count"] for item in items}
        self.assertEqual(counts_by_id[t1_id], 50)
        self.assertEqual(counts_by_id[t2_id], 50)
        self.assertNotIn(t3_id, counts_by_id)

    def test_cross_user_isolation(self):
        """Verify User B cannot access User A's templates or inspect counts (returns 404)."""
        with self.app.app_context():
            nt_a = NoteType(name="NT Private A", user_id=self.user_a_id)
            db.session.add(nt_a)
            db.session.flush()
            t_a = attach_template(db.session, note_type_id=nt_a.id, owner_user_id=self.user_a_id, name="T_A", front_html="A", back_html="A", position=0, is_default=True)
            db.session.commit()
            nt_a_id = nt_a.id

        # Switch session to User B
        self.client.post("/logout", follow_redirects=True)
        self.client.post(
            "/login",
            data={"email": "user_b@example.com", "password": "pass_b"},
            follow_redirects=True,
        )

        response = self.client.get(f"/api/note-types/{nt_a_id}/templates")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json().get("error"), "FIELD_NOT_FOUND")

    def test_detail_endpoint_strictly_omits_note_count(self):
        """Verify GET /api/note-types/<id> NEVER includes note_count in any template object."""
        with self.app.app_context():
            nt = NoteType(name="NT Detail Isolation", user_id=self.user_a_id)
            db.session.add(nt)
            db.session.flush()
            nt_id = nt.id

            t1 = attach_template(db.session, note_type_id=nt_id, owner_user_id=self.user_a_id, name="T1", front_html="1", back_html="1", position=0, is_default=True)
            t2 = attach_template(db.session, note_type_id=nt_id, owner_user_id=self.user_a_id, name="T2", front_html="2", back_html="2", position=1, is_default=False)
            db.session.flush()

            n1 = Note(user_id=self.user_a_id, deck_id=self.deck_a_id, note_type_id=nt_id, field_values={})
            db.session.add(n1)
            db.session.commit()

        # Check detail endpoint
        detail_resp = self.client.get(f"/api/note-types/{nt_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_data = detail_resp.get_json()
        self.assertTrue(detail_data.get("templates"))
        for tpl in detail_data["templates"]:
            self.assertNotIn("note_count", tpl, f"note_count leaked in detail template: {tpl}")

        # In contrast, template listing endpoint DOES have note_count
        list_resp = self.client.get(f"/api/note-types/{nt_id}/templates")
        self.assertEqual(list_resp.status_code, 200)
        list_items = list_resp.get_json()["items"]
        for tpl in list_items:
            self.assertIn("note_count", tpl, f"note_count missing in template listing: {tpl}")


class AdversarialGT03CompositionNoteCountsTests(unittest.TestCase):
    """Adversarial stress testing for GT-03 study scope composition note counts."""

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
        self.app.config["STUDY_PROGRESS_SHADOW_COMPARE_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            self.user = create_note_user(db.session, username="admin_gt03", email="admin_gt03@example.com", is_admin=True)
            self.user.set_password("pass_gt03")
            self.user_id = self.user.id

            self.parent_deck = Deck(name="Parent Deck", owner_user_id=self.user_id)
            db.session.add(self.parent_deck)
            db.session.flush()
            self.parent_deck_id = self.parent_deck.id

            self.subdeck = Deck(name="Sub Deck", owner_user_id=self.user_id, parent_id=self.parent_deck_id)
            db.session.add(self.subdeck)
            db.session.flush()
            self.subdeck_id = self.subdeck.id

            self.empty_deck = Deck(name="Empty Deck", owner_user_id=self.user_id)
            db.session.add(self.empty_deck)
            db.session.flush()
            self.empty_deck_id = self.empty_deck.id

            self.note_type = NoteType(name="Composition NT", user_id=self.user_id)
            db.session.add(self.note_type)
            db.session.flush()
            self.nt_id = self.note_type.id

            self.t1 = attach_template(db.session, note_type_id=self.nt_id, owner_user_id=self.user_id, name="T1", front_html="1", back_html="1", position=0, is_default=True)
            self.t2 = attach_template(db.session, note_type_id=self.nt_id, owner_user_id=self.user_id, name="T2", front_html="2", back_html="2", position=1, is_default=False)
            self.t1_id = self.t1.id
            self.t2_id = self.t2.id
            # Only T1 presents Cards until a test activates T2 (ADR P11).
            from models.study_application import StudyApplication

            StudyApplication.query.filter_by(template_id=self.t2_id).one().status_code = "RETIRED"
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "admin_gt03@example.com", "password": "pass_gt03"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_include_counts_comprehensive_truthy_variations(self):
        """Stress: all casing, trimming, and truthy representations include note_counts."""
        with self.app.app_context():
            n = Note(user_id=self.user_id, deck_id=self.parent_deck_id, note_type_id=self.nt_id, field_values={})
            db.session.add(n)
            db.session.commit()

        truthy_values = ["1", "true", "True", "TRUE", "tRuE", "yes", "YES", "YeS", " 1 ", " true\t", "\nYES "]
        for val in truthy_values:
            resp = self.client.get(f"/api/study/scopes/deck/{self.parent_deck_id}/compositions?include_counts={val}")
            self.assertEqual(resp.status_code, 200, f"Failed HTTP 200 for include_counts='{val}'")
            body = resp.get_json()
            self.assertIn("note_counts", body, f"Expected note_counts for '{val}'")
            self.assertEqual(len(body["note_counts"]), 1)
            self.assertEqual(list(body["note_counts"].values())[0], 1)

    def test_include_counts_comprehensive_falsy_variations(self):
        """Stress: non-truthy values, negative integers, null/undefined strictly omit note_counts."""
        with self.app.app_context():
            n = Note(user_id=self.user_id, deck_id=self.parent_deck_id, note_type_id=self.nt_id, field_values={})
            db.session.add(n)
            db.session.commit()

        falsy_values = ["0", "false", "False", "FALSE", "no", "NO", "No", "random", "-1", "2", "none", "null", "undefined", "", "   "]
        for val in falsy_values:
            resp = self.client.get(f"/api/study/scopes/deck/{self.parent_deck_id}/compositions?include_counts={val}")
            self.assertEqual(resp.status_code, 200)
            body = resp.get_json()
            self.assertNotIn("note_counts", body, f"Unexpected note_counts present for falsy '{val}'")

    def test_empty_deck_zero_notes_and_cards(self):
        """Verify deck with 0 notes returns cardinality: 'zero', empty compositions, and empty note_counts."""
        resp = self.client.get(f"/api/study/scopes/deck/{self.empty_deck_id}/compositions?include_counts=1")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["cardinality"], "zero")
        self.assertEqual(body["compositions"], [])
        self.assertEqual(body["groups"], [])
        self.assertEqual(body["note_counts"], {})

    def test_subdeck_hierarchy_distinct_note_aggregation(self):
        """Stress: Parent deck scope must accurately aggregate distinct notes across subdecks."""
        with self.app.app_context():
            # Note 1 in Parent Deck; Notes 2 and 3 in Subdeck. With T2 active
            # every Note presents both Templates (ADR P11).
            from models.study_application import StudyApplication

            n1 = Note(user_id=self.user_id, deck_id=self.parent_deck_id, note_type_id=self.nt_id, field_values={"F": "1"})
            n2 = Note(user_id=self.user_id, deck_id=self.subdeck_id, note_type_id=self.nt_id, field_values={"F": "2"})
            n3 = Note(user_id=self.user_id, deck_id=self.subdeck_id, note_type_id=self.nt_id, field_values={"F": "3"})
            db.session.add_all([n1, n2, n3])
            StudyApplication.query.filter_by(template_id=self.t2_id).one().status_code = "ACTIVE"
            db.session.commit()

        # Query parent deck with include_counts=1
        resp = self.client.get(f"/api/study/scopes/deck/{self.parent_deck_id}/compositions?include_counts=1")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["cardinality"], "many")
        self.assertEqual(len(body["compositions"]), 2)

        t1_comp_id = next(c["composition_id"] for c in body["compositions"] if c["template_id"] == self.t1_id)
        t2_comp_id = next(c["composition_id"] for c in body["compositions"] if c["template_id"] == self.t2_id)

        # Each Template has Note 1 (parent) + Notes 2 and 3 (subdeck) = 3 distinct notes
        self.assertEqual(body["note_counts"][t1_comp_id], 3)
        self.assertEqual(body["note_counts"][t2_comp_id], 3)

    def test_single_sql_query_stress_under_high_cardinality(self):
        """Stress: 100 notes with multiple templates executed in exactly ONE single SELECT query."""
        with self.app.app_context():
            # Keep template references in scope so id() is stable during Card flush
            all_templates = [
                attach_template(db.session, note_type_id=self.nt_id, owner_user_id=self.user_id, name=f"T_stress_{i}", front_html="f", back_html="b", position=i, is_default=(i == 0))
                for i in range(5)
            ]
            all_template_ids = [t.id for t in all_templates]

            # Create 100 notes across parent deck and subdeck
            notes = [
                Note(
                    user_id=self.user_id,
                    deck_id=self.parent_deck_id if i % 2 == 0 else self.subdeck_id,
                    note_type_id=self.nt_id,
                    field_values={"i": str(i)},
                )
                for i in range(100)
            ]
            db.session.add_all(notes)
            # Every Note presents every stress Template; T1/T2 are retired.
            from models.study_application import StudyApplication

            StudyApplication.query.filter_by(template_id=self.t1_id).one().status_code = "RETIRED"
            db.session.commit()

            # Now build query and capture SQL statement count
            scope_deck_ids = [self.parent_deck_id, self.subdeck_id]
            query = Card.query.join(Note, Card.note_id == Note.id).filter(
                Note.user_id == self.user_id,
                Note.deck_id.in_(scope_deck_ids),
            )
            compositions = list_available_compositions_for_query(query, clone_scope=None)
            self.assertEqual(len(compositions), 5)

            queries = []

            def capture_sql(conn, cursor, statement, parameters, context, executemany):
                queries.append(statement)

            event.listen(db.engine, "before_cursor_execute", capture_sql)
            try:
                counts = count_notes_by_composition(query, clone_scope=None, compositions=compositions)
            finally:
                event.remove(db.engine, "before_cursor_execute", capture_sql)

            select_queries = [q for q in queries if q.strip().upper().startswith("SELECT")]
            # STRICT REQUIREMENT: exactly 1 SELECT query!
            self.assertEqual(len(select_queries), 1, f"Expected 1 SELECT query, got {len(select_queries)}: {select_queries}")

            # Every Note presents every ACTIVE occurrence (ADR P11).
            id_map = {template_id: 100 for template_id in all_template_ids}

            for comp in compositions:
                exp_count = id_map[comp.template_id]
                self.assertEqual(counts[comp.composition_id], exp_count)


if __name__ == "__main__":
    unittest.main()
