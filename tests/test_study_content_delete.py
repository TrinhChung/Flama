"""Admin NoteType and deck purges coordinate NOTE and LEGACY learners atomically."""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from tests import test_study_direct_note_replay as fixtures
from app.repositories.study_authority_repository import StudyAuthorityFenceError
from app.services import deck_management_service
from app.services import flashcard_content_service as content
from app.services import study_progress_lifecycle_mirror_service as lifecycle
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from models.review_event import ReviewEvent
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt


class StudyContentDeleteTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    def _add_learners(self):
        note_type = NoteType.query.one()
        other = User(username="other-owner", email="other-owner@example.test")
        legacy = User(username="legacy-reader", email="legacy-reader@example.test")
        db.session.add_all([other, legacy])
        db.session.flush()
        deck = Deck(owner_user_id=other.id, name="Other learner")
        db.session.add(deck)
        db.session.flush()
        note = Note(user_id=other.id, deck_id=deck.id, note_type_id=note_type.id, field_values={"Word": "other"})
        db.session.add(note)
        db.session.flush()
        for template in Template.query.all():
            db.session.add(Card(note_id=note.id, template_id=template.id))
        db.session.add(CardProgress(user_id=legacy.id, card_id=self.card_ids[0]))
        db.session.commit()
        stage_note_authority_enrollment(db.session, learner_user_id=other.id,
            now_utc=datetime.now(timezone.utc).replace(tzinfo=None))
        db.session.commit()
        return note_type.id

    def _purge(self, note_type_id):
        return content.delete_note_type(user_id=self.user_id, note_type_id=note_type_id,
            purge=True, is_admin=True)

    def test_mixed_learner_purge_tombstones_both_note_states_and_keeps_history(self):
        self._answer()
        with self.app.app_context():
            note_type_id = self._add_learners()
            revisions = {row.subject_id: row.authority_revision for row in StudyAuthoritySubjectToken.query.all()}
            self.assertEqual(CardProgress.query.count(), 5)
            self.assertTrue(self._purge(note_type_id)["purged"])
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(Card.query.count(), 0)
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(StudyProgressState.query.count(), 0)
            self.assertEqual(StudyProgressSubject.query.count(), 2)
            for subject in StudyProgressSubject.query.all():
                self.assertEqual(subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
                self.assertIsNone(subject.live_note_id)
            for token in StudyAuthoritySubjectToken.query.all():
                self.assertEqual(token.authority_revision, revisions[token.subject_id] + 1)
                self.assertIsNone(token.semantic_state_hash)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 2)
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)

    def test_second_learner_fault_rolls_back_whole_purge(self):
        with self.app.app_context():
            note_type_id = self._add_learners()
            original = lifecycle.finalize_note_authority_delete
            calls = 0
            def fail_second(*args, **kwargs):
                nonlocal calls
                calls += 1
                result = original(*args, **kwargs)
                if calls == 2:
                    raise RuntimeError("second learner fault")
                return result
            with patch.object(lifecycle, "finalize_note_authority_delete", side_effect=fail_second):
                with self.assertRaisesRegex(RuntimeError, "second learner fault"):
                    self._purge(note_type_id)
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(NoteType.query.count(), 1)
            self.assertEqual(Note.query.count(), 2)
            self.assertEqual(Card.query.count(), 4)
            self.assertEqual(CardProgress.query.count(), 5)
            self.assertEqual(StudyProgressState.query.count(), 2)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def _add_note_source_reader(self):
        """Enroll a second NOTE learner with canonical state on the source Cards."""
        from app.services import study_progress_shadow_mirror_service as mirror
        learner = User(username="source-reader", email="source-reader@example.test")
        db.session.add(learner)
        db.session.flush()
        learner_id = learner.id
        cards = Card.query.all()
        for card in cards:
            db.session.add(CardProgress(user_id=learner_id, card_id=card.id))
        db.session.commit()
        with patch.dict(self.app.config, STUDY_PROGRESS_SHADOW_WRITE_ENABLED=True):
            plan = mirror.prepare_native_mirror(db.session, learner_user_id=learner_id, cards=cards)
            mirror.finalize_native_mirror(plan, review_events=())
            db.session.commit()
        stage_note_authority_enrollment(db.session, learner_user_id=learner_id,
            now_utc=datetime.now(timezone.utc).replace(tzinfo=None))
        db.session.commit()
        return learner_id

    def _purge_deck(self, deck_id):
        return deck_management_service.delete_deck_subtree(deck_obj=db.session.get(Deck, deck_id),
            user_id=self.user_id, is_admin=True, purge=True)

    def test_two_note_learners_on_same_source_cards_are_both_tombstoned(self):
        with self.app.app_context():
            self._add_note_source_reader()
            self.assertEqual(StudyProgressState.query.count(), 2)
            self.assertEqual(Card.query.count(), 2)
            self.assertTrue(self._purge(NoteType.query.one().id)["purged"])
            self.assertEqual(StudyProgressState.query.count(), 0)
            self.assertEqual(StudyProgressSubject.query.filter_by(status_code="TOMBSTONED_SUBJECT_DELETED").count(), 2)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 2)

    def test_cardless_canonical_state_rejects_purge_without_partial_delete(self):
        with self.app.app_context():
            note_type_id = NoteType.query.one().id
            CardProgress.query.delete(synchronize_session=False)
            Card.query.delete(synchronize_session=False)
            db.session.commit()
            with self.assertRaises(content.ContentApiError) as failure:
                self._purge(note_type_id)
            self.assertEqual(failure.exception.error, "AUTHORITY_DELETE_INCOMPLETE")
            self.assertEqual(NoteType.query.count(), 1)
            self.assertEqual(Note.query.count(), 1)
            self.assertEqual(StudyProgressState.query.count(), 1)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def test_mixed_learner_deck_purge_tombstones_only_subtree_state_and_keeps_history(self):
        self._answer()
        with self.app.app_context():
            self._add_learners()
            other_subject_id = StudyProgressSubject.query.filter(
                StudyProgressSubject.learner_user_id != self.user_id).one().id
            own_subject_id = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one().id
            revision = db.session.get(StudyAuthoritySubjectToken, own_subject_id).authority_revision
            self.assertEqual(self._purge_deck(self.deck_id), "purged")
            self.assertIsNone(db.session.get(Deck, self.deck_id))
            self.assertEqual(Note.query.count(), 1)
            self.assertEqual(Card.query.count(), 2)
            # The LEGACY reader's row and both owner rows on the purged Cards go.
            self.assertEqual(CardProgress.query.count(), 2)
            self.assertEqual({row.subject_id for row in StudyProgressState.query.all()}, {other_subject_id})
            own_subject = db.session.get(StudyProgressSubject, own_subject_id)
            self.assertEqual(own_subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
            self.assertIsNone(own_subject.live_note_id)
            own_token = db.session.get(StudyAuthoritySubjectToken, own_subject_id)
            self.assertEqual(own_token.authority_revision, revision + 1)
            self.assertIsNone(own_token.semantic_state_hash)
            self.assertIsNotNone(db.session.get(StudyProgressSubject, other_subject_id).live_note_id)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 1)
            self.assertIsNone(ReviewEvent.query.one().deck_id)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)

    def test_deck_purge_tombstones_two_note_learners_on_same_cards(self):
        with self.app.app_context():
            reader_id = self._add_note_source_reader()
            self.assertEqual(self._purge_deck(self.deck_id), "purged")
            self.assertEqual(StudyProgressState.query.count(), 0)
            self.assertEqual({subject.learner_user_id for subject in StudyProgressSubject.query.filter_by(
                status_code="TOMBSTONED_SUBJECT_DELETED")}, {self.user_id, reader_id})
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 2)

    def test_deck_purge_fault_rolls_back_every_learner(self):
        with self.app.app_context():
            self._add_learners()
            with patch.object(lifecycle, "finalize_note_authority_delete",
                    side_effect=RuntimeError("deck purge fault")):
                with self.assertRaisesRegex(RuntimeError, "deck purge fault"):
                    self._purge_deck(self.deck_id)
            self.assertFalse(db.session().in_transaction())
            self.assertIsNotNone(db.session.get(Deck, self.deck_id))
            self.assertEqual(Note.query.count(), 2)
            self.assertEqual(Card.query.count(), 4)
            self.assertEqual(CardProgress.query.count(), 5)
            self.assertEqual(StudyProgressState.query.count(), 2)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def test_deck_purge_cancels_note_session_opened_on_parent_deck(self):
        with self.app.app_context():
            parent = Deck(name="Parent", owner_user_id=self.user_id)
            db.session.add(parent)
            db.session.flush()
            db.session.get(Deck, self.deck_id).parent_id = parent.id
            study_session = StudySession(user_id=self.user_id, scope_type="deck", scope_id=str(parent.id),
                local_deck_id=parent.id, snapshot_hash="parent-snapshot", token_hash="b" * 64,
                config_snapshot_json="{}", expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1))
            db.session.add(study_session)
            db.session.flush()
            db.session.add(StudySessionCard(session_id=study_session.id, card_id=self.card_ids[0],
                source_deck_id=self.deck_id, local_deck_id=self.deck_id,
                note_type_id=NoteType.query.one().id, base_progress_revision=0,
                base_state_hash="parent-state", scheduler_config_hash="parent-config",
                initial_state_json="{}", ordinal=0))
            db.session.commit()
            session_id, parent_id = study_session.id, parent.id
            self.assertEqual(self._purge_deck(self.deck_id), "purged")
            self.assertIsNotNone(db.session.get(Deck, parent_id))
            self.assertEqual(db.session.get(StudySession, session_id).status, "cancelled")
            self.assertEqual(StudyProgressState.query.count(), 0)

    def test_deck_purge_of_note_learner_clone_node_removes_install_only(self):
        with self.app.app_context():
            self._add_learners()
            source = Deck.query.filter_by(name="Other learner").one()
            item = DeckMarketplaceItem(owner_user_id=source.owner_user_id, source_deck_id=source.id,
                title="Other learner")
            db.session.add(item)
            db.session.flush()
            db.session.add(DeckInstall(deck_item_id=item.id, user_id=self.user_id,
                local_deck_id=self.deck_id, source_deck_id=source.id,
                source_owner_user_id=source.owner_user_id))
            db.session.commit()
            self.assertEqual(self._purge_deck(self.deck_id), "purged")
            self.assertIsNone(db.session.get(Deck, self.deck_id))
            self.assertEqual(DeckInstall.query.count(), 0)
            # The purged Notes are tombstoned; the install source stays live.
            self.assertEqual(StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one().status_code,
                "TOMBSTONED_SUBJECT_DELETED")
            self.assertEqual(StudyProgressState.query.count(), 1)
            self.assertIsNotNone(Deck.query.filter_by(name="Other learner").one_or_none())

    def _open_session(self, learner_id, card_id):
        study_session = StudySession(user_id=learner_id, scope_type="deck", scope_id=str(self.deck_id),
            local_deck_id=self.deck_id, snapshot_hash=f"snapshot-{learner_id}", token_hash=f"{learner_id:064d}",
            config_snapshot_json="{}", expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1))
        db.session.add(study_session)
        db.session.flush()
        db.session.add(StudySessionCard(session_id=study_session.id, card_id=card_id,
            source_deck_id=self.deck_id, local_deck_id=self.deck_id,
            note_type_id=NoteType.query.one().id, base_progress_revision=0,
            base_state_hash="state", scheduler_config_hash="config", initial_state_json="{}", ordinal=0))
        db.session.commit()
        return study_session.id

    def _own_note_id(self):
        return Note.query.filter_by(user_id=self.user_id).one().id

    def _state_tokens(self):
        return {token.subject_id: (token.authority_revision, token.semantic_state_hash)
            for token in StudyAuthoritySubjectToken.query.all()}

    def test_owner_note_delete_retires_legacy_reader_and_keeps_its_session(self):
        with self.app.app_context():
            self._add_learners()
            reader_id = User.query.filter_by(username="legacy-reader").one().id
            own_session = self._open_session(self.user_id, self.card_ids[0])
            reader_session = self._open_session(reader_id, self.card_ids[0])
            self.assertEqual(content.delete_note(user_id=self.user_id, note_id=self._own_note_id()), {"success": True})
            self.assertEqual(CardProgress.query.filter(CardProgress.card_id.in_(self.card_ids)).count(), 0)
            own_subject = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one()
            self.assertEqual(own_subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
            self.assertEqual(StudyProgressState.query.count(), 1)
            self.assertEqual(db.session.get(StudySession, own_session).status, "cancelled")
            self.assertEqual(db.session.get(StudySession, reader_session).status, "open")

    def test_mcp_batch_note_delete_tombstones_second_note_learner(self):
        from app.services.mcp import note_tools
        with self.app.app_context():
            reader_id = self._add_note_source_reader()
            result = note_tools.batch_delete_notes(user_id=self.user_id,
                note_ids=[self._own_note_id()], confirm=True)
            self.assertEqual(result["deleted_count"], 1)
            self.assertEqual(StudyProgressState.query.count(), 0)
            self.assertEqual({subject.learner_user_id for subject in StudyProgressSubject.query.filter_by(
                status_code="TOMBSTONED_SUBJECT_DELETED")}, {self.user_id, reader_id})

    def test_owned_deck_delete_retires_legacy_reader_progress(self):
        with self.app.app_context():
            self._add_learners()
            self.assertEqual(deck_management_service.delete_deck_subtree(
                deck_obj=db.session.get(Deck, self.deck_id), user_id=self.user_id, is_admin=False), "deleted")
            self.assertIsNone(db.session.get(Deck, self.deck_id))
            self.assertEqual(CardProgress.query.count(), 2)
            self.assertEqual(StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one().status_code,
                "TOMBSTONED_SUBJECT_DELETED")
            self.assertEqual(StudyProgressState.query.count(), 1)

    def test_browse_partial_card_delete_keeps_every_note_learner_state(self):
        from app.services import browse_card_service
        with self.app.app_context():
            self._add_note_source_reader()
            before = self._state_tokens()
            browse_card_service.delete_browse_card(user_id=self.user_id, admin_mode=False, card_id=self.card_ids[0])
            self.assertEqual(Card.query.count(), 1)
            self.assertEqual(Note.query.count(), 1)
            self.assertEqual({row.card_id for row in CardProgress.query.all()}, {self.card_ids[1]})
            self.assertEqual(CardProgress.query.count(), 2)
            self.assertEqual(self._state_tokens(), before)
            self.assertEqual(StudyProgressState.query.count(), 2)
            self.assertTrue(all(subject.status_code.startswith("MIRRORED_")
                for subject in StudyProgressSubject.query.all()))
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 2)

    def test_browse_batch_delete_of_every_card_tombstones_the_note(self):
        from app.services import browse_card_service
        with self.app.app_context():
            self._add_learners()
            browse_card_service.delete_browse_cards_batch(user_id=self.user_id, admin_mode=False,
                card_ids=list(self.card_ids))
            self.assertIsNone(Note.query.filter_by(user_id=self.user_id).one_or_none())
            self.assertEqual(CardProgress.query.count(), 2)
            self.assertEqual(StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one().status_code,
                "TOMBSTONED_SUBJECT_DELETED")

    def test_template_delete_keeps_state_for_owner_and_second_note_learner(self):
        with self.app.app_context():
            self._add_note_source_reader()
            before = self._state_tokens()
            template = Template.query.filter_by(name="Card 1").one()
            content.delete_template(user_id=self.user_id, note_type_id=template.note_type_id, template_id=template.id)
            self.assertEqual(Card.query.count(), 1)
            self.assertEqual({row.card_id for row in CardProgress.query.all()}, {self.card_ids[0]})
            self.assertEqual(CardProgress.query.count(), 2)
            self.assertEqual(self._state_tokens(), before)

    def test_rollback_to_legacy_skips_notes_deleted_under_note_authority(self):
        from app.services.study_authority_enrollment_service import stage_legacy_authority_enrollment
        with self.app.app_context():
            deleted_note_id = self._own_note_id()
            created = content.create_note(user_id=self.user_id, payload={"note_type_id": NoteType.query.one().id,
                "deck_id": self.deck_id, "field_values": {"Word": "kept"}})
            content.delete_note(user_id=self.user_id, note_id=deleted_note_id)
            self.assertEqual(StudyProgressSubject.query.filter_by(
                learner_user_id=self.user_id, status_code="TOMBSTONED_SUBJECT_DELETED").count(), 1)
            result = stage_legacy_authority_enrollment(db.session, learner_user_id=self.user_id,
                now_utc=datetime.now(timezone.utc).replace(tzinfo=None))
            db.session.commit()
            self.assertEqual((result.mode_code, result.subject_count, result.card_count), ("LEGACY", 1, 2))
            kept_cards = {card.id for card in Card.query.filter_by(note_id=created["id"])}
            self.assertEqual({row.card_id for row in CardProgress.query.filter_by(user_id=self.user_id)}, kept_cards)

    def test_rollback_rejects_deleted_subject_that_kept_canonical_state(self):
        from app.services.study_authority_enrollment_service import (
            StudyAuthorityEnrollmentError, stage_legacy_authority_enrollment)
        with self.app.app_context():
            subject = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one()
            # Corrupt tombstone: status/pointer say deleted but state survived.
            subject.status_code, subject.live_note_id = "TOMBSTONED_SUBJECT_DELETED", None
            db.session.commit()
            with self.assertRaises(StudyAuthorityEnrollmentError) as failure:
                stage_legacy_authority_enrollment(db.session, learner_user_id=self.user_id,
                    now_utc=datetime.now(timezone.utc).replace(tzinfo=None))
            self.assertEqual(failure.exception.code, "AUTHORITY_SUBJECT_NOT_READY")
            db.session.rollback()

    def test_rest_template_create_expands_second_note_learner(self):
        with self.app.app_context():
            reader_id = self._add_note_source_reader()
            before = self._state_tokens()
            content.create_template(user_id=self.user_id, note_type_id=NoteType.query.one().id,
                payload={"name": "Reverse"})
            self.assertEqual(Card.query.count(), 3)
            self.assertEqual(CardProgress.query.filter_by(user_id=reader_id).count(), 3)
            self.assertEqual(CardProgress.query.filter_by(user_id=self.user_id).count(), 3)
            self.assertEqual(self._state_tokens(), before)

    def test_owner_delete_rejects_learner_that_gains_progress_after_admission(self):
        from app.services import study_content_delete_service as content_delete
        with self.app.app_context():
            late = User(username="late-learner", email="late-learner@example.test")
            db.session.add(late)
            db.session.commit()
            late_id = late.id
            original = content_delete.prepare_content_delete

            def add_late_progress(*args, **kwargs):
                plan = original(*args, **kwargs)
                db.session.add(CardProgress(user_id=late_id, card_id=self.card_ids[1]))
                db.session.flush()
                return plan

            with patch.object(content_delete, "prepare_content_delete", side_effect=add_late_progress):
                with self.assertRaises(content.ContentApiError) as failure:
                    content.delete_note(user_id=self.user_id, note_id=self._own_note_id())
            self.assertEqual(failure.exception.error, "CONTENT_SCOPE_CHANGED")
            self.assertEqual(Note.query.count(), 1)
            self.assertEqual(CardProgress.query.count(), 2)
            self.assertEqual(StudyProgressState.query.count(), 1)

    def test_owner_note_delete_fault_leaves_every_learner_untouched(self):
        with self.app.app_context():
            self._add_learners()
            with patch.object(lifecycle, "finalize_note_authority_delete", side_effect=RuntimeError("owner fault")):
                with self.assertRaisesRegex(RuntimeError, "owner fault"):
                    content.delete_note(user_id=self.user_id, note_id=self._own_note_id())
            db.session.rollback()
            self.assertEqual(Note.query.count(), 2)
            self.assertEqual(CardProgress.query.count(), 5)
            self.assertEqual(StudyProgressState.query.count(), 2)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def test_deck_purge_rejects_cardless_canonical_state(self):
        with self.app.app_context():
            CardProgress.query.delete(synchronize_session=False)
            Card.query.delete(synchronize_session=False)
            db.session.commit()
            with self.assertRaises(StudyAuthorityFenceError) as failure:
                self._purge_deck(self.deck_id)
            self.assertEqual(failure.exception.code, "AUTHORITY_DELETE_INCOMPLETE")
            self.assertIsNotNone(db.session.get(Deck, self.deck_id))
            self.assertEqual(Note.query.count(), 1)
            self.assertEqual(StudyProgressState.query.count(), 1)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)
