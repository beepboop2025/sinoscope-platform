"""
DragonScope Enterprise - Market Data Service Architecture

High-performance tick-by-tick data processing components.
"""

from __future__ import annotations

import asyncio
import heapq
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, auto
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

import numpy as np


# =============================================================================
# Data Models
# =============================================================================

class TickSide(Enum):
    BUY = auto()
    SELL = auto()
    UNKNOWN = auto()


class TickCondition(Enum):
    REGULAR = auto()
    OPENING = auto()
    CLOSING = auto()
    OUT_OF_SEQUENCE = auto()
    CANCEL = auto()
    CORRECTION = auto()


@dataclass(slots=True)
class Tick:
    """Normalized market tick data."""
    symbol: str
    timestamp: float  # Nanoseconds since epoch
    price: Decimal
    size: Decimal
    exchange: str
    side: TickSide = TickSide.UNKNOWN
    conditions: List[TickCondition] = field(default_factory=list)
    tape: str = ""
    source: str = ""  # Original data source
    
    # Pre-computed hash for fast lookups
    def __post_init__(self):
        object.__setattr__(
            self, '_hash', 
            hash((self.symbol, self.timestamp, self.price, self.size))
        )
    
    def __hash__(self):
        return self._hash


@dataclass(slots=True)
class PriceLevel:
    """Price level in order book."""
    price: Decimal
    size: Decimal
    order_count: int = 0
    timestamp: float = 0.0
    
    def __hash__(self):
        return hash(self.price)
    
    def __eq__(self, other):
        if isinstance(other, PriceLevel):
            return self.price == other.price
        return self.price == other
    
    def __lt__(self, other):
        if isinstance(other, PriceLevel):
            return self.price < other.price
        return self.price < other


@dataclass(slots=True)
class OrderBookSnapshot:
    """L2 Order book snapshot."""
    symbol: str
    timestamp: float
    sequence: int
    bids: List[PriceLevel]  # Sorted descending
    asks: List[PriceLevel]  # Sorted ascending
    
    def best_bid(self) -> Optional[PriceLevel]:
        return self.bids[0] if self.bids else None
    
    def best_ask(self) -> Optional[PriceLevel]:
        return self.asks[0] if self.asks else None
    
    def mid_price(self) -> Optional[Decimal]:
        best_bid = self.best_bid()
        best_ask = self.best_ask()
        if best_bid and best_ask:
            return (best_bid.price + best_ask.price) / 2
        return None
    
    def spread(self) -> Optional[Decimal]:
        best_bid = self.best_bid()
        best_ask = self.best_ask()
        if best_bid and best_ask:
            return best_ask.price - best_bid.price
        return None


@dataclass(slots=True)
class OrderBookUpdate:
    """Incremental order book update."""
    symbol: str
    timestamp: float
    sequence: int
    is_snapshot: bool
    bids_changes: List[Tuple[Decimal, Decimal]]  # (price, size) - size=0 means delete
    asks_changes: List[Tuple[Decimal, Decimal]]


@dataclass(slots=True)
class OHLCVBar:
    """OHLCV Bar data."""
    symbol: str
    timestamp: float  # Bar open time
    timeframe: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    trades: int = 0
    vwap: Optional[Decimal] = None
    
    @property
    def range(self) -> Decimal:
        return self.high - self.low


# =============================================================================
# Circuit Breaker
# =============================================================================

class CircuitState(Enum):
    CLOSED = auto()      # Normal operation
    OPEN = auto()        # Failing, rejecting requests
    HALF_OPEN = auto()   # Testing if recovered


class CircuitBreaker:
    """Circuit breaker for fault tolerance."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
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
    
    async def call(self, coro: Coroutine) -> Any:
        """Execute coroutine with circuit breaker protection."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                else:
                    raise CircuitBreakerOpen(f"Circuit {self.name} is OPEN")
            
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpen(f"Circuit {self.name} is HALF_OPEN (max calls)")
                self._half_open_calls += 1
        
        try:
            result = await coro
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        return time.monotonic() - self._last_failure_time >= self.recovery_timeout
    
    async def _on_success(self):
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._reset()
            else:
                self._failure_count = 0
    
    async def _on_failure(self):
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
    
    def _reset(self):
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time = None


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass


# =============================================================================
# Backpressure Handler
# =============================================================================

class DropPolicy(Enum):
    OLDEST = auto()
    NEWEST = auto()
    SAMPLE = auto()  # Drop every Nth message


