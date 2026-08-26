"""Small Redis adapter for state that must be shared by Gunicorn workers."""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
from typing import Any

from flask import current_app

logger = logging.getLogger(__name__)

_CLIENTS: dict[tuple[str, int, int], Any] = {}
_CLIENT_LOCK = threading.Lock()


class SharedStateUnavailable(RuntimeError):
    pass


def backend_mode(config_name: str, *, default: str = "local") -> str:
    mode = str(current_app.config.get(config_name, default) or default).strip().lower()
    return mode if mode in {"local", "shadow_redis", "redis"} else default


def redis_client():
    try:
        import redis
    except ImportError as exc:  # pragma: no cover - deployment dependency guard
        raise SharedStateUnavailable("redis package is not installed") from exc

    url = str(current_app.config.get("REDIS_URL") or "").strip()
    if not url:
        raise SharedStateUnavailable("REDIS_URL is not configured")
    connect_timeout = max(
        int(current_app.config.get("REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", 1)), 1
    )
    socket_timeout = max(
        int(current_app.config.get("REDIS_SOCKET_TIMEOUT_SECONDS", 1)), 1
    )
    cache_key = (url, connect_timeout, socket_timeout)
    with _CLIENT_LOCK:
        client = _CLIENTS.get(cache_key)
        if client is None:
            client = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=connect_timeout,
                socket_timeout=socket_timeout,
                health_check_interval=30,
            )
            _CLIENTS[cache_key] = client
    return client


def private_key(namespace: str, value: str) -> str:
    secret = str(
        current_app.config.get("RATE_LIMIT_HMAC_KEY")
        or current_app.config.get("SECRET_KEY")
        or "development-only"
    ).encode("utf-8")
    digest = hmac.new(secret, str(value).encode("utf-8"), hashlib.sha256).hexdigest()
    prefix = str(current_app.config.get("RATE_LIMIT_KEY_PREFIX", "flama:v1")).strip(":")
    return f"{prefix}:{namespace}:{digest}"


def clear_client_cache() -> None:
    with _CLIENT_LOCK:
        _CLIENTS.clear()
