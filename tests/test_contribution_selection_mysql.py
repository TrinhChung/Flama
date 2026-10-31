"""Choosing notes to send, partial owner approval and whole-note review context."""
from flask import g

from app.services import deck_release_service
from app.services.change_request.helpers import compute_overlay_fingerprint
from app.services.clone_field_identity_service import stage_clone_note_field_override
from models import db
from models.deck import Deck
from models.deck_change_request import DeckChangeRequest
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import create_note_user


class ContributionSelectionTests(NoteBaseMySQLTestCase):
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
        self.learner.display_name = "Trusted Learner"
        self.nt = NoteType(user_id=self.owner.id, name="Selection test")
        db.session.add(self.nt)
        db.session.flush()
        self.meaning = FieldDef(note_type_id=self.nt.id, name="Meaning", field_type="array", position=0)
        self.image = FieldDef(note_type_id=self.nt.id, name="Image", field_type="image", position=1)
        self.source = Deck(owner_user_id=self.owner.id, note_type_id=self.nt.id, name="Source")
        self.local = Deck(owner_user_id=self.learner.id, note_type_id=self.nt.id, name="Installed")
        db.session.add_all([self.meaning, self.image, self.source, self.local])
        db.session.flush()
        notes = [
            Note(user_id=self.owner.id, note_type_id=self.nt.id, deck_id=self.source.id,
                 field_values={"Meaning": [f"base {index}"], "Image": f"https://example.invalid/{index}.png"})
            for index in range(2)
        ]
        self.item = DeckMarketplaceItem(owner_user_id=self.owner.id, source_deck_id=self.source.id,
            source_note_type_id=self.nt.id, title="Shared", publish_status="published")
        db.session.add_all([*notes, self.item])
        db.session.commit()
        # Overrides are ordered by note id, so name the notes by that order.
        self.first, self.second = sorted(notes, key=lambda note: str(note.id))
        self.first_index = notes.index(self.first)
        deck_release_service.publish_release_and_commit(deck_item_id=self.item.id,
            user_id=self.owner.id, version_label="v1", changelog=None,
            expected_current_release_id=self.item.current_release_id,
            expected_working_revision=self.item.working_revision, idempotency_key="v1")
        self.install = DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
            local_deck_id=self.local.id, clone_mode="logical_overlay",
            source_deck_id=self.source.id, source_note_type_id=self.nt.id, source_owner_user_id=self.owner.id,
            **self.install_version())
        db.session.add(self.install)
        db.session.flush()
        db.session.add(DeckCloneDeckMap(deck_install_id=self.install.id,
            source_deck_id=self.source.id, local_deck_id=self.local.id))
        self.override(self.first, self.meaning, ["first personal"])
        self.override(self.second, self.meaning, ["second personal"])
        self.override(self.second, self.image, "https://example.invalid/second-new.png")
        db.session.commit()
        self.url = f"/api/shared/decks/{self.item.id}/change-requests/send"
        self.login(self.learner.id)

    def install_version(self):
        return {"version_mode": "published_base"}

    def override(self, note, field, value):
        stage_clone_note_field_override(install=self.install, source_note=note,
            field_name=field.name, field_identity_key=field.id, operation="set", value=value,
            identity_labels={self.meaning.id: "Meaning", self.image.id: "Image"})

    def login(self, user_id):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        g.pop("_login_user", None)

    def send(self, selection=None, *, status=200):
        payload = {"title": "", "description": "",
                   "expected_overlay_fingerprint": compute_overlay_fingerprint(self.install)}
        if selection is not None:
            payload["selection"] = selection
        response = self.client.post(self.url, json=payload)
        self.assertEqual(response.status_code, status, response.get_json())
        return response.get_json()

    def test_sends_only_the_selected_note_with_its_whole_note_context(self):
        result = self.send({"mode": "only", "note_ids": [self.first.id]})
        self.assertEqual(result["status"], "pending_review")
        self.assertEqual({item["source_ref_id"] for item in result["items"]}, {self.first.id})
        self.assertEqual(result["note_count"], 1)
        self.assertEqual(result["title"], "")
        self.assertEqual(result["requester"]["display_name"], "Trusted Learner")
        self.assertEqual(result["requester"]["username"], "contributor")
        self.assertEqual([field["name"] for field in result["field_defs"]], ["Meaning", "Image"])
        self.assertEqual(result["notes"][self.first.id]["values"], {
            "Meaning": [f"base {self.first_index}"],
            "Image": f"https://example.invalid/{self.first_index}.png",
        })

    def test_excluding_every_note_sends_nothing(self):
        result = self.send({"mode": "all_except", "note_ids": [self.first.id, self.second.id]}, status=400)
        self.assertEqual(result["error"], "NO_SELECTED_CHANGES")
        self.assertEqual(DeckChangeRequest.query.count(), 0)

    def test_pending_contribution_accepts_only_an_identical_retry(self):
        first = self.send({"mode": "only", "note_ids": [self.first.id]})
        retry = self.send({"mode": "only", "note_ids": [self.first.id]})
        self.assertEqual(retry["id"], first["id"])
        other = self.send({"mode": "only", "note_ids": [self.second.id]}, status=409)
        self.assertEqual(other["error"], "CHANGE_REQUEST_PENDING")
        self.assertEqual(DeckChangeRequest.query.count(), 1)

    def test_owner_merges_only_accepted_items(self):
        sent = self.send()
        self.assertEqual(sent["note_count"], 2)
        accepted = [item["id"] for item in sent["items"] if item["source_ref_id"] == self.first.id]
        self.login(self.owner.id)
        response = self.client.post(f"/api/change-requests/{sent['id']}/approve",
            json={"selection": {"mode": "only", "item_ids": accepted}})
        self.assertEqual(response.status_code, 200, response.get_json())
        merged = response.get_json()
        self.assertEqual(merged["status"], "merged")
        decisions = {item["id"]: item["review_decision"] for item in merged["items"]}
        self.assertEqual({decisions[item_id] for item_id in accepted}, {"accepted"})
        self.assertEqual(
            {decision for item_id, decision in decisions.items() if item_id not in accepted}, {"declined"})
        db.session.expire_all()
        self.assertEqual(db.session.get(Note, self.first.id).field_values["Meaning"], ["first personal"])
        second = db.session.get(Note, self.second.id).field_values
        self.assertNotEqual(second["Meaning"], ["second personal"])
        self.assertNotEqual(second["Image"], "https://example.invalid/second-new.png")

    def test_owner_must_accept_something(self):
        sent = self.send()
        self.login(self.owner.id)
        response = self.client.post(f"/api/change-requests/{sent['id']}/approve",
            json={"selection": {"mode": "only", "item_ids": []}})
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(response.get_json()["error"], "NO_SELECTED_CHANGES")
        self.assertEqual(db.session.get(DeckChangeRequest, sent["id"]).status, "pending_review")

    def test_pages_end_on_a_whole_note(self):
        # Two items fit a page, but the second note's two changes stay together.
        preview = self.client.get(
            f"/api/shared/decks/{self.item.id}/change-requests/local-changes?limit=2").get_json()
        self.assertEqual({item["source_ref_id"] for item in preview["items"]}, {self.first.id})
        self.assertTrue(preview["page"]["has_more"])
        self.assertEqual(set(preview["notes"]), {self.first.id})
        sent = self.send()
        first_page = self.client.get(f"/api/change-requests/{sent['id']}?limit=2").get_json()
        self.assertEqual({item["source_ref_id"] for item in first_page["items"]}, {self.first.id})
        cursor = first_page["page"]["next_cursor"]
        second_page = self.client.get(f"/api/change-requests/{sent['id']}?limit=2&cursor={cursor}").get_json()
        self.assertEqual([item["source_ref_id"] for item in second_page["items"]], [self.second.id] * 2)
        self.assertFalse(second_page["page"]["has_more"])
        # The note total is counted once, with the first page.
        self.assertEqual(first_page["note_count"], 2)
        self.assertIsNone(second_page["note_count"])
        whole = self.client.get(f"/api/change-requests/{sent['id']}").get_json()
        self.assertEqual(whole["note_count"], 2)

    def test_preview_labels_notes_from_the_base_the_learner_sees(self):
        # The owner's later, unpublished edit must not leak into the label.
        self.first.field_values = {**self.first.field_values, "Meaning": ["owner draft"]}
        db.session.commit()
        preview = self.client.get(f"/api/shared/decks/{self.item.id}/change-requests/local-changes").get_json()
        labels = {item["source_ref_id"]: item["metadata_json"]["source_note_label"] for item in preview["items"]}
        self.assertEqual(labels[self.first.id], f"base {self.first_index}")


