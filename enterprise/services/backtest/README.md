# DragonScope Enterprise Backtesting Engine

A professional-grade, event-driven backtesting framework designed for institutional quantitative trading strategy validation.

## Overview

The DragonScope Backtesting Engine provides high-fidelity simulation of trading strategies with realistic market microstructure modeling, including slippage, market impact, and partial fills. It supports both tick-level and bar-level simulations with comprehensive performance analytics.

## Features

### Event-Driven Architecture
- **Discrete Event Simulation**: Event loop processes market data ticks/bars and order events chronologically
- **High-Precision Timestamping**: Nanosecond-level resolution for HFT strategies
- **Asynchronous Event Queue**: Priority-based event processing for complex scenarios
- **Multi-Asset Support**: Simultaneous backtesting across multiple instruments

### Market Simulation Fidelity
- **Tick-Level Precision**: Replay historical tick data with microsecond accuracy
- **Bar Simulation**: OHLCV aggregation with intra-bar modeling
- **Gap Handling**: Proper handling of market opens, closes, and trading halts
- **Corporate Actions**: Dividends, splits, and other adjustment factors

### Execution Modeling
- **Multiple Order Types**: Market, Limit, Stop, Stop-Limit, Trailing Stop
- **Partial Fill Simulation**: Realistic fill rates based on available liquidity
- **Smart Order Router**: Multi-venue execution simulation
- **Latency Modeling**: Configurable network and processing delays

### Market Impact Models
- **Linear Impact Model**: Price impact proportional to order size
- **Square Root Impact (Almgren)**: Industry-standard non-linear impact model
- **Permanent vs Temporary Impact**: Separate modeling of transient and lasting effects
- **Volume Participation**: VWAP-style execution with volume constraints

### Performance Analytics
- **Risk-Adjusted Returns**: Sharpe, Sortino, Calmar, Omega ratios
- **Drawdown Analysis**: Maximum drawdown, duration, and recovery statistics
- **Trade Analytics**: Win rate, profit factor, expectancy, Kelly criterion
- **Benchmark Comparison**: Alpha, beta, tracking error, information ratio
- **Attribution Analysis**: Factor exposure and return decomposition

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BacktestEngine                               │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Event Loop   │  │ Portfolio    │  │ Performance          │  │
│  │              │──│ Tracker      │──│ Calculator           │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└──────────┬─────────────────────────────────────────────────────┘
           │
     ┌─────┴──────┬──────────────┬──────────────┐
     ▼            ▼              ▼              ▼
┌─────────┐ ┌──────────┐ ┌──────────────┐ ┌──────────┐
│ Market  │ │ Order    │ │ Execution    │ │ Market   │
│ Data    │ │ Manager  │ │ Models       │ │ Impact   │
│ Feed    │ │          │ │              │ │ Models   │
└─────────┘ └──────────┘ └──────────────┘ └──────────┘
```

## Quick Start

```python
from backtest.engine import BacktestEngine, BacktestConfig
from backtest.execution_models import MarketOrderModel
from backtest.market_impact import SquareRootImpactModel
from examples.moving_average_crossover import MACrossoverStrategy

# Configure backtest
config = BacktestConfig(
    initial_capital=1_000_000,
    start_date="2023-01-01",
    end_date="2023-12-31",
    symbols=["AAPL", "MSFT", "GOOGL"],
    execution_model=MarketOrderModel(slippage_bps=1.0),
    impact_model=SquareRootImpactModel(eta=0.5)
)

# Initialize engine
engine = BacktestEngine(config)

# Load strategy
strategy = MACrossoverStrategy(fast_period=20, slow_period=50)

# Run backtest
results = engine.run(strategy)

# Analyze performance
print(f"Total Return: {results.metrics.total_return:.2%}")
print(f"Sharpe Ratio: {results.metrics.sharpe_ratio:.2f}")
print(f"Max Drawdown: {results.metrics.max_drawdown:.2%}")
```

## Configuration

### BacktestConfig Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `initial_capital` | float | Starting portfolio value | 1,000,000 |
| `start_date` | str | Backtest start date (YYYY-MM-DD) | Required |
| `end_date` | str | Backtest end date (YYYY-MM-DD) | Required |
| `symbols` | List[str] | Instruments to trade | Required |
| `data_frequency` | str | tick, 1min, 5min, 1h, 1d | 1d |
| `commission_rate` | float | Commission as decimal (0.001 = 10bps) | 0.0 |
| `slippage_bps` | float | Slippage in basis points | 0.0 |
| `execution_model` | ExecutionModel | Order execution simulation | MarketOrderModel |
| `impact_model` | MarketImpactModel | Price impact model | LinearImpactModel |
| `allow_short` | bool | Enable short selling | True |
| `margin_requirement` | float | Initial margin for shorts | 0.5 |

## Order Execution Models

### MarketOrderModel
Immediate fill at current market price plus slippage.

```python
from backtest.execution_models import MarketOrderModel

