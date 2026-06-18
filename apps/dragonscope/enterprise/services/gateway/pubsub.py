"""
DragonScope Enterprise - Redis Pub/Sub Integration
==================================================
High-performance pub/sub system with channel mapping, fan-out,
and backpressure handling.

Features:
- Redis Pub/Sub for message distribution
- Channel-to-subscribers mapping
- Fan-out to WebSocket connections
- Backpressure handling with circuit breaker
- Message buffering and batching
"""

import asyncio
import logging
import time
from typing import Callable, Optional, Set, Dict, List, Any
from dataclasses import dataclass, field
from collections import defaultdict
from contextlib import asynccontextmanager
from enum import Enum

import aioredis
from aioredis.client import PubSub


logger = logging.getLogger(__name__)


class BackpressureStrategy(Enum):
    """Backpressure handling strategies."""
    DROP_NEW = "drop_new"          # Drop new messages when buffer full
    DROP_OLD = "drop_old"          # Drop oldest messages when buffer full
    BLOCK = "block"                # Block producer until space available
    THROTTLE = "throttle"          # Reduce message rate


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"              # Normal operation
    OPEN = "open"                  # Failure threshold reached, rejecting requests
    HALF_OPEN = "half_open"        # Testing if service recovered


@dataclass
class ChannelStats:
    """Statistics for a channel."""
    channel: str
    messages_published: int = 0
    messages_dropped: int = 0
    subscribers_peak: int = 0
    last_message_at: Optional[float] = None
    bytes_transferred: int = 0
    
    def record_message(self, size_bytes: int):
        """Record a published message."""
        self.messages_published += 1
        self.bytes_transferred += size_bytes
        self.last_message_at = time.time()
    
    def record_drop(self):
        """Record a dropped message."""
        self.messages_dropped += 1
    
    def update_subscriber_count(self, count: int):
        """Update peak subscriber count."""
        self.subscribers_peak = max(self.subscribers_peak, count)


@dataclass
class PubSubMetrics:
    """Global pub/sub metrics."""
    total_channels: int = 0
    total_subscribers: int = 0
    messages_published: int = 0
    messages_delivered: int = 0
    messages_dropped: int = 0
    redis_reconnections: int = 0
    circuit_breaker_trips: int = 0
    avg_fanout_time_ms: float = 0.0


