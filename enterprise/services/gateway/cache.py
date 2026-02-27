"""
DragonScope Enterprise Cache Layer
Multi-tier caching with memory, Redis, and CDN support.
Supports: cache-aside, write-through, write-behind strategies.
"""

import asyncio
import hashlib
import json
import logging
import pickle
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Union, Set
from functools import wraps
from collections import OrderedDict

import aioboto3
import httpx
import redis.asyncio as redis
from pydantic import BaseModel

logger = logging.getLogger("cache")

T = TypeVar("T")


# =============================================================================
# Data Models
# =============================================================================

class CacheStrategy(Enum):
    """Cache write strategies."""
    CACHE_ASIDE = "cache_aside"      # Lazy loading
    WRITE_THROUGH = "write_through"  # Write to cache and DB together
    WRITE_BEHIND = "write_behind"    # Write to cache, async to DB
    REFRESH_AHEAD = "refresh_ahead"  # Proactive refresh before expiry


class CacheTier(Enum):
    """Cache storage tiers."""
    MEMORY = "memory"      # L1 - Local in-memory
    REDIS = "redis"        # L2 - Distributed cache
    CDN = "cdn"            # L3 - CDN edge cache


@dataclass
class CacheConfig:
    """Cache configuration."""
    # TTL settings
    default_ttl: int = 300  # 5 minutes
    ttl_variation: float = 0.1  # +/- 10% to prevent thundering herd
    
    # Tier settings
    memory_max_size: int = 10000
    memory_ttl: int = 60
    redis_ttl: int = 300
    cdn_ttl: int = 3600
    
    # Strategy
    strategy: CacheStrategy = CacheStrategy.CACHE_ASIDE
    
    # Warming
    warmup_keys: List[str] = field(default_factory=list)
    
    # Invalidation
    invalidate_on_write: bool = True
    tags: List[str] = field(default_factory=list)


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata."""
    value: T
    created_at: float
    ttl: int
    tags: Set[str] = field(default_factory=set)
    access_count: int = 0
    last_accessed: float = 0.0
    
    @property
    def is_expired(self) -> bool:
        return time.time() > self.created_at + self.ttl
    
    @property
    def remaining_ttl(self) -> int:
        remaining = int(self.created_at + self.ttl - time.time())
        return max(0, remaining)


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_gets: int = 0
    total_sets: int = 0
    total_deletes: int = 0
    hit_rate: float = 0.0
    avg_get_time_ms: float = 0.0
    avg_set_time_ms: float = 0.0
    size: int = 0
    memory_usage_bytes: int = 0


# =============================================================================
# Cache Backends
# =============================================================================

class CacheBackend(ABC, Generic[T]):
    """Abstract cache backend."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[CacheEntry[T]]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(
        self,
        key: str,
        value: T,
        ttl: int = None,
        tags: Set[str] = None
    ) -> bool:
        """Set value in cache."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """Clear all cache."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        pass
    
    @abstractmethod
    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with tag."""
        pass


class InMemoryCache(CacheBackend[T]):
    """
    L1 Cache: Local in-memory cache with LRU eviction.
    Thread-safe with asyncio lock.
    """
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 60):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._tag_index: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
        self._stats = CacheStats()
    
    async def get(self, key: str) -> Optional[CacheEntry[T]]:
        start_time = time.time()
        self._stats.total_gets += 1
        
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats.misses += 1
                return None
            
            if entry.is_expired:
                await self._remove(key)
                self._stats.misses += 1
                return None
            
            # Update access stats
            entry.access_count += 1
            entry.last_accessed = time.time()
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            
            self._stats.hits += 1
            self._update_hit_rate()
            self._stats.avg_get_time_ms = self._update_avg_time(
                self._stats.avg_get_time_ms, time.time() - start_time
            )
            
            return entry
    
    async def set(
        self,
        key: str,
        value: T,
        ttl: int = None,
        tags: Set[str] = None
    ) -> bool:
        start_time = time.time()
        self._stats.total_sets += 1
        
        async with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                await self._evict_lru()
            
            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl or self.default_ttl,
                tags=tags or set()
            )
            
            self._cache[key] = entry
            
            # Update tag index
            for tag in entry.tags:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(key)
            
            self._stats.size = len(self._cache)
            self._stats.avg_set_time_ms = self._update_avg_time(
                self._stats.avg_set_time_ms, time.time() - start_time
            )
            
            return True
    
    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                await self._remove(key)
                self._stats.total_deletes += 1
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired:
                return True
            return False
    
    async def clear(self) -> bool:
        async with self._lock:
            self._cache.clear()
            self._tag_index.clear()
            self._stats.size = 0
            return True
    
    async def get_stats(self) -> CacheStats:
        async with self._lock:
            stats = CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                total_gets=self._stats.total_gets,
                total_sets=self._stats.total_sets,
                total_deletes=self._stats.total_deletes,
                hit_rate=self._stats.hit_rate,
                avg_get_time_ms=self._stats.avg_get_time_ms,
                avg_set_time_ms=self._stats.avg_set_time_ms,
                size=len(self._cache)
            )
            # Estimate memory usage
            stats.memory_usage_bytes = sum(
                len(pickle.dumps(entry.value)) for entry in self._cache.values()
            )
            return stats
    
    async def invalidate_by_tag(self, tag: str) -> int:
        async with self._lock:
            keys = self._tag_index.get(tag, set()).copy()
            for key in keys:
                await self._remove(key)
            return len(keys)
    
    async def _remove(self, key: str):
        """Remove entry and update indexes."""
        if key in self._cache:
            entry = self._cache.pop(key)
            for tag in entry.tags:
                if tag in self._tag_index:
                    self._tag_index[tag].discard(key)
    
    async def _evict_lru(self):
        """Evict least recently used entry."""
        if self._cache:
            key, _ = self._cache.popitem(last=False)
            self._stats.evictions += 1
    
    def _update_hit_rate(self):
        """Update cache hit rate."""
        total = self._stats.hits + self._stats.misses
        if total > 0:
            self._stats.hit_rate = self._stats.hits / total
    
    def _update_avg_time(self, current_avg: float, new_time: float) -> float:
        """Update running average."""
        count = self._stats.total_gets + self._stats.total_sets
        if count > 1:
            return (current_avg * (count - 1) + new_time * 1000) / count
        return new_time * 1000
    
    async def get_ttl(self, key: str) -> int:
        """Get remaining TTL for key."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry:
                return entry.remaining_ttl
            return -1


