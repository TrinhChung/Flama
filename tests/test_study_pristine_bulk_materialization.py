"""P5-11c: set-wise first-state materialization writes what the per-Note path writes."""

from datetime import datetime
import json
import unittest

from sqlalchemy import select

from app import create_app
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.repositories.study_progress_subject_repository import ensure_and_lock_subject
from app.services import study_progress_lifecycle_mirror_service as lifecycle
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from app.services.study_note_pristine_service import materialize_pristine_notes
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User
from tests.study_note_fixtures import attach_template

NOW = datetime(2026, 9, 30, 12, 0, 0)


def _columns(row, *, skip=()):
    return {
        column.key: (bytes(value).hex() if isinstance(value, (bytes, bytearray, memoryview)) else value)
        for column in row.__table__.columns
        if column.key not in skip
        for value in [getattr(row, column.key)]
    }


class StudyPristineBulkMaterializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
        })

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        user = User(username="pristine-bulk", email="pristine-bulk@example.test")
        db.session.add(user)
        db.session.flush()
        self.user_id = int(user.id)
        stage_note_authority_enrollment(db.session, learner_user_id=self.user_id, now_utc=NOW)
        db.session.commit()
        deck = Deck(name="Pristine", owner_user_id=self.user_id)
        db.session.add(deck)
        db.session.flush()
        self.note_ids = []
        # Notes written after enrollment without materialization stay pristine:
        # two Templates (two Cards per Note) and one Template.
        for templates, count in ((2, 4), (1, 3)):
            note_type = NoteType(name=f"Pristine {templates}", user_id=self.user_id)
            db.session.add(note_type)
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
            rows = [attach_template(db.session, note_type_id=note_type.id, owner_user_id=self.user_id,
                             name=f"T{index}", front_html="{{Word}}",
                             back_html="{{Word}}", position=index, is_default=index == 0)
                    for index in range(templates)]
            db.session.add_all(rows)
            db.session.flush()
            for number in range(count):
                note = Note(user_id=self.user_id, note_type_id=note_type.id, deck_id=deck.id,
                            field_values={"Word": f"w{templates}-{number}"})
                db.session.add(note)
                db.session.flush()
                self.note_ids.append(str(note.id))
        db.session.commit()
        # Two Notes already have a pristine row without state.
        for index in (1, 5):
            ensure_and_lock_subject(db.session, learner_user_id=self.user_id, logical_note_key=self.note_ids[index],
                                    live_note_id=self.note_ids[index], now_utc=NOW)
        db.session.commit()
        self.ease = {note_id: 2.5 if index % 2 else 2.3 for index, note_id in enumerate(self.note_ids)}

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _route(self):
        return lock_study_authority_route(db.session, learner_user_id=self.user_id, allow_note_authority=True)

    def _per_note(self):
        route = self._route()
        for note_id in sorted(self.note_ids, key=str.encode):
            siblings = tuple(db.session.execute(
                select(Card).where(Card.note_id == note_id).order_by(Card.id.asc())).scalars())
            lifecycle.materialize_pristine_note_authority(
                db.session, route=route, note=db.session.get(Note, note_id), cards=siblings,
                starting_ease=self.ease[note_id], provenance_code="NATIVE_DIRECT", now_utc=NOW)
        db.session.flush()

    def _rows(self):
        """Every written column of the learner's rows, keyed by Note."""
        db.session.flush()
        exact = db.engine.dialect.name == "sqlite"
        skip = {"id"} if exact else {"id", "created_at", "updated_at"}
        rows = {
            bytes(row.logical_note_key).decode(): _columns(row, skip=skip)
            for row in StudyProgressSubject.query.filter_by(learner_user_id=self.user_id)
        }
        return json.loads(json.dumps(rows, sort_keys=True, default=str))

    def test_bulk_path_writes_exactly_what_the_per_note_path_writes(self):
        self._per_note()
        expected = self._rows()
        db.session.rollback()
        self.assertEqual(len(expected), 7)
        self.assertEqual({row["status_code"] for row in expected.values()},
                         {"MIRRORED_SINGLE", "MIRRORED_EQUIVALENT_FANIN"})
        self.assertTrue(all(row["state_payload"] is not None for row in expected.values()))
        self.assertEqual({row["authority_revision"] for row in expected.values()}, {0})

        route = self._route()
        cards = Card.query.filter(Card.note_id.in_(self.note_ids)).all()
        materialized = materialize_pristine_notes(db.session, route=route, cards=cards,
                                                  starting_ease_by_note_id=self.ease, now_utc=NOW)
        self.assertEqual(materialized, frozenset(self.note_ids))
        self.assertEqual(self._rows(), expected)
        db.session.commit()

        runner = self.app.test_cli_runner()
        audit = runner.invoke(args=["study-authority-read-audit", "--user-id", str(self.user_id)])
        self.assertEqual(audit.exit_code, 0, audit.output)
        self.assertEqual(json.loads(audit.output.strip().splitlines()[-1])["status"], "PASS")

    def test_the_comparison_sees_a_different_starting_ease(self):
        self._per_note()
        expected = self._rows()
        db.session.rollback()
        lifecycle.materialize_pristine_notes_bulk(
            db.session, route=self._route(), note_ids=self.note_ids,
            starting_ease_by_note_id={note_id: 2.9 for note_id in self.note_ids}, now_utc=NOW)
        self.assertNotEqual(self._rows(), expected)
        db.session.rollback()

    def test_bulk_path_refuses_what_the_per_note_path_refuses(self):
        subject = StudyProgressSubject.query.filter_by(logical_note_key=self.note_ids[1].encode()).one()
        subject.status_code = "MIRRORED_SINGLE"
        db.session.flush()
        with self.assertRaises(StudyAuthorityFenceError) as refused:
            lifecycle.materialize_pristine_notes_bulk(
                db.session, route=self._route(), note_ids=self.note_ids,
                starting_ease_by_note_id=self.ease, now_utc=NOW)
        self.assertEqual(refused.exception.code, "AUTHORITY_SUBJECT_EXISTS")
        db.session.rollback()
        self.assertEqual(
            StudyProgressSubject.query.filter(StudyProgressSubject.state_payload.isnot(None)).count(), 0)


if __name__ == "__main__":
    unittest.main()
