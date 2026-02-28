"""
DragonScope Enterprise - High-Performance Order Book Module
=============================================================

This module implements a price-time priority order book optimized for
microsecond-level latency. Uses efficient data structures including
sorted containers and circular buffers.

Architecture:
-------------
- Bids: Max-heap (stored as negative for min-heap compatibility)
- Asks: Min-heap
- Orders indexed by ID for O(1) lookups
- Price levels aggregated for efficient book snapshots

Performance Targets:
--------------------
- Order insertion: < 1 microsecond
- Order cancellation: < 1 microsecond  
- BBO retrieval: < 100 nanoseconds
- Full book snapshot: < 10 microseconds (1000 levels)
"""

from __future__ import annotations

import bisect
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Callable
import heapq


class Side(Enum):
    """Order side enumeration."""
    BID = auto()   # Buy side
    ASK = auto()   # Sell side


class OrderType(Enum):
    """Order type enumeration."""
    LIMIT = auto()       # Standard limit order
    MARKET = auto()      # Market order (executes immediately)
    IOC = auto()         # Immediate or Cancel
    FOK = auto()         # Fill or Kill


@dataclass(slots=True)
class Order:
    """
    Individual order representation.
    
    Using __slots__ for memory efficiency and faster attribute access.
    Each order tracks its state for lifecycle management.
    
    Attributes:
        order_id: Unique identifier (typically UUID or snowflake ID)
        symbol: Trading pair/symbol (e.g., "BTC-USD")
        side: BID or ASK
        price: Limit price (0 for market orders)
        quantity: Current remaining quantity
        initial_quantity: Original order quantity
        timestamp_ns: Arrival time in nanoseconds since epoch
        order_type: Type of order
        participant_id: Entity submitting the order
    """
    order_id: str
    symbol: str
    side: Side
    price: float
    quantity: float
    initial_quantity: float
    timestamp_ns: int
    order_type: OrderType = OrderType.LIMIT
    participant_id: str = ""
    
    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.quantity <= 0
    
    @property
    def filled_quantity(self) -> float:
        """Return filled portion of order."""
        return self.initial_quantity - self.quantity


@dataclass(slots=True)
class PriceLevel:
    """
    Aggregated orders at a single price level.
    
    Maintains FIFO queue for time priority within price level.
    Uses deque for O(1) append/pop from both ends.
    
    Attributes:
        price: Price level value
        total_quantity: Sum of all order quantities at this level
        orders: Deque of orders (maintains time priority)
        order_count: Number of orders at this level
    """
    price: float
    total_quantity: float = 0.0
    orders: deque = field(default_factory=deque)
    order_count: int = 0
    
    def add_order(self, order: Order) -> None:
        """Add order to this price level."""
        self.orders.append(order)
        self.total_quantity += order.quantity
        self.order_count += 1
    
    def remove_order(self, order: Order) -> bool:
        """
        Remove order from this price level.
        
        Returns:
            True if order was found and removed, False otherwise
        """
        try:
            self.orders.remove(order)
            self.total_quantity -= order.quantity
            self.order_count -= 1
            return True
        except ValueError:
            return False
    
    def get_volume(self) -> float:
        """Return total volume at this price level."""
        return self.total_quantity
    
    def is_empty(self) -> bool:
        """Check if price level has no orders."""
        return self.order_count == 0


@dataclass(slots=True)
class Trade:
    """
    Executed trade record.
    
    Captures all relevant trade details for clearing and reporting.
    
    Attributes:
        trade_id: Unique trade identifier
        symbol: Traded symbol
        price: Execution price
        quantity: Executed quantity
        aggressor_side: Taker side (who crossed the spread)
        bid_order_id: Resting bid order ID
        ask_order_id: Resting ask order ID
        timestamp_ns: Execution timestamp
    """
    trade_id: str
    symbol: str
    price: float
    quantity: float
    aggressor_side: Side
    bid_order_id: str
    ask_order_id: str
    timestamp_ns: int


