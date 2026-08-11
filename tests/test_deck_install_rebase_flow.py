"""Behavior tests for applying immutable releases to logical clone overlays."""

import unittest

from app import create_app
from app.services import deck_install_rebase_service
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_install_rebase import DeckInstallRebase
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


if __name__ == "__main__":
    unittest.main()
