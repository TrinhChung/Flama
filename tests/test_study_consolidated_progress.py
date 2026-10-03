"""P10: NOTE progress on the consolidated subject row (CONSOLIDATED_V1, ADR P10)."""

from __future__ import annotations

from datetime import datetime, timezone
import re
import traceback
import unittest
from unittest import mock
from uuid import uuid4

from sqlalchemy import event

from app.services import flashcard_content_service as content
from app.services.study_composition_service import make_compatibility_composition_id
from app.services.study_consolidated_switch_service import apply_consolidated_switch
from models import db
from models.card import Card
from models.note import Note
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_subject import StudyProgressSubject
from tests import test_study_direct_note_replay as fixtures
from tests import test_study_algorithm_switch as switch_tests
from tests import test_study_note_batch as batch_tests
from tests import test_study_note_overlay as overlay_tests
from tests import test_study_note_templates as template_tests

PROFILES = frozenset({"PROJECTION_V1", "CANONICAL_V1", "CONSOLIDATED_V1"})
OLD_TABLES = re.compile(
    r"\b(card_progress|study_progress_states|study_authority_subject_tokens|"
    r"study_progress_contributors|study_progress_availability|study_progress_lineage_refs)\b",
    re.IGNORECASE,
)


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class StudyConsolidatedProgressTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup

    def setUp(self):
        fixtures.StudyDirectNoteReplayTests.setUp(self)
        self._consolidate()

    def _consolidate(self):
        supported = mock.patch(
            "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", PROFILES
        )
        supported.start()
        self.addCleanup(supported.stop)
        self.app.config["STUDY_WIRE_V4_ENABLED"] = True
        self.addCleanup(self.app.config.__setitem__, "STUDY_WIRE_V4_ENABLED", False)
        with self.app.app_context():
            # As in production: CANONICAL_V1 (P9-06), then the P10 switch copies onto the rows.
            db.session.add(StudyAuthorityStorageProfile(
                id=1, profile_code="CANONICAL_V1", epoch=2, created_at=_now(), updated_at=_now()))
            db.session.commit()
            self.switch = apply_consolidated_switch(db.session, now_utc=_now())
            db.session.commit()
            card = db.session.get(Card, self.card_ids[0])
            self.note_id = card.note_id
            self.note_type_id = card.note.note_type_id
            self.template_ids = [db.session.get(Card, card_id).template_id for card_id in self.card_ids]
            engine = db.engine
        self.old_table_statements = []

        def record(_conn, _cursor, statement, *_args):
            match = OLD_TABLES.search(statement)
            if not match:
                return
            verb = statement.split()[0].upper()
            # Deleting Content still clears its frozen card_progress rows, as
            # under CANONICAL_V1 (an explicit DELETE or the ORM Card cascade).
            if match.group(1).lower() == "card_progress" and (verb == "DELETE" or any(
                frame.name == "cascade_iterator"
                or frame.filename.replace("\\", "/").endswith(("orm/dependency.py", "orm/unitofwork.py"))
                for frame in traceback.extract_stack()
            )):
                return
            self.old_table_statements.append(f"{verb} {match.group(1)}")

        event.listen(engine, "before_cursor_execute", record)
        self.addCleanup(lambda: event.remove(engine, "before_cursor_execute", record))

    def _answer(self, card_id, rating="good", operation_key=None):
        response = self.client.post(f"/api/study/{card_id}/answer", json={
            "rating": rating, "operation_key": operation_key or str(uuid4()), "duration_ms": 500,
            "scope": "deck", "scope_id": self.deck_id})
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def _subject(self):
        return StudyProgressSubject.query.filter_by(
            learner_user_id=self.user_id, logical_note_key=self.note_id.encode()).one()

    def test_direct_answers_keep_the_whole_progress_on_one_row(self):
        operation_key = str(uuid4())
        first = self._answer(self.card_ids[0], operation_key=operation_key)
        self.assertEqual(first["authority"]["replayed"], False)
        second = self._answer(self.card_ids[1], rating="easy")
        replay = self._answer(self.card_ids[0], operation_key=operation_key)
        self.assertEqual(replay["authority"]["replayed"], True)
        self.assertEqual(replay["intervals_preview"], first["intervals_preview"])
        self.assertEqual(self.old_table_statements, [])
        with self.app.app_context():
            subject = self._subject()
            self.assertEqual(int(subject.authority_revision), 2)
            self.assertEqual(subject.state_payload["type"], subject.normalized_queue)
            self.assertEqual(subject.history_completeness_code, "HISTORY_NATIVE_COMPLETE")
            self.assertEqual(subject.current_provenance_code, "NATIVE_DIRECT")
            self.assertEqual(len(subject.semantic_state_hash), 32)
            facts = StudyProgressHistoryFact.query.order_by(StudyProgressHistoryFact.id).all()
            self.assertEqual([fact.contributor_id for fact in facts], [None, None])
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 2)
            self.assertEqual({event.note_id for event in ReviewEvent.query.all()}, {self.note_id})
        self.assertNotEqual(first["intervals_preview"], second["intervals_preview"])

    def _open(self, template_index=0):
        opened = self.client.post("/api/study/sessions", json={
            "scope": "deck", "scope_id": self.deck_id,
            "composition_id": make_compatibility_composition_id(self.note_type_id, self.template_ids[template_index]),
            "accepted_session_schema_versions": ["study-session.v4"],
            "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
        })
        self.assertEqual(opened.status_code, 201, opened.get_json())
        return opened.get_json()

    def _commit(self, snapshot, ratings):
        card = snapshot["cards"][0]
        policy = snapshot["policies"][card["policy_key"]]
        events = []
        for sequence, rating in enumerate(ratings, start=1):
            event_id = str(uuid4())
            events.append({
                "event_id": event_id, "sequence": sequence, "card_id": card["card_id"], "rating": rating,
                "policy_key": card["policy_key"], "scheduler_offset_ms": 1000 * sequence, "duration_ms": 900,
                "action_key": f"review.{rating}", "action_contract_version": "1",
                "trigger_key": f"scheduler.review.{rating}", "trigger_contract_version": "1",
                "algorithm_key": snapshot["scheduler_algorithm"], "algorithm_version": snapshot["algorithm_version"],
                "config_schema_version": policy["config_schema_version"], "config_hash": policy["config_hash"],
                "study_session_id": snapshot["session_id"], "operation_key": event_id,
                **{key: value for key, value in card["authority_pin"].items() if key != "schema_version"},
            })
        return self.client.post(f"/api/study/sessions/{snapshot['session_id']}/commit", json={
            "schema_version": "study-commit.v3", "commit_id": str(uuid4()),
            "session_token": snapshot["session_token"], "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover", "events": events, "final_states": []})

    def _add_note(self, word):
        with self.app.app_context():
            template_card = db.session.get(Card, self.card_ids[0])
            note = Note(user_id=self.user_id, note_type_id=self.note_type_id, deck_id=self.deck_id,
                        field_values={"Word": word})
            db.session.add(note)
            db.session.flush()
            db.session.add(Card(note_id=note.id, template_id=template_card.template_id))
            db.session.commit()
            return note.id

    def test_switch_copies_the_enrolled_state_onto_the_row(self):
        self.assertEqual((self.switch["profile"], self.switch["epoch"]), ("CONSOLIDATED_V1", 3))
        with self.app.app_context():
            subject = self._subject()
            self.assertEqual((int(subject.authority_revision), subject.normalized_queue), (0, "new"))
            self.assertIsNotNone(subject.state_payload)

    def test_session_materializes_new_notes_and_commits_on_the_row(self):
        new_note_id = self._add_note("after switch")
        snapshot = self._open()
        self.assertEqual({card["state"]["type"] for card in snapshot["cards"]}, {"new"})
        with self.app.app_context():
            fresh = StudyProgressSubject.query.filter_by(
                learner_user_id=self.user_id, logical_note_key=new_note_id.encode()).one()
            self.assertEqual((int(fresh.authority_revision), fresh.normalized_queue), (0, "new"))
            self.assertEqual(fresh.current_provenance_code, "NATIVE_DIRECT")
            self.assertEqual(fresh.history_completeness_code, "HISTORY_NATIVE_COMPLETE")
        committed = self._commit(snapshot, ["good", "good"])
        self.assertEqual(committed.status_code, 200, committed.get_json())
        self.assertEqual(self.old_table_statements, [])
        with self.app.app_context():
            subject = self._subject()
            self.assertEqual(int(subject.authority_revision), 2)
            self.assertEqual(subject.current_provenance_code, "NATIVE_SESSION")
            self.assertEqual(StudyProgressHistoryFact.query.count(), 2)

    def test_readers_answer_from_the_row(self):
        self._answer(self.card_ids[0])
        self.old_table_statements.clear()
        for path in (
            "/api/dashboard",
            "/api/statistics/overview",
            "/api/statistics/today-future?scope=collection",
            f"/api/statistics/today-future?scope=deck&deck_id={self.deck_id}",
            f"/api/study/next?scope=deck&scope_id={self.deck_id}",
            "/api/browse/decks/tree",
            f"/api/browse/cards?deck_id={self.deck_id}",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, (path, response.get_json()))
        self.assertEqual(self.old_table_statements, [])
        # The Note's two Cards share one learning state: two Cards, or one Note (D6-04).
        for count_by_note, learning in ((False, 2), (True, 1)):
            with self.subTest(count_by_note=count_by_note):
                self.app.config["STUDY_NOTE_COUNT_ENABLED"] = count_by_note
                summary = self.client.get("/api/dashboard").get_json()["summary"]
                self.assertEqual((summary["new"], summary["learning"], summary["due"]), (0, learning, 0))
        self.app.config["STUDY_NOTE_COUNT_ENABLED"] = False

    def _row(self):
        db.session.expire_all()
        subject = StudyProgressSubject.query.filter_by(
            learner_user_id=self.user_id, logical_note_key=self.note_id.encode()).one()
        return {
            "status": subject.status_code,
            "generation": int(subject.subject_generation),
            "revision": int(subject.authority_revision),
            "type": None if subject.state_payload is None else subject.state_payload["type"],
            "reps": None if subject.state_payload is None else int(subject.state_payload["reps"]),
            "queue": subject.normalized_queue,
            "hash": None if subject.semantic_state_hash is None else bytes(subject.semantic_state_hash),
            "provenance": subject.current_provenance_code,
            "live": subject.live_note_id is not None,
        }

    def test_study_next_orders_from_the_rows_and_verifies_the_returned_card(self):
        ok = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(ok.status_code, 200, ok.get_json())
        self.assertIn(ok.get_json()["card_id"], self.card_ids)
        with self.app.app_context():
            # A row whose availability disagrees with its state: ordered as due,
            # then refused by the full read of the returned Card.
            subject = self._subject()
            subject.normalized_queue, subject.due_day = "review", 0
            db.session.commit()
        refused = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual((refused.status_code, refused.get_json()["error"]),
                         (409, "AUTHORITY_READ_PARITY_DIVERGED"), refused.get_json())

    def test_lifecycle_story_stays_on_the_row(self):
        self._answer(self.card_ids[0])
        self._answer(self.card_ids[0], rating="hard")
        with self.app.app_context():
            reviewed = self._row()
            self.assertEqual((reviewed["generation"], reviewed["revision"], reviewed["reps"]), (1, 2, 2))
            # ADR P10 §2.3: Template add/remove neither copies nor detaches progress.
            template_tests.StudyNoteTemplateTests._update(self, {"added": [{"name": "Reverse"}]})
            db.session.commit()
            self.assertEqual(Card.query.count(), 3)
            self.assertEqual(self._row(), reviewed)
            template_tests.StudyNoteTemplateTests._update(self, {"removed": ["Card 1"]}, confirmed=True)
            db.session.commit()
            self.assertEqual(Card.query.count(), 2)
            self.assertEqual(self._row(), reviewed)
            surviving = sorted(card.id for card in Card.query.all())
        next_card = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_card.status_code, 200, next_card.get_json())

        reset = self.client.post(f"/api/decks/{self.deck_id}/progress-reset")
        self.assertEqual(reset.status_code, 200, reset.get_json())
        self.assertEqual(reset.get_json()["deleted_progress_count"], 2)
        with self.app.app_context():
            after_reset = self._row()
            self.assertEqual(
                {key: after_reset[key] for key in ("generation", "revision", "type", "reps", "queue", "provenance")},
                {"generation": 2, "revision": 3, "type": "new", "reps": 0, "queue": "new",
                 "provenance": "UNKNOWN_LEGACY"},
            )
        self._answer(surviving[0])
        with self.app.app_context():
            answered = self._row()
            self.assertEqual((answered["generation"], answered["revision"], answered["reps"]), (2, 4, 1))
            self.assertEqual(content.delete_note(user_id=self.user_id, note_id=self.note_id), {"success": True})
            deleted = self._row()
            self.assertEqual(
                {key: deleted[key] for key in ("status", "generation", "revision", "type", "queue", "hash", "live")},
                {"status": "TOMBSTONED_SUBJECT_DELETED", "generation": 3, "revision": 5, "type": None,
                 "queue": None, "hash": None, "live": False},
            )
            self.assertEqual(
                [(row.transition_code, int(row.old_generation), int(row.new_generation))
                 for row in StudyProgressLifecycleEvent.query.order_by(StudyProgressLifecycleEvent.id)],
                [("TOMBSTONED_RESET", 1, 2), ("TOMBSTONED_SUBJECT_DELETED", 2, 3)],
            )
            # History and receipts outlive the Note.
            self.assertEqual(StudyProgressHistoryFact.query.count(), 3)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 3)
            self.assertEqual(Card.query.count(), 0)
        self.assertEqual(self.old_table_statements, [])

    def test_mcp_tools_create_review_read_and_delete_on_the_row(self):
        from app.services.mcp import note_tools, study_tools

        with self.app.app_context():
            created = note_tools.create_note(user_id=self.user_id, note_data={
                "deck_id": self.deck_id, "note_type_id": self.note_type_id, "fields": {"Word": "mcp"}})
            note_id = str(created.get("note_id") or created.get("id"))
            row = StudyProgressSubject.query.filter_by(
                learner_user_id=self.user_id, logical_note_key=note_id.encode()).one()
            self.assertEqual((row.normalized_queue, row.current_provenance_code), ("new", "NATIVE_MCP"))
            card_ids = sorted(str(card.id) for card in Card.query.filter_by(note_id=note_id))
            study_tools.submit_review(user_id=self.user_id, card_id=card_ids[0], rating="good",
                                      operation_key=str(uuid4()))
            note = note_tools.get_note(user_id=self.user_id, note_id=note_id)
            # Every sibling reports the Note's one state.
            self.assertEqual({card["reps"] for card in note["cards"]}, {1})
            self.assertEqual(len(note["cards"]), len(card_ids))
            stats = study_tools.get_deck_stats(user_id=self.user_id, deck_id=self.deck_id)
            self.assertEqual(stats["note_count"], 2)
            deleted = note_tools.batch_delete_notes(user_id=self.user_id, note_ids=[note_id], confirm=True)
            self.assertTrue(deleted.get("success", True), deleted)
            db.session.expire_all()
            row = db.session.get(StudyProgressSubject, row.id)
            self.assertEqual((row.status_code, row.live_note_id, row.state_payload),
                             ("TOMBSTONED_SUBJECT_DELETED", None, None))
        self.assertEqual(self.old_table_statements, [])

    def test_deck_purge_tombstones_the_rows_and_keeps_history(self):
        from app.services import deck_management_service
        from models.deck import Deck

        self._answer(self.card_ids[0])
        second_note = self._add_note("purged too")
        snapshot = self._open()
        with self.app.app_context():
            self.assertEqual(deck_management_service.delete_deck_subtree(
                deck_obj=db.session.get(Deck, self.deck_id), user_id=self.user_id, is_admin=True,
                purge=True), "purged")
            db.session.expire_all()
            rows = StudyProgressSubject.query.order_by(StudyProgressSubject.id).all()
            self.assertEqual({row.status_code for row in rows}, {"TOMBSTONED_SUBJECT_DELETED"})
            self.assertEqual({row.live_note_id for row in rows}, {None})
            self.assertEqual({bytes(row.logical_note_key).decode() for row in rows},
                             {self.note_id, second_note})
            self.assertEqual(StudyProgressHistoryFact.query.count(), 1)
            self.assertEqual(Card.query.count(), 0)
            from models.study_session import StudySession

            # Purge removes the deck's sessions, or at least closes them.
            session_row = db.session.get(StudySession, snapshot["session_id"])
            self.assertTrue(session_row is None or session_row.status != "open")
        self.assertEqual(self.old_table_statements, [])


