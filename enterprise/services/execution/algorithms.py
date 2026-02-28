"""
DragonScope Enterprise - Execution Algorithms

Institutional-grade execution algorithms for minimizing market impact
and optimizing trade performance.

Implemented Algorithms:
- TWAP: Time-Weighted Average Price
- VWAP: Volume-Weighted Average Price
- PoV: Percentage of Volume
- Arrival Price: Implementation Shortfall
- Adaptive Shortfall: Dynamic risk-adjusted execution
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Tuple
from collections import deque
import numpy as np


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS & DATA CLASSES
# ============================================================================

class AlgoStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class UrgencyLevel(Enum):
    PASSIVE = 0.1    # Very low urgency, minimize impact
    LOW = 0.25
    MEDIUM = 0.5
    HIGH = 0.75
    AGGRESSIVE = 1.0  # High urgency, prioritize completion


@dataclass
class MarketData:
    """Current market data snapshot."""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    last_price: float
    last_size: float
    volume: float
    vwap: float
    open: float
    high: float
    low: float
    close: float
    bid_size: float = 0.0
    ask_size: float = 0.0


@dataclass
class Slice:
    """Represents a child order slice."""
    id: str
    sequence: int
    target_quantity: float
    target_time: datetime
    min_quantity: Optional[float] = None
    max_quantity: Optional[float] = None
    order_type: str = "market"
    limit_price: Optional[float] = None
    status: str = "pending"
    executed_quantity: float = 0.0
    executed_price: float = 0.0
    
    @property
    def remaining_quantity(self) -> float:
        return self.target_quantity - self.executed_quantity


@dataclass
class AlgoMetrics:
    """Execution algorithm performance metrics."""
    algorithm: str
    symbol: str
    side: str
    target_quantity: float
    executed_quantity: float = 0.0
    average_price: float = 0.0
    vwap_benchmark: float = 0.0
    twap_benchmark: float = 0.0
    arrival_price: float = 0.0
    implementation_shortfall: float = 0.0
    slippage_bps: float = 0.0
    market_impact_bps: float = 0.0
    participation_rate: float = 0.0
    duration_seconds: float = 0.0
    num_slices: int = 0
    completion_percentage: float = 0.0
    
    @property
    def remaining_quantity(self) -> float:
        return self.target_quantity - self.executed_quantity
    
    @property
    def is_complete(self) -> bool:
        return self.executed_quantity >= self.target_quantity


@dataclass
class VolumeProfile:
    """Historical volume profile for VWAP calculation."""
    intervals: List[datetime] = field(default_factory=list)
    volumes: List[float] = field(default_factory=list)
    cumulative_pct: List[float] = field(default_factory=list)
    
    def get_expected_volume_pct(self, time_of_day: datetime) -> float:
        """Get expected volume percentage for a given time."""
        if not self.intervals:
            return 1.0 / 390  # Assume 1/390th for each minute (trading day)
        
        # Find the interval
        for i, interval in enumerate(self.intervals):
            if time_of_day.time() <= interval.time():
                return self.cumulative_pct[i] if i < len(self.cumulative_pct) else 0.0
        
        return self.cumulative_pct[-1] if self.cumulative_pct else 0.0


# ============================================================================
# BASE EXECUTION ALGORITHM
# ============================================================================

class BaseExecutionAlgo(ABC):
    """
    Abstract base class for execution algorithms.
    
    Provides common functionality for:
    - Slice generation and management
    - Fill processing
    - Metrics calculation
    - Event callbacks
    """
    
    def __init__(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
        total_quantity: float,
        duration: timedelta,
        order_callback: Optional[Callable] = None,
        market_data_callback: Optional[Callable] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.symbol = symbol.upper()
        self.side = side.lower()
        self.total_quantity = total_quantity
        self.remaining_quantity = total_quantity
        self.duration = duration
        self.order_callback = order_callback
        self.market_data_callback = market_data_callback
        self.config = config or {}
        
        # State
        self.status = AlgoStatus.IDLE
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.slices: List[Slice] = []
        self.current_slice_index = 0
        self.fills: List[Dict[str, Any]] = []
        
        # Market data
        self.market_data: Optional[MarketData] = None
        self.arrival_price: Optional[float] = None
        self.volume_profile: Optional[VolumeProfile] = None
        
        # Metrics
        self.metrics = AlgoMetrics(
            algorithm=self.__class__.__name__,
            symbol=self.symbol,
            side=self.side,
            target_quantity=total_quantity
        )
        
        # Execution tracking
        self.total_executed = 0.0
        self.vwap_sum = 0.0  # For calculating execution VWAP
        self.price_history: deque = deque(maxlen=100)
        self.volume_history: deque = deque(maxlen=100)
        
        # Event subscribers
        self.on_fill_callbacks: List[Callable] = []
        self.on_complete_callbacks: List[Callable] = []
        self.on_error_callbacks: List[Callable] = []
        
        # Async control
        self._task: Optional[asyncio.Task] = None
        self._cancel_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially
    
    # ====================================================================
    # ABSTRACT METHODS
    # ====================================================================
    
    @abstractmethod
    def generate_slices(self) -> List[Slice]:
        """Generate order slices according to algorithm schedule."""
        pass
    
    @abstractmethod
    def calculate_slice_quantity(self, slice_obj: Slice, market_data: MarketData) -> float:
        """Calculate quantity for the current slice based on market conditions."""
        pass
    
    @abstractmethod
    def get_target_price(self, slice_obj: Slice, market_data: MarketData) -> Optional[float]:
        """Get target price for a slice (for limit orders)."""
        pass
    
    # ====================================================================
    # LIFECYCLE METHODS
    # ====================================================================
    
    async def execute(self) -> AlgoMetrics:
        """
        Execute the algorithm.
        
        Returns:
            AlgoMetrics with execution results
        """
        if self.status == AlgoStatus.RUNNING:
            raise RuntimeError("Algorithm already running")
        
        self.status = AlgoStatus.RUNNING
        self.start_time = datetime.utcnow()
        self.end_time = self.start_time + self.duration
        
        # Capture arrival price
        if self.market_data:
            self.arrival_price = self.market_data.last_price
            self.metrics.arrival_price = self.arrival_price
        
        # Generate slices
        self.slices = self.generate_slices()
        self.metrics.num_slices = len(self.slices)
        
        logger.info(f"Starting {self.__class__.__name__} for {self.symbol}: "
                   f"{self.total_quantity} shares over {self.duration}")
        
        try:
            await self._execution_loop()
        except asyncio.CancelledError:
            self.status = AlgoStatus.CANCELLED
            logger.info(f"Algorithm cancelled for {self.symbol}")
        except Exception as e:
            self.status = AlgoStatus.ERROR
            logger.error(f"Algorithm error: {e}")
            await self._notify_error(e)
        
        # Calculate final metrics
        self._update_metrics()
        
        if self.status == AlgoStatus.RUNNING:
            self.status = AlgoStatus.COMPLETED
            await self._notify_complete()
        
        return self.metrics
    
    async def _execution_loop(self):
        """Main execution loop."""
        for i, slice_obj in enumerate(self.slices):
            if self._cancel_event.is_set():
                break
            
            # Wait if paused
            await self._pause_event.wait()
            
            self.current_slice_index = i
            
            # Wait until slice target time
            now = datetime.utcnow()
            if slice_obj.target_time > now:
                wait_seconds = (slice_obj.target_time - now).total_seconds()
                try:
                    await asyncio.wait_for(
                        self._cancel_event.wait(),
                        timeout=wait_seconds
                    )
                    if self._cancel_event.is_set():
                        break
                except asyncio.TimeoutError:
                    pass
            
            # Execute slice
            await self._execute_slice(slice_obj)
            
            # Check if complete
            if self.remaining_quantity <= 0:
                break
    
    async def _execute_slice(self, slice_obj: Slice):
        """Execute a single slice."""
        if not self.market_data:
            logger.warning("No market data available, skipping slice")
            return
        
        # Calculate slice quantity
        quantity = self.calculate_slice_quantity(slice_obj, self.market_data)
        quantity = min(quantity, self.remaining_quantity)
        
        if quantity <= 0:
            return
        
        # Get target price
        limit_price = self.get_target_price(slice_obj, self.market_data)
        
        # Build order
        order = {
            "slice_id": slice_obj.id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": quantity,
            "order_type": "limit" if limit_price else "market",
            "limit_price": limit_price,
            "timestamp": datetime.utcnow()
        }
        
        slice_obj.status = "executing"
        
        # Send order via callback
        if self.order_callback:
            try:
                if asyncio.iscoroutinefunction(self.order_callback):
                    await self.order_callback(order)
                else:
                    self.order_callback(order)
            except Exception as e:
                logger.error(f"Order callback error: {e}")
        
        logger.debug(f"Executed slice {slice_obj.sequence}: {quantity} @ {limit_price}")
    
    # ====================================================================
    # FILL PROCESSING
    # ====================================================================
    
    def process_fill(self, fill_quantity: float, fill_price: float, timestamp: Optional[datetime] = None):
        """Process a fill notification."""
        timestamp = timestamp or datetime.utcnow()
        
        self.fills.append({
            "quantity": fill_quantity,
            "price": fill_price,
            "timestamp": timestamp
        })
        
        self.total_executed += fill_quantity
        self.remaining_quantity -= fill_quantity
        self.vwap_sum += fill_quantity * fill_price
        
        # Update current slice
        if self.current_slice_index < len(self.slices):
            slice_obj = self.slices[self.current_slice_index]
            slice_obj.executed_quantity += fill_quantity
            slice_obj.executed_price = fill_price
        
        # Update metrics
        self._update_metrics()
        
        # Notify subscribers
        asyncio.create_task(self._notify_fill(fill_quantity, fill_price))
        
        logger.info(f"Fill: {fill_quantity} @ {fill_price} "
                   f"(Total: {self.total_executed}/{self.total_quantity})")
    
    def _update_metrics(self):
        """Update algorithm metrics."""
        self.metrics.executed_quantity = self.total_executed
        
        if self.total_executed > 0:
            self.metrics.average_price = self.vwap_sum / self.total_executed
        
        self.metrics.completion_percentage = (self.total_executed / self.total_quantity) * 100
        
        if self.start_time:
            self.metrics.duration_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        
        # Calculate implementation shortfall
        if self.arrival_price and self.metrics.average_price:
            if self.side == "buy":
                self.metrics.implementation_shortfall = self.metrics.average_price - self.arrival_price
            else:
                self.metrics.implementation_shortfall = self.arrival_price - self.metrics.average_price
            
            self.metrics.slippage_bps = (self.metrics.implementation_shortfall / self.arrival_price) * 10000
    
    # ====================================================================
    # CONTROL METHODS
    # ====================================================================
    
    def pause(self):
        """Pause algorithm execution."""
        if self.status == AlgoStatus.RUNNING:
            self.status = AlgoStatus.PAUSED
            self._pause_event.clear()
            logger.info(f"Algorithm paused for {self.symbol}")
    
    def resume(self):
        """Resume algorithm execution."""
        if self.status == AlgoStatus.PAUSED:
            self.status = AlgoStatus.RUNNING
            self._pause_event.set()
            logger.info(f"Algorithm resumed for {self.symbol}")
    
    def cancel(self):
        """Cancel algorithm execution."""
        self._cancel_event.set()
        self.status = AlgoStatus.CANCELLED
        logger.info(f"Algorithm cancelled for {self.symbol}")
    
    def update_market_data(self, market_data: MarketData):
        """Update current market data."""
        self.market_data = market_data
        self.price_history.append(market_data.last_price)
        self.volume_history.append(market_data.volume)
    
    # ====================================================================
    # EVENT SUBSCRIPTION
    # ====================================================================
    
    def on_fill(self, callback: Callable):
        """Register fill callback."""
        self.on_fill_callbacks.append(callback)
    
    def on_complete(self, callback: Callable):
        """Register completion callback."""
        self.on_complete_callbacks.append(callback)
    
    def on_error(self, callback: Callable):
        """Register error callback."""
        self.on_error_callbacks.append(callback)
    
    async def _notify_fill(self, quantity: float, price: float):
        """Notify fill subscribers."""
        for callback in self.on_fill_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(quantity, price, self.metrics)
                else:
                    callback(quantity, price, self.metrics)
            except Exception as e:
                logger.error(f"Fill callback error: {e}")
    
    async def _notify_complete(self):
        """Notify completion subscribers."""
        for callback in self.on_complete_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self.metrics)
                else:
                    callback(self.metrics)
            except Exception as e:
                logger.error(f"Complete callback error: {e}")
    
    async def _notify_error(self, error: Exception):
        """Notify error subscribers."""
        for callback in self.on_error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error)
                else:
                    callback(error)
            except Exception as e:
                logger.error(f"Error callback error: {e}")


# ============================================================================
# TWAP ALGORITHM
# ============================================================================

class TWAPAlgo(BaseExecutionAlgo):
    """
    Time-Weighted Average Price Algorithm.
    
    Distributes order evenly over the specified duration.
    Minimizes timing risk by spreading execution across time intervals.
    
    Parameters:
    - num_slices: Number of time slices (default: auto-calculated)
    - slice_interval: Seconds between slices (default: 60)
    - randomize: Add slight randomization to slice times (default: True)
    - max_participation: Max participation rate (default: 0.25)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slice_interval = self.config.get("slice_interval", 60)
        self.randomize = self.config.get("randomize", True)
        self.max_participation = self.config.get("max_participation", 0.25)
        
        # Calculate number of slices
        total_seconds = self.duration.total_seconds()
        self.num_slices = int(total_seconds / self.slice_interval)
        if self.num_slices < 1:
            self.num_slices = 1
    
    def generate_slices(self) -> List[Slice]:
        """Generate evenly spaced time slices."""
        slices = []
        interval_seconds = self.duration.total_seconds() / self.num_slices
        
        for i in range(self.num_slices):
            # Base time
            target_time = self.start_time + timedelta(seconds=interval_seconds * i)
            
            # Add slight randomization if enabled
            if self.randomize and i > 0:
                jitter = np.random.uniform(-0.1, 0.1) * interval_seconds
                target_time += timedelta(seconds=jitter)
            
            # Calculate quantity for this slice
            remaining_slices = self.num_slices - i
            target_qty = self.remaining_quantity / remaining_slices
            
            slice_obj = Slice(
                id=f"{self.symbol}_twap_{i}",
                sequence=i,
                target_quantity=target_qty,
                target_time=target_time,
                order_type="market"
            )
            slices.append(slice_obj)
        
        return slices
    
    def calculate_slice_quantity(self, slice_obj: Slice, market_data: MarketData) -> float:
        """Calculate TWAP slice quantity."""
        return min(slice_obj.target_quantity, self.remaining_quantity)
    
    def get_target_price(self, slice_obj: Slice, market_data: MarketData) -> Optional[float]:
        """TWAP typically uses market orders, but can use limits."""
        use_limit = self.config.get("use_limit", False)
        if not use_limit:
            return None
        
        # Place limit at bid/ask depending on side
        if self.side == "buy":
            return market_data.bid
        else:
            return market_data.ask


