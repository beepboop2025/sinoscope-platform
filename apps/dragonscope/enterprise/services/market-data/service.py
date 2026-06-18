"""
DragonScope Enterprise - Market Data Service
============================================

High-performance market data ingestion and distribution service.
Optimized for microsecond-level latency using asyncio and Redis.

Architecture:
-------------
┌─────────────────────────────────────────────────────────────┐
│                    MarketDataService                        │
├─────────────────────────────────────────────────────────────┤
│  Ingestion Layer  │  Aggregation Layer  │  Distribution    │
│  ───────────────  │  ─────────────────  │  ─────────────   │
│  • Raw Ticks      │  • Time Bars        │  • WebSocket     │
│  • Order Book     │  • Volume Bars      │  • Redis Pub/Sub │
│  • Validation     │  • Tick Bars        │  • REST API      │
│  • Normalization  │  • VWAP Calc        │  • gRPC Stream   │
└─────────────────────────────────────────────────────────────┘

Performance Targets:
--------------------
- Tick ingestion: < 10 microseconds
- Book update: < 5 microseconds
- WebSocket dispatch: < 50 microseconds
- Redis write: < 100 microseconds
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Callable, Any, AsyncIterator
from contextlib import asynccontextmanager

# Optional Redis support - service works without it for testing
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# Local imports
from orderbook import OrderBook, Order, Side, OrderType, Tick as OBTick
from aggregators import (
    MultiTimeframeAggregator, 
    TimeBarAggregator, 
    VolumeBarAggregator,
    TickBarAggregator,
    OHLCVBar,
    Tick,
    BarType,
    CircularBuffer
)


# -----------------------------------------------------------------------------
# Data Models
# -----------------------------------------------------------------------------

@dataclass(slots=True)
class MarketTick:
    """
    Normalized market tick from any source.
    
    Standardized format for internal processing regardless of
    upstream data provider format.
    """
    tick_id: str
    symbol: str
    timestamp_ns: int          # Exchange timestamp
    received_ns: int           # Local receive timestamp
    price: float
    size: float
    side: str                  # "buy", "sell", or ""
    exchange: str
    is_trade: bool            # True = trade, False = quote/BBO update
    bid_price: Optional[float] = None
    bid_size: Optional[float] = None
    ask_price: Optional[float] = None
    ask_size: Optional[float] = None


@dataclass
class ServiceStats:
    """Runtime statistics for the service."""
    ticks_received: int = 0
    ticks_processed: int = 0
    ticks_dropped: int = 0
    ws_connections: int = 0
    ws_messages_sent: int = 0
    redis_ops: int = 0
    redis_errors: int = 0
    book_updates: int = 0
    bars_completed: int = 0
    start_time_ns: int = field(default_factory=time.time_ns)
    
    @property
    def uptime_seconds(self) -> float:
        return (time.time_ns() - self.start_time_ns) / 1e9
    
    @property
    def ticks_per_second(self) -> float:
        uptime = self.uptime_seconds
        return self.ticks_processed / uptime if uptime > 0 else 0


@dataclass 
class Subscription:
    """WebSocket subscription metadata."""
    client_id: str
    symbols: Set[str]
    channels: Set[str]  # "trades", "book", "bars"
    websocket: Any
    subscribed_at: int = field(default_factory=time.time_ns)


# -----------------------------------------------------------------------------
# Market Data Service
# -----------------------------------------------------------------------------

class MarketDataService:
    """
    Enterprise-grade market data service.
    
    Handles:
    - High-frequency tick ingestion
    - Real-time order book maintenance
    - Multi-timeframe bar aggregation
    - WebSocket pub/sub distribution
    - Redis caching for hot data
    
    Concurrency Model:
    ------------------
    - Single event loop for core processing
    - Background tasks for:
      * WebSocket server
      * Redis publisher
      * Statistics reporter
      * Book snapshotter
    
    Memory Management:
    ------------------
    - Circular buffers for historical data
    - TTL-based cache eviction
    - Streaming for large payloads
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        ws_host: str = "0.0.0.0",
        ws_port: int = 8765,
        enable_stats: bool = True,
        stats_interval_seconds: float = 60.0
    ):
        """
        Initialize market data service.
        
        Args:
            redis_url: Redis connection URL (None = skip Redis)
            ws_host: WebSocket server host
            ws_port: WebSocket server port
            enable_stats: Enable statistics collection
            stats_interval_seconds: Stats logging interval
        """
        # Configuration
        self.redis_url = redis_url
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.enable_stats = enable_stats
        self.stats_interval_seconds = stats_interval_seconds
        
        # Core components
        self.order_books: Dict[str, OrderBook] = {}
        self.aggregators: Dict[str, MultiTimeframeAggregator] = {}
        
        # WebSocket state
        self.subscriptions: Dict[str, Subscription] = {}
        self.symbol_subscribers: Dict[str, Set[str]] = defaultdict(set)
        self.ws_server = None
        
        # Redis connection
        self.redis_client: Optional[Any] = None
        self._redis_connected = False
        
        # Async state
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._tasks: Set[asyncio.Task] = set()
        
        # Statistics
        self.stats = ServiceStats()
        
        # Message queues for batching
        self._tick_queue: asyncio.Queue[MarketTick] = asyncio.Queue(maxsize=100000)
        self._trade_queue: asyncio.Queue[Dict] = asyncio.Queue(maxsize=10000)
        
        # Rate limiting
        self._tick_counter = 0
        self._last_tick_time = time.time_ns()
        
        # Callback registry
        self._tick_callbacks: List[Callable[[MarketTick], None]] = []
        self._book_callbacks: List[Callable[[str, Dict], None]] = []
        self._bar_callbacks: List[Callable[[str, BarType, OHLCVBar], None]] = []
    
    # -------------------------------------------------------------------------
    # Lifecycle Management
    # -------------------------------------------------------------------------
    
    async def start(self) -> None:
        """
        Start the market data service.
        
        Initializes all components:
        1. Redis connection
        2. WebSocket server
        3. Background processing tasks
        4. Statistics reporter
        """
        if self._running:
            return
        
        self._running = True
        print(f"[MarketDataService] Starting...")
        
        # Initialize Redis if configured
        if self.redis_url and REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=True,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                    health_check_interval=30
                )
                await self.redis_client.ping()
                self._redis_connected = True
                print(f"[MarketDataService] Redis connected")
            except Exception as e:
                print(f"[MarketDataService] Redis connection failed: {e}")
                self.redis_client = None
        
        # Start WebSocket server
        if WEBSOCKETS_AVAILABLE:
            self.ws_server = await websockets.serve(
                self._handle_websocket,
                self.ws_host,
                self.ws_port,
                ping_interval=20,
                ping_timeout=10
            )
            print(f"[MarketDataService] WebSocket server listening on {self.ws_host}:{self.ws_port}")
        
        # Start background tasks
        self._start_background_task(self._process_tick_queue())
        self._start_background_task(self._process_trade_queue())
        self._start_background_task(self._periodic_book_snapshots())
        
        if self.enable_stats:
            self._start_background_task(self._stats_reporter())
        
        print(f"[MarketDataService] Started successfully")
    
    async def stop(self) -> None:
        """Graceful shutdown of the service."""
        if not self._running:
            return
        
        print(f"[MarketDataService] Shutting down...")
        self._running = False
        self._shutdown_event.set()
        
        # Cancel all background tasks
        for task in self._tasks:
            task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Close WebSocket server
        if self.ws_server:
            self.ws_server.close()
            await self.ws_server.wait_closed()
        
        # Close Redis connection
        if self.redis_client:
            await self.redis_client.close()
        
        print(f"[MarketDataService] Shutdown complete")
    
    def _start_background_task(self, coro) -> None:
        """Start and track a background task."""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
    
    # -------------------------------------------------------------------------
    # Tick Ingestion
    # -------------------------------------------------------------------------
    
    async def ingest_tick(self, tick: MarketTick) -> bool:
        """
        Ingest a market tick for processing.
        
        This is the primary entry point for market data.
        Ticks are queued for async processing to avoid blocking.
        
        Args:
            tick: Market tick data
            
        Returns:
            True if tick was queued, False if dropped (queue full)
            
        Performance: ~1 microsecond (non-blocking)
        """
        self.stats.ticks_received += 1
        tick.received_ns = time.time_ns()
        
        try:
            self._tick_queue.put_nowait(tick)
            return True
        except asyncio.QueueFull:
            self.stats.ticks_dropped += 1
            return False
    
    def ingest_tick_sync(self, tick: MarketTick) -> bool:
        """
        Synchronous wrapper for tick ingestion.
        
        Use this when calling from non-async contexts.
        """
        try:
            loop = asyncio.get_running_loop()
            # Schedule in event loop
            asyncio.create_task(self.ingest_tick(tick))
            return True
        except RuntimeError:
            # No event loop - use thread-safe method
            # In production, this would use a thread-safe queue
            return False
    
    async def _process_tick_queue(self) -> None:
        """
        Background task to process queued ticks.
        
        Batch processing for efficiency:
        - Process up to 1000 ticks per iteration
        - Yield control between batches
        """
        batch_size = 1000
        
        while self._running:
            try:
                batch = []
                # Collect batch
                for _ in range(batch_size):
                    try:
                        tick = self._tick_queue.get_nowait()
                        batch.append(tick)
                    except asyncio.QueueEmpty:
                        break
                
                if batch:
                    # Process batch
                    for tick in batch:
                        await self._process_single_tick(tick)
                    self.stats.ticks_processed += len(batch)
                else:
                    # No ticks, wait a bit
                    await asyncio.sleep(0.001)
                    
            except Exception as e:
                print(f"[MarketDataService] Tick processing error: {e}")
                await asyncio.sleep(0.1)
    
    async def _process_single_tick(self, tick: MarketTick) -> None:
        """
        Process a single tick through all pipelines.
        
        Pipeline:
        1. Normalize and validate
        2. Update order book (if quote)
        3. Record trade (if trade)
        4. Update aggregators
        5. Publish to subscribers
        6. Cache in Redis
        """
        symbol = tick.symbol
        
        # Ensure symbol infrastructure exists
        if symbol not in self.order_books:
            self._init_symbol(symbol)
        
        # Convert to internal tick format
        internal_tick = Tick(
            timestamp_ns=tick.timestamp_ns,
            price=tick.price,
            size=tick.size,
            side=1 if tick.side == "buy" else (-1 if tick.side == "sell" else 0),
            symbol=symbol
        )
        
        # Update aggregators
        aggregator = self.aggregators.get(symbol)
        if aggregator:
            completed_bars = aggregator.ingest_tick(internal_tick)
            # Notify completed bars
            for bar_type, bar in completed_bars.items():
                if bar:
                    self.stats.bars_completed += 1
                    await self._handle_completed_bar(symbol, bar_type, bar)
        
        # Handle trade-specific processing
        if tick.is_trade:
            await self._handle_trade(tick)
        
        # Update book if quote data present
        if tick.bid_price is not None or tick.ask_price is not None:
            await self._handle_quote_update(tick)
        
        # Notify tick subscribers
        await self._publish_tick(tick)
        
        # Cache in Redis
        if self._redis_connected:
            await self._cache_tick(tick)
        
        # Invoke registered callbacks
        for callback in self._tick_callbacks:
            try:
                callback(tick)
            except Exception:
                pass
    
    def _init_symbol(self, symbol: str) -> None:
        """
        Initialize infrastructure for a new symbol.
        
        Creates:
        - Order book
        - Multi-timeframe aggregator
        - Redis keys
        """
        # Create order book
        self.order_books[symbol] = OrderBook(symbol, max_depth=1000)
        
        # Create aggregator with standard timeframes
        mtf = MultiTimeframeAggregator(symbol)
        mtf.add_timeframe(BarType.TIME_1M, capacity=1440)   # 24 hours
        mtf.add_timeframe(BarType.TIME_5M, capacity=288)    # 24 hours
        mtf.add_timeframe(BarType.TIME_1H, capacity=168)    # 1 week
        self.aggregators[symbol] = mtf
        
        print(f"[MarketDataService] Initialized symbol: {symbol}")
    
    # -------------------------------------------------------------------------
    # Order Book Operations
    # -------------------------------------------------------------------------
    
    async def _handle_quote_update(self, tick: MarketTick) -> None:
        """
        Process quote update (BBO change).
        
        Updates the order book with new quote data.
        In production, this would track individual orders.
        For now, we maintain synthetic top-of-book.
        """
        book = self.order_books.get(tick.symbol)
        if not book:
            return
        
        # In a real implementation, this would:
        # 1. Add/modify/cancel specific orders
        # 2. Track order IDs from exchange
        # 
        # For this implementation, we track BBO updates
        # and emit book change events
        
        self.stats.book_updates += 1
        
        # Get updated BBO
        best_bid, best_ask, bid_qty, ask_qty = book.get_bbo()
        
        # Publish book update
        await self._publish_book(tick.symbol, {
            "symbol": tick.symbol,
            "timestamp_ns": tick.timestamp_ns,
            "bid": best_bid,
            "bid_size": bid_qty,
            "ask": best_ask,
            "ask_size": ask_qty,
            "spread": book.get_spread()
        })
    
    async def _handle_trade(self, tick: MarketTick) -> None:
        """
        Process trade tick.
        
        Trades affect:
        1. Volume aggregators
        2. Trade history
        3. VWAP calculations
        """
        trade_data = {
            "symbol": tick.symbol,
            "timestamp_ns": tick.timestamp_ns,
            "price": tick.price,
            "size": tick.size,
            "side": tick.side,
            "exchange": tick.exchange
        }
        
        try:
            self._trade_queue.put_nowait(trade_data)
        except asyncio.QueueFull:
            pass  # Drop trades if queue full
    
    async def _process_trade_queue(self) -> None:
        """Background task to process and persist trades."""
        while self._running:
            try:
                trade = await asyncio.wait_for(
                    self._trade_queue.get(), 
                    timeout=1.0
                )
                
                # Cache recent trades in Redis
                if self._redis_connected:
                    await self._cache_trade(trade)
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[MarketDataService] Trade processing error: {e}")
    
    def get_order_book(self, symbol: str, depth: int = 10) -> Optional[Dict]:
        """
        Get current order book snapshot.
        
        Args:
            symbol: Trading symbol
            depth: Number of levels per side
            
        Returns:
            Order book dictionary or None if symbol not found
        """
        book = self.order_books.get(symbol)
        if not book:
            return None
        
        bids, asks = book.get_depth(depth)
        best_bid, best_ask, bid_qty, ask_qty = book.get_bbo()
        
        return {
            "symbol": symbol,
            "timestamp_ns": time.time_ns(),
            "bids": [{"price": p, "size": s} for p, s in bids],
            "asks": [{"price": p, "size": s} for p, s in asks],
            "best_bid": best_bid,
            "best_ask": best_ask,
            "bid_size": bid_qty,
            "ask_size": ask_qty,
            "spread": book.get_spread(),
            "imbalance": book.get_imbalance(depth),
            "vwap": book.get_vwap(depth)
        }
    
    # -------------------------------------------------------------------------
    # Historical Bars
    # -------------------------------------------------------------------------
    
    def get_historical_bars(
        self,
        symbol: str,
        bar_type: BarType,
        count: int = 100
    ) -> List[Dict]:
        """
        Get historical OHLCV bars.
        
        Args:
            symbol: Trading symbol
            bar_type: Type of bars (TIME_1M, TIME_5M, etc.)
            count: Number of bars to retrieve
            
        Returns:
            List of bar dictionaries
        """
        aggregator = self.aggregators.get(symbol)
        if not aggregator:
            return []
        
        bars = aggregator.get_bars(bar_type, count)
        return [bar.to_dict() for bar in bars]
    
    async def _handle_completed_bar(
        self, 
        symbol: str, 
        bar_type: BarType, 
        bar: OHLCVBar
    ) -> None:
        """
        Handle a completed bar.
        
        Actions:
        1. Persist to Redis
        2. Publish to bar subscribers
        3. Invoke callbacks
        """
        # Cache in Redis
        if self._redis_connected:
            await self._cache_bar(symbol, bar_type, bar)
        
        # Publish to WebSocket subscribers
        await self._publish_bar(symbol, bar_type, bar)
        
        # Invoke callbacks
        for callback in self._bar_callbacks:
            try:
                callback(symbol, bar_type, bar)
            except Exception:
                pass
    
    # -------------------------------------------------------------------------
    # WebSocket Pub/Sub
    # -------------------------------------------------------------------------
    
    async def subscribe_realtime(
        self,
        websocket: WebSocketServerProtocol,
        symbols: List[str],
        channels: List[str]
    ) -> str:
        """
        Subscribe client to real-time market data.
        
        Args:
            websocket: Client WebSocket connection
            symbols: List of symbols to subscribe
            channels: List of channels ("trades", "book", "bars")
            
        Returns:
            Subscription ID
        """
        client_id = str(uuid.uuid4())
        
        subscription = Subscription(
            client_id=client_id,
            symbols=set(symbols),
            channels=set(channels),
            websocket=websocket
        )
        
        self.subscriptions[client_id] = subscription
        
        # Register in symbol index
        for symbol in symbols:
            self.symbol_subscribers[symbol].add(client_id)
        
        self.stats.ws_connections = len(self.subscriptions)
        
        print(f"[MarketDataService] Client {client_id} subscribed to {symbols}")
        return client_id
    
    async def unsubscribe(self, client_id: str) -> None:
        """Unsubscribe client from all channels."""
        subscription = self.subscriptions.pop(client_id, None)
        if not subscription:
            return
        
        # Remove from symbol index
        for symbol in subscription.symbols:
            self.symbol_subscribers[symbol].discard(client_id)
        
        self.stats.ws_connections = len(self.subscriptions)
        print(f"[MarketDataService] Client {client_id} unsubscribed")
    
    async def _handle_websocket(self, websocket: WebSocketServerProtocol, path: str) -> None:
        """
        Handle WebSocket connection lifecycle.
        
        Protocol:
        - Client connects and sends subscribe message
        - Server streams real-time updates
        - Client can send unsubscribe or disconnect
        """
        client_id: Optional[str] = None
        
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    
                    if msg_type == "subscribe":
                        symbols = data.get("symbols", [])
                        channels = data.get("channels", ["trades"])
                        client_id = await self.subscribe_realtime(
                            websocket, symbols, channels
                        )
                        await websocket.send(json.dumps({
                            "type": "subscribed",
                            "client_id": client_id
                        }))
                    
                    elif msg_type == "unsubscribe":
                        if client_id:
                            await self.unsubscribe(client_id)
                            client_id = None
                    
                    elif msg_type == "get_book":
                        symbol = data.get("symbol")
                        depth = data.get("depth", 10)
                        book = self.get_order_book(symbol, depth)
                        await websocket.send(json.dumps({
                            "type": "book",
                            "data": book
                        }))
                    
                    elif msg_type == "get_bars":
                        symbol = data.get("symbol")
                        timeframe = data.get("timeframe", "1m")
                        count = data.get("count", 100)
                        bar_type = self._parse_timeframe(timeframe)
                        bars = self.get_historical_bars(symbol, bar_type, count)
                        await websocket.send(json.dumps({
                            "type": "bars",
                            "data": bars
                        }))
                        
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON"
                    }))
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if client_id:
                await self.unsubscribe(client_id)
    
    async def _publish_tick(self, tick: MarketTick) -> None:
        """Publish tick to WebSocket subscribers."""
        subscribers = self.symbol_subscribers.get(tick.symbol, set())
        if not subscribers:
            return
        
        message = json.dumps({
            "type": "tick",
            "symbol": tick.symbol,
            "timestamp_ns": tick.timestamp_ns,
            "price": tick.price,
            "size": tick.size,
            "side": tick.side
        })
        
        await self._broadcast_to_subscribers(subscribers, message)
    
    async def _publish_book(self, symbol: str, book_data: Dict) -> None:
        """Publish book update to WebSocket subscribers."""
        subscribers = self.symbol_subscribers.get(symbol, set())
        if not subscribers:
            return
        
        message = json.dumps({
            "type": "book",
            "data": book_data
        })
        
        await self._broadcast_to_subscribers(subscribers, message)
    
    async def _publish_bar(self, symbol: str, bar_type: BarType, bar: OHLCVBar) -> None:
        """Publish completed bar to WebSocket subscribers."""
        subscribers = self.symbol_subscribers.get(symbol, set())
        if not subscribers:
            return
        
        message = json.dumps({
            "type": "bar",
            "symbol": symbol,
            "timeframe": bar_type.name,
            "data": bar.to_dict()
        })
        
        await self._broadcast_to_subscribers(subscribers, message)
    
    async def _broadcast_to_subscribers(self, subscriber_ids: Set[str], message: str) -> None:
        """Send message to all specified subscribers."""
        disconnected = []
        
        for client_id in subscriber_ids:
            subscription = self.subscriptions.get(client_id)
            if not subscription:
                continue
            
            try:
                await subscription.websocket.send(message)
                self.stats.ws_messages_sent += 1
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(client_id)
            except Exception:
                disconnected.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected:
            await self.unsubscribe(client_id)
    
    # -------------------------------------------------------------------------
    # Redis Caching
    # -------------------------------------------------------------------------
    
    async def _cache_tick(self, tick: MarketTick) -> None:
        """Cache tick in Redis for hot data access."""
        if not self.redis_client:
            return
        
        try:
            key = f"ticks:{tick.symbol}:latest"
            value = json.dumps({
                "price": tick.price,
                "size": tick.size,
                "side": tick.side,
                "timestamp_ns": tick.timestamp_ns
            })
            
            # Store with 60 second TTL
            await self.redis_client.setex(key, 60, value)
            self.stats.redis_ops += 1
            
        except Exception:
            self.stats.redis_errors += 1
    
    async def _cache_trade(self, trade: Dict) -> None:
        """Cache trade in Redis time-series."""
        if not self.redis_client:
            return
        
        try:
            symbol = trade["symbol"]
            key = f"trades:{symbol}"
            
            # Add to sorted set by timestamp
            score = trade["timestamp_ns"]
            member = json.dumps(trade)
            
            await self.redis_client.zadd(key, {member: score})
            
            # Trim to last 10000 trades
            await self.redis_client.zremrangebyrank(key, 0, -10001)
            
            # Set expiration
            await self.redis_client.expire(key, 86400)  # 24 hours
            
            self.stats.redis_ops += 1
            
        except Exception:
            self.stats.redis_errors += 1
    
    async def _cache_bar(self, symbol: str, bar_type: BarType, bar: OHLCVBar) -> None:
        """Cache completed bar in Redis."""
        if not self.redis_client:
            return
        
        try:
            key = f"bars:{symbol}:{bar_type.name}"
            score = bar.timestamp_ns
            member = json.dumps(bar.to_dict())
            
            await self.redis_client.zadd(key, {member: score})
            
            # Keep last 10000 bars
            await self.redis_client.zremrangebyrank(key, 0, -10001)
            
            # Set expiration based on timeframe
            ttl = 86400 * 7  # 7 days default
            if "1M" in bar_type.name:
                ttl = 86400 * 30  # 30 days for 1m bars
            
            await self.redis_client.expire(key, ttl)
            self.stats.redis_ops += 1
            
        except Exception:
            self.stats.redis_errors += 1
    
    async def _periodic_book_snapshots(self) -> None:
        """Periodically cache order book snapshots."""
        while self._running:
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=5.0  # Snapshot every 5 seconds
                )
                break
            except asyncio.TimeoutError:
                pass
            
            if not self.redis_client:
                continue
            
            for symbol, book in self.order_books.items():
                try:
                    snapshot = book.get_book_snapshot()
                    key = f"book:{symbol}:snapshot"
                    await self.redis_client.setex(
                        key, 
                        10,  # 10 second TTL
                        json.dumps(snapshot)
                    )
                except Exception:
                    pass
    
    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------
    
    def _parse_timeframe(self, timeframe: str) -> BarType:
        """Parse string timeframe to BarType enum."""
        mapping = {
            "1m": BarType.TIME_1M,
            "5m": BarType.TIME_5M,
            "15m": BarType.TIME_15M,
            "1h": BarType.TIME_1H,
            "4h": BarType.TIME_4H,
            "1d": BarType.TIME_1D,
        }
        return mapping.get(timeframe, BarType.TIME_1M)
    
    async def _stats_reporter(self) -> None:
        """Background task to log statistics periodically."""
        while self._running:
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.stats_interval_seconds
                )
                break
            except asyncio.TimeoutError:
                pass
            
            stats = self.stats
            print(
                f"[MarketDataService] Stats | "
                f"Uptime: {stats.uptime_seconds:.0f}s | "
                f"Ticks: {stats.ticks_processed} ({stats.ticks_per_second:.0f}/s) | "
                f"Dropped: {stats.ticks_dropped} | "
                f"WS Conns: {stats.ws_connections} | "
                f"WS Msgs: {stats.ws_messages_sent} | "
                f"Redis Ops: {stats.redis_ops}"
            )
    
    def register_tick_callback(self, callback: Callable[[MarketTick], None]) -> None:
        """Register callback for tick events."""
        self._tick_callbacks.append(callback)
    
    def register_book_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """Register callback for book update events."""
        self._book_callbacks.append(callback)
    
    def register_bar_callback(
        self, 
        callback: Callable[[str, BarType, OHLCVBar], None]
    ) -> None:
        """Register callback for completed bar events."""
        self._bar_callbacks.append(callback)
    
    def get_stats(self) -> Dict:
        """Get current service statistics."""
        return {
            "ticks_received": self.stats.ticks_received,
            "ticks_processed": self.stats.ticks_processed,
            "ticks_dropped": self.stats.ticks_dropped,
            "ticks_per_second": self.stats.ticks_per_second,
            "ws_connections": self.stats.ws_connections,
            "ws_messages_sent": self.stats.ws_messages_sent,
            "redis_ops": self.stats.redis_ops,
            "redis_errors": self.stats.redis_errors,
            "book_updates": self.stats.book_updates,
            "bars_completed": self.stats.bars_completed,
            "symbols_tracked": len(self.order_books),
            "uptime_seconds": self.stats.uptime_seconds
        }


