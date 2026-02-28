# DragonScope Enterprise - Trading Execution System

A high-performance Order Management System (OMS) with Smart Order Routing (SOR) for institutional-grade trade execution.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TRADING EXECUTION SYSTEM                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   Client    │    │   Client    │    │   Client    │    │   Client    │  │
│  │   (UI)      │    │   (API)     │    │  (Algo)     │    │   (Risk)    │  │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │
│         │                  │                  │                  │         │
│         └──────────────────┴──────────────────┴──────────────────┘         │
│                                    │                                        │
│                         ┌──────────▼──────────┐                            │
│                         │   Order Manager     │                            │
│                         │     (oms.py)        │                            │
│                         └──────────┬──────────┘                            │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         │                          │                          │            │
│  ┌──────▼──────┐          ┌────────▼────────┐        ┌───────▼───────┐     │
│  │ Pre-Trade   │          │  Execution      │        │   Position    │     │
│  │ Risk Engine │          │  Algorithms     │        │   Manager     │     │
│  └──────┬──────┘          └────────┬────────┘        └───────────────┘     │
│         │                          │                                        │
│         │               ┌──────────▼──────────┐                            │
│         │               │  Smart Order Router │                            │
│         │               └──────────┬──────────┘                            │
│         │                          │                                        │
│  ┌──────▼──────────────────────────▼──────────────────────┐                │
│  │              Broker Connectors                         │                │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │                │
│  │  │  Alpaca  │ │    IB    │ │ Coinbase │ │   FIX    │  │                │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │                │
│  └────────────────────────────────────────────────────────┘                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Order Lifecycle

```
                    ┌─────────────────────────────────────┐
                    │                                     │
    ┌──────────┐    │  ┌────────┐    ┌──────────┐        │
    │  CREATE  │────┼─►│ PENDING│───►│  OPEN    │        │
    └──────────┘    │  └────────┘    └────┬─────┘        │
                    │       │               │             │
                    │       ▼               ▼             │
                    │  ┌────────┐    ┌──────────┐        │
                    │  │REJECTED│    │  FILLED  │        │
                    │  └────────┘    └────┬─────┘        │
                    │       ▲               │             │
                    │       │               ▼             │
                    │  ┌────────┐    ┌──────────┐        │
                    │  │CANCELLED│   │ PARTIAL  │        │
                    │  └────────┘    └────┬─────┘        │
                    │                     │               │
                    │                     ▼               │
                    │               ┌──────────┐         │
                    └──────────────►│ COMPLETED│◄────────┘
                                    └──────────┘
```

### State Definitions

| State | Description |
|-------|-------------|
| **CREATED** | Order initialized but not yet submitted to market |
| **PENDING** | Order submitted, awaiting exchange acknowledgment |
| **OPEN** | Order active in the market, available for execution |
| **PARTIAL** | Order partially filled, remaining quantity still active |
| **FILLED** | Order completely filled |
| **CANCELLED** | Order cancelled by user or system |
| **REJECTED** | Order rejected by pre-trade risk or exchange |
| **EXPIRED** | Order reached time limit without complete fill |
| **ERROR** | System error occurred during processing |

### Order Events

```python
class OrderEvent:
    SUBMITTED      = "submitted"      # Sent to broker
    ACKNOWLEDGED   = "acknowledged"   # Broker confirmed
    PARTIAL_FILL   = "partial_fill"   # Partial execution
    FILL           = "fill"           # Complete execution
    CANCEL_REQUEST = "cancel_request" # Cancel sent
    CANCELLED      = "cancelled"      # Cancel confirmed
    REJECTED       = "rejected"       # Order rejected
    MODIFIED       = "modified"       # Order modified
    EXPIRED        = "expired"        # Time limit reached
```

## Smart Order Router (SOR)

The Smart Order Router intelligently distributes orders across multiple venues to optimize execution quality.

### Routing Strategies

1. **Best Price Routing**
   - Compares quoted prices across venues
   - Routes to venue with best available price
   - Accounts for fees and rebates

2. **Liquidity-Based Routing**
   - Routes to venues with deepest liquidity
   - Minimizes market impact
   - Uses Level 2 order book analysis

3. **Cost-Optimized Routing**
   - Minimizes total execution cost
   - Considers: fees + spread + market impact
   - Uses historical venue performance

4. **Latency-Based Routing**
   - Routes to lowest-latency venue
   - Critical for time-sensitive strategies
   - Uses real-time latency monitoring

### Routing Decision Matrix

```python
@dataclass
class RoutingDecision:
    venue: str
    quantity: float
    order_type: OrderType
    priority: int
    expected_cost: float
    expected_fill_time: timedelta
```

## Execution Algorithms

### 1. TWAP (Time-Weighted Average Price)

Distributes order evenly over a time window.

```python
# Example: Execute 10,000 shares over 4 hours
# Slice interval: 15 minutes
# Slices: 16
# Quantity per slice: 625 shares

Schedule:
├─ 09:30 ── 625 shares
├─ 09:45 ── 625 shares
├─ 10:00 ── 625 shares
├─ ...
└─ 13:30 ── 625 shares
```

**Use Case:** Large orders where minimal market impact is prioritized over execution speed.

