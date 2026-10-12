"""Phase 3 Exit Gate — Composition determinism and unambiguous resolution.

Exit gate spec (study-interaction-trigger-algorithm-plan.md, line 1315):
  "every effective Card/application context resolves unambiguously to one
   behaviorally equivalent compatibility composition. A source Card reused
   through different install/clone overlays may require context-specific
   application resolution; this gate does not assume one global composition
   per physical Card."
"""

import unittest
from uuid import uuid4
from types import SimpleNamespace

from app import create_app, db
from models.card import Card
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from tests.study_note_fixtures import attach_template
from app.services.study_composition_service import (
    AppliedComposition,
    list_available_compositions_for_scope,
    make_compatibility_composition_id,
    resolve_compatibility_composition_for_card,
)


class CompositionExitGateTests(unittest.TestCase):
    """Automated verification of the Phase 3 exit gate."""

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

    def tearDown(self):
        db.session.rollback()
        db.drop_all()
        self.app_ctx.pop()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_note_type(self, name="NT", *, templates=None):
        """Create a NoteType with specified templates (default: one)."""
        nt = NoteType(name=name, user_id=self.user.id)
        db.session.add(nt)
        db.session.commit()

        tpl_specs = templates or [("Default", True)]
        created = []
        for pos, (tpl_name, is_default) in enumerate(tpl_specs):
            tpl = attach_template(db.session, owner_user_id=self.user.id,
                note_type_id=nt.id,
                name=tpl_name,
                front_html="<div>{{Front}}</div>",
                back_html="<div>{{Back}}</div>",
                position=pos,
                is_default=is_default,
            )
            db.session.add(tpl)
            created.append(tpl)
        db.session.commit()
        return nt, created

    def _make_deck(self, name="Deck", *, note_type=None, parent_id=None):
        deck = Deck(
            name=name,
            owner_user_id=self.user.id,
            note_type_id=note_type.id if note_type else None,
            parent_id=parent_id,
        )
        db.session.add(deck)
        db.session.commit()
        return deck

    def _make_card(self, deck, note_type, template):
        note = Note(
            user_id=self.user.id,
            deck_id=deck.id,
            note_type_id=note_type.id,
            field_values={"Front": "Q", "Back": "A"},
        )
        db.session.add(note)
        db.session.commit()
        card = Card.query.filter_by(note_id=note.id, template_id=template.id).one()
        db.session.commit()
        return card

    # ------------------------------------------------------------------
    # Gate 1: Every card resolves to exactly one composition
    # ------------------------------------------------------------------

    def test_every_card_resolves_to_exactly_one_composition(self):
        """Each Card maps to exactly one AppliedComposition via its Template."""
        nt, (tpl_a, tpl_b) = self._make_note_type(
            templates=[("Front->Back", True), ("Back->Front", False)]
        )
        deck = self._make_deck(note_type=nt)
        card_a = self._make_card(deck, nt, tpl_a)
        card_b = self._make_card(deck, nt, tpl_b)

        comp_a = resolve_compatibility_composition_for_card(card_a)
        comp_b = resolve_compatibility_composition_for_card(card_b)

        # Each is an AppliedComposition
        self.assertIsInstance(comp_a, AppliedComposition)
        self.assertIsInstance(comp_b, AppliedComposition)

        # Each maps to its own template
        self.assertEqual(comp_a.template_id, str(tpl_a.id))
        self.assertEqual(comp_b.template_id, str(tpl_b.id))

        # composition_id encodes identity correctly
        self.assertEqual(
            comp_a.composition_id,
            make_compatibility_composition_id(nt.id, tpl_a.id),
        )
        self.assertEqual(
            comp_b.composition_id,
            make_compatibility_composition_id(nt.id, tpl_b.id),
        )

        # They are distinct compositions
        self.assertNotEqual(comp_a.composition_id, comp_b.composition_id)

    # ------------------------------------------------------------------
    # Gate 2: Owned cards retain the legacy compatibility projection
    # ------------------------------------------------------------------

    def test_owned_cards_in_different_decks_share_legacy_projection(self):
        """Owned cards with the same Template share one legacy projection.

        Real overlay context coverage lives in
        test_shared_deck_logical_overlay_via_real_service_path; this test is
        intentionally limited to the non-installed compatibility grammar.
        """
        nt, (tpl,) = self._make_note_type(templates=[("Primary", True)])
        source_deck = self._make_deck("Source", note_type=nt)
        second_deck = self._make_deck("Second owned deck", note_type=nt)

        # Same owned NoteType/Template, different owned decks.
        source_card = self._make_card(source_deck, nt, tpl)
        second_card = self._make_card(second_deck, nt, tpl)

        comp_source = resolve_compatibility_composition_for_card(source_card)
        comp_second = resolve_compatibility_composition_for_card(second_card)

        # Both resolve to the same composition identity (same Template)
        self.assertEqual(comp_source.composition_id, comp_second.composition_id)
        self.assertEqual(comp_source.template_id, comp_second.template_id)
        self.assertEqual(comp_source.note_type_id, comp_second.note_type_id)

        # Behaviorally equivalent — all runtime fields match
        self.assertEqual(comp_source.interaction_key, comp_second.interaction_key)
        self.assertEqual(comp_source.trigger_key, comp_second.trigger_key)
        self.assertEqual(comp_source.algorithm_key, comp_second.algorithm_key)
        self.assertEqual(comp_source.algorithm_version, comp_second.algorithm_version)

    # ------------------------------------------------------------------
    # Gate 3: Mixed-NoteType deck compositions are distinct and complete
    # ------------------------------------------------------------------

    def test_mixed_notetype_deck_compositions_are_distinct(self):
        """A parent deck with child decks of different NoteTypes produces
        compositions from ALL NoteTypes with no duplicates."""
        nt_jp, (tpl_jp,) = self._make_note_type(
            "Japanese", templates=[("JP Template", True)]
        )
        nt_en, (tpl_en_a, tpl_en_b) = self._make_note_type(
            "English", templates=[("EN Forward", True), ("EN Reverse", False)]
        )

        parent = self._make_deck("Parent")
        child_jp = self._make_deck("Japanese Child", note_type=nt_jp, parent_id=parent.id)
        child_en = self._make_deck("English Child", note_type=nt_en, parent_id=parent.id)

        self._make_card(child_jp, nt_jp, tpl_jp)
        self._make_card(child_en, nt_en, tpl_en_a)

        comps = list_available_compositions_for_scope("deck", parent.id, self.user.id)

        # Should include templates from both NoteTypes (recursive subtree)
        comp_ids = {c.composition_id for c in comps}
        expected_ids = {
            make_compatibility_composition_id(nt_jp.id, tpl_jp.id),
            make_compatibility_composition_id(nt_en.id, tpl_en_a.id),
            make_compatibility_composition_id(nt_en.id, tpl_en_b.id),
        }
        self.assertEqual(comp_ids, expected_ids)

        # No duplicates
        self.assertEqual(len(comps), len(comp_ids))

    # ------------------------------------------------------------------
    # Gate 4: Deleted template raises clear error
    # ------------------------------------------------------------------

    def test_deleted_template_card_raises_clear_error(self):
        """If a Card references a Template that no longer exists in the DB,
        resolution fails with a clear ValueError."""
        nt, (tpl,) = self._make_note_type(templates=[("Doomed", True)])
        deck = self._make_deck(note_type=nt)
        card = self._make_card(deck, nt, tpl)

        # A damaged historical reference cannot resolve a missing definition.
        # Current Cards are read-only, so no physical UPDATE is possible.
        fake_template_id = str(uuid4())
        card_reloaded = SimpleNamespace(id=card.id, template_id=fake_template_id, template=None)

        with self.assertRaises(ValueError) as ctx:
            resolve_compatibility_composition_for_card(card_reloaded)

        self.assertIn(str(card_reloaded.id), str(ctx.exception))
        self.assertIn("missing template", str(ctx.exception).lower())

    # ------------------------------------------------------------------
    # Gate 5: Determinism — identical results across calls
    # ------------------------------------------------------------------

    def test_composition_determinism_across_calls(self):
        """Calling resolve twice for the same card yields identical results."""
        nt, (tpl,) = self._make_note_type(templates=[("Stable", True)])
        deck = self._make_deck(note_type=nt)
        card = self._make_card(deck, nt, tpl)

        comp_1 = resolve_compatibility_composition_for_card(card)
        comp_2 = resolve_compatibility_composition_for_card(card)

        # Frozen dataclass equality
        self.assertEqual(comp_1, comp_2)

        # All fields identical
        self.assertEqual(comp_1.composition_id, comp_2.composition_id)
        self.assertEqual(comp_1.mode_key, comp_2.mode_key)
        self.assertEqual(comp_1.interaction_key, comp_2.interaction_key)
        self.assertEqual(comp_1.trigger_key, comp_2.trigger_key)
        self.assertEqual(comp_1.trigger_contract_version, comp_2.trigger_contract_version)
        self.assertEqual(comp_1.algorithm_key, comp_2.algorithm_key)
        self.assertEqual(comp_1.algorithm_version, comp_2.algorithm_version)

    # ------------------------------------------------------------------
    # Gate 6: note_type scope returns owned compositions
    # ------------------------------------------------------------------

    def test_note_type_scope_returns_compositions(self):
        """list_available_compositions_for_scope('note_type', ...) returns
        all Templates for the owned NoteType."""
        nt, (tpl_a, tpl_b) = self._make_note_type(
            templates=[("Forward", True), ("Reverse", False)]
        )
        deck = self._make_deck("NoteType scope", note_type=nt)
        self._make_card(deck, nt, tpl_a)
        self._make_card(deck, nt, tpl_b)

        comps = list_available_compositions_for_scope(
            "note_type", nt.id, self.user.id
        )
        comp_ids = {c.composition_id for c in comps}
        expected = {
            make_compatibility_composition_id(nt.id, tpl_a.id),
            make_compatibility_composition_id(nt.id, tpl_b.id),
        }
        self.assertEqual(comp_ids, expected)

    # ------------------------------------------------------------------
    # Gate 7: Empty deck does not advertise an unusable composition
    # ------------------------------------------------------------------

    def test_empty_deck_has_no_eligible_composition(self):
        """An empty deck does not advertise a Template without a Card."""
        nt, (_tpl,) = self._make_note_type(templates=[("Solo", True)])
        deck = self._make_deck("EmptyDeck", note_type=nt)

        comps = list_available_compositions_for_scope(
            "deck", deck.id, self.user.id
        )
        self.assertEqual(comps, [])

    # ------------------------------------------------------------------
    # Gate 8: Permission check rejects foreign NoteType
    # ------------------------------------------------------------------

    def test_scope_permission_rejects_foreign_note_type(self):
        """list_available_compositions_for_scope('note_type', ...) returns
        empty list when the NoteType belongs to a different user."""
        nt, _ = self._make_note_type(templates=[("Private", True)])

        other_uid = uuid4().hex[:8]
        other_user = User(
            username=f"other_{other_uid}",
            email=f"other_{other_uid}@example.com",
        )
        other_user.set_password("pass")
        db.session.add(other_user)
        db.session.commit()

        # Other user should get empty list for this NoteType
        comps = list_available_compositions_for_scope(
            "note_type", nt.id, other_user.id
        )
        self.assertEqual(comps, [])


if __name__ == "__main__":
    unittest.main()