model = MarketOrderModel(
    slippage_bps=2.0,  # 2 basis points slippage
    fill_probability=0.99  # 99% fill probability
)
```

### LimitOrderModel
Fill when price touches limit level with time priority simulation.

```python
from backtest.execution_models import LimitOrderModel

model = LimitOrderModel(
    fill_at_touch=True,  # Fill when price equals limit
    queue_position_model="time",  # Time-based queue priority
    partial_fill_enabled=True
)
```

### StopOrderModel
Market order triggered when stop level is breached.

```python
from backtest.execution_models import StopOrderModel

model = StopOrderModel(
    trigger_type="trade",  # Trade or quote trigger
    slippage_on_trigger=5.0  # Additional slippage on stop
)
```

### SmartOrderRouterModel
Multi-venue execution with intelligent routing.

```python
from backtest.execution_models import SmartOrderRouterModel

model = SmartOrderRouterModel(
    venues=["NYSE", "NASDAQ", "IEX"],
    routing_strategy="price_improvement",
    venue_priority={"NYSE": 0.5, "NASDAQ": 0.4, "IEX": 0.1}
)
```

## Market Impact Models

### LinearImpactModel
Simple proportional impact model.

```python
from backtest.market_impact import LinearImpactModel

model = LinearImpactModel(
    eta=0.1,  # Impact coefficient
    gamma=1.0  # Linear exponent
)
```

### SquareRootImpactModel (Almgren)
Industry-standard square root impact model.

```python
from backtest.market_impact import SquareRootImpactModel

model = SquareRootImpactModel(
    eta=0.5,  # Temporary impact coefficient
    gamma=0.5,  # Permanent impact coefficient
    beta=0.6  # Decay parameter
)
```

## Performance Metrics

### Return Metrics
- **Total Return**: Cumulative strategy return
- **Annualized Return**: Return normalized to yearly basis
- **CAGR**: Compound Annual Growth Rate

### Risk Metrics
- **Volatility**: Standard deviation of returns
- **Downside Deviation**: Volatility of negative returns only
- **Value at Risk (VaR)**: Parametric and historical VaR
- **Conditional VaR**: Expected shortfall

### Risk-Adjusted Performance
- **Sharpe Ratio**: Return per unit of total risk
- **Sortino Ratio**: Return per unit of downside risk
- **Calmar Ratio**: Return relative to max drawdown
- **Omega Ratio**: Probability-weighted gains/losses

### Drawdown Analysis
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Average Drawdown**: Mean of all drawdowns
- **Drawdown Duration**: Time to recover from drawdowns
- **Ulcer Index**: Square root of mean squared drawdown

### Trade Statistics
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Gross profit / gross loss
- **Expectancy**: Average return per trade
- **Kelly Criterion**: Optimal position sizing fraction

### Benchmark Comparison
- **Alpha**: Excess return over benchmark
- **Beta**: Systematic risk exposure
- **Information Ratio**: Alpha per unit of tracking error
- **Treynor Ratio**: Return per unit of systematic risk

## Example Strategies

### Moving Average Crossover
```python
# examples/moving_average_crossover.py
class MACrossoverStrategy:
    def __init__(self, fast_period=20, slow_period=50):
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def on_bar(self, bar, portfolio):
        fast_ma = bar.close.rolling(self.fast_period).mean()
        slow_ma = bar.close.rolling(self.slow_period).mean()
        
        if fast_ma[-1] > slow_ma[-1] and fast_ma[-2] <= slow_ma[-2]:
            return Signal.BUY
        elif fast_ma[-1] < slow_ma[-1] and fast_ma[-2] >= slow_ma[-2]:
            return Signal.SELL
```

### RSI Mean Reversion
```python
# examples/rsi_mean_reversion.py
class RSIMeanReversionStrategy:
    def __init__(self, period=14, overbought=70, oversold=30):
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
```

### Momentum Strategy
```python
# examples/momentum_strategy.py
class MomentumStrategy:
    def __init__(self, lookback=12, holding_period=1):
        self.lookback = lookback
        self.holding_period = holding_period
```

## API Endpoints

### Run Backtest
```bash
POST /api/v1/backtests
{
  "strategy_id": "ma_crossover_001",
  "config": {
    "symbols": ["AAPL", "MSFT"],
    "start_date": "2023-01-01",
    "end_date": "2023-12-31"
  }
}
```

### Get Results
```bash
GET /api/v1/backtests/{backtest_id}/results
```

### Compare Backtests
```bash
POST /api/v1/backtests/compare
{
  "backtest_ids": ["bt_001", "bt_002"],
  "metrics": ["sharpe_ratio", "max_drawdown", "total_return"]
}
```

## Performance Considerations

- **Tick Data**: Use bar data for faster iteration during development
- **Vectorization**: NumPy/Pandas operations preferred over loops
- **Caching**: Market data and intermediate results cached in memory
- **Parallelization**: Multi-core support for parameter sweeps
- **Memory Management**: Streaming data processing for large datasets

## Testing

```bash
# Run unit tests
pytest tests/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=backtest tests/
```

## License

Proprietary - DragonScope Enterprise License

## Support

For enterprise support and custom feature development, contact enterprise@dragonscope.io
