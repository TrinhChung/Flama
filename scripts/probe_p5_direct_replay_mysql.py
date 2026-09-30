"""Run NOTE replay and content lifecycle contracts on disposable local MySQL.

Reuses the SQLite regression scenarios and adds independent concurrent HTTP
requests. No configured application rows are read or written. Creation and
cleanup are restricted to a generated database name on loopback MySQL.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import unittest
from unittest.mock import patch

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from models import db
from scripts.probe_phase4_shadow_schema_mysql import (
    _connection_settings, _database_uri, _source_database_collation,
)
from tests.test_study_direct_note_replay import StudyDirectNoteReplayTests
from tests.test_study_note_batch import StudyNoteBatchTests
from tests.test_study_note_templates import StudyNoteTemplateTests
from tests.test_study_content_delete import StudyContentDeleteTests
from tests.test_study_note_overlay import StudyNoteOverlayTests
from tests.test_study_algorithm_switch import StudyAlgorithmSwitchTests
from tests.test_study_phase6_continuity import (
    StudyPhase6ContinuityTests, StudyRepeatedApplicationTests,
)

PROBE_NAME_PATTERN = re.compile(r"^flama_p5_direct_probe_[0-9]+_[a-f0-9]{8}$")


def _probe_app(uri):
    url = sa.engine.make_url(uri)
    if (
        url.get_backend_name() != "mysql"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or not PROBE_NAME_PATTERN.fullmatch(url.database or "")
    ):
        raise ValueError("Direct replay probe requires a generated local MySQL database.")
    return create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": uri,
        "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
        "STARTUP_RUN_DB_CREATE_ALL": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
        "REDIS_URL": "", "STUDY_QUEUE_NAMESPACE": "",
        "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": False,
        "STUDY_WIRE_V4_ENABLED": True, "STUDY_ASYNC_BATCH_ENABLED": False,
    })


def _concurrent_answers(case, *, conflicting):
    from app.services import study_service

    barrier = threading.Barrier(2, timeout=15)
    counter_lock = threading.Lock()
    arrivals = 0
    original_lock = study_service.lock_study_authority_route

    def synchronized_lock(*args, **kwargs):
        nonlocal arrivals
        with counter_lock:
            arrivals += 1
            should_wait = arrivals <= 2
        if should_wait:
            barrier.wait()
        return original_lock(*args, **kwargs)

    def request(index):
        client = case.app.test_client()
        with client.session_transaction() as login:
            login["_user_id"], login["_fresh"] = str(case.user_id), True
        payload = dict(case.payload)
        if conflicting and index:
            payload["rating"] = "good"
        response = client.post(f"/api/study/{case.card_ids[0]}/answer", json=payload)
        return response.status_code, response.get_json()

    with patch.object(study_service, "lock_study_authority_route", side_effect=synchronized_lock):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(request, index) for index in range(2)]
            results = [future.result(timeout=30) for future in futures]
    if conflicting:
        case.assertEqual(sorted(status for status, _ in results), [200, 409], results)
        case.assertEqual(next(body["error"] for status, body in results if status == 409), "AUTHORITY_OPERATION_REUSED")
    else:
        case.assertEqual([status for status, _ in results], [200, 200], results)
        case.assertEqual(sorted(body["authority"]["replayed"] for _, body in results), [False, True])
        case.assertEqual(results[0][1]["intervals_preview"], results[1][1]["intervals_preview"])
    case._counts()


def _concurrent_first_state_answers(case):
    """Two first reviews of one pristine overlay Note race on real MySQL locks."""
    from uuid import uuid4

    from app.services import study_service
    from models.card_progress import CardProgress
    from models.review_event import ReviewEvent
    from models.study_authority_subject_token import StudyAuthoritySubjectToken
    from models.study_progress_subject import StudyProgressSubject

    case._install_overlay()
    barrier = threading.Barrier(2, timeout=15)
    counter_lock = threading.Lock()
    arrivals = 0
    original_lock = study_service.lock_study_authority_route

    def synchronized_lock(*args, **kwargs):
        nonlocal arrivals
        with counter_lock:
            arrivals += 1
            should_wait = arrivals <= 2
        if should_wait:
            barrier.wait()
        return original_lock(*args, **kwargs)

    def request(_index):
        client = case.app.test_client()
        with client.session_transaction() as login:
            login["_user_id"], login["_fresh"] = str(case.user_id), True
        response = client.post(f"/api/study/{case.source_card_ids[0]}/answer", json={
            "rating": "good", "operation_key": str(uuid4()), "duration_ms": 400,
            "scope": "deck", "scope_id": case.local_deck_id})
        return response.status_code, response.get_json()

    with patch.object(study_service, "lock_study_authority_route", side_effect=synchronized_lock):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(request, index) for index in range(2)]
            results = [future.result(timeout=60) for future in futures]
    succeeded = [body for status, body in results if status == 200]
    # The loser either serializes behind the materialization and applies a
    # second review, or gets a typed conflict; never a split first state.
    case.assertTrue(succeeded, results)
    case.assertTrue(all(status in (200, 409) for status, _ in results), results)
    with case.app.app_context():
        subjects = StudyProgressSubject.query.filter_by(
            learner_user_id=case.user_id, logical_note_key=case.source_note_id.encode()).all()
        case.assertEqual(len(subjects), 1)
        token = StudyAuthoritySubjectToken.query.filter_by(subject_id=subjects[0].id).one()
        case.assertEqual(int(token.authority_revision), len(succeeded))
        case.assertEqual(
            ReviewEvent.query.filter(ReviewEvent.card_id.in_(case.source_card_ids)).count(), len(succeeded))
        case.assertEqual(
            CardProgress.query.filter(CardProgress.card_id.in_(case.source_card_ids)).count(), 2)


def _template_preview_race(case, *, change_count):
    """Force an old RR snapshot before another transaction changes topology."""
    from app.services import study_content_delete_service as content_topology
    from app.services.mcp import note_type_tools
    from app.validators.flashcard_input import RequestValidationError
    from models.note_type import NoteType
    from models.template import Template

    with case.app.app_context():
        note_type = NoteType.query.one()
        note_type_id = note_type.id
        original_timestamp = note_type.updated_at
        changes = {"removed": ["Card 0"]}
        preview = note_type_tools.preview_note_type_update(
            user_id=case.user_id, note_type_id=note_type_id, templates=changes)
        before = case._identity()

    reached_fence = threading.Event()
    release_fence = threading.Event()
    counter_lock = threading.Lock()
    arrivals = 0
    # update_note_type takes every learner fence through the topology coordinator.
    original_lock = content_topology.lock_study_authority_route

    def hold_first(*args, **kwargs):
        nonlocal arrivals
        with counter_lock:
            arrivals += 1
            first = arrivals == 1
        if first:
            # _owned_note_type_for_mutation already performed a consistent
            # read, so the stale transaction has an actual MySQL RR snapshot.
            reached_fence.set()
            if not release_fence.wait(30):
                raise TimeoutError("Template race did not release the fence")
        return original_lock(*args, **kwargs)

    def stale_confirmation():
        with case.app.app_context():
            try:
                note_type_tools.update_note_type(user_id=case.user_id, note_type_id=note_type_id,
                    templates=changes, preview_id=preview["preview_id"], confirm=True)
            except RequestValidationError as exc:
                return exc.code
            return "UNEXPECTED_SUCCESS"

    with patch.object(content_topology, "lock_study_authority_route", side_effect=hold_first):
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(stale_confirmation)
            try:
                case.assertTrue(reached_fence.wait(15), "Stale request did not reach the learner fence")
                with case.app.app_context():
                    if change_count:
                        mutation = {"added": [{"name": "Concurrent sibling"}]}
                    else:
                        template_id = Template.query.filter_by(name="Card 1").one().id
                        mutation = {"updated": [{"id": template_id, "front_html": "<b>Concurrent edit</b>"}]}
                    note_type_tools.update_note_type(user_id=case.user_id,
                        note_type_id=note_type_id, templates=mutation)
                    # DATETIME(0) can be identical for distinct writes. Force
                    # that case so the test proves topology/content refresh,
                    # rather than passing only because updated_at changed.
                    db.session.get(NoteType, note_type_id).updated_at = original_timestamp
                    db.session.commit()
            finally:
                release_fence.set()
            case.assertEqual(future.result(timeout=30), "STALE_PREVIEW_ERROR")
    with case.app.app_context():
        case._assert_state(before, cards=3 if change_count else 2, generations=1 if change_count else 0)
        case.assertIsNotNone(Template.query.filter_by(name="Card 0").one_or_none())


def run_probe(*, templates_only=False, content_delete_only=False, overlay_only=False, switch_only=False,
              test_name=None):
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p5_direct_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("Direct replay probe requires a generated local MySQL database.")
    connection = pymysql.connect(**settings)
    created = False
    app = None
    report = {"schema_version": "p5-direct-note-replay-mysql.v1", "configured_database_modified": False}
    try:
        collation = _source_database_collation(connection)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        app = _probe_app(_database_uri(settings, name))
        app.config["MCP_PREVIEW_BACKEND"] = "local"

        class MySQLDirectReplayTests(StudyDirectNoteReplayTests):
            @classmethod
            def setUpClass(cls):
                cls.app = app

            def test_concurrent_duplicate_has_one_committed_result(self):
                _concurrent_answers(self, conflicting=False)

            def test_concurrent_changed_body_cannot_reuse_key(self):
                _concurrent_answers(self, conflicting=True)

        class MySQLNumericReplayTests(StudyNoteBatchTests):
            @classmethod
            def setUpClass(cls):
                cls.app = app

        class MySQLNoteTemplateTests(StudyNoteTemplateTests):
            @classmethod
            def setUpClass(cls):
                cls.app = app

            def test_stale_rr_preview_after_concurrent_template_content_edit(self):
                _template_preview_race(self, change_count=False)

            def test_stale_rr_preview_after_concurrent_sibling_addition(self):
                _template_preview_race(self, change_count=True)

        class MySQLContentDeleteTests(StudyContentDeleteTests):
            @classmethod
            def setUpClass(cls):
                cls.app = app

        class MySQLPhase6ContinuityTests(StudyPhase6ContinuityTests):
            @classmethod
            def setUpClass(cls):
                cls.app = app

        class MySQLRepeatedApplicationTests(StudyRepeatedApplicationTests):
            @classmethod
            def setUpClass(cls):
                cls.app = app

        class MySQLNoteOverlayTests(StudyNoteOverlayTests):
            @classmethod
            def setUpClass(cls):
                cls.app = app

            def test_concurrent_first_state_answers_on_pristine_overlay_note(self):
                _concurrent_first_state_answers(self)

        class MySQLAlgorithmSwitchTests(StudyAlgorithmSwitchTests):
            @classmethod
            def setUpClass(cls):
                cls.app = app

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(MySQLNoteTemplateTests)
        report["scope"] = (
            "note-templates" if templates_only
            else "direct-replay-numeric-templates-content-delete-overlay-switch"
        )
        if content_delete_only:
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(MySQLContentDeleteTests)
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MySQLPhase6ContinuityTests))
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MySQLRepeatedApplicationTests))
            report["scope"] = "content-delete"
        elif overlay_only:
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(MySQLNoteOverlayTests)
            report["scope"] = "note-overlay"
        elif switch_only:
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(MySQLAlgorithmSwitchTests)
            report["scope"] = "algorithm-switch"
        elif not templates_only:
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MySQLAlgorithmSwitchTests))
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MySQLNoteOverlayTests))
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MySQLContentDeleteTests))
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MySQLPhase6ContinuityTests))
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MySQLRepeatedApplicationTests))
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(MySQLDirectReplayTests))
            suite.addTests(MySQLNumericReplayTests(name) for name in (
                "test_direct_note_answers_use_same_numeric_profile_for_all_ratings",
                "test_sync_note_commit_uses_same_numeric_profile_for_all_ratings",
                "test_all_ratings_across_batches_have_lossless_numeric_projection_and_retry",
            ))
        if test_name:
            suite = unittest.TestSuite(test for test in suite if test_name in test.id())
            if not suite.countTestCases():
                raise ValueError("No probe scenarios match --test-name.")
            report["test_name_filter"] = test_name
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        report.update({"tests_run": result.testsRun, "failures": len(result.failures),
            "errors": len(result.errors), "status": "PASS" if result.wasSuccessful() else "FAIL"})
        return report
    finally:
        try:
            if app is not None:
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
        finally:
            try:
                if created:
                    if not PROBE_NAME_PATTERN.fullmatch(name):
                        raise RuntimeError("Refusing an unsafe direct replay probe cleanup target.")
                    with connection.cursor() as cursor:
                        cursor.execute(f"DROP DATABASE `{name}`")
                    report["probe_database_removed"] = True
            finally:
                connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--templates-only", action="store_true", help="Run only the NOTE template lifecycle scenarios.")
    scope.add_argument("--content-delete-only", action="store_true", help="Run only the multi-learner content deletion scenarios.")
    scope.add_argument("--overlay-only", action="store_true", help="Run only the NOTE logical-overlay / pristine-Note scenarios.")
    scope.add_argument("--switch-only", action="store_true", help="Run only the requested Algorithm switch scenarios.")
    parser.add_argument("--test-name", help="Run scenarios whose test ID contains this string.")
    args = parser.parse_args()
    report = run_probe(templates_only=args.templates_only, content_delete_only=args.content_delete_only,
        overlay_only=args.overlay_only, switch_only=args.switch_only, test_name=args.test_name)
    print(json.dumps(report, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)
