"""Opt-in concurrency regressions on existing loopback MySQL; never run DDL.

Only UUID-tagged synthetic users/schema fixtures are committed for cross-thread
visibility. Cleanup deletes exactly those fixtures. Worker writes use the real
service transaction; no source notes or production accounts are touched.
"""

from concurrent.futures import ThreadPoolExecutor
import os
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import create_audit_app
from app.services import note_type_release_service
from app.services.share import helpers, note_types
from models import db
from models.field_def import FieldDef
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.user import User


@unittest.skipUnless(os.getenv("FLAMA_MYSQL_TESTS") == "1", "requires opt-in loopback MySQL")
class NoteTypeInstallLockingMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_audit_app({"TESTING": True, "REDIS_URL": ""})
        with cls.app.app_context():
            if db.engine.dialect.name != "mysql" or db.engine.url.host not in {"localhost", "127.0.0.1", "::1"}:
                raise RuntimeError("Install locking regressions require loopback MySQL")

    def setUp(self):
        context = self.app.app_context()
        context.push()
        self.addCleanup(context.pop)
        self.user_ids = []
        self.addCleanup(self._cleanup)
        self.token = uuid4().hex
        users = [User(username=f"install-lock-{self.token}-{i}", email=f"{self.token}-{i}@example.invalid",
            is_disabled=True) for i in range(3)]
        db.session.add_all(users)
        db.session.flush()
        self.user_ids = [user.id for user in users]
        source = NoteType(user_id=users[0].id, name="Install lock source", publish_status="published")
        db.session.add(source)
        db.session.flush()
        db.session.add(FieldDef(note_type_id=source.id, name="Word", field_type="text", position=0))
        db.session.flush()
        note_type_release_service.stage_publication(db.session, note_type=source, actor_user_id=users[0].id)
        self.source_id = source.id
        db.session.commit()

    def _cleanup(self):
        db.session.rollback()
        if self.user_ids:
            # Break the source -> release -> source cycle before FK cascades.
            NoteType.query.filter(NoteType.user_id.in_(self.user_ids)).update(
                {NoteType.current_release_id: None}, synchronize_session=False)
            NoteType.query.filter(NoteType.user_id.in_(self.user_ids)).delete(synchronize_session=False)
            User.query.filter(User.id.in_(self.user_ids), User.username.like(f"install-lock-{self.token}-%")).delete(
                synchronize_session=False)
            db.session.commit()
        db.session.remove()

    def _stage(self, mode, user_id):
        source = db.session.get(NoteType, self.source_id)
        if mode == "deck":
            return note_types.ensure_note_type_install_for_user(
                source_note_type=source, user_id=user_id, copy_legacy_templates=False)
        receipt, _created = note_type_release_service.stage_receipt(
            db.session, source_note_type=source, user_id=user_id)
        return receipt

    def _parallel(self, modes, *, same_user=False):
        # Release fixture reads/connection before worker commits start.
        db.session.remove()
        barrier = threading.Barrier(2)
        increment = helpers._increment_counter

        def delayed_increment(*args, **kwargs):
            # Widen the original FK-S-lock -> counter-X-lock collision window.
            time.sleep(0.075)
            return increment(*args, **kwargs)

        def worker(index):
            with self.app.app_context():
                try:
                    user_id = self.user_ids[1 if same_user else index + 1]
                    db.session.execute(db.text("SET SESSION innodb_lock_wait_timeout = 3"))
                    # Establish an RR snapshot before the other worker commits.
                    db.session.get(NoteType, self.source_id)
                    NoteTypeInstall.query.filter_by(source_note_type_id=self.source_id, user_id=user_id).all()
                    barrier.wait(timeout=5)
                    receipt = self._stage(modes[index], user_id)
                    result = (receipt.id, receipt.installed_note_type_id)
                    db.session.commit()
                    return result
                finally:
                    db.session.rollback()
                    db.session.remove()

        with patch.object(helpers, "_increment_counter", side_effect=delayed_increment), \
                patch.object(note_types, "_increment_counter", side_effect=delayed_increment):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(worker, index) for index in range(2)]
                results = [future.result(timeout=15) for future in futures]
        expected = 1 if same_user else 2
        self.assertEqual(db.session.get(NoteType, self.source_id).install_count, expected)
        self.assertEqual(NoteTypeInstall.query.filter_by(source_note_type_id=self.source_id).count(), expected)
        self.assertEqual(NoteType.query.filter(NoteType.user_id.in_(self.user_ids[1:])).count(), expected)
        if same_user:
            self.assertEqual(results[0], results[1])
        else:
            self.assertNotEqual(results[0], results[1])
        for _receipt_id, copy_id in results:
            copied = db.session.get(NoteType, copy_id)
            self.assertEqual(copied.name, "Install lock source")
            self.assertEqual([field.name for field in copied.field_defs], ["Word"])

    def test_parallel_deck_note_types_for_different_users(self):
        self._parallel(("deck", "deck"))

    def test_parallel_release_receipts_for_different_users(self):
        self._parallel(("release", "release"))

    def test_deck_install_and_release_receipt_use_consistent_lock_order(self):
        self._parallel(("deck", "release"))

    def test_same_user_deck_install_rechecks_after_waiting(self):
        self._parallel(("deck", "deck"), same_user=True)

    def test_same_user_release_receipt_rechecks_after_waiting(self):
        self._parallel(("release", "release"), same_user=True)

    def test_restoring_deleted_copy_does_not_double_count(self):
        receipt = self._stage("deck", self.user_ids[1])
        receipt_id, copy_id = receipt.id, receipt.installed_note_type_id
        db.session.commit()
        NoteType.query.filter_by(id=copy_id).delete(synchronize_session=False)
        db.session.commit()
        db.session.expire_all()
        restored = self._stage("deck", self.user_ids[1])
        self.assertEqual(restored.id, receipt_id)
        self.assertNotEqual(restored.installed_note_type_id, copy_id)
        db.session.commit()
        self.assertEqual(db.session.get(NoteType, self.source_id).install_count, 1)

    def test_receipt_uses_published_schema_and_metadata(self):
        source = db.session.get(NoteType, self.source_id)
        source.name = "Unpublished draft name"
        source.field_defs[0].name = "DraftWord"
        db.session.commit()
        receipt = self._stage("release", self.user_ids[1])
        copied = db.session.get(NoteType, receipt.installed_note_type_id)
        self.assertEqual(copied.name, "Install lock source")
        self.assertEqual([field.name for field in copied.field_defs], ["Word"])

    def test_deck_install_keeps_source_notes_as_overlay(self):
        from app.services.share.install import install_shared_deck_item_for_user
        from models.deck import Deck
        from models.deck_install import DeckInstall
        from models.deck_marketplace_item import DeckMarketplaceItem
        from models.deck_release import DeckRelease
        from models.deck_release_entity_membership import DeckReleaseEntityMembership
        from models.note import Note
        from tests.study_note_fixtures import enroll_note_user

        # All extra deck/release data stays in this rollback-only transaction.
        for user_id in self.user_ids[:2]:
            enroll_note_user(db.session, db.session.get(User, user_id))
        source_deck = Deck(name="Overlay source", owner_user_id=self.user_ids[0], note_type_id=self.source_id)
        db.session.add(source_deck)
        db.session.flush()
        note = Note(user_id=self.user_ids[0], note_type_id=self.source_id, deck_id=source_deck.id,
            field_values={"Word": "original"})
        item = DeckMarketplaceItem(owner_user_id=self.user_ids[0], source_deck_id=source_deck.id,
            source_note_type_id=self.source_id, title="Overlay source", publish_status="published")
        db.session.add_all([note, item])
        db.session.flush()
        release = DeckRelease(deck_item_id=item.id, sequence_no=1, version_label="1",
            status="published", template_pins_initialized=True)
        db.session.add(release)
        db.session.flush()
        item.current_release_id = release.id
        db.session.add(DeckReleaseEntityMembership(deck_item_id=item.id, entity_kind="note", entity_id=note.id,
            source_deck_id=source_deck.id, introduced_sequence=1))
        db.session.flush()
        result = install_shared_deck_item_for_user(item, user_id=self.user_ids[1])
        self.assertTrue(result["created"])
        install = DeckInstall.query.filter_by(deck_item_id=item.id, user_id=self.user_ids[1]).one()
        self.assertEqual(install.clone_mode, "logical_overlay")
        self.assertEqual(install.applied_release_id, release.id)
        self.assertEqual(install.source_deck_id, source_deck.id)
        self.assertIsNotNone(install.local_deck_id)
        self.assertEqual(Note.query.filter_by(user_id=self.user_ids[1]).count(), 0)
        self.assertEqual(db.session.get(Note, note.id).field_values, {"Word": "original"})

    def test_rollback_removes_receipt_copy_and_counter_increment(self):
        for mode in ("deck", "release"):
            with self.subTest(mode=mode):
                self._stage(mode, self.user_ids[1])
                db.session.rollback()
                self.assertEqual(db.session.get(NoteType, self.source_id).install_count, 0)
                self.assertEqual(NoteTypeInstall.query.filter_by(source_note_type_id=self.source_id).count(), 0)
                self.assertEqual(NoteType.query.filter_by(user_id=self.user_ids[1]).count(), 0)


if __name__ == "__main__":
    unittest.main()
