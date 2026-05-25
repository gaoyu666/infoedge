from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime
from typing import Any, Awaitable, Callable, TypeVar

import redis.asyncio as redis

from app.core.config import settings


logger = logging.getLogger(__name__)
T = TypeVar("T")

_client: redis.Redis | None = None
_memory_cache: dict[str, tuple[float, Any]] = {}
_redis_disabled_until = 0.0
_redis_failure_count = 0

REDIS_RETRY_DELAY_SECONDS = 300.0
MEMORY_CACHE_MAX_TTL_SECONDS = 300


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def get_cache_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=0.1,
            socket_timeout=0.25,
            health_check_interval=30,
        )
    return _client


def _redis_available(now: float | None = None) -> bool:
    return (now or time.monotonic()) >= _redis_disabled_until


def _mark_redis_failure(exc: Exception) -> None:
    global _redis_disabled_until, _redis_failure_count
    _redis_failure_count += 1
    _redis_disabled_until = time.monotonic() + REDIS_RETRY_DELAY_SECONDS
    logger.warning(
        "Redis cache unavailable; falling back to memory cache for %.0fs: %s",
        REDIS_RETRY_DELAY_SECONDS,
        exc,
    )


def _mark_redis_success() -> None:
    global _redis_disabled_until, _redis_failure_count
    _redis_disabled_until = 0.0
    _redis_failure_count = 0


async def cache_get(key: str) -> Any | None:
    now = time.monotonic()
    memory_hit = _memory_cache.get(key)
    if memory_hit is not None:
        expires_at, value = memory_hit
        if expires_at > now:
            return value
        _memory_cache.pop(key, None)

    if not _redis_available(now):
        return None

    try:
        raw = await get_cache_client().get(key)
    except Exception as exc:
        _mark_redis_failure(exc)
        return None
    if not raw:
        _mark_redis_success()
        return None
    try:
        value = json.loads(raw)
        _memory_cache[key] = (now + 30, value)
        _mark_redis_success()
        return value
    except json.JSONDecodeError:
        return None


async def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    _memory_cache[key] = (time.monotonic() + min(ttl_seconds, MEMORY_CACHE_MAX_TTL_SECONDS), value)
    if not _redis_available():
        return
    try:
        payload = json.dumps(value, ensure_ascii=False, default=_json_default)
        await get_cache_client().setex(key, ttl_seconds, payload)
    except Exception as exc:
        _mark_redis_failure(exc)
    else:
        _mark_redis_success()


async def cached(key: str, ttl_seconds: int, loader: Callable[[], Awaitable[T]]) -> T:
    cached_value = await cache_get(key)
    if cached_value is not None:
        return cached_value
    value = await loader()
    await cache_set(key, value, ttl_seconds)
    return value


async def cache_delete_pattern(pattern: str) -> int:
    deleted = 0
    prefix = pattern.rstrip("*")
    for key in list(_memory_cache):
        if key.startswith(prefix):
            _memory_cache.pop(key, None)
    try:
        client = get_cache_client()
        async for key in client.scan_iter(match=pattern, count=100):
            deleted += await client.delete(key)
    except Exception as exc:
        _mark_redis_failure(exc)
    return deleted
