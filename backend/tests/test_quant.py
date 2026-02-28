"""Tests for Quantitative Analytics Engine."""

import math

import pytest

from app.services.quant_engine import QuantEngine


# ---------------------------------------------------------------------------
# Black-Scholes pricing
# ---------------------------------------------------------------------------
class TestBlackScholes:
    """Test Black-Scholes option pricing and Greeks."""

    def test_call_price_positive(self):
        """A call option should have a positive price."""
        price, greeks = QuantEngine.black_scholes(
            spot=100, strike=100, time_to_expiry=1.0,
            rate=0.05, vol=0.20, option_type="call",
        )
        assert price > 0
        # ATM call with 1Y to expiry, 20% vol, 5% rate should be roughly ~10
        assert 5.0 < price < 20.0

    def test_put_price_positive(self):
        """A put option should have a positive price."""
        price, greeks = QuantEngine.black_scholes(
            spot=100, strike=100, time_to_expiry=1.0,
            rate=0.05, vol=0.20, option_type="put",
        )
        assert price > 0
        assert 3.0 < price < 15.0

    def test_put_call_parity(self):
        """Put-Call parity: C - P = S - K * exp(-rT)."""
        spot, strike, T, r, vol = 100, 100, 1.0, 0.05, 0.20
        call_price, _ = QuantEngine.black_scholes(spot, strike, T, r, vol, "call")
        put_price, _ = QuantEngine.black_scholes(spot, strike, T, r, vol, "put")
        expected_diff = spot - strike * math.exp(-r * T)
        assert abs((call_price - put_price) - expected_diff) < 0.01

    def test_deep_itm_call(self):
        """Deep in-the-money call should be close to intrinsic value."""
        price, _ = QuantEngine.black_scholes(
            spot=200, strike=100, time_to_expiry=0.01,
            rate=0.05, vol=0.20, option_type="call",
        )
        assert price > 99.0  # intrinsic = 100

    def test_deep_otm_call(self):
        """Deep out-of-the-money call should be near zero."""
        price, _ = QuantEngine.black_scholes(
            spot=50, strike=200, time_to_expiry=0.1,
            rate=0.05, vol=0.20, option_type="call",
        )
        assert price < 0.01

    def test_greeks_call(self):
        """Call Greeks should be in expected ranges."""
        _, greeks = QuantEngine.black_scholes(
            spot=100, strike=100, time_to_expiry=1.0,
            rate=0.05, vol=0.20, option_type="call",
        )
        assert 0.0 < greeks["delta"] < 1.0  # call delta 0..1
        assert greeks["gamma"] > 0  # gamma always positive
        assert greeks["theta"] < 0  # time decay is negative for long options
        assert greeks["vega"] > 0   # vega positive

    def test_greeks_put(self):
        """Put Greeks should be in expected ranges."""
        _, greeks = QuantEngine.black_scholes(
            spot=100, strike=100, time_to_expiry=1.0,
            rate=0.05, vol=0.20, option_type="put",
        )
        assert -1.0 < greeks["delta"] < 0.0  # put delta -1..0
        assert greeks["gamma"] > 0
        assert greeks["rho"] < 0  # put rho is negative

    def test_at_expiry(self):
        """At expiry, option should return intrinsic value."""
        call_price, _ = QuantEngine.black_scholes(
            spot=110, strike=100, time_to_expiry=0,
            rate=0.05, vol=0.20, option_type="call",
        )
        assert abs(call_price - 10.0) < 0.01

        put_price, _ = QuantEngine.black_scholes(
            spot=90, strike=100, time_to_expiry=0,
            rate=0.05, vol=0.20, option_type="put",
        )
        assert abs(put_price - 10.0) < 0.01


# ---------------------------------------------------------------------------
# Value at Risk
# ---------------------------------------------------------------------------
class TestVaR:
    """Test Value at Risk calculations."""

    @pytest.fixture
    def sample_returns(self):
        """Generate sample returns for testing."""
        import random
        rng = random.Random(42)
        return [rng.gauss(0.0005, 0.02) for _ in range(500)]

    def test_historical_var_positive(self, sample_returns):
        """Historical VaR should be positive."""
        var, cvar = QuantEngine.historical_var(sample_returns, 0.95)
        assert var >= 0
        assert cvar >= 0

    def test_cvar_greater_or_equal_var(self, sample_returns):
        """CVaR (Expected Shortfall) should be >= VaR."""
        var, cvar = QuantEngine.historical_var(sample_returns, 0.95)
        assert cvar >= var or abs(cvar - var) < 0.0001

    def test_parametric_var_positive(self):
        """Parametric VaR should be positive for typical portfolio."""
        var, cvar = QuantEngine.parametric_var(
            mean=0.0005, std=0.02, confidence=0.95, horizon=1,
        )
        assert var >= 0
        assert cvar >= 0

    def test_parametric_var_horizon_scaling(self):
        """Longer horizon should generally produce larger VaR."""
        var_1, _ = QuantEngine.parametric_var(mean=0.0, std=0.02, confidence=0.95, horizon=1)
        var_10, _ = QuantEngine.parametric_var(mean=0.0, std=0.02, confidence=0.95, horizon=10)
        assert var_10 > var_1

    def test_monte_carlo_var_positive(self, sample_returns):
        """Monte Carlo VaR should be positive."""
        var, cvar = QuantEngine.monte_carlo_var(
            sample_returns, confidence=0.95, horizon=1, num_sims=5000,
        )
        assert var >= 0
        assert cvar >= 0

    def test_higher_confidence_higher_var(self, sample_returns):
        """Higher confidence level should produce higher VaR."""
        var_90, _ = QuantEngine.historical_var(sample_returns, 0.90)
        var_99, _ = QuantEngine.historical_var(sample_returns, 0.99)
        assert var_99 >= var_90

    def test_empty_returns(self):
        """Empty returns should return zero."""
        var, cvar = QuantEngine.historical_var([], 0.95)
        assert var == 0.0
        assert cvar == 0.0


