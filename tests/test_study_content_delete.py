"""Content deletion coordinates canonical NOTE learners and immutable history."""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests import test_study_direct_note_replay as fixtures
from tests.study_note_fixtures import create_note_user, assert_retired_progress_absent, archive_wire_alias
from tests.note_progress_fixtures import stage_note_state
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.services import deck_management_service
from app.services import flashcard_content_service as content
from app.services import study_progress_lifecycle_mirror_service as lifecycle
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from models import db
from models.card import Card, PresentationAlias, get_card
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from models.review_event import ReviewEvent
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_application import StudyApplication
from models.study_session_card import StudySessionCard
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt


class StudyContentDeleteTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    def setUp(self):
        fixtures.StudyDirectNoteReplayTests.setUp(self)
        with self.app.app_context():
            from app.repositories.study_authority_repository import lock_study_authority_route
            from app.services.study_progress_lifecycle_mirror_service import materialize_new_note_authority
            route = lock_study_authority_route(db.session, learner_user_id=self.user_id, allow_note_authority=True)
            note = Note.query.filter_by(user_id=self.user_id).one()
            materialize_new_note_authority(db.session, route=route, note=note,
                cards=tuple(Card.query.filter_by(note_id=note.id).all()))
            db.session.commit()
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    @staticmethod
    def _live_states():
        return StudyProgressSubject.query.filter(StudyProgressSubject.state_payload.isnot(None))

    def _add_learners(self):
        note_type = NoteType.query.one()
        other = create_note_user(db.session, username="other-owner", email="other-owner@example.test")
        legacy = create_note_user(db.session, username="legacy-reader", email="legacy-reader@example.test")
        db.session.add_all([other, legacy])
        db.session.flush()
        deck = Deck(owner_user_id=other.id, name="Other learner")
        db.session.add(deck)
        db.session.flush()
        # The Note presents every Template of its type (ADR P11).
        note = Note(user_id=other.id, deck_id=deck.id, note_type_id=note_type.id, field_values={"Word": "other"})
        db.session.add(note)
        db.session.flush()
        stage_note_state(db.session, user_id=other.id, note_id=str(note.id))
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
            revisions = {row.id: row.authority_revision for row in StudyProgressSubject.query.all()}
            # Both owners hold canonical rows; the pristine reader has no state.
            assert_retired_progress_absent(self, db.session)
            self.assertTrue(self._purge(note_type_id)["purged"])
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(Card.query.count(), 0)
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(self._live_states().count(), 0)
            self.assertEqual(StudyProgressSubject.query.count(), 2)
            for subject in StudyProgressSubject.query.all():
                self.assertEqual(subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
                self.assertIsNone(subject.live_note_id)
                self.assertEqual(subject.authority_revision, revisions[subject.id] + 1)
                self.assertIsNone(subject.semantic_state_hash)
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
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(self._live_states().count(), 2)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def _add_note_source_reader(self):
        """Enroll a second NOTE learner with a state on the source Cards."""
        learner = create_note_user(db.session, username="source-reader", email="source-reader@example.test")
        db.session.add(learner)
        db.session.commit()
        learner_id = learner.id
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stage_note_authority_enrollment(db.session, learner_user_id=learner_id, now_utc=now)
        db.session.commit()
        route = lock_study_authority_route(db.session, learner_user_id=learner_id, allow_note_authority=True)
        note = Note.query.filter_by(user_id=self.user_id).one()
        lifecycle.materialize_pristine_note_authority(
            db.session, route=route, note=note, cards=tuple(Card.query.filter_by(note_id=note.id).order_by(Card.id)),
            starting_ease=2.5, provenance_code="NATIVE_DIRECT", now_utc=now)
        db.session.commit()
        return learner_id

    def _purge_deck(self, deck_id):
        return deck_management_service.delete_deck_subtree(deck_obj=db.session.get(Deck, deck_id),
            user_id=self.user_id, is_admin=True, purge=True)

    def test_two_note_learners_on_same_source_cards_are_both_tombstoned(self):
        with self.app.app_context():
            self._add_note_source_reader()
            self.assertEqual(self._live_states().count(), 2)
            self.assertEqual(Card.query.count(), 2)
            self.assertTrue(self._purge(NoteType.query.one().id)["purged"])
            self.assertEqual(self._live_states().count(), 0)
            self.assertEqual(StudyProgressSubject.query.filter_by(status_code="TOMBSTONED_SUBJECT_DELETED").count(), 2)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 2)

    def test_cardless_canonical_state_rejects_purge_without_partial_delete(self):
        with self.app.app_context():
            note_type_id = NoteType.query.one().id
            StudyApplication.query.delete(synchronize_session=False)
            db.session.commit()
            with self.assertRaises(content.ContentApiError) as failure:
                self._purge(note_type_id)
            self.assertEqual(failure.exception.error, "AUTHORITY_DELETE_INCOMPLETE")
            self.assertEqual(NoteType.query.count(), 1)
            self.assertEqual(Note.query.count(), 1)
            self.assertEqual(self._live_states().count(), 1)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def test_mixed_learner_deck_purge_tombstones_only_subtree_state_and_keeps_history(self):
        self._answer()
        with self.app.app_context():
            self._add_learners()
            other_subject_id = StudyProgressSubject.query.filter(
                StudyProgressSubject.learner_user_id != self.user_id).one().id
            own_subject_id = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one().id
            revision = db.session.get(StudyProgressSubject, own_subject_id).authority_revision
            self.assertEqual(self._purge_deck(self.deck_id), "purged")
            self.assertIsNone(db.session.get(Deck, self.deck_id))
            self.assertEqual(Note.query.count(), 1)
            self.assertEqual(Card.query.count(), 2)
            # No retired progress table is read or rewritten.
            assert_retired_progress_absent(self, db.session)
            self.assertEqual({row.id for row in self._live_states()}, {other_subject_id})
            own_subject = db.session.get(StudyProgressSubject, own_subject_id)
            self.assertEqual(own_subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
            self.assertIsNone(own_subject.live_note_id)
            self.assertEqual(own_subject.authority_revision, revision + 1)
            self.assertIsNone(own_subject.semantic_state_hash)
            self.assertIsNotNone(db.session.get(StudyProgressSubject, other_subject_id).live_note_id)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 1)
            self.assertIsNone(ReviewEvent.query.one().deck_id)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)

    def test_deck_purge_tombstones_two_note_learners_on_same_cards(self):
        with self.app.app_context():
            reader_id = self._add_note_source_reader()
            self.assertEqual(self._purge_deck(self.deck_id), "purged")
            self.assertEqual(self._live_states().count(), 0)
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
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(self._live_states().count(), 2)
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
            self.assertEqual(self._live_states().count(), 0)

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
            self.assertEqual(self._live_states().count(), 1)
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
        return {row.id: (row.authority_revision, row.semantic_state_hash)
            for row in StudyProgressSubject.query.all()}

    def test_owner_note_delete_cancels_pristine_reader_lease_and_keeps_membership(self):
        with self.app.app_context():
            self._add_learners()
            reader_id = User.query.filter_by(username="legacy-reader").one().id
            own_session = self._open_session(self.user_id, self.card_ids[0])
            reader_session = self._open_session(reader_id, self.card_ids[0])
            self.assertEqual(content.delete_note(user_id=self.user_id, note_id=self._own_note_id()), {"success": True})
            assert_retired_progress_absent(self, db.session)
            own_subject = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one()
            self.assertEqual(own_subject.status_code, "TOMBSTONED_SUBJECT_DELETED")
            self.assertEqual(self._live_states().count(), 1)
            self.assertEqual(db.session.get(StudySession, own_session).status, "cancelled")
            self.assertEqual(db.session.get(StudySession, reader_session).status, "cancelled")
            self.assertEqual(StudySessionCard.query.filter_by(session_id=reader_session).one().card_id, self.card_ids[0])

    def test_mcp_batch_note_delete_tombstones_second_note_learner(self):
        from app.services.mcp import note_tools
        with self.app.app_context():
            reader_id = self._add_note_source_reader()
            result = note_tools.batch_delete_notes(user_id=self.user_id,
                note_ids=[self._own_note_id()], confirm=True)
            self.assertEqual(result["deleted_count"], 1)
            self.assertEqual(self._live_states().count(), 0)
            self.assertEqual({subject.learner_user_id for subject in StudyProgressSubject.query.filter_by(
                status_code="TOMBSTONED_SUBJECT_DELETED")}, {self.user_id, reader_id})

    def test_owned_deck_delete_tombstones_owner_and_keeps_other_note_state(self):
        with self.app.app_context():
            self._add_learners()
            self.assertEqual(deck_management_service.delete_deck_subtree(
                deck_obj=db.session.get(Deck, self.deck_id), user_id=self.user_id, is_admin=False), "deleted")
            self.assertIsNone(db.session.get(Deck, self.deck_id))
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one().status_code,
                "TOMBSTONED_SUBJECT_DELETED")
            self.assertEqual(self._live_states().count(), 1)

    def test_browse_partial_card_delete_is_refused_and_keeps_every_note_learner_state(self):
        # A Card is its Note shown through one occurrence (ADR P11): it goes with
        # its Note or its Template, never alone.
        from app.services import browse_card_service
        with self.app.app_context():
            self._add_note_source_reader()
            before = self._state_tokens()
            with self.assertRaises(browse_card_service.BrowseApiError) as failure:
                browse_card_service.delete_browse_card(user_id=self.user_id, admin_mode=False, card_id=self.card_ids[0])
            self.assertEqual(failure.exception.code, "CARD_PARTIAL_DELETE_UNSUPPORTED")
            db.session.rollback()
            self.assertEqual(Card.query.count(), 2)
            self.assertEqual(Note.query.count(), 1)
            self.assertEqual(self._state_tokens(), before)
            self.assertEqual(self._live_states().count(), 2)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def test_browse_batch_delete_of_every_card_tombstones_the_note(self):
        from app.services import browse_card_service
        with self.app.app_context():
            self._add_learners()
            browse_card_service.delete_browse_cards_batch(user_id=self.user_id, admin_mode=False,
                card_ids=list(self.card_ids))
            self.assertIsNone(Note.query.filter_by(user_id=self.user_id).one_or_none())
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one().status_code,
                "TOMBSTONED_SUBJECT_DELETED")

    def test_browse_selected_note_delete_keeps_templates_and_cancels_all_presentations(self):
        from app.services import browse_card_service
        with self.app.app_context():
            reader_id = self._add_note_source_reader()
            own_session = self._open_session(self.user_id, self.card_ids[0])
            reader_session = self._open_session(reader_id, self.card_ids[1])
            listing = browse_card_service.list_browse_cards(user_id=self.user_id, admin_mode=False,
                timezone_name="UTC", query_args={"deck_id": str(self.deck_id)})
            self.assertEqual(listing["total"], 1)
            ids = [row["note_id"] for row in listing["items"]]
        response = self.client.post("/api/browse/notes/batch-delete", json={"note_ids": ids + ids})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["deleted_count"], 1)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Note, ids[0]))
            self.assertEqual(Card.query.count(), 0)
            self.assertEqual(Template.query.count(), 2)
            self.assertEqual(StudyApplication.query.count(), 2)
            self.assertEqual({row.status_code for row in StudyProgressSubject.query.all()},
                {"TOMBSTONED_SUBJECT_DELETED"})
            for session_id in (own_session, reader_session):
                self.assertEqual(db.session.get(StudySession, session_id).status, "cancelled")

    def test_browse_note_delete_works_without_active_presentations(self):
        with self.app.app_context():
            note_id = self._own_note_id()
            for app in StudyApplication.query.all():
                app.status_code = "RETIRED"
            db.session.commit()
        response = self.client.delete(f"/api/browse/notes/{note_id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            self.assertIsNone(db.session.get(Note, note_id))
            self.assertEqual(Template.query.count(), 2)
            self.assertEqual(StudyApplication.query.count(), 2)

    def test_browse_note_batch_rejects_foreign_note_without_deleting_owned_note(self):
        with self.app.app_context():
            self._add_learners()
            own_id = self._own_note_id()
            foreign_id = Note.query.filter(Note.user_id != self.user_id).one().id
        response = self.client.post("/api/browse/notes/batch-delete",
            json={"note_ids": [own_id, foreign_id]})
        self.assertEqual(response.status_code, 403, response.get_json())
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Note, own_id))
            self.assertIsNotNone(db.session.get(Note, foreign_id))

    def test_browse_note_batch_validates_ids_and_missing_notes_atomically(self):
        for payload in ([], {}, {"note_ids": "bad"}, {"note_ids": [None]}, {"note_ids": [{}]},
                        {"note_ids": [""]}, {"note_ids": ["x" * 37]}):
            with self.subTest(payload=payload):
                response = self.client.post("/api/browse/notes/batch-delete", json=payload)
                self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            own_id = self._own_note_id()
        response = self.client.post("/api/browse/notes/batch-delete",
            json={"note_ids": [own_id, str(uuid4())]})
        self.assertEqual(response.status_code, 404)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Note, own_id))

    def test_browse_note_delete_preserves_released_source_even_for_owner(self):
        from models.deck_release_entity_membership import DeckReleaseEntityMembership
        with self.app.app_context():
            note = db.session.get(Note, self._own_note_id())
            note_id = note.id
            item = DeckMarketplaceItem(owner_user_id=self.user_id, source_deck_id=self.deck_id,
                source_note_type_id=note.note_type_id, title="Published source", publish_status="published",
                pricing_mode="free")
            db.session.add(item)
            db.session.flush()
            db.session.add(DeckReleaseEntityMembership(deck_item_id=item.id, entity_kind="note",
                entity_id=note_id, source_deck_id=self.deck_id, introduced_sequence=1))
            db.session.commit()
        response = self.client.delete(f"/api/browse/notes/{note_id}")
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["code"], "SHARED_ENTITY_RETIRE_REQUIRED")
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Note, note_id))
            self.assertEqual(Template.query.count(), 2)

    def test_template_delete_keeps_state_for_owner_and_second_note_learner(self):
        with self.app.app_context():
            self._add_note_source_reader()
            before = self._state_tokens()
            template = Template.query.filter_by(name="Card 1").one()
            content.delete_template(user_id=self.user_id, note_type_id=NoteType.query.one().id, template_id=template.id)
            self.assertEqual(Card.query.count(), 1)
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(self._state_tokens(), before)

    def test_rollback_to_legacy_is_retired_and_changes_nothing(self):
        from app.services.study_authority_enrollment_service import (
            StudyAuthorityEnrollmentError, stage_legacy_authority_enrollment)
        with self.app.app_context():
            content.delete_note(user_id=self.user_id, note_id=self._own_note_id())
            before = self._state_tokens()
            with self.assertRaises(StudyAuthorityEnrollmentError) as failure:
                stage_legacy_authority_enrollment(db.session, learner_user_id=self.user_id,
                    now_utc=datetime.now(timezone.utc).replace(tzinfo=None))
            self.assertEqual(failure.exception.code, "LEGACY_ROLLBACK_RETIRED")
            db.session.rollback()
            self.assertEqual(self._state_tokens(), before)
            assert_retired_progress_absent(self, db.session)

    def test_rest_template_create_expands_second_note_learner(self):
        with self.app.app_context():
            reader_id = self._add_note_source_reader()
            before = self._state_tokens()
            content.create_template(user_id=self.user_id, note_type_id=NoteType.query.one().id,
                payload={"name": "Reverse"})
            self.assertEqual(Card.query.count(), 3)
            # A new Template's Card shares its Note's row; nothing is copied (ADR P10).
            assert_retired_progress_absent(self, db.session)
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(self._state_tokens(), before)

    def test_owner_delete_rejects_learner_that_gains_progress_after_admission(self):
        from app.services import study_content_delete_service as content_delete
        with self.app.app_context():
            late = create_note_user(db.session, username="late-learner", email="late-learner@example.test")
            db.session.add(late)
            db.session.commit()
            late_id = late.id
            original = content_delete.prepare_content_delete

            def add_late_progress(*args, **kwargs):
                plan = original(*args, **kwargs)
                stage_note_state(db.session, user_id=late_id, note_id=str(self._own_note_id()))
                db.session.flush()
                return plan

            with patch.object(content_delete, "prepare_content_delete", side_effect=add_late_progress):
                with self.assertRaises(content.ContentApiError) as failure:
                    content.delete_note(user_id=self.user_id, note_id=self._own_note_id())
            self.assertEqual(failure.exception.error, "CONTENT_SCOPE_CHANGED")
            self.assertEqual(Note.query.count(), 1)
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(self._live_states().count(), 1)

    def test_owner_note_delete_fault_leaves_every_learner_untouched(self):
        with self.app.app_context():
            self._add_learners()
            with patch.object(lifecycle, "finalize_note_authority_delete", side_effect=RuntimeError("owner fault")):
                with self.assertRaisesRegex(RuntimeError, "owner fault"):
                    content.delete_note(user_id=self.user_id, note_id=self._own_note_id())
            db.session.rollback()
            self.assertEqual(Note.query.count(), 2)
            assert_retired_progress_absent(self, db.session)
            self.assertEqual(self._live_states().count(), 2)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)

    def test_note_delete_cancels_old_uuid_lease_and_preserves_receipt_history_and_alias(self):
        old_uuid = str(uuid4())
        with self.app.app_context():
            card = db.session.get(Card, self.card_ids[0])
            note_id = card.note_id
            archive_wire_alias(db.session, card, old_uuid)
            db.session.commit()
        self._answer(card_id=old_uuid)
        with self.app.app_context():
            session_id = self._open_session(self.user_id, old_uuid)
            membership = StudySessionCard.query.one()
            event = ReviewEvent.query.one()
            receipt = StudyAuthorityCommandReceipt.query.one()
            before = (membership.initial_state_json, event.payload_json,
                receipt.request_fingerprint, receipt.response_payload)
            self.assertEqual(content.delete_note(user_id=self.user_id, note_id=note_id), {"success": True})
            self.assertEqual(db.session.get(StudySession, session_id).status, "cancelled")
            self.assertIsNone(get_card(db.session, old_uuid))
            self.assertIsNotNone(db.session.get(PresentationAlias, old_uuid))
            self.assertEqual(StudyProgressSubject.query.one().status_code, "TOMBSTONED_SUBJECT_DELETED")
            membership = StudySessionCard.query.one()
            event = ReviewEvent.query.one()
            receipt = StudyAuthorityCommandReceipt.query.one()
            self.assertEqual(membership.card_id, old_uuid)
            self.assertEqual(event.card_id, old_uuid)
            self.assertEqual(event.note_id, note_id)
            self.assertEqual((membership.initial_state_json, event.payload_json,
                receipt.request_fingerprint, receipt.response_payload), before)

    def test_deck_purge_rejects_cardless_canonical_state(self):
        with self.app.app_context():
            StudyApplication.query.delete(synchronize_session=False)
            db.session.commit()
            with self.assertRaises(StudyAuthorityFenceError) as failure:
                self._purge_deck(self.deck_id)
            self.assertEqual(failure.exception.code, "AUTHORITY_DELETE_INCOMPLETE")
            self.assertIsNotNone(db.session.get(Deck, self.deck_id))
            self.assertEqual(Note.query.count(), 1)
            self.assertEqual(self._live_states().count(), 1)
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 0)
