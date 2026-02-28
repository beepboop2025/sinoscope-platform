# DragonScope Enterprise - Market Data Service

High-performance market data infrastructure optimized for microsecond-level latency.

## Architecture

```
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
```

## Performance Targets

| Operation | Target Latency |
|-----------|---------------|
| Tick Ingestion | < 10 microseconds |
| Order Book Update | < 5 microseconds |
| WebSocket Dispatch | < 50 microseconds |
| Redis Write | < 100 microseconds |
| Bar Aggregation | < 1 microsecond |

## Components

### 1. Order Book (`orderbook.py`)

Price-time priority order book with:
- O(log N) order insertion
- O(1) BBO retrieval
- Full L2 depth tracking
- Spread and imbalance calculations

```python
from orderbook import OrderBook, Order, Side, OrderType

book = OrderBook("BTC-USD", max_depth=1000)

# Add order
order = Order(
    order_id="ord-123",
    symbol="BTC-USD",
    side=Side.BID,
    price=50000.0,
    quantity=1.0,
    initial_quantity=1.0,
    timestamp_ns=time.time_ns()
)
trades = book.add_order(order)

# Get BBO
best_bid, best_ask, bid_qty, ask_qty = book.get_bbo()

# Get depth
bids, asks = book.get_depth(levels=10)
```

### 2. Aggregators (`aggregators.py`)

Multiple aggregation strategies with circular buffers:

**TimeBarAggregator** - Fixed time intervals (1m, 5m, 1h)
```python
from aggregators import TimeBarAggregator, BarType

agg = TimeBarAggregator("BTC-USD", BarType.TIME_1M, capacity=1440)
completed_bar = agg.ingest_tick(tick)
```

**VolumeBarAggregator** - Fixed volume intervals
```python
from aggregators import VolumeBarAggregator

agg = VolumeBarAggregator("BTC-USD", volume_threshold=100.0)
```

**TickBarAggregator** - Fixed tick count intervals
```python
from aggregators import TickBarAggregator

agg = TickBarAggregator("BTC-USD", tick_threshold=1000)
```

**MultiTimeframeAggregator** - Manage multiple timeframes
```python
from aggregators import MultiTimeframeAggregator, BarType

mtf = MultiTimeframeAggregator("BTC-USD")
mtf.add_timeframe(BarType.TIME_1M, capacity=1440)
mtf.add_timeframe(BarType.TIME_5M, capacity=288)
mtf.add_timeframe(BarType.TIME_1H, capacity=168)

completed = mtf.ingest_tick(tick)  # Returns dict of completed bars
```

### 3. Service (`service.py`)

Main service class with WebSocket and Redis integration:

```python
import asyncio
from service import MarketDataService, MarketTick

async def main():
    # Create and start service
    service = MarketDataService(
        redis_url="redis://localhost:6379/0",
        ws_host="0.0.0.0",
        ws_port=8765
    )
    await service.start()
    
    # Ingest tick
    tick = MarketTick(
        tick_id="123",
        symbol="BTC-USD",
        timestamp_ns=time.time_ns(),
        received_ns=0,
        price=50000.0,
        size=1.0,
        side="buy",
        exchange="EXCHANGE",
        is_trade=True
    )
    await service.ingest_tick(tick)
    
    # Get order book
    book = service.get_order_book("BTC-USD", depth=10)
    
    # Get historical bars
    bars = service.get_historical_bars("BTC-USD", BarType.TIME_1M, count=100)
    
    # Get stats
    stats = service.get_stats()
    
    await service.stop()

asyncio.run(main())
```

## WebSocket Protocol

Connect to `ws://host:port` and send subscription messages:

### Subscribe
```json
{
    "type": "subscribe",
    "symbols": ["BTC-USD", "ETH-USD"],
    "channels": ["trades", "book", "bars"]
}
```

### Tick Message (from server)
```json
{
    "type": "tick",
    "symbol": "BTC-USD",
    "timestamp_ns": 1700000000000000000,
    "price": 50000.0,
    "size": 1.0,
    "side": "buy"
}
```

### Book Message (from server)
```json
{
    "type": "book",
    "data": {
        "symbol": "BTC-USD",
        "bid": 49999.5,
        "ask": 50000.5,
        "bid_size": 10.0,
        "ask_size": 10.0,
        "spread": 1.0
    }
}
```

### Bar Message (from server)
```json
{
    "type": "bar",
    "symbol": "BTC-USD",
    "timeframe": "TIME_1M",
    "data": {
        "timestamp_ns": 1700000000000000000,
        "open": 50000.0,
        "high": 50100.0,
        "low": 49900.0,
        "close": 50050.0,
        "volume": 100.0,
        "trades": 50
    }
}
```

### Get Book Snapshot
```json
{
    "type": "get_book",
    "symbol": "BTC-USD",
    "depth": 10
}
```

### Get Historical Bars
```json
{
    "type": "get_bars",
    "symbol": "BTC-USD",
    "timeframe": "1m",
    "count": 100
}
```

## Redis Schema

### Latest Tick
```
Key: ticks:{symbol}:latest
Type: String (JSON)
TTL: 60 seconds
```

### Trade History
```
Key: trades:{symbol}
Type: Sorted Set (timestamp -> trade_json)
Size: Last 10000 trades
TTL: 86400 seconds (24 hours)
```

### Bar History
```
Key: bars:{symbol}:{timeframe}
Type: Sorted Set (timestamp -> bar_json)
Size: Last 10000 bars
TTL: 86400 * 7 seconds (7 days)
```

### Book Snapshot
```
Key: book:{symbol}:snapshot
Type: String (JSON)
TTL: 10 seconds
```

## Dependencies

Optional dependencies for full functionality:

```bash
# Redis support
pip install redis

# WebSocket support
pip install websockets
```

Service works without these for testing (data only kept in memory).

## Testing

Run the example:

```bash
cd /Users/mrinal/dev/DragonScope/enterprise/services/market-data
python service.py
```

Connect WebSocket client:

```bash
wscat -c ws://localhost:8765
> {"type": "subscribe", "symbols": ["BTC-USD"], "channels": ["trades", "book"]}
```

## Design Principles

1. **Zero-allocation hot path** - Pre-allocate circular buffers
2. **Lock-free where possible** - Single producer/consumer per component
3. **Cache-friendly** - Contiguous memory layouts
4. **Microsecond precision** - Nanosecond timestamps throughout
5. **Graceful degradation** - Works without Redis/WebSocket