class StudyConsolidatedSwitchCliTests(unittest.TestCase):
    """``flask study-consolidated-switch``: plan, apply, and fail-closed evidence."""

    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    def setUp(self):
        fixtures.StudyDirectNoteReplayTests.setUp(self)
        supported = mock.patch(
            "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", PROFILES
        )
        supported.start()
        self.addCleanup(supported.stop)
        with self.app.app_context():
            db.session.add(StudyAuthorityStorageProfile(
                id=1, profile_code="CANONICAL_V1", epoch=2, created_at=_now(), updated_at=_now()))
            db.session.commit()
        self.runner = self.app.test_cli_runner()

    def _cli(self, *args):
        import json

        result = self.runner.invoke(args=["study-consolidated-switch", *args])
        return result.exit_code, json.loads(result.output.strip().splitlines()[-1])

    def test_plan_apply_and_audit(self):
        self._answer()
        code, plan = self._cli()
        self.assertEqual((code, plan["blockers"], plan["subjects_with_state"]), (0, [], 1))
        code, applied = self._cli("--apply")
        self.assertEqual((code, applied["profile"], applied["epoch"]), (0, "CONSOLIDATED_V1", 3))
        code, again = self._cli()
        self.assertIn("PROFILE_IS_CONSOLIDATED_V1", again["blockers"])
        code, refused = self._cli("--apply")
        self.assertEqual((code, refused["error"]), (1, "PROFILE_NOT_CANONICAL"))
        audit = self.runner.invoke(args=["study-authority-read-audit", "--user-id", str(self.user_id)])
        self.assertEqual(audit.exit_code, 0, audit.output)
        self.assertIn('"status":"PASS"', audit.output)
        self.assertIn('"storage_profile":"CONSOLIDATED_V1"', audit.output)
        # The answered Note keeps its revision across the copy.
        self._answer({**self.payload, "operation_key": str(uuid4())})
        with self.app.app_context():
            self.assertEqual(int(StudyProgressSubject.query.one().authority_revision), 2)

    def test_divergent_evidence_or_a_legacy_learner_blocks_without_writing(self):
        from models.study_progress_availability import StudyProgressAvailability
        from models.user import User
        from models.study_authority_enrollment import StudyAuthorityEnrollment

        self._answer()
        with self.app.app_context():
            row = StudyProgressAvailability.query.first()
            row.normalized_queue = "review" if row.normalized_queue != "review" else "new"
            legacy = User(username="still-legacy", email="still-legacy@example.test")
            db.session.add(legacy)
            db.session.flush()
            db.session.add(StudyAuthorityEnrollment(
                learner_user_id=legacy.id, mode_code="LEGACY", epoch=1, created_at=_now(), updated_at=_now()))
            db.session.commit()
        code, refused = self._cli("--apply")
        self.assertEqual((code, refused["error"]), (1, "SWITCH_BLOCKED"))
        self.assertIn("LEGACY_LEARNERS", refused["blockers"])
        self.assertTrue(any(code.startswith("SUBJECT_EVIDENCE_") for code in refused["blockers"]))
        with self.app.app_context():
            self.assertEqual(db.session.get(StudyAuthorityStorageProfile, 1).profile_code, "CANONICAL_V1")
            self.assertIsNone(StudyProgressSubject.query.one().state_payload)


class StudyConsolidatedAlgorithmSwitchTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _consolidate = StudyConsolidatedProgressTests._consolidate
    _switch = switch_tests.StudyAlgorithmSwitchTests._switch
    _row = StudyConsolidatedProgressTests._row

    def setUp(self):
        switch_tests.StudyAlgorithmSwitchTests.setUp(self)
        self._consolidate()

    def _post_answer(self):
        return self.client.post(f"/api/study/{self.card_ids[0]}/answer", json={
            "rating": "good", "operation_key": str(uuid4()), "duration_ms": 500,
            "scope": "deck", "scope_id": self.deck_id})

    def test_switch_rewrites_the_row_and_keeps_its_cards(self):
        with self.app.app_context():
            before = self._row()
            result = self._switch(switch_tests.SYNTHETIC, operation_key="switch-1", expected=0)
            db.session.commit()
            self.assertFalse(result.replayed)
            after = self._row()
            self.assertEqual((after["revision"], after["generation"]), (1, before["generation"]))
            subject = StudyProgressSubject.query.one()
            self.assertEqual(subject.algorithm_key, switch_tests.SYNTHETIC.key)
            self.assertEqual(subject.normalized_queue, "new")
            self.assertEqual(result.response["projected_card_revisions"],
                             {card_id: 1 for card_id in sorted(self.card_ids)})
            replay = self._switch(switch_tests.SYNTHETIC, operation_key="switch-1", expected=0)
            db.session.commit()
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.response, result.response)
            # ADR P10 §2.3: a new Card inherits the switched row; nothing to re-mirror.
            template_tests.StudyNoteTemplateTests._update(self, {"added": [{"name": "Reverse"}]})
            db.session.commit()
            self.assertEqual(Card.query.count(), 3)
            self.assertEqual(self._row(), after)
        refused = self._post_answer()
        self.assertEqual(refused.status_code, 409, refused.get_json())
        self.assertEqual(refused.get_json()["error"], "ALGORITHM_IDENTITY_CHANGE_UNAUTHORIZED")
        self.assertEqual(self.old_table_statements, [])

    def test_unprojectable_state_writes_nothing_but_a_wider_one_switches(self):
        with self.app.app_context():
            before = self._row()
            self.initializers[switch_tests.SYNTHETIC.key].extra = {"type": "not-a-queue"}
            with self.assertRaises(switch_tests.StudyAlgorithmSwitchError) as failure:
                self._switch(switch_tests.SYNTHETIC)
            self.assertEqual(failure.exception.code, "SWITCH_TARGET_NOT_PROJECTABLE")
            db.session.rollback()
            self.assertEqual(self._row(), before)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 0)
            # No CardProgress rollback projection: extra state fields are the target's own.
            self._switch(switch_tests.UNPROJECTABLE)
            db.session.commit()
            self.assertEqual(int(StudyProgressSubject.query.one().state_payload["wide"]), 1)
        self.assertEqual(self.old_table_statements, [])


