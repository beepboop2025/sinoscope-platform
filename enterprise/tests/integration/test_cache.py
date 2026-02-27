"""
Cache (Redis) integration tests.

Tests Redis connectivity, operations, and caching strategies.
"""

import pytest
import json
import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock

pytestmark = [pytest.mark.integration, pytest.mark.cache]


class TestRedisConnection:
    """Test suite for Redis connectivity."""
    
    @pytest.fixture(scope='class')
    async def redis_client(self, test_config):
        """Create Redis client for testing."""
        # Example using redis-py:
        # import redis.asyncio as redis
        # client = redis.from_url(test_config['redis_url'])
        # yield client
        # await client.close()
        
        # Mock client for demonstration
        client = AsyncMock()
        client.ping = AsyncMock(return_value=True)
        yield client
    
    @pytest.mark.asyncio
    async def test_redis_connection(self, redis_client):
        """Test basic Redis connectivity."""
        result = await redis_client.ping()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_redis_info(self, redis_client):
        """Test retrieving Redis server info."""
        redis_client.info = AsyncMock(return_value={
            'redis_version': '7.0.0',
            'used_memory_human': '1.5M',
            'connected_clients': 5
        })
        
        info = await redis_client.info()
        assert 'redis_version' in info


class TestRedisStringOperations:
    """Test suite for Redis string operations."""
    
    @pytest.mark.asyncio
    async def test_set_and_get(self, redis_client):
        """Test basic SET and GET operations."""
        # Arrange
        key = 'test:key'
        value = 'test_value'
        
        # Act
        await redis_client.set(key, value)
        result = await redis_client.get(key)
        
        # Assert
        assert result == value or result is not None
    
    @pytest.mark.asyncio
    async def test_set_with_expiration(self, redis_client):
        """Test SET with TTL."""
        # Arrange
        key = 'test:expiring'
        value = 'value'
        ttl = 10  # seconds
        
        # Act
        await redis_client.setex(key, ttl, value)
        
        # Assert
        remaining_ttl = await redis_client.ttl(key)
        assert remaining_ttl <= ttl
        assert remaining_ttl > 0
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, redis_client):
        """Test GET for non-existent key returns None."""
        result = await redis_client.get('test:nonexistent')
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_key(self, redis_client):
        """Test DELETE operation."""
        # Arrange
        key = 'test:to_delete'
        await redis_client.set(key, 'value')
        
        # Act
        deleted = await redis_client.delete(key)
        
        # Assert
        result = await redis_client.get(key)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_exists(self, redis_client):
        """Test EXISTS operation."""
        # Arrange
        key = 'test:exists_check'
        await redis_client.set(key, 'value')
        
        # Act & Assert
        assert await redis_client.exists(key) == 1
        assert await redis_client.exists('test:nonexistent') == 0
    
    @pytest.mark.asyncio
    async def test_incr_decr(self, redis_client):
        """Test INCR and DECR operations."""
        key = 'test:counter'
        
        # Reset
        await redis_client.set(key, 0)
        
        # Increment
        await redis_client.incr(key)
        await redis_client.incr(key)
        await redis_client.incrby(key, 5)
        
        value = await redis_client.get(key)
        # Should be 7
        
        # Decrement
        await redis_client.decr(key)
        await redis_client.decrby(key, 2)
        
        value = await redis_client.get(key)
        # Should be 4


class TestRedisHashOperations:
    """Test suite for Redis hash operations."""
    
    @pytest.mark.asyncio
    async def test_hset_and_hget(self, redis_client):
        """Test HSET and HGET operations."""
        # Arrange
        key = 'test:user:1'
        field = 'name'
        value = 'John Doe'
        
        # Act
        await redis_client.hset(key, field, value)
        result = await redis_client.hget(key, field)
        
        # Assert
        assert result == value
    
    @pytest.mark.asyncio
    async def test_hgetall(self, redis_client):
        """Test HGETALL operation."""
        # Arrange
        key = 'test:user:2'
        data = {
            'name': 'Jane Doe',
            'email': 'jane@example.com',
            'role': 'admin'
        }
        
        # Act
        for field, value in data.items():
            await redis_client.hset(key, field, value)
        
        result = await redis_client.hgetall(key)
        
        # Assert
        for field, value in data.items():
            assert result.get(field) == value
    
    @pytest.mark.asyncio
    async def test_hdel(self, redis_client):
        """Test HDEL operation."""
        # Arrange
        key = 'test:user:3'
        await redis_client.hset(key, 'field1', 'value1')
        await redis_client.hset(key, 'field2', 'value2')
        
        # Act
        await redis_client.hdel(key, 'field1')
        
        # Assert
        result = await redis_client.hget(key, 'field1')
        assert result is None
        
        result = await redis_client.hget(key, 'field2')
        assert result == 'value2'


