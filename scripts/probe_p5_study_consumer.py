"""Real Redis + disposable local MySQL consumer restart/readiness probe.

Use a local Redis or an explicit SSH tunnel. Only a generated, DB-scoped Redis
namespace is written/removed; no FLUSHDB, global queue deletion or Redis restart.
Initial fixtures use test admission. The final NOTE batch is admitted with
TESTING=False through Flask after a real consumer heartbeat. Child consumers use
the standalone entrypoint, no startup repair and new admission disabled.
"""

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy.engine import make_url

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.redis_state_service import redis_client
from app.services.study_queue_namespace import study_queue_prefix
from app.services.study_queue_service import acquire_session_lock, enqueue_study_batch, release_session_lock
from app.services.study_worker_readiness_service import HEARTBEAT_TTL_SECONDS, has_ready_study_worker
from models import db
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from scripts.probe_p5_study_batch_mysql import PROBE_NAME_PATTERN, run_probe


def _validate_redis_url(value):
    url = make_url(value)
    if url.drivername != "redis" or url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use a local Redis URL or explicit local SSH tunnel.")
    return value


def _await(predicate, *, seconds, label):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.2)
    raise AssertionError(f"Timed out waiting for {label}.")


class ContinuousConsumerProbe:
    def __init__(self, redis_url):
        self.redis_url = _validate_redis_url(redis_url)
        self.report = {}

    def __call__(self, app, session_id, batch_ids, first_job, *, http_client, pending_payload, open_payload):
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        url = make_url(uri)
        if url.host not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(url.database or ""):
            raise RuntimeError("Consumer subprocess refuses a non-disposable/non-local database.")
        namespace = "p5_consumer_probe_" + uuid4().hex
        workers = []
        with patch.dict(app.config, REDIS_URL=self.redis_url, STUDY_QUEUE_NAMESPACE=namespace), app.app_context():
            prefix = study_queue_prefix(require_namespace=True)
            client = redis_client()
            client.ping()

            def launch(redis_url):
                env = dict(os.environ)
                env.update(
                    SQLALCHEMY_DATABASE_URI=uri, REDIS_URL=redis_url, STUDY_QUEUE_NAMESPACE=namespace,
                    STUDY_ASYNC_BATCH_ENABLED="0", STARTUP_RUN_MAINTENANCE="0",
                )
                process = subprocess.Popen(
                    [sys.executable, str(ROOT_DIR / "study_worker.py")], cwd=ROOT_DIR,
                    env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                workers.append(process)
                return process

            def live_ready(process):
                if process.poll() is not None:
                    raise AssertionError("Consumer exited before shared readiness.")
                return has_ready_study_worker("study-session.v4")

            def stop(process):
                if process.poll() is None:
                    process.kill()  # Only this probe's explicitly tracked child.
                process.wait(timeout=10)

            def completed():
                try:
                    session = db.session.get(StudySession, session_id)
                    return session.status == "committed"
                finally:
                    db.session.rollback()  # Fresh MySQL RR snapshot every poll.

            def post_batch(expected):
                with patch.dict(app.config, TESTING=False, STUDY_ASYNC_BATCH_ENABLED=True):
                    response = http_client.post(f"/api/study/sessions/{session_id}/batch", json=pending_payload)
                if response.status_code != expected:
                    raise AssertionError(f"Normal-mode admission returned {response.status_code}, expected {expected}.")
                if expected == 503 and response.get_json().get("error") != "ASYNC_BATCH_WORKER_UNAVAILABLE":
                    raise AssertionError("Readiness failure did not return its typed error.")
                if "no-store" not in response.headers.get("Cache-Control", ""):
                    raise AssertionError("Admission response is not private/no-store.")
                return response.get_json()

            def open_snapshot(*, advertised):
                with patch.dict(app.config, TESTING=False, STUDY_ASYNC_BATCH_ENABLED=True, STUDY_WIRE_V4_ENABLED=True):
                    response = http_client.post("/api/study/sessions", json=open_payload)
                if response.status_code != 201 or ("batch_transport" in response.get_json()) != advertised:
                    raise AssertionError("Normal-mode snapshot capability did not follow live readiness.")

            def read_receipt(*, status):
                with patch.dict(app.config, TESTING=False, STUDY_ASYNC_BATCH_ENABLED=False):
                    response = http_client.get(f"/api/study/sessions/{session_id}/batch/{pending_payload['batch_id']}")
                if response.status_code != 200 or response.get_json()["status"] != status:
                    raise AssertionError("Disabling admission/readiness hid a durable batch receipt.")
                return response.get_json()

            try:
                post_batch(503)
                open_snapshot(advertised=False)
                if StudySessionBatch.query.filter_by(session_id=session_id).count() != 2:
                    raise AssertionError("Not-ready HTTP created a durable admission.")
                db.session.rollback()
                # Hold the advisory lease so the first worker can prove liveness
                # but not consume the three already admitted NOTE batches.
                lease = acquire_session_lock(session_id, timeout=120)
                if not lease:
                    raise AssertionError("Could not own this probe session lease.")
                first = launch(self.redis_url)
                _await(lambda: live_ready(first), seconds=20, label="consumer heartbeat")
                open_snapshot(advertised=True)
                admitted = post_batch(202)
                if admitted["status"] != "enqueued" or admitted["event_count"] != 2:
                    raise AssertionError("Normal-mode HTTP did not admit the final two NOTE actions.")
                with patch.dict(app.config, STUDY_QUEUE_NAMESPACE=namespace + "_wrong"):
                    if has_ready_study_worker("study-session.v4"):
                        raise AssertionError("Wrong namespace borrowed readiness.")
                with patch.dict(app.config, SQLALCHEMY_DATABASE_URI=url.set(database=url.database + "_wrong").render_as_string(hide_password=False)):
                    if has_ready_study_worker("study-session.v4"):
                        raise AssertionError("Wrong database borrowed readiness.")
                if has_ready_study_worker("study-session.v999"):
                    raise AssertionError("Unsupported wire borrowed readiness.")
                stop(first)
                _await(lambda: not has_ready_study_worker("study-session.v4"), seconds=HEARTBEAT_TTL_SECONDS + 5, label="crashed worker TTL expiry")
                post_batch(503)
                read_receipt(status="enqueued")
                if completed():
                    raise AssertionError("Advisory session lock did not hold probe work.")
                if not release_session_lock(session_id, lease):
                    raise AssertionError("Probe session lease was not owned at release.")
                # Remove only this probe's Redis delivery hints. Durable rows are
                # untouched. Next process cannot reach Redis at all.
                client.delete(prefix + ":queue")
                with socket.socket() as unavailable:
                    unavailable.bind(("127.0.0.1", 0))  # Reserved but not listening.
                    outage_url = f"redis://127.0.0.1:{unavailable.getsockname()[1]}/0"
                    second = launch(outage_url)
                    _await(completed, seconds=35, label="outbox recovery without Redis")
                    if second.poll() is not None:
                        raise AssertionError("Outage worker stopped instead of continuing.")
                    if has_ready_study_worker("study-session.v4"):
                        raise AssertionError("Redis outage advertised shared readiness.")
                    stop(second)
                if read_receipt(status="completed")["receipt"]["cumulative_event_count"] != 4:
                    raise AssertionError("Normal-mode HTTP lost final receipt recovery after Redis outage.")

                # Restart with Redis restored. A duplicate identity must not add
                # another NOTE transition; the parent checks all four facts,
                # receipts and both sibling projections after this callback.
                enqueue_study_batch(first_job)
                third = launch(self.redis_url)
                _await(lambda: live_ready(third), seconds=20, label="restored Redis heartbeat")
                processed_key = prefix + ":processed:" + session_id + ":" + first_job["batch_id"]
                _await(lambda: client.exists(processed_key), seconds=70, label="duplicate receipt replay")
                stop(third)
                rows = StudySessionBatch.query.filter_by(session_id=session_id).all()
                if {row.batch_id for row in rows} != set(batch_ids) or any(row.status != "completed" for row in rows):
                    raise AssertionError("Consumer lost a durable admitted batch.")
                db.session.rollback()
                self.report = {
                    "continuous_consumer_real_entrypoint": "PASS",
                    "redis_heartbeat_crash_expiry": "PASS",
                    "redis_readiness_scope_and_wire_isolation": "PASS",
                    "note_outbox_restart_without_redis": "PASS",
                    "note_duplicate_hint_after_restart": "PASS",
                    "normal_mode_http_readiness_negotiation_and_admission": "PASS",
                    "normal_mode_receipt_recovery_without_admission": "PASS",
                    "production_database_modified": False,
                    "production_consumer_deployed": False,
                }
            finally:
                for process in workers:
                    stop(process)
                db.session.rollback()
                # Exact unique namespace + DB fingerprint, never a global key
                # pattern. Refuse every unexpected target before deleting it.
                keys = list(client.scan_iter(match=prefix + ":*", count=100))
                if any(not isinstance(key, str) or not key.startswith(prefix + ":") for key in keys):
                    raise RuntimeError("Refusing unexpected Redis cleanup target.")
                if keys:
                    client.delete(*keys)
                if list(client.scan_iter(match=prefix + ":*", count=100)):
                    raise AssertionError("Probe Redis keys remain after cleanup.")
                self.report["isolated_redis_namespace_removed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redis-url", required=True, type=_validate_redis_url)
    args = parser.parse_args()
    consumer_probe = ContinuousConsumerProbe(args.redis_url)
    report = run_probe(continuous_probe=consumer_probe)
    # The base probe separately reports no Redis coverage; this wrapper adds it.
    report.pop("production_consumer_or_redis_tested", None)
    report.update(consumer_probe.report, real_redis_continuous_consumer_tested=True)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
