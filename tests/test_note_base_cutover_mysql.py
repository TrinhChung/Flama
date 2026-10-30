"""D6 and expansion rehearsal against a disposable real MySQL database."""
from copy import deepcopy
from datetime import datetime
import importlib
import json

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from models import db
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.deck_working_dirty_entity import DeckWorkingDirtyEntity
from models.field_def import FieldDef
from models.note import Note
from models.note_draft import NoteDraft
from models.note_type import NoteType
from models.deck_install import DeckInstall
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from scripts.note_base_cutover import (
    _json_default, apply_manifest, build_manifest, checksum, manifest_checksum, rollback_manifest,
    manual_draft_review,
)
from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import create_note_user


class NoteBaseCutoverMySQLTests(NoteBaseMySQLTestCase):
    def seed(self):
        owner = create_note_user(db.session, username="cutover-owner", email="cutover@example.test")
        note_type = NoteType(user_id=owner.id, name="cutover-type")
        db.session.add(note_type)
        db.session.flush()
        word = FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0)
        meanings = FieldDef(note_type_id=note_type.id, name="Meanings", field_type="array", position=1)
        deck = Deck(name="cutover-root", owner_user_id=owner.id, note_type_id=note_type.id)
        db.session.add_all([word, meanings, deck])
        db.session.flush()
        note = Note(note_type_id=note_type.id, user_id=owner.id, deck_id=deck.id,
                    field_values={"Word": "manual current", "Meanings": ["native", ["array"]]}, tags=["keep"])
        unpublished = Note(note_type_id=note_type.id, user_id=owner.id, deck_id=deck.id,
                           field_values={"Word": "never published"})
        item = DeckMarketplaceItem(owner_user_id=owner.id, source_deck_id=deck.id,
                                   source_note_type_id=note_type.id, title="cutover", publish_status="published")
        db.session.add_all([note, unpublished, item])
        db.session.flush()
        release = DeckRelease(deck_item_id=item.id, sequence_no=1, version_label="legacy-1",
                              status="published", published_at=datetime(2026, 10, 10), created_by_user_id=owner.id)
        db.session.add(release)
        db.session.flush()
        item.current_release_id = release.id
        for kind, identity in (("note", note.id), ("field_def", word.id), ("field_def", meanings.id)):
            db.session.add(DeckReleaseEntityMembership(deck_item_id=item.id, entity_kind=kind,
                    entity_id=identity, introduced_sequence=1, source_deck_id=deck.id,
                    metadata_json={"note_type_id": note_type.id}))
        db.session.add(DeckReleaseNoteCheckpoint(release_id=release.id,
                source_note_id=note.id, release_sequence_no=1, source_deck_id=deck.id,
                note_type_id=note_type.id, field_values={"Word": "old published", "Meanings": "$legacy"}, tags=["keep"],
                content_hash=checksum({"Word": "old published", "Meanings": "$legacy"})))
        for field in (word, meanings):
            for key, value in dict(name=field.name, field_type=field.field_type, position=field.position,
                                   required=False, identity_role=None).items():
                db.session.add(DeckReleaseChange(release_id=release.id, release_sequence_no=1,
                    change_key=f"field:{field.id}:{key}", entity_kind="field_def", entity_id=field.id,
                    field_def_id=field.id, property_key=key, operation="add", after_value=value,
                    sort_key=f"field:{field.id}:{key}"))
        for field, when in ((word, datetime(2026, 10, 16)), (meanings, datetime(2026, 10, 23, 12, 2))):
            db.session.add(DeckWorkingDirtyEntity(deck_item_id=item.id, entity_kind="note_field", entity_id=note.id,
                field_def_id=field.id, property_key=f"field:{field.id}", operation="set",
                source_deck_id=deck.id, metadata_json={"field_name": field.name}, updated_at=when))
        db.session.commit()
        return dict(note=note.id, unpublished=unpublished.id, item=item.id, release=release.id,
                    word=word.id, meanings=meanings.id)

    def test_mysql_expansion_backfills_only_frozen_membership_and_schema(self):
        ids = self.seed()
        db.session.remove()
        revision = importlib.import_module("migrations.versions.20261029_000076_note_published_base")
        with db.engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE note_drafts")
            connection.exec_driver_sql("ALTER TABLE notes DROP COLUMN published_at, DROP COLUMN deleted_at")
            connection.exec_driver_sql("ALTER TABLE field_defs DROP COLUMN deleted_at")
            connection.exec_driver_sql("ALTER TABLE deck_marketplace_items DROP COLUMN published_schema_json")
            connection.exec_driver_sql("ALTER TABLE deck_clone_note_field_overrides DROP COLUMN base_hash")
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                revision.upgrade()
            rows = dict(connection.execute(sa.text("SELECT id,published_at FROM notes")).all())
            self.assertEqual(rows[ids["note"]], datetime(2026, 10, 10))
            self.assertIsNone(rows[ids["unpublished"]])
            schema = connection.execute(sa.select(DeckMarketplaceItem.published_schema_json)).scalar_one()
            self.assertEqual(schema[ids["word"]]["name"], "Word")
            self.assertEqual(schema[ids["meanings"]]["field_type"], "array")
            indexes = connection.execute(sa.text(
                "SELECT INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='note_drafts'"
            )).scalars().all()
            self.assertEqual(indexes, ["PRIMARY"])
            connection.execute(sa.update(Note.__table__).where(Note.id == ids["note"]).values(published_at=None))
            connection.execute(sa.update(DeckMarketplaceItem.__table__).where(
                DeckMarketplaceItem.id == ids["item"]).values(published_schema_json=sa.null()))
            with Operations.context(context):
                revision.upgrade()  # Complete a simulated interruption after DDL.
            self.assertIsNotNone(connection.execute(sa.select(Note.published_at).where(Note.id == ids["note"])).scalar_one())
            connection.execute(sa.update(DeckMarketplaceItem.__table__).where(
                DeckMarketplaceItem.id == ids["item"]).values(published_schema_json={"keep": "current snapshot"}))
            with Operations.context(context):
                revision.upgrade()
            self.assertEqual(connection.execute(sa.select(DeckMarketplaceItem.published_schema_json)).scalar_one(),
                             {"keep": "current snapshot"})

    def test_cutover_preserves_manual_draft_and_current_script_base_then_rolls_back(self):
        ids = self.seed()
        manifest = build_manifest(db.session)
        before_values = deepcopy(db.session.get(Note, ids["note"]).field_values_by_id)
        self.assertEqual(manifest["classification"], {"script_fields": 1, "manual_fields": 1})
        review = manual_draft_review(manifest)
        self.assertEqual(review["manifest_sha256"], manifest["sha256"])
        self.assertEqual(review["manual_notes"], 1)
        self.assertEqual(review["notes"][0]["fields"][0]["published_base"], "old published")
        self.assertEqual(review["notes"][0]["fields"][0]["author_draft"], "manual current")
        receipt = apply_manifest(db.session, manifest, approved_sha256=manifest["sha256"],
                                 backup_reference="disposable-rehearsal-only", writers_stopped=True)
        db.session.commit()
        db.session.expire_all()
        note = db.session.get(Note, ids["note"])
        draft = db.session.get(NoteDraft, note.id)
        self.assertEqual(note.field_values_by_id[ids["word"]], "old published")
        self.assertEqual(note.field_values_by_id[ids["meanings"]], ["native", ["array"]])
        self.assertEqual(draft.field_values_by_id[ids["word"]], {"op": "set", "value": "manual current"})
        self.assertIsNone(db.session.get(Note, ids["unpublished"]).published_at)
        self.assertNotEqual(db.session.get(DeckMarketplaceItem, ids["item"]).current_release_id, ids["release"])
        from deploy.check_field_code_rollback import check_field_code_rollback
        from pathlib import Path
        self.assertEqual(check_field_code_rollback(db.engine)["error"], "NOTE_BASE_CODE_ROLLBACK_UNSUPPORTED")
        self.assertTrue(check_field_code_rollback(db.engine, previous_release=Path(__file__).resolve().parents[1])["ok"])
        rollback_manifest(db.session, manifest, receipt, backup_reference="disposable-rehearsal-only", writers_stopped=True)
        db.session.commit()
        db.session.expire_all()
        self.assertEqual(db.session.get(Note, ids["note"]).field_values_by_id, before_values)
        self.assertEqual(db.session.get(DeckMarketplaceItem, ids["item"]).current_release_id, ids["release"])
        self.assertIsNone(db.session.get(NoteDraft, ids["note"]))
        self.assertEqual(DeckRelease.query.count(), 1)

    def test_manifest_roundtrip_and_stale_note_are_fail_closed(self):
        ids = self.seed()
        manifest = json.loads(json.dumps(build_manifest(db.session), default=_json_default))
        self.assertEqual(manifest_checksum(manifest), manifest["sha256"])
        db.session.connection().execute(sa.update(Note.__table__).where(Note.id == ids["note"]).values(tags=["changed"]))
        with self.assertRaisesRegex(RuntimeError, "Note changed since review"):
            apply_manifest(db.session, manifest, approved_sha256=manifest["sha256"],
                           backup_reference="test", writers_stopped=True)
        db.session.rollback()

    def _personal_override(self, ids):
        learner = create_note_user(db.session, username="cutover-learner", email="cutover-learner@example.invalid")
        item = db.session.get(DeckMarketplaceItem, ids["item"])
        install = DeckInstall(deck_item_id=item.id, user_id=learner.id, clone_mode="logical_overlay",
            source_deck_id=item.source_deck_id, source_note_type_id=item.source_note_type_id,
            source_owner_user_id=item.owner_user_id, applied_release_id=ids["release"])
        db.session.add(install)
        db.session.flush()
        row = DeckCloneNoteFieldOverride(deck_install_id=install.id, source_note_id=ids["note"],
            field_identity_key=ids["word"], field_name="Word", source_field_def_id=ids["word"],
            operation="set", value="personal", base_release_id=ids["release"])
        db.session.add(row)
        db.session.commit()
        return install, row

    def test_existing_personal_override_hash_backfill_and_rollback_preserve_edits(self):
        from app.services.note_base_comparison_service import base_value_hash
        ids = self.seed()
        install, row = self._personal_override(ids)
        row_id, original_time = row.id, row.updated_at
        manifest = build_manifest(db.session)
        self.assertEqual(manual_draft_review(manifest)["personal_overrides"]["base_hash_backfills"], 1)
        for edit_during_soak in (False, True):
            receipt = apply_manifest(db.session, manifest, approved_sha256=manifest["sha256"],
                backup_reference="disposable-rehearsal", writers_stopped=True)
            db.session.commit()
            row = db.session.get(DeckCloneNoteFieldOverride, row_id)
            self.assertEqual(row.base_hash, base_value_hash("old published", exists=True))
            self.assertEqual(row.value, "personal")
            self.assertEqual(row.updated_at, original_time)
            if edit_during_soak:
                row.value = "personal after cutover"
                db.session.commit()
            rollback_manifest(db.session, manifest, receipt, backup_reference="disposable-rehearsal", writers_stopped=True)
            db.session.commit()
            db.session.expire_all()
            row = db.session.get(DeckCloneNoteFieldOverride, row_id)
            self.assertEqual(row.value, "personal after cutover" if edit_during_soak else "personal")
            self.assertEqual(row.base_hash, base_value_hash("old published", exists=True) if edit_during_soak else None)

    def test_cutover_refuses_personal_or_install_changes_since_review(self):
        ids = self.seed()
        install, row = self._personal_override(ids)
        manifest = build_manifest(db.session)
        row.value = "new personal edit"
        db.session.commit()
        with self.assertRaisesRegex(RuntimeError, "Personal override changed"):
            apply_manifest(db.session, manifest, approved_sha256=manifest["sha256"],
                backup_reference="test", writers_stopped=True)
        db.session.rollback()
        manifest = build_manifest(db.session)
        install.auto_update_enabled = not bool(install.auto_update_enabled)
        db.session.commit()
        with self.assertRaisesRegex(RuntimeError, "Install changed"):
            apply_manifest(db.session, manifest, approved_sha256=manifest["sha256"],
                backup_reference="test", writers_stopped=True)
        db.session.rollback()
        self.assertEqual(NoteDraft.query.count(), 0)

    def test_exact_script_receipt_wins_over_unknown_timestamp(self):
        ids = self.seed()
        manifest = build_manifest(db.session, script_receipts=[(ids["note"], ids["word"])])
        self.assertEqual(manifest["classification"]["manual_fields"], 0)
        self.assertFalse(manifest["notes"][0]["delta"])

    def test_schema_drift_without_listing_revision_is_rejected(self):
        ids = self.seed()
        manifest = build_manifest(db.session)
        db.session.connection().execute(sa.update(FieldDef.__table__).where(
            FieldDef.id == ids["word"]).values(name="Renamed after review"))
        with self.assertRaisesRegex(RuntimeError, "Schema changed since review"):
            apply_manifest(db.session, manifest, approved_sha256=manifest["sha256"],
                backup_reference="test", writers_stopped=True)
        db.session.rollback()
        self.assertEqual(NoteDraft.query.count(), 0)

    def test_apply_requires_review_checksum_backup_and_stopped_writers(self):
        self.seed()
        manifest = build_manifest(db.session)
        for options in ({"approved_sha256": "wrong", "backup_reference": "test", "writers_stopped": True},
                        {"approved_sha256": manifest["sha256"], "backup_reference": "", "writers_stopped": True},
                        {"approved_sha256": manifest["sha256"], "backup_reference": "test", "writers_stopped": False}):
            with self.assertRaises(RuntimeError):
                apply_manifest(db.session, manifest, **options)
        self.assertEqual(NoteDraft.query.count(), 0)

    def test_rollback_refuses_after_first_new_publish(self):
        ids = self.seed()
        manifest = build_manifest(db.session)
        receipt = apply_manifest(db.session, manifest, approved_sha256=manifest["sha256"], backup_reference="test", writers_stopped=True)
        db.session.commit()
        db.session.connection().execute(sa.update(DeckMarketplaceItem.__table__).where(
            DeckMarketplaceItem.id == ids["item"]).values(current_release_id=ids["release"]))
        with self.assertRaisesRegex(RuntimeError, "publish occurred"):
            rollback_manifest(db.session, manifest, receipt, backup_reference="test", writers_stopped=True)
        db.session.rollback()

    def test_rollback_preserves_new_install_using_the_runtime_release_default(self):
        from models.deck_clone_deck_map import DeckCloneDeckMap
        from models.deck_clone_added_note import DeckCloneAddedNote
        ids = self.seed()
        manifest = build_manifest(db.session)
        receipt = apply_manifest(db.session, manifest, approved_sha256=manifest["sha256"],
            backup_reference="disposable", writers_stopped=True)
        db.session.commit()
        learner = create_note_user(db.session, username="new-soak-learner", email="new-soak@example.invalid")
        item = db.session.get(DeckMarketplaceItem, ids["item"])
        local = Deck(name="Private folder", owner_user_id=learner.id, note_type_id=item.source_note_type_id)
        db.session.add(local)
        db.session.flush()
        install = DeckInstall(deck_item_id=item.id, user_id=learner.id, local_deck_id=local.id,
            clone_mode="logical_overlay", source_deck_id=item.source_deck_id,
            source_note_type_id=item.source_note_type_id, source_owner_user_id=item.owner_user_id,
            applied_release_id=item.current_release_id, seen_release_id=item.current_release_id,
            version_mode="release")  # share/install.py's actual current constructor
        db.session.add(install)
        db.session.flush()
        mapping = DeckCloneDeckMap(deck_install_id=install.id, source_deck_id=item.source_deck_id, local_deck_id=local.id)
        note = Note(user_id=learner.id, note_type_id=item.source_note_type_id, deck_id=local.id,
            field_values={"Word": "personal local note"})
        db.session.add_all([mapping, note])
        db.session.flush()
        db.session.add(DeckCloneAddedNote(deck_install_id=install.id, note_id=note.id))
        db.session.commit()
        install_id, local_id, note_id = install.id, local.id, note.id
        rollback_manifest(db.session, manifest, receipt, backup_reference="disposable", writers_stopped=True)
        db.session.commit()
        db.session.expire_all()
        install = db.session.get(DeckInstall, install_id)
        self.assertEqual(install.applied_release_id, ids["release"])
        self.assertEqual(install.seen_release_id, ids["release"])
        self.assertEqual(install.local_deck_id, local_id)
        self.assertEqual(db.session.get(Note, note_id).field_values["Word"], "personal local note")
        self.assertEqual(DeckCloneDeckMap.query.filter_by(deck_install_id=install_id).count(), 1)
        self.assertEqual(DeckCloneAddedNote.query.filter_by(deck_install_id=install_id).count(), 1)

    def test_rollback_preserves_latest_soak_draft_and_rebuilds_dirty_evidence(self):
        ids = self.seed()
        manifest = build_manifest(db.session)
        receipt = apply_manifest(db.session, manifest, approved_sha256=manifest["sha256"], backup_reference="test", writers_stopped=True)
        db.session.commit()
        db.session.connection().execute(sa.update(NoteDraft.__table__).where(NoteDraft.note_id == ids["note"]).values(
            field_values_by_id={ids["word"]: {"op": "set", "value": "edited during soak"}}, tags=["latest tag"]))
        db.session.commit()
        rollback_manifest(db.session, manifest, receipt, backup_reference="test", writers_stopped=True)
        db.session.commit()
        db.session.expire_all()
        note = db.session.get(Note, ids["note"])
        self.assertEqual(note.field_values_by_id[ids["word"]], "edited during soak")
        self.assertEqual(note.tags, ["latest tag"])
        dirty = DeckWorkingDirtyEntity.query.filter_by(entity_id=ids["note"], field_def_id=ids["word"]).one()
        self.assertEqual(dirty.current_hash, checksum("edited during soak"))
        self.assertEqual(db.session.get(DeckMarketplaceItem, ids["item"]).dirty_tracking_revision, -1)

    def test_backfill_hides_schema_when_all_fields_are_removed(self):
        ids = self.seed()
        revision = importlib.import_module("migrations.versions.20261029_000076_note_published_base")
        connection = db.session.connection()
        connection.execute(sa.update(DeckReleaseEntityMembership.__table__).where(
            DeckReleaseEntityMembership.deck_item_id == ids["item"],
            DeckReleaseEntityMembership.entity_kind == "field_def").values(removed_sequence=1))
        revision.backfill_current_release(connection, notes=False, schema=True)
        schema = connection.execute(sa.select(DeckMarketplaceItem.published_schema_json).where(
            DeckMarketplaceItem.id == ids["item"])).scalar_one()
        self.assertEqual(schema, {})

    def test_draft_fk_cascades_without_secondary_indexes(self):
        ids = self.seed()
        connection = db.session.connection()
        connection.execute(sa.insert(NoteDraft.__table__).values(note_id=ids["note"],
            field_values_by_id={ids["word"]: {"op": "set", "value": None}}, op="edit", updated_at=datetime.utcnow()))
        connection.execute(sa.delete(Note.__table__).where(Note.id == ids["note"]))
        self.assertIsNone(connection.execute(sa.select(NoteDraft.note_id)).first())
