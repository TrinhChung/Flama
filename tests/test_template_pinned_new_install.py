"""New installs rehydrate immutable pins even after source occurrence retirement."""

import unittest

from app import create_audit_app
from app.repositories import template_library_repository
from app.repositories import template_release_repository
from app.services import flashcards_share_service
from app.services.share import install as modular_install
from app.services.study_authority_enrollment_service import enroll_new_learner_note_authority
from app.services.template_release_service import capture_deck_release_template_pins
from models import db
from models.card import Card
from models.deck import Deck
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.template import Template
from models.user import User


class PinnedNewInstallTests(unittest.TestCase):
    def setUp(self):
        self.app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "REDIS_URL": ""})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.author = User(username="pinned-author", email="pinned-author@example.test")
        self.learner = User(username="pinned-learner", email="pinned-learner@example.test")
        db.session.add_all([self.author, self.learner])
        db.session.flush()
        for user in (self.author, self.learner):
            enroll_new_learner_note_authority(db.session, user=user)
        self.nt = NoteType(name="Pinned", user_id=self.author.id, publish_status="published")
        db.session.add(self.nt)
        db.session.flush()
        self.field = FieldDef(note_type_id=self.nt.id, name="Word", field_type="text", position=0)
        db.session.add(self.field)
        db.session.flush()
        self.template = template_library_repository.create_attached_template(
            db.session, note_type=self.nt, name="Pinned card", front_html="frozen {{term}}", back_html="{{term}}",
            input_schema=[{"key": "term", "label": "Term", "type": "text", "required": True}],
            input_bindings={"term": self.field.id}, position=4, is_default=True, source_ord=8,
        )
        self.deck = Deck(name="Pinned source", owner_user_id=self.author.id, note_type_id=self.nt.id)
        db.session.add(self.deck)
        db.session.flush()
        self.source_note = Note(user_id=self.author.id, note_type_id=self.nt.id, deck_id=self.deck.id,
                                field_values={"Word": "source"}, tags=[])
        self.item = DeckMarketplaceItem(owner_user_id=self.author.id, source_deck_id=self.deck.id,
                                        source_note_type_id=self.nt.id, title="Pinned source",
                                        publish_status="published", pricing_mode="free")
        db.session.add_all([self.source_note, self.item])
        db.session.commit()
        self.source_app = template_library_repository.applications(db.session, self.nt.id)[0]

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _publish(self, *, empty=False):
        release = DeckRelease(deck_item_id=self.item.id, sequence_no=1, version_label="1",
                              status="published", template_pins_initialized=empty)
        db.session.add(release)
        db.session.flush()
        if not empty:
            capture_deck_release_template_pins(db.session, release, actor_user_id=self.author.id)
        self.item.current_release_id = release.id
        db.session.add(DeckReleaseEntityMembership(deck_item_id=self.item.id, entity_kind="note",
                       entity_id=self.source_note.id, source_deck_id=self.deck.id, introduced_sequence=1))
        db.session.commit()
        return release

    def _install(self, entry):
        result = entry(self.item, user_id=self.learner.id)
        self.assertTrue(result["created"])
        db.session.commit()
        install = DeckInstall.query.filter_by(deck_item_id=self.item.id, user_id=self.learner.id).one()
        nt_install = NoteTypeInstall.query.filter_by(source_note_type_id=self.nt.id, user_id=self.learner.id).one()
        return install, db.session.get(NoteType, nt_install.installed_note_type_id)

    def _retired_pin_case(self, entry):
        self._publish()
        frozen_version = self.template.current_version_id
        self.source_app.status_code = "RETIRED"
        self.source_app.position = 99
        self.source_app.is_default = False
        self.source_app.input_bindings = {}
        self.template.front_html = "unpublished draft"
        db.session.commit()
        install, local_nt = self._install(entry)
        local_apps = template_library_repository.applications(db.session, local_nt.id)
        self.assertEqual(len(local_apps), 1)
        app = local_apps[0]
        self.assertEqual((app.status_code, app.position, app.is_default), ("ACTIVE", 4, True))
        local_template = db.session.get(Template, app.template_id)
        self.assertEqual(local_template.front_html, "frozen {{term}}")
        self.assertEqual(local_template.source_version_id, frozen_version)
        local_word = next(field for field in local_nt.field_defs if field.name == "Word")
        self.assertEqual(app.input_bindings, {"term": local_word.id})
        self.assertNotEqual(local_word.id, self.field.id)
        # Source content stays a pointer; local-added content presents the
        # received frozen template through its own active occurrence.
        local_note = Note(user_id=self.learner.id, note_type_id=local_nt.id, deck_id=install.local_deck_id,
                          field_values={"Word": "mine"}, tags=[])
        db.session.add(local_note)
        db.session.flush()
        db.session.add(DeckCloneAddedNote(deck_install_id=install.id, note_id=local_note.id))
        db.session.commit()
        scope = flashcards_share_service.resolve_clone_scope_for_local_deck(
            user_id=self.learner.id, local_deck_id=install.local_deck_id)
        visible = flashcards_share_service.query_clone_scope_cards(scope).all()
        self.assertEqual({card.note_id for card in visible}, {self.source_note.id, local_note.id})
        self.assertEqual(Note.query.filter_by(user_id=self.author.id).count(), 1)
        self.assertEqual(Card.query.filter_by(note_id=local_note.id).count(), 1)
        from app.services.study_composition_service import list_available_compositions_for_query
        from app.services.study_template_preset_service import template_inputs_for_compositions
        compositions = list_available_compositions_for_query(
            flashcards_share_service.query_clone_scope_cards(scope), clone_scope=scope)
        inputs = template_inputs_for_compositions(compositions,
            user_id=self.learner.id, clone_scope=scope)
        source = next(item for item in compositions if item.context_kind == "installed_source")
        self.assertEqual(source.study_application_id, self.source_app.id)
        self.assertEqual(inputs[source.composition_id]["input_bindings"], {"term": self.field.id})

    def _empty_case(self, entry):
        self._publish(empty=True)
        self.assertEqual(self.source_app.status_code, "ACTIVE")
        install, local_nt = self._install(entry)
        self.assertEqual(template_library_repository.applications(db.session, local_nt.id), [])
        scope = flashcards_share_service.resolve_clone_scope_for_local_deck(
            user_id=self.learner.id, local_deck_id=install.local_deck_id)
        self.assertEqual(flashcards_share_service.query_clone_scope_cards(scope).count(), 0)

    def test_flat_install_preserves_retired_pin_for_source_and_local_added_notes(self):
        self._retired_pin_case(flashcards_share_service.install_shared_deck_item_for_user)

    def test_modular_install_preserves_retired_pin_for_source_and_local_added_notes(self):
        self._retired_pin_case(modular_install.install_shared_deck_item_for_user)

    def test_flat_initialized_empty_manifest_copies_no_draft_application(self):
        self._empty_case(flashcards_share_service.install_shared_deck_item_for_user)

    def test_modular_initialized_empty_manifest_copies_no_draft_application(self):
        self._empty_case(modular_install.install_shared_deck_item_for_user)

    def test_unrelated_null_source_note_type_install_grants_no_template_access(self):
        private = Template(owner_user_id=self.author.id, name="Unrelated private definition",
                           front_html="private", back_html="", input_schema=[])
        db.session.add(private)
        # Such a NULL source scope can survive historical source deletion. It
        # must never become a wildcard for independent definitions.
        db.session.add(DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
                                   source_note_type_id=None, source_deck_id=None, local_deck_id=None,
                                   clone_mode="logical_overlay"))
        db.session.commit()
        self.assertFalse(template_release_repository.source_access(
            db.session, user_id=self.learner.id, source_template_id=private.id))

    def test_missing_author_never_infers_ownership_from_a_note_type_usage(self):
        self.assertIsNone(template_release_repository.template_owner(
            db.session, {"owner_user_id": None, "note_type_id": self.nt.id}))


if __name__ == "__main__":
    unittest.main()