class BackpressureHandler:
    """Handles backpressure with configurable drop policies."""
    
    def __init__(
        self,
        max_queue_size: int = 1_000_000,
        drop_policy: DropPolicy = DropPolicy.OLDEST,
        sample_rate: int = 10,
    ):
        self.max_queue_size = max_queue_size
        self.drop_policy = drop_policy
        self.sample_rate = sample_rate
        
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._dropped_count = 0
        self._total_count = 0
        self._sample_counter = 0
    
    @property
    def queue_size(self) -> int:
        return self._queue.qsize()
    
    @property
    def utilization(self) -> float:
        return self._queue.qsize() / self.max_queue_size
    
    @property
    def drop_rate(self) -> float:
        if self._total_count == 0:
            return 0.0
        return self._dropped_count / self._total_count
    
    async def put(self, item: Any) -> bool:
        """Put item into queue, applying drop policy if full."""
        self._total_count += 1
        
        if self._queue.qsize() < self.max_queue_size:
            await self._queue.put(item)
            return True
        
        # Queue is full, apply drop policy
        self._dropped_count += 1
        
        if self.drop_policy == DropPolicy.OLDEST:
            # Drop oldest and add new
            try:
                self._queue.get_nowait()
                await self._queue.put(item)
                return True
            except asyncio.QueueEmpty:
                pass
        
        elif self.drop_policy == DropPolicy.NEWEST:
            # Simply drop the new item
            return False
        
        elif self.drop_policy == DropPolicy.SAMPLE:
            self._sample_counter += 1
            if self._sample_counter % self.sample_rate == 0:
                # Keep this one, drop oldest
                try:
                    self._queue.get_nowait()
                    await self._queue.put(item)
                    return True
                except asyncio.QueueEmpty:
                    pass
        
        return False
    
    async def get(self) -> Any:
        """Get item from queue."""
        return await self._queue.get()
    
    def get_nowait(self) -> Optional[Any]:
        """Get item from queue without waiting."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None


# =============================================================================
# Market Data Publisher (WebSocket Pub/Sub)
# =============================================================================

T = TypeVar('T')


class Subscription:
    """Represents a client subscription."""
    
    def __init__(
        self,
        client_id: str,
        channels: Set[str],
        symbols: Set[str],
        callback: Callable[[Any], Coroutine],
    ):
        self.client_id = client_id
        self.channels = channels
        self.symbols = symbols
        self.callback = callback
        self.created_at = time.monotonic()
        self.message_count = 0
        self.byte_count = 0


class MarketDataPublisher:
    """
    High-performance WebSocket publisher with pub/sub semantics.
    
    Features:
    - Channel-based subscriptions
    - Symbol filtering
    - Compression
    - Connection pooling
    - Backpressure handling
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        max_connections: int = 100_000,
        compression: bool = True,
        heartbeat_interval: float = 30.0,
    ):
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.compression = compression
        self.heartbeat_interval = heartbeat_interval
        
        # Subscriptions: channel -> symbol -> set of subscriptions
        self._subscriptions: Dict[str, Dict[str, Set[Subscription]]] = defaultdict(
            lambda: defaultdict(set)
        )
        
        # Client lookup: client_id -> subscription
        self._clients: Dict[str, Subscription] = {}
        
        # Metrics
        self._total_messages_sent = 0
        self._total_bytes_sent = 0
        self._active_connections = 0
        
        # Backpressure
        self._backpressure = BackpressureHandler()
        
        # Circuit breaker
        self._circuit = CircuitBreaker("websocket_publisher")
        
        # Locks
        self._sub_lock = asyncio.Lock()
        self._running = False
        self._server = None
    
    async def start(self):
        """Start the WebSocket server."""
        self._running = True
        # Start heartbeat task
        asyncio.create_task(self._heartbeat_loop())
        # Start publish loop
        asyncio.create_task(self._publish_loop())
    
    async def stop(self):
        """Stop the WebSocket server."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
    
    async def subscribe(
        self,
        client_id: str,
        channels: List[str],
        symbols: List[str],
        callback: Callable[[Any], Coroutine],
    ) -> bool:
        """Subscribe a client to channels and symbols."""
        if self._active_connections >= self.max_connections:
            return False
        
        async with self._sub_lock:
            # Unsubscribe existing if any
            await self.unsubscribe(client_id)
            
            subscription = Subscription(
                client_id=client_id,
                channels=set(channels),
                symbols=set(symbols),
                callback=callback,
            )
            
            self._clients[client_id] = subscription
            
            for channel in channels:
                for symbol in symbols:
                    self._subscriptions[channel][symbol].add(subscription)
            
            self._active_connections += 1
            return True
    
    async def unsubscribe(self, client_id: str):
        """Unsubscribe a client."""
        async with self._sub_lock:
            if client_id not in self._clients:
                return
            
            subscription = self._clients.pop(client_id)
            
            for channel in subscription.channels:
                for symbol in subscription.symbols:
                    self._subscriptions[channel][symbol].discard(subscription)
                    # Clean up empty sets
                    if not self._subscriptions[channel][symbol]:
                        del self._subscriptions[channel][symbol]
                if not self._subscriptions[channel]:
                    del self._subscriptions[channel]
            
            self._active_connections -= 1
    
    async def publish(self, channel: str, symbol: str, message: Any):
        """Publish a message to channel/symbol subscribers."""
        await self._backpressure.put((channel, symbol, message))
    
    async def _publish_loop(self):
        """Main publish loop with batching."""
        while self._running:
            try:
                # Batch messages for efficiency
                batch = []
                deadline = time.monotonic() + 0.001  # 1ms max wait
                
                while len(batch) < 100 and time.monotonic() < deadline:
                    try:
                        item = await asyncio.wait_for(
                            self._backpressure.get(),
                            timeout=0.001
                        )
                        batch.append(item)
                    except asyncio.TimeoutError:
                        break
                
                if batch:
                    await self._circuit.call(self._process_batch(batch))
                
            except Exception as e:
                # Log error but continue
                await asyncio.sleep(0.001)
    
    async def _process_batch(self, batch: List[Tuple[str, str, Any]]):
        """Process a batch of messages."""
        # Group by subscription for efficiency
        messages_by_client: Dict[str, List[Any]] = defaultdict(list)
        
        async with self._sub_lock:
            for channel, symbol, message in batch:
                if channel in self._subscriptions:
                    if symbol in self._subscriptions[channel]:
                        for sub in self._subscriptions[channel][symbol]:
                            messages_by_client[sub.client_id].append(message)
        
        # Send to clients concurrently
        tasks = []
        for client_id, messages in messages_by_client.items():
            if client_id in self._clients:
                sub = self._clients[client_id]
                for msg in messages:
                    tasks.append(self._send_to_client(sub, msg))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_to_client(self, subscription: Subscription, message: Any):
        """Send message to a client."""
        try:
            await subscription.callback(message)
            subscription.message_count += 1
            self._total_messages_sent += 1
        except Exception:
            # Client disconnected or error, unsubscribe
            await self.unsubscribe(subscription.client_id)
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats to clients."""
        while self._running:
            await asyncio.sleep(self.heartbeat_interval)
            
            heartbeat_msg = {"type": "heartbeat", "timestamp": time.time()}
            
            async with self._sub_lock:
                clients = list(self._clients.values())
            
            for sub in clients:
                try:
                    await sub.callback(heartbeat_msg)
                except Exception:
                    await self.unsubscribe(sub.client_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics."""
        return {
            "active_connections": self._active_connections,
            "total_messages_sent": self._total_messages_sent,
            "total_bytes_sent": self._total_bytes_sent,
            "queue_utilization": self._backpressure.utilization,
            "drop_rate": self._backpressure.drop_rate,
            "circuit_state": self._circuit.state.name,
        }


# =============================================================================
# Tick Aggregator
# =============================================================================

class TickAggregator:
    """
    High-performance tick-to-bar aggregator.
    
    Supports:
    - Time-based aggregation (1s, 5s, 1m, etc.)
    - Volume-based aggregation
    - Tick-based aggregation
    - Running VWAP calculation
    """
    
    def __init__(
        self,
        timeframes: List[str] = None,
        on_bar_callback: Optional[Callable[[OHLCVBar], Coroutine]] = None,
    ):
        # Parse timeframes: e.g., "1m" -> 60 seconds
        self.timeframes = timeframes or ["1m"]
        self.timeframe_seconds = {
            tf: self._parse_timeframe(tf) for tf in self.timeframes
        }
        
        self.on_bar_callback = on_bar_callback
        
        # Bar state: symbol -> timeframe -> current bar
        self._bars: Dict[str, Dict[str, dict]] = defaultdict(
            lambda: defaultdict(dict)
        )
        
        # Completed bars buffer
        self._completed_bars: asyncio.Queue = asyncio.Queue(maxsize=10000)
        
        # Backpressure
        self._backpressure = BackpressureHandler()
        
        # Running state
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    @staticmethod
    def _parse_timeframe(tf: str) -> int:
        """Parse timeframe string to seconds."""
        unit = tf[-1].lower()
        value = int(tf[:-1])
        
        multipliers = {
            's': 1,
            'm': 60,
            'h': 60 * 60,
            'd': 24 * 60 * 60,
        }
        return value * multipliers.get(unit, 60)
    
    def start(self):
        """Start the aggregator."""
        self._running = True
        self._task = asyncio.create_task(self._aggregation_loop())
    
    async def stop(self):
        """Stop the aggregator."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def process_tick(self, tick: Tick):
        """Process a single tick."""
        await self._backpressure.put(tick)
    
    async def _aggregation_loop(self):
        """Main aggregation loop."""
        while self._running:
            try:
                tick = await asyncio.wait_for(
                    self._backpressure.get(),
                    timeout=0.1
                )
                await self._process_tick_internal(tick)
            except asyncio.TimeoutError:
                # Check for bars that need to be closed
                await self._close_expired_bars()
            except asyncio.CancelledError:
                break
            except Exception:
                # Log and continue
                await asyncio.sleep(0.001)
    
    async def _process_tick_internal(self, tick: Tick):
        """Process tick and update bars."""
        symbol = tick.symbol
        tick_time = tick.timestamp / 1e9  # Convert ns to seconds
        
        for timeframe, seconds in self.timeframe_seconds.items():
            # Calculate bar timestamp (floor to timeframe)
            bar_time = (int(tick_time) // seconds) * seconds
            
            bar_state = self._bars[symbol][timeframe]
            
            if not bar_state or bar_state['timestamp'] != bar_time:
                # Close previous bar if exists
                if bar_state:
                    await self._close_bar(symbol, timeframe, bar_state)
                
                # Start new bar
                bar_state.update({
                    'timestamp': bar_time,
                    'open': tick.price,
                    'high': tick.price,
                    'low': tick.price,
                    'close': tick.price,
                    'volume': tick.size,
                    'trades': 1,
                    'vwap_numerator': tick.price * tick.size,
                })
            else:
                # Update existing bar
                bar_state['high'] = max(bar_state['high'], tick.price)
                bar_state['low'] = min(bar_state['low'], tick.price)
                bar_state['close'] = tick.price
                bar_state['volume'] += tick.size
                bar_state['trades'] += 1
                bar_state['vwap_numerator'] += tick.price * tick.size
    
    async def _close_bar(self, symbol: str, timeframe: str, bar_state: dict):
        """Close a completed bar and emit."""
        volume = bar_state['volume']
        vwap = (
            bar_state['vwap_numerator'] / volume
            if volume > 0 else bar_state['close']
        )
        
        bar = OHLCVBar(
            symbol=symbol,
            timestamp=bar_state['timestamp'],
            timeframe=timeframe,
            open=bar_state['open'],
            high=bar_state['high'],
            low=bar_state['low'],
            close=bar_state['close'],
            volume=volume,
            trades=bar_state['trades'],
            vwap=vwap,
        )
        
        await self._completed_bars.put(bar)
        
        if self.on_bar_callback:
            try:
                await self.on_bar_callback(bar)
            except Exception:
                pass
    
    async def _close_expired_bars(self):
        """Close bars that have expired."""
        current_time = time.time()
        
        for symbol in list(self._bars.keys()):
            for timeframe, seconds in self.timeframe_seconds.items():
                bar_state = self._bars[symbol][timeframe]
                if bar_state:
                    bar_end_time = bar_state['timestamp'] + seconds
                    if current_time >= bar_end_time:
                        await self._close_bar(symbol, timeframe, bar_state)
                        self._bars[symbol][timeframe] = {}
    
    async def get_bar(self, symbol: str, timeframe: str) -> Optional[OHLCVBar]:
        """Get current bar for symbol/timeframe."""
        bar_state = self._bars[symbol][timeframe]
        if not bar_state:
            return None
        
        volume = bar_state['volume']
        vwap = (
            bar_state['vwap_numerator'] / volume
            if volume > 0 else bar_state['close']
        )
        
        return OHLCVBar(
            symbol=symbol,
            timestamp=bar_state['timestamp'],
            timeframe=timeframe,
            open=bar_state['open'],
            high=bar_state['high'],
            low=bar_state['low'],
            close=bar_state['close'],
            volume=volume,
            trades=bar_state['trades'],
            vwap=vwap,
        )


# =============================================================================
# Order Book Reconstructor
# =============================================================================

class OrderBookReconstructor:
    """
    L2 Order book reconstructor with snapshot management.
    
    Features:
    - Incremental updates
    - Snapshot synchronization
    - Sequence validation
    - Price level aggregation
    """
    
    def __init__(
        self,
        max_depth: int = 1000,
        snapshot_interval: float = 5.0,
        price_precision: int = 8,
        size_precision: int = 8,
    ):
        self.max_depth = max_depth
        self.snapshot_interval = snapshot_interval
        self.price_precision = price_precision
        self.size_precision = size_precision
        
        # Order books: symbol -> book state
        self._books: Dict[str, dict] = {}
        
        # Snapshot callbacks
        self._snapshot_callbacks: List[Callable[[OrderBookSnapshot], Coroutine]] = []
        self._update_callbacks: List[Callable[[OrderBookUpdate], Coroutine]] = []
        
        # Backpressure
        self._backpressure = BackpressureHandler()
        
        # Running state
        self._running = False
        self._tasks: List[asyncio.Task] = []
    
    def start(self):
        """Start the reconstructor."""
        self._running = True
        self._tasks.append(asyncio.create_task(self._process_loop()))
        self._tasks.append(asyncio.create_task(self._snapshot_loop()))
    
    async def stop(self):
        """Stop the reconstructor."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    
    def register_snapshot_callback(
        self,
        callback: Callable[[OrderBookSnapshot], Coroutine]
    ):
        """Register callback for snapshot events."""
        self._snapshot_callbacks.append(callback)
    
    def register_update_callback(
        self,
        callback: Callable[[OrderBookUpdate], Coroutine]
    ):
        """Register callback for update events."""
        self._update_callbacks.append(callback)
    
    async def process_update(self, update: OrderBookUpdate):
        """Process an order book update."""
        await self._backpressure.put(update)
    
    async def process_snapshot(self, snapshot: OrderBookSnapshot):
        """Process a full snapshot."""
        symbol = snapshot.symbol
        
        self._books[symbol] = {
            'bids': {level.price: level for level in snapshot.bids},
            'asks': {level.price: level for level in snapshot.asks},
            'sequence': snapshot.sequence,
            'timestamp': snapshot.timestamp,
            'last_update': time.monotonic(),
        }
        
        # Notify callbacks
        for callback in self._snapshot_callbacks:
            try:
                await callback(snapshot)
            except Exception:
                pass
    
    async def _process_loop(self):
        """Main processing loop."""
        while self._running:
            try:
                update = await asyncio.wait_for(
                    self._backpressure.get(),
                    timeout=0.1
                )
                await self._process_update_internal(update)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(0.001)
    
    async def _process_update_internal(self, update: OrderBookUpdate):
        """Process incremental update."""
        symbol = update.symbol
        
        if symbol not in self._books and not update.is_snapshot:
            # Skip updates until we have a snapshot
            return
        
        if update.is_snapshot:
            # Convert update to snapshot
            bids = [
                PriceLevel(price=p, size=s, timestamp=update.timestamp)
                for p, s in update.bids_changes
            ]
            asks = [
                PriceLevel(price=p, size=s, timestamp=update.timestamp)
                for p, s in update.asks_changes
            ]
            snapshot = OrderBookSnapshot(
                symbol=symbol,
                timestamp=update.timestamp,
                sequence=update.sequence,
                bids=sorted(bids, reverse=True)[:self.max_depth],
                asks=sorted(asks)[:self.max_depth],
            )
            await self.process_snapshot(snapshot)
            return
        
        book = self._books[symbol]
        
        # Validate sequence
        if update.sequence <= book['sequence']:
            # Duplicate or out of order, skip
            return
        
        # Apply bid changes
        for price, size in update.bids_changes:
            if size == 0:
                book['bids'].pop(price, None)
            else:
                book['bids'][price] = PriceLevel(
                    price=price,
                    size=size,
                    timestamp=update.timestamp,
                )
        
        # Apply ask changes
        for price, size in update.asks_changes:
            if size == 0:
                book['asks'].pop(price, None)
            else:
                book['asks'][price] = PriceLevel(
                    price=price,
                    size=size,
                    timestamp=update.timestamp,
                )
        
        book['sequence'] = update.sequence
        book['last_update'] = time.monotonic()
        
        # Notify callbacks
        for callback in self._update_callbacks:
            try:
                await callback(update)
            except Exception:
                pass
    
    async def _snapshot_loop(self):
        """Generate periodic snapshots."""
        while self._running:
            await asyncio.sleep(self.snapshot_interval)
            
            current_time = time.monotonic()
            
            for symbol, book in list(self._books.items()):
                # Check if book is stale
                if current_time - book['last_update'] > 60:
                    continue
                
                # Build snapshot
                bids = sorted(book['bids'].values(), reverse=True)[:self.max_depth]
                asks = sorted(book['asks'].values())[:self.max_depth]
                
                snapshot = OrderBookSnapshot(
                    symbol=symbol,
                    timestamp=time.time() * 1e9,
                    sequence=book['sequence'],
                    bids=bids,
                    asks=asks,
                )
                
                for callback in self._snapshot_callbacks:
                    try:
                        await callback(snapshot)
                    except Exception:
                        pass
    
    def get_book(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """Get current order book for symbol."""
        if symbol not in self._books:
            return None
        
        book = self._books[symbol]
        bids = sorted(book['bids'].values(), reverse=True)[:self.max_depth]
        asks = sorted(book['asks'].values())[:self.max_depth]
        
        return OrderBookSnapshot(
            symbol=symbol,
            timestamp=time.time() * 1e9,
            sequence=book['sequence'],
            bids=bids,
            asks=asks,
        )
    
    def get_quote(self, symbol: str) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Get best bid/ask for symbol."""
        book = self.get_book(symbol)
        if not book:
            return None, None
        
        best_bid = book.bids[0].price if book.bids else None
        best_ask = book.asks[0].price if book.asks else None
        
        return best_bid, best_ask


# =============================================================================
# Data Normalizer
# =============================================================================

class DataNormalizer:
    """
    Multi-source data normalizer with circuit breaker and failover.
    
    Features:
    - Schema validation
    - Timestamp normalization
    - Source failover
    - Duplicate detection
    """
    
    def __init__(
        self,
        primary_source: str = "polygon",
        failover_sources: List[str] = None,
        dedup_window_ms: float = 100.0,
    ):
        self.primary_source = primary_source
        self.failover_sources = failover_sources or []
        self.dedup_window_ms = dedup_window_ms
        
        # Source registry
        self._sources: Dict[str, Any] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Current active source
        self._active_source = primary_source
        
        # Duplicate detection
        self._recent_ticks: Set[int] = set()
        self._tick_timestamps: List[Tuple[int, float]] = []
        
        # Normalization callbacks
        self._tick_callbacks: List[Callable[[Tick], Coroutine]] = []
        
        # Stats
        self._normalized_count = 0
        self._dropped_count = 0
    
    def register_source(self, name: str, source: Any):
        """Register a data source."""
        self._sources[name] = source
        self._circuit_breakers[name] = CircuitBreaker(
            name=f"source_{name}",
            failure_threshold=5,
            recovery_timeout=30.0,
        )
    
    def register_tick_callback(self, callback: Callable[[Tick], Coroutine]):
        """Register callback for normalized ticks."""
        self._tick_callbacks.append(callback)
    
    async def normalize_tick(
        self,
        source: str,
        raw_data: Dict[str, Any],
    ) -> Optional[Tick]:
        """Normalize raw tick data from a source."""
        try:
            # Check circuit breaker
            cb = self._circuit_breakers.get(source)
            if cb and cb.state == CircuitState.OPEN:
                # Try failover
                if source == self._active_source:
                    await self._failover()
                return None
            
            # Normalize based on source
            normalizer = self._get_normalizer(source)
            tick = await normalizer(raw_data)
            
            if tick is None:
                return None
            
            # Deduplication
            if self._is_duplicate(tick):
                self._dropped_count += 1
                return None
            
            self._normalized_count += 1
            
            # Notify callbacks
            for callback in self._tick_callbacks:
                try:
                    await callback(tick)
                except Exception:
                    pass
            
            return tick
            
        except Exception as e:
            # Record failure
            if cb:
                await cb._on_failure()
            raise
    
    def _get_normalizer(self, source: str) -> Callable:
        """Get normalizer function for source."""
        normalizers = {
            "polygon": self._normalize_polygon,
            "alpaca": self._normalize_alpaca,
            "binance": self._normalize_binance,
            "coinbase": self._normalize_coinbase,
            "twelvedata": self._normalize_twelvedata,
        }
        return normalizers.get(source, self._normalize_generic)
    
    async def _normalize_polygon(self, data: Dict) -> Optional[Tick]:
        """Normalize Polygon.io tick data."""
        # Polygon format: { "sym": "AAPL", "p": 150.25, "s": 100, ... }
        symbol = data.get("sym", "")
        if not symbol:
            return None
        
        # Convert timestamp (nanoseconds)
        timestamp = data.get("t", int(time.time() * 1e9))
        
        # Map conditions
        conditions = []
        raw_conditions = data.get("c", [])
        for c in raw_conditions:
            if c == 1:
                conditions.append(TickCondition.REGULAR)
            elif c == 7:
                conditions.append(TickCondition.OPENING)
            elif c == 14:
                conditions.append(TickCondition.CLOSING)
        
        return Tick(
            symbol=symbol,
            timestamp=timestamp,
            price=Decimal(str(data.get("p", 0))),
            size=Decimal(str(data.get("s", 0))),
            exchange=data.get("x", ""),
            side=TickSide.BUY if data.get("t") == 1 else TickSide.SELL,
            conditions=conditions,
            tape=data.get("z", ""),
            source="polygon",
        )
    
    async def _normalize_alpaca(self, data: Dict) -> Optional[Tick]:
        """Normalize Alpaca Markets tick data."""
        # Alpaca format: { "T": "t", "S": "AAPL", "p": 150.25, ... }
        msg_type = data.get("T")
        if msg_type != "t":
            return None
        
        symbol = data.get("S", "")
        if not symbol:
            return None
        
        timestamp = data.get("t", int(time.time() * 1e9))
        
        return Tick(
            symbol=symbol,
            timestamp=timestamp,
            price=Decimal(str(data.get("p", 0))),
            size=Decimal(str(data.get("s", 0))),
            exchange=data.get("x", ""),
            side=TickSide.BUY if data.get("tks") == "B" else TickSide.SELL,
            conditions=[TickCondition.REGULAR],
            tape="",
            source="alpaca",
        )
    
    async def _normalize_binance(self, data: Dict) -> Optional[Tick]:
        """Normalize Binance trade data."""
        # Binance format: { "e": "trade", "s": "BTCUSDT", "p": "50000.00", ... }
        event_type = data.get("e")
        if event_type != "trade":
            return None
        
        symbol = data.get("s", "").replace("USDT", "-USD")
        if not symbol:
            return None
        
        # Binance timestamp is milliseconds
        timestamp = data.get("T", int(time.time() * 1000)) * 1_000_000
        
        return Tick(
            symbol=symbol,
            timestamp=timestamp,
            price=Decimal(str(data.get("p", 0))),
            size=Decimal(str(data.get("q", 0))),
            exchange="BINANCE",
            side=TickSide.BUY if data.get("m") == False else TickSide.SELL,
            conditions=[TickCondition.REGULAR],
            tape="",
            source="binance",
        )
    
    async def _normalize_coinbase(self, data: Dict) -> Optional[Tick]:
        """Normalize Coinbase trade data."""
        # Coinbase format: { "type": "match", "product_id": "BTC-USD", ... }
        msg_type = data.get("type")
        if msg_type != "match":
            return None
        
        symbol = data.get("product_id", "")
        if not symbol:
            return None
        
        # Parse ISO timestamp
        time_str = data.get("time", "")
        if time_str:
            from datetime import datetime
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            timestamp = int(dt.timestamp() * 1e9)
        else:
            timestamp = int(time.time() * 1e9)
        
        return Tick(
            symbol=symbol,
            timestamp=timestamp,
            price=Decimal(str(data.get("price", 0))),
            size=Decimal(str(data.get("size", 0))),
            exchange="COINBASE",
            side=TickSide.BUY if data.get("side") == "buy" else TickSide.SELL,
            conditions=[TickCondition.REGULAR],
            tape="",
            source="coinbase",
        )
    
    async def _normalize_twelvedata(self, data: Dict) -> Optional[Tick]:
        """Normalize TwelveData tick data."""
        # TwelveData format
        symbol = data.get("symbol", "")
        if not symbol:
            return None
        
        timestamp = data.get("timestamp", int(time.time() * 1e9))
        
        return Tick(
            symbol=symbol,
            timestamp=timestamp,
            price=Decimal(str(data.get("price", 0))),
            size=Decimal(str(data.get("volume", 0))),
            exchange=data.get("exchange", ""),
            side=TickSide.UNKNOWN,
            conditions=[TickCondition.REGULAR],
            tape="",
            source="twelvedata",
        )
    
    async def _normalize_generic(self, data: Dict) -> Optional[Tick]:
        """Generic normalizer fallback."""
        # Attempt to extract common fields
        symbol = data.get("symbol", data.get("sym", data.get("s", "")))
        if not symbol:
            return None
        
        price = data.get("price", data.get("p", 0))
        size = data.get("size", data.get("s", data.get("volume", data.get("q", 0))))
        
        return Tick(
            symbol=symbol,
            timestamp=int(time.time() * 1e9),
            price=Decimal(str(price)),
            size=Decimal(str(size)),
            exchange=data.get("exchange", data.get("x", "")),
            side=TickSide.UNKNOWN,
            conditions=[],
            tape="",
            source="generic",
        )
    
    def _is_duplicate(self, tick: Tick) -> bool:
        """Check if tick is a duplicate."""
        tick_hash = hash(tick)
        
        # Clean old entries
        cutoff = time.monotonic() - (self.dedup_window_ms / 1000)
        self._tick_timestamps = [
            (h, t) for h, t in self._tick_timestamps if t > cutoff
        ]
        self._recent_ticks = set(h for h, t in self._tick_timestamps)
        
        if tick_hash in self._recent_ticks:
            return True
        
        self._recent_ticks.add(tick_hash)
        self._tick_timestamps.append((tick_hash, time.monotonic()))
        return False
    
    async def _failover(self):
        """Failover to next available source."""
        current_idx = -1
        if self._active_source in [self.primary_source] + self.failover_sources:
            try:
                current_idx = [self.primary_source] + self.failover_sources.index(
                    self._active_source
                )
            except ValueError:
                pass
        
        # Try next sources
        all_sources = [self.primary_source] + self.failover_sources
        for i in range(current_idx + 1, len(all_sources)):
            source = all_sources[i]
            cb = self._circuit_breakers.get(source)
            if cb and cb.state != CircuitState.OPEN:
                self._active_source = source
                return
        
        # All sources down, stay with current
    
    def get_stats(self) -> Dict[str, Any]:
        """Get normalizer statistics."""
        return {
            "active_source": self._active_source,
            "normalized_count": self._normalized_count,
            "dropped_count": self._dropped_count,
            "circuit_states": {
                name: cb.state.name
                for name, cb in self._circuit_breakers.items()
            },
        }


# =============================================================================
# Service Orchestrator
# =============================================================================

class MarketDataService:
    """
    Main service orchestrator that wires all components together.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Initialize components
        self.publisher = MarketDataPublisher(
            host=self.config.get("websocket_host", "0.0.0.0"),
            port=self.config.get("websocket_port", 8080),
            max_connections=self.config.get("max_connections", 100000),
        )
        
        self.aggregator = TickAggregator(
            timeframes=self.config.get("timeframes", ["1m", "5m", "15m"]),
            on_bar_callback=self._on_bar,
        )
        
        self.orderbook = OrderBookReconstructor(
            max_depth=self.config.get("orderbook_depth", 1000),
        )
        
        self.normalizer = DataNormalizer(
            primary_source=self.config.get("primary_source", "polygon"),
            failover_sources=self.config.get("failover_sources", []),
        )
        
        # Wire components
        self._wire_components()
    
    def _wire_components(self):
        """Wire components together."""
        # Normalizer -> Publisher (ticks)
        self.normalizer.register_tick_callback(self._on_normalized_tick)
        
        # Normalizer -> Aggregator
        self.normalizer.register_tick_callback(self.aggregator.process_tick)
        
        # OrderBook -> Publisher
        self.orderbook.register_update_callback(self._on_orderbook_update)
        
        # Aggregator bars already have callback in constructor
    
    async def _on_normalized_tick(self, tick: Tick):
        """Handle normalized tick."""
        await self.publisher.publish("ticks", tick.symbol, {
            "type": "tick",
            "symbol": tick.symbol,
            "timestamp": tick.timestamp,
            "price": str(tick.price),
            "size": str(tick.size),
            "exchange": tick.exchange,
            "side": tick.side.name,
        })
    
    async def _on_orderbook_update(self, update: OrderBookUpdate):
        """Handle order book update."""
        await self.publisher.publish("orderbook", update.symbol, {
            "type": "orderbook",
            "symbol": update.symbol,
            "timestamp": update.timestamp,
            "sequence": update.sequence,
            "bids": update.bids_changes,
            "asks": update.asks_changes,
        })
    
    async def _on_bar(self, bar: OHLCVBar):
        """Handle new bar."""
        await self.publisher.publish("bars", bar.symbol, {
            "type": "bar",
            "symbol": bar.symbol,
            "timestamp": bar.timestamp,
            "timeframe": bar.timeframe,
            "open": str(bar.open),
            "high": str(bar.high),
            "low": str(bar.low),
            "close": str(bar.close),
            "volume": str(bar.volume),
            "vwap": str(bar.vwap) if bar.vwap else None,
        })
    
    async def start(self):
        """Start the service."""
        self.aggregator.start()
        self.orderbook.start()
        await self.publisher.start()
    
    async def stop(self):
        """Stop the service."""
        await self.publisher.stop()
        await self.aggregator.stop()
        await self.orderbook.stop()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get combined service statistics."""
        return {
            "publisher": self.publisher.get_stats(),
            "normalizer": self.normalizer.get_stats(),
        }
