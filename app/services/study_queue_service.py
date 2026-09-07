"""Redis queue manager for asynchronous study review batches."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import logging
import threading
import time
from typing import Any

from app.services.redis_state_service import SharedStateUnavailable, redis_client

logger = logging.getLogger(__name__)

STUDY_QUEUE_KEY = "flama:study:queue"
STUDY_DLQ_KEY = "flama:study:dlq"
STUDY_BATCH_LOCK_PREFIX = "flama:study:lock:batch:"
STUDY_SESSION_LOCK_PREFIX = "flama:study:lock:session:"
STUDY_BATCH_PROCESSED_PREFIX = "flama:study:processed:"

# In-memory fallback structures for local development and testing
_LOCAL_QUEUE: deque[dict[str, Any]] = deque()
_LOCAL_DLQ: deque[dict[str, Any]] = deque()
_LOCAL_LOCKS: dict[str, float] = {}
_LOCAL_PROCESSED: set[str] = set()
_LOCAL_LOCK = threading.Lock()


def is_redis_available() -> bool:
    """Check if Redis connection is live."""
    try:
        client = redis_client()
        return client.ping() is True
    except Exception:
        return False


def enqueue_study_batch(job_payload: dict[str, Any]) -> bool:
    """Enqueue a review batch into Redis (or local memory queue fallback)."""
    payload_copy = dict(job_payload)
    if "enqueued_at" not in payload_copy:
        payload_copy["enqueued_at"] = datetime.now(timezone.utc).isoformat()
    if "attempts" not in payload_copy:
        payload_copy["attempts"] = 0
    if "max_retries" not in payload_copy:
        payload_copy["max_retries"] = 3

    batch_id = payload_copy.get("batch_id") or "unknown"
    encoded = json.dumps(payload_copy)

    try:
        client = redis_client()
        client.rpush(STUDY_QUEUE_KEY, encoded)
        logger.info(
            "Enqueued study batch to Redis queue: batch_id=%s, session_id=%s, events=%d",
            batch_id,
            payload_copy.get("session_id"),
            len(payload_copy.get("events") or []),
        )
        return True
    except (SharedStateUnavailable, Exception) as exc:
        logger.debug("Redis queue unavailable (%s), enqueuing study batch to in-memory queue: %s", exc, batch_id)
        with _LOCAL_LOCK:
            _LOCAL_QUEUE.append(payload_copy)
        return True


def pop_study_batch(*, timeout: int = 1) -> dict[str, Any] | None:
    """Pop a pending study batch from the queue."""
    try:
        client = redis_client()
        result = client.blpop(STUDY_QUEUE_KEY, timeout=timeout)
        if result and len(result) == 2:
            _, raw_data = result
            return json.loads(raw_data)
    except (SharedStateUnavailable, Exception):
        pass

    with _LOCAL_LOCK:
        if _LOCAL_QUEUE:
            return _LOCAL_QUEUE.popleft()
    return None


def get_queue_length() -> int:
    """Get the current number of pending items in the study queue."""
    try:
        client = redis_client()
        return int(client.llen(STUDY_QUEUE_KEY) or 0)
    except Exception:
        with _LOCAL_LOCK:
            return len(_LOCAL_QUEUE)


def get_dlq_length() -> int:
    """Get the current number of failed items in the study DLQ."""
    try:
        client = redis_client()
        return int(client.llen(STUDY_DLQ_KEY) or 0)
    except Exception:
        with _LOCAL_LOCK:
            return len(_LOCAL_DLQ)


def clear_study_queue() -> None:
    """Clear all pending items and locks (useful in test teardown)."""
    try:
        client = redis_client()
        client.delete(STUDY_QUEUE_KEY)
        client.delete(STUDY_DLQ_KEY)
    except Exception:
        pass
    with _LOCAL_LOCK:
        _LOCAL_QUEUE.clear()
        _LOCAL_DLQ.clear()
        _LOCAL_LOCKS.clear()
        _LOCAL_PROCESSED.clear()


def acquire_batch_lock(batch_id: str, timeout: int = 60) -> bool:
    """Acquire a distributed lock for a specific batch to prevent concurrent execution."""
    lock_key = f"{STUDY_BATCH_LOCK_PREFIX}{batch_id}"
    try:
        client = redis_client()
        acquired = bool(client.set(lock_key, "locked", ex=timeout, nx=True))
        if acquired:
            return True
        return False
    except Exception:
        pass

    now = time.time()
    with _LOCAL_LOCK:
        expires = _LOCAL_LOCKS.get(lock_key, 0)
        if expires > now:
            return False
        _LOCAL_LOCKS[lock_key] = now + timeout
        return True


def release_batch_lock(batch_id: str) -> None:
    """Release a batch lock."""
    lock_key = f"{STUDY_BATCH_LOCK_PREFIX}{batch_id}"
    try:
        client = redis_client()
        client.delete(lock_key)
    except Exception:
        pass
    with _LOCAL_LOCK:
        _LOCAL_LOCKS.pop(lock_key, None)


def acquire_session_lock(session_id: str, timeout: int = 60) -> bool:
    """Acquire a distributed lock for a study session to ensure sequential batch execution."""
    lock_key = f"{STUDY_SESSION_LOCK_PREFIX}{session_id}"
    try:
        client = redis_client()
        acquired = bool(client.set(lock_key, "locked", ex=timeout, nx=True))
        if acquired:
            return True
        return False
    except Exception:
        pass

    now = time.time()
    with _LOCAL_LOCK:
        expires = _LOCAL_LOCKS.get(lock_key, 0)
        if expires > now:
            return False
        _LOCAL_LOCKS[lock_key] = now + timeout
        return True


def release_session_lock(session_id: str) -> None:
    """Release a session lock."""
    lock_key = f"{STUDY_SESSION_LOCK_PREFIX}{session_id}"
    try:
        client = redis_client()
        client.delete(lock_key)
    except Exception:
        pass
    with _LOCAL_LOCK:
        _LOCAL_LOCKS.pop(lock_key, None)


def is_batch_processed(batch_id: str) -> bool:
    """Check if a batch was already marked as processed (idempotency)."""
    key = f"{STUDY_BATCH_PROCESSED_PREFIX}{batch_id}"
    try:
        client = redis_client()
        return bool(client.exists(key))
    except Exception:
        pass
    with _LOCAL_LOCK:
        return batch_id in _LOCAL_PROCESSED


def mark_batch_processed(batch_id: str, ttl: int = 604800) -> None:
    """Mark a batch as processed with TTL (default: 7 days)."""
    key = f"{STUDY_BATCH_PROCESSED_PREFIX}{batch_id}"
    try:
        client = redis_client()
        client.set(key, "1", ex=ttl)
    except Exception:
        pass
    with _LOCAL_LOCK:
        _LOCAL_PROCESSED.add(batch_id)


def push_to_dlq(job_payload: dict[str, Any], error_message: str) -> None:
    """Push an exhausted or permanently failing job to Dead-Letter Queue."""
    record = dict(job_payload)
    record["failed_at"] = datetime.now(timezone.utc).isoformat()
    record["error"] = error_message
    encoded = json.dumps(record)

    try:
        client = redis_client()
        client.rpush(STUDY_DLQ_KEY, encoded)
        logger.error(
            "Pushed study batch %s to DLQ: %s",
            job_payload.get("batch_id"),
            error_message,
        )
    except Exception as exc:
        logger.error("Failed to push study batch %s to Redis DLQ (%s); storing locally.", job_payload.get("batch_id"), exc)
        with _LOCAL_LOCK:
            _LOCAL_DLQ.append(record)


def pop_dlq_job(*, timeout: int = 0) -> dict[str, Any] | None:
    """Pop a job from Dead-Letter Queue for diagnosis."""
    try:
        client = redis_client()
        if timeout > 0:
            result = client.blpop(STUDY_DLQ_KEY, timeout=timeout)
        else:
            raw = client.lpop(STUDY_DLQ_KEY)
            result = (STUDY_DLQ_KEY, raw) if raw else None
        if result and len(result) == 2:
            _, raw_data = result
            return json.loads(raw_data)
    except Exception:
        pass

    with _LOCAL_LOCK:
        if _LOCAL_DLQ:
            return _LOCAL_DLQ.popleft()
    return None
