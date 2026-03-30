"""Integration tests for shared-deck change request workflow."""

import unittest

from app import create_app
from models import db
from models.deck import Deck
from models.flashcard import (
    DeckChangeRequest,
    DeckChangeRequestConflict,
    DeckChangeRequestItem,
    DeckCloneAddedFieldDef,
    DeckCloneFieldDefOverride,
    DeckCloneFieldOrderOverride,
    DeckCloneNoteFieldOverride,
    DeckInstall,
    DeckMarketplaceItem,
    FieldDef,
    Note,
)
from models.user import User


class DeckChangeRequestFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = User(username="owner", email="owner@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.owner_user_id = user.id

            deck = Deck(name="Owner Root Deck")
            db.session.add(deck)
            db.session.flush()
            self.owner_deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "owner@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_note_type(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "Japanese Vocabulary",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Reading", "field_type": "text", "position": 1, "required": False},
                    {"name": "Meaning", "field_type": "richtext", "position": 2, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}} - {{Reading}} {{{Meaning}}}</div>",
                    "shared_css": ".card{color:red;}",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def _create_shared_clone_context(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        field_ids = {row["name"]: row["id"] for row in note_type.get("field_defs", [])}

        with self.app.app_context():
            child_deck = Deck(name="Shared Child", parent_id=self.owner_deck_id)
            db.session.add(child_deck)
            db.session.flush()
            child_deck_id = child_deck.id
            db.session.commit()

        owner_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": child_deck_id,
                "field_values": {
                    "Word": "犬",
                    "Reading": "いぬ",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(owner_note_resp.status_code, 201)
        source_note_id = owner_note_resp.get_json()["id"]

        with self.app.app_context():
            learner = User(username="learner", email="learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            learner_id = learner.id

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.owner_user_id,
                source_deck_id=self.owner_deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Change Request",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "learner@example.com", "password": "password"},
            follow_redirects=True,
        )
        install_resp = learner_client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_resp.status_code, 201)

        with self.app.app_context():
            install_row = DeckInstall.query.filter_by(deck_item_id=deck_item_id, user_id=learner_id).first()
            self.assertIsNotNone(install_row)
            install_id = install_row.id

        return {
            "deck_item_id": deck_item_id,
            "note_type_id": note_type_id,
            "field_ids": field_ids,
            "source_note_id": source_note_id,
            "learner_id": learner_id,
            "learner_client": learner_client,
            "install_id": install_id,
        }

    def _apply_overlay(self, learner_client, deck_item_id, payload):
        response = learner_client.post(
            f"/api/shared/decks/{deck_item_id}/clone/overlay",
            json=payload,
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json() or {}

    def _create_draft(self, learner_client, deck_item_id, *, title="Word fixes", description="Update clone edits"):
        response = learner_client.post(
            f"/api/shared/decks/{deck_item_id}/change-requests/draft",
            json={"title": title, "description": description},
        )
        return response

    def _sync_request(self, learner_client, deck_item_id, request_id):
        return learner_client.post(
            f"/api/shared/decks/{deck_item_id}/change-requests/{request_id}/sync"
        )

    def _submit_request(self, learner_client, deck_item_id, request_id):
        return learner_client.post(
            f"/api/shared/decks/{deck_item_id}/change-requests/{request_id}/submit"
        )

    def test_change_request_draft_requires_meaningful_overlay_changes(self):
        ctx = self._create_shared_clone_context()
        learner_client = ctx["learner_client"]
        deck_item_id = ctx["deck_item_id"]

        empty_resp = self._create_draft(learner_client, deck_item_id)
        self.assertEqual(empty_resp.status_code, 400)
        self.assertEqual((empty_resp.get_json() or {}).get("error"), "NO_LOCAL_CHANGES")

        self._apply_overlay(
            learner_client,
            deck_item_id,
            {
                "note_field_overrides": [
                    {
                        "source_note_id": ctx["source_note_id"],
                        "field_name": "Word",
                        "operation": "set",
                        "value": "犬*",
                    }
                ]
            },
        )

        draft_resp = self._create_draft(
            learner_client,
            deck_item_id,
            title="Word polish",
            description="Tighten the front field text.",
        )
        self.assertEqual(draft_resp.status_code, 201)
        draft_payload = draft_resp.get_json() or {}
        self.assertEqual(draft_payload.get("status"), "needs_sync")
        self.assertEqual(int(draft_payload.get("item_count") or 0), 1)
        self.assertEqual(draft_payload.get("requester", {}).get("id"), ctx["learner_id"])
        self.assertEqual(draft_payload.get("owner", {}).get("id"), self.owner_user_id)

        with self.app.app_context():
            request_row = DeckChangeRequest.query.get(draft_payload["id"])
            self.assertIsNotNone(request_row)
            self.assertEqual(request_row.deck_install_id, ctx["install_id"])
            self.assertEqual(
                DeckChangeRequestItem.query.filter_by(change_request_id=request_row.id).count(),
                1,
            )

    def test_change_request_sync_conflict_resolution_and_submit_guards(self):
        ctx = self._create_shared_clone_context()
        learner_client = ctx["learner_client"]
        deck_item_id = ctx["deck_item_id"]

        self._apply_overlay(
            learner_client,
            deck_item_id,
            {
                "note_field_overrides": [
                    {
                        "source_note_id": ctx["source_note_id"],
                        "field_name": "Word",
                        "operation": "set",
                        "value": "犬*",
                    }
                ]
            },
        )

        draft_resp = self._create_draft(learner_client, deck_item_id)
        self.assertEqual(draft_resp.status_code, 201)
        request_id = draft_resp.get_json()["id"]

        submit_without_sync = self._submit_request(learner_client, deck_item_id, request_id)
        self.assertEqual(submit_without_sync.status_code, 409)
        self.assertEqual(
            (submit_without_sync.get_json() or {}).get("error"),
            "CHANGE_REQUEST_SYNC_REQUIRED",
        )

        with self.app.app_context():
            note = Note.query.get(ctx["source_note_id"])
            note.field_values = {**dict(note.field_values or {}), "Word": "犬-owner"}
            db.session.commit()

        sync_resp = self._sync_request(learner_client, deck_item_id, request_id)
        self.assertEqual(sync_resp.status_code, 200)
        sync_payload = sync_resp.get_json() or {}
        self.assertEqual(sync_payload.get("status"), "has_conflict")
        self.assertEqual(int(sync_payload.get("unresolved_conflict_count") or 0), 1)
        conflict_id = (sync_payload.get("conflicts") or [])[0]["id"]

        submit_with_conflict = self._submit_request(learner_client, deck_item_id, request_id)
        self.assertEqual(submit_with_conflict.status_code, 409)
        self.assertEqual(
            (submit_with_conflict.get_json() or {}).get("error"),
            "CHANGE_REQUEST_CONFLICTS_UNRESOLVED",
        )

        resolve_resp = learner_client.post(
            f"/api/shared/decks/{deck_item_id}/change-requests/{request_id}/conflicts/{conflict_id}/resolve",
            json={"resolution_mode": "keep_mine"},
        )
        self.assertEqual(resolve_resp.status_code, 200)
        resolve_payload = resolve_resp.get_json() or {}
        self.assertEqual(resolve_payload.get("status"), "draft")
        self.assertEqual(int(resolve_payload.get("unresolved_conflict_count") or 0), 0)

        submit_resp = self._submit_request(learner_client, deck_item_id, request_id)
        self.assertEqual(submit_resp.status_code, 200)
        submit_payload = submit_resp.get_json() or {}
        self.assertEqual(submit_payload.get("status"), "pending_review")

        with self.app.app_context():
            request_row = DeckChangeRequest.query.get(request_id)
            self.assertEqual(request_row.status, "pending_review")
            conflict_row = DeckChangeRequestConflict.query.filter_by(change_request_id=request_id).first()
            self.assertIsNotNone(conflict_row)
            self.assertEqual(conflict_row.resolution_mode, "keep_mine")

    def test_change_request_owner_approve_merges_and_keeps_traceability(self):
        ctx = self._create_shared_clone_context()
        learner_client = ctx["learner_client"]
        deck_item_id = ctx["deck_item_id"]

        self._apply_overlay(
            learner_client,
            deck_item_id,
            {
                "updated_defs": [
                    {
                        "source_field_def_id": ctx["field_ids"]["Meaning"],
                        "properties": {"required": True},
                    }
                ],
                "note_field_overrides": [
                    {
                        "source_note_id": ctx["source_note_id"],
                        "field_name": "Word",
                        "operation": "set",
                        "value": "犬*",
                    }
                ],
            },
        )

        draft_resp = self._create_draft(learner_client, deck_item_id)
        self.assertEqual(draft_resp.status_code, 201)
        request_id = draft_resp.get_json()["id"]

        sync_resp = self._sync_request(learner_client, deck_item_id, request_id)
        self.assertEqual(sync_resp.status_code, 200)
        self.assertEqual((sync_resp.get_json() or {}).get("status"), "draft")

        submit_resp = self._submit_request(learner_client, deck_item_id, request_id)
        self.assertEqual(submit_resp.status_code, 200)

        approve_resp = self.client.post(
            f"/api/change-requests/{request_id}/approve",
            json={"review_comment": "Looks good."},
        )
        self.assertEqual(approve_resp.status_code, 200)
        approve_payload = approve_resp.get_json() or {}
        self.assertEqual(approve_payload.get("status"), "merged")
        self.assertIsNotNone(approve_payload.get("merged_at"))

        with self.app.app_context():
            note = Note.query.get(ctx["source_note_id"])
            self.assertEqual((note.field_values or {}).get("Word"), "犬*")
            meaning_field = FieldDef.query.get(ctx["field_ids"]["Meaning"])
            self.assertTrue(bool(meaning_field.required))

            request_row = DeckChangeRequest.query.get(request_id)
            self.assertEqual(request_row.requester_user_id, ctx["learner_id"])
            self.assertEqual(request_row.deck_item_id, deck_item_id)
            self.assertEqual(request_row.status, "merged")
            self.assertIsNotNone(request_row.merged_at)
            self.assertEqual(request_row.reviewed_by_user_id, self.owner_user_id)
            self.assertGreater(
                DeckChangeRequestItem.query.filter_by(change_request_id=request_id).count(),
                0,
            )

            install_row = DeckInstall.query.get(ctx["install_id"])
            self.assertEqual(install_row.last_sync_status, "clean")
            self.assertEqual(
                DeckCloneFieldDefOverride.query.filter_by(deck_install_id=ctx["install_id"]).count(),
                0,
            )
            self.assertEqual(
                DeckCloneAddedFieldDef.query.filter_by(deck_install_id=ctx["install_id"]).count(),
                0,
            )
            self.assertEqual(
                DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=ctx["install_id"]).count(),
                0,
            )
            self.assertEqual(
                DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=ctx["install_id"]).count(),
                0,
            )

    def test_change_request_owner_reject_keeps_source_unchanged(self):
        ctx = self._create_shared_clone_context()
        learner_client = ctx["learner_client"]
        deck_item_id = ctx["deck_item_id"]

        self._apply_overlay(
            learner_client,
            deck_item_id,
            {
                "note_field_overrides": [
                    {
                        "source_note_id": ctx["source_note_id"],
                        "field_name": "Word",
                        "operation": "set",
                        "value": "犬*",
                    }
                ]
            },
        )

        draft_resp = self._create_draft(learner_client, deck_item_id)
        request_id = draft_resp.get_json()["id"]
        self._sync_request(learner_client, deck_item_id, request_id)
        self._submit_request(learner_client, deck_item_id, request_id)

        reject_resp = self.client.post(
            f"/api/change-requests/{request_id}/reject",
            json={"review_comment": "Not enough justification."},
        )
        self.assertEqual(reject_resp.status_code, 200)
        reject_payload = reject_resp.get_json() or {}
        self.assertEqual(reject_payload.get("status"), "rejected")
        self.assertEqual(reject_payload.get("review_comment"), "Not enough justification.")

        with self.app.app_context():
            note = Note.query.get(ctx["source_note_id"])
            self.assertEqual((note.field_values or {}).get("Word"), "犬")

            request_row = DeckChangeRequest.query.get(request_id)
            self.assertEqual(request_row.status, "rejected")
            self.assertEqual(request_row.reviewed_by_user_id, self.owner_user_id)

            install_row = DeckInstall.query.get(ctx["install_id"])
            self.assertEqual(install_row.last_sync_status, "needs_sync")
            self.assertEqual(
                DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=ctx["install_id"]).count(),
                1,
            )