class CircuitBreaker:
    """Circuit breaker for handling Redis failures."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker entering HALF_OPEN state")
                else:
                    raise Exception("Circuit breaker is OPEN")
            
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise Exception("Circuit breaker HALF_OPEN limit reached")
                self._half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise e
    
    async def _on_success(self):
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info("Circuit breaker CLOSED - service recovered")
            else:
                self._failure_count = 0
    
    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker OPEN - failure in HALF_OPEN")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit breaker OPEN after {self._failure_count} failures")


class MessageBuffer:
    """Buffered message queue with backpressure handling."""
    
    def __init__(
        self,
        max_size: int = 10000,
        strategy: BackpressureStrategy = BackpressureStrategy.DROP_OLD,
        batch_size: int = 100,
        flush_interval_ms: float = 10.0
    ):
        self.max_size = max_size
        self.strategy = strategy
        self.batch_size = batch_size
        self.flush_interval = flush_interval_ms / 1000.0
        
        self._buffer: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self._dropped_count = 0
        self._total_enqueued = 0
        self._lock = asyncio.Lock()
    
    async def put(self, message: Any) -> bool:
        """
        Add a message to the buffer.
        
        Returns True if message was added, False if dropped.
        """
        try:
            self._buffer.put_nowait(message)
            self._total_enqueued += 1
            return True
        except asyncio.QueueFull:
            if self.strategy == BackpressureStrategy.DROP_NEW:
                self._dropped_count += 1
                return False
            elif self.strategy == BackpressureStrategy.DROP_OLD:
                # Remove oldest and add new
                try:
                    self._buffer.get_nowait()
                    self._dropped_count += 1
                    self._buffer.put_nowait(message)
                    return True
                except asyncio.QueueEmpty:
                    self._buffer.put_nowait(message)
                    return True
            elif self.strategy == BackpressureStrategy.BLOCK:
                await self._buffer.put(message)
                self._total_enqueued += 1
                return True
            else:  # THROTTLE
                await asyncio.sleep(0.001)
                return await self.put(message)
    
    async def get_batch(self, timeout: Optional[float] = None) -> List[Any]:
        """Get a batch of messages from the buffer."""
        batch = []
        
        try:
            # Wait for first message
            msg = await asyncio.wait_for(
                self._buffer.get(),
                timeout=timeout or self.flush_interval
            )
            batch.append(msg)
            
            # Get more messages up to batch_size
            while len(batch) < self.batch_size:
                try:
                    msg = self._buffer.get_nowait()
                    batch.append(msg)
                except asyncio.QueueEmpty:
                    break
        except asyncio.TimeoutError:
            pass
        
        return batch
    
    @property
    def size(self) -> int:
        return self._buffer.qsize()
    
    @property
    def stats(self) -> dict:
        return {
            'size': self.size,
            'max_size': self.max_size,
            'dropped': self._dropped_count,
            'enqueued': self._total_enqueued
        }


class ChannelManager:
    """Manages channel-to-subscribers mapping."""
    
    def __init__(self):
        # channel -> set of subscriber IDs
        self._channels: Dict[str, Set[str]] = defaultdict(set)
        # subscriber ID -> set of channels
        self._subscriber_channels: Dict[str, Set[str]] = defaultdict(set)
        # channel -> ChannelStats
        self._channel_stats: Dict[str, ChannelStats] = {}
        self._lock = asyncio.RLock()
    
    async def subscribe(self, subscriber_id: str, channel: str) -> bool:
        """Subscribe a subscriber to a channel."""
        async with self._lock:
            if subscriber_id not in self._channels[channel]:
                self._channels[channel].add(subscriber_id)
                self._subscriber_channels[subscriber_id].add(channel)
                
                if channel not in self._channel_stats:
                    self._channel_stats[channel] = ChannelStats(channel)
                
                self._channel_stats[channel].update_subscriber_count(
                    len(self._channels[channel])
                )
                return True
            return False
    
    async def unsubscribe(self, subscriber_id: str, channel: str) -> bool:
        """Unsubscribe a subscriber from a channel."""
        async with self._lock:
            if subscriber_id in self._channels[channel]:
                self._channels[channel].discard(subscriber_id)
                self._subscriber_channels[subscriber_id].discard(channel)
                
                # Clean up empty channels
                if not self._channels[channel]:
                    del self._channels[channel]
                
                return True
            return False
    
    async def unsubscribe_all(self, subscriber_id: str) -> List[str]:
        """Unsubscribe a subscriber from all channels."""
        async with self._lock:
            channels = list(self._subscriber_channels.get(subscriber_id, []))
            for channel in channels:
                self._channels[channel].discard(subscriber_id)
                if not self._channels[channel]:
                    del self._channels[channel]
            
            if subscriber_id in self._subscriber_channels:
                del self._subscriber_channels[subscriber_id]
            
            return channels
    
    def get_subscribers(self, channel: str) -> Set[str]:
        """Get all subscribers for a channel."""
        return self._channels.get(channel, set()).copy()
    
    def get_channels(self, subscriber_id: str) -> Set[str]:
        """Get all channels a subscriber is subscribed to."""
        return self._subscriber_channels.get(subscriber_id, set()).copy()
    
    def get_channel_stats(self, channel: str) -> Optional[ChannelStats]:
        """Get statistics for a channel."""
        return self._channel_stats.get(channel)
    
    def get_all_stats(self) -> Dict[str, ChannelStats]:
        """Get statistics for all channels."""
        return self._channel_stats.copy()
    
    @property
    def channel_count(self) -> int:
        return len(self._channels)
    
    @property
    def subscriber_count(self) -> int:
        return len(self._subscriber_channels)


class RedisPubSub:
    """Redis Pub/Sub integration with fan-out and backpressure handling."""
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_connections: int = 100,
        buffer_size: int = 10000,
        batch_size: int = 100,
        flush_interval_ms: float = 10.0,
        enable_circuit_breaker: bool = True
    ):
        self.redis_url = redis_url
        self.max_connections = max_connections
        
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[PubSub] = None
        self._channel_manager = ChannelManager()
        self._message_buffer = MessageBuffer(
            max_size=buffer_size,
            batch_size=batch_size,
            flush_interval_ms=flush_interval_ms
        )
        
        self._circuit_breaker = CircuitBreaker() if enable_circuit_breaker else None
        self._metrics = PubSubMetrics()
        
        # Subscriber ID -> callback function
        self._callbacks: Dict[str, Callable] = {}
        
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
    
    async def start(self):
        """Start the Redis Pub/Sub system."""
        if self._running:
            return
        
        self._running = True
        
        # Connect to Redis
        await self._connect()
        
        # Start background tasks
        self._tasks.append(
            asyncio.create_task(self._process_messages())
        )
        self._tasks.append(
            asyncio.create_task(self._monitor_connection())
        )
        
        logger.info("Redis Pub/Sub started")
    
    async def stop(self):
        """Stop the Redis Pub/Sub system."""
        self._running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Close Redis connection
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        
        logger.info("Redis Pub/Sub stopped")
    
    async def _connect(self):
        """Establish Redis connection."""
        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                decode_responses=False
            )
            self._pubsub = self._redis.pubsub()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def _reconnect(self):
        """Reconnect to Redis after failure."""
        logger.warning("Attempting to reconnect to Redis...")
        self._metrics.redis_reconnections += 1
        
        try:
            if self._pubsub:
                await self._pubsub.close()
            if self._redis:
                await self._redis.close()
            
            await self._connect()
            
            # Resubscribe to all channels
            channels = list(self._channel_manager._channels.keys())
            if channels:
                await self._pubsub.subscribe(*channels)
                logger.info(f"Resubscribed to {len(channels)} channels")
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            raise
    
    async def _monitor_connection(self):
        """Monitor Redis connection health."""
        while self._running:
            try:
                if self._redis:
                    await self._redis.ping()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Redis connection lost: {e}")
                try:
                    await self._reconnect()
                except Exception:
                    await asyncio.sleep(5)
    
    async def _process_messages(self):
        """Process messages from the buffer."""
        while self._running:
            try:
                batch = await self._message_buffer.get_batch()
                if batch:
                    await self._fanout_batch(batch)
            except Exception as e:
                logger.error(f"Error processing message batch: {e}")
                await asyncio.sleep(0.1)
    
    async def _fanout_batch(self, messages: List[dict]):
        """Fan out a batch of messages to subscribers."""
        start_time = time.time()
        
        # Group messages by subscriber for efficient delivery
        subscriber_messages: Dict[str, List[bytes]] = defaultdict(list)
        
        for msg in messages:
            channel = msg.get('channel')
            data = msg.get('data')
            
            if not channel or not data:
                continue
            
            subscribers = self._channel_manager.get_subscribers(channel)
            
            # Update channel stats
            stats = self._channel_manager.get_channel_stats(channel)
            if stats:
                stats.record_message(len(data) if isinstance(data, bytes) else len(str(data)))
            
            for subscriber_id in subscribers:
                subscriber_messages[subscriber_id].append(data)
        
        # Deliver to subscribers
        delivery_tasks = []
        for subscriber_id, msgs in subscriber_messages.items():
            callback = self._callbacks.get(subscriber_id)
            if callback:
                delivery_tasks.append(
                    self._deliver_to_subscriber(subscriber_id, msgs, callback)
                )
        
        if delivery_tasks:
            results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
            
            # Update metrics
            for result in results:
                if isinstance(result, Exception):
                    self._metrics.messages_dropped += 1
                else:
                    self._metrics.messages_delivered += result
        
        # Update fanout time metric
        fanout_time = (time.time() - start_time) * 1000
        self._metrics.avg_fanout_time_ms = (
            self._metrics.avg_fanout_time_ms * 0.9 + fanout_time * 0.1
        )
    
    async def _deliver_to_subscriber(
        self,
        subscriber_id: str,
        messages: List[bytes],
        callback: Callable
    ) -> int:
        """Deliver messages to a single subscriber."""
        try:
            await callback(subscriber_id, messages)
            return len(messages)
        except Exception as e:
            logger.warning(f"Failed to deliver to {subscriber_id}: {e}")
            raise
    
    async def register_subscriber(
        self,
        subscriber_id: str,
        callback: Callable[[str, List[bytes]], None]
    ):
        """Register a subscriber with a callback function."""
        async with self._lock:
            self._callbacks[subscriber_id] = callback
            self._metrics.total_subscribers += 1
    
    async def unregister_subscriber(self, subscriber_id: str):
        """Unregister a subscriber."""
        async with self._lock:
            # Unsubscribe from all channels
            channels = await self._channel_manager.unsubscribe_all(subscriber_id)
            
            # Unsubscribe from Redis channels if no subscribers left
            for channel in channels:
                if not self._channel_manager.get_subscribers(channel):
                    try:
                        if self._circuit_breaker:
                            await self._circuit_breaker.call(
                                self._pubsub.unsubscribe, channel
                            )
                        else:
                            await self._pubsub.unsubscribe(channel)
                    except Exception as e:
                        logger.error(f"Failed to unsubscribe from {channel}: {e}")
            
            # Remove callback
            if subscriber_id in self._callbacks:
                del self._callbacks[subscriber_id]
                self._metrics.total_subscribers -= 1
    
    async def subscribe(self, subscriber_id: str, channel: str) -> bool:
        """Subscribe a subscriber to a channel."""
        is_new = await self._channel_manager.subscribe(subscriber_id, channel)
        
        if is_new:
            # Subscribe to Redis channel if first subscriber
            if len(self._channel_manager.get_subscribers(channel)) == 1:
                try:
                    if self._circuit_breaker:
                        await self._circuit_breaker.call(
                            self._pubsub.subscribe, channel
                        )
                    else:
                        await self._pubsub.subscribe(channel)
                    
                    self._metrics.total_channels = self._channel_manager.channel_count
                    logger.debug(f"Subscribed to Redis channel: {channel}")
                except Exception as e:
                    logger.error(f"Failed to subscribe to {channel}: {e}")
                    await self._channel_manager.unsubscribe(subscriber_id, channel)
                    return False
        
        return True
    
    async def unsubscribe(self, subscriber_id: str, channel: str) -> bool:
        """Unsubscribe a subscriber from a channel."""
        was_removed = await self._channel_manager.unsubscribe(subscriber_id, channel)
        
        if was_removed:
            # Unsubscribe from Redis if no subscribers left
            if not self._channel_manager.get_subscribers(channel):
                try:
                    if self._circuit_breaker:
                        await self._circuit_breaker.call(
                            self._pubsub.unsubscribe, channel
                        )
                    else:
                        await self._pubsub.unsubscribe(channel)
                    
                    self._metrics.total_channels = self._channel_manager.channel_count
                    logger.debug(f"Unsubscribed from Redis channel: {channel}")
                except Exception as e:
                    logger.error(f"Failed to unsubscribe from {channel}: {e}")
        
        return was_removed
    
    async def publish(self, channel: str, message: bytes) -> bool:
        """
        Publish a message to a channel.
        
        This adds the message to the buffer for fan-out.
        """
        self._metrics.messages_published += 1
        
        return await self._message_buffer.put({
            'channel': channel,
            'data': message
        })
    
    async def publish_to_redis(self, channel: str, message: bytes) -> int:
        """
        Publish a message directly to Redis.
        
        Use this for cross-instance message distribution.
        """
        try:
            if self._circuit_breaker:
                return await self._circuit_breaker.call(
                    self._redis.publish, channel, message
                )
            else:
                return await self._redis.publish(channel, message)
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}")
            return 0
    
    def get_metrics(self) -> dict:
        """Get current metrics."""
        return {
            'pubsub': {
                'total_channels': self._metrics.total_channels,
                'total_subscribers': self._metrics.total_subscribers,
                'messages_published': self._metrics.messages_published,
                'messages_delivered': self._metrics.messages_delivered,
                'messages_dropped': self._metrics.messages_dropped,
                'redis_reconnections': self._metrics.redis_reconnections,
                'circuit_breaker_trips': self._metrics.circuit_breaker_trips,
                'avg_fanout_time_ms': round(self._metrics.avg_fanout_time_ms, 3),
            },
            'buffer': self._message_buffer.stats,
            'channels': {
                name: {
                    'subscribers': len(self._channel_manager.get_subscribers(name)),
                    'messages_published': stats.messages_published,
                    'messages_dropped': stats.messages_dropped,
                    'subscribers_peak': stats.subscribers_peak
                }
                for name, stats in self._channel_manager.get_all_stats().items()
            }
        }


class LocalPubSub:
    """In-memory Pub/Sub for single-instance deployments (no Redis)."""
    
    def __init__(
        self,
        buffer_size: int = 10000,
        batch_size: int = 100,
        flush_interval_ms: float = 10.0
    ):
        self._channel_manager = ChannelManager()
        self._message_buffer = MessageBuffer(
            max_size=buffer_size,
            batch_size=batch_size,
            flush_interval_ms=flush_interval_ms
        )
        self._callbacks: Dict[str, Callable] = {}
        self._metrics = PubSubMetrics()
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the local pub/sub system."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._process_messages())
        logger.info("Local Pub/Sub started")
    
    async def stop(self):
        """Stop the local pub/sub system."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Local Pub/Sub stopped")
    
    async def _process_messages(self):
        """Process messages from the buffer."""
        while self._running:
            try:
                batch = await self._message_buffer.get_batch()
                if batch:
                    await self._fanout_batch(batch)
            except Exception as e:
                logger.error(f"Error processing messages: {e}")
                await asyncio.sleep(0.1)
    
    async def _fanout_batch(self, messages: List[dict]):
        """Fan out messages to subscribers."""
        for msg in messages:
            channel = msg.get('channel')
            data = msg.get('data')
            
            if not channel or not data:
                continue
            
            subscribers = self._channel_manager.get_subscribers(channel)
            
            for subscriber_id in subscribers:
                callback = self._callbacks.get(subscriber_id)
                if callback:
                    try:
                        await callback(subscriber_id, [data])
                        self._metrics.messages_delivered += 1
                    except Exception as e:
                        logger.warning(f"Failed to deliver to {subscriber_id}: {e}")
                        self._metrics.messages_dropped += 1
    
    async def register_subscriber(
        self,
        subscriber_id: str,
        callback: Callable[[str, List[bytes]], None]
    ):
        """Register a subscriber."""
        self._callbacks[subscriber_id] = callback
        self._metrics.total_subscribers += 1
    
    async def unregister_subscriber(self, subscriber_id: str):
        """Unregister a subscriber."""
        await self._channel_manager.unsubscribe_all(subscriber_id)
        if subscriber_id in self._callbacks:
            del self._callbacks[subscriber_id]
            self._metrics.total_subscribers -= 1
    
    async def subscribe(self, subscriber_id: str, channel: str) -> bool:
        """Subscribe to a channel."""
        result = await self._channel_manager.subscribe(subscriber_id, channel)
        if result:
            self._metrics.total_channels = self._channel_manager.channel_count
        return result
    
    async def unsubscribe(self, subscriber_id: str, channel: str) -> bool:
        """Unsubscribe from a channel."""
        result = await self._channel_manager.unsubscribe(subscriber_id, channel)
        if result:
            self._metrics.total_channels = self._channel_manager.channel_count
        return result
    
    async def publish(self, channel: str, message: bytes) -> bool:
        """Publish a message to a channel."""
        self._metrics.messages_published += 1
        return await self._message_buffer.put({
            'channel': channel,
            'data': message
        })
    
    def get_metrics(self) -> dict:
        """Get current metrics."""
        return {
            'pubsub': {
                'total_channels': self._metrics.total_channels,
                'total_subscribers': self._metrics.total_subscribers,
                'messages_published': self._metrics.messages_published,
                'messages_delivered': self._metrics.messages_delivered,
                'messages_dropped': self._metrics.messages_dropped,
            },
            'buffer': self._message_buffer.stats,
            'channels': {
                name: len(self._channel_manager.get_subscribers(name))
                for name in self._channel_manager._channels.keys()
            }
        }