class RedisCache(CacheBackend[T]):
    """
    L2 Cache: Distributed Redis cache.
    Supports clustering, persistence, and pub/sub invalidation.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis = None,
        redis_url: str = "redis://localhost:6379",
        default_ttl: int = 300,
        key_prefix: str = "cache:",
        serializer: str = "pickle"
    ):
        self.redis = redis_client or redis.from_url(redis_url)
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        self.serializer = serializer
        self._stats = CacheStats()
        self._pubsub_channel = "cache:invalidations"
    
    def _make_key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"
    
    def _serialize(self, value: T) -> bytes:
        if self.serializer == "json":
            return json.dumps(value).encode()
        return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> T:
        if self.serializer == "json":
            return json.loads(data.decode())
        return pickle.loads(data)
    
    async def get(self, key: str) -> Optional[CacheEntry[T]]:
        start_time = time.time()
        self._stats.total_gets += 1
        
        try:
            data = await self.redis.get(self._make_key(key))
            
            if data is None:
                self._stats.misses += 1
                return None
            
            entry = self._deserialize(data)
            
            if isinstance(entry, CacheEntry) and entry.is_expired:
                await self.delete(key)
                self._stats.misses += 1
                return None
            
            self._stats.hits += 1
            self._update_hit_rate()
            self._stats.avg_get_time_ms = self._update_avg_time(
                self._stats.avg_get_time_ms, time.time() - start_time
            )
            
            return entry if isinstance(entry, CacheEntry) else CacheEntry(
                value=entry,
                created_at=time.time(),
                ttl=self.default_ttl
            )
        
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._stats.misses += 1
            return None
    
    async def set(
        self,
        key: str,
        value: T,
        ttl: int = None,
        tags: Set[str] = None
    ) -> bool:
        start_time = time.time()
        self._stats.total_sets += 1
        
        try:
            entry = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl or self.default_ttl,
                tags=tags or set()
            )
            
            serialized = self._serialize(entry)
            
            await self.redis.setex(
                self._make_key(key),
                entry.ttl,
                serialized
            )
            
            # Store tag index
            if tags:
                for tag in tags:
                    tag_key = f"{self.key_prefix}tag:{tag}"
                    await self.redis.sadd(tag_key, key)
                    await self.redis.expire(tag_key, entry.ttl)
            
            self._stats.avg_set_time_ms = self._update_avg_time(
                self._stats.avg_set_time_ms, time.time() - start_time
            )
            
            return True
        
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        try:
            result = await self.redis.delete(self._make_key(key))
            self._stats.total_deletes += 1
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        try:
            return await self.redis.exists(self._make_key(key)) > 0
        except Exception as e:
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def clear(self) -> bool:
        try:
            # Use SCAN to find and delete all cache keys
            pattern = f"{self.key_prefix}*"
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break
            return True
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return False
    
    async def get_stats(self) -> CacheStats:
        try:
            info = await self.redis.info("stats")
            keyspace = await self.redis.info("keyspace")
            
            # Estimate size from keyspace
            db_info = keyspace.get("db0", {})
            keys = int(db_info.get("keys", 0)) if isinstance(db_info, dict) else 0
            
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                total_gets=self._stats.total_gets,
                total_sets=self._stats.total_sets,
                total_deletes=self._stats.total_deletes,
                hit_rate=self._stats.hit_rate,
                avg_get_time_ms=self._stats.avg_get_time_ms,
                avg_set_time_ms=self._stats.avg_set_time_ms,
                size=keys
            )
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return self._stats
    
    async def invalidate_by_tag(self, tag: str) -> int:
        try:
            tag_key = f"{self.key_prefix}tag:{tag}"
            keys = await self.redis.smembers(tag_key)
            
            if keys:
                # Delete all tagged keys
                pipe = self.redis.pipeline()
                for key in keys:
                    pipe.delete(self._make_key(key.decode()))
                await pipe.execute()
                
                # Clean up tag set
                await self.redis.delete(tag_key)
            
            return len(keys)
        except Exception as e:
            logger.error(f"Redis invalidate by tag error: {e}")
            return 0
    
    async def publish_invalidation(self, key: str):
        """Publish invalidation event to other nodes."""
        await self.redis.publish(self._pubsub_channel, json.dumps({"key": key}))
    
    def _update_hit_rate(self):
        total = self._stats.hits + self._stats.misses
        if total > 0:
            self._stats.hit_rate = self._stats.hits / total
    
    def _update_avg_time(self, current_avg: float, new_time: float) -> float:
        count = self._stats.total_gets + self._stats.total_sets
        if count > 1:
            return (current_avg * (count - 1) + new_time * 1000) / count
        return new_time * 1000


class CDNCache:
    """
    L3 Cache: CDN edge cache (CloudFront, Cloudflare, etc.)
    Manages cache control headers and invalidation.
    """
    
    def __init__(
        self,
        provider: str = "cloudfront",
        distribution_id: str = None,
        aws_region: str = "us-east-1"
    ):
        self.provider = provider
        self.distribution_id = distribution_id
        self.aws_region = aws_region
        self._session = aioboto3.Session()
    
    def get_cache_headers(
        self,
        ttl: int = 3600,
        stale_while_revalidate: int = None,
        vary: List[str] = None
    ) -> Dict[str, str]:
        """Generate cache control headers for CDN."""
        headers = {
            "Cache-Control": f"public, max-age={ttl}",
        }
        
        if stale_while_revalidate:
            headers["Cache-Control"] += f", stale-while-revalidate={stale_while_revalidate}"
        
        if vary:
            headers["Vary"] = ", ".join(vary)
        
        return headers
    
    async def invalidate(self, paths: List[str]) -> bool:
        """Invalidate CDN cache paths."""
        if self.provider == "cloudfront" and self.distribution_id:
            return await self._invalidate_cloudfront(paths)
        return False
    
    async def _invalidate_cloudfront(self, paths: List[str]) -> bool:
        """Invalidate CloudFront cache."""
        try:
            async with self._session.client(
                "cloudfront",
                region_name=self.aws_region
            ) as client:
                await client.create_invalidation(
                    DistributionId=self.distribution_id,
                    InvalidationBatch={
                        "Paths": {
                            "Quantity": len(paths),
                            "Items": paths
                        },
                        "CallerReference": str(time.time())
                    }
                )
            return True
        except Exception as e:
            logger.error(f"CloudFront invalidation error: {e}")
            return False
    
    async def invalidate_all(self) -> bool:
        """Invalidate all CDN cache."""
        return await self.invalidate(["/*"])


# =============================================================================
# Multi-Tier Cache
# =============================================================================

class MultiTierCache(CacheBackend[T]):
    """
    Multi-tier cache implementation.
    
    Hierarchy:
    L1: In-memory (fastest, smallest, local)
    L2: Redis (distributed, shared)
    L3: CDN (edge, static content)
    
    Read path: L1 -> L2 -> L3 -> Source
    Write path: Depends on strategy
    """
    
    def __init__(
        self,
        memory_cache: InMemoryCache = None,
        redis_cache: RedisCache = None,
        cdn_cache: CDNCache = None,
        config: CacheConfig = None
    ):
        self.l1 = memory_cache or InMemoryCache()
        self.l2 = redis_cache or RedisCache()
        self.l3 = cdn_cache
        self.config = config or CacheConfig()
        self._write_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[CacheEntry[T]]:
        """Get from cache with tiered lookup."""
        # L1: Memory
        entry = await self.l1.get(key)
        if entry:
            logger.debug(f"L1 cache hit: {key}")
            return entry
        
        # L2: Redis
        entry = await self.l2.get(key)
        if entry:
            logger.debug(f"L2 cache hit: {key}")
            # Promote to L1
            await self.l1.set(key, entry.value, self.config.memory_ttl, entry.tags)
            return entry
        
        logger.debug(f"Cache miss: {key}")
        return None
    
    async def set(
        self,
        key: str,
        value: T,
        ttl: int = None,
        tags: Set[str] = None
    ) -> bool:
        """Set cache value based on strategy."""
        ttl = ttl or self.config.default_ttl
        tags = tags or set()
        
        if self.config.strategy == CacheStrategy.CACHE_ASIDE:
            return await self._set_cache_aside(key, value, ttl, tags)
        elif self.config.strategy == CacheStrategy.WRITE_THROUGH:
            return await self._set_write_through(key, value, ttl, tags)
        elif self.config.strategy == CacheStrategy.WRITE_BEHIND:
            return await self._set_write_behind(key, value, ttl, tags)
        
        return False
    
    async def _set_cache_aside(
        self,
        key: str,
        value: T,
        ttl: int,
        tags: Set[str]
    ) -> bool:
        """Cache-aside: Write to all tiers."""
        results = []
        
        # Always write to L2 (source of truth)
        results.append(await self.l2.set(key, value, ttl, tags))
        
        # Write to L1
        results.append(await self.l1.set(key, value, min(ttl, self.config.memory_ttl), tags))
        
        return all(results)
    
    async def _set_write_through(
        self,
        key: str,
        value: T,
        ttl: int,
        tags: Set[str]
    ) -> bool:
        """Write-through: Write to DB and cache together."""
        # Same as cache-aside for this implementation
        return await self._set_cache_aside(key, value, ttl, tags)
    
    async def _set_write_behind(
        self,
        key: str,
        value: T,
        ttl: int,
        tags: Set[str]
    ) -> bool:
        """Write-behind: Write to cache, queue for DB."""
        # Write to L1 immediately
        await self.l1.set(key, value, ttl, tags)
        
        # Queue for async write to L2
        await self._write_queue.put(("set", key, value, ttl, tags))
        
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete from all tiers."""
        results = [
            await self.l1.delete(key),
            await self.l2.delete(key)
        ]
        return any(results)
    
    async def exists(self, key: str) -> bool:
        """Check existence in any tier."""
        return await self.l1.exists(key) or await self.l2.exists(key)
    
    async def clear(self) -> bool:
        """Clear all tiers."""
        results = [
            await self.l1.clear(),
            await self.l2.clear()
        ]
        return all(results)
    
    async def get_stats(self) -> Dict[str, CacheStats]:
        """Get stats from all tiers."""
        return {
            "l1_memory": await self.l1.get_stats(),
            "l2_redis": await self.l2.get_stats(),
        }
    
    async def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate by tag across all tiers."""
        l1_count = await self.l1.invalidate_by_tag(tag)
        l2_count = await self.l2.invalidate_by_tag(tag)
        return l1_count + l2_count
    
    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl: int = None,
        tags: Set[str] = None
    ) -> T:
        """Get from cache or compute and store."""
        # Try cache first
        entry = await self.get(key)
        if entry:
            return entry.value
        
        # Compute value
        value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
        
        # Store in cache
        await self.set(key, value, ttl, tags)
        
        return value
    
    async def refresh(self, key: str, factory: Callable[[], T], ttl: int = None) -> bool:
        """Refresh cache value proactively."""
        try:
            value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
            await self.set(key, value, ttl)
            return True
        except Exception as e:
            logger.error(f"Cache refresh error for {key}: {e}")
            return False
    
    async def start_write_behind_worker(self):
        """Start background worker for write-behind."""
        self._running = True
        while self._running:
            try:
                operation = await asyncio.wait_for(
                    self._write_queue.get(),
                    timeout=1.0
                )
                
                if operation[0] == "set":
                    _, key, value, ttl, tags = operation
                    await self.l2.set(key, value, ttl, tags)
                
                self._write_queue.task_done()
            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Write-behind worker error: {e}")
    
    async def stop_write_behind_worker(self):
        """Stop write-behind worker."""
        self._running = False


# =============================================================================
# Cache Warming
# =============================================================================

class CacheWarmer:
    """Proactive cache warming for predicted hot data."""
    
    def __init__(self, cache: MultiTierCache):
        self.cache = cache
        self._warming_tasks: Set[asyncio.Task] = set()
    
    async def warm_keys(self, keys_with_factories: Dict[str, Callable], ttl: int = None):
        """Warm cache with multiple keys."""
        tasks = []
        for key, factory in keys_with_factories.items():
            task = asyncio.create_task(self._warm_key(key, factory, ttl))
            tasks.append(task)
            self._warming_tasks.add(task)
            task.add_done_callback(self._warming_tasks.discard)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _warm_key(self, key: str, factory: Callable, ttl: int = None):
        """Warm single cache key."""
        try:
            if not await self.cache.exists(key):
                value = await factory() if asyncio.iscoroutinefunction(factory) else factory()
                await self.cache.set(key, value, ttl)
                logger.info(f"Warmed cache key: {key}")
        except Exception as e:
            logger.error(f"Cache warming error for {key}: {e}")
    
    async def warm_from_query(
        self,
        query_func: Callable,
        key_pattern: str,
        ttl: int = None
    ):
        """Warm cache from database query results."""
        try:
            results = await query_func() if asyncio.iscoroutinefunction(query_func) else query_func()
            
            keys_with_factories = {}
            for item in results:
                key = key_pattern.format(**item) if isinstance(item, dict) else key_pattern.format(item)
                keys_with_factories[key] = lambda i=item: i
            
            await self.warm_keys(keys_with_factories, ttl)
        
        except Exception as e:
            logger.error(f"Cache warming from query error: {e}")


# =============================================================================
# Cache Decorator
# =============================================================================

def cached(
    cache: MultiTierCache,
    key_pattern: str = None,
    ttl: int = None,
    tags: List[str] = None,
    unless: Callable = None
):
    """Decorator to cache function results."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Skip caching if unless condition met
            if unless and unless(*args, **kwargs):
                return await func(*args, **kwargs)
            
            # Generate cache key
            if key_pattern:
                key = key_pattern.format(*args, **kwargs)
            else:
                # Hash function call
                key_data = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
                key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try cache
            entry = await cache.get(key)
            if entry:
                return entry.value
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache.set(key, result, ttl, set(tags) if tags else None)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def cache_evict(cache: MultiTierCache, key_pattern: str = None):
    """Decorator to evict cache entries after function execution."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Generate key and evict
            if key_pattern:
                key = key_pattern.format(*args, **kwargs)
                await cache.delete(key)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# =============================================================================
# Factory Functions
# =============================================================================

def create_cache(
    redis_url: str = "redis://localhost:6379",
    memory_size: int = 10000,
    strategy: CacheStrategy = CacheStrategy.CACHE_ASIDE
) -> MultiTierCache:
    """Create configured multi-tier cache."""
    config = CacheConfig(strategy=strategy)
    
    l1 = InMemoryCache(max_size=memory_size, default_ttl=config.memory_ttl)
    l2 = RedisCache(redis_url=redis_url, default_ttl=config.redis_ttl)
    
    return MultiTierCache(l1, l2, config=config)


def create_enterprise_cache(redis_url: str = None) -> MultiTierCache:
    """Create enterprise-grade cache with optimized settings."""
    config = CacheConfig(
        strategy=CacheStrategy.WRITE_THROUGH,
        default_ttl=300,
        memory_max_size=50000,
        memory_ttl=120,
        redis_ttl=600,
        ttl_variation=0.15  # 15% variation to prevent thundering herd
    )
    
    l1 = InMemoryCache(max_size=config.memory_max_size, default_ttl=config.memory_ttl)
    l2 = RedisCache(
        redis_url=redis_url or "redis://localhost:6379",
        default_ttl=config.redis_ttl,
        serializer="pickle"
    )
    
    return MultiTierCache(l1, l2, config=config)


# =============================================================================
# Usage Examples
# =============================================================================

"""
# Basic usage
from cache import create_cache, cached, cache_evict

