"""Qualify durable template delivery on a generated loopback MySQL database.

Only configured-schema collation metadata is read. Every application write,
migration and cleanup targets a validated randomly generated probe schema.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import time
import unittest
from unittest.mock import patch

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_audit_app
from app.repositories import template_release_repository as releases
from app.services import template_release_service
from app.services import template_subscription_sync_service as sync
from app.services import study_consumer_service
from app.services.template_sync_cli import register_template_sync_commands
from models import db
from models.template import Template
from models.template_sync_job import TemplateSyncJob
from models.template_subscription import TemplateSubscription
from models.user import User
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

PROBE_NAME = re.compile(r"^flama_template_sync_probe_[0-9]+_[a-f0-9]{12}$")
EVIDENCE = {}


class TemplateSyncMySQLTests(unittest.TestCase):
    app = None

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        tag = secrets.token_hex(6)
        owner = User(username=f"owner-{tag}", email=f"owner-{tag}@example.invalid")
        learners = [User(username=f"learner-{tag}-{i}", email=f"learner-{tag}-{i}@example.invalid") for i in range(3)]
        db.session.add_all([owner, *learners])
        db.session.flush()
        self.owner_id = owner.id
        self.users = [row.id for row in learners]
        source = Template(owner_user_id=owner.id, name="Sync probe", front_html="FRONT", back_html="BACK", shared_css="", input_schema=[])
        db.session.add(source)
        db.session.commit()
        self.source_id = source.id
        self.first = self._publish("1")
        self.subscriptions = []
        for user_id in self.users:
            row = template_release_service.ensure_subscription(db.session, user_id=user_id, source_template_id=self.source_id, access_granted=True)
            db.session.execute(sa.update(TemplateSubscription.__table__).where(TemplateSubscription.id == row["id"]).values(auto_update_enabled=True))
            db.session.commit()
            self.subscriptions.append(row)
        sync.drain_template_sync_jobs(max_jobs=1000)
        db.session.rollback()

    def tearDown(self):
        db.session.remove()
        self.context.pop()

    def _publish(self, label):
        row = releases.template(db.session, self.source_id)
        publication = releases.publication(db.session, self.source_id) or {}
        return template_release_service.publish_release(user_id=self.owner_id, template_id=self.source_id,
            payload={"version_label": label, "expected_current_release_id": publication.get("current_release_id"),
                     "expected_current_version_id": row["current_version_id"]}, idempotency_key=f"probe:{label}")["release"]

    def _changed_release(self, label="2", **changes):
        source = db.session.get(Template, self.source_id)
        for key, value in (changes or {"back_html": "NEW BACK"}).items():
            setattr(source, key, value)
        db.session.commit()
        return self._publish(label)

    def _read(self, subscription):
        db.session.rollback()
        return releases.subscription(db.session, user_id=subscription["user_id"], local_template_id=subscription["local_template_id"])

    def test_publish_does_not_touch_locked_subscriber_and_other_recipients_deliver(self):
        blocked = self.subscriptions[0]
        with db.engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(sa.select(Template.id).where(Template.id == blocked["local_template_id"]).with_for_update()).all()
            started = time.monotonic()
            target = self._changed_release()
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 2, "Publication waited on a subscriber template")
            result = sync.drain_template_sync_jobs(max_jobs=20)
            self.assertGreaterEqual(result["retrying_count"], 1)
            for row in self.subscriptions[1:]:
                self.assertEqual(self._read(row)["applied_release_id"], target["id"])
            self.assertEqual(self._read(blocked)["applied_release_id"], self.first["id"])
            job = db.session.execute(sa.select(TemplateSyncJob).where(TemplateSyncJob.release_id == target["id"], TemplateSyncJob.recipient_key == blocked["id"])).scalar_one()
            self.assertEqual(job.last_error_code, "MYSQL_3572")
            db.session.rollback()
            transaction.rollback()
        retried = sync.drain_template_sync_jobs(max_jobs=20, now_utc=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10))
        self.assertGreaterEqual(retried["delivered_count"], 1)
        self.assertEqual(self._read(blocked)["applied_release_id"], target["id"])
        EVIDENCE["locked_subscriber"] = {"publish_seconds": round(elapsed, 3), "delivery_retry": True, "peers_delivered_while_locked": True}

    def test_opt_out_after_dispatch_is_preserved_and_duplicate_enqueue_is_idempotent(self):
        target = self._changed_release()
        sync.drain_template_sync_jobs(max_jobs=1)
        opted_out = self.subscriptions[0]
        db.session.execute(sa.update(TemplateSubscription.__table__).where(TemplateSubscription.id == opted_out["id"]).values(auto_update_enabled=False))
        sync.enqueue_template_release_sync(db.session, source_template_id=self.source_id, release_id=target["id"])
        db.session.commit()
        sync.drain_template_sync_jobs(max_jobs=100)
        self.assertEqual(self._read(opted_out)["applied_release_id"], self.first["id"])
        self.assertEqual(db.session.query(TemplateSyncJob).filter_by(release_id=target["id"], recipient_key="").count(), 1)
        self.assertEqual(db.session.query(TemplateSyncJob).filter_by(release_id=target["id"]).count(), 4)
        self.assertEqual(sync.drain_template_sync_jobs(max_jobs=100)["delivered_count"], 0)

    def test_conflict_is_durable_without_overwriting_local_work(self):
        edited = self.subscriptions[0]
        local = db.session.get(Template, edited["local_template_id"])
        local.front_html = "MY FRONT"
        db.session.commit()
        target = self._changed_release(front_html="UPSTREAM FRONT")
        result = sync.drain_template_sync_jobs(max_jobs=100)
        self.assertGreaterEqual(result["conflict_count"], 1)
        current = self._read(edited)
        self.assertEqual(current["applied_release_id"], self.first["id"])
        self.assertEqual(current["pending_update_json"]["to_release_id"], target["id"])
        self.assertEqual(current["pending_update_json"]["status"], "has_conflict")
        self.assertEqual(releases.template(db.session, edited["local_template_id"])["front_html"], "MY FRONT")

    def test_newer_applied_release_is_never_downgraded(self):
        second = self._changed_release()
        third = self._changed_release("3", back_html="THIRD")
        chosen = self.subscriptions[0]
        preparation = template_release_service.prepare_update(user_id=chosen["user_id"], template_id=chosen["local_template_id"], payload={"release_id": third["id"]})
        template_release_service.apply_update(user_id=chosen["user_id"], template_id=chosen["local_template_id"], payload={"preparation_id": preparation["id"]})
        result = sync.drain_template_sync_jobs(max_jobs=100)
        self.assertGreaterEqual(result["skipped_count"], 1)
        self.assertEqual(self._read(chosen)["applied_release_id"], third["id"])
        self.assertNotEqual(second["id"], third["id"])

    def test_delayed_older_job_preserves_newer_automatic_conflict(self):
        second = self._changed_release(front_html="SECOND")
        third = self._changed_release("3", front_html="THIRD")
        chosen = self.subscriptions[0]
        local = db.session.get(Template, chosen["local_template_id"])
        local.front_html = "MY FRONT"
        db.session.commit()
        subscription = self._read(chosen)
        local = releases.template(db.session, chosen["local_template_id"])
        prepared = template_release_service._prepare(db.session, subscription, local,
            {"release_id": third["id"]}, automatic=True)
        db.session.commit()
        self.assertEqual(prepared["status"], "has_conflict")
        sync.drain_template_sync_jobs(max_jobs=1)
        db.session.execute(sa.update(TemplateSyncJob.__table__).where(
            TemplateSyncJob.release_id == third["id"],
        ).values(available_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)))
        db.session.commit()
        result = sync.drain_template_sync_jobs(max_jobs=100)
        self.assertGreaterEqual(result["skipped_count"], 1)
        current = self._read(chosen)
        self.assertEqual(current["pending_update_json"]["id"], prepared["id"])
        self.assertEqual(current["pending_update_json"]["to_release_id"], third["id"])
        self.assertNotEqual(second["id"], current["pending_update_json"]["to_release_id"])
        sync.drain_template_sync_jobs(max_jobs=100,
            now_utc=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2))

    def test_failure_rolls_back_delivery_and_bounded_retry_keeps_diagnostics(self):
        target = self._changed_release()
        sync.drain_template_sync_jobs(max_jobs=1)
        chosen = self.subscriptions[0]
        def fail_after_write(session, subscription, local, payload):
            session.execute(sa.update(Template.__table__).where(Template.id == local["id"]).values(back_html="MUST ROLLBACK"))
            raise RuntimeError("sensitive content must never enter job error")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with patch.object(template_release_service, "_apply", side_effect=fail_after_write):
            for attempt in range(sync.MAX_ATTEMPTS):
                sync.drain_template_sync_jobs(max_jobs=100, now_utc=now + timedelta(minutes=10 * (attempt + 1)))
        row = db.session.execute(sa.select(TemplateSyncJob).where(TemplateSyncJob.release_id == target["id"], TemplateSyncJob.recipient_key == chosen["id"])).scalar_one()
        self.assertEqual(row.status, "failed")
        self.assertEqual(row.attempt_count, sync.MAX_ATTEMPTS)
        self.assertEqual(row.last_error_code, "RuntimeError")
        self.assertEqual(releases.template(db.session, chosen["local_template_id"])["back_html"], "BACK")

    def test_multiple_workers_deliver_each_recipient_once(self):
        target = self._changed_release()
        sync.drain_template_sync_jobs(max_jobs=1)
        barrier = threading.Barrier(2)
        def worker():
            with self.app.app_context():
                barrier.wait(timeout=10)
                return sync.drain_template_sync_jobs(max_jobs=100)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=20) for future in [pool.submit(worker), pool.submit(worker)]]
        self.assertEqual(sum(row["delivered_count"] for row in results), 3)
        self.assertEqual(db.session.query(TemplateSyncJob).filter_by(release_id=target["id"], status="done").count(), 4)
        for row in self.subscriptions:
            self.assertEqual(self._read(row)["applied_release_id"], target["id"])

    def test_staging_rolls_back_with_author_transaction(self):
        target = self._changed_release()
        count = db.session.query(TemplateSyncJob).filter_by(release_id=target["id"]).count()
        db.session.execute(sa.delete(TemplateSyncJob.__table__).where(TemplateSyncJob.release_id == target["id"]))
        sync.enqueue_template_release_sync(db.session, source_template_id=self.source_id, release_id=target["id"])
        db.session.rollback()
        self.assertEqual(db.session.query(TemplateSyncJob).filter_by(release_id=target["id"]).count(), count)

    def test_dispatch_is_bounded_and_resumes_without_duplicate_recipients(self):
        target = self._changed_release()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        first = sync.drain_template_sync_jobs(max_jobs=1, dispatcher_batch_size=1, now_utc=now)
        self.assertEqual(first["dispatched_count"], 1)
        jobs = db.session.query(TemplateSyncJob).filter_by(release_id=target["id"]).all()
        self.assertEqual(len(jobs), 2)
        dispatcher = next(row for row in jobs if row.recipient_key == "")
        self.assertEqual(dispatcher.status, "pending")
        self.assertEqual(dispatcher.after_subscription_id, min(row["id"] for row in self.subscriptions))
        db.session.rollback()
        for index in range(1, 10):
            result = sync.drain_template_sync_jobs(max_jobs=1, dispatcher_batch_size=1,
                now_utc=now + timedelta(seconds=index))
            self.assertLessEqual(result["dispatched_count"], 1)
            self.assertLessEqual(result["delivered_count"], 1)
        self.assertEqual(db.session.query(TemplateSyncJob).filter_by(release_id=target["id"], status="done").count(), 4)
        for row in self.subscriptions:
            self.assertEqual(self._read(row)["applied_release_id"], target["id"])
        EVIDENCE["bounded_dispatch"] = {"batch_size": 1, "max_jobs": 1, "recipient_count": 3,
            "resumed_without_duplicates": True}

    def test_locked_subscription_does_not_stall_publication_or_peers(self):
        blocked = self.subscriptions[0]
        with db.engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(sa.select(TemplateSubscription.id).where(
                TemplateSubscription.id == blocked["id"],
            ).with_for_update()).all()
            started = time.monotonic()
            target = self._changed_release()
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 2, "Publication waited on a subscriber row")
            result = sync.drain_template_sync_jobs(max_jobs=20)
            self.assertGreaterEqual(result["retrying_count"], 1)
            for row in self.subscriptions[1:]:
                self.assertEqual(self._read(row)["applied_release_id"], target["id"])
            self.assertEqual(self._read(blocked)["applied_release_id"], self.first["id"])
            transaction.rollback()
        sync.drain_template_sync_jobs(max_jobs=20,
            now_utc=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10))
        self.assertEqual(self._read(blocked)["applied_release_id"], target["id"])
        EVIDENCE["locked_subscription"] = {"publish_seconds": round(elapsed, 3),
            "peers_delivered_while_locked": True}

    def test_empty_queue_claim_does_not_gap_lock_author_and_resets_connection_isolation(self):
        db.session.rollback()
        with db.engine.connect() as connection:
            original_isolation = connection.execute(sa.text("SELECT @@transaction_isolation")).scalar_one()
        claimed = threading.Event()
        release_claim = threading.Event()
        original = sync.repository.claim_next
        worker_isolation = []
        def pause_claim(session, now):
            row = original(session, now)
            worker_isolation.append(session.execute(sa.text("SELECT @@transaction_isolation")).scalar_one())
            self.assertIsNone(row)
            claimed.set()
            if not release_claim.wait(timeout=10):
                raise AssertionError("Timed out waiting for concurrent author publication")
            return row
        def worker():
            with self.app.app_context():
                return sync.drain_template_sync_jobs(max_jobs=1)
        with patch.object(sync.repository, "claim_next", side_effect=pause_claim), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker)
            try:
                self.assertTrue(claimed.wait(timeout=10))
                started = time.monotonic()
                self._changed_release()
                elapsed = time.monotonic() - started
                self.assertLess(elapsed, 2, "Empty queue claim held an outbox gap lock")
            finally:
                release_claim.set()
            future.result(timeout=15)
        self.assertEqual(worker_isolation, ["READ-COMMITTED"])
        db.session.rollback()
        with db.engine.connect() as connection:
            self.assertEqual(connection.execute(sa.text("SELECT @@transaction_isolation")).scalar_one(), original_isolation)
        sync.drain_template_sync_jobs(max_jobs=100)
        EVIDENCE["worker_isolation"] = {"worker": worker_isolation[0],
            "original_connection_isolation_restored": original_isolation,
            "concurrent_publish_seconds": round(elapsed, 3)}

    def test_template_queue_failure_preserves_study_consumer_readiness_and_bounds(self):
        db.session.rollback()
        consumer = study_consumer_service.StudyBatchConsumer()
        empty = dict(processed_count=0, failed_count=0, retrying_count=0, skipped_count=0)
        with patch.object(study_consumer_service, "study_queue_prefix"), patch.object(
            study_consumer_service, "recover_admitted_study_batches", return_value={"next_cursor": None, "blocked": []},
        ), patch.object(study_consumer_service, "probe_study_worker_database"), patch.object(
            study_consumer_service, "publish_study_worker_heartbeat", return_value=True,
        ), patch.object(study_consumer_service, "drain_study_queue", return_value=empty), patch.object(
            study_consumer_service, "drain_template_sync_jobs", side_effect=RuntimeError("safe diagnostic only"),
        ) as template_drain:
            result = consumer.step()
        self.assertTrue(result["ready"])
        self.assertIsNone(result["template_sync"])
        template_drain.assert_called_once_with(max_jobs=3)

    def test_queue_status_is_read_only_and_does_not_expose_content(self):
        target = self._changed_release()
        before = db.session.query(TemplateSyncJob).count()
        statements = []
        def capture(_conn, _cursor, statement, *_args):
            statements.append(statement)
        sa.event.listen(db.engine, "before_cursor_execute", capture)
        try:
            result = sync.inspect_template_sync_queue()
        finally:
            sa.event.remove(db.engine, "before_cursor_execute", capture)
        self.assertTrue(statements)
        self.assertTrue(all(statement.lstrip().upper().startswith("SELECT") for statement in statements))
        self.assertGreaterEqual(result["counts"]["pending"], 1)
        self.assertGreaterEqual(result["ready_count"], 1)
        self.assertIsNotNone(result["oldest_ready_at"])
        self.assertEqual(db.session.query(TemplateSyncJob).count(), before)
        serialized = json.dumps(result)
        self.assertNotIn(self.source_id, serialized)
        self.assertNotIn("NEW BACK", serialized)
        sync.drain_template_sync_jobs(max_jobs=100)

    def test_operational_cli_reports_safe_status_and_rejects_unbounded_work(self):
        self._changed_release()
        runner = self.app.test_cli_runner()
        status = runner.invoke(args=["template-sync-status"])
        self.assertEqual(status.exit_code, 0, status.output)
        summary = json.loads(status.output)
        self.assertGreaterEqual(summary["ready_count"], 1)
        self.assertNotIn(self.source_id, status.output)
        for arguments in (["--max-jobs", "0"], ["--max-jobs", "1001"], ["--batch-size", "501"]):
            rejected = runner.invoke(args=["template-sync-drain", *arguments])
            self.assertEqual(rejected.exit_code, 2)
        drained = runner.invoke(args=["template-sync-drain", "--max-jobs", "1", "--batch-size", "1"])
        self.assertEqual(drained.exit_code, 0, drained.output)
        self.assertEqual(json.loads(drained.output)["dispatched_count"], 1)
        sync.drain_template_sync_jobs(max_jobs=100,
            now_utc=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=10))


def run(env_file):
    load_dotenv(env_file, override=False)
    settings = _connection_settings()
    name = f"flama_template_sync_probe_{os.getpid()}_{secrets.token_hex(6)}"
    source = os.getenv("DB_NAME", "").strip()
    def guard():
        if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME.fullmatch(name) or name == source:
            raise RuntimeError("Template sync probe requires a unique generated loopback schema.")
    guard()
    admin = pymysql.connect(**settings)
    created, app = False, None
    report = {"status": "FAIL", "configured_database_modified": False}
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
            if cursor.fetchone():
                raise RuntimeError("Generated database already exists.")
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name), "WTF_CSRF_ENABLED": False})
        register_template_sync_commands(app)
        with app.app_context():
            guard()
            if db.engine.url.database != name or set(db.engines) != {None}:
                raise RuntimeError("Probe engine points outside generated database.")
            db.create_all()
            revision = importlib.import_module("migrations.versions.20261020_000071_template_sync_jobs")
            with db.engine.begin() as connection:
                with Operations.context(MigrationContext.configure(connection)):
                    revision.downgrade()
                    revision.upgrade()
                    revision.upgrade()
                    op.drop_index("ix_template_sync_jobs_pending", table_name="template_sync_jobs")
                    revision.upgrade()
                    assert "ix_template_sync_jobs_pending" in {
                        row["name"] for row in sa.inspect(connection).get_indexes("template_sync_jobs")
                    }
            report["migration_empty_reupgrade"] = True
            report["migration_repairs_interrupted_index_creation"] = True
        TemplateSyncMySQLTests.app = app
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(unittest.defaultTestLoader.loadTestsFromTestCase(TemplateSyncMySQLTests))
        report.update(status="PASS" if result.wasSuccessful() else "FAIL", tests_run=result.testsRun,
            failures=len(result.failures), errors=len(result.errors), evidence=EVIDENCE)
        if not result.wasSuccessful():
            report["failed_cases"] = [case.id() for case, _ in result.failures + result.errors]
            report["failure_details"] = [trace for _, trace in result.failures + result.errors]
        with app.app_context(), db.engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                try:
                    revision.downgrade()
                except RuntimeError:
                    report["migration_preserves_delivery_history"] = True
                else:
                    raise AssertionError("Nonempty queue was dropped by downgrade")
        return report
    finally:
        if app:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            guard()
            if name == os.getenv("DB_NAME", "").strip():
                raise RuntimeError("Probe overlaps configured database; refusing cleanup.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
            report["probe_database_dropped"] = True
        admin.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    report = run(args.env_file)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "PASS" else 1)
