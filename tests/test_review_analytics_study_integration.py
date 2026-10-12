"""Exercise accepted review pipelines with analytics enabled after fixture seeding."""

from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import func

from tests import test_study_session_api as session_fixtures
from tests import test_study_note_batch as note_batch_fixtures
from tests import test_anki_import_api as anki_fixtures
from app.services.review_analytics_policy import resolve_review_analytics_policy
from app.services.study_worker_service import process_single_study_batch
from models import db
from models.card import Card
from models.note import Note
from models.review_event import ReviewEvent
from models.review_analytics import DailyReviewCount, ReviewAnalyticsGeneration, ReviewAnalyticsHead


def enable_empty_projection(app, user_id):
    """Publish an independently seeded empty generation before the first review."""
    with app.app_context():
        assert ReviewEvent.query.filter_by(user_id=user_id).count() == 0
        policy = resolve_review_analytics_policy(db.session, user_id)
        db.session.add(ReviewAnalyticsHead(user_id=user_id, source_revision=0, active_generation=1))
        db.session.flush()
        db.session.add(ReviewAnalyticsGeneration(
            user_id=user_id, generation=1, status=1, policy_hash=policy.policy_hash,
            timezone_name=policy.timezone_name, day_boundary_hour=policy.day_boundary_hour,
            grouping_version=policy.grouping_version, timezone_rules_version=policy.timezone_rules_version,
            baseline_high_water_id=0, backfill_cursor_id=0, applied_source_revision=0,
            verified_source_revision=0, verification_contract_version=1, verified_at=datetime.utcnow(),
        ))
        db.session.commit()
    app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = True


class ProjectionAssertions:
    def assert_projection(self, app, user_id, count, duration, passed, revision):
        with app.app_context():
            self.assertEqual(ReviewEvent.query.filter_by(user_id=user_id).count(), count)
            totals = db.session.query(
                func.coalesce(func.sum(DailyReviewCount.review_event_count), 0),
                func.coalesce(func.sum(DailyReviewCount.positive_duration_ms), 0),
                func.coalesce(func.sum(DailyReviewCount.passed_review_count), 0),
            ).filter_by(user_id=user_id, generation=1, scope_kind=0, scope_id=0).one()
            self.assertEqual(tuple(totals), (count, duration, passed))
            head = db.session.get(ReviewAnalyticsHead, user_id)
            generation = db.session.get(ReviewAnalyticsGeneration, (user_id, 1))
            self.assertEqual(head.source_revision, revision)
            self.assertEqual(generation.applied_source_revision, revision)
            self.assertEqual(generation.status, 1)


