"""
DragonScope Enterprise - Order Management System (OMS)

High-performance order management with pre-trade risk, position tracking,
and P&L calculation for institutional trading operations.
"""

import asyncio
import uuid
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum, auto
from typing import Dict, List, Optional, Callable, Any, Set
from collections import defaultdict
import json


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS
# ============================================================================

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(Enum):
    CREATED = "created"
    PENDING = "pending"
    OPEN = "open"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"


class OrderTimeInForce(Enum):
    GTC = "gtc"           # Good Till Cancelled
    DAY = "day"           # Day only
    IOC = "ioc"           # Immediate or Cancel
    FOK = "fok"           # Fill or Kill
    OPG = "opg"           # Market on Open
    CLS = "cls"           # Market on Close


class OrderEventType(Enum):
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIAL_FILL = "partial_fill"
    FILL = "fill"
    CANCEL_REQUEST = "cancel_request"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    MODIFIED = "modified"
    EXPIRED = "expired"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class OrderEvent:
    """Represents an order lifecycle event."""
    event_type: OrderEventType
    timestamp: datetime
    order_id: str
    quantity: Optional[float] = None
    price: Optional[float] = None
    message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Order:
    """Represents a trading order."""
    id: str
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    status: OrderStatus = OrderStatus.CREATED
    
    # Pricing
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    trailing_percent: Optional[float] = None
    
    # Timing
    time_in_force: OrderTimeInForce = OrderTimeInForce.DAY
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expired_at: Optional[datetime] = None
    
    # Execution tracking
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    remaining_quantity: float = field(init=False)
    
    # Algorithm
    algorithm: Optional[str] = None
    algo_params: Dict[str, Any] = field(default_factory=dict)
    
    # Broker
    broker_order_id: Optional[str] = None
    venue: Optional[str] = None
    
    # Metadata
    client_order_id: Optional[str] = None
    strategy_id: Optional[str] = None
    portfolio_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    events: List[OrderEvent] = field(default_factory=list)
    
    # Risk
    pre_trade_checks_passed: bool = False
    rejection_reason: Optional[str] = None
    
    def __post_init__(self):
        self.remaining_quantity = self.quantity
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "order_type": self.order_type.value,
            "status": self.status.value,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "average_fill_price": self.average_fill_price,
            "time_in_force": self.time_in_force.value,
            "created_at": self.created_at.isoformat(),
            "algorithm": self.algorithm,
            "venue": self.venue,
        }


@dataclass
class Position:
    """Represents a position in a symbol."""
    symbol: str
    portfolio_id: str
    quantity: float = 0.0
    average_entry_price: float = 0.0
    market_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = field(init=False)
    total_pnl: float = field(init=False)
    market_value: float = field(init=False)
    cost_basis: float = field(init=False)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        self._update_calculated_fields()
    
    def _update_calculated_fields(self):
        self.cost_basis = self.quantity * self.average_entry_price
        self.market_value = self.quantity * self.market_price
        self.unrealized_pnl = (self.market_price - self.average_entry_price) * self.quantity
        self.total_pnl = self.realized_pnl + self.unrealized_pnl
    
    def update_market_price(self, price: float):
        """Update position with latest market price."""
        self.market_price = price
        self.last_updated = datetime.utcnow()
        self._update_calculated_fields()
    
    def apply_fill(self, side: OrderSide, quantity: float, price: float):
        """Apply a fill to update position."""
        if side == OrderSide.BUY:
            # Increasing long position or reducing short
            if self.quantity >= 0:
                # Adding to long position
                new_quantity = self.quantity + quantity
                self.average_entry_price = (
                    (self.quantity * self.average_entry_price + quantity * price) / new_quantity
                )
                self.quantity = new_quantity
            else:
                # Reducing short position
                if quantity >= abs(self.quantity):
                    # Closing short and going long
                    realized = (self.average_entry_price - price) * abs(self.quantity)
                    self.realized_pnl += realized
                    remaining = quantity - abs(self.quantity)
                    self.quantity = remaining
                    self.average_entry_price = price if remaining > 0 else 0
                else:
                    # Partial close of short
                    realized = (self.average_entry_price - price) * quantity
                    self.realized_pnl += realized
                    self.quantity += quantity
        else:
            # SELL side
            if self.quantity <= 0:
                # Adding to short position
                new_quantity = self.quantity - quantity
                if self.quantity == 0:
                    self.average_entry_price = price
                else:
                    self.average_entry_price = (
                        (abs(self.quantity) * self.average_entry_price + quantity * price) / abs(new_quantity)
                    )
                self.quantity = new_quantity
            else:
                # Reducing long position
                if quantity >= self.quantity:
                    # Closing long and going short
                    realized = (price - self.average_entry_price) * self.quantity
                    self.realized_pnl += realized
                    remaining = quantity - self.quantity
                    self.quantity = -remaining
                    self.average_entry_price = price if remaining > 0 else 0
                else:
                    # Partial close of long
                    realized = (price - self.average_entry_price) * quantity
                    self.realized_pnl += realized
                    self.quantity -= quantity
        
        self.last_updated = datetime.utcnow()
        self._update_calculated_fields()


