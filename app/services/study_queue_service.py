"""Redis queue manager for asynchronous study review batches."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import logging
import secrets
import threading
import time
from typing import Any

from app.services.redis_state_service import SharedStateUnavailable, redis_client
from app.services.study_queue_namespace import study_queue_key, study_queue_prefix

logger = logging.getLogger(__name__)

STUDY_QUEUE_KEY = "flama:study:queue"
STUDY_DLQ_KEY = "flama:study:dlq"
STUDY_BATCH_LOCK_PREFIX = "flama:study:lock:batch:"
STUDY_SESSION_LOCK_PREFIX = "flama:study:lock:session:"
STUDY_BATCH_PROCESSED_PREFIX = "flama:study:processed:"

# In-memory fallback structures for local development and testing
_LOCAL_QUEUES: dict[str, deque[dict[str, Any]]] = {}
_LOCAL_DLQS: dict[str, deque[dict[str, Any]]] = {}
_LOCAL_LOCKS: dict[str, tuple[float, str]] = {}
_LOCAL_PROCESSED: set[str] = set()
_LOCAL_LOCK = threading.Lock()
_RELEASE_IF_OWNER = (
    "if redis.call('GET', KEYS[1]) == ARGV[1] then "
    "return redis.call('DEL', KEYS[1]) else return 0 end"
)


def is_redis_available() -> bool:
    """Check if Redis connection is live."""
    try:
        client = redis_client()
        return client.ping() is True
    except Exception:
        return False


def enqueue_study_batch(job_payload: dict[str, Any]) -> bool:
    """Enqueue a review batch into Redis (or local memory queue fallback)."""
    queue_key = study_queue_key("queue")
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
        client.rpush(queue_key, encoded)
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
            _LOCAL_QUEUES.setdefault(queue_key, deque()).append(payload_copy)
        return True


def pop_study_batch(*, timeout: int = 1) -> dict[str, Any] | None:
    """Pop a pending study batch from the queue."""
    queue_key = study_queue_key("queue")
    try:
        client = redis_client()
        if timeout > 0:
            result = client.blpop(queue_key, timeout=timeout)
        else:
            # BLPOP with zero waits forever and prevents idle outbox recovery.
            raw = client.lpop(queue_key)
            result = (queue_key, raw) if raw else None
        if result and len(result) == 2:
            _, raw_data = result
            decoded = json.loads(raw_data)
            if isinstance(decoded, dict):
                return decoded
    except (SharedStateUnavailable, Exception):
        pass

    with _LOCAL_LOCK:
        local_queue = _LOCAL_QUEUES.get(queue_key)
        if local_queue:
            return local_queue.popleft()
    return None


def get_queue_length() -> int:
    """Get the current number of pending items in the study queue."""
    queue_key = study_queue_key("queue")
    try:
        client = redis_client()
        return int(client.llen(queue_key) or 0)
    except Exception:
        with _LOCAL_LOCK:
            return len(_LOCAL_QUEUES.get(queue_key, ()))


def get_dlq_length() -> int:
    """Get the current number of failed items in the study DLQ."""
    dlq_key = study_queue_key("dlq")
    try:
        client = redis_client()
        return int(client.llen(dlq_key) or 0)
    except Exception:
        with _LOCAL_LOCK:
            return len(_LOCAL_DLQS.get(dlq_key, ()))


def clear_study_queue() -> None:
    """Clear this namespace only (test teardown, never a recovery operation)."""
    prefix = study_queue_prefix() + ":"
    queue_key, dlq_key = study_queue_key("queue"), study_queue_key("dlq")
    try:
        client = redis_client()
        client.delete(queue_key)
        client.delete(dlq_key)
    except Exception:
        pass
    with _LOCAL_LOCK:
        _LOCAL_QUEUES.pop(queue_key, None)
        _LOCAL_DLQS.pop(dlq_key, None)
        for key in tuple(_LOCAL_LOCKS):
            if key.startswith(prefix + "lock:"):
                del _LOCAL_LOCKS[key]
        _LOCAL_PROCESSED.difference_update(
            key for key in tuple(_LOCAL_PROCESSED) if key.startswith(prefix + "processed:")
        )


def _acquire_owned_lock(lock_key: str, timeout: int) -> str | None:
    owner_token = secrets.token_hex(16)
    lease_seconds = max(1, int(timeout))
    try:
        client = redis_client()
        return (
            owner_token
            if client.set(lock_key, owner_token, ex=lease_seconds, nx=True)
            else None
        )
    except Exception:
        pass

    now = time.time()
    with _LOCAL_LOCK:
        current = _LOCAL_LOCKS.get(lock_key)
        if current is not None and current[0] > now:
            return None
        _LOCAL_LOCKS[lock_key] = (now + lease_seconds, owner_token)
        return owner_token


def _release_owned_lock(lock_key: str, owner_token: str) -> bool:
    if not owner_token:
        return False
    try:
        client = redis_client()
        return bool(client.eval(_RELEASE_IF_OWNER, 1, lock_key, owner_token))
    except Exception:
        pass
    with _LOCAL_LOCK:
        current = _LOCAL_LOCKS.get(lock_key)
        if current is None or current[1] != owner_token:
            return False
        _LOCAL_LOCKS.pop(lock_key, None)
        return True


def acquire_batch_lock(batch_id: str, timeout: int = 60) -> str | None:
    """Return an owner token for this batch lock, or ``None`` when held."""

    return _acquire_owned_lock(study_queue_key(f"lock:batch:{batch_id}"), timeout)


def release_batch_lock(batch_id: str, owner_token: str) -> bool:
    """Release only this worker's batch lock."""

    return _release_owned_lock(study_queue_key(f"lock:batch:{batch_id}"), owner_token)


