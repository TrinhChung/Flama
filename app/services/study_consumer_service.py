"""Continuous Study consumer: periodic outbox sweeps, bounded queue passes."""

from dataclasses import dataclass
import logging
import math
import time
from uuid import uuid4

from sqlalchemy import select

from app.services.study_queue_namespace import study_queue_prefix
from app.services.study_worker_readiness_service import (
    HEARTBEAT_TTL_SECONDS,
    publish_study_worker_heartbeat,
    withdraw_study_worker_heartbeat,
)
from app.services.study_worker_service import drain_study_queue, recover_admitted_study_batches
from app.services.template_subscription_sync_service import drain_template_sync_jobs
from models import db
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_session_authority_pin import StudySessionAuthorityPin
from models.study_session_batch import StudySessionBatch

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StudyConsumerOptions:
    recovery_interval: float = 5.0
    heartbeat_interval: float = 5.0
    idle_interval: float = 0.25
    template_sync_interval: float = 5.0
    error_backoff: float = 1.0
    recovery_page_size: int = 100
    jobs_per_pass: int = 10

    def __post_init__(self):
        for name in ("recovery_interval", "heartbeat_interval", "idle_interval", "template_sync_interval", "error_backoff"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite interval.")
        if self.heartbeat_interval >= HEARTBEAT_TTL_SECONDS / 2:
            raise ValueError("Heartbeat interval must be less than half the worker TTL.")
        for name in ("recovery_page_size", "jobs_per_pass"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 1000:
                raise ValueError(f"{name} must be between 1 and 1000.")


def probe_study_worker_database():
    """Check mapped worker columns without startup repair, writes or payload reads.

    An empty outbox must not hide a missing NOTE table or attempt_count migration.
    This is a liveness/schema compatibility probe, not migration certification.
    """
    if db.session().in_transaction():
        raise RuntimeError("Worker readiness requires a transaction-neutral session.")
    try:
        for model in (
            StudySessionBatch, StudySession, StudySessionAuthorityPin,
            StudyAuthorityEnrollment, StudyAuthorityCommandReceipt,
            StudyProgressSubject, StudyProgressHistoryFact,
        ):
            db.session.execute(select(model.__table__).limit(0)).close()
    finally:
        db.session.rollback()


class StudyBatchConsumer:
    def __init__(self, *, options: StudyConsumerOptions | None = None, clock=time.monotonic):
        self.options = options or StudyConsumerOptions()
        self.clock = clock
        self.worker_id = uuid4().hex
        self.cursor = None
        self.next_recovery = 0.0
        self.next_heartbeat = 0.0
        self.next_template_sync = 0.0
        self.ready = False

    def step(self):
        """One bounded pass; recovery also runs when queue traffic is continuous."""
        study_queue_prefix(require_namespace=True)
        if db.session().in_transaction():
            raise RuntimeError("Consumer requires a transaction-neutral session.")
        now = self.clock()
        recovery = None
        if now >= self.next_recovery:
            recovery = recover_admitted_study_batches(max_jobs=self.options.recovery_page_size, after=self.cursor)
            self.cursor = recovery["next_cursor"]
            self.next_recovery = self.clock() + self.options.recovery_interval
            if recovery["blocked"]:
                logger.warning("Study outbox scan found %d blocked admissions; continuing the sweep.", len(recovery["blocked"]))
        if self.clock() >= self.next_heartbeat:
            probe_study_worker_database()
            ready = publish_study_worker_heartbeat(self.worker_id)
            if ready != self.ready:
                logger.info("Study consumer shared readiness=%s", ready)
            self.ready = ready
            self.next_heartbeat = self.clock() + self.options.heartbeat_interval
        counts = drain_study_queue(max_jobs=self.options.jobs_per_pass, recover_when_idle=False)
        template_sync = None
        # Each claim is a database transaction. Claiming on every idle pass was
        # most of MySQL's load while nobody studied; claim again at once only
        # while jobs keep coming, otherwise after template_sync_interval.
        if self.clock() >= self.next_template_sync:
            try:
                template_sync = drain_template_sync_jobs(max_jobs=min(3, self.options.jobs_per_pass))
            except Exception as exc:
                # A template queue outage must not withdraw study-worker readiness.
                logger.error("Template sync pass failed (%s); durable jobs will retry.", type(exc).__name__)
            if not (template_sync and any(template_sync.values())):
                self.next_template_sync = self.clock() + self.options.template_sync_interval
        return {"recovery": recovery, "ready": self.ready, "template_sync": template_sync, **counts}

    def withdraw(self):
        self.ready = False
        self.next_heartbeat = 0.0
        return withdraw_study_worker_heartbeat(self.worker_id)


def run_study_consumer(app, *, stop_event, consumer: StudyBatchConsumer | None = None):
    """SIGTERM sets stop_event; finish the current bounded pass, then withdraw.

    No readiness side-thread, no admission-flag check: already accepted DB rows
    must still drain after a rollout switch is disabled or Redis loses hints.
    """
    consumer = consumer or StudyBatchConsumer()
    with app.app_context():
        study_queue_prefix(require_namespace=True)
    try:
        while not stop_event.is_set():
            delay = 0.0
            with app.app_context():
                try:
                    result = consumer.step()
                    if result["retrying_count"] or not sum(result[name] for name in (
                        "processed_count", "failed_count", "retrying_count", "skipped_count",
                    )):
                        delay = consumer.options.idle_interval
                except Exception as exc:
                    # Do not log SQL parameters, session tokens or learner payloads.
                    logger.error("Study consumer pass failed (%s); durable outbox will retry.", type(exc).__name__)
                    consumer.withdraw()
                    delay = consumer.options.error_backoff
                finally:
                    # App contexts are per-pass: release failed reads, locks and
                    # the identity map before any wait or the next DB snapshot.
                    db.session.remove()
            if delay:
                stop_event.wait(delay)
    finally:
        with app.app_context():
            consumer.withdraw()