cache = create_cache()

# Cached function
@cached(cache, key_pattern="user:{user_id}", ttl=300, tags=["users"])
async def get_user(user_id: str):
    return await db.users.find_one({"_id": user_id})

# Cache eviction on write
@cache_evict(cache, key_pattern="user:{user_id}")
async def update_user(user_id: str, data: dict):
    return await db.users.update_one({"_id": user_id}, data)

# Manual cache operations
user = await cache.get_or_set(
    f"user:{user_id}",
    lambda: db.users.find_one({"_id": user_id}),
    ttl=300,
    tags={"users", f"tenant:{tenant_id}"}
)

# Invalidate by tag
await cache.invalidate_by_tag("users")

# Cache warming
warmer = CacheWarmer(cache)
await warmer.warm_keys({
    "config:app": load_app_config,
    "config:features": load_feature_flags,
})
"""


if __name__ == "__main__":
    # Test the cache
    async def test():
        cache = create_cache()
        
        # Test set/get
        await cache.set("test:key", {"data": "value"}, ttl=60)
        entry = await cache.get("test:key")
        print(f"Got: {entry.value if entry else None}")
        
        # Test stats
        stats = await cache.get_stats()
        for tier, stat in stats.items():
            print(f"{tier}: hits={stat.hits}, misses={stat.misses}, hit_rate={stat.hit_rate:.2%}")
    
    asyncio.run(test())
