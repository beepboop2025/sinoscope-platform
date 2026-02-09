"""Shared utilities for collector tasks."""

import json
import logging
import time
from datetime import datetime
from typing import Any

import httpx
import redis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Synchronous Redis for Celery tasks
_sync_redis = None


def get_sync_redis():
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _sync_redis


def save_data(category: str, data: Any, ttl: int = 120) -> None:
    """Save data to Redis and publish update notification."""
    r = get_sync_redis()
    payload = {
        "_updated": datetime.utcnow().isoformat(),
        "_source": category,
        "data": data,
    }
    r.set(f"market:{category}", json.dumps(payload), ex=ttl)
    r.set("collector:last_update", datetime.utcnow().isoformat())
    # Publish for WebSocket broadcast
    r.publish("market:updates", json.dumps({"category": category, "timestamp": payload["_updated"]}))
    logger.info(f"[{category.upper()}] Data saved to Redis")

    # Persist to TimescaleDB (fire-and-forget)
    _persist_to_db(category, data)


def _persist_to_db(category: str, data: Any) -> None:
    """Write data to TimescaleDB if enabled. Failures are logged, never raised."""
    if not settings.TIMESCALE_ENABLED:
        return
    try:
        from collector.db_writer import persist
        persist(category, data)
    except Exception as e:
        logger.error(f"[{category.upper()}] TimescaleDB persist failed: {e}")


def safe_fetch(url: str, headers: dict | None = None, timeout: float = 15.0) -> httpx.Response:
    """Synchronous HTTP fetch with timeout."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url, headers=headers or {})
        resp.raise_for_status()
        return resp


# Rate limiter state (in-memory per worker)
_rate_limits: dict[str, dict] = {}


def create_limiter(name: str, max_tokens: int, window_ms: int) -> None:
    _rate_limits[name] = {"max": max_tokens, "window_ms": window_ms, "tokens": max_tokens, "last_refill": time.time() * 1000}


def can_request(name: str) -> bool:
    l = _rate_limits.get(name)
    if not l:
        return True
    now = time.time() * 1000
    elapsed = now - l["last_refill"]
    if elapsed >= l["window_ms"]:
        l["tokens"] = l["max"]
        l["last_refill"] = now
    return l["tokens"] > 0


def consume_token(name: str) -> None:
    l = _rate_limits.get(name)
    if l:
        # Refill check before consuming
        now = time.time() * 1000
        elapsed = now - l["last_refill"]
        if elapsed >= l["window_ms"]:
            l["tokens"] = l["max"]
            l["last_refill"] = now
        l["tokens"] -= 1


# Initialize rate limits
create_limiter("frankfurter", 25, 60000)
create_limiter("coingecko", 20, 60000)
create_limiter("fred", 80, 60000)
create_limiter("alphavantage", 20, 86400000)
create_limiter("fmp", 200, 86400000)
create_limiter("finnhub", 50, 60000)
create_limiter("github", 25, 3600000)
create_limiter("huggingface", 25, 60000)
create_limiter("defillama", 15, 60000)
create_limiter("reddit", 8, 60000)
create_limiter("sec", 8, 60000)
create_limiter("arxiv", 8, 60000)
create_limiter("gnews", 80, 86400000)
create_limiter("newsdata", 12, 86400000)
create_limiter("newsapiorg", 80, 86400000)
create_limiter("worldnews", 40, 86400000)
