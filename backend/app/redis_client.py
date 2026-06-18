"""Redis client – thin wrapper around redis-py with a lazy connection pool.

Feature flag REDIS_ENABLED lets tests / environments without Redis degrade
gracefully instead of crashing at import time.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from .config import REDIS_URL
from .logging_config import StructLogger as _SL
get_logger = _SL

logger = get_logger(__name__)

_client: Optional[Any] = None  # redis.Redis | None


def _get_client() -> Any:
    global _client
    if _client is not None:
        return _client
    try:
        import redis  # type: ignore

        _client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        _client.ping()
        logger.info("redis.connected", url=REDIS_URL)
    except Exception as exc:
        logger.warning("redis.unavailable", reason=str(exc))
        _client = None
    return _client


# ── helpers ──────────────────────────────────────────────────────────────────

def cache_get(key: str) -> Optional[Any]:
    r = _get_client()
    if r is None:
        return None
    try:
        val = r.get(key)
        return json.loads(val) if val is not None else None
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    r = _get_client()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def cache_delete(key: str) -> None:
    r = _get_client()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception:
        pass


def cache_delete_pattern(pattern: str) -> None:
    r = _get_client()
    if r is None:
        return
    try:
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass


def rate_limit_check(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    r = _get_client()
    if r is None:
        return True  # fail open when Redis is down
    try:
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        count, _ = pipe.execute()
        return count <= limit
    except Exception:
        return True


def publish_event(topic: str, payload: dict) -> None:
    """Publish a JSON payload to a Redis Pub/Sub channel."""
    r = _get_client()
    if r is None:
        return
    try:
        r.publish(topic, json.dumps(payload, default=str))
    except Exception as exc:
        logger.warning("redis.publish.error", topic=topic, reason=str(exc))