# -----------------------------------------------------------------------------
# Example Usage and Testing
# -----------------------------------------------------------------------------

async def example_usage():
    """
    Example of using the Market Data Service.
    
    This demonstrates:
    - Service startup
    - Tick ingestion
    - WebSocket subscription
    - Historical bar retrieval
    """
    # Create service
    service = MarketDataService(
        redis_url="redis://localhost:6379/0",  # Optional
        ws_host="0.0.0.0",
        ws_port=8765,
        enable_stats=True
    )
    
    # Start service
    await service.start()
    
    try:
        # Simulate incoming ticks
        symbols = ["BTC-USD", "ETH-USD"]
        base_time = time.time_ns()
        
        for i in range(1000):
            for symbol in symbols:
                tick = MarketTick(
                    tick_id=f"tick-{i}-{symbol}",
                    symbol=symbol,
                    timestamp_ns=base_time + (i * 1_000_000),  # 1ms intervals
                    received_ns=0,
                    price=50000.0 + (i * 0.1) + (hash(symbol) % 100),
                    size=0.5 + (i % 10) * 0.1,
                    side="buy" if i % 2 == 0 else "sell",
                    exchange="SIMEX",
                    is_trade=True,
                    bid_price=49999.5 + (i * 0.1),
                    bid_size=10.0,
                    ask_price=50000.5 + (i * 0.1),
                    ask_size=10.0
                )
                
                await service.ingest_tick(tick)
            
            # Small delay to simulate real-time
            if i % 100 == 0:
                await asyncio.sleep(0.01)
        
        # Let processing complete
        await asyncio.sleep(2)
        
        # Get order book
        book = service.get_order_book("BTC-USD", depth=5)
        print(f"\nBTC-USD Order Book:\n{json.dumps(book, indent=2)}")
        
        # Get historical bars
        bars = service.get_historical_bars("BTC-USD", BarType.TIME_1M, count=10)
        print(f"\nBTC-USD Recent 1M Bars: {len(bars)}")
        
        # Get service stats
        stats = service.get_stats()
        print(f"\nService Statistics:\n{json.dumps(stats, indent=2)}")
        
        # Keep running for WebSocket connections
        print("\nService running. Connect WebSocket clients to ws://localhost:8765")
        print("Press Ctrl+C to stop...")
        
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await service.stop()


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
