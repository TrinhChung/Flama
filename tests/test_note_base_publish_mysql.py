"""Publication semantics on a generated local MySQL database."""
from unittest.mock import patch

from sqlalchemy import select

from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import create_note_user
from models import db
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.field_def import FieldDef
from models.note_draft import NoteDraft
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release_change import DeckReleaseChange
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from app.services import deck_release_service as releases
from app.services.note_base_context import note_author_view


class NoteBasePublishTests(NoteBaseMySQLTestCase):
    APP_CONFIG = {"NOTE_PUBLISHED_BASE_ENABLED": True}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from app.routes import register_blueprints
        register_blueprints(cls.app)

    def setUp(self):
        super().setUp()
        self.owner = create_note_user(db.session, username="base-author", email="author@example.invalid")
        self.learner = create_note_user(db.session, username="base-learner", email="learner@example.invalid")
        self.nt = NoteType(user_id=self.owner.id, name="Base semantics")
        db.session.add(self.nt)
        db.session.flush()
        self.field = FieldDef(note_type_id=self.nt.id, name="Word", field_type="array", position=0)
        self.deck = Deck(name="Base", owner_user_id=self.owner.id, note_type_id=self.nt.id)
        db.session.add_all([self.field, self.deck])
        db.session.flush()
        self.note = Note(user_id=self.owner.id, note_type_id=self.nt.id, deck_id=self.deck.id,
            field_values={"Word": ["base", ["nested"]]}, tags=["original"])
        self.item = DeckMarketplaceItem(owner_user_id=self.owner.id, source_deck_id=self.deck.id,
            source_note_type_id=self.nt.id, title="Base", publish_status="published")
        db.session.add_all([self.note, self.item])
        db.session.commit()

    def publish(self, label, key=None):
        return releases.publish_release_and_commit(deck_item_id=self.item.id, user_id=self.owner.id,
            version_label=label, changelog="Changes", expected_current_release_id=self.item.current_release_id,
            expected_working_revision=self.item.working_revision, idempotency_key=key or label)

    def test_publish_is_incremental_preserves_identity_and_replays(self):
        note_id = self.note.id
        first = self.publish("v1")
        self.assertIsNotNone(self.note.published_at)
        old_revision = self.note.content_revision
        self.note.field_values = {"Word": ["draft", None, ["nested"]]}
        db.session.commit()
        self.assertEqual(self.note.field_values_by_id[self.field.id], ["base", ["nested"]])
        self.assertEqual(self.note.content_revision, old_revision)
        with note_author_view(self.owner.id):
            self.assertEqual(self.note.field_values["Word"], ["draft", None, ["nested"]])
        self.assertIsNotNone(db.session.get(NoteDraft, self.note.id))
        request = dict(deck_item_id=self.item.id, user_id=self.owner.id, version_label="v2", changelog="Changes",
            expected_current_release_id=first.release.id, expected_working_revision=self.item.working_revision,
            idempotency_key="v2")
        with patch("app.services.deck_install_rebase_service.process_subscriber_auto_updates",
                   side_effect=AssertionError("Publication must not fan out")):
            second = releases.publish_release_and_commit(**request)
        self.assertEqual(self.note.id, note_id)
        self.assertEqual(self.note.field_values_by_id[self.field.id], ["draft", None, ["nested"]])
        self.assertGreater(self.note.content_revision, old_revision)
        self.assertIsNone(db.session.get(NoteDraft, self.note.id))
        self.assertEqual(DeckReleaseChange.query.count(), 0)
        replay = releases.publish_release_and_commit(**request)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.release.id, second.release.id)

    def test_draft_rollback_is_atomic(self):
        self.publish("v1")
        self.note.field_values = {"Word": ["draft"]}
        db.session.commit()
        with patch("app.services.template_release_service.capture_deck_release_template_pins", side_effect=RuntimeError("fail")):
            with self.assertRaises(RuntimeError):
                self.publish("v2")
        self.assertEqual(db.session.get(Note, self.note.id).field_values_by_id[self.field.id], ["base", ["nested"]])
        self.assertIsNotNone(db.session.get(NoteDraft, self.note.id))
        self.assertEqual(self.item.current_release.version_label, "v1")

    def test_delete_unreferenced_note_only_at_publish(self):
        from app.services.flashcard_content_service import delete_note
        self.publish("v1")
        note_id = self.note.id
        delete_note(user_id=self.owner.id, note_id=note_id)
        self.assertIsNotNone(db.session.get(Note, note_id))
        self.assertEqual(db.session.get(NoteDraft, note_id).op, "delete")
        self.publish("v2")
        self.assertIsNone(db.session.get(Note, note_id))

    def test_delete_referenced_note_retains_override(self):
        from app.services.flashcard_content_service import delete_note
        self.publish("v1")
        install = DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
            clone_mode="logical_overlay", source_deck_id=self.deck.id,
            source_note_type_id=self.nt.id, source_owner_user_id=self.owner.id)
        db.session.add(install)
        db.session.flush()
        override = DeckCloneNoteFieldOverride(deck_install_id=install.id, source_note_id=self.note.id,
            field_identity_key=self.field.id, field_name="Word", source_field_def_id=self.field.id,
            operation="set", value=["personal"])
        db.session.add(override)
        db.session.commit()
        note_id, override_id = self.note.id, override.id
        delete_note(user_id=self.owner.id, note_id=note_id)
        self.publish("v2")
        stored = db.session.execute(select(Note).where(Note.id == note_id).execution_options(include_deleted_notes=True)).scalar_one()
        self.assertIsNotNone(stored.deleted_at)
        self.assertEqual(db.session.get(DeckCloneNoteFieldOverride, override_id).value, ["personal"])
        db.session.expire_all()
        self.assertEqual(Note.query.filter(Note.id == note_id).count(), 0)

    def test_schema_does_not_change_until_publish(self):
        self.publish("v1")
        old_snapshot = self.item.published_schema_json
        self.field.name = "Renamed"
        db.session.commit()
        self.assertEqual(self.item.published_schema_json, old_snapshot)
        self.publish("v2")
        self.assertEqual(self.item.published_schema_json[self.field.id]["name"], "Renamed")

    def test_retention_is_dry_run_and_keeps_recent_identity(self):
        from datetime import datetime, timedelta
        from app.services.note_base_retention_service import run_retention
        from app.services.note_base_context import base_maintenance
        self.publish("v1")
        note_id = self.note.id
        with base_maintenance("retention fixture"):
            self.note.deleted_at = datetime.utcnow() - timedelta(days=91)
            db.session.flush()
        db.session.commit()
        preview = run_retention()
        self.assertEqual(preview["notes"], 1)
        self.assertIsNotNone(db.session.execute(select(Note).where(Note.id == note_id)
            .execution_options(include_deleted_notes=True)).scalar_one_or_none())
        report = run_retention(apply=True)
        self.assertEqual(report["notes"], 1)
        self.assertIsNone(db.session.execute(select(Note).where(Note.id == note_id)
            .execution_options(include_deleted_notes=True)).scalar_one_or_none())

    def test_note_type_batch_publishes_schema_for_each_owned_listing(self):
        from app.services.note_base_batch_publish_service import publish_note_type_listings
        self.publish("v1")
        second_deck = Deck(name="Second listing", owner_user_id=self.owner.id, note_type_id=self.nt.id)
        db.session.add(second_deck)
        db.session.flush()
        second_item = DeckMarketplaceItem(owner_user_id=self.owner.id, source_deck_id=second_deck.id,
            source_note_type_id=self.nt.id, title="Second", publish_status="published")
        db.session.add(second_item)
        db.session.commit()
        releases.publish_release_and_commit(deck_item_id=second_item.id, user_id=self.owner.id,
            version_label="v1", changelog=None, expected_current_release_id=None,
            expected_working_revision=second_item.working_revision, idempotency_key="second-v1")
        self.field.name = "Renamed together"
        db.session.commit()
        owner_id, type_id, field_id = self.owner.id, self.nt.id, self.field.id
        request = dict(user_id=owner_id, note_type_id=type_id, version_label="v2", batch_key="schema-v2")
        preview = publish_note_type_listings(**request)
        self.assertEqual([row["status"] for row in preview["items"]], ["preview", "preview"])
        self.assertNotEqual(self.item.published_schema_json[field_id]["name"], "Renamed together")
        applied = publish_note_type_listings(**request, apply=True)
        self.assertTrue(applied["complete"])
        self.assertEqual([row["status"] for row in applied["items"]], ["published", "published"])
        self.assertEqual(self.item.published_schema_json[field_id]["name"], "Renamed together")
        self.assertEqual(second_item.published_schema_json[field_id]["name"], "Renamed together")
        replay = publish_note_type_listings(**request, apply=True)
        self.assertTrue(replay["complete"])
        self.assertEqual([row["status"] for row in replay["items"]], ["replayed", "replayed"])

    def test_retention_preserves_canonical_field_override_then_expires_it(self):
        from datetime import datetime, timedelta
        from app.services.note_base_retention_service import run_retention
        from app.services.note_base_context import base_maintenance
        self.publish("v1")
        install = DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
            clone_mode="logical_overlay", source_deck_id=self.deck.id,
            source_note_type_id=self.nt.id, source_owner_user_id=self.owner.id)
        db.session.add(install)
        db.session.flush()
        row = DeckCloneNoteFieldOverride(deck_install_id=install.id, source_note_id=self.note.id,
            source_field_def_id=None, field_identity_key=self.field.id, field_name="Word",
            operation="set", value=["personal"])
        db.session.add(row)
        db.session.commit()
        now = datetime.utcnow()
        with base_maintenance("retention field fixture"):
            self.field.deleted_at = now - timedelta(days=91)
            db.session.flush()
        db.session.commit()
        self.publish("v2")
        self.assertEqual(run_retention(now=now)["fields"], 0)
        # Retention also expires overrides on a deleted Field while its Note
        # remains alive, including rows with only their canonical UUID.
        future = now + timedelta(days=92)
        preview = run_retention(now=future)
        self.assertEqual(preview["expired_overrides"], 1)
        self.assertEqual(preview["fields"], 1)
        field_id, note_id = self.field.id, self.note.id
        applied = run_retention(apply=True, now=future)
        self.assertEqual(applied["fields"], 1)
        self.assertEqual(DeckCloneNoteFieldOverride.query.count(), 0)
        self.assertIsNone(db.session.execute(select(FieldDef).where(FieldDef.id == field_id)
            .execution_options(include_deleted_fields=True)).scalar_one_or_none())
        self.assertIsNotNone(db.session.get(Note, note_id))

    def test_retention_cursor_advances_past_a_referenced_first_field(self):
        from datetime import datetime, timedelta
        from app.services.note_base_retention_service import run_retention
        self.publish("v1")
        old = datetime.utcnow() - timedelta(days=91)
        first_id, second_id = "00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"
        db.session.add_all([FieldDef(id=first_id, note_type_id=self.nt.id, name="Retained", position=1, deleted_at=old),
            FieldDef(id=second_id, note_type_id=self.nt.id, name="Eligible", position=2, deleted_at=old)])
        install = DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
            clone_mode="logical_overlay", source_deck_id=self.deck.id,
            source_note_type_id=self.nt.id, source_owner_user_id=self.owner.id)
        db.session.add(install)
        db.session.flush()
        db.session.add(DeckCloneNoteFieldOverride(deck_install_id=install.id, source_note_id=self.note.id,
            source_field_def_id=None, field_identity_key=first_id, field_name="Retained", operation="set", value=["keep"]))
        db.session.commit()
        first = run_retention(apply=True, limit=1)
        self.assertEqual(first["fields"], 0)
        self.assertEqual(first["next_cursor"], first_id)
        second = run_retention(apply=True, limit=1, after=first["next_cursor"])
        self.assertEqual(second["fields"], 1)
        self.assertEqual(second["next_cursor"], second_id)
        last = run_retention(apply=True, limit=1, after=second["next_cursor"])
        self.assertIsNone(last["next_cursor"])

    def test_personal_override_survives_publish_and_can_be_cleared(self):
        from app.services.clone_field_identity_service import stage_clone_note_field_override
        from app.services.note_base_comparison_service import compare_overrides, clear_override
        self.publish("v1")
        install = DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
            clone_mode="logical_overlay", source_deck_id=self.deck.id,
            source_note_type_id=self.nt.id, source_owner_user_id=self.owner.id)
        db.session.add(install)
        db.session.flush()
        override = stage_clone_note_field_override(install=install, source_note=self.note,
            field_name="Word", field_identity_key=self.field.id, operation="remove", value=None,
            identity_labels={self.field.id: "Word"})
        db.session.commit()
        override_id, install_id = override.id, install.id
        self.note.field_values = {"Word": ["new Base"]}
        db.session.commit()
        self.publish("v2")
        comparison = compare_overrides(install_id=install_id, user_id=self.learner.id)
        self.assertTrue(comparison["items"][0]["base_changed"])
        self.assertEqual(comparison["items"][0]["operation"], "remove")
        self.assertEqual(comparison["items"][0]["base_value"], ["new Base"])
        with self.assertRaises(Exception) as denied:
            compare_overrides(install_id=install_id, user_id=self.owner.id)
        self.assertEqual(denied.exception.status, 404)
        clear_override(install_id=install_id, override_id=override_id, user_id=self.learner.id,
            expected_overlay_revision=int(install.overlay_revision or 0))
        self.assertIsNone(db.session.get(DeckCloneNoteFieldOverride, override_id))

    def test_reader_transaction_sees_one_atomic_base_snapshot(self):
        from concurrent.futures import ThreadPoolExecutor
        from sqlalchemy import text
        self.publish("v1")
        self.note.field_values = {"Word": ["published later"]}
        db.session.commit()
        request = dict(deck_item_id=self.item.id, user_id=self.owner.id, version_label="v2", changelog=None,
            expected_current_release_id=self.item.current_release_id,
            expected_working_revision=self.item.working_revision, idempotency_key="concurrent-v2")
        note_id, field_id = self.note.id, self.field.id
        # Independent reader holds an InnoDB consistent snapshot while the
        # publisher commits through a second SQLAlchemy session/connection.
        with db.engine.connect() as reader:
            query = text("SELECT field_values_by_id,content_revision FROM notes WHERE id=:id")
            before = reader.execute(query, {"id": note_id}).one()
            def publish_elsewhere():
                with self.app.app_context():
                    try:
                        releases.publish_release_and_commit(**request)
                    finally:
                        db.session.remove()
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(publish_elsewhere).result(timeout=30)
            self.assertEqual(reader.execute(query, {"id": note_id}).one(), before)
            reader.rollback()
            after = reader.execute(query, {"id": note_id}).one()
            import json
            self.assertEqual(json.loads(after[0])[field_id], ["published later"])
            self.assertGreater(after[1], before[1])

    def test_delete_census_sees_override_committed_after_read_snapshot(self):
        from concurrent.futures import ThreadPoolExecutor
        from app.services.flashcard_content_service import delete_note
        self.publish("v1")
        note_id, field_id, item_id = self.note.id, self.field.id, self.item.id
        learner_id, owner_id = self.learner.id, self.owner.id
        deck_id, type_id = self.deck.id, self.nt.id
        delete_note(user_id=owner_id, note_id=note_id)
        # Establish the publisher's old consistent snapshot before a learner
        # saves. Its later reference census must be a current locking read.
        self.assertEqual(db.session.execute(select(DeckCloneNoteFieldOverride.id)).all(), [])
        def save_personal_edit():
            with self.app.app_context():
                try:
                    install = DeckInstall(deck_item_id=item_id, user_id=learner_id,
                        clone_mode="logical_overlay", source_deck_id=deck_id,
                        source_note_type_id=type_id, source_owner_user_id=owner_id)
                    db.session.add(install)
                    db.session.flush()
                    db.session.add(DeckCloneNoteFieldOverride(deck_install_id=install.id,
                        source_note_id=note_id, field_identity_key=field_id, field_name="Word",
                        source_field_def_id=field_id, operation="set", value=["keep me"]))
                    db.session.commit()
                finally:
                    db.session.remove()
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(save_personal_edit).result(timeout=30)
        self.publish("v2")
        stored = db.session.execute(select(Note).where(Note.id == note_id)
            .execution_options(include_deleted_notes=True)).scalar_one()
        self.assertIsNotNone(stored.deleted_at)
        self.assertEqual(DeckCloneNoteFieldOverride.query.count(), 1)

    def test_public_mcp_notes_and_search_never_expose_author_drafts(self):
        from app.services.mcp.marketplace_tools import list_shared_deck_notes
        from app.services.mcp.public_search_tools import _extract_preview_samples
        self.publish("v1")
        self.note.field_values = {"Word": ["private-draft-marker"]}
        new_note = Note(user_id=self.owner.id, note_type_id=self.nt.id, deck_id=self.deck.id,
            field_values={"Word": ["private-new-marker"]})
        db.session.add(new_note)
        db.session.commit()
        public = list_shared_deck_notes(user_id=self.learner.id, deck_item_id=self.item.id)
        self.assertEqual(public["total"], 1)
        self.assertEqual(public["notes"][0]["fields"]["Word"], ["base", ["nested"]])
        search = list_shared_deck_notes(user_id=self.learner.id, deck_item_id=self.item.id, query="private-draft-marker")
        self.assertEqual(search["total"], 0)
        owner = list_shared_deck_notes(user_id=self.owner.id, deck_item_id=self.item.id, query="private-draft-marker")
        self.assertEqual(owner["total"], 1)
        self.assertNotIn("private-", str(_extract_preview_samples(self.item)))

    def test_http_session_load_and_comparison_authentication(self):
        self.publish("v1")
        install = DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
            clone_mode="logical_overlay", source_deck_id=self.deck.id,
            source_note_type_id=self.nt.id, source_owner_user_id=self.owner.id)
        db.session.add(install)
        db.session.flush()
        override = DeckCloneNoteFieldOverride(deck_install_id=install.id, source_note_id=self.note.id,
            field_identity_key=self.field.id, field_name="Word", source_field_def_id=self.field.id,
            operation="set", value=["personal HTTP edit"])
        db.session.add(override)
        db.session.commit()
        install_id, override_id = install.id, override.id
        url = f"/api/marketplace/installations/{install_id}/base-overrides"
        self.assertEqual(self.client.get(url).status_code, 401)
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.learner.id)
            session["_fresh"] = True
        from flask import g
        g.pop("_login_user", None)
        self.assertEqual(self.client.get("/api/session").status_code, 200)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["content_model"], "published_base")
        kept = self.client.post(f"/api/marketplace/installations/{install_id}/overrides/{override_id}/keep",
            json={"expected_overlay_revision": int(install.overlay_revision or 0),
                "expected_base_hash": response.json["items"][0]["current_base_hash"]})
        self.assertEqual(kept.status_code, 200)
        self.assertEqual(self.client.get(url).json["items"][0]["personal_value"], ["personal HTTP edit"])
        reset = self.client.delete(f"/api/marketplace/installations/{install_id}/overrides/{override_id}",
            json={"expected_overlay_revision": kept.json["overlay_revision"]})
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(self.client.get(url).json["items"], [])
        self.assertEqual(self.client.get(f"/api/marketplace/installations/{install_id}/updates/old/diff").status_code, 410)
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.owner.id)
        g.pop("_login_user", None)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_public_sample_ignores_author_delete_draft(self):
        from app.services.note_draft_service import stage_note_delete
        from app.services.mcp.public_search_tools import _extract_preview_samples
        self.publish("v1")
        stage_note_delete(self.note)
        db.session.commit()
        with note_author_view(self.owner.id):
            samples = _extract_preview_samples(self.item)
        self.assertEqual(len(samples), 1)
        self.assertIn("base", samples[0]["word"])

    def test_publication_uses_current_schema_and_new_deck_after_old_read_snapshot(self):
        from concurrent.futures import ThreadPoolExecutor
        self.publish("v1")
        item_id, owner_id, type_id = self.item.id, self.owner.id, self.nt.id
        field_id, source_deck_id, head = self.field.id, self.deck.id, self.item.current_release_id
        self.assertEqual(db.session.execute(select(FieldDef.name).where(FieldDef.id == field_id)).scalar_one(), "Word")
        def change_source():
            with self.app.app_context():
                try:
                    field = db.session.get(FieldDef, field_id)
                    field.name = "Renamed"
                    db.session.commit()
                    child = Deck(name="New branch", parent_id=source_deck_id, owner_user_id=owner_id,
                        note_type_id=type_id)
                    db.session.add(child)
                    db.session.flush()
                    note = Note(user_id=owner_id, note_type_id=type_id, deck_id=child.id,
                        field_values={"Renamed": ["concurrent new Note"]})
                    db.session.add(note)
                    db.session.commit()
                    return note.id, db.session.get(DeckMarketplaceItem, item_id).working_revision
                finally:
                    db.session.remove()
        with ThreadPoolExecutor(max_workers=1) as pool:
            note_id, revision = pool.submit(change_source).result(timeout=30)
        releases.publish_release_and_commit(deck_item_id=item_id, user_id=owner_id, version_label="v2",
            changelog=None, expected_current_release_id=head, expected_working_revision=revision,
            idempotency_key="current-source-v2")
        self.assertEqual(self.item.published_schema_json[field_id]["name"], "Renamed")
        self.assertIsNotNone(db.session.get(Note, note_id).published_at)

    def test_publication_pins_current_template_after_old_snapshot(self):
        from concurrent.futures import ThreadPoolExecutor
        from tests.study_note_fixtures import attach_template
        from models.template import Template
        from app.repositories import template_release_repository as templates
        template = attach_template(db.session, note_type_id=self.nt.id, owner_user_id=self.owner.id,
            name="Current template", front_html="<div>Before</div>", back_html="<div>Back</div>", shared_css="")
        db.session.commit()
        self.publish("v1")
        template_id, item_id, owner_id, head = template.id, self.item.id, self.owner.id, self.item.current_release_id
        self.assertEqual(db.session.execute(select(Template.front_html).where(Template.id == template_id)).scalar_one(), "<div>Before</div>")
        def edit_template():
            with self.app.app_context():
                try:
                    db.session.get(Template, template_id).front_html = "<div>After concurrent edit</div>"
                    db.session.commit()
                    return db.session.get(DeckMarketplaceItem, item_id).working_revision
                finally:
                    db.session.remove()
        with ThreadPoolExecutor(max_workers=1) as pool:
            revision = pool.submit(edit_template).result(timeout=30)
        result = releases.publish_release_and_commit(deck_item_id=item_id, user_id=owner_id,
            version_label="v2", changelog=None, expected_current_release_id=head,
            expected_working_revision=revision, idempotency_key="current-template-v2")
        sources = templates.load_effective_template_overrides(db.session, user_id=-1,
            source_template_ids=[template_id], release_pins=templates.deck_pins(db.session, result.release.id))
        self.assertEqual(sources[template_id].front_html, "<div>After concurrent edit</div>")
        self.assertNotIn("flama.template.current_publication_reads", db.session.info)
