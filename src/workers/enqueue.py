"""Enqueue Arq worker jobs — Sprint 4."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Optional
from urllib.parse import urlparse

from arq.connections import RedisSettings
from loguru import logger

_pool = None


def redis_settings_from_env() -> RedisSettings:
    """Arq Redis settings. Default conn_timeout=1s is too tight on Docker Desktop."""
    parsed = urlparse(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or "0"),
        password=parsed.password,
        conn_timeout=10,
        conn_retries=10,
        conn_retry_delay=2,
        retry_on_timeout=True,
    )


@lru_cache(maxsize=1)
def _worker_enabled() -> bool:
    return os.getenv("ARQ_WORKER_ENABLED", "false").lower() in ("1", "true", "yes")


async def enqueue_process_report_ai(
    *,
    report_id: str,
    user_id: str,
    report_type: str,
    category: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    matched_to_report_id: Optional[str] = None,
) -> bool:
    payload: dict[str, Any] = {
        "report_id": report_id,
        "user_id": user_id,
        "report_type": report_type,
        "category": category,
        "title": title,
        "description": description,
        "latitude": latitude,
        "longitude": longitude,
        "matched_to_report_id": matched_to_report_id,
    }
    if not _worker_enabled():
        logger.info("ARQ disabled — stub process_report_ai {}", payload)
        return False
    try:
        global _pool
        from arq import create_pool

        if _pool is None:
            _pool = await create_pool(redis_settings_from_env())
        await _pool.enqueue_job("process_report_ai", **payload)
        logger.info("Enqueued process_report_ai {}", report_id)
        return True
    except Exception as exc:
        logger.warning("Enqueue failed ({}): stub log {}", exc, payload)
        return False


async def enqueue_compute_matches(
    *,
    report_id: str,
    user_id: str,
    report_type: str,
    matched_to_report_id: Optional[str] = None,
    redis: Any = None,
) -> bool:
    """Enqueue compute_matches job after AI pipeline completes.

    Pass the worker's ``ctx['redis']`` when calling from a job so we do not
    open a second pool that can drop the worker's own broker connection.
    """
    payload: dict[str, Any] = {
        "report_id": report_id,
        "user_id": user_id,
        "report_type": report_type,
        "matched_to_report_id": matched_to_report_id,
    }
    if not _worker_enabled():
        logger.info("ARQ disabled — stub compute_matches {}", payload)
        return False
    try:
        pool = redis
        if pool is None:
            global _pool
            from arq import create_pool

            if _pool is None:
                _pool = await create_pool(redis_settings_from_env())
            pool = _pool
        await pool.enqueue_job("compute_matches", **payload)
        logger.info("Enqueued compute_matches {}", report_id)
        return True
    except Exception as exc:
        logger.warning("Enqueue compute_matches failed ({}): {}", exc, payload)
        return False
