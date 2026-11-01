import unittest

from app import create_app
from app.services.flashcard_media_normalizer import (
    backfill_media_field_values,
    rollback_media_field_migration,
)
from models import db
from models.deck import Deck
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.media_field_migration import MediaFieldMigrationItem, MediaFieldMigrationRun
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from tests.study_note_fixtures import attach_template, create_note_user


class FlashcardMediaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        user = create_note_user(db.session, username="media_migration", email="media-migration@example.com")
        user.set_password("password")
        deck = Deck(name="Media migration", owner_user_id=user.id)
        note_type = NoteType(user_id=user.id, name="Media migration type")
        db.session.add_all([deck, note_type])
        db.session.flush()
        db.session.add_all([
            FieldDef(note_type_id=note_type.id, name="Picture", field_type="image", position=0),
            FieldDef(note_type_id=note_type.id, name="Diagram", field_type="diagram", position=1),
            FieldDef(note_type_id=note_type.id, name="Audio", field_type="audio", position=2),
            FieldDef(note_type_id=note_type.id, name="MissingAudio", field_type="audio", position=3),
            FieldDef(note_type_id=note_type.id, name="WrongAudio", field_type="audio", position=4),
        ])
        note = Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={
                "Picture": '<img src="https://cdn.example.com/picture.png">',
                "Diagram": "null",
                "Audio": "[sound:voice.wav]",
                "MissingAudio": "missing.mp3",
                "WrongAudio": '<img src="https://cdn.example.com/wrong.png">',
            },
        )
        db.session.add(note)
        db.session.flush()
        db.session.add(MediaAsset(
            note_id=note.id,
            field_name="Audio",
            filename="voice.wav",
            mime_type="audio/wav",
            storage_path="test/voice.wav",
            sha256="a" * 64,
            size_bytes=1,
        ))
        template = attach_template(
            db.session,
            owner_user_id=user.id,
            note_type_id=note_type.id,
            name="Card",
            front_html='<audio src="{{Audio}}"></audio>{{Picture}}',
            back_html="{{Diagram}}",
            input_schema=[
                {"key": "Picture", "type": "image"},
                {"key": "Diagram", "type": "diagram"},
                {"key": "Audio", "type": "audio"},
                {"key": "MissingAudio", "type": "audio"},
                {"key": "WrongAudio", "type": "audio"},
            ],
        )
        db.session.commit()
        self.deck_id = deck.id
        self.note_id = note.id
        self.template_id = template.id
        self.user_id = user.id
        self.note_type_id = note_type.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_rollback_uses_stable_field_after_rename_and_keeps_audit_bytes(self):
        before = dict(db.session.get(Note, self.note_id).field_values)
        applied = backfill_media_field_values(deck_id=self.deck_id, apply=True, include_overlays=False,
            include_templates=False)
        db.session.commit()
        audit = MediaFieldMigrationItem.query.filter_by(run_id=applied.run_id, entity_type="note", field_name="Picture").one()
        archived = (audit.field_name, audit.old_value, audit.new_value)
        field = FieldDef.query.filter_by(note_type_id=self.note_type_id, name="Picture").one()
        field.name = "Renamed picture"
        db.session.commit()
        result = rollback_media_field_migration(run_id=applied.run_id, apply=True)
        db.session.commit()
        self.assertGreater(result.restored, 0)
        note = db.session.get(Note, self.note_id)
        self.assertEqual(note.field_values["Renamed picture"], before["Picture"])
        self.assertNotIn("Picture", note.field_values)
        self.assertEqual(archived, (audit.field_name, audit.old_value, audit.new_value))

    def test_rollback_refuses_deleted_field_and_same_name_replacement(self):
        from app.services.field_value_identity_service import FieldIdentityConflict
        applied = backfill_media_field_values(deck_id=self.deck_id, apply=True, include_overlays=False,
            include_templates=False)
        db.session.commit()
        field = FieldDef.query.filter_by(note_type_id=self.note_type_id, name="Picture").one()
        db.session.delete(field)
        db.session.flush()
        replacement = FieldDef(note_type_id=self.note_type_id, name="Picture", field_type="image")
        db.session.add(replacement)
        db.session.commit()
        note = db.session.get(Note, self.note_id)
        before = dict(note.field_values_by_id)
        with self.assertRaises(FieldIdentityConflict):
            rollback_media_field_migration(run_id=applied.run_id, apply=True)
        db.session.rollback()
        self.assertEqual(note.field_values_by_id, before)

    def test_rollback_does_not_coerce_a_new_empty_array_into_audited_empty_text(self):
        applied = backfill_media_field_values(deck_id=self.deck_id, apply=True, include_overlays=False,
            include_templates=False)
        db.session.commit()
        note = db.session.get(Note, self.note_id)
        values = dict(note.field_values)
        values["Diagram"] = []
        note.field_values = values
        db.session.commit()
        result = rollback_media_field_migration(run_id=applied.run_id, apply=True)
        db.session.commit()
        self.assertGreaterEqual(result.skipped_changed_since, 1)
        self.assertEqual(note.field_values["Diagram"], [])

    def test_dry_run_apply_audit_idempotency_and_safe_rollback(self):
        original_values = dict(db.session.get(Note, self.note_id).field_values)
        dry_run = backfill_media_field_values(
            deck_id=self.deck_id,
            apply=False,
            include_overlays=False,
        )
        self.assertEqual(dry_run.normalized, 2)
        self.assertEqual(dry_run.cleared, 2)
        self.assertEqual(dry_run.quarantined, 1)
        self.assertEqual(db.session.get(Note, self.note_id).field_values, original_values)
        self.assertEqual(MediaFieldMigrationRun.query.count(), 0)

        applied = backfill_media_field_values(
            deck_id=self.deck_id,
            apply=True,
            include_overlays=False,
        )
        db.session.commit()
        self.assertIsNotNone(applied.run_id)
        values = dict(db.session.get(Note, self.note_id).field_values)
        self.assertEqual(values["Picture"], "https://cdn.example.com/picture.png")
        self.assertEqual(values["Diagram"], "")
        self.assertTrue(values["Audio"].startswith("/store/"))
        self.assertEqual(values["MissingAudio"], "missing.mp3")
        self.assertEqual(values["WrongAudio"], "")
        self.assertIn(
            'src="{{Audio_url}}"',
            db.session.get(Template, self.template_id).front_html,
        )
        self.assertEqual(
            MediaFieldMigrationItem.query.filter_by(run_id=applied.run_id).count(),
            6,
        )

        second = backfill_media_field_values(
            deck_id=self.deck_id,
            apply=False,
            include_overlays=False,
        )
        self.assertEqual(second.changed, 0)
        self.assertEqual(second.quarantined, 1)

        rollback = rollback_media_field_migration(run_id=applied.run_id, apply=False)
        self.assertEqual(rollback.restorable, 5)
        self.assertEqual(rollback.restored, 5)
        self.assertEqual(rollback.skipped_changed_since, 0)

    def test_active_clone_override_is_migrated_without_mutating_source_note(self):
        learner = create_note_user(db.session, username="media_learner", email="media-learner@example.com")
        learner.set_password("password")
        clone_deck = Deck(name="Installed media deck", owner_user_id=learner.id)
        item = DeckMarketplaceItem(
            owner_user_id=self.user_id,
            source_deck_id=self.deck_id,
            source_note_type_id=self.note_type_id,
            title="Media item",
        )
        db.session.add_all([clone_deck, item])
        db.session.flush()
        install = DeckInstall(
            deck_item_id=item.id,
            user_id=learner.id,
            local_deck_id=clone_deck.id,
            source_deck_id=self.deck_id,
            source_note_type_id=self.note_type_id,
            source_owner_user_id=self.user_id,
            clone_mode="logical_overlay",
        )
        db.session.add(install)
        db.session.flush()
        picture_def = FieldDef.query.filter_by(
            note_type_id=self.note_type_id,
            name="Picture",
        ).one()
        override = DeckCloneNoteFieldOverride(
            deck_install_id=install.id,
            source_note_id=self.note_id,
            source_field_def_id=picture_def.id,
            field_name="Picture",
            operation="set",
            value='<img src="https://cdn.example.com/clone.png">',
        )
        db.session.add(override)
        db.session.commit()
        source_before = dict(db.session.get(Note, self.note_id).field_values)

        result = backfill_media_field_values(
            deck_id=clone_deck.id,
            apply=True,
            include_templates=False,
        )
        db.session.commit()

        self.assertEqual(result.overlays_changed, 1)
        self.assertEqual(
            db.session.get(DeckCloneNoteFieldOverride, override.id).value,
            "https://cdn.example.com/clone.png",
        )
        self.assertEqual(db.session.get(Note, self.note_id).field_values, source_before)
        self.assertEqual(
            MediaFieldMigrationItem.query.filter_by(
                run_id=result.run_id,
                entity_type="clone_override",
            ).count(),
            1,
        )


if __name__ == "__main__":
    unittest.main()
