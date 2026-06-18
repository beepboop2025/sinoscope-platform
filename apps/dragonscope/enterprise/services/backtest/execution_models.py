"""
Execution Models - Realistic order execution simulation for backtesting.

Provides various execution models that simulate how orders are filled in real markets,
including slippage, partial fills, and latency effects.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Tuple

import numpy as np

from .market_impact import MarketImpactModel


class OrderSide(Enum):
    BUY = 1
    SELL = -1


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(Enum):
    PENDING = "pending"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class MarketEvent:
    """Market data event for execution modeling."""
    timestamp: "Timestamp"
    symbol: str
    event_type: str
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: float = 0.0
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    
    @property
    def mid_price(self) -> float:
        if self.bid_price is not None and self.ask_price is not None:
            return (self.bid_price + self.ask_price) / 2
        return self.close_price or 0.0
    
    @property
    def spread(self) -> float:
        if self.bid_price is not None and self.ask_price is not None:
            return self.ask_price - self.bid_price
        return 0.0


@dataclass(frozen=True, order=True)
class Timestamp:
    """High-precision timestamp."""
    seconds: int
    nanoseconds: int = 0
    
    def to_datetime(self):
        from datetime import datetime
        return datetime.fromtimestamp(self.seconds + self.nanoseconds / 1e9)


@dataclass
class Order:
    """Order representation."""
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    timestamp: Timestamp
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING


@dataclass
class Fill:
    """Trade fill result."""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    fill_price: float
    timestamp: Timestamp
    commission: float = 0.0
    slippage: float = 0.0
    market_impact: float = 0.0
    venue: Optional[str] = None


class BaseExecutionModel(ABC):
    """
    Abstract base class for order execution models.
    
    Execution models determine how orders are filled given market conditions,
    including slippage, partial fills, and price impact.
    """
    
    def __init__(
        self,
        slippage_bps: float = 0.0,
        fill_probability: float = 0.99,
        partial_fill_enabled: bool = True,
        latency_ms: float = 0.0,
    ):
        """
        Initialize execution model.
        
        Args:
            slippage_bps: Slippage in basis points (1 bps = 0.01%)
            fill_probability: Probability of order being filled (0-1)
            partial_fill_enabled: Whether partial fills are allowed
            latency_ms: Simulated latency in milliseconds
        """
        self.slippage_bps = slippage_bps
        self.fill_probability = fill_probability
        self.partial_fill_enabled = partial_fill_enabled
        self.latency_ms = latency_ms
        self._random = random.Random()
    
    @abstractmethod
    def execute(
        self,
        order: Order,
        market_event: MarketEvent,
        impact_model: Optional[MarketImpactModel] = None,
    ) -> Optional[Fill]:
        """
        Execute an order against market data.
        
        Args:
            order: Order to execute
            market_event: Current market data
            impact_model: Optional market impact model for price adjustment
            
        Returns:
            Fill object if order is filled, None otherwise
        """
        pass
    
    def _calculate_slippage(self, base_price: float, side: OrderSide) -> float:
        """Calculate price adjustment due to slippage."""
        slippage_factor = self.slippage_bps / 10_000
        # Slippage is adverse to the trader
        if side == OrderSide.BUY:
            return base_price * (1 + slippage_factor)
        else:
            return base_price * (1 - slippage_factor)
    
    def _should_fill(self) -> bool:
        """Determine if order should be filled based on probability."""
        return self._random.random() < self.fill_probability
    
    def _apply_market_impact(
        self,
        price: float,
        quantity: float,
        side: OrderSide,
        impact_model: Optional[MarketImpactModel],
    ) -> Tuple[float, float]:
        """
        Apply market impact to price.
        
        Returns:
            Tuple of (adjusted_price, impact_amount)
        """
        if impact_model is None:
            return price, 0.0
        
        impact_bps = impact_model.calculate_impact(quantity, side)
        impact_factor = impact_bps / 10_000
        
        # Impact moves price against the trader
        if side == OrderSide.BUY:
            adjusted_price = price * (1 + impact_factor)
        else:
            adjusted_price = price * (1 - impact_factor)
        
        return adjusted_price, impact_bps


class MarketOrderModel(BaseExecutionModel):
    """
    Market order execution model.
    
    Market orders are filled immediately at the current market price
    plus slippage and market impact. By convention, market orders
    fill at the worst side of the spread (ask for buys, bid for sells).
    """
    
    def __init__(
        self,
        slippage_bps: float = 1.0,
        fill_probability: float = 0.999,
        partial_fill_enabled: bool = False,
        use_worse_side: bool = True,
    ):
        """
        Initialize market order model.
        
        Args:
            slippage_bps: Slippage in basis points
            fill_probability: Probability of immediate fill
            partial_fill_enabled: Whether partial fills allowed
            use_worse_side: Fill at ask (buy) or bid (sell) if available
        """
        super().__init__(slippage_bps, fill_probability, partial_fill_enabled)
        self.use_worse_side = use_worse_side
    
    def execute(
        self,
        order: Order,
        market_event: MarketEvent,
        impact_model: Optional[MarketImpactModel] = None,
    ) -> Optional[Fill]:
        """Execute market order."""
        if not self._should_fill():
            return None
        
        # Determine base price
        if self.use_worse_side and market_event.ask_price and market_event.bid_price:
            if order.side == OrderSide.BUY:
                base_price = market_event.ask_price
            else:
                base_price = market_event.bid_price
        else:
            base_price = market_event.close_price or market_event.mid_price
        
        if base_price <= 0:
            return None
        
        # Apply slippage
        price_with_slippage = self._calculate_slippage(base_price, order.side)
        
        # Apply market impact
        final_price, impact = self._apply_market_impact(
            price_with_slippage,
            order.quantity,
            order.side,
            impact_model,
        )
        
        # Calculate actual slippage component
        slippage = (final_price - base_price) / base_price * 10_000  # bps
        
        return Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=final_price,
            timestamp=market_event.timestamp,
            slippage=slippage,
            market_impact=impact,
        )


class LimitOrderModel(BaseExecutionModel):
    """
    Limit order execution model.
    
    Limit orders fill when the market price reaches or crosses the limit price.
    Supports time-based queue position simulation and partial fills.
    """
    
    def __init__(
        self,
        slippage_bps: float = 0.0,
        fill_at_touch: bool = True,
        queue_position_model: str = "time",
        partial_fill_enabled: bool = True,
        fill_probability_at_level: float = 0.8,
    ):
        """
        Initialize limit order model.
        
        Args:
            slippage_bps: Slippage in basis points (usually 0 for limits)
            fill_at_touch: Fill when price equals limit (True) or crosses it
            queue_position_model: "time" for time priority simulation
            partial_fill_enabled: Allow partial fills
            fill_probability_at_level: Probability of fill when price at limit
        """
        super().__init__(slippage_bps, 1.0, partial_fill_enabled)
        self.fill_at_touch = fill_at_touch
        self.queue_position_model = queue_position_model
        self.fill_probability_at_level = fill_probability_at_level
        self._order_queue: dict = {}  # Track queue positions
    
    def execute(
        self,
        order: Order,
        market_event: MarketEvent,
        impact_model: Optional[MarketImpactModel] = None,
    ) -> Optional[Fill]:
        """Execute limit order."""
        if order.limit_price is None:
            return None
        
        limit_price = order.limit_price
        
        # Check if limit price is touched/crossed
        if order.side == OrderSide.BUY:
            # Buy limit: fill when price <= limit
            if market_event.low_price is None:
                return None
            
            if self.fill_at_touch:
                price_triggered = market_event.low_price <= limit_price
                fill_price = min(limit_price, market_event.close_price or limit_price)
            else:
                price_triggered = market_event.low_price < limit_price
                fill_price = limit_price
        else:
            # Sell limit: fill when price >= limit
            if market_event.high_price is None:
                return None
            
            if self.fill_at_touch:
                price_triggered = market_event.high_price >= limit_price
                fill_price = max(limit_price, market_event.close_price or limit_price)
            else:
                price_triggered = market_event.high_price > limit_price
                fill_price = limit_price
        
        if not price_triggered:
            return None
        
        # Simulate queue position - earlier orders have higher fill probability
        queue_prob = self._calculate_queue_probability(order)
        if self._random.random() > queue_prob * self.fill_probability_at_level:
            return None
        
        # Determine fill quantity
        fill_quantity = order.remaining_quantity
        if self.partial_fill_enabled:
            # Simulate partial fill based on available liquidity
            available_volume = market_event.volume * 0.1  # Assume 10% available to this order
            fill_quantity = min(fill_quantity, available_volume)
            fill_quantity = max(fill_quantity, 0)  # Ensure non-negative
        
        if fill_quantity <= 0:
            return None
        
        return Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=fill_quantity,
            fill_price=fill_price,
            timestamp=market_event.timestamp,
        )
    
    def _calculate_queue_probability(self, order: Order) -> float:
        """Calculate fill probability based on queue position."""
        if self.queue_position_model == "time":
            # Simple time-based priority - newer orders have lower probability
            # In reality, this would track actual queue depth
            return 0.5 + 0.5 * self._random.random()
        return 1.0


class StopOrderModel(BaseExecutionModel):
    """
    Stop order execution model.
    
    Stop orders become market orders when the stop price is triggered.
    Includes additional slippage for stop orders due to momentum.
    """
    
    def __init__(
        self,
        slippage_bps: float = 2.0,
        slippage_on_trigger: float = 5.0,
        trigger_type: str = "trade",
        fill_probability: float = 0.95,
    ):
        """
        Initialize stop order model.
        
        Args:
            slippage_bps: Base slippage in basis points
            slippage_on_trigger: Additional slippage when stop triggers (bps)
            trigger_type: "trade" or "quote" based triggering
            fill_probability: Probability of fill after trigger
        """
        super().__init__(slippage_bps, fill_probability, False)
        self.slippage_on_trigger = slippage_on_trigger
        self.trigger_type = trigger_type
    
    def execute(
        self,
        order: Order,
        market_event: MarketEvent,
        impact_model: Optional[MarketImpactModel] = None,
    ) -> Optional[Fill]:
        """Execute stop order."""
        if order.stop_price is None:
            return None
        
        stop_price = order.stop_price
        
        # Check if stop is triggered
        if order.side == OrderSide.BUY:
            # Buy stop: trigger when price >= stop
            if market_event.high_price is None:
                return None
            triggered = market_event.high_price >= stop_price
            base_price = max(stop_price, market_event.close_price or stop_price)
        else:
            # Sell stop: trigger when price <= stop
            if market_event.low_price is None:
                return None
            triggered = market_event.low_price <= stop_price
            base_price = min(stop_price, market_event.close_price or stop_price)
        
        if not triggered:
            return None
        
        if not self._should_fill():
            return None
        
        # Apply enhanced slippage for stop orders
        total_slippage = self.slippage_bps + self.slippage_on_trigger
        slippage_factor = total_slippage / 10_000
        
        if order.side == OrderSide.BUY:
            fill_price = base_price * (1 + slippage_factor)
        else:
            fill_price = base_price * (1 - slippage_factor)
        
        # Apply market impact
        final_price, impact = self._apply_market_impact(
            fill_price,
            order.quantity,
            order.side,
            impact_model,
        )
        
        return Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=final_price,
            timestamp=market_event.timestamp,
            slippage=total_slippage + impact,
        )


class StopLimitOrderModel(BaseExecutionModel):
    """
    Stop-limit order execution model.
    
    Stop-limit orders become limit orders when the stop price is triggered.
    Combines stop triggering with limit execution logic.
    """
    
    def __init__(
        self,
        slippage_bps: float = 0.0,
        fill_at_touch: bool = True,
        trigger_type: str = "trade",
    ):
        super().__init__(slippage_bps, 1.0, True)
        self.fill_at_touch = fill_at_touch
        self.trigger_type = trigger_type
        self._triggered_stops: set = set()
    
    def execute(
        self,
        order: Order,
        market_event: MarketEvent,
        impact_model: Optional[MarketImpactModel] = None,
    ) -> Optional[Fill]:
        """Execute stop-limit order."""
        if order.stop_price is None or order.limit_price is None:
            return None
        
        # Check if already triggered
        if order.id not in self._triggered_stops:
            # Check trigger condition
            if order.side == OrderSide.BUY:
                triggered = (market_event.high_price or 0) >= order.stop_price
            else:
                triggered = (market_event.low_price or float('inf')) <= order.stop_price
            
            if not triggered:
                return None
            
            self._triggered_stops.add(order.id)
        
        # Now act as a limit order
        limit_price = order.limit_price
        
        if order.side == OrderSide.BUY:
            if self.fill_at_touch:
                price_triggered = (market_event.low_price or float('inf')) <= limit_price
                fill_price = min(limit_price, market_event.close_price or limit_price)
            else:
                price_triggered = (market_event.low_price or float('inf')) < limit_price
                fill_price = limit_price
        else:
            if self.fill_at_touch:
                price_triggered = (market_event.high_price or 0) >= limit_price
                fill_price = max(limit_price, market_event.close_price or limit_price)
            else:
                price_triggered = (market_event.high_price or 0) > limit_price
                fill_price = limit_price
        
        if not price_triggered:
            return None
        
        return Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.remaining_quantity,
            fill_price=fill_price,
            timestamp=market_event.timestamp,
        )


class SmartOrderRouterModel(BaseExecutionModel):
    """
    Smart Order Router (SOR) execution model.
    
    Simulates execution across multiple venues with intelligent routing
    based on price improvement, liquidity, and venue priority.
    """
    
    def __init__(
        self,
        venues: list = None,
        routing_strategy: str = "price_improvement",
        venue_priority: Optional[dict] = None,
        slippage_bps: float = 0.5,
        partial_fill_enabled: bool = True,
    ):
        """
        Initialize SOR model.
        
        Args:
            venues: List of venue names (e.g., ["NYSE", "NASDAQ", "IEX"])
            routing_strategy: "price_improvement", "liquidity", or "priority"
            venue_priority: Dict mapping venue to priority weight (0-1)
            slippage_bps: Base slippage in basis points
            partial_fill_enabled: Allow partial fills
        """
        super().__init__(slippage_bps, 0.99, partial_fill_enabled)
        self.venues = venues or ["NYSE", "NASDAQ"]
        self.routing_strategy = routing_strategy
        self.venue_priority = venue_priority or {v: 1.0 / len(self.venues) for v in self.venues}
        self._random = random.Random()
    
    def execute(
        self,
        order: Order,
        market_event: MarketEvent,
        impact_model: Optional[MarketImpactModel] = None,
    ) -> Optional[Fill]:
        """Execute order with smart routing."""
        if not self._should_fill():
            return None
        
        # Select venue based on routing strategy
        venue = self._select_venue()
        
        # Calculate venue-specific slippage
        venue_adjustment = self._venue_slippage_adjustment(venue)
        effective_slippage = self.slippage_bps + venue_adjustment
        
        # Determine base price
        base_price = market_event.close_price or market_event.mid_price
        
        # Apply slippage
        slippage_factor = effective_slippage / 10_000
        if order.side == OrderSide.BUY:
            fill_price = base_price * (1 + slippage_factor)
        else:
            fill_price = base_price * (1 - slippage_factor)
        
        # Apply market impact
        final_price, impact = self._apply_market_impact(
            fill_price,
            order.quantity,
            order.side,
            impact_model,
        )
        
        # Determine fill quantity
        fill_quantity = order.remaining_quantity
        if self.partial_fill_enabled:
            # Simulate venue liquidity
            fill_quantity = self._calculate_venue_fill_quantity(
                venue, order.remaining_quantity, market_event.volume
            )
        
        return Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=fill_quantity,
            fill_price=final_price,
            timestamp=market_event.timestamp,
            slippage=effective_slippage,
            market_impact=impact,
            venue=venue,
        )
    
    def _select_venue(self) -> str:
        """Select execution venue based on routing strategy."""
        if self.routing_strategy == "priority":
            # Weighted random selection based on venue priority
            venues = list(self.venue_priority.keys())
            weights = list(self.venue_priority.values())
            return self._random.choices(venues, weights=weights)[0]
        
        elif self.routing_strategy == "price_improvement":
            # Simulate venue with best price (random for backtest)
            return self._random.choice(self.venues)
        
        else:  # liquidity
            # Select most liquid venue
            return max(self.venue_priority.items(), key=lambda x: x[1])[0]
    
    def _venue_slippage_adjustment(self, venue: str) -> float:
        """Get venue-specific slippage adjustment."""
        # Simulate different slippage characteristics per venue
        venue_adjustments = {
            "IEX": -0.2,  # Slightly better
            "NASDAQ": 0.0,
            "NYSE": 0.1,
            "BATS": -0.1,
        }
        return venue_adjustments.get(venue, 0.0)
    
    def _calculate_venue_fill_quantity(
        self,
        venue: str,
        order_qty: float,
        market_volume: float,
    ) -> float:
        """Calculate fill quantity based on venue liquidity."""
        # Simulate venue market share
        venue_share = self.venue_priority.get(venue, 0.3)
        available_liquidity = market_volume * venue_share * 0.2
        return min(order_qty, available_liquidity)


class VWAPExecutionModel(BaseExecutionModel):
    """
    VWAP (Volume-Weighted Average Price) execution model.
    
    Simulates execution over time to track VWAP, with volume participation
    constraints and optimal scheduling.
    """
    
    def __init__(
        self,
        target_vwap: bool = True,
        max_participation_rate: float = 0.1,
        slippage_bps: float = 1.0,
        urgency: str = "normal",
    ):
        """
        Initialize VWAP execution model.
        
        Args:
            target_vwap: Whether to target VWAP price
            max_participation_rate: Max % of volume to participate in
            slippage_bps: Expected slippage from VWAP
            urgency: "low", "normal", "high" - affects execution speed
        """
        super().__init__(slippage_bps, 0.95, True)
        self.target_vwap = target_vwap
        self.max_participation_rate = max_participation_rate
        self.urgency = urgency
        self._scheduled_orders: dict = {}
    
    def execute(
        self,
        order: Order,
        market_event: MarketEvent,
        impact_model: Optional[MarketImpactModel] = None,
    ) -> Optional[Fill]:
        """Execute order with VWAP scheduling."""
        if order.id not in self._scheduled_orders:
            # Initialize scheduling for new order
            self._scheduled_orders[order.id] = {
                "remaining": order.quantity,
                "schedule": self._create_schedule(order.quantity),
            }
        
        schedule = self._scheduled_orders[order.id]
        
        # Calculate fill for this bar based on schedule and available volume
        available_participation = market_event.volume * self.max_participation_rate
        scheduled_qty = schedule["schedule"].pop(0) if schedule["schedule"] else 0
        
        fill_quantity = min(
            scheduled_qty,
            available_participation,
            schedule["remaining"],
        )
        
        if fill_quantity <= 0:
            return None
        
        schedule["remaining"] -= fill_quantity
        
        # Calculate fill price
        if self.target_vwap:
            # Use bar VWAP (approximated as typical price)
            typical_price = (
                (market_event.high_price or market_event.close_price) +
                (market_event.low_price or market_event.close_price) +
                (market_event.close_price or 0)
            ) / 3
        else:
            typical_price = market_event.close_price
        
        # Apply slippage
        slippage_factor = self.slippage_bps / 10_000
        if order.side == OrderSide.BUY:
            fill_price = typical_price * (1 + slippage_factor)
        else:
            fill_price = typical_price * (1 - slippage_factor)
        
        return Fill(
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            quantity=fill_quantity,
            fill_price=fill_price,
            timestamp=market_event.timestamp,
        )
    
    def _create_schedule(self, total_quantity: float) -> list:
        """Create execution schedule based on urgency."""
        # Simplified schedule - in practice would use historical volume profile
        urgency_periods = {
            "low": 20,
            "normal": 10,
            "high": 5,
        }
        
        periods = urgency_periods.get(self.urgency, 10)
        base_qty = total_quantity / periods
        
        # Add some randomization to simulate real volume distribution
        schedule = []
        for _ in range(periods):
            variation = self._random.uniform(0.5, 1.5)
            schedule.append(base_qty * variation)
        
        # Normalize to ensure total quantity
        total_scheduled = sum(schedule)
        schedule = [q / total_scheduled * total_quantity for q in schedule]
        
        return schedule
