"""
DragonScope Enterprise - Market Data Service Package
====================================================

High-performance market data infrastructure for enterprise trading systems.

Modules:
--------
- orderbook: Price-time priority order book with microsecond latency
- aggregators: Time, volume, and tick bar aggregators with circular buffers
- service: Main service class with WebSocket pub/sub and Redis caching

Example:
--------
    import asyncio
    from service import MarketDataService, MarketTick
    
    service = MarketDataService(redis_url="redis://localhost:6379")
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
"""

__version__ = "1.0.0"
__author__ = "DragonScope Enterprise"

# Core exports
from .orderbook import (
    OrderBook,
    Order,
    Trade,
    PriceLevel,
    Side,
    OrderType
)

from .aggregators import (
    MultiTimeframeAggregator,
    TimeBarAggregator,
    VolumeBarAggregator,
    TickBarAggregator,
    OHLCVBar,
    Tick,
    BarType,
    CircularBuffer
)

from .service import (
    MarketDataService,
    MarketTick,
    ServiceStats,
    Subscription
)

__all__ = [
    # Order Book
    "OrderBook",
    "Order",
    "Trade",
    "PriceLevel",
    "Side",
    "OrderType",
    
    # Aggregators
    "MultiTimeframeAggregator",
    "TimeBarAggregator",
    "VolumeBarAggregator",
    "TickBarAggregator",
    "OHLCVBar",
    "Tick",
    "BarType",
    "CircularBuffer",
    
    # Service
    "MarketDataService",
    "MarketTick",
    "ServiceStats",
    "Subscription",
]