class StudyConsolidatedOverlayTests(unittest.TestCase):
    """Logical-overlay installs: the learner's row is keyed on the publisher's Note."""

    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    setUp = StudyConsolidatedProgressTests.setUp
    _consolidate = StudyConsolidatedProgressTests._consolidate
    _install_overlay = overlay_tests.StudyNoteOverlayTests._install_overlay
    _answer_source = overlay_tests.StudyNoteOverlayTests._answer_source
    _source_subject = overlay_tests.StudyNoteOverlayTests._source_subject
    _reader_view = overlay_tests.StudyNoteOverlayTests._reader_view

    def test_overlay_answer_session_reset_and_readers_stay_on_the_row(self):
        from app.services import deck_management_service
        from app.services.scheduler_config_service import resolve_deck_options
        from models.deck import Deck

        self._install_overlay()
        with self.app.app_context():
            pristine = self._reader_view()
            self.assertIsNone(self._source_subject())
        self.assertEqual({row[1] for row in pristine["list"]}, {"new"})
        self._answer_source()
        with self.app.app_context():
            subject = self._source_subject()
            self.assertEqual((int(subject.authority_revision), subject.normalized_queue), (1, "learning"))
            source = db.session.get(Note, self.source_note_id)
            # Overlay-only: the publisher's Note is never mutated.
            self.assertEqual((source.field_values, source.user_id != self.user_id), ({"Word": "共有"}, True))
            studied = self._reader_view()
            self.assertEqual({row[1] for row in studied["list"]}, {"learning"})
            self.assertEqual(studied["list_total"], 2)
            deleted = deck_management_service.reset_deck_progress(
                deck_obj=db.session.get(Deck, self.local_deck_id), user_id=self.user_id)
            self.assertEqual(deleted, 2)
            db.session.expire_all()
            subject = self._source_subject()
            self.assertEqual((int(subject.authority_revision), subject.normalized_queue), (2, "new"))
            expected_ease = resolve_deck_options(user_id=self.user_id, deck_id=self.local_deck_id).startingEase
            from app.services.study_progress_shadow_codec import decode_float

            self.assertEqual(decode_float(subject.state_payload["ease"], field_name="ease"), float(expected_ease))
            self.assertEqual(self._reader_view()["list"], pristine["list"])
        self.assertEqual(self.old_table_statements, [])

    def test_v4_session_open_materializes_the_overlay_row(self):
        self._install_overlay()
        compositions = self.client.get(f"/api/study/scopes/deck/{self.local_deck_id}/compositions")
        self.assertEqual(compositions.status_code, 200, compositions.get_json())
        opened = self.client.post("/api/study/sessions", json={
            "scope": "deck", "scope_id": self.local_deck_id,
            "composition_id": compositions.get_json()["compositions"][0]["composition_id"],
            "accepted_session_schema_versions": ["study-session.v4"]})
        self.assertEqual(opened.status_code, 201, opened.get_json())
        with self.app.app_context():
            subject = self._source_subject()
            self.assertEqual((int(subject.authority_revision), subject.normalized_queue), (0, "new"))
        self.assertEqual(self.old_table_statements, [])


