"""Template presentation publication preserves deck history and user copies."""

import unittest
from datetime import datetime, timezone
from sqlalchemy import event
from sqlalchemy.orm import Session

from app import create_app
from app.repositories import template_release_repository as repository
from app.services import deck_release_service as releases, deck_install_rebase_service as rebases
from app.services.flashcards_share_service import install_shared_deck_item_for_user
from models import db
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.field_def import FieldDef
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.template import Template
from models.template_subscription import TemplateSubscription
from models.user import User

from tests.study_note_fixtures import attach_template, create_note_user

class TemplateDeckReleaseTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.owner = create_note_user(db.session, username="presentation-author", email="presentation-author@example.com")
        self.learner = create_note_user(db.session, username="presentation-learner", email="presentation-learner@example.com")
        db.session.add_all([self.owner, self.learner])
        db.session.flush()
        self.nt = NoteType(user_id=self.owner.id, name="Source")
        db.session.add(self.nt)
        db.session.flush()
        self.field = FieldDef(note_type_id=self.nt.id, name="Word", field_type="text", position=0)
        self.template = attach_template(db.session, note_type_id=self.nt.id, owner_user_id=self.owner.id, name="Front", front_html="FRONT", back_html="BACK", shared_css="", input_schema=[])
        db.session.add_all([self.field, self.template])
        db.session.commit()
        self.application = StudyApplication.query.filter_by(note_type_id=self.nt.id, template_id=self.template.id).one()
        self.deck = Deck(owner_user_id=self.owner.id, note_type_id=self.nt.id, name="Source deck")
        db.session.add(self.deck)
        db.session.flush()
        self.item = DeckMarketplaceItem(owner_user_id=self.owner.id, source_deck_id=self.deck.id, source_note_type_id=self.nt.id, title="Source", publish_status="published")
        db.session.add(self.item)
        db.session.commit()
        self.initial = self.publish("1")

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def publish(self, label):
        row = releases.publish_release(deck_item_id=self.item.id, user_id=self.owner.id, version_label=label, changelog=None, expected_current_release_id=self.item.current_release_id, expected_working_revision=self.item.working_revision, idempotency_key=f"presentation:{label}").release
        db.session.commit()
        return row

    def test_template_only_manual_release_freezes_content_without_public_code_diff(self):
        old_revision = self.item.working_revision
        self.template.front_html = "DRAFT FRONT"
        db.session.commit()
        self.assertEqual(self.item.working_revision, old_revision + 1)
        preview = releases.preview_release(deck_item_id=self.item.id, user_id=self.owner.id)
        self.assertEqual([row["entity_kind"] for row in preview["items"]], ["template"])
        self.assertNotIn("front_html", preview["items"][0]["after_value"])
        updated = self.publish("2")
        self.assertEqual(updated.change_count, 1)
        old_pin = repository.deck_pins(db.session, self.initial.id)[self.template.id]
        new_pin = repository.deck_pins(db.session, updated.id)[self.template.id]
        self.assertNotEqual(old_pin["template_release_id"], new_pin["template_release_id"])
        old_release = repository.release(db.session, old_pin["template_release_id"])
        self.assertEqual(repository.version(db.session, old_release["version_id"])["front_html"], "FRONT")
        with self.assertRaises(releases.DeckReleaseError) as caught:
            self.publish("3")
        self.assertEqual(caught.exception.error, "NO_RELEASE_CHANGES")
        db.session.rollback()

    def test_attachment_only_manual_release_freezes_bindings(self):
        self.application.input_bindings = {"Word": self.field.id}
        self.application.display_name = "My presentation"
        db.session.commit()
        updated = self.publish("2")
        old_apps = repository.deck_pins(db.session, self.initial.id)[self.template.id]["applications_json"]
        new_apps = repository.deck_pins(db.session, updated.id)[self.template.id]["applications_json"]
        self.assertFalse(old_apps[self.application.id]["input_bindings"])
        self.assertEqual(new_apps[self.application.id]["input_bindings"], {"Word": self.field.id})
        self.assertEqual(updated.change_count, 1)

    def test_template_and_attachment_auto_publish_without_recursive_flush(self):
        self.item.auto_publish_enabled = True
        db.session.commit()
        self.template.back_html = "NEW BACK"
        db.session.commit()
        first = self.item.current_release_id
        self.assertNotEqual(first, self.initial.id)
        self.assertEqual(db.session.get(DeckRelease, first).publish_mode, "automatic")
        self.application.display_name = "A new label"
        db.session.commit()
        self.assertNotEqual(self.item.current_release_id, first)
        self.assertIsNone(self.item.last_auto_publish_error)

    def test_template_rename_and_same_content_do_not_dirty_or_publish(self):
        self.item.auto_publish_enabled = True
        db.session.commit()
        revision = self.item.working_revision
        self.template.name = "A renamed template"
        self.template.front_html = "FRONT"
        db.session.commit()
        self.assertEqual(self.item.working_revision, revision)
        self.assertEqual(self.item.current_release_id, self.initial.id)
        self.assertEqual(releases.preview_release(deck_item_id=self.item.id, user_id=self.owner.id)["items"], [])

    def test_independent_session_auto_publish_uses_and_restores_writer_transaction(self):
        self.item.auto_publish_enabled = True
        db.session.commit()
        scoped = db.session()
        template_id, item_id, initial_id = self.template.id, self.item.id, self.initial.id
        db.session.rollback()
        with Session(db.engine) as writer:
            writer.get(Template, template_id).front_html = "EXTERNAL SESSION"
            writer.commit()
            self.assertIs(db.session(), scoped)
        db.session.expire_all()
        item = db.session.get(DeckMarketplaceItem, item_id)
        self.assertNotEqual(item.current_release_id, initial_id)
        self.assertEqual(item.current_release.source_working_revision, item.working_revision)
        self.assertIsNone(item.last_auto_publish_error)
        pin = repository.deck_pins(db.session, item.current_release_id)[template_id]
        snapshot = repository.release(db.session, pin["template_release_id"])
        self.assertEqual(repository.version(db.session, snapshot["version_id"])["front_html"], "EXTERNAL SESSION")

    def test_independent_session_publication_rolls_back_with_source_edit(self):
        from models.template_version import TemplateVersion
        from models.template_release import TemplateRelease
        self.item.auto_publish_enabled = True
        db.session.commit()
        scoped = db.session()
        template_id, item_id, initial_id = self.template.id, self.item.id, self.initial.id
        revision = self.item.working_revision
        version_count = TemplateVersion.query.count()
        template_release_count = TemplateRelease.query.count()
        deck_release_count = DeckRelease.query.count()
        db.session.rollback()
        with Session(db.engine) as writer:
            writer.get(Template, template_id).front_html = "DISCARDED SESSION"
            def abort_commit(session):
                self.assertNotEqual(session.get(DeckMarketplaceItem, item_id).current_release_id, initial_id)
                raise RuntimeError("Abort outer transaction after publication")
            event.listen(writer, "before_commit", abort_commit)
            with self.assertRaisesRegex(RuntimeError, "Abort outer transaction"):
                writer.commit()
            writer.rollback()
            self.assertIs(db.session(), scoped)
        db.session.expire_all()
        item = db.session.get(DeckMarketplaceItem, item_id)
        self.assertEqual(item.current_release_id, initial_id)
        self.assertEqual(item.working_revision, revision)
        self.assertEqual(db.session.get(Template, template_id).front_html, "FRONT")
        self.assertEqual(TemplateVersion.query.count(), version_count)
        self.assertEqual(TemplateRelease.query.count(), template_release_count)
        self.assertEqual(DeckRelease.query.count(), deck_release_count)

    def test_archived_definition_keeps_existing_use_and_can_publish_with_deck(self):
        from app.services import template_library_service as library
        self.template.archived_at = datetime.now(timezone.utc).replace(tzinfo=None)
        self.template.back_html = "ATTACHED ARCHIVED CONTENT"
        db.session.commit()
        updated = self.publish("2")
        self.assertEqual(set(repository.deck_pins(db.session, updated.id)), {self.template.id})
        self.assertEqual(self.application.status_code, "ACTIVE")
        install_shared_deck_item_for_user(self.item, user_id=self.learner.id)
        db.session.commit()
        received = repository.subscription(db.session, user_id=self.learner.id, source_template_id=self.template.id)
        self.assertEqual(repository.template(db.session, received["local_template_id"])["back_html"], "ATTACHED ARCHIVED CONTENT")
        other = NoteType(user_id=self.owner.id, name="Other owned notes")
        db.session.add(other)
        db.session.commit()
        with self.assertRaises(library.TemplateLibraryError) as caught:
            library.attach_template(user_id=self.owner.id, note_type_id=other.id, payload={"template_id": self.template.id, "input_bindings": {}})
        self.assertEqual(caught.exception.code, "TEMPLATE_ARCHIVED")

    def test_retired_attachment_metadata_and_savepoint_rollback_preserve_revision(self):
        self.application.status_code = "RETIRED"
        db.session.commit()
        retired = self.publish("2")
        revision = self.item.working_revision
        self.application.display_name = "Unused label"
        db.session.commit()
        self.assertEqual(self.item.working_revision, revision)
        with self.assertRaises(RuntimeError):
            with db.session.begin_nested():
                self.application.status_code = "ACTIVE"
                db.session.flush()
                raise RuntimeError("Discard attachment change")
        db.session.commit()
        self.assertEqual(self.item.working_revision, revision)
        self.assertEqual(self.item.current_release_id, retired.id)

    def test_legacy_release_without_pins_keeps_explicit_fallback_after_new_publish(self):
        # Simulate historical rows, retaining their original initialized flag.
        legacy = DeckRelease(deck_item_id=self.item.id, sequence_no=2, version_label="legacy", status="published", source_working_revision=self.item.working_revision)
        db.session.add(legacy)
        db.session.flush()
        self.item.current_release = legacy
        self.item.current_release_id = legacy.id
        db.session.commit()
        updated = self.publish("next")
        self.assertFalse(db.session.get(DeckRelease, legacy.id).template_pins_initialized)
        self.assertEqual(repository.deck_pins(db.session, legacy.id), {})
        self.assertTrue(updated.template_pins_initialized)
        self.assertEqual(set(repository.deck_pins(db.session, updated.id)), {self.template.id})

    def test_rebase_receives_new_template_and_preserves_existing_personal_copy(self):
        install_shared_deck_item_for_user(self.item, user_id=self.learner.id)
        db.session.commit()
        install = DeckInstall.query.filter_by(deck_item_id=self.item.id, user_id=self.learner.id).one()
        existing = repository.subscription(db.session, user_id=self.learner.id, source_template_id=self.template.id)
        local = db.session.get(Template, existing["local_template_id"])
        local.front_html = "PERSONAL"
        db.session.commit()
        another = Template(owner_user_id=self.owner.id, name="Standalone", front_html="SECOND", back_html="", shared_css="", input_schema=[])
        db.session.add(another)
        db.session.flush()
        db.session.add(StudyApplication(note_type_id=self.nt.id, template_id=another.id, occurrence_key="new", input_bindings={}, status_code="ACTIVE"))
        db.session.commit()
        updated = self.publish("2")
        rebase = rebases.prepare_update(install_id=install.id, release_id=updated.id, user_id=self.learner.id)
        self.assertEqual(rebase.status, "ready")
        rebases.apply_prepared_update(rebase_id=rebase.id, user_id=self.learner.id)
        db.session.commit()
        self.assertEqual(TemplateSubscription.query.filter_by(user_id=self.learner.id).count(), 2)
        self.assertEqual(repository.template(db.session, existing["local_template_id"])["front_html"], "PERSONAL")
        received = repository.subscription(db.session, user_id=self.learner.id, source_template_id=another.id)
        self.assertEqual(repository.template(db.session, received["local_template_id"])["front_html"], "SECOND")
        self.assertFalse(received["auto_update_enabled"])


if __name__ == "__main__":
    unittest.main()