# ---------------------------------------------------------------------------
# Portfolio Metrics
# ---------------------------------------------------------------------------
class TestPortfolioMetrics:
    """Test portfolio risk metric calculations."""

    @pytest.fixture
    def sample_portfolio(self):
        """Generate sample portfolio return data."""
        import random
        rng = random.Random(42)
        asset1 = [rng.gauss(0.001, 0.015) for _ in range(252)]
        asset2 = [rng.gauss(0.0005, 0.02) for _ in range(252)]
        asset3 = [rng.gauss(0.0008, 0.01) for _ in range(252)]
        return {
            "returns_matrix": [asset1, asset2, asset3],
            "weights": [0.4, 0.35, 0.25],
        }

    def test_sharpe_ratio_reasonable(self, sample_portfolio):
        """Sharpe ratio should be within reasonable bounds."""
        metrics = QuantEngine.portfolio_metrics(
            sample_portfolio["returns_matrix"],
            sample_portfolio["weights"],
        )
        assert -5.0 < metrics["sharpe_ratio"] < 5.0

    def test_max_drawdown_bounded(self, sample_portfolio):
        """Max drawdown should be between 0 and 1."""
        metrics = QuantEngine.portfolio_metrics(
            sample_portfolio["returns_matrix"],
            sample_portfolio["weights"],
        )
        assert 0.0 <= metrics["max_drawdown"] <= 1.0

    def test_annualized_vol_positive(self, sample_portfolio):
        """Annualized volatility should be positive."""
        metrics = QuantEngine.portfolio_metrics(
            sample_portfolio["returns_matrix"],
            sample_portfolio["weights"],
        )
        assert metrics["annualized_vol"] > 0

    def test_sortino_ratio_present(self, sample_portfolio):
        """Sortino ratio should be calculated."""
        metrics = QuantEngine.portfolio_metrics(
            sample_portfolio["returns_matrix"],
            sample_portfolio["weights"],
        )
        assert "sortino_ratio" in metrics

    def test_empty_input(self):
        """Empty inputs should return zeroed metrics."""
        metrics = QuantEngine.portfolio_metrics([], [])
        assert metrics["sharpe_ratio"] == 0.0
        assert metrics["max_drawdown"] == 0.0


# ---------------------------------------------------------------------------
# Covariance Matrix
# ---------------------------------------------------------------------------
class TestCovarianceMatrix:
    """Test covariance matrix computation."""

    def test_symmetric(self):
        """Covariance matrix should be symmetric."""
        returns = [
            [0.01, -0.02, 0.03, 0.01, -0.01],
            [-0.01, 0.02, -0.01, 0.03, 0.01],
        ]
        cov = QuantEngine.covariance_matrix(returns)
        assert len(cov) == 2
        assert len(cov[0]) == 2
        assert abs(cov[0][1] - cov[1][0]) < 1e-10

    def test_diagonal_positive(self):
        """Diagonal elements (variances) should be non-negative."""
        import random
        rng = random.Random(42)
        returns = [
            [rng.gauss(0, 0.01) for _ in range(50)],
            [rng.gauss(0, 0.02) for _ in range(50)],
            [rng.gauss(0, 0.015) for _ in range(50)],
        ]
        cov = QuantEngine.covariance_matrix(returns)
        for i in range(3):
            assert cov[i][i] >= 0

    def test_single_asset(self):
        """Single asset should return 1x1 matrix."""
        returns = [[0.01, -0.02, 0.03, 0.01]]
        cov = QuantEngine.covariance_matrix(returns)
        assert len(cov) == 1
        assert len(cov[0]) == 1
        assert cov[0][0] > 0


# ---------------------------------------------------------------------------
# Yield Curve Interpolation
# ---------------------------------------------------------------------------
class TestYieldCurveInterpolation:
    """Test yield curve interpolation."""

    def test_exact_tenor(self):
        """Exact tenor match should return the exact rate."""
        tenors = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
        rates = [4.5, 4.6, 4.7, 4.3, 4.1, 4.0]
        result = QuantEngine.interpolate_yield_curve(tenors, rates, 2.0)
        assert abs(result - 4.3) < 0.001

    def test_interpolation_between(self):
        """Interpolated value should be between bracketing rates."""
        tenors = [1.0, 2.0, 5.0, 10.0]
        rates = [4.0, 3.8, 3.5, 3.6]
        result = QuantEngine.interpolate_yield_curve(tenors, rates, 3.0)
        # Between 3.8 and 3.5
        assert 3.4 < result < 3.9

    def test_below_minimum(self):
        """Below minimum tenor should return first rate."""
        tenors = [0.25, 0.5, 1.0]
        rates = [4.5, 4.6, 4.7]
        result = QuantEngine.interpolate_yield_curve(tenors, rates, 0.1)
        assert abs(result - 4.5) < 0.001

    def test_above_maximum(self):
        """Above maximum tenor should return last rate."""
        tenors = [0.25, 0.5, 1.0]
        rates = [4.5, 4.6, 4.7]
        result = QuantEngine.interpolate_yield_curve(tenors, rates, 5.0)
        assert abs(result - 4.7) < 0.001