class StudyConsolidatedNoteBatchTests(unittest.TestCase):
    """Async NOTE batches (worker path) commit on the consolidated row."""

    setUpClass = classmethod(batch_tests.StudyNoteBatchTests.setUpClass.__func__)
    _seed = batch_tests.StudyNoteBatchTests._seed
    _cleanup = batch_tests.StudyNoteBatchTests._cleanup
    _event = batch_tests.StudyNoteBatchTests._event
    _batch_payload = batch_tests.StudyNoteBatchTests._batch_payload
    _admit = batch_tests.StudyNoteBatchTests._admit
    _process = batch_tests.StudyNoteBatchTests._process

    def setUp(self):
        supported = mock.patch(
            "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", PROFILES
        )
        supported.start()
        self.addCleanup(supported.stop)
        enroll = batch_tests.stage_note_authority_enrollment

        def enroll_then_switch(session, **kwargs):
            result = enroll(session, **kwargs)
            session.add(StudyAuthorityStorageProfile(
                id=1, profile_code="CANONICAL_V1", epoch=2, created_at=_now(), updated_at=_now()))
            session.flush()
            apply_consolidated_switch(session, now_utc=_now())
            return result

        with mock.patch.object(batch_tests, "stage_note_authority_enrollment", enroll_then_switch):
            batch_tests.StudyNoteBatchTests.setUp(self)
        with self.app.app_context():
            engine = db.engine
        self.old_table_statements = []

        def record(_conn, _cursor, statement, *_args):
            match = OLD_TABLES.search(statement)
            if match:
                self.old_table_statements.append(f"{statement.split()[0].upper()} {match.group(1)}")

        event.listen(engine, "before_cursor_execute", record)
        self.addCleanup(lambda: event.remove(engine, "before_cursor_execute", record))

    def test_two_batches_continue_the_same_row(self):
        first = self._admit(1, [self._event(1)])
        second = self._admit(2, [self._event(2)], final=True)
        receipt = self._process(first)
        self.assertEqual(receipt["applied_event_count"], 1)
        self.assertEqual(self._process(first), receipt)
        final_receipt = self._process(second)
        self.assertEqual(final_receipt["cumulative_event_count"], 2)
        with self.app.app_context():
            subject = StudyProgressSubject.query.one()
            self.assertEqual((int(subject.authority_revision), subject.current_provenance_code),
                             (2, "NATIVE_SESSION"))
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 2)
            self.assertEqual(StudyProgressHistoryFact.query.count(), 2)
            from models.study_session import StudySession

            self.assertEqual(db.session.get(StudySession, self.snapshot["session_id"]).status, "committed")
        self.assertEqual(self.old_table_statements, [])


if __name__ == "__main__":
    unittest.main()