# ============================================================================
# VWAP ALGORITHM
# ============================================================================

class VWAPAlgo(BaseExecutionAlgo):
    """
    Volume-Weighted Average Price Algorithm.
    
    Executes based on historical volume profile to match expected
    market volume distribution.
    
    Parameters:
    - volume_profile: Historical volume profile
    - participation_rate: Target participation rate (default: 0.10)
    - adaptive: Adjust based on real-time volume (default: True)
    - min_slice_interval: Minimum seconds between slices (default: 60)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.participation_rate = self.config.get("participation_rate", 0.10)
        self.adaptive = self.config.get("adaptive", True)
        self.min_slice_interval = self.config.get("min_slice_interval", 60)
        
        # Load or create volume profile
        self.volume_profile = self.config.get("volume_profile")
        if not self.volume_profile:
            self.volume_profile = self._create_default_volume_profile()
    
    def _create_default_volume_profile(self) -> VolumeProfile:
        """Create default volume profile (U-shaped curve)."""
        # Simplified U-shaped volume profile
        profile = VolumeProfile()
        
        # Assume 6.5 hour trading day (390 minutes)
        # Higher volume at open and close
        for i in range(390):
            # U-shaped distribution
            pct_through_day = i / 389
            volume_factor = 1.0 + 2.0 * (0.5 - abs(pct_through_day - 0.5))
            profile.intervals.append(datetime.min + timedelta(minutes=i))
            profile.volumes.append(volume_factor)
        
        # Normalize to percentages
        total = sum(profile.volumes)
        running_total = 0.0
        for vol in profile.volumes:
            running_total += vol
            profile.cumulative_pct.append(running_total / total)
        
        return profile
    
    def generate_slices(self) -> List[Slice]:
        """Generate volume-weighted slices."""
        slices = []
        current_time = self.start_time
        interval = timedelta(seconds=self.min_slice_interval)
        
        i = 0
        while current_time < self.end_time and self.remaining_quantity > 0:
            # Get expected volume percentage for this time
            vol_pct = self.volume_profile.get_expected_volume_pct(current_time)
            
            # Calculate slice quantity based on participation rate
            slice_qty = self.total_quantity * vol_pct * self.participation_rate
            
            # Adjust for remaining quantity
            slice_qty = min(slice_qty, self.remaining_quantity)
            
            slice_obj = Slice(
                id=f"{self.symbol}_vwap_{i}",
                sequence=i,
                target_quantity=slice_qty,
                target_time=current_time,
                order_type="market"
            )
            slices.append(slice_obj)
            
            current_time += interval
            i += 1
        
        return slices
    
    def calculate_slice_quantity(self, slice_obj: Slice, market_data: MarketData) -> float:
        """Calculate VWAP slice quantity with adaptive adjustment."""
        base_qty = slice_obj.target_quantity
        
        if self.adaptive and self.market_data:
            # Adjust based on current vs expected volume
            # Simplified: increase size if we're behind schedule
            progress_pct = self.total_executed / self.total_quantity
            time_pct = (datetime.utcnow() - self.start_time).total_seconds() / self.duration.total_seconds()
            
            if time_pct > 0 and progress_pct < time_pct:
                # Behind schedule, increase size
                adjustment = min(1.5, time_pct / max(progress_pct, 0.01))
                base_qty *= adjustment
        
        return min(base_qty, self.remaining_quantity)
    
    def get_target_price(self, slice_obj: Slice, market_data: MarketData) -> Optional[float]:
        """VWAP can use aggressive limits."""
        use_limit = self.config.get("use_limit", True)
        if not use_limit:
            return None
        
        # Place limit inside the spread for faster fills
        if self.side == "buy":
            # Buy at or near the ask
            return market_data.ask - 0.01
        else:
            # Sell at or near the bid
            return market_data.bid + 0.01


# ============================================================================
# PERCENTAGE OF VOLUME (POV) ALGORITHM
# ============================================================================

class PctVolumeAlgo(BaseExecutionAlgo):
    """
    Percentage of Volume Algorithm.
    
    Participates at a fixed percentage of market volume.
    Adapts slice sizes based on real-time volume.
    
    Parameters:
    - participation_rate: Target participation rate (default: 0.15)
    - min_participation: Minimum participation rate (default: 0.05)
    - max_participation: Maximum participation rate (default: 0.30)
    - lookback_seconds: Volume lookback window (default: 300)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.participation_rate = self.config.get("participation_rate", 0.15)
        self.min_participation = self.config.get("min_participation", 0.05)
        self.max_participation = self.config.get("max_participation", 0.30)
        self.lookback_seconds = self.config.get("lookback_seconds", 300)
        self.slice_interval = self.config.get("slice_interval", 60)
        
        # Volume tracking
        self.observed_volumes: deque = deque()
        self.last_volume = 0.0
    
    def generate_slices(self) -> List[Slice]:
        """Generate time-based slices for PoV."""
        slices = []
        interval_seconds = self.slice_interval
        num_slices = int(self.duration.total_seconds() / interval_seconds)
        
        for i in range(num_slices):
            target_time = self.start_time + timedelta(seconds=interval_seconds * i)
            
            slice_obj = Slice(
                id=f"{self.symbol}_pov_{i}",
                sequence=i,
                target_quantity=self.total_quantity / num_slices,  # Initial estimate
                target_time=target_time,
                order_type="market"
            )
            slices.append(slice_obj)
        
        return slices
    
    def calculate_slice_quantity(self, slice_obj: Slice, market_data: MarketData) -> float:
        """Calculate PoV slice based on observed volume."""
        # Calculate observed volume since last slice
        current_volume = market_data.volume
        volume_delta = current_volume - self.last_volume
        self.last_volume = current_volume
        
        # Store observed volume
        self.observed_volumes.append({
            "timestamp": datetime.utcnow(),
            "volume": volume_delta
        })
        
        # Calculate average volume over lookback
        cutoff = datetime.utcnow() - timedelta(seconds=self.lookback_seconds)
        recent_volumes = [v["volume"] for v in self.observed_volumes if v["timestamp"] > cutoff]
        
        if recent_volumes:
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            # Project volume for next interval
            projected_volume = avg_volume * (self.slice_interval / self.lookback_seconds)
            target_qty = projected_volume * self.participation_rate
        else:
            # No data yet, use proportional allocation
            remaining_time = (self.end_time - datetime.utcnow()).total_seconds()
            if remaining_time > 0:
                target_qty = self.remaining_quantity / (remaining_time / self.slice_interval)
            else:
                target_qty = self.remaining_quantity
        
        # Apply min/max participation bounds
        target_qty = max(target_qty, self.remaining_quantity * self.min_participation)
        target_qty = min(target_qty, self.remaining_quantity * self.max_participation)
        
        return min(target_qty, self.remaining_quantity)
    
    def get_target_price(self, slice_obj: Slice, market_data: MarketData) -> Optional[float]:
        """PoV typically uses market orders."""
        return None


