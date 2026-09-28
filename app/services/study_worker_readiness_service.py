"""Ephemeral worker liveness, never a substitute for durable batch receipts."""

import hashlib
import re

from app.services.redis_state_service import redis_client
from app.services.study_queue_namespace import study_queue_prefix
from app.services.study_note_storage_precision import NOTE_STORAGE_PROFILE

WORKER_WIRE_SCHEMAS = ("study-session.v2", "study-session.v3", "study-session.v4")
WORKER_CONTRACT = "study-consumer.v2|study-batch-job.v1|study-note-batch-job.v1|" + NOTE_STORAGE_PROFILE
HEARTBEAT_TTL_SECONDS = 30
_PUBLISH = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
redis.call('ZADD', KEYS[1], now + tonumber(ARGV[2]), ARGV[1])
redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[2]) * 2)
return 1
"""
_READ = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
return redis.call('ZCOUNT', KEYS[1], '(' .. now, '+inf')
"""


def _pool_key():
    contract_hash = hashlib.sha256((WORKER_CONTRACT + "|" + "|".join(WORKER_WIRE_SCHEMAS)).encode()).hexdigest()[:32]
    return f"{study_queue_prefix(require_namespace=True)}:workers:{contract_hash}"


def _check_worker_id(worker_id: str):
    if not isinstance(worker_id, str) or not re.fullmatch(r"[a-f0-9]{32}", worker_id):
        raise ValueError("worker_id must be a unique 32-character hexadecimal process identity.")


def publish_study_worker_heartbeat(worker_id: str) -> bool:
    """Call on the consumer thread only, after a successful fresh DB probe.

    Redis owns the clock. A hung/stopped consumer cannot extend its own lease;
    a lost Redis connection never falls back to process-local readiness.
    """
    _check_worker_id(worker_id)
    key = _pool_key()
    try:
        return redis_client().eval(_PUBLISH, 1, key, worker_id, HEARTBEAT_TTL_SECONDS * 1000) == 1
    except Exception:
        return False


def has_ready_study_worker(wire_schema: str) -> bool:
    if wire_schema not in WORKER_WIRE_SCHEMAS:
        return False
    try:
        return int(redis_client().eval(_READ, 1, _pool_key())) > 0
    except Exception:
        return False


def withdraw_study_worker_heartbeat(worker_id: str) -> bool:
    _check_worker_id(worker_id)
    key = _pool_key()
    try:
        redis_client().zrem(key, worker_id)
        return True
    except Exception:
        # TTL still removes a crashed/disconnected process. Never remove peers.
        return False
