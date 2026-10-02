"""P9-06: a v4 lease issued under PROJECTION_V1 still commits after the switch."""

import re
import unittest
from uuid import uuid4

from sqlalchemy import event

# Import the app (through the session tests) before any model module.
from tests import test_study_session_api as session_tests  # noqa: I001
from app.services.study_storage_profile_service import apply_storage_profile_switch
from models import db
from models.card_progress import CardProgress
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_session import StudySession

_TABLE = re.compile(r"\bcard_progress\b", re.IGNORECASE)


class StudyProfileSwitchLeaseTests(unittest.TestCase):
    setUpClass = classmethod(session_tests.StudySessionApiTests.setUpClass.__func__)
    setUp = session_tests.StudySessionApiTests.setUp
    tearDown = session_tests.StudySessionApiTests.tearDown
    _enable_existing_state_note_authority = session_tests.StudySessionApiTests._enable_existing_state_note_authority
    _open_session_v4 = session_tests.StudySessionApiTests._open_session_v4
    _commit_payload = staticmethod(session_tests.StudySessionApiTests._commit_payload)

    def test_v4_lease_opened_before_the_switch_commits_on_the_canonical_path(self):
        self._enable_existing_state_note_authority(epoch=5)
        snapshot = self._open_session_v4()
        with self.app.app_context():
            frozen = CardProgress.query.one()
            frozen_row = (int(frozen.revision), frozen.due_at, frozen.updated_at)
            revision = int(StudyAuthoritySubjectToken.query.one().authority_revision)
            apply_storage_profile_switch(db.session)
            db.session.commit()
            engine = db.engine
        statements = []

        def record(_conn, _cursor, statement, *_args):
            if _TABLE.search(statement):
                statements.append(statement.split()[0].upper())

        event.listen(engine, "before_cursor_execute", record)
        self.addCleanup(lambda: event.remove(engine, "before_cursor_execute", record))

        url = f"/api/study/sessions/{snapshot['session_id']}/commit"
        payload = self._commit_payload(snapshot, commit_id=str(uuid4()))
        response = self.client.post(url, json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        receipt = response.get_json()
        self.assertEqual((receipt["authority_mode"], receipt["applied_event_count"]), ("NOTE", 1))
        replay = self.client.post(url, json=payload)
        self.assertEqual(replay.status_code, 200, replay.get_json())
        self.assertEqual(replay.get_json(), receipt)
        with self.app.app_context():
            self.assertEqual(int(StudyAuthoritySubjectToken.query.one().authority_revision), revision + 1)
            progress = CardProgress.query.one()
            self.assertEqual((int(progress.revision), progress.due_at, progress.updated_at), frozen_row)
            self.assertEqual(db.session.get(StudySession, snapshot["session_id"]).status, "committed")
        self.assertNotIn("INSERT", statements)
        self.assertNotIn("UPDATE", statements)


if __name__ == "__main__":
    unittest.main()