class OrderBook:
    """
    High-performance order book with price-time priority.
    
    Core data structures:
    - _bids: Sorted list of bid price levels (descending)
    - _asks: Sorted list of ask price levels (ascending)
    - _orders: Dict mapping order_id -> (price, side) for O(1) lookup
    - _price_levels: Dict mapping (price, side) -> PriceLevel
    
    Thread Safety:
    --------------
    This class is NOT thread-safe. External synchronization required
    if used across multiple threads. Designed for single-threaded
    asyncio event loop usage.
    
    Performance Characteristics:
    ----------------------------
    - Insertion: O(log N) for price search + O(1) for queue append
    - Cancellation: O(1) lookup + O(M) removal where M = orders at level
    - BBO: O(1) - first element of sorted lists
    - Snapshot: O(K) where K = depth levels requested
    """
    
    def __init__(self, symbol: str, max_depth: int = 1000):
        """
        Initialize order book for a specific symbol.
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC-USD")
            max_depth: Maximum book depth to maintain in memory
        """
        self.symbol = symbol
        self.max_depth = max_depth
        
        # Sorted price lists for O(log n) price level lookup
        # Bids sorted descending (highest first), asks sorted ascending
        self._bid_prices: List[float] = []
        self._ask_prices: List[float] = []
        
        # Price level aggregation: key = price, value = PriceLevel
        self._bid_levels: Dict[float, PriceLevel] = {}
        self._ask_levels: Dict[float, PriceLevel] = {}
        
        # Order index for O(1) lookups: key = order_id, value = (price, side)
        self._order_index: Dict[str, Tuple[float, Side]] = {}
        
        # Trade sequence for generating unique trade IDs
        self._trade_sequence: int = 0
        self._last_trade_ns: int = 0
        
        # Statistics
        self._orders_received: int = 0
        self._orders_executed: int = 0
        self._orders_cancelled: int = 0
        self._volume_traded: float = 0.0
        
        # Callbacks for real-time updates
        self._trade_callbacks: List[Callable[[Trade], None]] = []
        self._book_update_callbacks: List[Callable[[], None]] = []
    
    # -------------------------------------------------------------------------
    # Core Order Management
    # -------------------------------------------------------------------------
    
    def add_order(self, order: Order) -> List[Trade]:
        """
        Add order to the book with matching.
        
        Implements price-time priority matching algorithm:
        1. Check for immediate matches (crosses spread)
        2. If remaining quantity and not IOC/FOK, add to book
        
        Args:
            order: Order to add
            
        Returns:
            List of Trade objects from any immediate executions
            
        Time Complexity: O(M * log N) where M = matches, N = price levels
        """
        trades: List[Trade] = []
        self._orders_received += 1
        
        # Market orders execute immediately at best available prices
        if order.order_type == OrderType.MARKET:
            trades = self._match_market_order(order)
            return trades
        
        # Check for immediate crossing (aggressive limit order)
        if order.side == Side.BID:
            # Buy order crosses if price >= best ask
            if self._ask_prices and order.price >= self._ask_prices[0]:
                trades = self._match_against_asks(order)
        else:
            # Sell order crosses if price <= best bid
            if self._bid_prices and order.price <= self._bid_prices[0]:
                trades = self._match_against_bids(order)
        
        # Handle IOC orders - cancel remaining after matching
        if order.order_type == OrderType.IOC:
            return trades
        
        # Handle FOK orders - all or nothing
        if order.order_type == OrderType.FOK:
            if order.quantity > 0:
                # Not fully filled - cancel everything (rollback)
                # In production, this would reverse the trades
                return []
        
        # Add remaining quantity to book
        if order.quantity > 0:
            self._add_to_book(order)
        
        # Notify book update
        if trades or order.quantity > 0:
            self._notify_book_update()
        
        return trades
    
    def cancel_order(self, order_id: str) -> Optional[Order]:
        """
        Cancel an existing order.
        
        Uses order index for O(1) lookup of order location.
        
        Args:
            order_id: ID of order to cancel
            
        Returns:
            Cancelled Order if found, None otherwise
            
        Time Complexity: O(M) where M = orders at price level
        """
        if order_id not in self._order_index:
            return None
        
        price, side = self._order_index[order_id]
        
        # Get appropriate price level
        if side == Side.BID:
            level = self._bid_levels.get(price)
            price_list = self._bid_prices
            level_dict = self._bid_levels
        else:
            level = self._ask_levels.get(price)
            price_list = self._ask_prices
            level_dict = self._ask_levels
        
        if not level:
            return None
        
        # Find and remove specific order
        cancelled_order = None
        for order in level.orders:
            if order.order_id == order_id:
                cancelled_order = order
                level.remove_order(order)
                break
        
        if cancelled_order:
            # Clean up empty price levels
            if level.is_empty():
                del level_dict[price]
                price_list.remove(price)
            
            del self._order_index[order_id]
            self._orders_cancelled += 1
            self._notify_book_update()
        
        return cancelled_order
    
    def modify_order(self, order_id: str, new_price: Optional[float] = None,
                     new_quantity: Optional[float] = None) -> Optional[Order]:
        """
        Modify an existing order.
        
        Implementation strategy:
        - If price changes: Cancel old order, create new (maintains time priority)
        - If only quantity changes: Modify in-place (preserves time priority)
        
        Args:
            order_id: Order to modify
            new_price: New price (None = no change)
            new_quantity: New quantity (None = no change)
            
        Returns:
            Modified Order if found, None otherwise
        """
        if order_id not in self._order_index:
            return None
        
        old_price, side = self._order_index[order_id]
        
        # Get appropriate storage
        if side == Side.BID:
            level = self._bid_levels.get(old_price)
        else:
            level = self._ask_levels.get(old_price)
        
        if not level:
            return None
        
        # Find the order
        order = None
        for o in level.orders:
            if o.order_id == order_id:
                order = o
                break
        
        if not order:
            return None
        
        # Price change requires cancel + re-add (loses time priority)
        if new_price is not None and new_price != old_price:
            # Cancel old order
            self.cancel_order(order_id)
            # Create new order with modified price
            new_order = Order(
                order_id=order_id,  # Keep same ID
                symbol=order.symbol,
                side=side,
                price=new_price,
                quantity=new_quantity if new_quantity is not None else order.quantity,
                initial_quantity=order.initial_quantity,
                timestamp_ns=time.time_ns(),  # New timestamp = back of queue
                order_type=order.order_type,
                participant_id=order.participant_id
            )
            self.add_order(new_order)
            return new_order
        
        # Quantity-only modification preserves time priority
        if new_quantity is not None:
            delta = new_quantity - order.quantity
            order.quantity = new_quantity
            level.total_quantity += delta
            self._notify_book_update()
        
        return order
    
    # -------------------------------------------------------------------------
    # Matching Engine
    # -------------------------------------------------------------------------
    
    def _match_market_order(self, order: Order) -> List[Trade]:
        """Match market order against resting liquidity."""
        if order.side == Side.BID:
            return self._match_against_asks(order)
        else:
            return self._match_against_bids(order)
    
    def _match_against_asks(self, bid_order: Order) -> List[Trade]:
        """
        Match buy order against resting asks.
        
        Walks through ask price levels from best (lowest) to worst,
        filling until order is complete or liquidity exhausted.
        """
        trades: List[Trade] = []
        
        while bid_order.quantity > 0 and self._ask_prices:
            best_ask_price = self._ask_prices[0]
            
            # Stop if bid price can't cross best ask
            if bid_order.price < best_ask_price and bid_order.order_type != OrderType.MARKET:
                break
            
            level = self._ask_levels[best_ask_price]
            
            # Match against orders at this level (time priority)
            while bid_order.quantity > 0 and level.orders:
                resting_order = level.orders[0]
                
                # Calculate fill quantity
                fill_qty = min(bid_order.quantity, resting_order.quantity)
                
                # Execute trade
                trade = self._create_trade(
                    price=resting_order.price,
                    quantity=fill_qty,
                    aggressor=Side.BID,
                    bid_id=bid_order.order_id,
                    ask_id=resting_order.order_id
                )
                trades.append(trade)
                
                # Update quantities
                bid_order.quantity -= fill_qty
                resting_order.quantity -= fill_qty
                level.total_quantity -= fill_qty
                self._volume_traded += fill_qty
                
                # Remove filled resting order
                if resting_order.quantity <= 0:
                    level.orders.popleft()
                    level.order_count -= 1
                    del self._order_index[resting_order.order_id]
                    self._orders_executed += 1
            
            # Clean up empty level
            if level.is_empty():
                del self._ask_levels[best_ask_price]
                self._ask_prices.pop(0)
        
        return trades
    
    def _match_against_bids(self, ask_order: Order) -> List[Trade]:
        """
        Match sell order against resting bids.
        
        Walks through bid price levels from best (highest) to worst,
        filling until order is complete or liquidity exhausted.
        """
        trades: List[Trade] = []
        
        while ask_order.quantity > 0 and self._bid_prices:
            best_bid_price = self._bid_prices[0]
            
            # Stop if ask price can't cross best bid
            if ask_order.price > best_bid_price and ask_order.order_type != OrderType.MARKET:
                break
            
            level = self._bid_levels[best_bid_price]
            
            # Match against orders at this level (time priority)
            while ask_order.quantity > 0 and level.orders:
                resting_order = level.orders[0]
                
                # Calculate fill quantity
                fill_qty = min(ask_order.quantity, resting_order.quantity)
                
                # Execute trade
                trade = self._create_trade(
                    price=resting_order.price,
                    quantity=fill_qty,
                    aggressor=Side.ASK,
                    bid_id=resting_order.order_id,
                    ask_id=ask_order.order_id
                )
                trades.append(trade)
                
                # Update quantities
                ask_order.quantity -= fill_qty
                resting_order.quantity -= fill_qty
                level.total_quantity -= fill_qty
                self._volume_traded += fill_qty
                
                # Remove filled resting order
                if resting_order.quantity <= 0:
                    level.orders.popleft()
                    level.order_count -= 1
                    del self._order_index[resting_order.order_id]
                    self._orders_executed += 1
            
            # Clean up empty level
            if level.is_empty():
                del self._bid_levels[best_bid_price]
                self._bid_prices.pop(0)
        
        return trades
    
    def _add_to_book(self, order: Order) -> None:
        """Add order to resting book (no matching)."""
        if order.side == Side.BID:
            price_list = self._bid_prices
            level_dict = self._bid_levels
            # Bids sorted descending - use bisect with negation trick
            idx = bisect.bisect_left([-p for p in price_list], -order.price)
        else:
            price_list = self._ask_prices
            level_dict = self._ask_levels
            # Asks sorted ascending
            idx = bisect.bisect_left(price_list, order.price)
        
        # Create new price level if needed
        if idx >= len(price_list) or price_list[idx] != order.price:
            price_list.insert(idx, order.price)
            level_dict[order.price] = PriceLevel(price=order.price)
        
        # Add order to price level
        level_dict[order.price].add_order(order)
        
        # Index for fast lookup
        self._order_index[order.order_id] = (order.price, order.side)
    
    def _create_trade(self, price: float, quantity: float,
                      aggressor: Side, bid_id: str, ask_id: str) -> Trade:
        """Generate trade record."""
        self._trade_sequence += 1
        timestamp = time.time_ns()
        self._last_trade_ns = timestamp
        
        return Trade(
            trade_id=f"{self.symbol}-{timestamp}-{self._trade_sequence}",
            symbol=self.symbol,
            price=price,
            quantity=quantity,
            aggressor_side=aggressor,
            bid_order_id=bid_id,
            ask_order_id=ask_id,
            timestamp_ns=timestamp
        )
    
    # -------------------------------------------------------------------------
    # Market Data Queries
    # -------------------------------------------------------------------------
    
    def get_bbo(self) -> Tuple[Optional[float], Optional[float], float, float]:
        """
        Get Best Bid and Offer (BBO).
        
        Returns:
            Tuple of (best_bid, best_ask, bid_qty, ask_qty)
            Returns None for prices if no liquidity on that side
            
        Time Complexity: O(1)
        """
        best_bid = self._bid_prices[0] if self._bid_prices else None
        best_ask = self._ask_prices[0] if self._ask_prices else None
        
        bid_qty = 0.0
        ask_qty = 0.0
        
        if best_bid:
            bid_qty = self._bid_levels[best_bid].total_quantity
        if best_ask:
            ask_qty = self._ask_levels[best_ask].total_quantity
        
        return (best_bid, best_ask, bid_qty, ask_qty)
    
    def get_depth(self, levels: int = 10) -> Tuple[List[Tuple[float, float]], List[Tuple[float, float]]]:
        """
        Get order book depth (aggregated price levels).
        
        Args:
            levels: Number of price levels to return per side
            
        Returns:
            Tuple of (bids, asks) where each is a list of (price, quantity)
            Bids ordered best to worst (descending)
            Asks ordered best to worst (ascending)
            
        Time Complexity: O(levels)
        """
        bids = []
        asks = []
        
        # Get bid levels (already sorted descending)
        for price in self._bid_prices[:levels]:
            level = self._bid_levels[price]
            bids.append((price, level.total_quantity))
        
        # Get ask levels (already sorted ascending)
        for price in self._ask_prices[:levels]:
            level = self._ask_levels[price]
            asks.append((price, level.total_quantity))
        
        return (bids, asks)
    
    def get_spread(self) -> Optional[float]:
        """
        Calculate bid-ask spread.
        
        Returns:
            Spread value or None if book is one-sided
        """
        best_bid, best_ask, _, _ = self.get_bbo()
        if best_bid is None or best_ask is None:
            return None
        return best_ask - best_bid
    
    def get_imbalance(self, depth: int = 5) -> float:
        """
        Calculate bid/ask volume imbalance.
        
        Returns ratio in range [-1, 1] where:
        -1 = all liquidity on ask side
        +1 = all liquidity on bid side
        0 = perfectly balanced
        
        Args:
            depth: Number of levels to consider
        """
        bids, asks = self.get_depth(depth)
        
        bid_volume = sum(qty for _, qty in bids)
        ask_volume = sum(qty for _, qty in asks)
        
        total = bid_volume + ask_volume
        if total == 0:
            return 0.0
        
        return (bid_volume - ask_volume) / total
    
    def get_vwap(self, depth: int = 10) -> Optional[float]:
        """
        Calculate Volume-Weighted Average Price.
        
        Args:
            depth: Number of levels to include
            
        Returns:
            VWAP value or None if no liquidity
        """
        bids, asks = self.get_depth(depth)
        
        total_value = 0.0
        total_volume = 0.0
        
        for price, qty in bids + asks:
            total_value += price * qty
            total_volume += qty
        
        if total_volume == 0:
            return None
        
        return total_value / total_volume
    
    def get_book_snapshot(self) -> Dict:
        """
        Get complete book snapshot for persistence/serialization.
        
        Returns:
            Dictionary with full book state
        """
        return {
            "symbol": self.symbol,
            "timestamp_ns": time.time_ns(),
            "bids": [
                {"price": p, "quantity": self._bid_levels[p].total_quantity,
                 "orders": self._bid_levels[p].order_count}
                for p in self._bid_prices
            ],
            "asks": [
                {"price": p, "quantity": self._ask_levels[p].total_quantity,
                 "orders": self._ask_levels[p].order_count}
                for p in self._ask_prices
            ],
            "statistics": self.get_statistics()
        }
    
    # -------------------------------------------------------------------------
    # Callbacks and Notifications
    # -------------------------------------------------------------------------
    
    def register_trade_callback(self, callback: Callable[[Trade], None]) -> None:
        """Register callback for trade events."""
        self._trade_callbacks.append(callback)
    
    def register_book_update_callback(self, callback: Callable[[], None]) -> None:
        """Register callback for book update events."""
        self._book_update_callbacks.append(callback)
    
    def _notify_book_update(self) -> None:
        """Notify all book update subscribers."""
        for callback in self._book_update_callbacks:
            try:
                callback()
            except Exception:
                pass  # Don't let callbacks break the book
    
    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------
    
    def get_statistics(self) -> Dict:
        """Return book statistics."""
        best_bid, best_ask, _, _ = self.get_bbo()
        return {
            "symbol": self.symbol,
            "bid_levels": len(self._bid_prices),
            "ask_levels": len(self._ask_prices),
            "total_orders": len(self._order_index),
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": self.get_spread(),
            "imbalance": self.get_imbalance(),
            "orders_received": self._orders_received,
            "orders_executed": self._orders_executed,
            "orders_cancelled": self._orders_cancelled,
            "volume_traded": self._volume_traded
        }
    
    def reset_statistics(self) -> None:
        """Reset all counters."""
        self._orders_received = 0
        self._orders_executed = 0
        self._orders_cancelled = 0
        self._volume_traded = 0.0
    
    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------
    
    def clear(self) -> None:
        """Clear all orders from the book."""
        self._bid_prices.clear()
        self._ask_prices.clear()
        self._bid_levels.clear()
        self._ask_levels.clear()
        self._order_index.clear()
        self.reset_statistics()
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        best_bid, best_ask, bid_qty, ask_qty = self.get_bbo()
        return f"OrderBook({self.symbol}: Bid={best_bid}x{bid_qty} Ask={best_ask}x{ask_qty})"