def acquire_session_lock(session_id: str, timeout: int = 60) -> str | None:
    """Return an owner token for the session lock, or ``None`` when held."""

    return _acquire_owned_lock(study_queue_key(f"lock:session:{session_id}"), timeout)


def release_session_lock(session_id: str, owner_token: str) -> bool:
    """Release only this worker's session lock."""

    return _release_owned_lock(study_queue_key(f"lock:session:{session_id}"), owner_token)


def is_batch_processed(batch_id: str) -> bool:
    """Check if a batch was already marked as processed (idempotency)."""
    key = study_queue_key(f"processed:{batch_id}")
    try:
        client = redis_client()
        return bool(client.exists(key))
    except Exception:
        pass
    with _LOCAL_LOCK:
        return key in _LOCAL_PROCESSED


def mark_batch_processed(batch_id: str, ttl: int = 604800) -> None:
    """Mark a batch as processed with TTL (default: 7 days)."""
    key = study_queue_key(f"processed:{batch_id}")
    try:
        client = redis_client()
        client.set(key, "1", ex=ttl)
    except Exception:
        pass
    with _LOCAL_LOCK:
        _LOCAL_PROCESSED.add(key)


def push_to_dlq(job_payload: dict[str, Any], error_message: str) -> None:
    """Push an exhausted or permanently failing job to Dead-Letter Queue."""
    dlq_key = study_queue_key("dlq")
    record = dict(job_payload)
    record["failed_at"] = datetime.now(timezone.utc).isoformat()
    record["error"] = error_message
    encoded = json.dumps(record)

    try:
        client = redis_client()
        client.rpush(dlq_key, encoded)
        logger.error(
            "Pushed study batch %s to DLQ: %s",
            job_payload.get("batch_id"),
            error_message,
        )
    except Exception as exc:
        logger.error("Failed to push study batch %s to Redis DLQ (%s); storing locally.", job_payload.get("batch_id"), exc)
        with _LOCAL_LOCK:
            _LOCAL_DLQS.setdefault(dlq_key, deque()).append(record)


def pop_dlq_job(*, timeout: int = 0) -> dict[str, Any] | None:
    """Pop a job from Dead-Letter Queue for diagnosis."""
    dlq_key = study_queue_key("dlq")
    try:
        client = redis_client()
        if timeout > 0:
            result = client.blpop(dlq_key, timeout=timeout)
        else:
            raw = client.lpop(dlq_key)
            result = (dlq_key, raw) if raw else None
        if result and len(result) == 2:
            _, raw_data = result
            return json.loads(raw_data)
    except Exception:
        pass

    with _LOCAL_LOCK:
        local_dlq = _LOCAL_DLQS.get(dlq_key)
        if local_dlq:
            return local_dlq.popleft()
    return None
