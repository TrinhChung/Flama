"""Focused coverage for owner note mutations that feed sparse deck releases."""

from __future__ import annotations

import io
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from werkzeug.datastructures import FileStorage

from app import create_app
from app.services import (
    anki_content_normalizer,
    browse_voicevox_service,
    deck_working_tree_service,
    flashcard_media_api_service,
    mcp_tool_service,
    note_sync_service,
    study_card_editor_service,
    study_service,
    tts_provider_service,
)
from app.services.anki_scheduler import _day_index
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_working_dirty_entity import DeckWorkingDirtyEntity
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


_MIN_WAV_BYTES = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


class OwnerNoteDirtyTrackingServiceTests(unittest.TestCase):
    def setUp(self):
        self.upload_tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": self.upload_tmp.name,
                "FLASHCARD_MEDIA_MAX_BYTES": 1024 * 1024,
            }
        )

        with self.app.app_context():
            db.create_all()
            owner = User(username="dirty-owner", email="dirty-owner@example.com")
            owner.set_password("password")
            learner = User(username="dirty-learner", email="dirty-learner@example.com")
            learner.set_password("password")
            db.session.add_all([owner, learner])
            db.session.flush()
            self.owner_id = owner.id
            self.learner_id = learner.id

            note_type = NoteType(user_id=owner.id, name="Tracked vocabulary")
            db.session.add(note_type)
            db.session.flush()
            fields = [
                FieldDef(
                    note_type_id=note_type.id,
                    name="Word",
                    field_type="text",
                    position=0,
                    required=True,
                    identity_role="primary",
                ),
                FieldDef(
                    note_type_id=note_type.id,
                    name="Meaning",
                    field_type="text",
                    position=1,
                    required=True,
                ),
                FieldDef(
                    note_type_id=note_type.id,
                    name="Sound",
                    field_type="audio",
                    position=2,
                    required=False,
                ),
            ]
            template = Template(
                note_type_id=note_type.id,
                name="Recognition",
                front_html="{{Word}}",
                back_html="{{Meaning}}{{Sound}}",
                position=0,
            )
            db.session.add_all([*fields, template])

            root_deck = Deck(
                name="Tracked root",
                owner_user_id=owner.id,
                note_type_id=note_type.id,
            )
            other_deck = Deck(
                name="Owner scratch deck",
                owner_user_id=owner.id,
                note_type_id=note_type.id,
            )
            db.session.add_all([root_deck, other_deck])
            db.session.flush()

            first_note = Note(
                note_type_id=note_type.id,
                user_id=owner.id,
                deck_id=root_deck.id,
                field_values={"Word": "犬", "Meaning": "dog", "Sound": ""},
                tags=["animal"],
            )
            second_note = Note(
                note_type_id=note_type.id,
                user_id=owner.id,
                deck_id=root_deck.id,
                field_values={"Word": "猫", "Meaning": "cat", "Sound": ""},
                tags=[],
            )
            db.session.add_all([first_note, second_note])
            db.session.flush()
            first_card = Card(note_id=first_note.id, template_id=template.id)
            second_card = Card(note_id=second_note.id, template_id=template.id)
            db.session.add_all([first_card, second_card])

            item = DeckMarketplaceItem(
                owner_user_id=owner.id,
                source_deck_id=root_deck.id,
                source_note_type_id=note_type.id,
                title="Tracked shared deck",
                description="fixture",
                primary_category="Vocabulary",
                tags=[],
                pricing_mode="free",
                version="1.0.0",
                publish_status="published",
                working_revision=0,
                dirty_tracking_revision=0,
            )
            db.session.add(item)
            db.session.flush()
            release = DeckRelease(
                deck_item_id=item.id,
                sequence_no=1,
                version_label="1.0.0",
                status="published",
                source_working_revision=0,
                manifest_hash="a" * 64,
                created_by_user_id=owner.id,
            )
            db.session.add(release)
            db.session.flush()
            item.current_release_id = release.id
            db.session.add(
                DeckReleaseEntityMembership(
                    deck_item_id=item.id,
                    entity_kind="note",
                    entity_id=str(first_note.id),
                    source_deck_id=root_deck.id,
                    introduced_sequence=1,
                    removed_sequence=None,
                    metadata_json={},
                )
            )

            source_ref = ConnectSourceNoteRef(
                user_id=owner.id,
                source_key="sheet",
                external_note_id="existing",
                source_model_id=str(note_type.id),
                source_deck_path="Tracked root",
                note_id=first_note.id,
                content_hash=note_sync_service.compute_note_content_hash(
                    field_values=first_note.field_values,
                    tags=first_note.tags,
                    deck_id=first_note.deck_id,
                ),
            )
            db.session.add(source_ref)
            db.session.commit()

            self.note_type_id = note_type.id
            self.root_deck_id = root_deck.id
            self.other_deck_id = other_deck.id
            self.item_id = item.id
            self.first_note_id = first_note.id
            self.second_note_id = second_note.id
            self.first_card_id = first_card.id
            self.second_card_id = second_card.id
            self.sound_field_id = fields[2].id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.upload_tmp.cleanup()

    def _item(self) -> DeckMarketplaceItem:
        return db.session.get(DeckMarketplaceItem, self.item_id)

    def _dirty_rows(self) -> list[DeckWorkingDirtyEntity]:
        return (
            DeckWorkingDirtyEntity.query.filter_by(deck_item_id=self.item_id)
            .order_by(DeckWorkingDirtyEntity.entity_id, DeckWorkingDirtyEntity.property_key)
            .all()
        )

    def test_study_edit_tracks_fields_rejects_released_tags_and_keeps_clone_source_safe(self):
        with self.app.app_context():
            result = study_card_editor_service.update_study_card_note(
                user_id=self.owner_id,
                card_id=self.first_card_id,
                payload={"field_values": {"Meaning": "hound"}},
                render_result=False,
            )
            self.assertEqual(result["field_values"]["Meaning"], "hound")
            self.assertEqual(int(self._item().working_revision), 1)
            self.assertEqual(int(self._item().dirty_tracking_revision), 1)
            dirty = self._dirty_rows()
            self.assertEqual(len(dirty), 1)
            self.assertEqual(dirty[0].entity_id, self.first_note_id)
            self.assertEqual(dirty[0].metadata_json["field_name"], "Meaning")
            self.assertIsNotNone(dirty[0].current_hash)

            with self.assertRaises(study_card_editor_service.StudyCardEditError) as raised:
                study_card_editor_service.update_study_card_note(
                    user_id=self.owner_id,
                    card_id=self.first_card_id,
                    payload={"tags": ["changed"]},
                    render_result=False,
                )
            self.assertEqual(raised.exception.status, 409)
            self.assertEqual(
                raised.exception.code,
                "SHARED_NOTE_METADATA_VERSIONING_REQUIRED",
            )
            self.assertEqual(db.session.get(Note, self.first_note_id).tags, ["animal"])

            with self.assertRaises(study_card_editor_service.StudyCardEditError) as moved:
                study_card_editor_service.update_study_card_note(
                    user_id=self.owner_id,
                    card_id=self.first_card_id,
                    payload={"deck_id": self.other_deck_id},
                    render_result=False,
                )
            self.assertEqual(moved.exception.status, 409)
            self.assertEqual(moved.exception.field, "deck_id")
            self.assertEqual(moved.exception.code, "SHARED_ENTITY_RETIRE_REQUIRED")
            self.assertEqual(
                db.session.get(Note, self.first_note_id).deck_id,
                self.root_deck_id,
            )
            self.assertEqual(int(self._item().working_revision), 1)

            with self.assertRaises(study_card_editor_service.StudyCardEditError) as clone_edit:
                study_card_editor_service.update_study_card_note(
                    user_id=self.learner_id,
                    card_id=self.first_card_id,
                    payload={"field_values": {"Meaning": "must not leak"}},
                    render_result=False,
                )
            self.assertEqual(clone_edit.exception.status, 404)
            self.assertEqual(
                db.session.get(Note, self.first_note_id).field_values["Meaning"],
                "hound",
            )

    def test_media_batch_and_delete_track_one_sparse_revision_per_transaction(self):
        with self.app.app_context():
            result = flashcard_media_api_service.upload_media_batch(
                user_id=self.owner_id,
                items=[
                    {
                        "item_id": "first",
                        "note_id": self.first_note_id,
                        "field_name": "Sound",
                        "uploaded": FileStorage(
                            stream=io.BytesIO(_MIN_WAV_BYTES),
                            filename="first.wav",
                            content_type="audio/wav",
                        ),
                    },
                    {
                        "item_id": "second",
                        "note_id": self.second_note_id,
                        "field_name": "Sound",
                        "uploaded": FileStorage(
                            stream=io.BytesIO(_MIN_WAV_BYTES),
                            filename="second.wav",
                            content_type="audio/wav",
                        ),
                    },
                ],
                upload_root=Path(self.upload_tmp.name),
                max_bytes=1024 * 1024,
            )
            self.assertEqual(result["success_count"], 2)
            self.assertEqual(int(self._item().working_revision), 1)
            dirty = self._dirty_rows()
            self.assertEqual(len(dirty), 2)
            self.assertEqual({row.field_def_id for row in dirty}, {self.sound_field_id})
            self.assertTrue(all(row.current_hash for row in dirty))

            first_asset_id = str(result["items"][0]["asset_id"])
            flashcard_media_api_service.delete_media(
                user_id=self.owner_id,
                asset_id=first_asset_id,
                upload_root=Path(self.upload_tmp.name),
            )
            self.assertEqual(int(self._item().working_revision), 2)
            first_note = db.session.get(Note, self.first_note_id)
            self.assertEqual(first_note.field_values["Sound"], "")
            first_dirty = DeckWorkingDirtyEntity.query.filter_by(
                deck_item_id=self.item_id,
                entity_id=self.first_note_id,
                field_def_id=self.sound_field_id,
            ).one()
            self.assertEqual(int(first_dirty.working_revision), 2)
            self.assertIsNotNone(first_dirty.current_hash)
            self.assertIsNone(db.session.get(MediaAsset, first_asset_id))

    def test_voicevox_tracks_all_generated_notes_in_one_revision(self):
        synthesized = tts_provider_service.SynthesizedAudioResult(
            content=_MIN_WAV_BYTES,
            mime_type="audio/wav",
            extension="wav",
            content_type_header="audio/wav",
        )
        with self.app.app_context(), patch.object(
            browse_voicevox_service,
            "_active_voicevox_provider",
            return_value=object(),
        ), patch.object(
            browse_voicevox_service.tts_provider_service,
            "synthesize_voicevox_audio_for_user",
            return_value=(synthesized, [], []),
        ):
            result = browse_voicevox_service.generate_voicevox(
                user_id=self.owner_id,
                admin_mode=False,
                payload={
                    "card_ids": [self.first_card_id, self.second_card_id],
                    "source_field": "Word",
                    "destination_field": "Sound",
                    "character_id": "speaker-1",
                },
                upload_root=Path(self.upload_tmp.name),
            )
            self.assertEqual(result["generated_count"], 2)
            self.assertEqual(int(self._item().working_revision), 1)
            dirty = self._dirty_rows()
            self.assertEqual(len(dirty), 2)
            self.assertEqual({row.field_def_id for row in dirty}, {self.sound_field_id})

    def test_note_sync_tracks_create_and_update_with_fixed_creation_tags(self):
        with self.app.app_context():
            result = note_sync_service.execute_sync_notes(
                user_id=self.owner_id,
                source_key="sheet",
                deck_id=self.root_deck_id,
                note_type_id=self.note_type_id,
                notes=[
                    {
                        "external_id": "existing",
                        "fields": {"Word": "犬", "Meaning": "hound", "Sound": ""},
                        "tags": ["animal"],
                    },
                    {
                        "external_id": "new-fixed-tags",
                        "fields": {"Word": "鳥", "Meaning": "bird", "Sound": ""},
                        "tags": ["fixed-at-create"],
                    },
                ],
            )
            self.assertEqual(result["summary"]["updated"], 1)
            self.assertEqual(result["summary"]["created"], 1)
            self.assertEqual(int(self._item().working_revision), 1)
            created = Note.query.join(
                ConnectSourceNoteRef,
                ConnectSourceNoteRef.note_id == Note.id,
            ).filter(
                ConnectSourceNoteRef.external_note_id == "new-fixed-tags"
            ).one()
            self.assertEqual(created.tags, ["fixed-at-create"])
            self.assertTrue(self._dirty_rows())

    def test_note_sync_rolls_back_pending_writes_on_late_tag_conflict(self):
        with self.app.app_context():
            with self.assertRaises(RequestValidationError) as raised:
                note_sync_service.execute_sync_notes(
                    user_id=self.owner_id,
                    source_key="sheet",
                    deck_id=self.root_deck_id,
                    note_type_id=self.note_type_id,
                    notes=[
                        {
                            "external_id": "pending-before-conflict",
                            "fields": {"Word": "魚", "Meaning": "fish", "Sound": ""},
                            "tags": ["fixed-at-create"],
                        },
                        {
                            "external_id": "existing",
                            "fields": {"Word": "犬", "Meaning": "dog", "Sound": ""},
                            "tags": ["changed-after-release"],
                        },
                    ],
                )
            self.assertEqual(raised.exception.status, 409)
            self.assertEqual(
                raised.exception.code,
                "SHARED_NOTE_METADATA_VERSIONING_REQUIRED",
            )
            self.assertIsNone(
                ConnectSourceNoteRef.query.filter_by(
                    external_note_id="pending-before-conflict"
                ).first()
            )
            self.assertEqual(Note.query.count(), 2)
            self.assertEqual(db.session.get(Note, self.first_note_id).tags, ["animal"])
            self.assertEqual(int(self._item().working_revision), 0)
            self.assertEqual(self._dirty_rows(), [])

    def test_note_sync_blocks_released_move_but_allows_post_release_note_move(self):
        with self.app.app_context():
            with self.assertRaises(RequestValidationError) as raised:
                note_sync_service.execute_sync_notes(
                    user_id=self.owner_id,
                    source_key="sheet",
                    deck_id=self.root_deck_id,
                    note_type_id=self.note_type_id,
                    notes=[
                        {
                            "external_id": "pending-before-move-conflict",
                            "fields": {
                                "Word": "new pending",
                                "Meaning": "must roll back",
                                "Sound": "",
                            },
                            "tags": ["fixed-at-create"],
                        },
                        {
                            "external_id": "existing",
                            "deck_id": self.other_deck_id,
                            "fields": {
                                "Word": "existing",
                                "Meaning": "dog",
                                "Sound": "",
                            },
                            "tags": ["animal"],
                        },
                    ],
                )
            self.assertEqual(raised.exception.status, 409)
            self.assertEqual(raised.exception.field, "deck_id")
            self.assertEqual(raised.exception.code, "SHARED_ENTITY_RETIRE_REQUIRED")
            self.assertIsNone(
                ConnectSourceNoteRef.query.filter_by(
                    external_note_id="pending-before-move-conflict"
                ).first()
            )
            released_note = db.session.get(Note, self.first_note_id)
            self.assertEqual(released_note.deck_id, self.root_deck_id)
            self.assertNotEqual(released_note.field_values["Word"], "existing")
            self.assertEqual(int(self._item().working_revision), 0)
            self.assertEqual(self._dirty_rows(), [])

            created_result = note_sync_service.execute_sync_notes(
                user_id=self.owner_id,
                source_key="sheet",
                deck_id=self.root_deck_id,
                note_type_id=self.note_type_id,
                notes=[
                    {
                        "external_id": "post-release-note",
                        "fields": {
                            "Word": "post release",
                            "Meaning": "new working note",
                            "Sound": "",
                        },
                        "tags": ["fixed-at-create"],
                    }
                ],
            )
            self.assertEqual(created_result["summary"]["created"], 1)

            moved_result = note_sync_service.execute_sync_notes(
                user_id=self.owner_id,
                source_key="sheet",
                deck_id=self.other_deck_id,
                note_type_id=self.note_type_id,
                notes=[
                    {
                        "external_id": "post-release-note",
                        "fields": {
                            "Word": "post release",
                            "Meaning": "new working note",
                            "Sound": "",
                        },
                        "tags": ["fixed-at-create"],
                    }
                ],
            )
            self.assertEqual(moved_result["summary"]["updated"], 1)
            moved_note = Note.query.join(
                ConnectSourceNoteRef,
                ConnectSourceNoteRef.note_id == Note.id,
            ).filter(
                ConnectSourceNoteRef.external_note_id == "post-release-note"
            ).one()
            self.assertEqual(moved_note.deck_id, self.other_deck_id)

    def test_anki_backfill_marks_only_changed_fields_before_caller_commit(self):
        with self.app.app_context():
            note = db.session.get(Note, self.first_note_id)
            note.field_values = {
                **dict(note.field_values or {}),
                "Meaning": "It&#x27;s tracked",
            }
            db.session.commit()

            result = anki_content_normalizer.backfill_anki_note_entities(
                deck_id=self.root_deck_id,
            )
            db.session.commit()

            self.assertEqual((result.scanned, result.changed), (1, 1))
            self.assertEqual(
                db.session.get(Note, self.first_note_id).field_values["Meaning"],
                "It's tracked",
            )
            self.assertEqual(int(self._item().working_revision), 1)
            dirty = self._dirty_rows()
            self.assertEqual(len(dirty), 1)
            self.assertEqual(dirty[0].metadata_json["field_name"], "Meaning")
            self.assertIsNotNone(dirty[0].current_hash)

    def test_batch_tracking_keeps_one_revision_and_forces_legacy_fallback(self):
        with self.app.app_context():
            note = db.session.get(Note, self.first_note_id)
            note.field_values = {
                **dict(note.field_values or {}),
                "Meaning": "tracked value",
                "LegacyOnly": "requires full diff",
            }

            tracked = deck_working_tree_service.mark_note_field_batches_changed(
                mutations=[
                    {
                        "note": note,
                        "field_names": {"Meaning", "LegacyOnly"},
                        "operation": "set",
                    }
                ]
            )
            db.session.flush()

            self.assertEqual(tracked, 1)
            self.assertEqual(int(self._item().working_revision), 1)
            self.assertEqual(int(self._item().dirty_tracking_revision), 0)
            dirty = self._dirty_rows()
            self.assertEqual(len(dirty), 1)
            self.assertEqual(dirty[0].metadata_json["field_name"], "Meaning")

    def test_mcp_delete_preview_is_read_only_until_confirmed(self):
        with self.app.app_context():
            preview = mcp_tool_service.delete_note(
                user_id=self.owner_id,
                note_id=self.second_note_id,
                confirm=False,
            )
            self.assertTrue(preview["requires_confirmation"])
            self.assertEqual(int(self._item().working_revision), 0)
            self.assertEqual(self._dirty_rows(), [])
            self.assertIsNotNone(db.session.get(Note, self.second_note_id))

            deleted = mcp_tool_service.delete_note(
                user_id=self.owner_id,
                note_id=self.second_note_id,
                confirm=True,
            )
            self.assertTrue(deleted["success"])
            self.assertEqual(int(self._item().working_revision), 1)
            self.assertTrue(self._dirty_rows())
            self.assertIsNone(db.session.get(Note, self.second_note_id))

    def test_legacy_study_keeps_leech_state_without_mutating_released_tags(self):
        with self.app.app_context(), patch.object(
            study_service,
            "record_review_event",
            return_value=SimpleNamespace(id=None),
        ), patch.object(
            study_service.flashcards_share_service,
            "touch_note_type_install_usage",
        ), patch.object(
            study_service.flashcards_share_service,
            "touch_deck_install_usage",
        ), patch.object(
            study_service,
            "_append_audit",
        ):
            user = db.session.get(User, self.owner_id)
            now = datetime.utcnow()

            for card_id, note_id, expected_tags in (
                (self.first_card_id, self.first_note_id, ["animal"]),
                (self.second_card_id, self.second_note_id, ["leech"]),
            ):
                progress = CardProgress(
                    user_id=self.owner_id,
                    card_id=card_id,
                    queue="review",
                    due_at=now,
                    due_day=_day_index(now, 4),
                    interval_days=5,
                    ease_factor=2.5,
                    lapses=7,
                    revision=0,
                )
                db.session.add(progress)
                db.session.commit()
                result = study_service.execute_native_review_command(
                    user=user,
                    card=db.session.get(Card, card_id),
                    now=now,
                    action="again",
                    payload={},
                    clone_scope=None,
                    requested_scope_id=self.root_deck_id,
                    timezone_name="UTC",
                )
                self.assertTrue(result.transition.state.leeched)

                stored_progress = CardProgress.query.filter_by(
                    user_id=self.owner_id,
                    card_id=card_id,
                ).one()
                self.assertTrue(stored_progress.is_suspended)
                self.assertEqual(int(stored_progress.lapses), 8)
                self.assertEqual(db.session.get(Note, note_id).tags, expected_tags)

    def test_study_session_keeps_leech_state_without_mutating_released_tags(self):
        now = datetime.utcnow()
        with self.app.app_context():
            db.session.add(
                CardProgress(
                    user_id=self.owner_id,
                    card_id=self.first_card_id,
                    queue="review",
                    due_at=now,
                    due_day=_day_index(now, 4),
                    interval_days=5,
                    ease_factor=2.5,
                    lapses=7,
                    revision=0,
                )
            )
            db.session.commit()

        client = self.app.test_client()
        login = client.post(
            "/login",
            data={"email": "dirty-owner@example.com", "password": "password"},
            follow_redirects=True,
        )
        self.assertEqual(login.status_code, 200)
        opened = client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": self.root_deck_id},
        )
        self.assertEqual(opened.status_code, 201, opened.get_json())
        snapshot = opened.get_json()
        card_payload = next(
            card
            for card in snapshot["cards"]
            if card["card_id"] == self.first_card_id
        )
        committed = client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit",
            json={
                "schema_version": "study-commit.v1",
                "commit_id": str(uuid4()),
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": [
                    {
                        "event_id": str(uuid4()),
                        "sequence": 1,
                        "card_id": self.first_card_id,
                        "rating": "again",
                        "policy_key": card_payload["policy_key"],
                        "scheduler_offset_ms": 1000,
                        "duration_ms": 500,
                    }
                ],
                "final_states": [],
            },
        )
        self.assertEqual(committed.status_code, 200, committed.get_json())

        with self.app.app_context():
            self.assertEqual(db.session.get(Note, self.first_note_id).tags, ["animal"])
            progress = CardProgress.query.filter_by(
                user_id=self.owner_id,
                card_id=self.first_card_id,
            ).one()
            self.assertTrue(progress.is_suspended)
            self.assertEqual(int(progress.lapses), 8)


if __name__ == "__main__":
    unittest.main()
