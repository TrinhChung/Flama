"""NOTE writes avoid locking absent rows, and deadlocks rerun instead of leaking.

A locking read of an absent unique key or an empty range takes an InnoDB gap
lock that neighbouring learners' inserts share, so concurrent first reviews
and sign-ups deadlock (see scripts/probe_p5_concurrency_mysql.py). SQLite does
not lock, so these tests pin the statement shapes that MySQL would lock and
the fallbacks that keep results exact.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import event as sql_event, select
from sqlalchemy.exc import IntegrityError, OperationalError

from app import create_app
from app.services.db_errors import domain_error_code, run_with_deadlock_retry
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from app.services.study_authority_evidence_service import _lock_current_lineage_refs
from app.services.study_authority_receipt_service import StudyAuthorityReceiptError
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_lineage_ref import StudyProgressLineageRef
from models.template import Template
from models.user import User


def _mysql_error(number: int) -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception(number, "simulated"))


class DatabaseErrorClassificationTests(unittest.TestCase):
    def test_sqlalchemy_codes_are_not_domain_refusals(self):
        self.assertIsNone(domain_error_code(_mysql_error(1213)))
        self.assertIsNone(domain_error_code(IntegrityError("INSERT", {}, Exception(1062, "dup"))))
        self.assertEqual(
            domain_error_code(StudyAuthorityReceiptError("AUTHORITY_OPERATION_REUSED", "x")),
            "AUTHORITY_OPERATION_REUSED",
        )
        self.assertIsNone(domain_error_code(ValueError("plain")))

    def test_deadlock_victims_rerun_but_other_errors_do_not(self):
        session = type("Session", (), {"rollback": lambda self: None})()
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise _mysql_error(1213)
            return "done"

        with patch("app.services.db_errors.time.sleep"):
            self.assertEqual(run_with_deadlock_retry(flaky, session=session, label="t"), "done")
            self.assertEqual(len(calls), 3)

            calls.clear()

            def always_deadlocks():
                calls.append(1)
                raise _mysql_error(1213)

            with self.assertRaises(OperationalError):
                run_with_deadlock_retry(always_deadlocks, session=session, label="t")
            self.assertEqual(len(calls), 3)

            calls.clear()

            def lock_wait_timeout():
                calls.append(1)
                raise _mysql_error(1205)

            with self.assertRaises(OperationalError):
                run_with_deadlock_retry(lock_wait_timeout, session=session, label="t")
            self.assertEqual(len(calls), 1)


class NoteWriteGapLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
            "STUDY_WIRE_V4_ENABLED": True, "STUDY_ASYNC_BATCH_ENABLED": False})

    def setUp(self):
        self.addCleanup(self._cleanup)
        with self.app.app_context():
            db.create_all()
            user = User(username="gap-locks", email="gap-locks@example.test")
            db.session.add(user)
            db.session.flush()
            deck = Deck(name="Gap locks", owner_user_id=user.id)
            note_type = NoteType(name="Gap locks", user_id=user.id)
            db.session.add_all([deck, note_type])
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
            note = Note(user_id=user.id, note_type_id=note_type.id, deck_id=deck.id, field_values={"Word": "w"})
            db.session.add(note)
            db.session.flush()
            template = Template(note_type_id=note_type.id, name="Card 1",
                front_html="{{Word}}", back_html="{{Word}}", is_default=True)
            db.session.add(template)
            db.session.flush()
            card = Card(note_id=note.id, template_id=template.id)
            db.session.add(card)
            db.session.commit()
            self.user_id, self.deck_id, self.card_id = user.id, deck.id, card.id
            stage_note_authority_enrollment(db.session, learner_user_id=self.user_id,
                now_utc=datetime.now(timezone.utc).replace(tzinfo=None))
            db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as login:
            login["_user_id"], login["_fresh"] = str(self.user_id), True

    def _cleanup(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @contextmanager
    def _statements(self):
        seen: list[str] = []
        with self.app.app_context():
            engine = db.engine

        def capture(_conn, _cursor, statement, _params, _context, _many):
            seen.append(" ".join(statement.split()))

        sql_event.listen(engine, "before_cursor_execute", capture)
        try:
            yield seen
        finally:
            sql_event.remove(engine, "before_cursor_execute", capture)

    def _answer(self, operation_key=None):
        response = self.client.post(f"/api/study/{self.card_id}/answer", json={
            "rating": "good", "operation_key": operation_key or str(uuid4()),
            "duration_ms": 500, "scope": "deck", "scope_id": self.deck_id})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_first_review_never_reads_absent_receipt_fact_or_lineage_rows_with_locking_shapes(self):
        with self._statements() as seen:
            self._answer()
        receipt_entity_lookups = [s for s in seen if "FROM study_authority_command_receipts" in s
                                  and "study_authority_command_receipts.response_payload" in s]
        fact_lookups = [s for s in seen if "FROM study_progress_history_facts" in s
                        and "fact_identity_hash =" in s]
        lineage_ranges = [s for s in seen if "study_progress_lineage_refs.source_row_key" in s
                          and "study_progress_lineage_refs.contributor_id IN" in s]
        self.assertEqual(receipt_entity_lookups, [])
        self.assertEqual(fact_lookups, [])
        self.assertEqual(lineage_ranges, [])

    def test_retry_still_replays_the_original_receipt(self):
        key = str(uuid4())
        first = self._answer(key)
        second = self._answer(key)
        self.assertFalse(first["authority"]["replayed"])
        self.assertTrue(second["authority"]["replayed"])
        self.assertEqual(first["authority"]["authority_revision"], second["authority"]["authority_revision"])

    def test_lineage_lock_matches_range_read_and_falls_back_on_unproven_hash(self):
        self._answer()
        self._answer()
        with self.app.app_context():
            contributor_ids = tuple(sorted(
                db.session.execute(select(StudyProgressContributor.id)).scalars()))
            expected = sorted(
                (row.contributor_id, row.ref_kind, bytes(row.source_row_key), row.id)
                for row in db.session.execute(select(StudyProgressLineageRef)).scalars())
            self.assertTrue(expected)
        with self._statements() as seen, self.app.app_context():
            proven = _lock_current_lineage_refs(db.session, contributor_ids=contributor_ids)
            self.assertEqual(
                [(r.contributor_id, r.ref_kind, bytes(r.source_row_key), r.id) for r in proven], expected)
            db.session.rollback()
        self.assertFalse([s for s in seen if "study_progress_lineage_refs.source_row_key" in s
                          and "study_progress_lineage_refs.contributor_id IN" in s])

        with self.app.app_context():
            contributor = db.session.get(StudyProgressContributor, contributor_ids[0])
            contributor.lineage_vector_hash = b"\x01" * 32
            db.session.commit()
        with self._statements() as seen, self.app.app_context():
            fallback = _lock_current_lineage_refs(db.session, contributor_ids=contributor_ids)
            self.assertEqual(
                [(r.contributor_id, r.ref_kind, bytes(r.source_row_key), r.id) for r in fallback], expected)
            db.session.rollback()
        self.assertTrue([s for s in seen if "study_progress_lineage_refs.source_row_key" in s
                         and "study_progress_lineage_refs.contributor_id IN" in s])

    def test_new_learner_enrollment_locks_no_absent_enrollment_row(self):
        from app.services.auth_service import register_user_and_commit

        with patch.dict(self.app.config, STUDY_NEW_LEARNER_NOTE_ENABLED=True):
            with self._statements() as seen, self.app.app_context():
                user = register_user_and_commit("fresh@example.test", "fresh_user", "Probe-Password-9731!")
                user_id = int(user.id)
        entity_reads = [s for s in seen if "FROM study_authority_enrollments" in s
                        and "study_authority_enrollments.mode_code" in s and s.startswith("SELECT")]
        self.assertEqual(entity_reads, [])
        with self.app.app_context():
            enrollment = db.session.get(StudyAuthorityEnrollment, user_id)
            self.assertEqual((enrollment.mode_code, enrollment.epoch), ("NOTE", 1))


if __name__ == "__main__":
    unittest.main()