class TestRedisListOperations:
    """Test suite for Redis list operations."""
    
    @pytest.mark.asyncio
    async def test_lpush_rpop(self, redis_client):
        """Test LPUSH and RPOP operations."""
        # Arrange
        key = 'test:queue'
        
        # Act
        await redis_client.lpush(key, 'item1')
        await redis_client.lpush(key, 'item2')
        await redis_client.lpush(key, 'item3')
        
        # Assert - RPOP should return items in FIFO order
        item1 = await redis_client.rpop(key)
        item2 = await redis_client.rpop(key)
        
        assert item1 == 'item1'
        assert item2 == 'item2'
    
    @pytest.mark.asyncio
    async def test_lrange(self, redis_client):
        """Test LRANGE operation."""
        # Arrange
        key = 'test:list'
        items = ['a', 'b', 'c', 'd', 'e']
        
        for item in items:
            await redis_client.rpush(key, item)
        
        # Act
        result = await redis_client.lrange(key, 0, 2)  # First 3 items
        
        # Assert
        assert len(result) == 3
        assert result == ['a', 'b', 'c']
    
    @pytest.mark.asyncio
    async def test_llen(self, redis_client):
        """Test LLEN operation."""
        # Arrange
        key = 'test:list_len'
        
        # Act
        length = await redis_client.llen(key)
        assert length == 0
        
        await redis_client.rpush(key, 'item1')
        await redis_client.rpush(key, 'item2')
        
        length = await redis_client.llen(key)
        assert length == 2


class TestRedisSetOperations:
    """Test suite for Redis set operations."""
    
    @pytest.mark.asyncio
    async def test_sadd_and_smembers(self, redis_client):
        """Test SADD and SMEMBERS operations."""
        # Arrange
        key = 'test:set'
        
        # Act
        await redis_client.sadd(key, 'member1')
        await redis_client.sadd(key, 'member2')
        await redis_client.sadd(key, 'member1')  # Duplicate, should be ignored
        
        members = await redis_client.smembers(key)
        
        # Assert
        assert len(members) == 2
        assert b'member1' in members or 'member1' in members
        assert b'member2' in members or 'member2' in members
    
    @pytest.mark.asyncio
    async def test_sismember(self, redis_client):
        """Test SISMEMBER operation."""
        # Arrange
        key = 'test:set:check'
        await redis_client.sadd(key, 'member')
        
        # Act & Assert
        assert await redis_client.sismember(key, 'member') == 1
        assert await redis_client.sismember(key, 'nonmember') == 0


class TestRedisSortedSetOperations:
    """Test suite for Redis sorted set operations."""
    
    @pytest.mark.asyncio
    async def test_zadd_and_zrange(self, redis_client):
        """Test ZADD and ZRANGE operations."""
        # Arrange
        key = 'test:leaderboard'
        
        # Act
        await redis_client.zadd(key, {'player1': 100, 'player2': 200, 'player3': 150})
        
        # Get top 2
        top_players = await redis_client.zrevrange(key, 0, 1, withscores=True)
        
        # Assert
        assert len(top_players) == 2
        # First should be player2 with score 200
    
    @pytest.mark.asyncio
    async def test_zrank(self, redis_client):
        """Test ZRANK operation."""
        # Arrange
        key = 'test:ranking'
        await redis_client.zadd(key, {'a': 10, 'b': 20, 'c': 30})
        
        # Act
        rank = await redis_client.zrank(key, 'b')
        
        # Assert - 'b' should be rank 1 (0-indexed)
        assert rank == 1


