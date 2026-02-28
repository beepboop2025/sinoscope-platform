"""
BacktestEngine - Core event-driven backtesting engine for DragonScope Enterprise.

Provides high-fidelity simulation of trading strategies with realistic market microstructure.
"""

from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, Union
import uuid

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator

from .analytics import PerformanceMetrics, TradeStatistics, DrawdownAnalyzer
from .execution_models import BaseExecutionModel, MarketOrderModel
from .market_impact import MarketImpactModel, LinearImpactModel

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = auto()
    SELL = auto()


class OrderType(Enum):
    MARKET = auto()
    LIMIT = auto()
    STOP = auto()
    STOP_LIMIT = auto()
    TRAILING_STOP = auto()


class OrderStatus(Enum):
    PENDING = auto()
    PARTIAL_FILL = auto()
    FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()


class Signal(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0


@dataclass(frozen=True, order=True)
class Timestamp:
    """High-precision timestamp for event ordering."""
    seconds: int
    nanoseconds: int = 0
    
    def to_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.seconds + self.nanoseconds / 1e9)
    
    @classmethod
    def from_datetime(cls, dt: datetime) -> Timestamp:
        ts = dt.timestamp()
        seconds = int(ts)
        nanoseconds = int((ts - seconds) * 1e9)
        return cls(seconds, nanoseconds)
    
    def __add__(self, delta: timedelta) -> Timestamp:
        total_ns = self.nanoseconds + int(delta.total_seconds() * 1e9)
        add_seconds = total_ns // 1_000_000_000
        new_ns = total_ns % 1_000_000_000
        return Timestamp(self.seconds + int(delta.total_seconds()) + add_seconds, new_ns)


@dataclass
class MarketEvent:
    """Market data event (tick or bar)."""
    timestamp: Timestamp
    symbol: str
    event_type: str  # 'tick', 'bar', 'quote'
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
    
    @property
    def remaining_quantity(self) -> float:
        return self.quantity - self.filled_quantity
    
    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED


@dataclass
class Fill:
    """Trade fill event."""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    fill_price: float
    timestamp: Timestamp
    commission: float = 0.0
    slippage: float = 0.0
    market_impact: float = 0.0


@dataclass
class Position:
    """Position tracking for a symbol."""
    symbol: str
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    @property
    def market_value(self, current_price: float = 0.0) -> float:
        return self.quantity * current_price
    
    def update_on_fill(self, fill: Fill) -> None:
        """Update position based on fill."""
        if fill.side == OrderSide.BUY:
            if self.quantity >= 0:
                # Increasing long position
                total_cost = self.quantity * self.avg_entry_price + fill.quantity * fill.fill_price
                self.quantity += fill.quantity
                self.avg_entry_price = total_cost / self.quantity if self.quantity > 0 else 0
            else:
                # Covering short position
                self.realized_pnl += abs(fill.quantity) * (self.avg_entry_price - fill.fill_price)
                self.quantity += fill.quantity
                if self.quantity > 0:
                    self.avg_entry_price = fill.fill_price
        else:  # SELL
            if self.quantity <= 0:
                # Increasing short position
                total_cost = abs(self.quantity) * self.avg_entry_price + fill.quantity * fill.fill_price
                self.quantity -= fill.quantity
                self.avg_entry_price = total_cost / abs(self.quantity) if self.quantity < 0 else 0
            else:
                # Selling long position
                self.realized_pnl += fill.quantity * (fill.fill_price - self.avg_entry_price)
                self.quantity -= fill.quantity
                if self.quantity < 0:
                    self.avg_entry_price = fill.fill_price
    
    def update_unrealized_pnl(self, current_price: float) -> None:
        """Update unrealized P&L based on current price."""
        self.unrealized_pnl = self.quantity * (current_price - self.avg_entry_price)