# ============================================================================
# ARRIVAL PRICE ALGORITHM
# ============================================================================

class ArrivalPriceAlgo(BaseExecutionAlgo):
    """
    Arrival Price (Implementation Shortfall) Algorithm.
    
    Minimizes slippage from decision/arrival price.
    Balances market impact vs opportunity cost using optimal trading model.
    
    Parameters:
    - urgency: Urgency level (default: MEDIUM)
    - risk_aversion: Risk aversion coefficient (default: 1.0)
    - alpha_decay: Expected alpha decay rate (default: 0.0)
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urgency = self.config.get("urgency", UrgencyLevel.MEDIUM)
        self.risk_aversion = self.config.get("risk_aversion", 1.0)
        self.alpha_decay = self.config.get("alpha_decay", 0.0)
        
        # Market impact model parameters
        self.impact_coefficient = self.config.get("impact_coefficient", 1.0)
        self.temporary_impact_power = self.config.get("temporary_impact_power", 0.6)
        
        # Price volatility estimation
        self.volatility = self.config.get("estimated_volatility", 0.02)  # 2% daily
    
    def generate_slices(self) -> List[Slice]:
        """Generate optimally spaced slices based on risk/impact tradeoff."""
        slices = []
        
        # Use optimal trading schedule
        # Schedule follows: x(t) = X * sinh(κ(T-t)) / sinh(κT)
        # where κ depends on urgency and risk aversion
        
        kappa = self._calculate_kappa()
        T = self.duration.total_seconds()
        
        num_slices = max(10, int(T / 30))  # At least every 30 seconds
        
        for i in range(num_slices):
            t = i * (T / num_slices)
            remaining_t = T - t
            
            # Optimal trajectory
            if kappa * T > 0.01:
                remaining_pct = np.sinh(kappa * remaining_t) / np.sinh(kappa * T)
            else:
                remaining_pct = remaining_t / T
            
            target_remaining = self.total_quantity * remaining_pct
            already_targeted = sum(s.target_quantity for s in slices)
            slice_qty = (self.total_quantity - target_remaining) - already_targeted
            
            target_time = self.start_time + timedelta(seconds=t)
            
            slice_obj = Slice(
                id=f"{self.symbol}_arrival_{i}",
                sequence=i,
                target_quantity=max(0, slice_qty),
                target_time=target_time,
                order_type="limit"
            )
            slices.append(slice_obj)
        
        return slices
    
    def _calculate_kappa(self) -> float:
        """Calculate urgency parameter based on risk/impact tradeoff."""
        # κ = sqrt(λ * σ² / η)
        # where λ is risk aversion, σ is volatility, η is impact coefficient
        
        urgency_multiplier = self.urgency.value
        kappa = np.sqrt(self.risk_aversion * (self.volatility ** 2) / self.impact_coefficient)
        kappa *= urgency_multiplier
        
        return kappa
    
    def calculate_slice_quantity(self, slice_obj: Slice, market_data: MarketData) -> float:
        """Calculate slice quantity with urgency adjustment."""
        base_qty = slice_obj.target_quantity
        
        # Adjust based on current market conditions
        spread_pct = (market_data.ask - market_data.bid) / market_data.last_price
        
        # In wide spreads, be more passive
        if spread_pct > 0.001:  # > 10 bps
            base_qty *= 0.8
        
        return min(base_qty, self.remaining_quantity)
    
    def get_target_price(self, slice_obj: Slice, market_data: MarketData) -> Optional[float]:
        """Set aggressive limit price based on arrival price."""
        if not self.arrival_price:
            return None
        
        # Calculate acceptable slippage based on remaining quantity
        remaining_pct = self.remaining_quantity / self.total_quantity
        acceptable_slippage = remaining_pct * 0.001 * self.urgency.value  # 0-10 bps
        
        if self.side == "buy":
            # Don't pay more than arrival + acceptable slippage
            max_price = self.arrival_price * (1 + acceptable_slippage)
            return min(max_price, market_data.ask)
        else:
            min_price = self.arrival_price * (1 - acceptable_slippage)
            return max(min_price, market_data.bid)


# ============================================================================
# IMPLEMENTATION SHORTFALL ALGORITHM
# ============================================================================

class ImplementationShortfallAlgo(BaseExecutionAlgo):
    """
    Advanced Implementation Shortfall Algorithm.
    
    Dynamically optimizes execution to minimize total implementation cost:
    - Market impact
    - Opportunity cost (price drift)
    - Timing risk
    
    Uses real-time market conditions and fills to adjust strategy.
    
    Parameters:
    - target_is: Target implementation shortfall in bps (default: auto)
    - max_is: Maximum acceptable IS (default: 50 bps)
    - adaptive_schedule: Dynamically adjust schedule (default: True)
    - price_forecast_model: Model for price prediction (default: "drift")
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_is_bps = self.config.get("target_is_bps")
        self.max_is_bps = self.config.get("max_is_bps", 50.0)
        self.adaptive_schedule = self.config.get("adaptive_schedule", True)
        self.price_forecast_model = self.config.get("price_forecast_model", "drift")
        
        # Dynamic parameters
        self.current_participation_rate = 0.15
        self.estimated_impact_bps = 0.0
        self.price_drift_prediction = 0.0
        
        # Historical for predictions
        self.fill_prices: List[float] = []
        self.fill_times: List[datetime] = []
    
    def generate_slices(self) -> List[Slice]:
        """Generate adaptive schedule."""
        slices = []
        
        # Start with moderate pace
        initial_slices = 20
        interval = self.duration.total_seconds() / initial_slices
        
        for i in range(initial_slices):
            target_time = self.start_time + timedelta(seconds=interval * i)
            
            slice_obj = Slice(
                id=f"{self.symbol}_is_{i}",
                sequence=i,
                target_quantity=self.total_quantity / initial_slices,
                target_time=target_time,
                order_type="market"
            )
            slices.append(slice_obj)
        
        return slices
    
    def calculate_slice_quantity(self, slice_obj: Slice, market_data: MarketData) -> float:
        """Dynamically calculate slice size based on IS optimization."""
        if not self.adaptive_schedule:
            return min(slice_obj.target_quantity, self.remaining_quantity)
        
        # Update estimates based on observed fills
        self._update_estimates()
        
        # Calculate optimal pace
        remaining_time = (self.end_time - datetime.utcnow()).total_seconds()
        if remaining_time <= 0:
            return self.remaining_quantity
        
        # Estimate cost of waiting vs trading
        expected_drift_cost = abs(self.price_drift_prediction) * remaining_time / 86400
        expected_impact_cost = self._estimate_impact(self.remaining_quantity)
        
        # Trade more aggressively if drift cost > impact cost
        if expected_drift_cost > expected_impact_cost:
            # Accelerate
            urgency_factor = 1.5
        else:
            # Slow down
            urgency_factor = 0.8
        
        # Calculate target quantity
        proportional_qty = self.remaining_quantity / max(1, len(self.slices) - self.current_slice_index)
        target_qty = proportional_qty * urgency_factor
        
        # Apply participation limits
        if market_data and market_data.volume > 0:
            max_qty = market_data.volume * 0.01 * self.current_participation_rate  # Per minute
            target_qty = min(target_qty, max_qty)
        
        return min(target_qty, self.remaining_quantity)
    
    def _update_estimates(self):
        """Update cost estimates based on observed data."""
        if len(self.fill_prices) < 2:
            return
        
        # Calculate observed volatility
        returns = []
        for i in range(1, len(self.fill_prices)):
            ret = (self.fill_prices[i] - self.fill_prices[i-1]) / self.fill_prices[i-1]
            returns.append(ret)
        
        if returns:
            vol = np.std(returns) * np.sqrt(len(returns))
            # Simple price drift prediction
            self.price_drift_prediction = np.mean(returns) * vol if vol > 0 else 0
    
    def _estimate_impact(self, quantity: float) -> float:
        """Estimate market impact for a given quantity."""
        # Simplified square-root impact model
        # Impact = η * σ * sqrt(Q/V)
        if self.total_quantity > 0:
            participation = quantity / self.total_quantity
            impact_bps = 10 * np.sqrt(participation)  # Simplified
            return impact_bps / 10000
        return 0.0
    
    def get_target_price(self, slice_obj: Slice, market_data: MarketData) -> Optional[float]:
        """Set price limit based on IS budget."""
        if not self.arrival_price:
            return None
        
        # Calculate remaining IS budget
        if self.target_is_bps:
            remaining_budget_bps = self.target_is_bps - (self.metrics.slippage_bps or 0)
        else:
            remaining_budget_bps = self.max_is_bps - (self.metrics.slippage_bps or 0)
        
        # Allocate budget proportionally
        remaining_pct = self.remaining_quantity / self.total_quantity
        slice_budget_bps = remaining_budget_bps * remaining_pct
        
        # Convert to price
        price_adjustment = 1 + (slice_budget_bps / 10000)
        
        if self.side == "buy":
            max_acceptable = self.arrival_price * price_adjustment
            return min(max_acceptable, market_data.ask)
        else:
            min_acceptable = self.arrival_price / price_adjustment
            return max(min_acceptable, market_data.bid)
    
    def process_fill(self, fill_quantity: float, fill_price: float, timestamp: Optional[datetime] = None):
        """Track fills for IS calculation."""
        super().process_fill(fill_quantity, fill_price, timestamp)
        
        self.fill_prices.append(fill_price)
        self.fill_times.append(timestamp or datetime.utcnow())