class ContributionSelectionReleaseTests(ContributionSelectionTests):
    """The same flows on the release-pinned path that runs while the Base flag is off."""

    APP_CONFIG = {"NOTE_PUBLISHED_BASE_ENABLED": False, "WTF_CSRF_ENABLED": False}

    def install_version(self):
        return {"version_mode": "release", "applied_release_id": self.item.current_release_id}


class ContributionDeckGroupingTests(NoteBaseMySQLTestCase):
    """Changes are listed sub-deck by sub-deck, named as each viewer's library names them."""

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
        nt = NoteType(user_id=self.owner.id, name="Deck test")
        db.session.add(nt)
        db.session.flush()
        self.word = FieldDef(note_type_id=nt.id, name="Word", field_type="text", position=0)
        self.source = Deck(owner_user_id=self.owner.id, note_type_id=nt.id, name="Source")
        self.local = Deck(owner_user_id=self.learner.id, note_type_id=nt.id, name="Installed")
        db.session.add_all([self.word, self.source, self.local])
        db.session.flush()
        self.lesson = Deck(owner_user_id=self.owner.id, note_type_id=nt.id, name="Lesson 1", parent_id=self.source.id)
        self.local_lesson = Deck(owner_user_id=self.learner.id, note_type_id=nt.id, name="My lesson",
                                 parent_id=self.local.id)
        notes = [Note(user_id=self.owner.id, note_type_id=nt.id, deck_id=self.source.id,
                      field_values={"Word": f"word {index}"}) for index in range(2)]
        self.item = DeckMarketplaceItem(owner_user_id=self.owner.id, source_deck_id=self.source.id,
            source_note_type_id=nt.id, title="Shared", publish_status="published")
        db.session.add_all([self.lesson, self.local_lesson, *notes, self.item])
        db.session.flush()
        # The note with the smaller id goes into the sub-deck, so only folder
        # order can put the root note first.
        self.in_lesson, self.in_root = sorted(notes, key=lambda note: str(note.id))
        self.in_lesson.deck_id = self.lesson.id
        db.session.commit()
        deck_release_service.publish_release_and_commit(deck_item_id=self.item.id,
            user_id=self.owner.id, version_label="v1", changelog=None,
            expected_current_release_id=self.item.current_release_id,
            expected_working_revision=self.item.working_revision, idempotency_key="v1")
        self.install = DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
            local_deck_id=self.local.id, clone_mode="logical_overlay",
            source_deck_id=self.source.id, source_note_type_id=nt.id, source_owner_user_id=self.owner.id,
            **self.install_version())
        db.session.add(self.install)
        db.session.flush()
        db.session.add_all([
            DeckCloneDeckMap(deck_install_id=self.install.id, source_deck_id=self.source.id,
                             local_deck_id=self.local.id),
            DeckCloneDeckMap(deck_install_id=self.install.id, source_deck_id=self.lesson.id,
                             local_deck_id=self.local_lesson.id),
        ])
        for note in notes:
            stage_clone_note_field_override(install=self.install, source_note=note, field_name="Word",
                field_identity_key=self.word.id, operation="set", value="edited",
                identity_labels={self.word.id: "Word"})
        db.session.commit()
        self.login(self.learner.id)

    def install_version(self):
        return {"version_mode": "published_base"}

    def login(self, user_id):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True
        g.pop("_login_user", None)

    def test_learner_sees_changes_folder_by_folder_under_their_own_folder_names(self):
        preview = self.client.get(f"/api/shared/decks/{self.item.id}/change-requests/local-changes").get_json()
        self.assertEqual([item["source_ref_id"] for item in preview["items"]], [self.in_root.id, self.in_lesson.id])
        decks = {note_id: note["deck"] for note_id, note in preview["notes"].items()}
        self.assertEqual(decks[self.in_root.id], {"key": str(self.local.id), "path": ["Installed"], "order": 0})
        self.assertEqual(decks[self.in_lesson.id],
                         {"key": str(self.local_lesson.id), "path": ["Installed", "My lesson"], "order": 1})

    def test_owner_sees_the_same_notes_under_the_source_folders(self):
        sent = self.client.post(f"/api/shared/decks/{self.item.id}/change-requests/send", json={
            "title": "", "description": "",
            "expected_overlay_fingerprint": compute_overlay_fingerprint(self.install)}).get_json()
        self.login(self.owner.id)
        detail = self.client.get(f"/api/change-requests/{sent['id']}").get_json()
        self.assertEqual([item["source_ref_id"] for item in detail["items"]], [self.in_root.id, self.in_lesson.id])
        self.assertEqual(detail["notes"][self.in_lesson.id]["deck"],
                         {"key": str(self.lesson.id), "path": ["Source", "Lesson 1"], "order": 1})


class ContributionDeckGroupingReleaseTests(ContributionDeckGroupingTests):
    APP_CONFIG = {"NOTE_PUBLISHED_BASE_ENABLED": False, "WTF_CSRF_ENABLED": False}

    def install_version(self):
        return {"version_mode": "release", "applied_release_id": self.item.current_release_id}