@dataclass
class Portfolio:
    """Portfolio state tracking."""
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    fills: List[Fill] = field(default_factory=list)
    
    @property
    def total_value(self, prices: Dict[str, float]) -> float:
        position_value = sum(
            pos.quantity * prices.get(sym, 0) 
            for sym, pos in self.positions.items()
        )
        return self.cash + position_value
    
    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        return self.positions[symbol]
    
    def apply_fill(self, fill: Fill) -> None:
        """Apply fill to portfolio."""
        position = self.get_position(fill.symbol)
        
        # Update cash
        fill_cost = fill.quantity * fill.fill_price + fill.commission
        if fill.side == OrderSide.BUY:
            self.cash -= fill_cost
        else:
            self.cash += fill_cost - fill.commission
        
        # Update position
        position.update_on_fill(fill)
        self.fills.append(fill)
    
    def update_market_prices(self, prices: Dict[str, float]) -> None:
        """Update unrealized P&L based on current prices."""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].update_unrealized_pnl(price)


class Strategy(Protocol):
    """Protocol for trading strategies."""
    
    def on_bar(self, bar: MarketEvent, portfolio: Portfolio) -> Optional[Signal]:
        """Called on each bar. Returns signal or None."""
        ...
    
    def on_tick(self, tick: MarketEvent, portfolio: Portfolio) -> Optional[Signal]:
        """Called on each tick. Returns signal or None."""
        ...
    
    def on_order_fill(self, fill: Fill, portfolio: Portfolio) -> None:
        """Called when an order is filled."""
        ...


