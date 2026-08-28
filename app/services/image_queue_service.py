"""Redis queue manager for asynchronous image processing jobs."""

from __future__ import annotations

from collections import deque
from datetime import datetime
import json
import logging
import threading
from typing import Any

from flask import current_app

from app.services.redis_state_service import SharedStateUnavailable, redis_client

logger = logging.getLogger(__name__)

IMAGE_QUEUE_KEY = "flama:images:queue"
IMAGE_LOCK_PREFIX = "flama:images:lock:"

# In-memory fallback queue for local development and testing
_LOCAL_QUEUE: deque[dict[str, Any]] = deque()
_LOCAL_LOCK = threading.Lock()


def is_redis_available() -> bool:
    try:
        client = redis_client()
        return client.ping() is True
    except Exception:
        return False


def enqueue_image_job(
    asset_id: str,
    *,
    source_url: str | None = None,
    usage_type: str = "general",
    preset: str | None = None,
) -> bool:
    """Enqueue an image processing job into Redis (or local memory queue fallback)."""
    job_payload = {
        "asset_id": asset_id,
        "source_url": source_url,
        "usage_type": usage_type,
        "preset": preset,
        "attempts": 0,
        "enqueued_at": datetime.utcnow().isoformat(),
    }
    encoded = json.dumps(job_payload)

    try:
        client = redis_client()
        client.rpush(IMAGE_QUEUE_KEY, encoded)
        logger.info("Enqueued image job to Redis queue: %s", asset_id)
        return True
    except (SharedStateUnavailable, Exception) as exc:
        logger.debug("Redis queue unavailable (%s), enqueuing to local in-memory queue.", exc)
        with _LOCAL_LOCK:
            _LOCAL_QUEUE.append(job_payload)
        return True


def pop_image_job(*, timeout: int = 1) -> dict[str, Any] | None:
    """Pop a pending job from the queue."""
    try:
        client = redis_client()
        result = client.blpop(IMAGE_QUEUE_KEY, timeout=timeout)
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
    """Get the current number of pending items in the image queue."""
    try:
        client = redis_client()
        return int(client.llen(IMAGE_QUEUE_KEY) or 0)
    except Exception:
        with _LOCAL_LOCK:
            return len(_LOCAL_QUEUE)


def clear_image_queue() -> None:
    """Clear all pending items (useful in test teardown)."""
    try:
        client = redis_client()
        client.delete(IMAGE_QUEUE_KEY)
    except Exception:
        pass
    with _LOCAL_LOCK:
        _LOCAL_QUEUE.clear()
