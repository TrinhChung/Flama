"""Single-action contributions against disposable local MySQL, including retries."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from flask import g

from app.services import deck_release_service
from app.services.change_request.lifecycle import build_or_refresh_draft_request
from app.services.change_request.helpers import compute_overlay_fingerprint
from app.services.clone_field_identity_service import stage_clone_note_field_override
from models import db
from models.deck import Deck
from models.deck_change_request import DeckChangeRequest
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_draft import NoteDraft
from models.note_type import NoteType
from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import create_note_user


class ContributionSendTests(NoteBaseMySQLTestCase):
    APP_CONFIG = {"NOTE_PUBLISHED_BASE_ENABLED": True, "WTF_CSRF_ENABLED": False}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from app.routes import register_blueprints
        register_blueprints(cls.app)

    def setUp(self):
        super().setUp()
        self.owner = create_note_user(db.session, username="author", email="author@example.invalid")
        self.learner = create_note_user(db.session, username="contributor", email="learner@example.invalid")
        self.nt = NoteType(user_id=self.owner.id, name="Contribution test")
        db.session.add(self.nt)
        db.session.flush()
        self.field = FieldDef(note_type_id=self.nt.id, name="Meaning", field_type="array", position=0)
        self.source = Deck(owner_user_id=self.owner.id, note_type_id=self.nt.id, name="Source")
        self.local = Deck(owner_user_id=self.learner.id, note_type_id=self.nt.id, name="Installed")
        db.session.add_all([self.field, self.source, self.local])
        db.session.flush()
        self.note = Note(user_id=self.owner.id, note_type_id=self.nt.id, deck_id=self.source.id,
                         field_values={"Meaning": ["base"]})
        self.item = DeckMarketplaceItem(owner_user_id=self.owner.id, source_deck_id=self.source.id,
            source_note_type_id=self.nt.id, title="Shared", publish_status="published")
        db.session.add_all([self.note, self.item])
        db.session.commit()
        self.publish("v1")
        self.install = DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
            local_deck_id=self.local.id, clone_mode="logical_overlay", version_mode="published_base",
            source_deck_id=self.source.id, source_note_type_id=self.nt.id, source_owner_user_id=self.owner.id)
        db.session.add(self.install)
        db.session.flush()
        db.session.add(DeckCloneDeckMap(deck_install_id=self.install.id,
            source_deck_id=self.source.id, local_deck_id=self.local.id))
        self.override = stage_clone_note_field_override(install=self.install, source_note=self.note,
            field_name="Meaning", field_identity_key=self.field.id, operation="set", value=["personal"],
            identity_labels={self.field.id: "Meaning"})
        db.session.commit()
        self.url = f"/api/shared/decks/{self.item.id}/change-requests/send"
        self.login(self.learner.id)

    def login(self, user_id):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        g.pop("_login_user", None)

    def publish(self, label):
        return deck_release_service.publish_release_and_commit(deck_item_id=self.item.id,
            user_id=self.owner.id, version_label=label, changelog=None,
            expected_current_release_id=self.item.current_release_id,
            expected_working_revision=self.item.working_revision, idempotency_key=label)

    def payload(self):
        return {"title": "Fix meaning", "description": "Correct the saved definition",
                "expected_overlay_fingerprint": compute_overlay_fingerprint(self.install)}

    def send(self, payload=None):
        response = self.client.post(self.url, json=payload or self.payload())
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def legacy_draft(self):
        row = build_or_refresh_draft_request(deck_item_id=self.item.id,
            requester_user_id=self.learner.id, title="Old draft", description="Old description")
        db.session.commit()
        return row

    def test_sends_saved_changes_without_manual_draft_or_sync(self):
        result = self.send()
        self.assertEqual(result["status"], "pending_review")
        self.assertEqual(result["item_count"], 1)
        self.assertEqual(result["title"], "Fix meaning")
        self.assertEqual(result["items"][0]["after_value"], ["personal"])
        self.assertEqual(db.session.get(Note, self.note.id).field_values["Meaning"], ["base"])
        self.assertIsNone(db.session.get(NoteDraft, self.note.id))
        self.assertEqual(DeckCloneNoteFieldOverride.query.one().value, ["personal"])

    def test_reuses_an_existing_unsynced_draft_and_updates_its_metadata(self):
        old = self.legacy_draft()
        result = self.send()
        self.assertEqual(result["id"], old.id)
        self.assertEqual(result["status"], "pending_review")
        self.assertEqual(result["description"], "Correct the saved definition")

    def test_retry_returns_same_pending_request(self):
        payload = self.payload()
        first, second = self.send(payload), self.send(payload)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["revision"], second["revision"])
        self.assertEqual(DeckChangeRequest.query.count(), 1)

    def test_metadata_alone_cannot_create_an_empty_contribution(self):
        db.session.delete(self.override)
        db.session.commit()
        response = self.client.post(self.url, json=self.payload())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "NO_LOCAL_CHANGES")
        self.assertEqual(DeckChangeRequest.query.count(), 0)

    def test_stale_preview_requires_review_before_sending(self):
        old = self.payload()
        self.override.value = ["new saved edit"]
        db.session.commit()
        response = self.client.post(self.url, json=old)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json["error"], "CHANGE_REQUEST_STALE")
        self.assertEqual(DeckChangeRequest.query.count(), 0)
        self.assertEqual(self.send()["items"][0]["after_value"], ["new saved edit"])

    def test_conflicts_survive_and_resolved_manual_values_are_preserved(self):
        old = self.legacy_draft()
        self.note.field_values = {"Meaning": ["author update"]}
        db.session.commit()
        self.publish("v2")
        result = self.send()
        self.assertEqual(result["status"], "has_conflict")
        self.assertEqual(result["unresolved_conflict_count"], 1)
        conflict_id = result["conflicts"][0]["id"]
        response = self.client.post(
            f"/api/shared/decks/{self.item.id}/change-requests/{old.id}/conflicts/{conflict_id}/resolve",
            json={"resolution_mode": "manual", "resolved_value": ["chosen", ["nested"]]})
        self.assertEqual(response.status_code, 200, response.json)
        submitted = self.send()
        self.assertEqual(submitted["id"], old.id)
        self.assertEqual(submitted["status"], "pending_review")
        self.assertEqual(submitted["items"][0]["effective_after_value"], ["chosen", ["nested"]])
        self.assertEqual(submitted["conflicts"][0]["resolution_mode"], "manual")

    def test_changed_personal_edits_refresh_old_draft(self):
        old = self.legacy_draft()
        self.override.value = ["latest personal edit"]
        db.session.commit()
        result = self.send()
        self.assertEqual(result["id"], old.id)
        self.assertEqual(result["items"][0]["after_value"], ["latest personal edit"])

    def test_failure_rolls_back_automatic_draft(self):
        with patch("app.services.change_request.lifecycle.submit_request_for_review", side_effect=RuntimeError("failure")):
            response = self.client.post(self.url, json=self.payload())
            self.assertEqual(response.status_code, 500)
        self.assertEqual(DeckChangeRequest.query.count(), 0)
        self.assertEqual(DeckCloneNoteFieldOverride.query.one().value, ["personal"])

    def test_requires_authentication_install_ownership_and_valid_preview(self):
        payload = self.payload()
        self.assertEqual(self.app.test_client().post(self.url, json=payload).status_code, 401)
        self.login(self.owner.id)
        self.assertEqual(self.client.post(self.url, json=payload).status_code, 404)
        self.login(self.learner.id)
        payload["expected_overlay_fingerprint"] = "invalid"
        self.assertEqual(self.client.post(self.url, json=payload).status_code, 400)
        self.assertEqual(DeckChangeRequest.query.count(), 0)

    def test_parallel_sends_produce_one_pending_request(self):
        payload, url, learner_id = self.payload(), self.url, self.learner.id
        barrier = Barrier(2)
        db.session.remove()

        def send_in_process_session():
            client = self.app.test_client()
            with client.session_transaction() as session:
                session["_user_id"] = str(learner_id)
                session["_fresh"] = True
            barrier.wait(timeout=10)
            response = client.post(url, json=payload)
            return response.status_code, response.get_json()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(send_in_process_session) for _ in range(2)]
            results = [future.result(timeout=25) for future in futures]
        self.assertEqual([status for status, _ in results], [200, 200], results)
        self.assertEqual(results[0][1]["id"], results[1][1]["id"])
        self.assertEqual(DeckChangeRequest.query.count(), 1)