@dataclass
class PnLReport:
    """P&L report for a portfolio or symbol."""
    portfolio_id: str
    symbol: Optional[str] = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    gross_proceeds: float = 0.0
    gross_pnl: float = 0.0
    commissions: float = 0.0
    fees: float = 0.0
    net_pnl: float = 0.0
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    report_date: datetime = field(default_factory=datetime.utcnow)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


@dataclass
class RiskCheckResult:
    """Result of pre-trade risk check."""
    passed: bool
    check_name: str
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# PRE-TRADE RISK ENGINE
# ============================================================================

class PreTradeRiskEngine:
    """
    Pre-trade risk validation engine.
    Performs comprehensive checks before order submission.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.checks: List[Callable[[Order, Dict[str, Position]], RiskCheckResult]] = []
        self._setup_default_checks()
        
        # Velocity tracking
        self.order_history: List[Dict[str, Any]] = []
        self.restriction_list: Set[str] = set()
    
    def _setup_default_checks(self):
        """Setup default risk checks."""
        self.checks = [
            self._check_symbol_valid,
            self._check_size_limits,
            self._check_price_bounds,
            self._check_position_limits,
            self._check_credit_limits,
            self._check_velocity_limits,
            self._check_restricted_securities,
        ]
    
    async def validate_order(self, order: Order, positions: Dict[str, Position]) -> List[RiskCheckResult]:
        """Run all risk checks on an order."""
        results = []
        for check in self.checks:
            try:
                result = check(order, positions)
                results.append(result)
            except Exception as e:
                logger.error(f"Risk check {check.__name__} failed: {e}")
                results.append(RiskCheckResult(
                    passed=False,
                    check_name=check.__name__,
                    message=f"Check error: {str(e)}"
                ))
        return results
    
    def _check_symbol_valid(self, order: Order, positions: Dict[str, Position]) -> RiskCheckResult:
        """Check if symbol is valid and tradeable."""
        # In production, check against symbol master database
        if not order.symbol or len(order.symbol) < 1:
            return RiskCheckResult(
                passed=False,
                check_name="symbol_valid",
                message="Invalid symbol"
            )
        return RiskCheckResult(passed=True, check_name="symbol_valid")
    
    def _check_size_limits(self, order: Order, positions: Dict[str, Position]) -> RiskCheckResult:
        """Check order size against limits."""
        max_order_size = self.config.get("max_order_size", 100_000)
        max_notional = self.config.get("max_notional", 10_000_000)
        
        if order.quantity > max_order_size:
            return RiskCheckResult(
                passed=False,
                check_name="size_limits",
                message=f"Order size {order.quantity} exceeds limit {max_order_size}",
                details={"limit": max_order_size, "requested": order.quantity}
            )
        
        if order.limit_price:
            notional = order.quantity * order.limit_price
            if notional > max_notional:
                return RiskCheckResult(
                    passed=False,
                    check_name="notional_limits",
                    message=f"Order notional ${notional:,.2f} exceeds limit ${max_notional:,.2f}",
                    details={"limit": max_notional, "requested": notional}
                )
        
        return RiskCheckResult(passed=True, check_name="size_limits")
    
    def _check_price_bounds(self, order: Order, positions: Dict[str, Position]) -> RiskCheckResult:
        """Check if limit price is within acceptable bounds."""
        if not order.limit_price:
            return RiskCheckResult(passed=True, check_name="price_bounds")
        
        # In production, get reference price from market data
        price_band_pct = self.config.get("price_band_pct", 0.10)
        
        # Placeholder - would use actual reference price
        reference_price = order.limit_price  # This would come from market data
        lower_bound = reference_price * (1 - price_band_pct)
        upper_bound = reference_price * (1 + price_band_pct)
        
        if not (lower_bound <= order.limit_price <= upper_bound):
            return RiskCheckResult(
                passed=False,
                check_name="price_bounds",
                message=f"Limit price {order.limit_price} outside valid range [{lower_bound:.2f}, {upper_bound:.2f}]"
            )
        
        return RiskCheckResult(passed=True, check_name="price_bounds")
    
    def _check_position_limits(self, order: Order, positions: Dict[str, Position]) -> RiskCheckResult:
        """Check if order would exceed position limits."""
        max_position_value = self.config.get("max_position_value", 1_000_000)
        
        current_position = positions.get(order.symbol)
        if current_position:
            projected_position = current_position.quantity
            if order.side == OrderSide.BUY:
                projected_position += order.quantity
            else:
                projected_position -= order.quantity
            
            # Check position value limit
            price = order.limit_price or current_position.market_price
            position_value = abs(projected_position) * price
            
            if position_value > max_position_value:
                return RiskCheckResult(
                    passed=False,
                    check_name="position_limits",
                    message=f"Projected position value ${position_value:,.2f} exceeds limit",
                    details={"limit": max_position_value, "projected": position_value}
                )
        
        return RiskCheckResult(passed=True, check_name="position_limits")
    
    def _check_credit_limits(self, order: Order, positions: Dict[str, Position]) -> RiskCheckResult:
        """Check available buying power."""
        # In production, check against actual account buying power
        return RiskCheckResult(passed=True, check_name="credit_limits")
    
    def _check_velocity_limits(self, order: Order, positions: Dict[str, Position]) -> RiskCheckResult:
        """Check order velocity/rate limits."""
        max_orders_per_minute = self.config.get("max_orders_per_minute", 100)
        
        # Clean old history
        cutoff = datetime.utcnow() - timedelta(minutes=1)
        self.order_history = [h for h in self.order_history if h["timestamp"] > cutoff]
        
        if len(self.order_history) >= max_orders_per_minute:
            return RiskCheckResult(
                passed=False,
                check_name="velocity_limits",
                message=f"Order rate limit exceeded: {len(self.order_history)} orders in last minute"
            )
        
        return RiskCheckResult(passed=True, check_name="velocity_limits")
    
    def _check_restricted_securities(self, order: Order, positions: Dict[str, Position]) -> RiskCheckResult:
        """Check if symbol is on restricted list."""
        if order.symbol in self.restriction_list:
            return RiskCheckResult(
                passed=False,
                check_name="restricted_securities",
                message=f"Symbol {order.symbol} is restricted"
            )
        return RiskCheckResult(passed=True, check_name="restricted_securities")
    
    def add_to_restriction_list(self, symbol: str):
        """Add symbol to restricted list."""
        self.restriction_list.add(symbol)
    
    def record_order(self, order: Order):
        """Record order for velocity tracking."""
        self.order_history.append({
            "order_id": order.id,
            "timestamp": datetime.utcnow(),
            "symbol": order.symbol
        })


# ============================================================================
# ORDER MANAGER
# ============================================================================

class OrderManager:
    """
    Central Order Management System.
    
    Features:
    - Order lifecycle management
    - Position tracking
    - P&L calculation
    - Pre-trade risk validation
    - Event-driven architecture
    """
    
    def __init__(self, risk_engine: Optional[PreTradeRiskEngine] = None):
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Dict[str, Position]] = defaultdict(dict)  # portfolio -> symbol -> position
        self.pnl_history: List[PnLReport] = []
        self.risk_engine = risk_engine or PreTradeRiskEngine()
        
        # Event callbacks
        self.event_subscribers: Dict[OrderEventType, List[Callable]] = defaultdict(list)
        
        # Broker connectors
        self.broker_connectors: Dict[str, Any] = {}
        
        # Statistics
        self.stats = {
            "orders_created": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_rejected": 0,
            "total_volume": 0.0,
            "total_commissions": 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info("OrderManager initialized")
    
    # ========================================================================
    # ORDER OPERATIONS
    # ========================================================================
    
    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: OrderTimeInForce = OrderTimeInForce.DAY,
        algorithm: Optional[str] = None,
        algo_params: Optional[Dict[str, Any]] = None,
        portfolio_id: str = "default",
        strategy_id: Optional[str] = None,
        client_order_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        skip_risk_check: bool = False
    ) -> Order:
        """
        Create and optionally submit a new order.
        
        Args:
            symbol: Trading symbol
            side: Buy or sell
            quantity: Order quantity
            order_type: Market, limit, stop, etc.
            limit_price: Limit price (for limit orders)
            stop_price: Stop price (for stop orders)
            time_in_force: Order duration
            algorithm: Execution algorithm name
            algo_params: Algorithm parameters
            portfolio_id: Portfolio identifier
            strategy_id: Strategy identifier
            client_order_id: Client reference ID
            tags: Order tags
            skip_risk_check: Bypass pre-trade risk (admin only)
        
        Returns:
            Created Order object
        """
        async with self._lock:
            # Create order object
            order = Order(
                id=str(uuid.uuid4()),
                symbol=symbol.upper(),
                side=side,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                time_in_force=time_in_force,
                algorithm=algorithm,
                algo_params=algo_params or {},
                portfolio_id=portfolio_id,
                strategy_id=strategy_id,
                client_order_id=client_order_id,
                tags=tags or [],
            )
            
            # Pre-trade risk check
            if not skip_risk_check:
                portfolio_positions = self.positions.get(portfolio_id, {})
                risk_results = await self.risk_engine.validate_order(order, portfolio_positions)
                
                failed_checks = [r for r in risk_results if not r.passed]
                if failed_checks:
                    order.status = OrderStatus.REJECTED
                    order.rejection_reason = "; ".join([f"{r.check_name}: {r.message}" for r in failed_checks])
                    order.events.append(OrderEvent(
                        event_type=OrderEventType.REJECTED,
                        timestamp=datetime.utcnow(),
                        order_id=order.id,
                        message=order.rejection_reason
                    ))
                    self.orders[order.id] = order
                    self.stats["orders_rejected"] += 1
                    logger.warning(f"Order {order.id} rejected: {order.rejection_reason}")
                    return order
                
                order.pre_trade_checks_passed = True
            
            # Store order
            self.orders[order.id] = order
            self.stats["orders_created"] += 1
            
            # Record for velocity tracking
            self.risk_engine.record_order(order)
            
            # Add creation event
            order.events.append(OrderEvent(
                event_type=OrderEventType.SUBMITTED,
                timestamp=datetime.utcnow(),
                order_id=order.id
            ))
            
            logger.info(f"Order created: {order.id} - {side.value} {quantity} {symbol}")
            
            return order
    
    async def submit_order(self, order_id: str, venue: Optional[str] = None) -> Order:
        """
        Submit order to broker/exchange.
        
        Args:
            order_id: Order identifier
            venue: Target venue/connector
        
        Returns:
            Updated Order object
        """
        async with self._lock:
            order = self.orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            if order.status != OrderStatus.CREATED:
                raise ValueError(f"Cannot submit order in status {order.status.value}")
            
            order.status = OrderStatus.PENDING
            order.venue = venue
            order.updated_at = datetime.utcnow()
            
            order.events.append(OrderEvent(
                event_type=OrderEventType.SUBMITTED,
                timestamp=datetime.utcnow(),
                order_id=order.id,
                message=f"Submitted to {venue}"
            ))
            
            # In production, send to actual broker connector
            # if venue and venue in self.broker_connectors:
            #     connector = self.broker_connectors[venue]
            #     response = await connector.submit_order(order)
            
            logger.info(f"Order {order_id} submitted to {venue}")
            return order
    
    async def cancel_order(self, order_id: str, reason: str = "user_request") -> Order:
        """
        Cancel an open order.
        
        Args:
            order_id: Order identifier
            reason: Cancellation reason
        
        Returns:
            Updated Order object
        """
        async with self._lock:
            order = self.orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            if order.status not in [OrderStatus.CREATED, OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIAL]:
                raise ValueError(f"Cannot cancel order in status {order.status.value}")
            
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.utcnow()
            
            order.events.append(OrderEvent(
                event_type=OrderEventType.CANCEL_REQUEST,
                timestamp=datetime.utcnow(),
                order_id=order.id,
                message=f"Cancel requested: {reason}"
            ))
            
            order.events.append(OrderEvent(
                event_type=OrderEventType.CANCELLED,
                timestamp=datetime.utcnow(),
                order_id=order.id,
                message="Cancelled confirmed"
            ))
            
            self.stats["orders_cancelled"] += 1
            
            # Notify subscribers
            await self._notify_event_subscribers(OrderEventType.CANCELLED, order)
            
            logger.info(f"Order {order_id} cancelled: {reason}")
            return order
    
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Order:
        """
        Modify an existing order.
        
        Args:
            order_id: Order identifier
            quantity: New quantity
            limit_price: New limit price
            stop_price: New stop price
        
        Returns:
            Updated Order object
        """
        async with self._lock:
            order = self.orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            if order.status not in [OrderStatus.OPEN, OrderStatus.PARTIAL]:
                raise ValueError(f"Cannot modify order in status {order.status.value}")
            
            old_values = {
                "quantity": order.quantity,
                "limit_price": order.limit_price,
                "stop_price": order.stop_price
            }
            
            if quantity is not None:
                order.quantity = quantity
                order.remaining_quantity = quantity - order.filled_quantity
            
            if limit_price is not None:
                order.limit_price = limit_price
            
            if stop_price is not None:
                order.stop_price = stop_price
            
            order.updated_at = datetime.utcnow()
            
            order.events.append(OrderEvent(
                event_type=OrderEventType.MODIFIED,
                timestamp=datetime.utcnow(),
                order_id=order.id,
                message=f"Modified: {old_values} -> quantity={order.quantity}, limit={order.limit_price}"
            ))
            
            logger.info(f"Order {order_id} modified")
            return order
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)
    
    async def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """Get order status."""
        order = self.orders.get(order_id)
        return order.status if order else None
    
    async def list_orders(
        self,
        portfolio_id: Optional[str] = None,
        symbol: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        strategy_id: Optional[str] = None
    ) -> List[Order]:
        """
        List orders with optional filtering.
        
        Args:
            portfolio_id: Filter by portfolio
            symbol: Filter by symbol
            status: Filter by status
            strategy_id: Filter by strategy
        
        Returns:
            List of matching orders
        """
        result = list(self.orders.values())
        
        if portfolio_id:
            result = [o for o in result if o.portfolio_id == portfolio_id]
        
        if symbol:
            result = [o for o in result if o.symbol == symbol.upper()]
        
        if status:
            result = [o for o in result if o.status == status]
        
        if strategy_id:
            result = [o for o in result if o.strategy_id == strategy_id]
        
        return sorted(result, key=lambda o: o.created_at, reverse=True)
    
    # ========================================================================
    # FILL PROCESSING
    # ========================================================================
    
    async def process_fill(
        self,
        order_id: str,
        fill_quantity: float,
        fill_price: float,
        timestamp: Optional[datetime] = None,
        commission: float = 0.0,
        venue: Optional[str] = None
    ) -> Order:
        """
        Process an order fill.
        
        Args:
            order_id: Order identifier
            fill_quantity: Quantity filled
            fill_price: Fill price
            timestamp: Fill timestamp
            commission: Commission paid
            venue: Executing venue
        
        Returns:
            Updated Order object
        """
        async with self._lock:
            order = self.orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            timestamp = timestamp or datetime.utcnow()
            
            # Update fill tracking
            old_filled = order.filled_quantity
            order.filled_quantity += fill_quantity
            order.remaining_quantity = order.quantity - order.filled_quantity
            
            # Update average fill price
            if order.filled_quantity > 0:
                order.average_fill_price = (
                    (old_filled * order.average_fill_price + fill_quantity * fill_price) / order.filled_quantity
                )
            
            # Update status
            if order.filled_quantity >= order.quantity:
                order.status = OrderStatus.FILLED
                self.stats["orders_filled"] += 1
                event_type = OrderEventType.FILL
            else:
                order.status = OrderStatus.PARTIAL
                event_type = OrderEventType.PARTIAL_FILL
            
            order.updated_at = timestamp
            
            # Add fill event
            order.events.append(OrderEvent(
                event_type=event_type,
                timestamp=timestamp,
                order_id=order.id,
                quantity=fill_quantity,
                price=fill_price,
                message=f"Fill: {fill_quantity} @ {fill_price}",
                metadata={"commission": commission, "venue": venue}
            ))
            
            # Update position
            await self._update_position(order, fill_quantity, fill_price)
            
            # Update stats
            self.stats["total_volume"] += fill_quantity * fill_price
            self.stats["total_commissions"] += commission
            
            # Notify subscribers
            await self._notify_event_subscribers(event_type, order)
            
            logger.info(f"Order {order_id} fill: {fill_quantity} @ {fill_price}")
            return order
    
    async def _update_position(self, order: Order, fill_quantity: float, fill_price: float):
        """Update position for a fill."""
        portfolio_id = order.portfolio_id or "default"
        symbol = order.symbol
        
        # Get or create position
        if symbol not in self.positions[portfolio_id]:
            self.positions[portfolio_id][symbol] = Position(
                symbol=symbol,
                portfolio_id=portfolio_id
            )
        
        position = self.positions[portfolio_id][symbol]
        position.apply_fill(order.side, fill_quantity, fill_price)
        
        logger.debug(f"Position updated: {portfolio_id}:{symbol} = {position.quantity}")
    
    # ========================================================================
    # POSITION & P&L
    # ========================================================================
    
    async def get_position(self, symbol: str, portfolio_id: str = "default") -> Optional[Position]:
        """Get position for a symbol in a portfolio."""
        return self.positions.get(portfolio_id, {}).get(symbol)
    
    async def get_all_positions(self, portfolio_id: Optional[str] = None) -> Dict[str, Position]:
        """
        Get all positions.
        
        Args:
            portfolio_id: Filter by portfolio (None for all)
        
        Returns:
            Dictionary of positions
        """
        if portfolio_id:
            return self.positions.get(portfolio_id, {})
        
        # Flatten all positions
        all_positions = {}
        for pf_id, positions in self.positions.items():
            for symbol, position in positions.items():
                all_positions[f"{pf_id}:{symbol}"] = position
        return all_positions
    
    async def update_market_prices(self, prices: Dict[str, float], portfolio_id: Optional[str] = None):
        """
        Update market prices for position P&L calculation.
        
        Args:
            prices: Dict of symbol -> price
            portfolio_id: Update specific portfolio (None for all)
        """
        async with self._lock:
            targets = [portfolio_id] if portfolio_id else list(self.positions.keys())
            
            for pf_id in targets:
                for symbol, price in prices.items():
                    if symbol in self.positions[pf_id]:
                        self.positions[pf_id][symbol].update_market_price(price)
    
    async def calculate_pnl(
        self,
        portfolio_id: Optional[str] = None,
        symbol: Optional[str] = None,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None
    ) -> PnLReport:
        """
        Calculate P&L report.
        
        Args:
            portfolio_id: Filter by portfolio
            symbol: Filter by symbol
            period_start: Start of period
            period_end: End of period
        
        Returns:
            PnLReport object
        """
        report = PnLReport(
            portfolio_id=portfolio_id or "all",
            symbol=symbol,
            period_start=period_start,
            period_end=period_end or datetime.utcnow()
        )
        
        # Aggregate positions
        positions_to_include = []
        
        if portfolio_id and symbol:
            pos = await self.get_position(symbol, portfolio_id)
            if pos:
                positions_to_include.append(pos)
        elif portfolio_id:
            positions_to_include = list(self.positions.get(portfolio_id, {}).values())
        else:
            for pf_positions in self.positions.values():
                positions_to_include.extend(pf_positions.values())
        
        # Calculate totals
        for pos in positions_to_include:
            report.realized_pnl += pos.realized_pnl
            report.unrealized_pnl += pos.unrealized_pnl
        
        report.total_pnl = report.realized_pnl + report.unrealized_pnl
        report.gross_pnl = report.total_pnl
        report.net_pnl = report.gross_pnl - report.commissions - report.fees
        
        return report
    
    # ========================================================================
    # EVENT SUBSCRIPTION
    # ========================================================================
    
    def subscribe_to_events(self, event_type: OrderEventType, callback: Callable):
        """Subscribe to order events."""
        self.event_subscribers[event_type].append(callback)
    
    def unsubscribe_from_events(self, event_type: OrderEventType, callback: Callable):
        """Unsubscribe from order events."""
        if callback in self.event_subscribers[event_type]:
            self.event_subscribers[event_type].remove(callback)
    
    async def _notify_event_subscribers(self, event_type: OrderEventType, order: Order):
        """Notify event subscribers."""
        for callback in self.event_subscribers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(order)
                else:
                    callback(order)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
    
    # ========================================================================
    # BROKER CONNECTORS
    # ========================================================================
    
    def register_broker_connector(self, name: str, connector: Any):
        """Register a broker connector."""
        self.broker_connectors[name] = connector
        logger.info(f"Registered broker connector: {name}")
    
    # ========================================================================
    # STATISTICS & REPORTING
    # ========================================================================
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get OMS statistics."""
        return {
            **self.stats,
            "active_orders": len([o for o in self.orders.values() if o.status in [OrderStatus.OPEN, OrderStatus.PARTIAL]]),
            "total_orders": len(self.orders),
            "open_positions": sum(len(p) for p in self.positions.values()),
        }
    
    async def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive OMS report."""
        pnl = await self.calculate_pnl()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": await self.get_statistics(),
            "pnl_summary": {
                "realized_pnl": pnl.realized_pnl,
                "unrealized_pnl": pnl.unrealized_pnl,
                "total_pnl": pnl.total_pnl,
                "net_pnl": pnl.net_pnl,
            },
            "orders_by_status": self._get_orders_by_status(),
            "positions_summary": self._get_positions_summary(),
        }
    
    def _get_orders_by_status(self) -> Dict[str, int]:
        """Count orders by status."""
        counts = defaultdict(int)
        for order in self.orders.values():
            counts[order.status.value] += 1
        return dict(counts)
    
    def _get_positions_summary(self) -> Dict[str, Any]:
        """Get positions summary."""
        summary = {
            "long_positions": 0,
            "short_positions": 0,
            "total_long_value": 0.0,
            "total_short_value": 0.0,
            "gross_exposure": 0.0,
            "net_exposure": 0.0,
        }
        
        for pf_positions in self.positions.values():
            for pos in pf_positions.values():
                if pos.quantity > 0:
                    summary["long_positions"] += 1
                    summary["total_long_value"] += pos.market_value
                elif pos.quantity < 0:
                    summary["short_positions"] += 1
                    summary["total_short_value"] += abs(pos.market_value)
        
        summary["gross_exposure"] = summary["total_long_value"] + summary["total_short_value"]
        summary["net_exposure"] = summary["total_long_value"] - summary["total_short_value"]
        
        return summary


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def main():
    """Example usage of OrderManager."""
    # Initialize OMS
    oms = OrderManager()
    
    # Create orders
    order1 = await oms.create_order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price=150.00,
        portfolio_id="portfolio_1"
    )
    print(f"Created order: {order1.id}")
    
    # Submit order
    await oms.submit_order(order1.id, venue="alpaca")
    
    # Simulate fill
    await oms.process_fill(order1.id, fill_quantity=50, fill_price=149.50)
    
    # Check position
    position = await oms.get_position("AAPL", "portfolio_1")
    print(f"Position: {position.quantity} @ {position.average_entry_price}")
    
    # Create sell order
    order2 = await oms.create_order(
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=50,
        order_type=OrderType.MARKET,
        portfolio_id="portfolio_1"
    )
    
    await oms.submit_order(order2.id)
    await oms.process_fill(order2.id, fill_quantity=50, fill_price=151.00)
    
    # Update market price
    await oms.update_market_prices({"AAPL": 152.00}, portfolio_id="portfolio_1")
    
    # Get P&L
    pnl = await oms.calculate_pnl(portfolio_id="portfolio_1")
    print(f"Realized P&L: ${pnl.realized_pnl:,.2f}")
    print(f"Unrealized P&L: ${pnl.unrealized_pnl:,.2f}")
    
    # Generate report
    report = await oms.generate_report()
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