### 2. VWAP (Volume-Weighted Average Price)

Executes based on historical volume profile.

```python
# Example: Execute proportional to expected volume
# Historical volume at 10:00: 5% of daily volume
# Target participation: 10%
# Order quantity: 10,000 shares

At 10:00, if expected volume = 1M shares:
  Slice quantity = 1M × 5% × 10% = 5,000 shares
```

**Use Case:** Benchmark execution against VWAP, minimizing tracking error.

### 3. Percentage of Volume (PoV)

Participates at a fixed percentage of market volume.

```python
# Participation rate: 15%
# Market volume: 100,000 shares/minute
# Execution: 15,000 shares/minute

Adaptive: Increases participation during low-volume periods
```

**Use Case:** Steady execution with controlled participation rate.

### 4. Arrival Price (Implementation Shortfall)

Minimizes slippage from decision price.

```python
# Decision price: $100.00
# Current price: $100.25
# Urgency: High (execute quickly)
# Risk aversion: Medium

Optimal schedule balances:
- Execution risk (price drift)
- Market impact (large slices)
```

**Use Case:** Minimize tracking error to decision-time price.

### 5. Implementation Shortfall

Advanced algorithm balancing market impact and opportunity cost.

```python
IS = (Execution Price - Decision Price) / Decision Price

Components:
- Explicit costs: commissions, fees
- Implicit costs: spread, market impact
- Opportunity cost: unexecuted quantity × price drift
```

**Use Case:** Minimize total implementation cost.

## Pre-Trade Risk Checks

### Risk Validation Pipeline

```
Order Submission
       │
       ▼
┌─────────────────┐
│ 1. Symbol Valid │ ──► Check symbol exists, is tradeable
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. Size Limits  │ ──► Max order size, position limits
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. Price Checks │ ──► Price bands, fat finger checks
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. Credit Check │ ──► Available buying power
└────────┬────────┘
         ▼
┌─────────────────┐
│ 5. Velocity     │ ──► Order frequency limits
└────────┬────────┘
         ▼
   [PASSED / REJECTED]
```

### Risk Limits

| Limit Type | Description | Default |
|------------|-------------|---------|
| Max Order Size | Maximum single order quantity | 100,000 |
| Max Position | Maximum position per symbol | $1M |
| Max Notional | Maximum order notional value | $10M |
| Price Band | Valid price range (±10% last) | ±10% |
| Daily Loss | Maximum daily loss limit | $100K |
| Order Rate | Max orders per minute | 100 |

## Compliance Validation

### Pre-Trade Compliance

1. **Restricted Securities**
   - Blocklist checking
   - Sector restrictions
   - Watchlist monitoring

2. **Regulatory Checks**
   - Reg SHO (short sale restrictions)
   - Reg M (distribution compliance)
   - Rule 15c3-5 (Market Access Rule)

3. **Firm-Specific Rules**
   - Approved symbol lists
   - Strategy restrictions
   - Time-of-day restrictions

### Post-Trade Compliance

- TCA (Transaction Cost Analysis)
- Best execution reporting
- Audit trail maintenance

## API Reference

### OrderManager

```python
from execution.oms import OrderManager

oms = OrderManager()

# Create order
order = await oms.create_order(
    symbol="AAPL",
    side=OrderSide.BUY,
    quantity=1000,
    order_type=OrderType.LIMIT,
    limit_price=150.00,
    algorithm="TWAP",
    algo_params={"duration": 3600, "slices": 12}
)

# Cancel order
await oms.cancel_order(order.id)

# Modify order
await oms.modify_order(order.id, quantity=500)

# Get status
status = await oms.get_order_status(order.id)
```

### Execution Algorithms

```python
from execution.algorithms import VWAPAlgo

# Configure VWAP
vwap = VWAPAlgo(
    symbol="AAPL",
    side=OrderSide.BUY,
    total_quantity=10000,
    duration=timedelta(hours=4),
    participation_rate=0.15
)

# Start execution
await vwap.execute()
```

### Broker Connectors

```python
from execution.broker_connectors import AlpacaConnector

# Initialize connector
alpaca = AlpacaConnector(
    api_key="...",
    secret_key="...",
    paper=True
)

# Submit order
response = await alpaca.submit_order(order)

# Stream fills
async for fill in alpaca.stream_fills():
    print(f"Fill: {fill.quantity} @ {fill.price}")
```

## Configuration

```yaml
# config/execution.yaml
oms:
  order_timeout: 30
  max_pending_orders: 1000
  
risk:
  max_order_size: 100000
  max_position_value: 1000000
  price_band_pct: 0.10
  
routing:
  default_strategy: "best_price"
  venues:
    - alpaca
    - interactive_brokers
    - coinbase_pro
  
algorithms:
  twap:
    min_slice_interval: 60
    max_participation: 0.25
  vwap:
    volume_profile_lookback: 30
```

## Performance Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Order Latency | Submit to ack time | < 50ms |
| Fill Latency | Order to fill time | < 100ms |
| Throughput | Orders per second | > 1000 |
| Availability | System uptime | 99.99% |

## License

Proprietary - DragonScope Enterprise