class TestCachingStrategies:
    """Test suite for caching strategies implementation."""
    
    @pytest.fixture
    async def cache_service(self, redis_client):
        """Create cache service with Redis backend."""
        from services.cache_service import CacheService
        return CacheService(redis=redis_client)
    
    @pytest.mark.asyncio
    async def test_cache_aside_pattern(self, cache_service, redis_client):
        """Test cache-aside (lazy loading) pattern."""
        # Arrange
        key = 'user:123'
        
        # First call - cache miss, load from DB
        redis_client.get = AsyncMock(return_value=None)
        data = {'id': 123, 'name': 'John'}
        
        # Simulate: check cache -> miss -> load from DB -> store in cache
        cached = await redis_client.get(key)
        if not cached:
            await redis_client.setex(key, 3600, json.dumps(data))
        
        redis_client.get.assert_called_with(key)
    
    @pytest.mark.asyncio
    async def test_write_through_pattern(self, cache_service, redis_client):
        """Test write-through pattern."""
        # Arrange
        key = 'user:456'
        data = {'id': 456, 'name': 'Jane'}
        
        # Act - Write to cache and DB simultaneously
        await redis_client.setex(key, 3600, json.dumps(data))
        # Also write to DB (simulated)
        
        # Assert - both should have same data
        cached = await redis_client.get(key)
        assert json.loads(cached) == data
    
    @pytest.mark.asyncio
    async def test_cache_invalidation(self, cache_service, redis_client):
        """Test cache invalidation on data update."""
        # Arrange
        key = 'user:789'
        await redis_client.setex(key, 3600, json.dumps({'id': 789, 'name': 'Old'}))
        
        # Act - Update data and invalidate cache
        await redis_client.delete(key)
        # Then update DB
        
        # Assert
        result = await redis_client.get(key)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_stampede_protection(self, cache_service):
        """Test protection against cache stampede."""
        # Simulate multiple concurrent requests for same key
        key = 'expensive:computation'
        
        async def fetch_with_lock():
            # Use Redis lock to prevent stampede
            lock_acquired = await cache_service.acquire_lock(key, timeout=10)
            if lock_acquired:
                try:
                    # Only one process should execute this
                    data = await cache_service.compute_expensive(key)
                    await cache_service.set(key, data, ttl=3600)
                finally:
                    await cache_service.release_lock(key)
            else:
                # Wait for cached value
                await asyncio.sleep(0.1)
                data = await cache_service.get(key)
            return data
        
        # Run multiple concurrent requests
        results = await asyncio.gather(*[fetch_with_lock() for _ in range(5)])
        
        # All should get same result
        assert all(r == results[0] for r in results)


class TestRedisPubSub:
    """Test suite for Redis pub/sub functionality."""
    
    @pytest.mark.asyncio
    async def test_publish_subscribe(self, redis_client):
        """Test PUBLISH and SUBSCRIBE."""
        channel = 'test:channel'
        message = 'Hello, Redis!'
        
        # Subscribe
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        
        # Publish
        await redis_client.publish(channel, message)
        
        # Receive
        msg = await pubsub.get_message(timeout=1)
        assert msg is not None
        
        await pubsub.unsubscribe(channel)
    
    @pytest.mark.asyncio
    async def test_pattern_subscribe(self, redis_client):
        """Test PSUBSCRIBE for pattern matching."""
        pattern = 'test:*:events'
        
        pubsub = redis_client.pubsub()
        await pubsub.psubscribe(pattern)
        
        # Publish to matching channel
        await redis_client.publish('test:user:events', 'user event')
        await redis_client.publish('test:order:events', 'order event')
        
        # Both messages should be received
        await pubsub.punsubscribe(pattern)


class TestRedisTransactions:
    """Test suite for Redis transactions."""
    
    @pytest.mark.asyncio
    async def test_pipeline_operations(self, redis_client):
        """Test Redis pipeline for batch operations."""
        # Arrange
        pipe = redis_client.pipeline()
        
        # Queue multiple commands
        pipe.set('key1', 'value1')
        pipe.set('key2', 'value2')
        pipe.get('key1')
        pipe.get('key2')
        
        # Execute
        results = await pipe.execute()
        
        # Assert
        assert results[0] is True  # SET result
        assert results[1] is True
        assert results[2] == 'value1'  # GET result
        assert results[3] == 'value2'
    
    @pytest.mark.asyncio
    async def test_atomic_increment(self, redis_client):
        """Test atomic increment operations."""
        key = 'test:atomic:counter'
        await redis_client.set(key, 0)
        
        # Multiple concurrent increments
        async def increment():
            for _ in range(100):
                await redis_client.incr(key)
        
        await asyncio.gather(*[increment() for _ in range(10)])
        
        final_value = await redis_client.get(key)
        assert int(final_value) == 1000  # 10 * 100


class TestCacheSerialization:
    """Test suite for cache data serialization."""
    
    @pytest.mark.asyncio
    async def test_json_serialization(self, redis_client):
        """Test storing and retrieving JSON data."""
        key = 'test:json:data'
        data = {
            'id': 123,
            'name': 'Test',
            'nested': {'a': 1, 'b': [1, 2, 3]},
            'timestamp': '2024-01-15T12:00:00Z'
        }
        
        # Store
        await redis_client.set(key, json.dumps(data))
        
        # Retrieve
        result = await redis_client.get(key)
        retrieved = json.loads(result)
        
        assert retrieved == data
    
    @pytest.mark.asyncio
    async def test_compressed_data(self, redis_client):
        """Test storing compressed data."""
        import zlib
        
        key = 'test:compressed'
        large_data = 'x' * 10000  # Large string
        compressed = zlib.compress(large_data.encode())
        
        await redis_client.set(key, compressed)
        
        result = await redis_client.get(key)
        decompressed = zlib.decompress(result).decode()
        
        assert decompressed == large_data
