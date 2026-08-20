"""Behavior tests for applying immutable releases to logical clone overlays."""

import unittest
from unittest.mock import patch

from sqlalchemy import event

from app import create_app
from app.services import deck_install_rebase_service, deck_release_service
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_install_rebase import DeckInstallRebase
from models.deck_install_rebase_conflict import DeckInstallRebaseConflict
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


class DeckInstallRebaseFlowTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        self.client = self.app.test_client()
        db.create_all()
        self.ids = self._seed_release_context()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _seed_release_context(self):
        owner = User(username="release-owner", email="release-owner@example.com")
        owner.set_password("password")
        learner = User(username="release-learner", email="release-learner@example.com")
        learner.set_password("password")
        db.session.add_all([owner, learner])
        db.session.flush()

        note_type = NoteType(user_id=owner.id, name="Release note type")
        db.session.add(note_type)
        db.session.flush()
        word_field = FieldDef(
            note_type_id=note_type.id,
            name="Word",
            field_type="text",
            position=0,
            required=True,
        )
        reading_field = FieldDef(
            note_type_id=note_type.id,
            name="Reading",
            field_type="text",
            position=1,
            required=False,
        )
        template = Template(
            note_type_id=note_type.id,
            name="Card",
            front_html="{{Word}}",
            back_html="{{Reading}}",
        )
        source_deck = Deck(
            owner_user_id=owner.id,
            note_type_id=note_type.id,
            name="Source deck",
        )
        local_deck = Deck(
            owner_user_id=learner.id,
            note_type_id=note_type.id,
            name="Local deck shell",
        )
        db.session.add_all([word_field, reading_field, template, source_deck, local_deck])
        db.session.flush()

        note = Note(
            note_type_id=note_type.id,
            user_id=owner.id,
            deck_id=source_deck.id,
            field_values={"Word": "dog", "Reading": "inu"},
            tags=[],
        )
        db.session.add(note)
        db.session.flush()
        card = Card(note_id=note.id, template_id=template.id)
        db.session.add(card)
        db.session.flush()
        progress = CardProgress(
            user_id=learner.id,
            card_id=card.id,
            queue="review",
            interval_days=12,
            reps=7,
            revision=9,
        )

        item = DeckMarketplaceItem(
            owner_user_id=owner.id,
            source_deck_id=source_deck.id,
            source_note_type_id=note_type.id,
            title="Versioned deck",
            description="",
            primary_category="General",
            tags=[],
            pricing_mode="free",
            publish_status="published",
        )
        db.session.add_all([progress, item])
        db.session.flush()
        first_release = DeckRelease(
            deck_item_id=item.id,
            sequence_no=1,
            version_label="1.0.0",
            status="published",
            created_by_user_id=owner.id,
            change_count=10,
        )
        second_release = DeckRelease(
            deck_item_id=item.id,
            sequence_no=2,
            version_label="1.1.0",
            status="published",
            created_by_user_id=owner.id,
            change_count=1,
        )
        db.session.add_all([first_release, second_release])
        db.session.flush()
        second_release.parent_release_id = first_release.id
        for field in (word_field, reading_field):
            properties = {
                "name": field.name,
                "field_type": field.field_type,
                "position": int(field.position or 0),
                "required": bool(field.required),
                "identity_role": field.identity_role,
            }
            for property_key, value in properties.items():
                db.session.add(
                    DeckReleaseChange(
                        release_id=first_release.id,
                        release_sequence_no=1,
                        change_key=f"field_def:{field.id}:{property_key}",
                        entity_kind="field_def",
                        entity_id=field.id,
                        field_def_id=field.id,
                        property_key=property_key,
                        operation="add",
                        before_value=None,
                        after_value=value,
                        source_deck_id=source_deck.id,
                        sort_key=f"field:{field.position}:{field.id}:{property_key}",
                    )
                )
            db.session.add(
                DeckReleaseEntityMembership(
                    deck_item_id=item.id,
                    entity_kind="field_def",
                    entity_id=field.id,
                    source_deck_id=source_deck.id,
                    introduced_sequence=1,
                    metadata_json={},
                )
            )
        db.session.add(
            DeckReleaseNoteCheckpoint(
                release_id=first_release.id,
                release_sequence_no=1,
                source_note_id=note.id,
                source_deck_id=source_deck.id,
                note_type_id=note_type.id,
                field_values={"Word": "dog", "Reading": "inu"},
                tags=[],
                content_hash="initial-checkpoint",
            )
        )
        db.session.add(
            DeckReleaseEntityMembership(
                deck_item_id=item.id,
                entity_kind="note",
                entity_id=note.id,
                source_deck_id=source_deck.id,
                introduced_sequence=1,
                metadata_json={"note_type_id": note_type.id},
            )
        )
        db.session.add(
            DeckReleaseChange(
                release_id=second_release.id,
                release_sequence_no=2,
                change_key=f"note_field:{note.id}:{word_field.id}",
                entity_kind="note_field",
                entity_id=note.id,
                field_def_id=word_field.id,
                property_key="Word",
                operation="set",
                before_value="dog",
                after_value="hound",
                source_deck_id=source_deck.id,
                sort_key=f"{note.id}:Word",
            )
        )
        install = DeckInstall(
            deck_item_id=item.id,
            user_id=learner.id,
            local_deck_id=local_deck.id,
            source_deck_id=source_deck.id,
            source_note_type_id=note_type.id,
            source_owner_user_id=owner.id,
            clone_mode="logical_overlay",
            applied_release_id=first_release.id,
            seen_release_id=first_release.id,
            overlay_revision=0,
            version_mode="release",
        )
        item.current_release_id = second_release.id
        db.session.add(install)
        db.session.commit()
        return {
            "learner_id": learner.id,
            "note_id": note.id,
            "card_id": card.id,
            "word_field_id": word_field.id,
            "reading_field_id": reading_field.id,
            "first_release_id": first_release.id,
            "second_release_id": second_release.id,
            "install_id": install.id,
        }

    def _add_overlay(self, *, field_name: str, field_def_id: str, value: str):
        install = db.session.get(DeckInstall, self.ids["install_id"])
        install.overlay_revision = int(install.overlay_revision or 0) + 1
        db.session.add(
            DeckCloneNoteFieldOverride(
                deck_install_id=install.id,
                source_note_id=self.ids["note_id"],
                source_field_def_id=field_def_id,
                base_release_id=self.ids["first_release_id"],
                field_name=field_name,
                operation="set",
                value=value,
            )
        )
        db.session.commit()

    def _login(self, email: str):
        self.client.delete("/api/session")
        response = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "password"},
        )
        self.assertEqual(response.status_code, 200)
        return self.client

    def test_apply_non_overlapping_update_keeps_overlay_and_progress(self):
        self._add_overlay(
            field_name="Reading",
            field_def_id=self.ids["reading_field_id"],
            value="いぬ",
        )
        install = db.session.get(DeckInstall, self.ids["install_id"])
        before_progress = db.session.get(
            CardProgress,
            CardProgress.query.filter_by(
                user_id=self.ids["learner_id"],
                card_id=self.ids["card_id"],
            ).first().id,
        )
        progress_snapshot = (
            before_progress.card_id,
            before_progress.interval_days,
            before_progress.reps,
            before_progress.revision,
        )

        rebase = deck_install_rebase_service.prepare_and_apply_update(
            install_id=install.id,
            release_id=self.ids["second_release_id"],
            user_id=self.ids["learner_id"],
            expected_applied_release_id=self.ids["first_release_id"],
            expected_overlay_revision=1,
            idempotency_key="apply-no-overlap",
        )
        db.session.commit()

        self.assertEqual(rebase.status, "applied")
        db.session.refresh(install)
        self.assertEqual(install.applied_release_id, self.ids["second_release_id"])
        self.assertEqual(install.seen_release_id, self.ids["second_release_id"])
        self.assertEqual(int(install.overlay_revision), 1)
        self.assertEqual(
            DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install.id).count(),
            1,
        )
        after_progress = CardProgress.query.filter_by(
            user_id=self.ids["learner_id"],
            card_id=self.ids["card_id"],
        ).one()
        self.assertEqual(
            (
                after_progress.card_id,
                after_progress.interval_days,
                after_progress.reps,
                after_progress.revision,
            ),
            progress_snapshot,
        )
        replay = deck_install_rebase_service.prepare_and_apply_update(
            install_id=install.id,
            release_id=self.ids["second_release_id"],
            user_id=self.ids["learner_id"],
            expected_applied_release_id=self.ids["first_release_id"],
            expected_overlay_revision=1,
            idempotency_key="apply-no-overlap",
        )
        self.assertEqual(replay.id, rebase.id)
        self.assertEqual(
            DeckInstallRebase.query.filter_by(deck_install_id=install.id).count(),
            1,
        )
        with self.assertRaises(deck_install_rebase_service.DeckInstallUpdateError) as reused:
            deck_install_rebase_service.prepare_and_apply_update(
                install_id=install.id,
                release_id=self.ids["second_release_id"],
                user_id=self.ids["learner_id"],
                expected_applied_release_id=self.ids["second_release_id"],
                expected_overlay_revision=1,
                idempotency_key="apply-no-overlap",
            )
        self.assertEqual(reused.exception.error, "IDEMPOTENCY_KEY_REUSED")

    def test_clone_reads_applied_release_instead_of_owner_working_values(self):
        from app.services import flashcards_share_service

        install = db.session.get(DeckInstall, self.ids["install_id"])
        note = db.session.get(Note, self.ids["note_id"])
        note.field_values = {"Word": "unpublished-owner-edit", "Reading": "inu"}
        db.session.commit()

        schema = flashcards_share_service.build_clone_schema_view(
            install=install,
            source_note_type_id=note.note_type_id,
        )
        pinned_values = flashcards_share_service.apply_clone_note_field_overrides(
            install=install,
            source_note=note,
            schema_view=schema,
        )
        self.assertEqual(pinned_values["Word"], "dog")

        install.applied_release_id = self.ids["second_release_id"]
        db.session.commit()
        updated_schema = flashcards_share_service.build_clone_schema_view(
            install=install,
            source_note_type_id=note.note_type_id,
        )
        updated_values = flashcards_share_service.apply_clone_note_field_overrides(
            install=install,
            source_note=note,
            schema_view=updated_schema,
        )
        self.assertEqual(updated_values["Word"], "hound")

    def test_clone_browse_search_uses_pinned_release_values(self):
        install = db.session.get(DeckInstall, self.ids["install_id"])
        note = db.session.get(Note, self.ids["note_id"])
        note.field_values = {
            "Word": "unpublished-owner-edit",
            "Reading": "inu",
        }
        db.session.commit()

        learner_client = self._login("release-learner@example.com")
        pinned_match = learner_client.get(
            "/api/browse/cards",
            query_string={
                "deck_id": install.local_deck_id,
                "q": "dog",
                "sort_by": "word",
            },
        )
        self.assertEqual(pinned_match.status_code, 200)
        self.assertEqual(pinned_match.get_json()["total"], 1)
        self.assertEqual(pinned_match.get_json()["items"][0]["word"], "dog")

        unpublished_match = learner_client.get(
            "/api/browse/cards",
            query_string={
                "deck_id": install.local_deck_id,
                "q": "unpublished-owner-edit",
                "sort_by": "word",
            },
        )
        self.assertEqual(unpublished_match.status_code, 200)
        self.assertEqual(unpublished_match.get_json()["total"], 0)

        self._add_overlay(
            field_name="Word",
            field_def_id=self.ids["word_field_id"],
            value="learner-only-word",
        )
        overlay_match = learner_client.get(
            "/api/browse/cards",
            query_string={
                "deck_id": install.local_deck_id,
                "q": "learner-only-word",
                "sort_by": "word",
            },
        )
        self.assertEqual(overlay_match.status_code, 200)
        self.assertEqual(overlay_match.get_json()["total"], 1)
        self.assertEqual(
            overlay_match.get_json()["items"][0]["word"],
            "learner-only-word",
        )
        pinned_hidden_by_overlay = learner_client.get(
            "/api/browse/cards",
            query_string={"deck_id": install.local_deck_id, "q": "dog"},
        )
        self.assertEqual(pinned_hidden_by_overlay.status_code, 200)
        self.assertEqual(pinned_hidden_by_overlay.get_json()["total"], 0)

    def test_clone_browse_word_sort_uses_pinned_release_values_before_pagination(self):
        install = db.session.get(DeckInstall, self.ids["install_id"])
        first_note = db.session.get(Note, self.ids["note_id"])
        first_card = db.session.get(Card, self.ids["card_id"])
        second_note = Note(
            note_type_id=first_note.note_type_id,
            user_id=first_note.user_id,
            deck_id=first_note.deck_id,
            field_values={"Word": "zebra", "Reading": "neko"},
            tags=[],
        )
        db.session.add(second_note)
        db.session.flush()
        second_card = Card(note_id=second_note.id, template_id=first_card.template_id)
        db.session.add(second_card)
        db.session.flush()

        first_release = db.session.get(DeckRelease, self.ids["first_release_id"])
        db.session.add_all(
            [
                DeckReleaseNoteCheckpoint(
                    release_id=first_release.id,
                    release_sequence_no=1,
                    source_note_id=second_note.id,
                    source_deck_id=second_note.deck_id,
                    note_type_id=second_note.note_type_id,
                    field_values={"Word": "cat", "Reading": "neko"},
                    tags=[],
                    content_hash="second-initial-checkpoint",
                ),
                DeckReleaseEntityMembership(
                    deck_item_id=install.deck_item_id,
                    entity_kind="note",
                    entity_id=second_note.id,
                    source_deck_id=second_note.deck_id,
                    introduced_sequence=1,
                    metadata_json={"note_type_id": second_note.note_type_id},
                ),
            ]
        )
        first_note.field_values = {"Word": "aardvark", "Reading": "inu"}
        db.session.commit()

        learner_client = self._login("release-learner@example.com")
        response = learner_client.get(
            "/api/browse/cards",
            query_string={
                "deck_id": install.local_deck_id,
                "sort_by": "word",
                "sort_dir": "asc",
                "page": 1,
                "per_page": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["items"][0]["word"], "cat")

    def test_conflict_keep_upstream_clears_only_overlapping_overlay(self):
        self._add_overlay(
            field_name="Word",
            field_def_id=self.ids["word_field_id"],
            value="puppy",
        )
        rebase = deck_install_rebase_service.prepare_update(
            install_id=self.ids["install_id"],
            release_id=self.ids["second_release_id"],
            user_id=self.ids["learner_id"],
            expected_applied_release_id=self.ids["first_release_id"],
            expected_overlay_revision=1,
            idempotency_key="prepare-conflict",
        )
        db.session.commit()

        self.assertEqual(rebase.status, "has_conflict")
        self.assertEqual(int(rebase.conflict_count), 1)
        conflict = rebase.conflicts[0]
        self.assertEqual(conflict.base_value, "dog")
        self.assertEqual(conflict.upstream_value, "hound")
        self.assertEqual(conflict.local_value, "puppy")

        rebase = deck_install_rebase_service.resolve_conflict(
            rebase_id=rebase.id,
            conflict_id=conflict.id,
            user_id=self.ids["learner_id"],
            resolution_mode="keep_upstream",
        )
        db.session.commit()
        self.assertEqual(rebase.status, "ready")

        rebase = deck_install_rebase_service.apply_prepared_update(
            rebase_id=rebase.id,
            user_id=self.ids["learner_id"],
        )
        db.session.commit()
        self.assertEqual(rebase.status, "applied")
        self.assertEqual(
            DeckCloneNoteFieldOverride.query.filter_by(
                deck_install_id=self.ids["install_id"]
            ).count(),
            0,
        )
        install = db.session.get(DeckInstall, self.ids["install_id"])
        self.assertEqual(install.applied_release_id, self.ids["second_release_id"])
        self.assertEqual(int(install.overlay_revision), 2)
        self.assertEqual(DeckInstallRebase.query.filter_by(status="applied").count(), 1)

    def test_field_rename_keeps_stable_local_note_override_visible(self):
        from app.services import flashcards_share_service

        item = db.session.get(
            DeckMarketplaceItem,
            db.session.get(DeckInstall, self.ids["install_id"]).deck_item_id,
        )
        third_release = DeckRelease(
            deck_item_id=item.id,
            sequence_no=3,
            version_label="1.2.0",
            parent_release_id=self.ids["second_release_id"],
            status="published",
            created_by_user_id=item.owner_user_id,
            change_count=1,
        )
        db.session.add(third_release)
        db.session.flush()
        db.session.add(
            DeckReleaseChange(
                release_id=third_release.id,
                release_sequence_no=3,
                change_key=f"field_def:{self.ids['word_field_id']}:name",
                entity_kind="field_def",
                entity_id=self.ids["word_field_id"],
                field_def_id=self.ids["word_field_id"],
                property_key="name",
                operation="set",
                before_value="Word",
                after_value="Term",
                source_deck_id=item.source_deck_id,
                sort_key=f"field:0:{self.ids['word_field_id']}:name",
            )
        )
        item.current_release_id = third_release.id
        install = db.session.get(DeckInstall, self.ids["install_id"])
        install.applied_release_id = self.ids["second_release_id"]
        install.seen_release_id = self.ids["second_release_id"]
        db.session.commit()

        self._add_overlay(
            field_name="Word",
            field_def_id=self.ids["word_field_id"],
            value="my local term",
        )
        install = db.session.get(DeckInstall, self.ids["install_id"])
        rebase = deck_install_rebase_service.prepare_and_apply_update(
            install_id=install.id,
            release_id=third_release.id,
            user_id=self.ids["learner_id"],
            expected_applied_release_id=self.ids["second_release_id"],
            expected_overlay_revision=1,
            idempotency_key="apply-field-rename",
        )
        db.session.commit()
        self.assertEqual(rebase.status, "applied")

        note = db.session.get(Note, self.ids["note_id"])
        schema = flashcards_share_service.build_clone_schema_view(
            install=install,
            source_note_type_id=note.note_type_id,
        )
        values = flashcards_share_service.apply_clone_note_field_overrides(
            install=install,
            source_note=note,
            schema_view=schema,
        )
        self.assertEqual(values.get("Term"), "my local term")
        self.assertNotIn("Word", values)

        learner_client = self._login("release-learner@example.com")
        overlay_match = learner_client.get(
            "/api/browse/cards",
            query_string={
                "deck_id": install.local_deck_id,
                "q": "my local term",
                "sort_by": "word",
            },
        )
        self.assertEqual(overlay_match.status_code, 200)
        self.assertEqual(overlay_match.get_json()["total"], 1)
        self.assertEqual(
            overlay_match.get_json()["items"][0]["word"],
            "my local term",
        )

        upstream_hidden_by_overlay = learner_client.get(
            "/api/browse/cards",
            query_string={"deck_id": install.local_deck_id, "q": "hound"},
        )
        self.assertEqual(upstream_hidden_by_overlay.status_code, 200)
        self.assertEqual(upstream_hidden_by_overlay.get_json()["total"], 0)

    def test_overlay_equal_to_base_is_not_a_conflict_and_is_compacted(self):
        self._add_overlay(
            field_name="Word",
            field_def_id=self.ids["word_field_id"],
            value="dog",
        )
        rebase = deck_install_rebase_service.prepare_and_apply_update(
            install_id=self.ids["install_id"],
            release_id=self.ids["second_release_id"],
            user_id=self.ids["learner_id"],
            expected_applied_release_id=self.ids["first_release_id"],
            expected_overlay_revision=1,
            idempotency_key="base-equivalent-overlay",
        )
        db.session.commit()

        self.assertEqual(rebase.status, "applied")
        self.assertEqual(int(rebase.conflict_count), 0)
        self.assertEqual(
            DeckCloneNoteFieldOverride.query.filter_by(
                deck_install_id=self.ids["install_id"]
            ).count(),
            0,
        )
        install = db.session.get(DeckInstall, self.ids["install_id"])
        self.assertEqual(int(install.overlay_revision), 2)
        self.assertEqual(install.applied_release_id, self.ids["second_release_id"])

    def test_update_routes_hide_other_users_install_and_validate_cursor(self):
        owner_client = self._login("release-owner@example.com")
        hidden = owner_client.get(
            f"/api/marketplace/installations/{self.ids['install_id']}/updates"
        )
        self.assertEqual(hidden.status_code, 404)

        hidden_apply = owner_client.post(
            f"/api/marketplace/installations/{self.ids['install_id']}/updates/"
            f"{self.ids['second_release_id']}/apply",
            json={"expected_overlay_revision": 0},
        )
        self.assertEqual(hidden_apply.status_code, 404)

        learner_client = self._login("release-learner@example.com")
        invalid_limit = learner_client.get(
            f"/api/marketplace/installations/{self.ids['install_id']}/updates/"
            f"{self.ids['second_release_id']}/diff",
            query_string={"limit": 0},
        )
        self.assertEqual(invalid_limit.status_code, 400)
        self.assertEqual(invalid_limit.get_json()["field"], "limit")

        # base64url("99:1") points outside this install's release range.
        invalid_cursor = learner_client.get(
            f"/api/marketplace/installations/{self.ids['install_id']}/updates/"
            f"{self.ids['second_release_id']}/diff",
            query_string={"cursor": "OTk6MQ"},
        )
        self.assertEqual(invalid_cursor.status_code, 400)
        self.assertEqual(invalid_cursor.get_json()["field"], "cursor")

        invalid_body = learner_client.post(
            f"/api/marketplace/installations/{self.ids['install_id']}/updates/"
            f"{self.ids['second_release_id']}/prepare",
            json=["not", "an", "object"],
        )
        self.assertEqual(invalid_body.status_code, 400)

    def test_skipped_release_summary_is_aggregated_without_full_range_load(self):
        install = db.session.get(DeckInstall, self.ids["install_id"])
        item = install.deck_item
        second_release = db.session.get(
            DeckRelease,
            self.ids["second_release_id"],
        )
        word_change_key = (
            f"note_field:{self.ids['note_id']}:{self.ids['word_field_id']}"
        )
        second_word_change = DeckReleaseChange.query.filter_by(
            release_id=second_release.id,
            change_key=word_change_key,
        ).one()
        second_word_change.before_hash = deck_release_service._hash_value("dog")
        second_word_change.after_hash = deck_release_service._hash_value("hound")
        second_release.change_count = 3
        second_release.entity_count = 2
        second_release.modified_count = 2
        second_release.added_count = 1
        transient_change_key = (
            f"note_field:transient-note:{self.ids['reading_field_id']}"
        )
        db.session.add_all(
            [
                DeckReleaseChange(
                    release_id=second_release.id,
                    release_sequence_no=2,
                    change_key=(
                        f"note_field:{self.ids['note_id']}:"
                        f"{self.ids['reading_field_id']}"
                    ),
                    entity_kind="note_field",
                    entity_id=self.ids["note_id"],
                    field_def_id=self.ids["reading_field_id"],
                    property_key=f"field:{self.ids['reading_field_id']}",
                    operation="set",
                    before_value="inu",
                    after_value="wan",
                    before_hash=deck_release_service._hash_value("inu"),
                    after_hash=deck_release_service._hash_value("wan"),
                    source_deck_id=item.source_deck_id,
                    sort_key=f"{self.ids['note_id']}:Reading",
                ),
                DeckReleaseChange(
                    release_id=second_release.id,
                    release_sequence_no=2,
                    change_key=transient_change_key,
                    entity_kind="note_field",
                    entity_id="transient-note",
                    field_def_id=self.ids["reading_field_id"],
                    property_key=f"field:{self.ids['reading_field_id']}",
                    operation="add",
                    before_value=None,
                    after_value="temporary",
                    before_hash=None,
                    after_hash=deck_release_service._hash_value("temporary"),
                    source_deck_id=item.source_deck_id,
                    sort_key="transient-note:Reading",
                ),
            ]
        )
        third_release = DeckRelease(
            deck_item_id=item.id,
            sequence_no=3,
            version_label="1.2.0",
            parent_release_id=self.ids["second_release_id"],
            status="published",
            created_by_user_id=item.owner_user_id,
            change_count=3,
            entity_count=3,
            modified_count=2,
            removed_count=1,
        )
        db.session.add(third_release)
        db.session.flush()
        db.session.add_all(
            [
                DeckReleaseChange(
                    release_id=third_release.id,
                    release_sequence_no=3,
                    change_key=word_change_key,
                    entity_kind="note_field",
                    entity_id=self.ids["note_id"],
                    field_def_id=self.ids["word_field_id"],
                    property_key=f"field:{self.ids['word_field_id']}",
                    operation="set",
                    before_value="hound",
                    after_value="dog",
                    before_hash=deck_release_service._hash_value("hound"),
                    after_hash=deck_release_service._hash_value("dog"),
                    source_deck_id=item.source_deck_id,
                    sort_key=f"{self.ids['note_id']}:Word",
                ),
                DeckReleaseChange(
                    release_id=third_release.id,
                    release_sequence_no=3,
                    change_key=transient_change_key,
                    entity_kind="note_field",
                    entity_id="transient-note",
                    field_def_id=self.ids["reading_field_id"],
                    property_key=f"field:{self.ids['reading_field_id']}",
                    operation="remove",
                    before_value="temporary",
                    after_value=None,
                    before_hash=deck_release_service._hash_value("temporary"),
                    after_hash=None,
                    source_deck_id=item.source_deck_id,
                    sort_key="transient-note:Reading",
                ),
                DeckReleaseChange(
                    release_id=third_release.id,
                    release_sequence_no=3,
                    change_key=(
                        f"field_def:{self.ids['reading_field_id']}:required"
                    ),
                    entity_kind="field_def",
                    entity_id=self.ids["reading_field_id"],
                    field_def_id=self.ids["reading_field_id"],
                    property_key="required",
                    operation="set",
                    before_value=False,
                    after_value=True,
                    before_hash=deck_release_service._hash_value(False),
                    after_hash=deck_release_service._hash_value(True),
                    source_deck_id=item.source_deck_id,
                    sort_key=f"field:{self.ids['reading_field_id']}:required",
                ),
            ]
        )
        item.current_release_id = third_release.id
        db.session.commit()

        with patch.object(
            deck_release_service,
            "get_atomic_changes_between_releases",
            side_effect=AssertionError("range summary loaded all change rows"),
        ):
            payload = deck_install_rebase_service.get_update_diff(
                install_id=install.id,
                release_id=third_release.id,
                user_id=self.ids["learner_id"],
                cursor=None,
                limit=1,
            )

        self.assertEqual(payload["summary_mode"], "effective")
        self.assertEqual(payload["summary"]["change_count"], 2)
        self.assertEqual(payload["summary"]["entity_count"], 2)
        self.assertEqual(payload["summary"]["modified_count"], 2)
        self.assertEqual(len(payload["items"]), 1)
        self.assertTrue(payload["page"]["has_more"])
        self.assertIsNotNone(payload["page"]["next_cursor"])

        next_page = deck_install_rebase_service.get_update_diff(
            install_id=install.id,
            release_id=third_release.id,
            user_id=self.ids["learner_id"],
            cursor=payload["page"]["next_cursor"],
            limit=1,
        )
        effective_keys = {
            payload["items"][0]["change_key"],
            next_page["items"][0]["change_key"],
        }
        self.assertEqual(len(effective_keys), 2)
        self.assertNotIn(transient_change_key, effective_keys)
        self.assertNotIn(word_change_key, effective_keys)
        self.assertFalse(next_page["page"]["has_more"])

        status = deck_install_rebase_service.get_update_status(
            install_id=install.id,
            user_id=self.ids["learner_id"],
        )
        self.assertEqual(status["change_count"], 2)
        rebase = deck_install_rebase_service.prepare_update(
            install_id=install.id,
            release_id=third_release.id,
            user_id=self.ids["learner_id"],
            expected_applied_release_id=self.ids["first_release_id"],
            expected_overlay_revision=0,
            idempotency_key="effective-range-count",
        )
        self.assertEqual(int(rebase.change_count), 2)

    def test_conflict_envelopes_are_keyset_paginated_and_bounded(self):
        rebase = DeckInstallRebase(
            deck_install_id=self.ids["install_id"],
            from_release_id=self.ids["first_release_id"],
            to_release_id=self.ids["second_release_id"],
            status="has_conflict",
            expected_overlay_revision=0,
            idempotency_key="bulk-conflict-page",
            change_count=1005,
            conflict_count=1005,
            resolved_conflict_count=0,
        )
        db.session.add(rebase)
        db.session.flush()
        db.session.bulk_save_objects(
            [
                DeckInstallRebaseConflict(
                    rebase_id=rebase.id,
                    conflict_key=f"note_field:bulk-note:{index}",
                    entity_kind="note_field",
                    entity_id="bulk-note",
                    field_def_id=self.ids["word_field_id"],
                    property_key=f"field:{self.ids['word_field_id']}",
                    base_value=f"base-{index}",
                    upstream_value=f"upstream-{index}",
                    local_value=f"local-{index}",
                )
                for index in range(1005)
            ]
        )
        db.session.commit()
        rebase_id = rebase.id
        rebase = db.session.get(DeckInstallRebase, rebase_id)

        conflict_selects: list[str] = []

        def capture_conflict_select(
            _conn,
            _cursor,
            statement,
            _parameters,
            _context,
            _executemany,
        ):
            normalized = str(statement).strip().lower()
            if normalized.startswith("select") and "deck_install_rebase_conflicts" in normalized:
                conflict_selects.append(normalized)

        event.listen(db.engine, "before_cursor_execute", capture_conflict_select)
        try:
            payload = deck_install_rebase_service.serialize_rebase(rebase)
        finally:
            event.remove(db.engine, "before_cursor_execute", capture_conflict_select)

        self.assertEqual(len(payload["conflicts"]), 100)
        self.assertTrue(payload["conflict_page"]["has_more"])
        self.assertIsNotNone(payload["conflict_page"]["next_after_id"])
        self.assertEqual(len(conflict_selects), 1)
        self.assertIn("limit", conflict_selects[0])

        learner_client = self._login("release-learner@example.com")
        prepared = learner_client.post(
            f"/api/marketplace/installations/{self.ids['install_id']}/updates/"
            f"{self.ids['second_release_id']}/prepare",
            headers={"Idempotency-Key": "bulk-conflict-page"},
            json={
                "expected_applied_release_id": self.ids["first_release_id"],
                "expected_overlay_revision": 0,
            },
        )
        self.assertEqual(prepared.status_code, 200)
        prepared_rebase = prepared.get_json()["rebase"]
        self.assertEqual(len(prepared_rebase["conflicts"]), 100)
        self.assertTrue(prepared_rebase["conflict_page"]["has_more"])

        resolved = learner_client.post(
            f"/api/marketplace/rebases/{rebase_id}/conflicts/"
            f"{payload['conflicts'][0]['id']}/resolve",
            json={"resolution_mode": "keep_upstream"},
        )
        self.assertEqual(resolved.status_code, 200)
        resolved_rebase = resolved.get_json()["rebase"]
        self.assertEqual(resolved_rebase["resolved_conflict_count"], 1)
        self.assertNotIn("conflicts", resolved_rebase)
        self.assertNotIn("conflict_page", resolved_rebase)

        second_page = learner_client.get(
            f"/api/marketplace/rebases/{rebase_id}/conflicts",
            query_string={
                "after_id": payload["conflict_page"]["next_after_id"],
                "limit": 100,
            },
        )
        self.assertEqual(second_page.status_code, 200)
        second_payload = second_page.get_json()
        self.assertEqual(len(second_payload["items"]), 100)
        self.assertGreater(
            second_payload["items"][0]["id"],
            payload["conflicts"][-1]["id"],
        )
        self.assertTrue(second_payload["page"]["has_more"])

        invalid_limit = learner_client.get(
            f"/api/marketplace/rebases/{rebase_id}/conflicts",
            query_string={"limit": 201},
        )
        self.assertEqual(invalid_limit.status_code, 400)
        self.assertEqual(invalid_limit.get_json()["field"], "limit")

        with self.assertRaises(
            deck_install_rebase_service.DeckInstallUpdateError
        ) as unresolved:
            deck_install_rebase_service.apply_prepared_update(
                rebase_id=rebase_id,
                user_id=self.ids["learner_id"],
            )
        error_rebase = unresolved.exception.details["rebase"]
        self.assertEqual(len(error_rebase["conflicts"]), 100)
        self.assertTrue(error_rebase["conflict_page"]["has_more"])

        owner_client = self._login("release-owner@example.com")
        hidden = owner_client.get(
            f"/api/marketplace/rebases/{rebase_id}/conflicts"
        )
        self.assertEqual(hidden.status_code, 404)

    def test_overlap_query_uses_exists_for_more_than_one_thousand_overlays(self):
        install = db.session.get(DeckInstall, self.ids["install_id"])
        source_note = db.session.get(Note, self.ids["note_id"])
        dummy_note_ids = [f"bulk-note-{index:04d}" for index in range(1005)]
        db.session.bulk_save_objects(
            [
                Note(
                    id=note_id,
                    note_type_id=source_note.note_type_id,
                    user_id=source_note.user_id,
                    deck_id=source_note.deck_id,
                    field_values={"Word": f"word-{index}"},
                    tags=[],
                )
                for index, note_id in enumerate(dummy_note_ids)
            ]
        )
        db.session.commit()
        db.session.bulk_save_objects(
            [
                DeckCloneNoteFieldOverride(
                    id=f"bulk-override-{index:04d}",
                    deck_install_id=install.id,
                    source_note_id=note_id,
                    source_field_def_id=self.ids["word_field_id"],
                    base_release_id=self.ids["first_release_id"],
                    field_name="Word",
                    operation="set",
                    value=f"local-{index}",
                )
                for index, note_id in enumerate(dummy_note_ids)
            ]
            + [
                DeckCloneNoteFieldOverride(
                    id="bulk-override-matching",
                    deck_install_id=install.id,
                    source_note_id=self.ids["note_id"],
                    source_field_def_id=self.ids["word_field_id"],
                    base_release_id=self.ids["first_release_id"],
                    field_name="Word",
                    operation="set",
                    value="my dog",
                )
            ]
        )
        db.session.commit()

        release_change_queries: list[tuple[str, object]] = []

        def capture_release_change_query(
            _conn,
            _cursor,
            statement,
            parameters,
            _context,
            _executemany,
        ):
            normalized = str(statement).strip().lower()
            if normalized.startswith("select") and "from deck_release_changes" in normalized:
                release_change_queries.append((normalized, parameters))

        event.listen(db.engine, "before_cursor_execute", capture_release_change_query)
        try:
            collapsed, _local_state = deck_install_rebase_service._overlapping_changes(
                install,
                db.session.get(DeckRelease, self.ids["second_release_id"]),
            )
        finally:
            event.remove(
                db.engine,
                "before_cursor_execute",
                capture_release_change_query,
            )

        self.assertEqual(len(collapsed), 1)
        self.assertEqual(len(release_change_queries), 1)
        statement, parameters = release_change_queries[0]
        self.assertIn("exists", statement)
        self.assertIn("deck_clone_note_field_overrides", statement)
        self.assertLess(len(parameters), 20)


if __name__ == "__main__":
    unittest.main()