# ============================================================================
# ALGORITHM FACTORY
# ============================================================================

class ExecutionAlgoFactory:
    """Factory for creating execution algorithms."""
    
    ALGORITHMS = {
        "TWAP": TWAPAlgo,
        "VWAP": VWAPAlgo,
        "POV": PctVolumeAlgo,
        "PCT_VOLUME": PctVolumeAlgo,
        "ARRIVAL_PRICE": ArrivalPriceAlgo,
        "IS": ImplementationShortfallAlgo,
        "IMPLEMENTATION_SHORTFALL": ImplementationShortfallAlgo,
    }
    
    @classmethod
    def create(
        cls,
        algo_name: str,
        symbol: str,
        side: str,
        total_quantity: float,
        duration: timedelta,
        **kwargs
    ) -> BaseExecutionAlgo:
        """
        Create an execution algorithm instance.
        
        Args:
            algo_name: Algorithm name (TWAP, VWAP, POV, etc.)
            symbol: Trading symbol
            side: "buy" or "sell"
            total_quantity: Total order quantity
            duration: Execution duration
            **kwargs: Additional algorithm-specific parameters
        
        Returns:
            BaseExecutionAlgo instance
        """
        algo_class = cls.ALGORITHMS.get(algo_name.upper())
        if not algo_class:
            raise ValueError(f"Unknown algorithm: {algo_name}. "
                           f"Available: {list(cls.ALGORITHMS.keys())}")
        
        return algo_class(
            symbol=symbol,
            side=side,
            total_quantity=total_quantity,
            duration=duration,
            **kwargs
        )
    
    @classmethod
    def list_algorithms(cls) -> List[str]:
        """List available algorithm names."""
        return list(cls.ALGORITHMS.keys())


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def example():
    """Example usage of execution algorithms."""
    
    # Create market data
    market_data = MarketData(
        symbol="AAPL",
        timestamp=datetime.utcnow(),
        bid=150.00,
        ask=150.05,
        last_price=150.02,
        last_size=100,
        volume=1000000,
        vwap=149.95,
        open=149.50,
        high=150.50,
        low=149.25,
        close=149.00
    )
    
    # Order callback
    async def on_order(order):
        print(f"Order: {order['side']} {order['quantity']} {order['symbol']}")
    
    # Create TWAP algorithm
    twap = ExecutionAlgoFactory.create(
        algo_name="TWAP",
        symbol="AAPL",
        side="buy",
        total_quantity=10000,
        duration=timedelta(hours=1),
        order_callback=on_order,
        config={"slice_interval": 300, "randomize": True}
    )
    
    # Update market data
    twap.update_market_data(market_data)
    
    # Set up callbacks
    def on_fill(qty, price, metrics):
        print(f"Fill: {qty} @ {price}, Progress: {metrics.completion_percentage:.1f}%")
    
    def on_complete(metrics):
        print(f"Completed! VWAP: {metrics.average_price:.2f}, "
              f"IS: {metrics.implementation_shortfall:.4f}")
    
    twap.on_fill(on_fill)
    twap.on_complete(on_complete)
    
    # Simulate execution (would normally run async)
    print("\n=== TWAP Example ===")
    slices = twap.generate_slices()
    print(f"Generated {len(slices)} slices")
    for i, s in enumerate(slices[:3]):
        print(f"  Slice {i}: qty={s.target_quantity:.0f}, time={s.target_time.strftime('%H:%M:%S')}")
    
    # Create VWAP algorithm
    print("\n=== VWAP Example ===")
    vwap = ExecutionAlgoFactory.create(
        algo_name="VWAP",
        symbol="AAPL",
        side="buy",
        total_quantity=10000,
        duration=timedelta(hours=1),
        config={"participation_rate": 0.10}
    )
    vwap.update_market_data(market_data)
    vwap.start_time = datetime.utcnow()
    vwap.end_time = vwap.start_time + vwap.duration
    
    vwap_slices = vwap.generate_slices()
    print(f"Generated {len(vwap_slices)} slices")
    for i, s in enumerate(vwap_slices[:3]):
        print(f"  Slice {i}: qty={s.target_quantity:.0f}, time={s.target_time.strftime('%H:%M:%S')}")


if __name__ == "__main__":
    asyncio.run(example())
