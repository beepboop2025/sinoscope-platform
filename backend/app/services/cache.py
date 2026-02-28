import json
import logging
from typing import Any

from app.redis import get_redis

logger = logging.getLogger(__name__)

MARKET_DATA_TTL = 120  # seconds


async def get_cached_json(key: str) -> Any | None:
    """Get a JSON value from Redis cache."""
    try:
        r = get_redis()
        val = await r.get(key)
        if val:
            return json.loads(val)
    except Exception as e:
        logger.warning(f"Redis get error for {key}: {e}")
    return None


async def set_cached_json(key: str, value: Any, ttl: int = MARKET_DATA_TTL) -> None:
    """Set a JSON value in Redis with TTL."""
    try:
        r = get_redis()
        await r.set(key, json.dumps(value), ex=ttl)
    except Exception as e:
        logger.warning(f"Redis set error for {key}: {e}")


async def invalidate_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern."""
    try:
        r = get_redis()
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break
    except Exception as e:
        logger.warning(f"Redis invalidate error for {pattern}: {e}")


async def publish_update(channel: str, data: Any) -> None:
    """Publish an update to a Redis pub/sub channel."""
    try:
        r = get_redis()
        await r.publish(channel, json.dumps(data))
    except Exception as e:
        logger.warning(f"Redis publish error for {channel}: {e}")
