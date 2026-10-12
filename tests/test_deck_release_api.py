"""Focused integration tests for immutable shared-deck release APIs."""

import unittest
from unittest.mock import patch

from app import create_app
from app.repositories import deck_release_repository
from app.services import (
    deck_release_service,
    deck_working_tree_service,
    marketplace_query_service,
)
from models import db
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.deck_working_dirty_entity import DeckWorkingDirtyEntity
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.user import User
from tests.study_note_fixtures import create_note_user


class DeckReleaseApiTests(unittest.TestCase):
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
            owner = create_note_user(db.session,
                username="release-owner",
                email="release-owner@example.com",
            )
            owner.set_password("password")
            learner = create_note_user(db.session,
                username="release-learner",
                email="release-learner@example.com",
            )
            learner.set_password("password")
            db.session.add_all([owner, learner])
            db.session.flush()
            self.owner_id = owner.id
            self.learner_id = learner.id

            note_type = NoteType(
                user_id=owner.id,
                name="Release Vocabulary",
                publish_status="private",
                pricing_mode="free",
            )
            db.session.add(note_type)
            db.session.flush()
            word_field = FieldDef(
                note_type_id=note_type.id,
                name="Word",
                field_type="text",
                position=0,
                required=True,
            )
            meaning_field = FieldDef(
                note_type_id=note_type.id,
                name="Meaning",
                field_type="richtext",
                position=1,
                required=False,
            )
            db.session.add_all([word_field, meaning_field])

            root_deck = Deck(
                name="Release Root",
                owner_user_id=owner.id,
                note_type_id=note_type.id,
            )
            db.session.add(root_deck)
            db.session.flush()
            child_deck = Deck(
                name="Release Child",
                parent_id=root_deck.id,
                owner_user_id=owner.id,
                note_type_id=note_type.id,
            )
            db.session.add(child_deck)
            db.session.flush()

            first_note = Note(
                note_type_id=note_type.id,
                user_id=owner.id,
                deck_id=root_deck.id,
                field_values={"Word": "犬", "Meaning": "dog"},
                tags=["animal"],
            )
            second_note = Note(
                note_type_id=note_type.id,
                user_id=owner.id,
                deck_id=child_deck.id,
                field_values={"Word": "猫", "Meaning": "cat"},
                tags=[],
            )
            db.session.add_all([first_note, second_note])
            db.session.flush()

            deck_item = DeckMarketplaceItem(
                owner_user_id=owner.id,
                source_deck_id=root_deck.id,
                source_note_type_id=note_type.id,
                title="Release Test Deck",
                description="Release API fixture",
                primary_category="Vocabulary",
                tags=[],
                pricing_mode="free",
                version="0.0.0",
                publish_status="published",
                working_revision=0,
            )
            db.session.add(deck_item)
            db.session.commit()

            self.deck_item_id = deck_item.id
            self.note_type_id = note_type.id
            self.word_field_id = word_field.id
            self.meaning_field_id = meaning_field.id
            self.first_note_id = first_note.id
            self.second_note_id = second_note.id

        self._login("release-owner@example.com")

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, email: str):
        self.client.delete("/api/session")
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "password"},
        )
        self.assertEqual(response.status_code, 200)

    def _publish(
        self,
        *,
        version_label: str,
        expected_release_id,
        expected_working_revision: int,
        key: str,
        changelog: str = "Release notes",
    ):
        return self.client.post(
            f"/api/marketplace/decks/{self.deck_item_id}/releases",
            headers={"Idempotency-Key": key},
            json={
                "version_label": version_label,
                "changelog": changelog,
                "expected_current_release_id": expected_release_id,
                "expected_working_revision": expected_working_revision,
            },
        )

    def test_publish_stores_release_bound_samples_that_ignore_live_mutation(self):
        response = self._publish(
            version_label="1.0.0",
            expected_release_id=None,
            expected_working_revision=0,
            key="release-sample-cache",
        )
        self.assertEqual(response.status_code, 201)

        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            cached = marketplace_query_service.build_shared_deck_test_samples(
                item,
                limit=5,
            )
            self.assertEqual(item.preview_samples_release_id, item.current_release_id)
            self.assertEqual(item.preview_samples_schema_version, 1)
            self.assertTrue(cached)

            original_word = cached[0]["word"]
            cached_note = db.session.get(Note, cached[0]["note_id"])
            cached_note.field_values = {
                **dict(cached_note.field_values or {}),
                "Word": "live-working-copy-only",
            }
            db.session.flush()

            after_live_mutation = marketplace_query_service.build_shared_deck_test_samples(
                item,
                limit=5,
            )
            self.assertEqual(after_live_mutation[0]["word"], original_word)

    def test_owner_preview_is_atomic_cursor_paginated_and_owner_only(self):
        with patch.object(
            deck_release_repository,
            "list_source_notes",
            side_effect=AssertionError("checkpoint preview scanned all notes"),
        ):
            response = self.client.get(
                f"/api/marketplace/decks/{self.deck_item_id}/releases/preview",
                query_string={"limit": 3},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIsNone(payload["base_release"])
        self.assertEqual(payload["working_revision"], 0)
        self.assertEqual(payload["summary"]["change_count"], 10)
        self.assertEqual(payload["summary"]["baseline_note_count"], 2)
        self.assertEqual(payload["initial_baseline_mode"], "checkpoint")
        self.assertEqual(len(payload["items"]), 3)
        self.assertIsNotNone(payload["next_cursor"])
        self.assertTrue(
            all(row["operation"] == "add" for row in payload["items"])
        )

        second_page = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/preview",
            query_string={"limit": 3, "cursor": payload["next_cursor"]},
        )
        self.assertEqual(second_page.status_code, 200)
        self.assertNotEqual(
            payload["items"][0]["change_key"],
            second_page.get_json()["items"][0]["change_key"],
        )

        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            item.working_revision = 1
            db.session.commit()
        stale_page = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/preview",
            query_string={"limit": 3, "cursor": payload["next_cursor"]},
        )
        self.assertEqual(stale_page.status_code, 409)
        self.assertEqual(stale_page.get_json()["error"], "WORKING_REVISION_STALE")

        self._login("release-learner@example.com")
        forbidden = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/preview"
        )
        self.assertEqual(forbidden.status_code, 404)

    def test_initial_publish_is_immutable_idempotent_and_snapshots_notes(self):
        missing_key = self.client.post(
            f"/api/marketplace/decks/{self.deck_item_id}/releases",
            json={
                "version_label": "1.0.0",
                "expected_current_release_id": None,
            },
        )
        self.assertEqual(missing_key.status_code, 400)
        self.assertEqual(missing_key.get_json()["error"], "IDEMPOTENCY_KEY_REQUIRED")

        first = self._publish(
            version_label="1.0.0",
            expected_release_id=None,
            expected_working_revision=0,
            key="release-initial",
        )
        self.assertEqual(first.status_code, 201)
        first_payload = first.get_json()
        self.assertFalse(first_payload["replayed"])
        release_id = first_payload["release"]["id"]
        self.assertEqual(first_payload["release"]["sequence_no"], 1)
        self.assertEqual(first_payload["release"]["change_count"], 10)

        replay = self._publish(
            version_label="1.0.0",
            expected_release_id=None,
            expected_working_revision=0,
            key="release-initial",
        )
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.get_json()["replayed"])
        self.assertEqual(replay.get_json()["release"]["id"], release_id)

        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            self.assertEqual(item.current_release_id, release_id)
            self.assertEqual(item.version, "1.0.0")
            self.assertEqual(
                DeckRelease.query.filter_by(deck_item_id=self.deck_item_id).count(),
                1,
            )
            self.assertEqual(
                DeckReleaseChange.query.filter_by(release_id=release_id).count(),
                10,
            )
            self.assertEqual(
                DeckReleaseNoteCheckpoint.query.filter_by(
                    release_id=release_id
                ).count(),
                2,
            )
            self.assertEqual(
                DeckReleaseEntityMembership.query.filter_by(
                    deck_item_id=self.deck_item_id
                ).count(),
                4,
            )
            release = db.session.get(DeckRelease, release_id)
            persisted_changes = DeckReleaseChange.query.filter_by(
                release_id=release_id
            ).all()
            schema_only_manifest = deck_release_service._release_manifest_hash(
                [
                    {
                        "change_key": row.change_key,
                        "entity_kind": row.entity_kind,
                        "entity_id": row.entity_id,
                        "field_def_id": row.field_def_id,
                        "property_key": row.property_key,
                        "operation": row.operation,
                        "before_hash": row.before_hash,
                        "after_hash": row.after_hash,
                        "source_deck_id": row.source_deck_id,
                    }
                    for row in persisted_changes
                ]
            )
            self.assertNotEqual(release.manifest_hash, schema_only_manifest)
            self.assertEqual(
                deck_release_service.get_note_values_at_release(
                    release_id,
                    self.first_note_id,
                )["Word"],
                db.session.get(Note, self.first_note_id).field_values["Word"],
            )

    def test_publish_accepts_idempotency_key_in_payload_fallback(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.owner_id)
            sess["_fresh"] = True

        response = self.client.post(
            f"/api/marketplace/decks/{self.deck_item_id}/releases",
            json={
                "version_label": "1.0.0",
                "expected_current_release_id": None,
                "idempotency_key": "release-payload-fallback-key",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["release"]["version_label"], "1.0.0")

    def test_initial_release_preserves_atomic_baseline_for_legacy_install(self):
        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            db.session.add(
                DeckInstall(
                    deck_item_id=item.id,
                    user_id=self.learner_id,
                    clone_mode="logical_overlay",
                    source_deck_id=item.source_deck_id,
                    source_note_type_id=item.source_note_type_id,
                    source_owner_user_id=item.owner_user_id,
                    applied_release_id=None,
                    seen_release_id=None,
                    version_mode="legacy_snapshot",
                )
            )
            db.session.commit()

        preview = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/preview"
        )
        self.assertEqual(preview.status_code, 200)
        preview_payload = preview.get_json()
        self.assertEqual(preview_payload["initial_baseline_mode"], "atomic")
        self.assertEqual(preview_payload["summary"]["baseline_note_count"], 2)
        self.assertEqual(preview_payload["summary"]["change_count"], 14)

        published = self._publish(
            version_label="1.0.0",
            expected_release_id=None,
            expected_working_revision=0,
            key="legacy-baseline-v1",
        )
        self.assertEqual(published.status_code, 201)
        release_id = published.get_json()["release"]["id"]
        self.assertEqual(published.get_json()["release"]["change_count"], 14)
        with self.app.app_context():
            self.assertEqual(
                DeckReleaseChange.query.filter_by(
                    release_id=release_id,
                    entity_kind="note_field",
                ).count(),
                4,
            )
            self.assertEqual(
                DeckReleaseNoteCheckpoint.query.filter_by(
                    release_id=release_id
                ).count(),
                2,
            )

    def test_second_release_diff_history_filters_and_reconstruction(self):
        first = self._publish(
            version_label="1.0.0",
            expected_release_id=None,
            expected_working_revision=0,
            key="release-v1",
        )
        self.assertEqual(first.status_code, 201)
        first_release_id = first.get_json()["release"]["id"]

        with self.app.app_context():
            note = db.session.get(Note, self.first_note_id)
            note.field_values = {**dict(note.field_values), "Word": "犬 updated"}
            meaning_field = db.session.get(FieldDef, self.meaning_field_id)
            meaning_field.required = True
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            item.working_revision = int(item.working_revision or 0) + 1
            db.session.add(
                DeckWorkingDirtyEntity(
                    deck_item_id=self.deck_item_id,
                    entity_kind="note_field",
                    entity_id=self.first_note_id,
                    field_def_id=self.word_field_id,
                    property_key=f"field:{self.word_field_id}",
                    operation="set",
                    current_hash="a" * 64,
                    source_deck_id=note.deck_id,
                    working_revision=1,
                    metadata_json={"field_name": "Word"},
                )
            )
            db.session.commit()

        preview = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/preview"
        )
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["summary"]["change_count"], 2)
        self.assertEqual(
            {row["operation"] for row in preview.get_json()["items"]},
            {"set"},
        )

        stale = self._publish(
            version_label="1.1.0",
            expected_release_id=None,
            expected_working_revision=1,
            key="release-stale",
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.get_json()["error"], "RELEASE_HEAD_STALE")

        stale_working = self._publish(
            version_label="1.1.0",
            expected_release_id=first_release_id,
            expected_working_revision=0,
            key="release-stale-working",
        )
        self.assertEqual(stale_working.status_code, 409)
        self.assertEqual(
            stale_working.get_json()["error"],
            "WORKING_REVISION_STALE",
        )

        second = self._publish(
            version_label="1.1.0",
            expected_release_id=first_release_id,
            expected_working_revision=1,
            key="release-v2",
            changelog="Update one value and schema flag",
        )
        self.assertEqual(second.status_code, 201)
        second_payload = second.get_json()["release"]
        second_release_id = second_payload["id"]
        self.assertEqual(second_payload["parent_release_id"], first_release_id)
        self.assertEqual(second_payload["change_count"], 2)
        self.assertEqual(second_payload["modified_count"], 2)
        with self.app.app_context():
            self.assertEqual(
                DeckWorkingDirtyEntity.query.filter_by(
                    deck_item_id=self.deck_item_id
                ).count(),
                0,
            )
            self.assertEqual(
                DeckReleaseNoteCheckpoint.query.filter_by(
                    release_id=second_release_id
                ).count(),
                0,
            )

        filtered = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/"
            f"{second_release_id}/changes",
            query_string={"type": "modified", "limit": 1},
        )
        self.assertEqual(filtered.status_code, 200)
        filtered_payload = filtered.get_json()
        self.assertEqual(len(filtered_payload["items"]), 1)
        self.assertIsNotNone(filtered_payload["next_cursor"])
        self.assertEqual(filtered_payload["items"][0]["operation"], "set")

        schema_only = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/"
            f"{second_release_id}/changes",
            query_string={"entity_kind": "field_def"},
        )
        self.assertEqual(schema_only.status_code, 200)
        self.assertEqual(len(schema_only.get_json()["items"]), 1)
        self.assertEqual(schema_only.get_json()["items"][0]["property_key"], "required")
        self.assertEqual(schema_only.get_json()["items"][0]["field_name"], "Meaning")

        conflict_only = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/"
            f"{second_release_id}/changes",
            query_string={"type": "conflict"},
        )
        self.assertEqual(conflict_only.status_code, 200)
        self.assertEqual(conflict_only.get_json()["items"], [])

        history = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases",
            query_string={"limit": 1},
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json()["items"][0]["id"], second_release_id)
        self.assertIsNotNone(history.get_json()["next_cursor"])

        with self.app.app_context():
            self.assertEqual(
                deck_release_service.get_note_values_at_release(
                    first_release_id,
                    self.first_note_id,
                )["Word"],
                "犬",
            )
            self.assertEqual(
                deck_release_service.get_note_values_at_release(
                    second_release_id,
                    self.first_note_id,
                )["Word"],
                "犬 updated",
            )
            batch = deck_release_service.get_note_values_for_ids_at_release(
                second_release_id,
                [self.first_note_id, self.second_note_id],
            )
            self.assertEqual(batch[self.second_note_id]["Meaning"], "cat")
            field_defs = deck_release_service.get_field_defs_at_release(
                second_release_id
            )
            self.assertTrue(field_defs[self.meaning_field_id]["required"])
            collapsed = deck_release_service.get_atomic_changes_between_releases(
                from_release_or_id=first_release_id,
                to_release_or_id=second_release_id,
            )
            self.assertEqual(len(collapsed), 2)

    def test_published_history_is_visible_but_publish_stays_owner_only(self):
        first = self._publish(
            version_label="1.0.0",
            expected_release_id=None,
            expected_working_revision=0,
            key="release-public",
        )
        release_id = first.get_json()["release"]["id"]

        self._login("release-learner@example.com")
        history = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases"
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.get_json()["items"][0]["id"], release_id)
        changes = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/"
            f"{release_id}/changes"
        )
        self.assertEqual(changes.status_code, 200)

        publish = self._publish(
            version_label="2.0.0",
            expected_release_id=release_id,
            expected_working_revision=0,
            key="learner-cannot-publish",
        )
        self.assertEqual(publish.status_code, 404)

    def test_explicit_null_and_remove_are_distinguished_by_operation(self):
        first = self._publish(
            version_label="1.0.0",
            expected_release_id=None,
            expected_working_revision=0,
            key="null-remove-v1",
        )
        first_release_id = first.get_json()["release"]["id"]

        with self.app.app_context():
            note = db.session.get(Note, self.first_note_id)
            note.field_values = {**dict(note.field_values), "Word": None}
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            item.working_revision = 1
            db.session.commit()

        second = self._publish(
            version_label="1.1.0",
            expected_release_id=first_release_id,
            expected_working_revision=1,
            key="null-remove-v2",
        )
        second_release_id = second.get_json()["release"]["id"]
        second_changes = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/"
            f"{second_release_id}/changes",
            query_string={"entity_kind": "note_field"},
        ).get_json()["items"]
        self.assertEqual(len(second_changes), 1)
        self.assertEqual(second_changes[0]["operation"], "set")
        self.assertIsNone(second_changes[0]["after_value"])

        with self.app.app_context():
            values = deck_release_service.get_note_values_at_release(
                second_release_id,
                self.first_note_id,
            )
            self.assertIn("Word", values)
            self.assertIsNone(values["Word"])

            note = db.session.get(Note, self.first_note_id)
            next_values = dict(note.field_values)
            next_values.pop("Word")
            note.field_values = next_values
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            item.working_revision = 2
            db.session.commit()

        third = self._publish(
            version_label="1.2.0",
            expected_release_id=second_release_id,
            expected_working_revision=2,
            key="null-remove-v3",
        )
        third_release_id = third.get_json()["release"]["id"]
        third_changes = self.client.get(
            f"/api/marketplace/decks/{self.deck_item_id}/releases/"
            f"{third_release_id}/changes",
            query_string={"entity_kind": "note_field"},
        ).get_json()["items"]
        self.assertEqual(len(third_changes), 1)
        self.assertEqual(third_changes[0]["operation"], "remove")
        self.assertIsNone(third_changes[0]["after_value"])

        with self.app.app_context():
            values = deck_release_service.get_note_values_at_release(
                third_release_id,
                self.first_note_id,
            )
            self.assertNotIn("Word", values)

    def test_service_leaves_commit_and_rollback_to_caller(self):
        with self.app.app_context():
            result = deck_release_service.publish_release(
                deck_item_id=self.deck_item_id,
                user_id=self.owner_id,
                version_label="1.0.0",
                changelog="Transaction ownership",
                expected_current_release_id=None,
                expected_working_revision=0,
                idempotency_key="service-transaction",
            )
            self.assertFalse(result.replayed)
            self.assertEqual(
                DeckRelease.query.filter_by(deck_item_id=self.deck_item_id).count(),
                1,
            )
            db.session.rollback()
            self.assertEqual(
                DeckRelease.query.filter_by(deck_item_id=self.deck_item_id).count(),
                0,
            )
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            self.assertIsNone(item.current_release_id)

    def test_note_membership_history_survives_remove_and_readd(self):
        first = self._publish(
            version_label="1.0.0",
            expected_release_id=None,
            expected_working_revision=0,
            key="membership-v1",
        )
        first_release_id = first.get_json()["release"]["id"]

        with self.app.app_context():
            outside_deck = Deck(
                name="Outside release scope",
                owner_user_id=self.owner_id,
                note_type_id=self.note_type_id,
            )
            db.session.add(outside_deck)
            db.session.flush()
            note = db.session.get(Note, self.first_note_id)
            original_deck_id = note.deck_id
            note.deck_id = outside_deck.id
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            item.working_revision = 1
            db.session.commit()

        second = self._publish(
            version_label="1.1.0",
            expected_release_id=first_release_id,
            expected_working_revision=1,
            key="membership-v2",
        )
        second_release_id = second.get_json()["release"]["id"]

        with self.app.app_context():
            note = db.session.get(Note, self.first_note_id)
            note.deck_id = original_deck_id
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            item.working_revision = 2
            db.session.commit()

        third = self._publish(
            version_label="1.2.0",
            expected_release_id=second_release_id,
            expected_working_revision=2,
            key="membership-v3",
        )
        third_release_id = third.get_json()["release"]["id"]

        with self.app.app_context():
            self.assertIsNotNone(
                deck_release_service.get_note_values_at_release(
                    first_release_id,
                    self.first_note_id,
                )
            )
            self.assertIsNone(
                deck_release_service.get_note_values_at_release(
                    second_release_id,
                    self.first_note_id,
                )
            )
            self.assertIsNotNone(
                deck_release_service.get_note_values_at_release(
                    third_release_id,
                    self.first_note_id,
                )
            )
            memberships = DeckReleaseEntityMembership.query.filter_by(
                deck_item_id=self.deck_item_id,
                entity_kind="note",
                entity_id=self.first_note_id,
            ).order_by(DeckReleaseEntityMembership.introduced_sequence).all()
            self.assertEqual(len(memberships), 2)
            self.assertEqual(int(memberships[0].removed_sequence), 2)
            self.assertEqual(int(memberships[1].introduced_sequence), 3)
            self.assertIsNone(memberships[1].removed_sequence)

    def test_tracked_second_release_uses_sparse_note_reads(self):
        first = self._publish(
            version_label="1.0.0",
            expected_release_id=None,
            expected_working_revision=0,
            key="sparse-v1",
        )
        first_release_id = first.get_json()["release"]["id"]

        with self.app.app_context():
            note = db.session.get(Note, self.first_note_id)
            note.field_values = {
                **dict(note.field_values or {}),
                "Word": "tracked sparse update",
            }
            deck_working_tree_service.mark_note_fields_changed(
                note=note,
                field_names={"Word"},
            )
            db.session.commit()
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            self.assertEqual(int(item.working_revision), 1)
            self.assertEqual(int(item.dirty_tracking_revision), 1)

        with patch.object(
            deck_release_repository,
            "list_source_notes",
            side_effect=AssertionError("sparse release scanned the full note set"),
        ):
            preview = self.client.get(
                f"/api/marketplace/decks/{self.deck_item_id}/releases/preview"
            )
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.get_json()["summary"]["change_count"], 1)
            second = self._publish(
                version_label="1.1.0",
                expected_release_id=first_release_id,
                expected_working_revision=1,
                key="sparse-v2",
            )

        self.assertEqual(second.status_code, 201)
        second_release_id = second.get_json()["release"]["id"]
        self.assertEqual(second.get_json()["release"]["change_count"], 1)
        with self.app.app_context():
            values = deck_release_service.get_note_values_at_release(
                second_release_id,
                self.first_note_id,
            )
            self.assertEqual(values["Word"], "tracked sparse update")
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            self.assertEqual(
                int(item.dirty_tracking_revision),
                int(item.working_revision),
            )

    def test_untrusted_dirty_journal_falls_back_to_full_comparison(self):
        first = self._publish(
            version_label="1.0.0",
            expected_release_id=None,
            expected_working_revision=0,
            key="fallback-v1",
        )
        first_release_id = first.get_json()["release"]["id"]

        with self.app.app_context():
            # Simulate a mutation path that bumped the working revision without
            # journaling its field-level change (for example an older merge
            # worker), followed by a normally tracked owner edit.
            meaning_field = db.session.get(FieldDef, self.meaning_field_id)
            meaning_field.required = True
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            item.working_revision = 1
            note = db.session.get(Note, self.first_note_id)
            note.field_values = {
                **dict(note.field_values or {}),
                "Word": "tracked after journal gap",
            }
            deck_working_tree_service.mark_note_fields_changed(
                note=note,
                field_names={"Word"},
            )
            self.assertEqual(int(item.working_revision), 2)
            # A later tracked edit must not paper over the earlier journal gap.
            self.assertEqual(int(item.dirty_tracking_revision), 0)
            db.session.commit()

        with patch.object(
            deck_release_repository,
            "list_source_notes",
            wraps=deck_release_repository.list_source_notes,
        ) as full_scan:
            second = self._publish(
                version_label="1.1.0",
                expected_release_id=first_release_id,
                expected_working_revision=2,
                key="fallback-v2",
            )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.get_json()["release"]["change_count"], 2)
        self.assertGreaterEqual(full_scan.call_count, 1)

    def test_release_bootstrap_cli_is_dry_run_by_default_and_idempotent(self):
        runner = self.app.test_cli_runner()

        dry_run = runner.invoke(
            args=["deck-release-bootstrap", "--deck-item-id", self.deck_item_id]
        )
        self.assertEqual(dry_run.exit_code, 0, dry_run.output)
        self.assertIn("dry run", dry_run.output)
        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            self.assertIsNone(item.current_release_id)

        applied = runner.invoke(
            args=[
                "deck-release-bootstrap",
                "--deck-item-id",
                self.deck_item_id,
                "--apply",
            ]
        )
        self.assertEqual(applied.exit_code, 0, applied.output)
        self.assertIn("created=1", applied.output)
        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, self.deck_item_id)
            self.assertIsNotNone(item.current_release_id)
            self.assertEqual(item.current_release.version_label, "0.0.0")

        replay = runner.invoke(
            args=[
                "deck-release-bootstrap",
                "--deck-item-id",
                self.deck_item_id,
                "--apply",
            ]
        )
        self.assertEqual(replay.exit_code, 0, replay.output)
        self.assertIn("scanned=0", replay.output)


if __name__ == "__main__":
    unittest.main()
