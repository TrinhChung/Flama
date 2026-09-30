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
from app.repositories.study_progress_shadow_repository import ensure_and_lock_subject
from app.services import study_progress_lifecycle_mirror_service as lifecycle
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from app.services.study_note_pristine_service import materialize_pristine_notes
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User

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
        # two Templates (fan-in of two Cards) and one Template.
        for templates, count in ((2, 4), (1, 3)):
            note_type = NoteType(name=f"Pristine {templates}", user_id=self.user_id)
            db.session.add(note_type)
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
            rows = [Template(note_type_id=note_type.id, name=f"T{index}", front_html="{{Word}}",
                             back_html="{{Word}}", position=index, is_default=index == 0)
                    for index in range(templates)]
            db.session.add_all(rows)
            db.session.flush()
            for number in range(count):
                note = Note(user_id=self.user_id, note_type_id=note_type.id, deck_id=deck.id,
                            field_values={"Word": f"w{templates}-{number}"})
                db.session.add(note)
                db.session.flush()
                db.session.add_all(Card(note_id=note.id, template_id=template.id) for template in rows)
                self.note_ids.append(str(note.id))
        db.session.commit()
        # One Note already has a pristine envelope, another also has a token.
        ensure_and_lock_subject(db.session, learner_user_id=self.user_id, logical_note_key=self.note_ids[1],
                                live_note_id=self.note_ids[1], now_utc=NOW)
        subject = ensure_and_lock_subject(db.session, learner_user_id=self.user_id,
                                          logical_note_key=self.note_ids[5], live_note_id=self.note_ids[5],
                                          now_utc=NOW)
        db.session.add(StudyAuthoritySubjectToken(subject_id=subject.id, subject_generation=1,
                                                  authority_revision=0, semantic_state_hash=None,
                                                  created_at=NOW, updated_at=NOW))
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

    def test_bulk_path_writes_exactly_what_the_per_note_path_writes(self):
        self._per_note()
        expected = self._snapshot_uncommitted()
        db.session.rollback()
        self.assertEqual(StudyProgressState.query.count(), 0)
        self.assertEqual((len(expected["states"]), len(expected["contributors"]), len(expected["progress"])),
                         (7, 11, 11))
        self.assertEqual({row["status_code"] for row in expected["subjects"].values()},
                         {"MIRRORED_SINGLE", "MIRRORED_EQUIVALENT_FANIN"})

        route = self._route()
        cards = Card.query.filter(Card.note_id.in_(self.note_ids)).all()
        materialized = materialize_pristine_notes(db.session, route=route, cards=cards,
                                                  starting_ease_by_note_id=self.ease, now_utc=NOW)
        self.assertEqual(materialized, frozenset(self.note_ids))
        actual = self._snapshot_uncommitted()
        self.assertEqual(len(actual["states"]), 7)
        self.assertEqual(len(actual["contributors"]), 11)
        for table in expected:
            self.assertEqual(actual[table], expected[table], table)
        db.session.commit()

        runner = self.app.test_cli_runner()
        audit = runner.invoke(args=["study-authority-read-audit", "--user-id", str(self.user_id)])
        self.assertEqual(audit.exit_code, 0, audit.output)
        self.assertEqual(json.loads(audit.output.strip().splitlines()[-1])["status"], "PASS")

    def _snapshot_uncommitted(self):
        """Every written column, keyed by Note/Card, inside the open transaction.

        SQLite reuses rolled-back ids, so both runs compare exactly. MySQL
        never reuses AUTO_INCREMENT values; there the id-derived columns
        (progress ids, raw payload id, raw and vector hashes) are left out.
        """
        db.session.flush()
        exact = db.engine.dialect.name == "sqlite"
        id_derived = set() if exact else {
            "id", "source_progress_id", "live_card_progress_id", "raw_progress_hash",
            "raw_payload_size", "authority_vector_hash", "lineage_vector_hash",
        }
        key_by_subject = {
            int(row.id): bytes(row.logical_note_key).decode()
            for row in StudyProgressSubject.query.filter_by(learner_user_id=self.user_id)
        }
        card_by_contributor = {}
        snapshot = {"subjects": {}, "tokens": {}, "progress": {}, "contributors": {}, "availability": {},
                    "states": {}}
        for row in StudyProgressSubject.query.filter_by(learner_user_id=self.user_id):
            snapshot["subjects"][key_by_subject[int(row.id)]] = _columns(row, skip={"id"} | id_derived)
        for row in StudyAuthoritySubjectToken.query.all():
            snapshot["tokens"][key_by_subject[int(row.subject_id)]] = _columns(row, skip={"subject_id"})
        for row in CardProgress.query.filter_by(user_id=self.user_id):
            snapshot["progress"][str(row.card_id)] = _columns(row, skip=id_derived)
        for row in StudyProgressContributor.query.all():
            card_by_contributor[int(row.id)] = str(row.live_card_id)
            values = _columns(row, skip={"id", "subject_id"} | id_derived)
            if not exact:
                payload = values["raw_payload"]
                payload = json.loads(payload) if isinstance(payload, str) else dict(payload)
                payload.pop("id", None)
                values["raw_payload"] = payload
            snapshot["contributors"][str(row.live_card_id)] = values
        for row in StudyProgressAvailability.query.all():
            snapshot["availability"][card_by_contributor[int(row.contributor_id)]] = _columns(
                row, skip={"contributor_id", "subject_id"})
        for row in StudyProgressState.query.all():
            snapshot["states"][key_by_subject[int(row.subject_id)]] = _columns(row, skip={"subject_id"})
        return json.loads(json.dumps(snapshot, sort_keys=True, default=str))

    def test_the_comparison_sees_a_different_starting_ease(self):
        self._per_note()
        expected = self._snapshot_uncommitted()
        db.session.rollback()
        lifecycle.materialize_pristine_notes_bulk(
            db.session, route=self._route(), note_ids=self.note_ids,
            starting_ease_by_note_id={note_id: 2.9 for note_id in self.note_ids}, now_utc=NOW)
        actual = self._snapshot_uncommitted()
        # Without exact ids (MySQL) the subject differs only in its vector hashes.
        tables = ("progress", "contributors", "states", "tokens")
        if db.engine.dialect.name == "sqlite":
            tables += ("subjects",)
        for table in tables:
            self.assertNotEqual(actual[table], expected[table], table)
        db.session.rollback()

    def test_bulk_path_refuses_what_the_per_note_path_refuses(self):
        card = Card.query.filter_by(note_id=self.note_ids[2]).first()
        db.session.add(CardProgress(user_id=self.user_id, card_id=card.id, queue="new", ease_factor=2.5,
                                    revision=0, created_at=NOW, updated_at=NOW))
        db.session.flush()
        with self.assertRaises(StudyAuthorityFenceError) as refused:
            lifecycle.materialize_pristine_notes_bulk(
                db.session, route=self._route(), note_ids=self.note_ids,
                starting_ease_by_note_id=self.ease, now_utc=NOW)
        self.assertEqual(refused.exception.code, "AUTHORITY_PROGRESS_EXISTS")
        db.session.rollback()

        token = StudyAuthoritySubjectToken.query.one()
        token.semantic_state_hash = b"\x01" * 32
        db.session.flush()
        with self.assertRaises(StudyAuthorityFenceError) as refused:
            lifecycle.materialize_pristine_notes_bulk(
                db.session, route=self._route(), note_ids=self.note_ids,
                starting_ease_by_note_id=self.ease, now_utc=NOW)
        self.assertEqual(refused.exception.code, "AUTHORITY_STATE_DIVERGED")
        db.session.rollback()

        subject = StudyProgressSubject.query.filter_by(logical_note_key=self.note_ids[1].encode()).one()
        subject.status_code = "MIRRORED_SINGLE"
        db.session.flush()
        with self.assertRaises(StudyAuthorityFenceError) as refused:
            lifecycle.materialize_pristine_notes_bulk(
                db.session, route=self._route(), note_ids=self.note_ids,
                starting_ease_by_note_id=self.ease, now_utc=NOW)
        self.assertEqual(refused.exception.code, "AUTHORITY_SUBJECT_EXISTS")
        db.session.rollback()
        self.assertEqual(StudyProgressState.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
