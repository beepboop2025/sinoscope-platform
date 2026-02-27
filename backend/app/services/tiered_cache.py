"""
Two-level tiered cache: L1 in-memory LRU + L2 Redis.

Lookup order: L1 (memory, 5s TTL) -> L2 (Redis, configurable TTL) -> miss.
Writes populate both layers. Invalidation removes from both.

Usage:
    from app.services.tiered_cache import get_cache

    cache = get_cache()
    await cache.set("prices:BTC", {"price": 65000}, ttl=60)
    val = await cache.get("prices:BTC")  # L1 hit
"""

import json
import logging
import time
from collections import OrderedDict
from typing import Any

from app.redis import get_redis

logger = logging.getLogger(__name__)

L1_DEFAULT_TTL = 5.0       # seconds — short to avoid stale reads
L1_MAX_SIZE = 1024          # max entries in in-memory cache
L2_DEFAULT_TTL = 120        # seconds


class _L1Cache:
    """In-memory LRU cache with per-key TTL."""

    def __init__(self, max_size: int = L1_MAX_SIZE) -> None:
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None

        value, expires_at = entry
        if time.monotonic() > expires_at:
            # Expired — evict
            del self._store[key]
            return None

        # Move to end (most recently used)
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl: float = L1_DEFAULT_TTL) -> None:
        expires_at = time.monotonic() + ttl
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, expires_at)
        self._evict_if_needed()

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def _evict_if_needed(self) -> None:
        """Evict expired entries first, then oldest if still over max size."""
        now = time.monotonic()

        # Pass 1: remove expired
        expired_keys = [
            k for k, (_, exp) in self._store.items() if now > exp
        ]
        for k in expired_keys:
            del self._store[k]

        # Pass 2: evict oldest if still over limit
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)


class TieredCache:
    """
    Two-tier cache: fast in-memory L1 backed by Redis L2.

    Args:
        l1_ttl: Time-to-live for L1 entries in seconds.
        l2_ttl: Default time-to-live for L2 entries in seconds.
        l1_max_size: Maximum number of entries in the L1 cache.
    """

    def __init__(
        self,
        l1_ttl: float = L1_DEFAULT_TTL,
        l2_ttl: int = L2_DEFAULT_TTL,
        l1_max_size: int = L1_MAX_SIZE,
    ) -> None:
        self._l1 = _L1Cache(max_size=l1_max_size)
        self._l1_ttl = l1_ttl
        self._l2_ttl = l2_ttl

    async def get(self, key: str) -> Any | None:
        """
        Retrieve a value by key.

        Checks L1 first, then L2. On L2 hit, the value is promoted to L1.
        Returns None on miss.
        """
        # L1 check
        val = self._l1.get(key)
        if val is not None:
            return val

        # L2 check
        try:
            r = get_redis()
            raw = await r.get(f"tc:{key}")
        except Exception as e:
            logger.warning("TieredCache L2 get error for %s: %s", key, e)
            return None

        if raw is None:
            return None

        try:
            val = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None

        # Promote to L1
        self._l1.set(key, val, self._l1_ttl)
        return val

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Store a value in both L1 and L2.

        Args:
            key: Cache key.
            value: JSON-serializable value.
            ttl: L2 TTL in seconds. Defaults to the instance's l2_ttl.
        """
        l2_ttl = ttl if ttl is not None else self._l2_ttl

        # L1
        self._l1.set(key, value, self._l1_ttl)

        # L2
        try:
            r = get_redis()
            await r.set(f"tc:{key}", json.dumps(value, default=str), ex=l2_ttl)
        except Exception as e:
            logger.warning("TieredCache L2 set error for %s: %s", key, e)

    async def invalidate(self, key: str) -> None:
        """Remove a key from both cache tiers."""
        self._l1.delete(key)

        try:
            r = get_redis()
            await r.delete(f"tc:{key}")
        except Exception as e:
            logger.warning("TieredCache L2 invalidate error for %s: %s", key, e)

    def clear_l1(self) -> None:
        """Clear the in-memory L1 cache (useful in tests or hot-reload)."""
        self._l1.clear()


# ── Singleton ─────────────────────────────────────────────────────────────────

_instance: TieredCache | None = None


def get_cache() -> TieredCache:
    """Return the singleton TieredCache instance."""
    global _instance
    if _instance is None:
        _instance = TieredCache()
    return _instance
