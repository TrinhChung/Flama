"""Publication, user-scoped receipt, immutable pins and three-way parity."""

import unittest
from unittest.mock import patch

from app import create_app
from app.repositories import template_release_repository as repository
from app.services import template_release_service as service
from models import db
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_template_pin import DeckReleaseTemplatePin
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.template import Template
from models.template_publication import TemplatePublication
from models.template_release import TemplateRelease
from models.template_subscription import TemplateSubscription
from models.template_version import TemplateVersion
from models.user import User
from models.field_def import FieldDef
from models.study_application import StudyApplication
from tests.study_note_fixtures import attach_template, create_note_user


class TemplateReleaseServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False})
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        owner = create_note_user(db.session, username="template-publisher", email="template-publisher@example.com")
        learner = create_note_user(db.session, username="template-receiver", email="template-receiver@example.com")
        stranger = create_note_user(db.session, username="template-stranger", email="template-stranger@example.com")
        db.session.add_all([owner, learner, stranger])
        db.session.flush()
        self.owner_id, self.learner_id, self.stranger_id = owner.id, learner.id, stranger.id
        nt = NoteType(user_id=owner.id, name="Source")
        db.session.add(nt)
        db.session.flush()
        source = attach_template(db.session, note_type_id=nt.id, owner_user_id=owner.id, name="Reusable", front_html="FRONT", back_html="BACK", shared_css=".card{}", input_schema=[])
        db.session.add(source)
        db.session.flush()
        self.source_id, self.nt_id = source.id, nt.id
        db.session.add(NoteTypeInstall(user_id=learner.id, source_note_type_id=nt.id))
        db.session.commit()
        self.first = self.publish("1.0.0")

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def publish(self, label):
        source = repository.template(db.session, self.source_id)
        publication = repository.publication(db.session, self.source_id) or {}
        return service.publish_release(user_id=self.owner_id, template_id=self.source_id, payload={
            "version_label": label, "expected_current_release_id": publication.get("current_release_id"),
            "expected_current_version_id": source["current_version_id"],
        }, idempotency_key=f"publish:{label}")["release"]

    def receive(self):
        subscription = service.ensure_subscription(db.session, user_id=self.learner_id, source_template_id=self.source_id, release_id=self.first["id"])
        db.session.commit()
        return subscription["local_template_id"]

    def edit(self, template_id, **values):
        row = db.session.get(Template, template_id)
        for key, value in values.items():
            setattr(row, key, value)
        db.session.commit()
        return repository.template(db.session, template_id)

    def test_manual_publication_is_opt_in_and_snapshot_does_not_follow_edits(self):
        status = service.get_publication(user_id=self.owner_id, template_id=self.source_id)
        self.assertFalse(status["auto_publish_enabled"])
        self.edit(self.source_id, front_html="UNPUBLISHED")
        self.assertEqual(repository.version(db.session, self.first["version_id"])["front_html"], "FRONT")
        self.assertEqual(service.get_publication(user_id=self.owner_id, template_id=self.source_id)["current_release"]["id"], self.first["id"])
        self.assertTrue(service.get_publication(user_id=self.owner_id, template_id=self.source_id)["has_unpublished_changes"])

    def test_idempotent_publish_replay_and_mismatched_key(self):
        payload = {"version_label": "1.0.0", "expected_current_release_id": None, "expected_current_version_id": self.first["version_id"]}
        result = service.publish_release(user_id=self.owner_id, template_id=self.source_id, payload=payload, idempotency_key="publish:1.0.0")
        self.assertTrue(result["replayed"])
        self.assertEqual(TemplateRelease.query.count(), 1)
        with self.assertRaises(service.TemplateReleaseError) as caught:
            service.publish_release(user_id=self.owner_id, template_id=self.source_id, payload={**payload, "version_label": "Other"}, idempotency_key="publish:1.0.0")
        self.assertEqual(caught.exception.code, "IDEMPOTENCY_KEY_REUSED")

    def test_publication_fences_stale_version_and_head(self):
        current = self.edit(self.source_id, front_html="LATEST")
        base = {"version_label": "2.0.0", "expected_current_release_id": self.first["id"], "expected_current_version_id": self.first["version_id"]}
        for payload, code in ((base, "WORKING_REVISION_STALE"), ({**base, "expected_current_release_id": None, "expected_current_version_id": current["current_version_id"]}, "RELEASE_HEAD_STALE")):
            with self.assertRaises(service.TemplateReleaseError) as caught:
                service.publish_release(user_id=self.owner_id, template_id=self.source_id, payload=payload, idempotency_key=code)
            self.assertEqual(caught.exception.code, code)
        self.assertEqual(TemplateRelease.query.count(), 1)

    def test_receipt_requires_install_and_keeps_one_copy_with_no_downgrade(self):
        with self.assertRaises(service.TemplateReleaseError) as caught:
            service.ensure_subscription(db.session, user_id=self.stranger_id, source_template_id=self.source_id)
        self.assertEqual(caught.exception.code, "TEMPLATE_ACCESS_DENIED")
        db.session.rollback()
        local_id = self.receive()
        self.edit(local_id, front_html="PERSONAL")
        again = service.ensure_subscription(db.session, user_id=self.learner_id, source_template_id=self.source_id, release_id=self.first["id"])
        self.assertEqual(again["local_template_id"], local_id)
        self.assertEqual(TemplateSubscription.query.count(), 1)
        self.assertEqual(repository.template(db.session, local_id)["front_html"], "PERSONAL")
        self.assertFalse(again["auto_update_enabled"])
        self.assertEqual(repository.template(db.session, self.source_id)["front_html"], "FRONT")

    def test_subscription_stage_rolls_back_all_copy_and_history_rows(self):
        template_count, version_count = Template.query.count(), TemplateVersion.query.count()
        service.ensure_subscription(db.session, user_id=self.learner_id, source_template_id=self.source_id)
        db.session.rollback()
        self.assertEqual(Template.query.count(), template_count)
        self.assertEqual(TemplateVersion.query.count(), version_count)
        self.assertEqual(TemplateSubscription.query.count(), 0)

    def test_received_copy_and_other_user_cannot_publish_or_enable_publication(self):
        local_id = self.receive()
        for action in (
            lambda: service.update_publication_settings(user_id=self.learner_id, template_id=local_id, payload={"auto_publish_enabled": True}),
            lambda: service.publish_release(user_id=self.learner_id, template_id=local_id, payload={"version_label": "x", "expected_current_release_id": None, "expected_current_version_id": repository.template(db.session, local_id)["current_version_id"]}, idempotency_key="republish"),
        ):
            with self.assertRaises(service.TemplateReleaseError) as caught:
                action()
            self.assertEqual(caught.exception.code, "MARKET_TEMPLATE_REPUBLISH_FORBIDDEN")
        with self.assertRaises(service.TemplateReleaseError) as caught:
            service.get_subscription(user_id=self.stranger_id, template_id=local_id)
        self.assertEqual(caught.exception.status, 404)

    def test_recipient_reads_upstream_immutable_releases_through_owned_copy(self):
        local_id = self.receive()
        self.edit(self.source_id, front_html="UNPUBLISHED SECRET")
        result = service.list_releases(user_id=self.learner_id, template_id=local_id)
        self.assertEqual(result["source_template_id"], self.source_id)
        self.assertEqual(result["items"][0]["id"], self.first["id"])
        detail = service.get_release(user_id=self.learner_id, template_id=local_id, release_id=self.first["id"])
        self.assertEqual(detail["version"]["front_html"], "FRONT")
        for template_id, user_id in ((self.source_id, self.learner_id), (local_id, self.stranger_id)):
            with self.assertRaises(service.TemplateReleaseError) as caught:
                service.list_releases(user_id=user_id, template_id=template_id)
            self.assertEqual(caught.exception.status, 404)

    def test_standalone_note_type_receipt_uses_published_copy_and_one_user_identity(self):
        from app.services.flashcards_share_service import install_shared_note_type
        NoteTypeInstall.query.filter_by(user_id=self.learner_id, source_note_type_id=self.nt_id).delete()
        db.session.commit()
        self.edit(self.source_id, front_html="AUTHOR DRAFT")
        installed, _ = install_shared_note_type(db.session.get(NoteType, self.nt_id), self.learner_id)
        subscription = repository.subscription(db.session, user_id=self.learner_id, source_template_id=self.source_id)
        self.assertEqual(repository.template(db.session, subscription["local_template_id"])["front_html"], "FRONT")
        self.assertEqual(Template.query.filter_by(owner_user_id=self.learner_id, source_template_id=self.source_id).count(), 1)
        active = StudyApplication.query.filter_by(note_type_id=installed.id, status_code="ACTIVE").all()
        self.assertEqual([row.template_id for row in active], [subscription["local_template_id"]])
        self.assertEqual(service.ensure_subscription(db.session, user_id=self.learner_id, source_template_id=self.source_id)["local_template_id"], subscription["local_template_id"])

    def test_received_attachment_cannot_be_redistributed_as_own_note_type(self):
        from app.services import flashcards_share_service as share
        local_id = self.receive()
        note_type = NoteType(user_id=self.learner_id, name="Own NoteType", description="Mine", primary_category="General", preview_text="Preview")
        db.session.add(note_type)
        db.session.flush()
        app = StudyApplication(note_type_id=note_type.id, template_id=local_id, occurrence_key="custom", input_bindings={})
        db.session.add(app)
        db.session.commit()
        self.assertEqual(share.get_note_type_publish_eligibility(note_type=note_type, user_id=self.learner_id)["block_code"], "marketplace_template")
        self.assertIn("cannot be redistributed", share.validate_note_type_publish_requirements(note_type))
        item = DeckMarketplaceItem(owner_user_id=self.learner_id, source_note_type_id=note_type.id, title="Own deck")
        self.assertIn("cannot be redistributed", share.validate_deck_source_note_type_provenance(deck_item=item, source_note_type=note_type))
        app.status_code = "RETIRED"
        db.session.commit()
        self.assertTrue(share.get_note_type_publish_eligibility(note_type=note_type, user_id=self.learner_id)["is_selectable"])

    def test_independent_and_received_definitions_list_and_preview_active_bindings(self):
        from app.services import marketplace_note_type_service, marketplace_query_service
        from app.services.flashcards_share_service import install_shared_note_type
        source = db.session.get(Template, self.source_id)
        note_type = db.session.get(NoteType, self.nt_id)
        note_type.publish_status = "published"
        field = FieldDef(note_type_id=self.nt_id, name="Word", field_type="text", position=0)
        db.session.add(field)
        db.session.flush()
        source.note_type_id = None
        source.front_html = "{{Prompt}}"
        source.input_schema = [{"key": "Prompt", "label": "Prompt", "type": "text", "required": False}]
        app = StudyApplication.query.filter_by(note_type_id=self.nt_id, template_id=self.source_id).one()
        app.input_bindings = {"Prompt": field.id}
        db.session.commit()
        self.publish("2.0.0")
        source.front_html = "AUTHOR DRAFT"
        db.session.commit()
        owned = marketplace_query_service.serialize_note_type(note_type)
        self.assertEqual(owned["templates"][0]["id"], self.source_id)
        self.assertEqual(owned["templates"][0]["note_type_id"], self.nt_id)
        self.assertEqual(owned["templates"][0]["front_html"], "AUTHOR DRAFT")
        shared = marketplace_query_service.serialize_note_type_marketplace_card(note_type)
        self.assertEqual(shared["templates"][0]["front_html"], "{{Prompt}}")
        preview = marketplace_note_type_service.preview_shared_note_type_template(user_id=self.learner_id, note_type_id=self.nt_id, template_id=self.source_id)
        self.assertEqual(preview["front_html"], "<style>.card{}</style>Word")
        NoteTypeInstall.query.filter_by(user_id=self.learner_id, source_note_type_id=self.nt_id).delete()
        db.session.commit()
        installed, _ = install_shared_note_type(note_type, self.learner_id)
        received = marketplace_query_service.serialize_note_type(installed)
        self.assertEqual(len(received["templates"]), 1)
        self.assertEqual(received["templates"][0]["front_html"], "{{Prompt}}")
        local_field_id = received["templates"][0]["input_bindings"]["Prompt"]
        self.assertEqual(db.session.get(FieldDef, local_field_id).note_type_id, installed.id)
        app.status_code = "RETIRED"
        db.session.commit()
        self.assertEqual(marketplace_query_service.serialize_note_type_marketplace_card(note_type)["templates"], [])
        with self.assertRaises(marketplace_note_type_service.MarketplaceNoteTypeError) as caught:
            marketplace_note_type_service.preview_shared_note_type_template(user_id=self.learner_id, note_type_id=self.nt_id, template_id=self.source_id)
        self.assertEqual(caught.exception.status, 404)

    def test_three_way_update_preserves_independent_local_edits(self):
        local_id = self.receive()
        self.edit(local_id, front_html="MY FRONT")
        self.edit(self.source_id, back_html="NEW BACK")
        target = self.publish("2.0.0")
        pending = service.prepare_update(user_id=self.learner_id, template_id=local_id, payload={"release_id": target["id"]})
        self.assertEqual(pending["status"], "ready")
        result = service.apply_update(user_id=self.learner_id, template_id=local_id, payload={"preparation_id": pending["id"]})
        self.assertEqual(result["template"]["front_html"], "MY FRONT")
        self.assertEqual(result["template"]["back_html"], "NEW BACK")
        self.assertEqual(result["applied_release_id"], target["id"])
        self.assertEqual(repository.template(db.session, self.source_id)["front_html"], "FRONT")
        self.assertEqual(repository.version(db.session, result["current_version_id"])["origin"], "update")

    def test_conflicts_require_valid_resolutions_and_do_not_mutate_upstream(self):
        local_id = self.receive()
        self.edit(local_id, front_html="MY FRONT", shared_css=".mine{}")
        self.edit(self.source_id, front_html="NEW FRONT", shared_css=".upstream{}")
        target = self.publish("2.0.0")
        pending = service.prepare_update(user_id=self.learner_id, template_id=local_id, payload={"release_id": target["id"]})
        self.assertEqual(set(pending["conflicts"]), {"front_html", "shared_css"})
        for resolutions in ({}, {"front_html": {"mode": "bogus"}}, {"back_html": {"mode": "keep_mine"}}):
            with self.assertRaises(service.TemplateReleaseError):
                service.apply_update(user_id=self.learner_id, template_id=local_id, payload={"preparation_id": pending["id"], "resolutions": resolutions})
        result = service.apply_update(user_id=self.learner_id, template_id=local_id, payload={"preparation_id": pending["id"], "resolutions": {
            "front_html": {"mode": "keep_mine"}, "shared_css": {"mode": "manual", "value": ".manual{}"},
        }})
        self.assertEqual(result["template"]["front_html"], "MY FRONT")
        self.assertEqual(result["template"]["shared_css"], ".manual{}")
        self.assertEqual(repository.template(db.session, self.source_id)["shared_css"], ".upstream{}")
        service.reset_to_upstream(user_id=self.learner_id, template_id=local_id)
        self.assertEqual(repository.template(db.session, local_id)["front_html"], "NEW FRONT")

    def test_prepare_cannot_cross_source_and_apply_rejects_new_local_edits(self):
        local_id = self.receive()
        self.edit(self.source_id, front_html="NEW")
        target = self.publish("2.0.0")
        pending = service.prepare_update(user_id=self.learner_id, template_id=local_id, payload={"release_id": target["id"]})
        self.edit(local_id, back_html="EDIT AFTER PREPARE")
        with self.assertRaises(service.TemplateReleaseError) as caught:
            service.apply_update(user_id=self.learner_id, template_id=local_id, payload={"preparation_id": pending["id"]})
        self.assertEqual(caught.exception.code, "TEMPLATE_UPDATE_STALE")
        self.assertEqual(repository.subscription(db.session, user_id=self.learner_id, local_template_id=local_id)["applied_release_id"], self.first["id"])

    def test_auto_update_is_off_until_enabled_and_conflict_keeps_pin(self):
        local_id = self.receive()
        self.edit(self.source_id, back_html="AUTO BACK")
        target = self.publish("2.0.0")
        self.assertEqual(repository.template(db.session, local_id)["back_html"], "BACK")
        service.update_subscription_settings(user_id=self.learner_id, template_id=local_id, payload={"auto_update_enabled": True})
        self.assertEqual(repository.template(db.session, local_id)["back_html"], "AUTO BACK")
        self.edit(local_id, front_html="MINE")
        self.edit(self.source_id, front_html="THEIRS")
        self.publish("3.0.0")
        subscription = repository.subscription(db.session, user_id=self.learner_id, local_template_id=local_id)
        self.assertEqual(subscription["applied_release_id"], target["id"])
        self.assertEqual(subscription["pending_update_json"]["status"], "has_conflict")
        self.assertEqual(repository.template(db.session, local_id)["front_html"], "MINE")

    def test_auto_publish_hook_uses_core_without_flush_and_can_update_subscribers(self):
        local_id = self.receive()
        service.update_subscription_settings(user_id=self.learner_id, template_id=local_id, payload={"auto_update_enabled": True})
        service.update_publication_settings(user_id=self.owner_id, template_id=self.source_id, payload={"auto_publish_enabled": True})
        current = self.edit(self.source_id, back_html="AUTOMATIC")
        # Calling the hook directly also proves the event contract independently
        # of where a caller commits. A second callback is a publication no-op.
        with patch.object(db.session(), "flush", side_effect=AssertionError("recursive flush")):
            service.on_version_appended(db.session, self.source_id, current["current_version_id"], self.owner_id)
        db.session.commit()
        head = service.get_publication(user_id=self.owner_id, template_id=self.source_id)["current_release"]
        self.assertEqual(head["publish_mode"], "automatic")
        self.assertEqual(repository.template(db.session, local_id)["back_html"], "AUTOMATIC")
        self.assertEqual(TemplateRelease.query.count(), 2)

    def test_boolean_settings_are_strict(self):
        local_id = self.receive()
        for value in ("false", 1, None):
            for action in (
                lambda: service.update_publication_settings(user_id=self.owner_id, template_id=self.source_id, payload={"auto_publish_enabled": value}),
                lambda: service.update_subscription_settings(user_id=self.learner_id, template_id=local_id, payload={"auto_update_enabled": value}),
            ):
                with self.assertRaises(service.TemplateReleaseError):
                    action()

    def test_archived_auto_published_template_remains_editable_without_new_publication(self):
        from app.services import template_library_service as library
        service.update_publication_settings(user_id=self.owner_id, template_id=self.source_id, payload={"auto_publish_enabled": True})
        library.archive_template(user_id=self.owner_id, template_id=self.source_id, payload={"archived": True})
        before = repository.template(db.session, self.source_id)
        versions = TemplateVersion.query.count()
        releases = TemplateRelease.query.count()
        result = library.update_template(user_id=self.owner_id, template_id=self.source_id, payload={"back_html": "ARCHIVED ACTIVE EDIT"})
        self.assertEqual(result["back_html"], "ARCHIVED ACTIVE EDIT")
        self.assertNotEqual(result["current_version_id"], before["current_version_id"])
        self.assertEqual(TemplateVersion.query.count(), versions + 1)
        self.assertEqual(TemplateRelease.query.count(), releases)
        self.assertEqual(service.get_publication(user_id=self.owner_id, template_id=self.source_id)["current_release"]["id"], self.first["id"])
        with self.assertRaises(service.TemplateReleaseError) as caught:
            self.publish("archived")
        self.assertEqual(caught.exception.code, "TEMPLATE_ARCHIVED")

    def test_deck_pin_freezes_content_and_bindings_without_live_backfill(self):
        deck = Deck(owner_user_id=self.owner_id, note_type_id=self.nt_id, name="Published deck")
        db.session.add(deck)
        db.session.flush()
        item = DeckMarketplaceItem(owner_user_id=self.owner_id, source_deck_id=deck.id, source_note_type_id=self.nt_id, title="Pinned deck", publish_status="published")
        db.session.add(item)
        db.session.flush()
        release = DeckRelease(deck_item_id=item.id, sequence_no=1, version_label="1", status="published")
        db.session.add(release)
        db.session.flush()
        service.capture_deck_release_template_pins(db.session, release, actor_user_id=self.owner_id)
        db.session.commit()
        pins = repository.deck_pins(db.session, release.id)
        self.assertTrue(db.session.get(DeckRelease, release.id).template_pins_initialized)
        self.assertEqual(set(pins), {self.source_id})
        self.assertTrue(pins[self.source_id]["applications_json"])
        self.edit(self.source_id, front_html="LATER UNPUBLISHED")
        overrides = repository.load_effective_template_overrides(db.session, user_id=self.stranger_id, source_template_ids=[self.source_id], release_pins=pins)
        self.assertEqual(overrides[self.source_id].id, self.source_id)
        self.assertEqual(overrides[self.source_id].front_html, "FRONT")
        self.assertEqual(overrides[self.source_id].application_bindings, pins[self.source_id]["applications_json"])
        self.assertEqual(repository.load_effective_template_overrides(db.session, user_id=self.stranger_id, source_template_ids=[self.source_id]), {})

    def test_paid_deck_receipt_reuses_user_template_for_another_own_note_type(self):
        from app.services import deck_release_service
        from app.services.flashcards_share_service import install_shared_deck_item_for_user
        field = FieldDef(note_type_id=self.nt_id, name="Word", field_type="text", position=0)
        db.session.add(field)
        db.session.flush()
        app = StudyApplication.query.filter_by(note_type_id=self.nt_id, template_id=self.source_id).first()
        app.input_bindings = {"Word": field.id}
        app.is_default = True
        deck = Deck(owner_user_id=self.owner_id, note_type_id=self.nt_id, name="Paid source")
        db.session.add(deck)
        db.session.flush()
        item = DeckMarketplaceItem(owner_user_id=self.owner_id, source_deck_id=deck.id, source_note_type_id=self.nt_id, title="Paid", pricing_mode="paid", price_amount_minor=50000, publish_status="published")
        db.session.add(item)
        db.session.flush()
        release = deck_release_service.publish_release(deck_item_id=item.id, user_id=self.owner_id, version_label="1", changelog=None, expected_current_release_id=None, expected_working_revision=0, idempotency_key="deck-paid").release
        db.session.commit()
        # The source author edits their draft after publishing the sold deck.
        self.edit(self.source_id, front_html="NOT SOLD YET")
        result = install_shared_deck_item_for_user(item, user_id=self.learner_id)
        db.session.commit()
        self.assertTrue(result["created"])
        subscription = repository.subscription(db.session, user_id=self.learner_id, source_template_id=self.source_id)
        local_id = subscription["local_template_id"]
        self.assertEqual(repository.template(db.session, local_id)["front_html"], "FRONT")
        install = DeckInstall.query.filter_by(user_id=self.learner_id, deck_item_id=item.id).first()
        self.assertEqual(install.purchase_amount_minor, 50000)
        received = service.list_install_templates(user_id=self.learner_id, install_id=install.id)
        self.assertEqual(received["items"][0]["template_id"], local_id)
        nt_install = NoteTypeInstall.query.filter_by(user_id=self.learner_id, source_note_type_id=self.nt_id).first()
        active = StudyApplication.query.filter_by(note_type_id=nt_install.installed_note_type_id, status_code="ACTIVE").all()
        self.assertEqual([row.template_id for row in active], [local_id])
        self.assertEqual(len(active[0].input_bindings), 1)
        mapped_field = db.session.get(FieldDef, active[0].input_bindings["Word"])
        self.assertEqual(mapped_field.note_type_id, nt_install.installed_note_type_id)
        # The same user copy can be attached to any owned NoteType, independently
        # of its originating paid deck; it remains forbidden to republish.
        other_nt = NoteType(user_id=self.learner_id, name="My unrelated notes")
        db.session.add(other_nt)
        db.session.flush()
        db.session.add(StudyApplication(note_type_id=other_nt.id, template_id=local_id, occurrence_key="custom", input_bindings={}))
        db.session.commit()
        self.edit(local_id, front_html="MY PAID COPY")
        self.assertFalse(install_shared_deck_item_for_user(item, user_id=self.learner_id)["created"])
        self.assertEqual(TemplateSubscription.query.count(), 1)
        self.assertEqual(repository.template(db.session, local_id)["front_html"], "MY PAID COPY")
        self.assertEqual(repository.deck_pins(db.session, release.id)[self.source_id]["template_release_id"], self.first["id"])

    def test_published_release_cannot_be_edited_through_the_orm(self):
        release = db.session.get(TemplateRelease, self.first["id"])
        release.version_label = "rewritten history"
        with self.assertRaises(service.TemplateReleaseError) as caught:
            db.session.commit()
        self.assertEqual(caught.exception.code, "IMMUTABLE_TEMPLATE_RELEASE")
        db.session.rollback()

    def test_marketplace_uses_active_attachment_binding_and_published_source_snapshot(self):
        from app.services import template_library_service as library, marketplace_query_service as queries, marketplace_note_type_service as marketplace
        nt = db.session.get(NoteType, self.nt_id)
        field = FieldDef(note_type_id=nt.id, name="Word", field_type="text", position=0)
        db.session.add(field)
        db.session.commit()
        independent = library.create_template(user_id=self.owner_id, payload={
            "name": "Independent source", "front_html": "<b>PUBLISHED {{term}}</b>", "back_html": "", "shared_css": "",
            "input_schema": [{"key": "term", "type": "text"}],
        })
        application = library.attach_template(user_id=self.owner_id, note_type_id=nt.id, payload={
            "template_id": independent["id"], "input_bindings": {"term": field.id}, "position": 7, "is_default": True,
        })
        published = service.publish_release(user_id=self.owner_id, template_id=independent["id"], payload={
            "version_label": "1", "expected_current_release_id": None, "expected_current_version_id": independent["current_version_id"],
        }, idempotency_key="independent-preview")["release"]
        library.update_template(user_id=self.owner_id, template_id=independent["id"], payload={"front_html": "SECRET DRAFT"})
        items = queries.serialize_note_type_templates(nt, published=True)
        row = next(row for row in items if row["id"] == independent["id"])
        self.assertEqual(row["front_html"], "<b>PUBLISHED {{term}}</b>")
        self.assertEqual(row["current_version_id"], published["version_id"])
        self.assertEqual(row["position"], 7)
        self.assertTrue(row["is_default"])
        self.assertEqual(row["input_bindings"], {"term": field.id})
        with patch.object(marketplace, "_get_shared_note_type_for_view", return_value=nt):
            preview = marketplace.preview_shared_note_type_template(user_id=self.stranger_id, note_type_id=nt.id, template_id=independent["id"])
            self.assertIn("PUBLISHED", preview["front_html"])
            self.assertNotIn("{{term}}", preview["front_html"])
            self.assertNotIn("SECRET", preview["front_html"])
            library.retire_application(user_id=self.owner_id, note_type_id=nt.id, application_id=application["id"])
            self.assertNotIn(independent["id"], {row["id"] for row in queries.serialize_note_type_templates(nt, published=True)})
            with self.assertRaises(marketplace.MarketplaceNoteTypeError) as caught:
                marketplace.preview_shared_note_type_template(user_id=self.stranger_id, note_type_id=nt.id, template_id=independent["id"])
            self.assertEqual(caught.exception.status, 404)


if __name__ == "__main__":
    unittest.main()
