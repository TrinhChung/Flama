"""P9-05c: Algorithm switch under CANONICAL_V1 needs no card_progress round-trip."""

import re
import unittest
from unittest import mock

from sqlalchemy import event

# Import the app (through the switch tests) before any model module.
from tests import test_study_algorithm_switch as switch_tests  # noqa: I001
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.note_type import NoteType
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState

BOTH_PROFILES = frozenset({"PROJECTION_V1", "CANONICAL_V1"})
_TABLE = re.compile(r"\bcard_progress\b", re.IGNORECASE)


class StudyCanonicalSwitchTests(unittest.TestCase):
    setUpClass = classmethod(switch_tests.fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    _cleanup = switch_tests.StudyAlgorithmSwitchTests._cleanup
    _answer = switch_tests.StudyAlgorithmSwitchTests._answer
    _switch = switch_tests.StudyAlgorithmSwitchTests._switch
    _token = switch_tests.StudyAlgorithmSwitchTests._token

    def setUp(self):
        switch_tests.StudyAlgorithmSwitchTests.setUp(self)
        profiles = mock.patch(
            "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", BOTH_PROFILES)
        profiles.start()
        self.addCleanup(profiles.stop)
        with self.app.app_context():
            db.session.add(StudyAuthorityStorageProfile(
                id=1, profile_code="CANONICAL_V1",
                created_at=switch_tests._now(), updated_at=switch_tests._now()))
            db.session.execute(CardProgress.__table__.delete())
            db.session.commit()
            engine = db.engine
        self.statements = []

        def record(_conn, _cursor, statement, *_args):
            if _TABLE.search(statement):
                self.statements.append(statement.split()[0].upper())

        event.listen(engine, "before_cursor_execute", record)
        self.addCleanup(lambda: event.remove(engine, "before_cursor_execute", record))

    def test_switch_replays_and_reports_the_authority_revision(self):
        with self.app.app_context():
            before = self._token().authority_revision
            result = self._switch(operation_key="switch-1", expected=before)
            db.session.commit()
            self.assertEqual(result.response["to_algorithm"]["key"], switch_tests.SYNTHETIC.key)
            self.assertEqual(self._token().authority_revision, before + 1)
            self.assertEqual(StudyProgressState.query.one().algorithm_key, switch_tests.SYNTHETIC.key)
            self.assertEqual(set(result.response["projected_card_revisions"].values()), {before + 1})
            replay = self._switch(operation_key="switch-1", expected=before)
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.response, result.response)
            self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 1)
            # A switch has no ReviewEvent: every contributor keeps its pointer.
            self.assertEqual(
                {row.pointer_status for row in StudyProgressContributor.query.filter_by(contributor_status="ACTIVE")},
                {"ABSENT"},
            )
        self.assertEqual(self.statements, [])

    def test_switch_freezes_history_of_contributors_without_projection_evidence(self):
        # A Note materialized after the profile switch has CANONICAL
        # contributors: no raw CardProgress evidence to put in the history cut.
        with self.app.app_context():
            StudyProgressContributor.query.filter_by(contributor_status="ACTIVE").update({
                "evidence_kind": "CANONICAL", "source_progress_id": None, "live_card_progress_id": None,
                "card_progress_revision": None, "raw_schema_version": None, "storage_codec": None,
                "raw_payload": None, "raw_payload_size": None, "raw_progress_hash": None,
            })
            db.session.commit()
            self._switch()
            db.session.commit()
            self.assertEqual(StudyProgressState.query.one().algorithm_key, switch_tests.SYNTHETIC.key)
        self.assertEqual(self.statements, [])

    def test_a_wider_state_no_longer_needs_a_projection_round_trip(self):
        # PROJECTION_V1 refuses it: CardProgress cannot hold the extra key.
        # CANONICAL_V1 only needs availability to be derivable (ADR §2.9).
        with self.app.app_context():
            self._switch(switch_tests.UNPROJECTABLE)
            db.session.commit()
            state = StudyProgressState.query.one()
            self.assertEqual(state.algorithm_key, switch_tests.UNPROJECTABLE.key)
            self.assertEqual(state.state_payload["wide"], 1)
        self.assertEqual(self.statements, [])

    def test_template_add_keeps_a_switched_algorithm(self):
        # PROJECTION_V1 refuses this (ALGORITHM_IDENTITY_MIRROR_CONFLICT): its
        # re-mirror from CardProgress would revert the Algorithm. CANONICAL_V1
        # never rewrites state on a topology change.
        from app.services import flashcard_content_service as content

        with self.app.app_context():
            self._switch()
            db.session.commit()
            state_before = dict(StudyProgressState.query.one().state_payload)
            content.create_template(user_id=self.user_id, note_type_id=NoteType.query.one().id,
                                    payload={"name": "Reverse"})
            db.session.commit()
            state = StudyProgressState.query.one()
            self.assertEqual(state.algorithm_key, switch_tests.SYNTHETIC.key)
            self.assertEqual(dict(state.state_payload), state_before)
            self.assertEqual(Card.query.count(), 3)
            self.assertEqual(StudyProgressContributor.query.filter_by(contributor_status="ACTIVE").count(), 3)


if __name__ == "__main__":
    unittest.main()
