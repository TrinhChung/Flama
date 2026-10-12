"""P5-04 complete sibling locking, including logical-overlay ownership."""

from __future__ import annotations

from datetime import datetime
import unittest

import sqlalchemy as sa

from app import create_app
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    StudyAuthorityRoute,
    lock_study_authority_siblings,
    lock_study_authority_subject,
)
from models import db
from models.card import Card
from tests.study_note_fixtures import attach_template, enroll_note_user, archive_wire_alias, assert_retired_progress_absent
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User


NOW = datetime(2026, 9, 21, 4, 5, 6)


class StudyAuthoritySiblingRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        learner = User(email="sibling-learner@example.test", username="sibling-learner")
        publisher = User(
            email="sibling-publisher@example.test", username="sibling-publisher"
        )
        db.session.add_all([learner, publisher])
        db.session.flush()
        enroll_note_user(db.session, learner)
        enroll_note_user(db.session, publisher)
        self.learner_id = int(learner.id)
        self.publisher_id = int(publisher.id)
        note_type = NoteType(user_id=self.publisher_id, name="Published source")
        db.session.add(note_type)
        db.session.flush()
        templates = (
            attach_template(db.session, owner_user_id=self.publisher_id, note_type_id=note_type.id, id="sibling-template-b", name="B", position=1),
            attach_template(db.session, owner_user_id=self.publisher_id, note_type_id=note_type.id, id="sibling-template-a", name="A", position=0),
        )
        deck = Deck(
            owner_user_id=self.publisher_id,
            note_type=note_type,
            name="Published source",
        )
        note = Note(
            id="sibling-source-note",
            note_type=note_type,
            user_id=self.publisher_id,
            field_values={"Front": "source"},
            tags=[],
        )
        # Both Templates present the Note (ADR P11); no Card is stored.
        db.session.add_all([note_type, *templates, deck, note])
        db.session.flush()
        note.deck_id = int(deck.id)
        subject = StudyProgressSubject(
            learner_user_id=self.learner_id,
            logical_note_key=str(note.id).encode("utf-8"),
            live_note_id=str(note.id),
            subject_generation=1,
            mirror_revision=0,
            status_code="NO_CURRENT_PROGRESS",
            contributor_count=0,
            created_at=NOW,
            updated_at=NOW,
        )
        db.session.add(subject)
        db.session.commit()
        self.subject_id = int(subject.id)
        self.card_ids = tuple(sorted(card.id for card in Card.query.filter_by(note_id=note.id)))
        self.assertEqual(len(self.card_ids), 2)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _route(self, *, mode: str = "NOTE") -> StudyAuthorityRoute:
        return StudyAuthorityRoute(
            learner_user_id=self.learner_id,
            mode_code=mode,
            epoch=4,
            persisted=True,
        )

    def _locked(self, route: StudyAuthorityRoute | None = None):
        effective_route = route or self._route()
        subject = db.session.execute(
            sa.select(StudyProgressSubject)
            .where(StudyProgressSubject.id == self.subject_id)
            .with_for_update()
        ).scalar_one()
        return lock_study_authority_subject(
            db.session,
            route=effective_route,
            subject=subject,
            now_utc=NOW,
        )

    def test_source_owned_overlay_note_resolves_its_cards_without_card_progress(self):
        assert_retired_progress_absent(self, db.session)
        locked = self._locked()
        siblings = lock_study_authority_siblings(
            db.session,
            route=self._route(),
            locked=locked,
            requested_card_id=self.card_ids[1],
        )
        self.assertNotEqual(self.publisher_id, self.learner_id)
        self.assertEqual(siblings.card_ids, self.card_ids)
        self.assertEqual(dict(siblings.progress_by_card_id), {})

    def test_retired_occurrence_card_stays_a_sibling_with_its_legacy_id(self):
        # An open session may have dealt a Card before its occurrence retired,
        # and history may name it by its pre-P11 ID (ADR P11).
        retired = StudyApplication.query.filter_by(template_id="sibling-template-b").one()
        card = Card.query.filter_by(note_id="sibling-source-note", application_id=retired.id).one()
        archive_wire_alias(db.session, card, "sibling-card-b")
        retired.status_code = "RETIRED"
        db.session.commit()
        retired_card_id = f"sibling-source-note.{retired.id}"
        self.assertEqual(Card.query.filter_by(note_id="sibling-source-note").count(), 1)
        siblings = lock_study_authority_siblings(
            db.session,
            route=self._route(),
            locked=self._locked(),
            requested_card_id=retired_card_id,
        )
        self.assertEqual(siblings.card_ids, self.card_ids)
        self.assertEqual(siblings.legacy_card_ids, ("sibling-card-b",))
        self.assertEqual(siblings.history_card_ids, (*self.card_ids, "sibling-card-b"))

    def test_requested_card_must_belong_to_the_locked_subject(self):
        locked = self._locked()
        with self.assertRaises(StudyAuthorityFenceError) as failure:
            lock_study_authority_siblings(
                db.session,
                route=self._route(),
                locked=locked,
                requested_card_id="another-card",
            )
        self.assertEqual(failure.exception.code, "CARD_OUTSIDE_AUTHORITY_SUBJECT")

    def test_detached_or_noncanonical_subject_identity_fails_closed(self):
        subject = db.session.get(StudyProgressSubject, self.subject_id)
        subject.logical_note_key = b"another-note"
        db.session.commit()
        locked = self._locked()
        with self.assertRaises(StudyAuthorityFenceError) as identity:
            lock_study_authority_siblings(
                db.session,
                route=self._route(),
                locked=locked,
            )
        self.assertEqual(identity.exception.code, "UNSUPPORTED_AUTHORITY_IDENTITY")
        db.session.rollback()

        subject = db.session.get(StudyProgressSubject, self.subject_id)
        subject.logical_note_key = b"sibling-source-note"
        subject.live_note_id = None
        db.session.commit()
        locked = self._locked()
        with self.assertRaises(StudyAuthorityFenceError) as detached:
            lock_study_authority_siblings(
                db.session,
                route=self._route(),
                locked=locked,
            )
        self.assertEqual(detached.exception.code, "DETACHED_AUTHORITY_SUBJECT")

    def test_legacy_route_and_cardless_note_fail_closed(self):
        with self.assertRaises(StudyAuthorityFenceError) as mode:
            self._locked(self._route(mode="LEGACY"))
        self.assertEqual(mode.exception.code, "AUTHORITY_MODE_CONFLICT")
        db.session.rollback()

        # A NoteType without any occurrence presents its Notes through nothing.
        StudyApplication.query.delete(synchronize_session=False)
        db.session.commit()
        locked = self._locked()
        with self.assertRaises(StudyAuthorityFenceError) as empty:
            lock_study_authority_siblings(
                db.session,
                route=self._route(),
                locked=locked,
            )
        self.assertEqual(empty.exception.code, "AUTHORITY_SIBLINGS_EMPTY")


if __name__ == "__main__":
    unittest.main()