class ReviewAnalyticsNativeIntegrationTests(ProjectionAssertions, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        session_fixtures.StudySessionApiTests.setUpClass()
        cls.app = session_fixtures.StudySessionApiTests.app

    def setUp(self):
        self.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = False
        self.fixture = session_fixtures.StudySessionApiTests("test_open_returns_self_contained_snapshot")
        self.fixture.setUp()

    def tearDown(self):
        self.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = False
        self.fixture.tearDown()

    def test_legacy_direct_answer_updates_projection_in_same_commit(self):
        fixture = self.fixture
        enable_empty_projection(self.app, fixture.user_id)
        with self.app.app_context():
            card_id = str(Card.query.join(Note, Card.note_id == Note.id).one().id)
        response = fixture.client.post(f"/api/study/{card_id}/answer", json={
            "rating": "good", "duration_ms": 1234, "scope": "deck", "scope_id": fixture.deck_id,
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assert_projection(self.app, fixture.user_id, 1, 1234, 1, 1)

    def test_legacy_sync_commit_and_duplicate_count_once(self):
        fixture = self.fixture
        enable_empty_projection(self.app, fixture.user_id)
        snapshot = fixture._open_session()
        payload = fixture._commit_payload(snapshot)
        url = f"/api/study/sessions/{snapshot['session_id']}/commit"
        accepted = fixture.client.post(url, json=payload)
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        self.assert_projection(self.app, fixture.user_id, 1, 500, 1, 1)
        duplicate = fixture.client.post(url, json=payload)
        self.assertEqual(duplicate.status_code, 200, duplicate.get_json())
        self.assertEqual(accepted.get_json(), duplicate.get_json())
        self.assert_projection(self.app, fixture.user_id, 1, 500, 1, 1)

    def test_note_sync_commit_and_duplicate_count_once(self):
        fixture = self.fixture
        fixture._enable_existing_state_note_authority(epoch=5)
        enable_empty_projection(self.app, fixture.user_id)
        snapshot = fixture._open_session_v4()
        payload = fixture._commit_payload(snapshot)
        url = f"/api/study/sessions/{snapshot['session_id']}/commit"
        accepted = fixture.client.post(url, json=payload)
        self.assertEqual(accepted.status_code, 200, accepted.get_json())
        self.assert_projection(self.app, fixture.user_id, 1, 500, 1, 1)
        duplicate = fixture.client.post(url, json=payload)
        self.assertEqual(duplicate.status_code, 200, duplicate.get_json())
        self.assertEqual(accepted.get_json(), duplicate.get_json())
        self.assert_projection(self.app, fixture.user_id, 1, 500, 1, 1)

    def test_note_direct_and_mcp_receipt_replays_do_not_repeat_counters(self):
        fixture = self.fixture
        fixture._enable_existing_state_note_authority(epoch=8)
        enable_empty_projection(self.app, fixture.user_id)
        with self.app.app_context():
            card_id = str(Card.query.join(Note, Card.note_id == Note.id).one().id)
        operation_key = str(uuid4())
        payload = {"rating": "good", "duration_ms": 1000, "scope": "deck", "scope_id": fixture.deck_id,
                   "operation_key": operation_key}
        for _ in range(2):
            response = fixture.client.post(f"/api/study/{card_id}/answer", json=payload)
            self.assertEqual(response.status_code, 200, response.get_json())
        self.assert_projection(self.app, fixture.user_id, 1, 1000, 1, 1)
        from app.services.mcp.study_tools import submit_review

        mcp_key = str(uuid4())
        with self.app.app_context():
            accepted = submit_review(user_id=fixture.user_id, card_id=card_id, rating="easy",
                                     duration_ms=250, operation_key=mcp_key)
            self.assertTrue(accepted["success"])
            replay = submit_review(user_id=fixture.user_id, card_id=card_id, rating="easy",
                                   duration_ms=250, operation_key=mcp_key)
            self.assertTrue(replay["authority"]["replayed"])
        self.assert_projection(self.app, fixture.user_id, 2, 1250, 2, 2)


class ReviewAnalyticsWorkerIntegrationTests(ProjectionAssertions, unittest.TestCase):
    def test_note_http_worker_accepts_once_and_retry_has_no_counter_delta(self):
        from app.services.study_queue_service import pop_study_batch
        note_batch_fixtures.StudyNoteBatchTests.setUpClass()
        fixture = note_batch_fixtures.StudyNoteBatchTests("test_two_batches_continue_same_note_and_project_every_sibling")
        fixture._seed()
        try:
            enable_empty_projection(fixture.app, fixture.user_id)
            fixture._http_admit(fixture._batch_payload(1, [fixture._event(1)], final=True))
            job = pop_study_batch(timeout=0)
            self.assertIsNotNone(job)
            with fixture.app.app_context():
                accepted = process_single_study_batch(job)
                self.assertIn(accepted["status"], {"processed", "completed"})
            self.assert_projection(fixture.app, fixture.user_id, 1, 500, 1, 1)
            with fixture.app.app_context():
                replay = process_single_study_batch(job)
                self.assertEqual(replay["status"], "already_processed")
            self.assert_projection(fixture.app, fixture.user_id, 1, 500, 1, 1)
        finally:
            fixture.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = False
            fixture._cleanup()

    def test_note_batch_continuation_and_replay_preserve_atomic_counters(self):
        note_batch_fixtures.StudyNoteBatchTests.setUpClass()
        fixture = note_batch_fixtures.StudyNoteBatchTests("test_two_batches_continue_same_note_and_project_every_sibling")
        fixture.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = False
        fixture._seed()
        try:
            enable_empty_projection(fixture.app, fixture.user_id)
            first = fixture._admit(1, [fixture._event(1)])
            accepted = fixture._process(first)
            self.assert_projection(fixture.app, fixture.user_id, 1, 500, 1, 1)
            self.assertEqual(fixture._process(first), accepted)
            self.assert_projection(fixture.app, fixture.user_id, 1, 500, 1, 1)
            second = fixture._admit(2, [fixture._event(2)], final=True)
            fixture._process(second)
            self.assert_projection(fixture.app, fixture.user_id, 2, 1000, 2, 2)
        finally:
            fixture.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = False
            fixture._cleanup()


class ReviewAnalyticsAnkiIntegrationTests(ProjectionAssertions, unittest.TestCase):
    def test_review_packages_savepoint_failure_and_replay_count_only_accepted_facts(self):
        fixture = anki_fixtures.AnkiImportApiTests("test_progress_and_full_revlog_are_separate_idempotent_sync_streams")
        fixture.setUp()
        fixture.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = False
        try:
            enable_empty_projection(fixture.app, fixture.admin_id)
            fixture._login()
            session_id = fixture._create_session()["importSessionId"]
            fixture._upload_package(session_id, "cards", 0, [{
                "ankiNoteId": 1001, "sourceModelId": "anki-model-1", "sourceDeckId": "anki-inbox",
                "sourceDeckPath": "Inbox", "contentHash": "1" * 64,
                "note": {"deckName": "Inbox", "modelName": fixture.note_type_id,
                         "fields": {"Word": "history", "Meaning": "projection"}, "tags": []},
            }])
            fixture._upload_package(session_id, "progress", 0, [{
                "externalNoteId": 1001, "sourceCardId": 2001, "ord": 0, "snapshotHash": "2" * 64,
                "type": 2, "queue": 2, "due": 50003, "sourceToday": 50000,
                "interval": 14, "factor": 2500, "reps": 2, "lapses": 1, "left": 0,
            }])
            self.assert_projection(fixture.app, fixture.admin_id, 0, 0, 0, 0)
            first_id = int(datetime(2026, 8, 12, 10, tzinfo=timezone.utc).timestamp() * 1000)
            reviews = [
                {"sourceReviewId": first_id, "sourceCardId": 2001, "ease": 3, "type": 1,
                 "ivl": 10, "lastIvl": 5, "factor": 2500, "time": 1200},
                {"sourceReviewId": first_id + 1000, "sourceCardId": 2001, "ease": 2, "type": 1,
                 "ivl": 14, "lastIvl": 10, "factor": 2450, "time": 2300},
            ]
            from app.services import anki_sync_service

            original = anki_sync_service._import_review

            def fail_after_flushed_second_fact(session, record):
                result = original(session, record)
                if record["sourceReviewId"] == first_id + 1000:
                    raise RuntimeError("injected failure after raw facts were flushed")
                return result

            with patch.object(anki_sync_service, "_import_review", side_effect=fail_after_flushed_second_fact):
                failed = fixture._upload_package(session_id, "reviews", 0, reviews)
                self.assertEqual(failed["status"], "partial_failed")
            self.assert_projection(fixture.app, fixture.admin_id, 0, 0, 0, 0)
            accepted = fixture._upload_package(session_id, "reviews", 1, reviews)
            self.assertEqual([row["state"] for row in accepted["results"]], ["imported", "imported"])
            self.assert_projection(fixture.app, fixture.admin_id, 2, 3500, 1, 1)
            replay = fixture._upload_package(session_id, "reviews", 1, reviews)
            self.assertTrue(replay["replayed"])
            self.assert_projection(fixture.app, fixture.admin_id, 2, 3500, 1, 1)
            manual = fixture._upload_package(session_id, "reviews", 2, [{
                **reviews[0], "sourceReviewId": first_id + 2000, "ease": 0,
            }])
            self.assertEqual(manual["results"][0]["state"], "ignored")
            self.assert_projection(fixture.app, fixture.admin_id, 2, 3500, 1, 1)
        finally:
            fixture.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = False
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