class BacktestConfig(BaseModel):
    """Configuration for backtest execution."""
    
    initial_capital: float = Field(default=1_000_000, gt=0)
    start_date: datetime
    end_date: datetime
    symbols: List[str] = Field(default_factory=list)
    data_frequency: str = Field(default="1d", regex="^(tick|1min|5min|1h|1d)$")
    commission_rate: float = Field(default=0.0, ge=0)
    min_commission: float = Field(default=0.0, ge=0)
    slippage_bps: float = Field(default=0.0, ge=0)
    execution_model: Optional[BaseExecutionModel] = None
    impact_model: Optional[MarketImpactModel] = None
    allow_short: bool = True
    margin_requirement: float = Field(default=0.5, gt=0, le=1)
    benchmark_symbol: Optional[str] = None
    
    @validator('end_date')
    def end_after_start(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    class Config:
        arbitrary_types_allowed = True


@dataclass
class BacktestResults:
    """Results container for backtest execution."""
    backtest_id: str
    config: BacktestConfig
    metrics: PerformanceMetrics
    trade_stats: TradeStatistics
    equity_curve: pd.DataFrame
    positions_history: pd.DataFrame
    fills: List[Fill]
    start_time: datetime
    end_time: datetime
    
    def summary(self) -> Dict[str, Any]:
        """Generate summary of backtest results."""
        return {
            "backtest_id": self.backtest_id,
            "total_return": self.metrics.total_return,
            "annualized_return": self.metrics.annualized_return,
            "sharpe_ratio": self.metrics.sharpe_ratio,
            "max_drawdown": self.metrics.max_drawdown,
            "total_trades": self.trade_stats.total_trades,
            "win_rate": self.trade_stats.win_rate,
            "profit_factor": self.trade_stats.profit_factor,
            "duration": (self.end_time - self.start_time).total_seconds(),
        }


class Event:
    """Event wrapper for priority queue."""
    
    def __init__(self, timestamp: Timestamp, event_type: str, data: Any):
        self.timestamp = timestamp
        self.event_type = event_type
        self.data = data
    
    def __lt__(self, other: Event) -> bool:
        return self.timestamp < other.timestamp


class BacktestEngine:
    """
    Event-driven backtesting engine.
    
    Processes market data and order events chronologically to simulate
    realistic trading execution.
    """
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.backtest_id = str(uuid.uuid4())[:8]
        
        # Initialize components
        self.execution_model = config.execution_model or MarketOrderModel(
            slippage_bps=config.slippage_bps
        )
        self.impact_model = config.impact_model or LinearImpactModel()
        
        # State
        self.portfolio = Portfolio(cash=config.initial_capital)
        self.event_queue: List[Event] = []
        self.current_time: Optional[Timestamp] = None
        self.market_data: Dict[str, MarketEvent] = {}
        
        # History tracking
        self.equity_history: List[Dict[str, Any]] = []
        self.position_history: List[Dict[str, Any]] = []
        
        # Strategy reference
        self.strategy: Optional[Strategy] = None
        
        logger.info(f"Initialized BacktestEngine {self.backtest_id}")
    
    def load_data(self, data: Union[pd.DataFrame, Dict[str, pd.DataFrame]]) -> None:
        """
        Load market data for backtest.
        
        Args:
            data: DataFrame with OHLCV data or dict mapping symbols to DataFrames
        """
        if isinstance(data, pd.DataFrame):
            data = {"default": data}
        
        for symbol, df in data.items():
            self._load_symbol_data(symbol, df)
        
        logger.info(f"Loaded data for {len(data)} symbols")
    
    def _load_symbol_data(self, symbol: str, df: pd.DataFrame) -> None:
        """Convert DataFrame to market events and add to queue."""
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        
        for col in required_cols:
            if col not in df.columns and col.capitalize() not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        for idx, row in df.iterrows():
            timestamp = Timestamp.from_datetime(pd.to_datetime(idx))
            
            event = MarketEvent(
                timestamp=timestamp,
                symbol=symbol,
                event_type='bar',
                open_price=row.get('open', row.get('Open')),
                high_price=row.get('high', row.get('High')),
                low_price=row.get('low', row.get('Low')),
                close_price=row.get('close', row.get('Close')),
                volume=row.get('volume', row.get('Volume', 0)),
                bid_price=row.get('bid'),
                ask_price=row.get('ask'),
            )
            
            heapq.heappush(self.event_queue, Event(timestamp, 'market', event))
    
    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """Submit a new order."""
        if self.current_time is None:
            raise RuntimeError("Cannot submit order before backtest starts")
        
        order = Order(
            id=str(uuid.uuid4())[:12],
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            timestamp=self.current_time,
            limit_price=limit_price,
            stop_price=stop_price,
        )
        
        # Add order execution event
        heapq.heappush(
            self.event_queue,
            Event(self.current_time, 'order', order)
        )
        
        logger.debug(f"Submitted {order_type.name} order: {order.id}")
        return order
    
    def _process_market_event(self, event: MarketEvent) -> None:
        """Process incoming market data."""
        self.market_data[event.symbol] = event
        
        # Update portfolio with current prices
        prices = {sym: ev.close_price for sym, ev in self.market_data.items() if ev.close_price}
        self.portfolio.update_market_prices(prices)
        
        # Record equity
        total_value = self.portfolio.total_value(prices)
        self.equity_history.append({
            'timestamp': event.timestamp.to_datetime(),
            'equity': total_value,
            'cash': self.portfolio.cash,
        })
        
        # Call strategy
        if self.strategy:
            signal = None
            if event.event_type == 'bar':
                signal = self.strategy.on_bar(event, self.portfolio)
            elif event.event_type == 'tick':
                signal = self.strategy.on_tick(event, self.portfolio)
            
            if signal and signal != Signal.HOLD:
                self._execute_signal(event.symbol, signal, event)
    
    def _execute_signal(
        self,
        symbol: str,
        signal: Signal,
        market_event: MarketEvent,
    ) -> None:
        """Execute trading signal."""
        position = self.portfolio.get_position(symbol)
        current_price = market_event.close_price or market_event.mid_price
        
        # Determine order side and quantity
        if signal == Signal.BUY:
            side = OrderSide.BUY
            # Simple position sizing: 10% of portfolio
            target_value = self.portfolio.cash * 0.1
            quantity = target_value / current_price if current_price > 0 else 0
        else:  # SELL
            side = OrderSide.SELL
            quantity = abs(position.quantity) if position.quantity > 0 else 0
            
            if quantity == 0 and self.config.allow_short:
                # Short sell
                portfolio_value = self.portfolio.total_value({symbol: current_price})
                target_value = portfolio_value * 0.1
                quantity = target_value / current_price if current_price > 0 else 0
        
        if quantity > 0:
            self.submit_order(symbol, side, quantity, OrderType.MARKET)
    
    def _process_order(self, order: Order) -> None:
        """Process order execution."""
        if order.symbol not in self.market_data:
            logger.warning(f"No market data for {order.symbol}")
            return
        
        market_event = self.market_data[order.symbol]
        
        # Execute using the configured execution model
        fill = self.execution_model.execute(
            order=order,
            market_event=market_event,
            impact_model=self.impact_model,
        )
        
        if fill:
            # Apply commission
            fill.commission = max(
                self.config.min_commission,
                fill.quantity * fill.fill_price * self.config.commission_rate
            )
            
            # Update portfolio
            self.portfolio.apply_fill(fill)
            order.filled_quantity += fill.quantity
            order.avg_fill_price = (
                (order.avg_fill_price * (order.filled_quantity - fill.quantity) + 
                 fill.fill_price * fill.quantity) / order.filled_quantity
                if order.filled_quantity > 0 else fill.fill_price
            )
            
            if order.filled_quantity >= order.quantity:
                order.status = OrderStatus.FILLED
            else:
                order.status = OrderStatus.PARTIAL_FILL
            
            # Notify strategy
            if self.strategy:
                self.strategy.on_order_fill(fill, self.portfolio)
            
            logger.debug(f"Order {order.id} filled: {fill.quantity} @ {fill.fill_price:.4f}")
    
    def run(self, strategy: Strategy) -> BacktestResults:
        """
        Execute backtest with given strategy.
        
        Args:
            strategy: Trading strategy to backtest
            
        Returns:
            BacktestResults containing performance metrics and trade history
        """
        self.strategy = strategy
        start_time = datetime.now()
        
        logger.info(f"Starting backtest {self.backtest_id}")
        
        # Main event loop
        while self.event_queue:
            event = heapq.heappop(self.event_queue)
            self.current_time = event.timestamp
            
            if event.event_type == 'market':
                self._process_market_event(event.data)
            elif event.event_type == 'order':
                self._process_order(event.data)
        
        end_time = datetime.now()
        
        # Generate results
        results = self._generate_results(start_time, end_time)
        
        logger.info(f"Backtest {self.backtest_id} completed in {(end_time - start_time).total_seconds():.2f}s")
        
        return results
    
    def _generate_results(self, start_time: datetime, end_time: datetime) -> BacktestResults:
        """Generate backtest results and metrics."""
        # Create equity curve DataFrame
        equity_df = pd.DataFrame(self.equity_history)
        if not equity_df.empty:
            equity_df.set_index('timestamp', inplace=True)
            equity_df['returns'] = equity_df['equity'].pct_change()
        
        # Calculate performance metrics
        metrics = PerformanceMetrics.calculate(equity_df)
        trade_stats = TradeStatistics.calculate(self.portfolio.fills)
        
        # Create positions history
        positions_data = []
        for fill in self.portfolio.fills:
            positions_data.append({
                'timestamp': fill.timestamp.to_datetime(),
                'symbol': fill.symbol,
                'side': fill.side.name,
                'quantity': fill.quantity,
                'price': fill.fill_price,
                'commission': fill.commission,
                'pnl': fill.quantity * fill.fill_price - fill.commission,
            })
        positions_df = pd.DataFrame(positions_data)
        
        return BacktestResults(
            backtest_id=self.backtest_id,
            config=self.config,
            metrics=metrics,
            trade_stats=trade_stats,
            equity_curve=equity_df,
            positions_history=positions_df,
            fills=self.portfolio.fills,
            start_time=start_time,
            end_time=end_time,
        )
    
    def reset(self) -> None:
        """Reset engine state for new backtest."""
        self.portfolio = Portfolio(cash=self.config.initial_capital)
        self.event_queue = []
        self.current_time = None
        self.market_data = {}
        self.equity_history = []
        self.position_history = []
        self.strategy = None
        self.backtest_id = str(uuid.uuid4())[:8]
        logger.info(f"Engine reset with new ID: {self.backtest_id}")
