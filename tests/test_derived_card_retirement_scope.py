"""P11 membership, pinned releases and exact historical wire identity."""

from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sqlalchemy as sa

from app import create_audit_app
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError, StudyAuthorityRoute, lock_study_authority_route,
    read_study_authority_route, lock_study_authority_siblings, lock_study_authority_subject,
)
from app.repositories.flashcards_share_repository import (
    clone_source_card_visibility, clone_source_note_visibility,
)
from app.services.flashcards_share_service import CloneDeckScope, query_clone_scope_cards
from models import db
from models.card import (
    Card, PresentationAlias, CardWireIdentity, card_key, canonical_card_ids,
    cutover_notes, cutover_applications, get_card, load_cards, forget_card_identities,
)
from models.deck import Deck
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_release import DeckRelease
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_template_pin import DeckReleaseTemplatePin
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User

OLD = datetime(2026, 8, 1, 5)
CUTOFF = OLD + timedelta(hours=12)
NEW = datetime(2026, 9, 30, 12)


class DerivedCardRetirementScopeTests(unittest.TestCase):
    def setUp(self):
        self.app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                                     "REDIS_URL": "", "WTF_CSRF_ENABLED": False})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        owner = User(username="qualification-owner", email="qualification-owner@example.test")
        learner = User(username="qualification-learner", email="qualification-learner@example.test")
        db.session.add_all([owner, learner])
        db.session.flush()
        self.owner_id, self.learner_id = owner.id, learner.id
        note_type = NoteType(id="qualification-nt", name="Qualification", user_id=owner.id)
        deck = Deck(name="Source", owner_user_id=owner.id)
        db.session.add_all([note_type, deck])
        db.session.flush()
        self.deck_id = deck.id
        templates = [Template(id=f"qualification-t{i}", owner_user_id=owner.id, name=f"T{i}", front_html="", back_html="") for i in (1, 2)]
        db.session.add_all(templates)
        db.session.flush()
        db.session.add_all([
            StudyApplication(id=f"qualification-a{i}", note_type_id=note_type.id,
                             template_id=f"qualification-t{i}", occurrence_key="test", position=i,
                             status_code="ACTIVE", created_at=NEW, updated_at=NEW)
            for i in (1, 2)
        ])
        db.session.add_all([
            Note(id=f"qualification-n{i}", note_type_id=note_type.id, user_id=owner.id,
                 deck_id=deck.id, field_values={}, tags=[], created_at=OLD, updated_at=OLD)
            for i in (1, 2)
        ])
        db.session.flush()
        # Only the first application survived for both original Notes.
        db.session.connection().execute(sa.insert(PresentationAlias.__table__), [
            dict(id=f"old-wire-{i}", note_id=f"qualification-n{i}", template_id="qualification-t1",
                 application_id="qualification-a1", created_at=(OLD if i == 1 else NEW),
                 updated_at=(OLD if i == 1 else NEW))
            for i in (1, 2)
        ])
        db.session.execute(sa.insert(cutover_notes), [dict(note_id=f"qualification-n{i}") for i in (1, 2)])
        db.session.execute(sa.insert(cutover_applications), [dict(application_id=f"qualification-a{i}") for i in (1, 2)])
        db.session.add(StudyAuthorityEnrollment(learner_user_id=self.learner_id, mode_code="NOTE", epoch=3,
                                               created_at=OLD, updated_at=OLD))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _scope(self, release=None, cutoff=CUTOFF):
        install = SimpleNamespace(id="qualification-install", user_id=self.learner_id,
                                  applied_release=release, applied_release_id=(release.id if release else None))
        return CloneDeckScope(install=install, local_scope_deck_id=self.deck_id + 100,
                              local_deck_ids=[self.deck_id + 100], source_deck_ids=[self.deck_id],
                              source_to_local_deck_id={self.deck_id: self.deck_id + 100},
                              source_owner_user_id=self.owner_id, base_snapshot_at=cutoff)

    def test_old_uuid_lookup_keeps_wire_id_and_internal_pair_separate(self):
        card = get_card(db.session, "old-wire-1")
        pair = card_key("qualification-n1", "qualification-a1")
        self.assertIsInstance(card, CardWireIdentity)
        self.assertEqual(card.id, "old-wire-1")
        self.assertEqual(card.key, pair)
        self.assertEqual(get_card(db.session, pair).id, pair)
        both = load_cards(db.session, ["old-wire-1", pair])
        self.assertEqual(both["old-wire-1"].id, "old-wire-1")
        self.assertEqual(both[pair].id, pair)
        self.assertEqual(canonical_card_ids(db.session, ["old-wire-1"]), {"old-wire-1": pair})
        self.assertFalse(db.session.dirty)

    def test_every_active_application_presents_every_note(self):
        # Only a1 has archived aliases; the archive maps old IDs and hides no pair.
        self.assertEqual({(c.note_id, c.application_id) for c in Card.query.all()},
                         {(f"qualification-n{n}", f"qualification-a{a}") for n in (1, 2) for a in (1, 2)})
        self.assertIsNotNone(get_card(db.session, "qualification-n1.qualification-a2"))

    def test_exact_per_note_card_creation_times_preserve_legacy_clone_cutoff(self):
        visible = query_clone_scope_cards(self._scope()).all()
        self.assertEqual([card.note_id for card in visible], ["qualification-n1"])
        self.assertEqual(visible[0].created_at, OLD)
        self.assertEqual(db.session.get(StudyApplication, "qualification-a1").created_at, NEW)

    def test_archived_uuid_tie_order_survives_canonical_pair_ids(self):
        aliases = PresentationAlias.__table__
        # Original Card UUID ordering reverses the Note/pair-key ordering.
        db.session.connection().execute(sa.update(aliases).where(aliases.c.note_id == "qualification-n1")
                                        .values(id="z-old-card", created_at=OLD))
        db.session.connection().execute(sa.update(aliases).where(aliases.c.note_id == "qualification-n2")
                                        .values(id="a-old-card", created_at=OLD))
        db.session.commit()
        cards = Card.query.filter_by(application_id="qualification-a1").order_by(
            Card.created_at, Card.order_key).all()
        self.assertEqual([card.note_id for card in cards], ["qualification-n2", "qualification-n1"])
        self.assertEqual([card.order_key for card in cards], ["a-old-card", "z-old-card"])
        self.assertTrue(all("." in card.id for card in cards))
        self.assertEqual(get_card(db.session, "z-old-card").id, "z-old-card")
        from app.services.study_authority_read_service import _availability_from_subject, _pristine_availability
        subject = SimpleNamespace(normalized_queue="review", due_at=None, due_day=100,
                                  is_suspended=False, is_buried=False, buried_until_day=None)
        for card in cards:
            pristine = _pristine_availability(card=card, progress=None, now_utc=NEW)
            stateful = _availability_from_subject(subject, card=card)
            self.assertEqual(pristine.card_order_key, card.order_key.encode("utf-8"))
            self.assertEqual(stateful.card_order_key, card.order_key.encode("utf-8"))

    def test_new_note_with_imported_historical_timestamp_is_still_new_content(self):
        db.session.add(Note(id="new-imported-note", note_type_id="qualification-nt", user_id=self.owner_id,
                            deck_id=self.deck_id, field_values={}, tags=[], created_at=OLD))
        db.session.commit()
        self.assertEqual(Card.query.filter_by(note_id="new-imported-note").count(), 2)
        self.assertEqual(PresentationAlias.query.count(), 2)

    def test_new_application_does_not_materialize_alias_rows(self):
        db.session.add(StudyApplication(id="new-app", note_type_id="qualification-nt", template_id="qualification-t1",
                                        occurrence_key="repeat", status_code="ACTIVE"))
        db.session.commit()
        self.assertEqual(Card.query.filter_by(application_id="new-app").count(), 2)
        self.assertEqual(PresentationAlias.query.count(), 2)
        self.assertNotIn("cards", db.metadata.tables)
        self.assertFalse(sa.inspect(db.engine).has_table("cards"))

    def test_release_pinned_retired_application_remains_visible(self):
        db.session.get(StudyApplication, "qualification-a1").status_code = "RETIRED"
        db.session.commit()
        release = SimpleNamespace(id="pinned-release", template_pins_initialized=True)
        pins = {"qualification-t1": {"applications_json": {"qualification-a1": {}}}}
        with patch("app.repositories.template_release_repository.deck_pins", return_value=pins), \
             patch("app.services.flashcards_share_service.release_note_membership_filter", return_value=None):
            visible = query_clone_scope_cards(self._scope(release, cutoff=None)).all()
        self.assertEqual(len(visible), 2)
        self.assertEqual(Card.query.filter_by(application_id="qualification-a1").count(), 0)
        self.assertEqual(get_card(db.session, "old-wire-1").id, "old-wire-1")

    def test_initialized_empty_release_manifest_exposes_no_source_cards(self):
        release = SimpleNamespace(id="empty-release", template_pins_initialized=True)
        with patch("app.repositories.template_release_repository.deck_pins", return_value={}), \
             patch("app.services.flashcards_share_service.release_note_membership_filter", return_value=None):
            self.assertEqual(query_clone_scope_cards(self._scope(release, cutoff=None)).count(), 0)

    def test_installed_local_added_note_uses_active_applications_independently_of_source_pins(self):
        local = Deck(name="Local shell", owner_user_id=self.learner_id)
        db.session.add(local)
        db.session.flush()
        scope = self._scope()
        scope.local_deck_ids = [local.id]
        scope.local_scope_deck_id = local.id
        note = Note(id="local-added-note", note_type_id="qualification-nt", user_id=self.learner_id,
                    deck_id=local.id, field_values={}, tags=[])
        db.session.add(note)
        db.session.flush()
        # The unit fixture records the overlay link without marketplace setup;
        # production FK enforcement is exercised by the complete install tests.
        db.session.connection().execute(sa.insert(DeckCloneAddedNote.__table__).values(
            deck_install_id=scope.install.id, note_id=note.id,
        ))
        db.session.commit()
        visible = query_clone_scope_cards(scope).all()
        self.assertEqual({c.application_id for c in visible if c.note_id == note.id},
                         {"qualification-a1", "qualification-a2"})

    def _setwise_install(self, *, initialize=True, pin=True):
        db.session.connection().execute(sa.insert(DeckRelease.__table__).values(
            id="setwise-release", deck_item_id="setwise-item", sequence_no=2, version_label="2",
            status="published", template_pins_initialized=initialize,
        ))
        db.session.connection().execute(sa.insert(DeckReleaseEntityMembership.__table__), [
            dict(deck_item_id="setwise-item", entity_kind="note", entity_id="qualification-n1",
                 introduced_sequence=1, removed_sequence=None),
            dict(deck_item_id="setwise-item", entity_kind="note", entity_id="qualification-n2",
                 introduced_sequence=1, removed_sequence=2),
        ])
        if pin:
            db.session.connection().execute(sa.insert(DeckReleaseTemplatePin.__table__).values(
                deck_release_id="setwise-release", source_template_id="qualification-t1",
                template_release_id="frozen-template-release",
                applications_json={"qualification-a1": {}},
            ))
        db.session.commit()
        return SimpleNamespace(applied_release_id="setwise-release", version_mode="release",
                               deck_item_id="setwise-item", base_snapshot_at=CUTOFF, installed_at=CUTOFF)

    def test_setwise_visibility_uses_pinned_retired_app_and_release_note_sequence(self):
        db.session.get(StudyApplication, "qualification-a1").status_code = "RETIRED"
        db.session.commit()
        install = self._setwise_install()
        rows = db.session.execute(sa.select(Card).join(Note, Card.note_id == Note.id).where(
            clone_source_card_visibility(install),
        ).execution_options(include_retired_cards=True)).scalars().all()
        self.assertEqual([c.note_id for c in rows], ["qualification-n1"])

    def test_setwise_initialized_empty_pins_are_empty(self):
        install = self._setwise_install(pin=False)
        rows = db.session.execute(sa.select(Card).join(Note, Card.note_id == Note.id).where(
            clone_source_card_visibility(install),
        ).execution_options(include_retired_cards=True)).scalars().all()
        self.assertEqual(rows, [])

    def test_setwise_legacy_timestamp_uses_exact_archived_card_cutoff(self):
        install = SimpleNamespace(applied_release_id=None, version_mode="legacy_snapshot",
                                  deck_item_id="not-a-release", base_snapshot_at=CUTOFF, installed_at=CUTOFF)
        rows = db.session.execute(sa.select(Card).join(Note, Card.note_id == Note.id).where(
            clone_source_card_visibility(install),
        ).execution_options(include_retired_cards=True)).scalars().all()
        self.assertEqual([c.note_id for c in rows], ["qualification-n1"])

    def test_note_grain_visibility_is_exactly_the_notes_of_visible_cards(self):
        release = self._setwise_install()
        legacy = SimpleNamespace(applied_release_id=None, version_mode="legacy_snapshot",
                                 deck_item_id="not-a-release", base_snapshot_at=CUTOFF, installed_at=CUTOFF)
        unbounded = SimpleNamespace(applied_release_id=None, version_mode="legacy_snapshot",
                                    deck_item_id="not-a-release", base_snapshot_at=None, installed_at=None)
        seen = {}
        for pins in ("pinned", "unpinned"):
            db.session.connection().execute(sa.update(DeckRelease.__table__).values(
                template_pins_initialized=pins == "pinned"))
            for status in ("ACTIVE", "RETIRED"):
                db.session.get(StudyApplication, "qualification-a1").status_code = status
                db.session.commit()
                for name, install in (("release", release), ("legacy", legacy), ("unbounded", unbounded)):
                    by_card = db.session.execute(sa.select(Card.note_id).join(Note, Card.note_id == Note.id).where(
                        clone_source_card_visibility(install),
                    ).execution_options(include_retired_cards=True)).scalars().all()
                    by_note = db.session.execute(sa.select(Note.id).where(
                        clone_source_note_visibility(install),
                    )).scalars().all()
                    with self.subTest(pins=pins, a1=status, install=name):
                        self.assertEqual(sorted(by_note), sorted(set(by_card)))
                    seen[pins, status, name] = sorted(by_note)
        # Pins, live ACTIVE, release sequence and the alias timestamp each decide.
        self.assertEqual(seen["pinned", "RETIRED", "release"], ["qualification-n1"])
        self.assertEqual(seen["unpinned", "RETIRED", "release"], ["qualification-n1"])
        self.assertEqual(seen["unpinned", "ACTIVE", "legacy"], ["qualification-n1"])
        self.assertEqual(seen["unpinned", "RETIRED", "legacy"], [])
        self.assertEqual(seen["unpinned", "RETIRED", "unbounded"], ["qualification-n1", "qualification-n2"])

    def test_alias_archive_survives_content_delete_but_does_not_resolve_live_card(self):
        forget_card_identities(db.session, ["qualification-n1"])
        db.session.query(Note).filter_by(id="qualification-n1").delete(synchronize_session=False)
        db.session.commit()
        self.assertEqual(PresentationAlias.query.count(), 2)
        self.assertIsNone(get_card(db.session, "old-wire-1"))

    def test_runtime_alias_mutation_is_refused(self):
        alias = db.session.get(PresentationAlias, "old-wire-1")
        alias.created_at = NEW
        with self.assertRaisesRegex(TypeError, "immutable"):
            db.session.flush()
        db.session.rollback()
        self.assertEqual(db.session.get(PresentationAlias, "old-wire-1").created_at, OLD)

    def test_old_uuid_is_accepted_by_subject_sibling_fence(self):
        subject = StudyProgressSubject(learner_user_id=self.learner_id,
                                       logical_note_key=b"qualification-n1", live_note_id="qualification-n1",
                                       subject_generation=1, mirror_revision=0, status_code="NO_CURRENT_PROGRESS",
                                       contributor_count=0, created_at=OLD, updated_at=OLD)
        db.session.add(subject)
        db.session.commit()
        route = StudyAuthorityRoute(self.learner_id, "NOTE", 3, True)
        locked = lock_study_authority_subject(db.session, route=route, subject=subject, now_utc=NEW)
        siblings = lock_study_authority_siblings(db.session, route=route, locked=locked, requested_card_id="old-wire-1")
        self.assertIn("old-wire-1", siblings.history_card_ids)

    def test_missing_and_legacy_enrollments_fail_migration_required(self):
        # No accidental enrollment or pristine state creation at a reader/fence.
        for reader in (read_study_authority_route, lock_study_authority_route):
            with self.assertRaises(StudyAuthorityFenceError) as failure:
                reader(db.session, learner_user_id=self.owner_id)
            self.assertEqual(failure.exception.code, "STUDY_AUTHORITY_MIGRATION_REQUIRED")
        enrollment = db.session.get(StudyAuthorityEnrollment, self.learner_id)
        enrollment.mode_code = "LEGACY"
        db.session.commit()
        for reader in (read_study_authority_route, lock_study_authority_route):
            with self.assertRaises(StudyAuthorityFenceError) as failure:
                reader(db.session, learner_user_id=self.learner_id)
            self.assertEqual(failure.exception.code, "STUDY_AUTHORITY_MIGRATION_REQUIRED")
        self.assertEqual(StudyProgressSubject.query.count(), 0)

    def test_native_note_enrollment_works_without_retired_rollout_flag(self):
        for reader in (read_study_authority_route, lock_study_authority_route):
            route = reader(db.session, learner_user_id=self.learner_id)
            self.assertEqual(route.mode_code, "NOTE")
            self.assertEqual(route.storage_profile, "CONSOLIDATED_V1")


if __name__ == "__main__":
    unittest.main()
