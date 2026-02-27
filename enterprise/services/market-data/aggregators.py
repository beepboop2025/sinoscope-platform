"""
DragonScope Enterprise - Market Data Aggregators Module
=======================================================

High-performance tick aggregation into OHLCV bars using circular buffers.
Optimized for microsecond-level processing with minimal memory allocations.

Aggregator Types:
-----------------
1. TimeBarAggregator: Fixed time intervals (1min, 5min, 1hr)
2. VolumeBarAggregator: Fixed volume intervals
3. TickBarAggregator: Fixed tick count intervals

Design Principles:
------------------
- Zero-allocation hot path: Pre-allocate circular buffers
- Lock-free where possible: Single producer/consumer per aggregator
- Cache-friendly: Contiguous memory layouts
- Microsecond precision: nanosecond timestamps throughout
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, List, Optional, Tuple, Deque, Any
from array import array
import struct


class BarType(Enum):
    """Types of aggregation bars."""
    TIME_1M = auto()      # 1 minute
    TIME_5M = auto()      # 5 minutes
    TIME_15M = auto()     # 15 minutes
    TIME_1H = auto()      # 1 hour
    TIME_4H = auto()      # 4 hours
    TIME_1D = auto()      # 1 day
    VOLUME = auto()       # Volume-based
    TICK = auto()         # Tick count-based


@dataclass(slots=True)
class Tick:
    """
    Raw market tick data.
    
    Minimal representation for efficient processing.
    Using __slots__ for memory efficiency.
    
    Attributes:
        timestamp_ns: Nanosecond precision timestamp
        price: Trade/BBO price
        size: Quantity/volume
        side: Trade side (1=buy, -1=sell, 0=undefined)
        symbol: Trading symbol
    """
    timestamp_ns: int
    price: float
    size: float
    side: int = 0
    symbol: str = ""


@dataclass(slots=True)
class OHLCVBar:
    """
    OHLCV (Open, High, Low, Close, Volume) bar.
    
    Standard candlestick/bar representation with microsecond precision.
    
    Attributes:
        timestamp_ns: Bar start time (nanoseconds)
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Total volume
        trades: Number of ticks/trades in bar
        buy_volume: Volume from buy-initiated trades
        sell_volume: Volume from sell-initiated trades
        vwap: Volume-weighted average price
    """
    timestamp_ns: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: int = 0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    vwap: float = 0.0
    
    @property
    def span_ns(self) -> int:
        """Time span of bar in nanoseconds (override in subclasses)."""
        return 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp_ns": self.timestamp_ns,
            "timestamp_ms": self.timestamp_ns // 1_000_000,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "trades": self.trades,
            "buy_volume": self.buy_volume,
            "sell_volume": self.sell_volume,
            "vwap": self.vwap
        }
    
    def to_struct(self) -> bytes:
        """
        Serialize to compact binary format.
        
        Format: 8-byte timestamp + 8 doubles for prices/volumes + 4-byte trades
        Total: 80 bytes per bar (efficient for storage/transmission)
        """
        return struct.pack(
            '!QdddddddI',
            self.timestamp_ns,
            self.open, self.high, self.low, self.close,
            self.volume, self.buy_volume, self.sell_volume,
            self.trades
        )
    
    @classmethod
    def from_struct(cls, data: bytes) -> OHLCVBar:
        """Deserialize from binary format."""
        unpacked = struct.unpack('!QdddddddI', data)
        return cls(
            timestamp_ns=unpacked[0],
            open=unpacked[1],
            high=unpacked[2],
            low=unpacked[3],
            close=unpacked[4],
            volume=unpacked[5],
            buy_volume=unpacked[6],
            sell_volume=unpacked[7],
            trades=unpacked[8],
            vwap=(unpacked[6] + unpacked[7]) / unpacked[5] if unpacked[5] > 0 else 0
        )


class CircularBuffer:
    """
    Fixed-size circular buffer for OHLCV bars.
    
    Efficiently maintains recent history without allocations.
    Uses modulo arithmetic for index wrapping.
    
    Time Complexity:
    - Append: O(1)
    - Random access: O(1)
    - Iteration: O(n)
    
    Memory: Fixed at capacity * sizeof(OHLCVBar)
    """
    
    def __init__(self, capacity: int):
        """
        Initialize circular buffer.
        
        Args:
            capacity: Maximum number of bars to store
        """
        self.capacity = capacity
        self.buffer: List[Optional[OHLCVBar]] = [None] * capacity
        self.head = 0  # Index of most recent element
        self.size = 0  # Current number of elements
        self._write_count = 0  # Total writes (for overflow detection)
    
    def append(self, bar: OHLCVBar) -> Optional[OHLCVBar]:
        """
        Append bar to buffer.
        
        Args:
            bar: OHLCV bar to add
            
        Returns:
            Evicted bar if buffer was full, None otherwise
        """
        evicted = None
        
        # If buffer is full, we're about to overwrite
        if self.size == self.capacity:
            evicted = self.buffer[self.head]
        else:
            self.size += 1
        
        # Store at head position
        self.buffer[self.head] = bar
        
        # Move head forward (with wrap)
        self.head = (self.head + 1) % self.capacity
        self._write_count += 1
        
        return evicted
    
    def get(self, index: int) -> Optional[OHLCVBar]:
        """
        Get bar at logical index (0 = most recent).
        
        Args:
            index: Index from head (0 = newest, size-1 = oldest)
            
        Returns:
            OHLCV bar or None if index out of range
        """
        if index >= self.size:
            return None
        
        # Calculate actual index (head - 1 - index, with wrap)
        actual_idx = (self.head - 1 - index) % self.capacity
        return self.buffer[actual_idx]
    
    def get_range(self, start: int, end: int) -> List[OHLCVBar]:
        """
        Get range of bars [start, end) from most recent.
        
        Args:
            start: Start index (inclusive)
            end: End index (exclusive)
            
        Returns:
            List of OHLCV bars (newest to oldest)
        """
        result = []
        for i in range(start, min(end, self.size)):
            bar = self.get(i)
            if bar:
                result.append(bar)
        return result
    
    def get_all(self) -> List[OHLCVBar]:
        """Get all bars in chronological order (oldest to newest)."""
        if self.size == 0:
            return []
        
        result = []
        # Oldest first
        for i in range(self.size - 1, -1, -1):
            bar = self.get(i)
            if bar:
                result.insert(0, bar)
        return result
    
    def clear(self) -> None:
        """Clear all bars from buffer."""
        self.buffer = [None] * self.capacity
        self.head = 0
        self.size = 0
        self._write_count = 0
    
    def __len__(self) -> int:
        return self.size
    
    def __iter__(self):
        """Iterate from most recent to oldest."""
        for i in range(self.size):
            yield self.get(i)


class BaseAggregator(ABC):
    """
    Abstract base class for tick aggregators.
    
    Defines the common interface and shared functionality
    for all aggregation strategies.
    """
    
    def __init__(self, symbol: str, capacity: int = 1000):
        """
        Initialize base aggregator.
        
        Args:
            symbol: Trading symbol
            capacity: Circular buffer capacity
        """
        self.symbol = symbol
        self.capacity = capacity
        self.buffer = CircularBuffer(capacity)
        
        # Current bar being built
        self.current_bar: Optional[OHLCVBar] = None
        
        # Statistics
        self.ticks_processed: int = 0
        self.bars_completed: int = 0
        
        # Callbacks for bar completion events
        self._bar_callbacks: List[Callable[[OHLCVBar], None]] = []
        
        # Running VWAP calculation
        self._typical_volume_sum: float = 0.0
        self._volume_sum: float = 0.0
    
    @abstractmethod
    def ingest_tick(self, tick: Tick) -> Optional[OHLCVBar]:
        """
        Process incoming tick.
        
        Args:
            tick: Market tick data
            
        Returns:
            Completed bar if this tick closed one, None otherwise
        """
        pass
    
    @abstractmethod
    def _should_close_bar(self, tick: Tick) -> bool:
        """Determine if current bar should be closed."""
        pass
    
    @abstractmethod
    def _create_new_bar(self, tick: Tick) -> OHLCVBar:
        """Create new bar from tick."""
        pass
    
    def _update_bar(self, bar: OHLCVBar, tick: Tick) -> None:
        """
        Update OHLCV bar with new tick.
        
        Updates all bar statistics in-place for efficiency.
        """
        # Update OHLC
        if tick.price > bar.high:
            bar.high = tick.price
        if tick.price < bar.low:
            bar.low = tick.price
        bar.close = tick.price
        
        # Update volume
        bar.volume += tick.size
        bar.trades += 1
        
        # Track buy/sell volume
        if tick.side > 0:
            bar.buy_volume += tick.size
        elif tick.side < 0:
            bar.sell_volume += tick.size
        
        # Update VWAP incrementally
        self._typical_volume_sum += tick.price * tick.size
        self._volume_sum += tick.size
        if self._volume_sum > 0:
            bar.vwap = self._typical_volume_sum / self._volume_sum
    
    def _close_current_bar(self) -> Optional[OHLCVBar]:
        """
        Close current bar and store in buffer.
        
        Returns:
            The completed bar
        """
        if self.current_bar is None:
            return None
        
        completed_bar = self.current_bar
        evicted = self.buffer.append(completed_bar)
        
        self.bars_completed += 1
        self.current_bar = None
        
        # Reset VWAP accumulators
        self._typical_volume_sum = 0.0
        self._volume_sum = 0.0
        
        # Notify callbacks
        for callback in self._bar_callbacks:
            try:
                callback(completed_bar)
            except Exception:
                pass  # Don't let callbacks break aggregation
        
        return completed_bar
    
    def register_bar_callback(self, callback: Callable[[OHLCVBar], None]) -> None:
        """Register callback for completed bar events."""
        self._bar_callbacks.append(callback)
    
    def get_historical_bars(self, count: int) -> List[OHLCVBar]:
        """
        Get recent historical bars.
        
        Args:
            count: Number of bars to retrieve
            
        Returns:
            List of bars (newest to oldest)
        """
        return self.buffer.get_range(0, count)
    
    def get_all_bars(self) -> List[OHLCVBar]:
        """Get all bars in chronological order."""
        return self.buffer.get_all()
    
    def get_current_bar(self) -> Optional[OHLCVBar]:
        """Get the bar currently being built."""
        return self.current_bar
    
    def reset(self) -> None:
        """Reset aggregator state."""
        self.buffer.clear()
        self.current_bar = None
        self.ticks_processed = 0
        self.bars_completed = 0
        self._typical_volume_sum = 0.0
        self._volume_sum = 0.0


class TimeBarAggregator(BaseAggregator):
    """
    Time-based bar aggregator.
    
    Creates bars at fixed time intervals (1min, 5min, etc.).
    Uses nanosecond-precision timestamps for alignment.
    
    Bar Alignment:
    --------------
    Bars are aligned to epoch boundaries. For example, 1-minute
    bars always start at :00 seconds of each minute.
    
    Gap Handling:
    -------------
    Gaps in data (no trades for a period) are represented by
    missing bars in the buffer - no synthetic bars created.
    """
    
    # Interval mappings in nanoseconds
    INTERVALS = {
        BarType.TIME_1M: 60_000_000_000,      # 60 seconds
        BarType.TIME_5M: 300_000_000_000,     # 5 minutes
        BarType.TIME_15M: 900_000_000_000,    # 15 minutes
        BarType.TIME_1H: 3_600_000_000_000,   # 1 hour
        BarType.TIME_4H: 14_400_000_000_000,  # 4 hours
        BarType.TIME_1D: 86_400_000_000_000,  # 1 day
    }
    
    def __init__(self, symbol: str, bar_type: BarType, capacity: int = 1000):
        """
        Initialize time bar aggregator.
        
        Args:
            symbol: Trading symbol
            bar_type: Time interval type
            capacity: Buffer capacity
        """
        super().__init__(symbol, capacity)
        self.bar_type = bar_type
        self.interval_ns = self.INTERVALS[bar_type]
        self._current_bar_start: int = 0
    
    def ingest_tick(self, tick: Tick) -> Optional[OHLCVBar]:
        """
        Process tick for time-based aggregation.
        
        Algorithm:
        1. Calculate which bar this tick belongs to
        2. If new bar needed, close current and start new
        3. Update bar with tick data
        """
        self.ticks_processed += 1
        
        # Calculate bar start time (aligned to interval)
        bar_start = (tick.timestamp_ns // self.interval_ns) * self.interval_ns
        
        completed_bar = None
        
        # Check if we need to start a new bar
        if self.current_bar is None or bar_start > self._current_bar_start:
            # Close existing bar if any
            if self.current_bar is not None:
                completed_bar = self._close_current_bar()
            
            # Start new bar
            self._current_bar_start = bar_start
            self.current_bar = OHLCVBar(
                timestamp_ns=bar_start,
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
                volume=tick.size,
                trades=1,
                buy_volume=tick.size if tick.side > 0 else 0.0,
                sell_volume=tick.size if tick.side < 0 else 0.0,
                vwap=tick.price
            )
            self._typical_volume_sum = tick.price * tick.size
            self._volume_sum = tick.size
        else:
            # Update current bar
            self._update_bar(self.current_bar, tick)
        
        return completed_bar
    
    def _should_close_bar(self, tick: Tick) -> bool:
        """Check if tick belongs to new bar."""
        bar_start = (tick.timestamp_ns // self.interval_ns) * self.interval_ns
        return bar_start > self._current_bar_start
    
    def _create_new_bar(self, tick: Tick) -> OHLCVBar:
        """Create new time-based bar."""
        bar_start = (tick.timestamp_ns // self.interval_ns) * self.interval_ns
        return OHLCVBar(
            timestamp_ns=bar_start,
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            volume=0.0
        )
    
    def get_interval_seconds(self) -> int:
        """Get interval in seconds."""
        return self.interval_ns // 1_000_000_000


class VolumeBarAggregator(BaseAggregator):
    """
    Volume-based bar aggregator.
    
    Creates bars after fixed volume threshold is reached.
    Useful for analyzing price action proportional to trading activity.
    
    Characteristics:
    ----------------
    - Bar duration varies based on market activity
    - High activity = shorter bars
    - Low activity = longer bars
    - More uniform information content per bar
    """
    
    def __init__(self, symbol: str, volume_threshold: float, capacity: int = 1000):
        """
        Initialize volume bar aggregator.
        
        Args:
            symbol: Trading symbol
            volume_threshold: Volume required to close a bar
            capacity: Buffer capacity
        """
        super().__init__(symbol, capacity)
        self.volume_threshold = volume_threshold
        self._current_volume: float = 0.0
    
    def ingest_tick(self, tick: Tick) -> Optional[OHLCVBar]:
        """
        Process tick for volume-based aggregation.
        
        Algorithm:
        1. Add tick volume to accumulator
        2. If threshold reached, close bar and start new
        3. Handle partial fills across thresholds
        """
        self.ticks_processed += 1
        
        completed_bar = None
        remaining_size = tick.size
        
        while remaining_size > 0:
            if self.current_bar is None:
                # Start new bar
                self.current_bar = OHLCVBar(
                    timestamp_ns=tick.timestamp_ns,
                    open=tick.price,
                    high=tick.price,
                    low=tick.price,
                    close=tick.price,
                    volume=0.0
                )
                self._current_volume = 0.0
                self._typical_volume_sum = 0.0
                self._volume_sum = 0.0
            
            # Calculate how much can fit in current bar
            space_remaining = self.volume_threshold - self._current_volume
            fill_size = min(remaining_size, space_remaining)
            
            # Create partial tick for this fill
            partial_tick = Tick(
                timestamp_ns=tick.timestamp_ns,
                price=tick.price,
                size=fill_size,
                side=tick.side,
                symbol=tick.symbol
            )
            
            # Update bar
            self._update_bar(self.current_bar, partial_tick)
            self._current_volume += fill_size
            remaining_size -= fill_size
            
            # Check if bar is complete
            if self._current_volume >= self.volume_threshold:
                completed_bar = self._close_current_bar()
        
        return completed_bar
    
    def _should_close_bar(self, tick: Tick) -> bool:
        """Check if this tick would exceed volume threshold."""
        return self._current_volume + tick.size >= self.volume_threshold
    
    def _create_new_bar(self, tick: Tick) -> OHLCVBar:
        """Create new volume-based bar."""
        return OHLCVBar(
            timestamp_ns=tick.timestamp_ns,
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            volume=0.0
        )


class TickBarAggregator(BaseAggregator):
    """
    Tick count-based bar aggregator.
    
    Creates bars after fixed number of ticks (trades).
    Useful for analyzing price action per transaction.
    
    Characteristics:
    ----------------
    - Each bar represents exactly N trades
    - Equal statistical weight per bar
    - Filters out time/volume variations
    - Useful for high-frequency analysis
    """
    
    def __init__(self, symbol: str, tick_threshold: int, capacity: int = 1000):
        """
        Initialize tick bar aggregator.
        
        Args:
            symbol: Trading symbol
            tick_threshold: Number of ticks per bar
            capacity: Buffer capacity
        """
        super().__init__(symbol, capacity)
        self.tick_threshold = tick_threshold
        self._current_tick_count: int = 0
    
    def ingest_tick(self, tick: Tick) -> Optional[OHLCVBar]:
        """
        Process tick for tick-count aggregation.
        
        Algorithm:
        1. Increment tick counter
        2. Update bar OHLCV
        3. If tick count reached threshold, close bar
        """
        self.ticks_processed += 1
        
        completed_bar = None
        
        if self.current_bar is None:
            # Start new bar
            self.current_bar = OHLCVBar(
                timestamp_ns=tick.timestamp_ns,
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
                volume=tick.size
            )
            self._current_tick_count = 1
            self._typical_volume_sum = tick.price * tick.size
            self._volume_sum = tick.size
            
            # Track side
            if tick.side > 0:
                self.current_bar.buy_volume = tick.size
            elif tick.side < 0:
                self.current_bar.sell_volume = tick.size
        else:
            # Update existing bar
            self._update_bar(self.current_bar, tick)
            self._current_tick_count += 1
        
        # Check if bar is complete
        if self._current_tick_count >= self.tick_threshold:
            completed_bar = self._close_current_bar()
            self._current_tick_count = 0
        
        return completed_bar
    
    def _should_close_bar(self, tick: Tick) -> bool:
        """Check if this tick completes the bar."""
        return self._current_tick_count + 1 >= self.tick_threshold
    
    def _create_new_bar(self, tick: Tick) -> OHLCVBar:
        """Create new tick-based bar."""
        return OHLCVBar(
            timestamp_ns=tick.timestamp_ns,
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            volume=0.0
        )


class MultiTimeframeAggregator:
    """
    Manages multiple timeframe aggregators for a single symbol.
    
    Efficiently fans out ticks to all configured aggregators
    to maintain multiple timeframe views simultaneously.
    
    Usage:
    ------
        mtf = MultiTimeframeAggregator("BTC-USD")
        mtf.add_timeframe(BarType.TIME_1M, capacity=1440)   # 1 day of 1m bars
        mtf.add_timeframe(BarType.TIME_5M, capacity=288)    # 1 day of 5m bars
        mtf.add_timeframe(BarType.TIME_1H, capacity=168)    # 1 week of hourly bars
        
        completed_bars = mtf.ingest_tick(tick)
    """
    
    def __init__(self, symbol: str):
        """
        Initialize multi-timeframe aggregator.
        
        Args:
            symbol: Trading symbol
        """
        self.symbol = symbol
        self.aggregators: Dict[BarType, BaseAggregator] = {}
        self._bar_callbacks: Dict[BarType, List[Callable]] = {}
    
    def add_timeframe(self, bar_type: BarType, 
                      capacity: int = 1000,
                      volume_threshold: Optional[float] = None,
                      tick_threshold: Optional[int] = None) -> BaseAggregator:
        """
        Add a timeframe aggregator.
        
        Args:
            bar_type: Type of bars to aggregate
            capacity: Buffer capacity
            volume_threshold: Required for VOLUME bars
            tick_threshold: Required for TICK bars
            
        Returns:
            The created aggregator
        """
        if bar_type in self.aggregators:
            raise ValueError(f"Timeframe {bar_type} already exists")
        
        if bar_type in (BarType.VOLUME,):
            if volume_threshold is None:
                raise ValueError("volume_threshold required for volume bars")
            aggregator = VolumeBarAggregator(self.symbol, volume_threshold, capacity)
        elif bar_type in (BarType.TICK,):
            if tick_threshold is None:
                raise ValueError("tick_threshold required for tick bars")
            aggregator = TickBarAggregator(self.symbol, tick_threshold, capacity)
        else:
            aggregator = TimeBarAggregator(self.symbol, bar_type, capacity)
        
        self.aggregators[bar_type] = aggregator
        self._bar_callbacks[bar_type] = []
        return aggregator
    
    def ingest_tick(self, tick: Tick) -> Dict[BarType, Optional[OHLCVBar]]:
        """
        Fan out tick to all aggregators.
        
        Args:
            tick: Market tick data
            
        Returns:
            Dict mapping bar_type to completed bar (if any)
        """
        completed = {}
        for bar_type, aggregator in self.aggregators.items():
            completed[bar_type] = aggregator.ingest_tick(tick)
        return completed
    
    def get_aggregator(self, bar_type: BarType) -> Optional[BaseAggregator]:
        """Get specific aggregator by type."""
        return self.aggregators.get(bar_type)
    
    def get_bars(self, bar_type: BarType, count: int) -> List[OHLCVBar]:
        """Get historical bars for specific timeframe."""
        agg = self.aggregators.get(bar_type)
        if agg:
            return agg.get_historical_bars(count)
        return []
    
    def reset(self) -> None:
        """Reset all aggregators."""
        for aggregator in self.aggregators.values():
            aggregator.reset()
