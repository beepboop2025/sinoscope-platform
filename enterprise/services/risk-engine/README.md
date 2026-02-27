# DragonScope Risk Analytics Engine

Enterprise-grade real-time portfolio risk calculation system designed for sub-second performance on portfolios up to 10,000 positions.

## Overview

The Risk Analytics Engine provides comprehensive risk metrics calculation using multiple methodologies:
- **Parametric (Variance-Covariance)**: Fast analytical calculations
- **Historical Simulation**: Non-parametric approach using historical returns
- **Monte Carlo Simulation**: Stochastic modeling for complex portfolios

## Supported Risk Metrics

### Core Metrics

| Metric | Description | Time Complexity |
|--------|-------------|-----------------|
| **VaR** (Value at Risk) | Maximum expected loss at confidence level | O(n) - O(n²) |
| **CVaR/ES** (Expected Shortfall) | Average loss beyond VaR threshold | O(n) - O(n²) |
| **Sharpe Ratio** | Risk-adjusted return metric | O(n) |
| **Sortino Ratio** | Downside risk-adjusted return | O(n) |
| **Beta** | Market sensitivity measure | O(n) |
| **Tracking Error** | Active risk vs benchmark | O(n) |

### Advanced Analytics

- **Greeks Calculation**: Delta, Gamma, Theta, Vega, Rho for options portfolios
- **Factor Exposure**: Multi-factor risk model decomposition
- **Stress Testing**: Scenario-based portfolio impact analysis
- **Correlation Analysis**: Dynamic correlation matrix management

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                       │
├─────────────────────────────────────────────────────────────┤
│  /risk/portfolio/{id}/var    │    /risk/portfolio/{id}/stress-test │
│  /risk/factors               │    /risk/scenarios                  │
├─────────────────────────────────────────────────────────────┤
│                   Calculation Engine                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ PortfolioAnalytics  │  │ ValueAtRisk     │  │ GreeksCalculator│        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
│  ┌──────────────┐  ┌──────────────┐                          │
│  │ FactorExposure    │  │ StressTest      │                          │
│  └──────────────┘  └──────────────┘                          │
├─────────────────────────────────────────────────────────────┤
│                    Caching Layer (Redis)                     │
├─────────────────────────────────────────────────────────────┤
│                    Data Models                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ RiskReport        │  │ Scenario        │  │ FactorModel     │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Monte Carlo Simulation

### Implementation Details

```python
# Geometric Brownian Motion for price paths
S(t) = S(0) * exp((μ - 0.5σ²)t + σ√t * Z)

Where:
- S(t): Price at time t
- μ: Drift (expected return)
- σ: Volatility
- Z: Standard normal random variable
```

### Performance Optimizations
- Vectorized numpy operations
- Parallel simulation runs
- Antithetic variates for variance reduction
- Cholesky decomposition for correlated paths

### Configuration
```python
{
    "n_simulations": 10000,      # Number of price paths
    "time_horizon": 21,          # Trading days
    "confidence_level": 0.95,    # VaR confidence
    "random_seed": 42,           # Reproducibility
    "variance_reduction": true   # Antithetic variates
}
```

## Historical Simulation

### Methodology
1. Collect historical returns (default: 252 trading days)
2. Apply current portfolio weights to historical scenarios
3. Sort portfolio P&L distribution
4. Extract quantile at confidence level

### Advantages
- Non-parametric (no distribution assumptions)
- Captures fat tails and skewness
- Simple to implement and explain

### Limitations
- Dependent on historical period
- May miss unprecedented events

## Performance Benchmarks

| Portfolio Size | VaR Calculation | Stress Test | Factor Analysis |
|----------------|-----------------|-------------|-----------------|
| 100 positions  | < 50ms          | < 100ms     | < 75ms          |
| 1,000 positions| < 100ms         | < 250ms     | < 150ms         |
| 10,000 positions| < 500ms        | < 1000ms    | < 750ms         |

## API Endpoints

### Calculate VaR
```http
POST /risk/portfolio/{id}/var
Content-Type: application/json

{
    "method": "monte_carlo",
    "confidence_level": 0.95,
    "time_horizon": 1,
    "n_simulations": 10000
}
```

### Run Stress Test
```http
POST /risk/portfolio/{id}/stress-test
Content-Type: application/json

{
    "scenario_id": "2008_financial_crisis",
    "shocks": {
        "equity": -0.40,
        "credit_spread": 0.03,
        "volatility": 0.50
    }
}
```

### Get Risk Factors
```http
GET /risk/factors
```

### Create Scenario
```http
POST /risk/scenarios
Content-Type: application/json

{
    "name": "Custom Scenario",
    "description": "Custom stress scenario",
    "shocks": {...},
    "correlation_stress": {...}
}
```

## Configuration

### Environment Variables
```bash
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Cache TTL (seconds)
CACHE_TTL_VAR=300
CACHE_TTL_STRESS=600
CACHE_TTL_FACTORS=3600

# Performance
MAX_POSITIONS=10000
DEFAULT_SIMULATIONS=10000
N_WORKERS=4
```

## Dependencies

- **numpy**: Numerical computations
- **pandas**: Data manipulation
- **scipy**: Statistical functions, optimization
- **fastapi**: API framework
- **redis**: Caching layer
- **pydantic**: Data validation

## Installation

```bash
pip install numpy pandas scipy fastapi redis pydantic
```

## Usage Example

```python
from risk_engine.calculations import PortfolioAnalytics, ValueAtRisk

# Initialize analytics
analytics = PortfolioAnalytics()

# Calculate portfolio VaR
var_result = analytics.calculate_var(
    positions=portfolio_positions,
    method='monte_carlo',
    confidence=0.99,
    horizon=1
)

print(f"VaR (99%, 1-day): ${var_result.var_99:,.2f}")
print(f"CVaR (99%, 1-day): ${var_result.cvar_99:,.2f}")
```

## License

Enterprise - DragonScope Financial Systems
