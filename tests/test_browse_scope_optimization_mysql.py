"""Browse subtree and compact-editor regressions on disposable local MySQL."""

import os
import unittest
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import inspect

from app.repositories import browse_note_repository
from app.services import browse_card_service, browse_note_service, flashcards_share
from models import db
from models.deck import Deck
from models.note import Note
from tests import test_browse_mysql_contract as mysql_harness
from tests import test_browse_query_bounds as fixtures


@unittest.skipUnless(os.getenv("FLAMA_BROWSE_MYSQL_TESTS") == "1", "Opt-in local MySQL qualification")
class BrowseScopeOptimizationMySQLTests(unittest.TestCase):
    setUp = mysql_harness.BrowseMySQLContractTests.setUp

    def _context(self, roots, *, admin_mode=False):
        return browse_card_service._build_browse_query(user_id=self.learner_id,
            admin_mode=admin_mode, timezone_name="UTC", query_args={},
            notes_only=True, scope_only=True, scoped_deck_ids=roots)

    def _detail(self, note_id, *, admin_mode=False, compact=True):
        return browse_note_service.get_note_detail(user_id=self.learner_id,
            admin_mode=admin_mode, timezone_name="UTC", note_id=note_id, compact=compact)

    def test_admin_selected_subtree_does_not_load_collection_or_cross_foreign_child(self):
        root_id = fixtures.seed_owned_deck(self.learner_id, count=6)
        child = Deck.query.filter_by(parent_id=root_id).one()
        child.owner_user_id = None
        stranger_id = fixtures.seed_learner(username="scope-stranger")
        foreign = Deck(name="Foreign child", parent_id=root_id, owner_user_id=stranger_id)
        unrelated = Deck(name="Unrelated owned", owner_user_id=self.learner_id)
        db.session.add_all([foreign, unrelated])
        db.session.flush()
        grandchild = Deck(name="Owned below foreign", parent_id=foreign.id, owner_user_id=self.learner_id)
        db.session.add(grandchild)
        db.session.flush()
        notes = Note.query.filter_by(user_id=self.learner_id).order_by(Note.id).all()
        notes[0].deck_id = foreign.id
        notes[1].deck_id = grandchild.id
        notes[2].deck_id = unrelated.id
        expected = {str(note.id) for note in notes[3:]}
        grandchild_id, unrelated_id, allowed_child_id = grandchild.id, unrelated.id, child.id
        db.session.commit()
        db.session.remove()
        with patch.object(browse_card_service.vocabulary_ctrl, "collect_accessible_browse_decks",
                side_effect=AssertionError("A selected admin deck must not scan the collection")):
            page = browse_note_service.list_notes(user_id=self.learner_id, admin_mode=True,
                timezone_name="UTC", query_args={"deck_id": root_id})
            scoped = self._context([root_id], admin_mode=True)
            direct = browse_note_service.list_notes(user_id=self.learner_id, admin_mode=True,
                timezone_name="UTC", query_args={"deck_id": grandchild_id})
        self.assertEqual({row["note_id"] for row in page["items"]}, expected)
        self.assertEqual(set(scoped.deck_by_id), {root_id, allowed_child_id})
        self.assertNotIn(unrelated_id, scoped.deck_by_id)
        self.assertEqual(direct["total"], 1, "An owned root stays directly accessible below a foreign parent")

    def test_admin_batch_requires_every_root_to_be_accessible(self):
        own_id = fixtures.seed_owned_deck(self.learner_id, count=2)
        stranger = fixtures.seed_learner(username="batch-stranger")
        foreign = Deck(name="Foreign", owner_user_id=stranger)
        deleted = Deck(name="Deleted", owner_user_id=self.learner_id, deleted_at=fixtures.NOW)
        db.session.add_all([foreign, deleted])
        db.session.commit()
        for inaccessible in (foreign.id, deleted.id, 999999):
            with self.subTest(root=inaccessible), self.assertRaises(browse_card_service.BrowseApiError) as caught:
                self._context([own_id, inaccessible], admin_mode=True)
            self.assertEqual(caught.exception.status, 404)

    def test_batch_owned_roots_walk_union_once_and_ignore_unrelated_decks(self):
        own_id = fixtures.seed_owned_deck(self.learner_id, count=4)
        child = Deck.query.filter_by(parent_id=own_id).one()
        extra = Deck(name="Other requested root", owner_user_id=self.learner_id)
        unrelated = Deck(name="Not requested", owner_user_id=self.learner_id)
        db.session.add_all([extra, unrelated])
        db.session.commit()
        expected = {own_id, child.id, extra.id}
        with patch.object(browse_card_service.vocabulary_ctrl, "collect_accessible_browse_decks",
                side_effect=AssertionError("All-owned batches must avoid whole-collection scope")):
            context = self._context([own_id, child.id, extra.id])
        self.assertEqual(set(context.deck_by_id), expected)
        self.assertEqual(context.query.count(), 4)

    def test_batch_clone_child_is_restricted_and_overlapping_roots_do_not_repeat_resolution(self):
        ids = fixtures.seed_clone_install(self.learner_id, count=6, release=True)
        unrelated = fixtures.seed_clone_install(self.learner_id, count=2, release=True, prefix="60000000")
        with patch.object(flashcards_share, "resolve_clone_scope_for_local_deck",
                wraps=flashcards_share.resolve_clone_scope_for_local_deck) as resolver:
            context = self._context([ids["local_child_id"]])
        self.assertEqual(resolver.call_count, 1)
        self.assertEqual(set(context.deck_by_id), {ids["local_child_id"]})
        self.assertEqual(context.query.count(), 3)
        self.assertEqual(len(context.clone_scopes), 1)
        scope = context.clone_scopes[0]
        self.assertEqual(scope.source_deck_ids, [ids["source_child_id"]])
        self.assertEqual(scope.source_to_local_deck_id, {ids["source_child_id"]: ids["local_child_id"]})
        self.assertNotIn(unrelated["local_root_id"], context.deck_by_id)
        with patch.object(flashcards_share, "resolve_clone_scope_for_local_deck",
                wraps=flashcards_share.resolve_clone_scope_for_local_deck) as resolver:
            overlap = self._context([ids["local_root_id"], ids["local_child_id"]])
        self.assertEqual(resolver.call_count, 1)
        self.assertEqual(overlap.query.count(), 6)
        counts = browse_note_repository.deck_counts(overlap, user_id=self.learner_id,
            admin_mode=False, today_day_index=1, day_cutoff_utc=fixtures.NOW)
        self.assertEqual(sum(row["total"] for row in counts.values()), 6)

    def test_mixed_learner_batch_preserves_ancestor_visibility_and_clips_context(self):
        own_id = fixtures.seed_owned_deck(self.learner_id, count=4)
        stranger = fixtures.seed_learner(username="mixed-batch-stranger")
        foreign = Deck(name="Foreign ancestor", parent_id=own_id, owner_user_id=stranger)
        unrelated = Deck(name="Unrelated learner", owner_user_id=self.learner_id)
        hidden = Deck(name="Hidden foreign", owner_user_id=stranger)
        db.session.add_all([foreign, unrelated, hidden])
        db.session.flush()
        descendant = Deck(name="Owned descendant", parent_id=foreign.id, owner_user_id=self.learner_id)
        db.session.add(descendant)
        db.session.flush()
        note = Note.query.filter_by(user_id=self.learner_id).first()
        note.deck_id = descendant.id
        foreign_id, descendant_id, hidden_id = foreign.id, descendant.id, hidden.id
        db.session.commit()
        context = self._context([foreign_id])
        self.assertEqual(set(context.deck_by_id), {foreign_id, descendant_id})
        self.assertEqual(context.query.count(), 1)
        with self.assertRaises(browse_card_service.BrowseApiError) as caught:
            self._context([foreign_id, hidden_id])
        self.assertEqual(caught.exception.status, 404)

    def test_nested_install_batch_counts_match_full_sidebar_for_overlapping_roots(self):
        from models.deck_install import DeckInstall

        outer = fixtures.seed_clone_install(self.learner_id, count=6, release=True)
        inner = fixtures.seed_clone_install(self.learner_id, count=4, release=True, prefix="70000000")
        db.session.get(Deck, inner["local_root_id"]).parent_id = outer["local_child_id"]
        # The existing resolver uses earliest-install precedence. Make the
        # inner install older so both branches are present in the full API;
        # an outer scope's covered-node optimization must not hide it.
        db.session.get(DeckInstall, inner["install_id"]).installed_at = fixtures.NOW - timedelta(seconds=1)
        db.session.get(DeckInstall, outer["install_id"]).installed_at = fixtures.NOW
        db.session.commit()
        with self.app.test_request_context("/api/browse/decks?view=notes"):
            full = browse_card_service._build_browse_query(user_id=self.learner_id,
                admin_mode=False, timezone_name="UTC", query_args={}, notes_only=True, scope_only=True)
            full_counts = browse_note_repository.deck_counts(full, user_id=self.learner_id,
                admin_mode=False, today_day_index=1, day_cutoff_utc=fixtures.NOW)
        with self.app.test_request_context("/api/browse/decks/summaries"), patch.object(
                flashcards_share, "resolve_clone_scope_for_local_deck",
                wraps=flashcards_share.resolve_clone_scope_for_local_deck) as resolver:
            scoped = self._context([outer["local_child_id"], inner["local_root_id"]])
            counts = browse_note_repository.deck_counts(scoped, user_id=self.learner_id,
                admin_mode=False, today_day_index=1, day_cutoff_utc=fixtures.NOW)
        self.assertEqual(resolver.call_count, 2, "Each relevant install is resolved once")
        self.assertEqual(counts, {key: value for key, value in full_counts.items() if key in scoped.deck_by_id})
        self.assertEqual(sum(row["total"] for row in counts.values()), 7)
        self.assertEqual(len(scoped.clone_scopes), 2)

    def test_missing_map_legacy_child_batch_matches_full_sidebar(self):
        from models.deck_clone_deck_map import DeckCloneDeckMap

        ids = fixtures.seed_clone_install(self.learner_id, count=4, release=False)
        DeckCloneDeckMap.query.filter_by(deck_install_id=ids["install_id"]).delete()
        db.session.commit()
        with self.app.test_request_context("/api/browse/decks?view=notes"):
            full = browse_card_service._build_browse_query(user_id=self.learner_id,
                admin_mode=False, timezone_name="UTC", query_args={}, notes_only=True, scope_only=True)
            full_counts = browse_note_repository.deck_counts(full, user_id=self.learner_id,
                admin_mode=False, today_day_index=1, day_cutoff_utc=fixtures.NOW)
        with self.app.test_request_context("/api/browse/decks/summaries"), patch.object(
                flashcards_share, "resolve_clone_scope_for_local_deck",
                wraps=flashcards_share.resolve_clone_scope_for_local_deck) as resolver:
            scoped = self._context([ids["local_child_id"]])
            counts = browse_note_repository.deck_counts(scoped, user_id=self.learner_id,
                admin_mode=False, today_day_index=1, day_cutoff_utc=fixtures.NOW)
        self.assertEqual(resolver.call_count, 1, "Legacy unmapped roots are checked before clipping")
        self.assertEqual(set(scoped.deck_by_id), {ids["local_child_id"]})
        self.assertEqual(counts, {key: value for key, value in full_counts.items() if key in scoped.deck_by_id})

    def test_batch_rejects_invalid_roots_and_more_than_50(self):
        for roots in ([], [True], [0], [-1], ["bad"], [1.5], list(range(1, 52))):
            with self.subTest(roots=roots), self.assertRaises(browse_card_service.BrowseApiError) as caught:
                self._context(roots)
            self.assertEqual(caught.exception.status, 400)

    def test_release_clone_editor_never_hydrates_live_values_and_preserves_arrays(self):
        ids = fixtures.seed_clone_install(self.learner_id, count=4, release=True)
        note_id = ids["note_ids"][0]
        original = deepcopy(db.session.get(Note, note_id).field_values_by_id)
        db.session.remove()
        loaded = []
        loader = browse_note_repository.load_note_reference

        def keep_loaded(*args, **kwargs):
            note = loader(*args, **kwargs)
            loaded.append(note)
            return note

        with self.app.test_request_context("/api/browse/notes/editor"), fixtures.StatementCounter() as capture, patch.object(
                browse_note_repository, "load_note_reference", side_effect=keep_loaded):
            detail = self._detail(note_id)
        live_reads = [sql for sql in capture.statements if "notes.field_values_by_id" in sql.lower()
            or "notes.field_values_extras" in sql.lower() or "notes.field_values_codec" in sql.lower()]
        self.assertEqual(live_reads, [], "Release-pinned editor must not fetch author working JSON")
        note = loaded[0]
        self.assertTrue({"field_values_by_id", "field_values_codec", "field_values_extras"}.issubset(inspect(note).unloaded))
        self.assertEqual(detail["note"]["field_values"]["Word"], "override-000001")
        self.assertIn("overlay_revision", detail["note"])
        self.assertNotIn("content_revision", detail["note"])
        full = self._detail(note_id, compact=False)
        self.assertEqual(detail["note"], {key: full["note"][key] for key in detail["note"]})
        from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
        from models.field_def import FieldDef
        meaning = FieldDef.query.filter_by(note_type_id=note.note_type_id, name="Meaning").one()
        db.session.add(DeckCloneFieldDefOverride(deck_install_id=ids["install_id"],
            source_field_def_id=meaning.id, properties={"field_type": "array"}))
        db.session.commit()
        edited = browse_note_service.update_note(user_id=self.learner_id, admin_mode=False,
            timezone_name="UTC", note_id=note_id, compact_detail=True,
            payload={"field_values": {"Meaning": [["one", "two"], "three"]},
                "expected_overlay_revision": detail["note"]["overlay_revision"]})
        self.assertEqual(edited["detail"]["note"]["field_values"]["Meaning"], [["one", "two"], "three"])
        self.assertEqual(db.session.get(Note, note_id).field_values_by_id, original)

    def test_owned_admin_and_snapshot_compact_editor_keep_live_content_contracts(self):
        owned = fixtures.seed_owned_deck(self.learner_id, count=2)
        own_note_id = Note.query.filter_by(deck_id=owned).first().id
        ids = fixtures.seed_clone_install(self.learner_id, count=2, release=False)
        note_id = ids["note_ids"][0]
        for identity, admin in ((own_note_id, False), (note_id, False), (note_id, True)):
            db.session.remove()
            with self.subTest(note=identity, admin=admin), self.app.test_request_context("/api/browse/notes/editor"):
                with fixtures.StatementCounter() as capture:
                    compact = self._detail(identity, admin_mode=admin)
                value_reads = [sql for sql in capture.statements if "notes.field_values_by_id" in sql.lower()]
                self.assertEqual(len(value_reads), 1, "Fallback values must hydrate in a single grouped fetch")
                self.assertTrue(all("notes.field_values_extras" in sql.lower()
                    and "notes.field_values_codec" in sql.lower()
                    and "notes.content_revision" in sql.lower() for sql in value_reads))
                full = self._detail(identity, admin_mode=admin, compact=False)
            self.assertEqual(compact["note"], {key: full["note"][key] for key in compact["note"]})
            self.assertEqual(compact["row"], full["row"])
            if admin or identity == own_note_id:
                self.assertIn("content_revision", compact["note"])
                self.assertIn("field_schema_revision", compact["note"])


if __name__ == "__main__":
    unittest.main()
