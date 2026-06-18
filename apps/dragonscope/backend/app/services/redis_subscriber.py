"""Redis pub/sub → WebSocket bridge.

Subscribes to the 'market:updates' Redis channel that Celery workers publish to
when new data is collected. On each message, reads the full data from the
corresponding Redis key and broadcasts it to all subscribed WebSocket clients.
"""

import asyncio
import json
import logging

from app.redis import get_redis
from app.services.cache import get_cached_json
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)


async def start_redis_subscriber() -> None:
    """Long-running task: listen to Redis pub/sub and broadcast via WebSocket."""
    r = get_redis()
    if r is None:
        logger.warning("[RedisSubscriber] Redis not available, skipping subscriber")
        return

    pubsub = r.pubsub()
    await pubsub.subscribe("market:updates")
    logger.info("[RedisSubscriber] Subscribed to market:updates channel")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            try:
                payload = json.loads(message["data"])
                category = payload.get("category")
                if not category:
                    continue

                # Read the full data from Redis cache
                cached = await get_cached_json(f"market:{category}")
                if cached:
                    await ws_manager.broadcast(category, cached)
                    logger.debug(f"[RedisSubscriber] Broadcast {category} to {ws_manager.connection_count} clients")
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.warning(f"[RedisSubscriber] Broadcast error: {e}")
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("[RedisSubscriber] Shutting down")
        await pubsub.unsubscribe("market:updates")
        await pubsub.close()
    except Exception as e:
        logger.error(f"[RedisSubscriber] Fatal error: {e}")
