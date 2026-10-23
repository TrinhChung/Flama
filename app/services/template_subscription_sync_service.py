"""Durable template release fan-out, isolated from the author's transaction.

A JSON recipient list would serialize all deliveries and their retry state on
one hot row. Normalized delivery rows let concurrent workers skip busy jobs.
Each claim, application and completion commits together while holding the job
lock: crashes roll back the claim; no expiring lease can cause a second apply.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.repositories import template_release_repository as releases
from app.repositories import template_sync_repository as repository
from models import db

MAX_ATTEMPTS = 6


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def inspect_template_sync_queue():
    """Read queue counters in an independent session for operator status."""
    with Session(bind=db.engine) as session:
        result = repository.queue_summary(session, _now())
        oldest = result["oldest_ready_at"]
        result["oldest_ready_at"] = oldest.replace(tzinfo=timezone.utc).isoformat() if oldest else None
        return result


def enqueue_template_release_sync(session, *, source_template_id, release_id):
    """Stage one dispatcher with the release; never flush/commit/read recipients."""
    now = _now()
    repository.insert_once(session, dict(
        source_template_id=source_template_id, release_id=release_id,
        recipient_key="", status="pending",
        attempt_count=0, available_at=now, created_at=now,
    ))


def _dispatch(session, job, *, limit, now):
    recipients = repository.recipient_page(session, job, limit)
    for subscription_id in recipients:
        repository.insert_once(session, dict(
            source_template_id=job["source_template_id"], release_id=job["release_id"],
            recipient_key=subscription_id,
            status="pending", attempt_count=0, available_at=now, created_at=job["created_at"],
        ))
    finished = len(recipients) < limit
    repository.update_job(session, job["id"],
        after_subscription_id=recipients[-1] if recipients else job["after_subscription_id"],
        status="done" if finished else "pending", completed_at=now if finished else None,
        # Let the newly dispatched page run before scanning another page.
        available_at=now + timedelta(milliseconds=100), last_error_code=None,
    )
    return "dispatched_count", len(recipients)


def _deliver(session, job):
    from app.services import template_release_service

    subscription, local = repository.lock_recipient(session, job["recipient_key"])
    if not subscription or not local or not subscription["auto_update_enabled"]:
        return "skipped_count", 1
    if subscription["source_template_id"] != job["source_template_id"]:
        raise ValueError("SYNC_SOURCE_MISMATCH")
    target = releases.release(session, job["release_id"], job["source_template_id"])
    applied = releases.release(session, subscription["applied_release_id"], job["source_template_id"])
    if target is None or applied is None:
        raise ValueError("SYNC_RELEASE_MISSING")
    if target["sequence_no"] <= applied["sequence_no"]:
        return "skipped_count", 1
    # Preserve a manual conflict-resolution preparation; automatic delivery must
    # not replace the user's work in progress.
    pending = subscription.get("pending_update_json")
    if pending and pending.get("mode") == "manual":
        return "skipped_count", 1
    if pending and pending.get("to_release_id"):
        prepared_target = releases.release(session, pending["to_release_id"], job["source_template_id"])
        if prepared_target and prepared_target["sequence_no"] > target["sequence_no"]:
            # A delayed retry of an older release must not replace a newer
            # automatic conflict the learner is already reviewing.
            return "skipped_count", 1
    pending = template_release_service._prepare(
        session, subscription, local, {"release_id": job["release_id"]}, automatic=True,
    )
    if pending["status"] != "ready":
        return "conflict_count", 1
    subscription["pending_update_json"] = pending
    template_release_service._apply(session, subscription, local, {"preparation_id": pending["id"]})
    return "delivered_count", 1


def _error_code(exc):
    # Never persist SQL parameters, HTML or learner data in queue diagnostics.
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    if args and isinstance(args[0], int):
        return f"MYSQL_{args[0]}"
    return str(getattr(exc, "code", type(exc).__name__))[:100]


def _record_failure(session, job_id, exc, now):
    # The failed delivery transaction was rolled back. Another worker may have
    # claimed it meanwhile; skip its lock and never overwrite a completed job.
    job = repository.lock_pending_job(session, job_id)
    if job is None:
        return "skipped_count"
    attempts = job["attempt_count"] + 1
    terminal = attempts >= MAX_ATTEMPTS
    repository.update_job(session, job_id, attempt_count=attempts,
        status="failed" if terminal else "pending",
        available_at=now + timedelta(seconds=min(300, 2 ** attempts)),
        completed_at=now if terminal else None, last_error_code=_error_code(exc))
    return "failed_count" if terminal else "retrying_count"


def drain_template_sync_jobs(*, max_jobs=10, dispatcher_batch_size=100, session_factory=None, now_utc=None):
    """Run bounded independent transactions; a busy recipient cannot stall peers.

    A source publication only stages the dispatcher. This drain is called by
    the existing continuous study consumer and is also available as Flask CLI.
    Failed jobs retain diagnostics after six attempts for operator inspection.
    """
    for name, value, maximum in (("max_jobs", max_jobs, 1000), ("dispatcher_batch_size", dispatcher_batch_size, 500)):
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError(f"{name} must be between 1 and {maximum}.")
    counts = {key: 0 for key in ("dispatched_count", "delivered_count", "conflict_count", "skipped_count", "retrying_count", "failed_count")}
    for _ in range(max_jobs):
        session = session_factory() if session_factory else Session(bind=db.engine, expire_on_commit=False)
        if session.in_transaction() or session.new or session.dirty or session.deleted:
            session.close()
            raise RuntimeError("Template sync requires a fresh worker Session.")
        job = None
        try:
            if session.get_bind().dialect.name == "mysql":
                # Queue claims need row locks, not REPEATABLE READ next-key
                # locks that could delay a concurrent author's outbox INSERT.
                # This is scoped to the worker connection and resets on close.
                session.connection(execution_options={"isolation_level": "READ COMMITTED"})
            now = now_utc or _now()
            job = repository.claim_next(session, now)
            if job is None:
                session.rollback()
                break
            if job["recipient_key"] == "":
                key, count = _dispatch(session, job, limit=dispatcher_batch_size, now=now)
            else:
                key, count = _deliver(session, job)
                repository.update_job(session, job["id"], status="done", completed_at=now, last_error_code=None)
            session.commit()
            counts[key] += count
        except Exception as exc:
            session.rollback()
            if job is None:
                raise
            key = _record_failure(session, job["id"], exc, now_utc or _now())
            session.commit()
            counts[key] += 1
        finally:
            session.close()
    return counts
