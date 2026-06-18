"""Quantitative analytics engine — Black-Scholes, VaR, portfolio metrics.

Pure Python implementation using only math and statistics stdlib modules.
No numpy/scipy dependency.
"""

import logging
import math
import random
import statistics
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normal distribution helpers (pure Python — no scipy)
# ---------------------------------------------------------------------------
def _norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal.

    Uses Abramowitz and Stegun approximation (formula 26.2.17).
    Accurate to ~1e-7.
    """
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    sign = 1.0 if x >= 0 else -1.0
    x = abs(x)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x / 2.0)
    return 0.5 * (1.0 + sign * y)


def _norm_pdf(x: float) -> float:
    """Probability density function for standard normal."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_ppf(p: float) -> float:
    """Percent point function (inverse CDF) for standard normal.

    Uses rational approximation by Peter Acklam.
    Accurate to ~1e-9 for 0.0 < p < 1.0.
    """
    if p <= 0.0:
        return -10.0
    if p >= 1.0:
        return 10.0

    # Coefficients
    a = [
        -3.969683028665376e+01,
        2.209460984245205e+02,
        -2.759285104469687e+02,
        1.383577518672690e+02,
        -3.066479806614716e+01,
        2.506628277459239e+00,
    ]
    b = [
        -5.447609879822406e+01,
        1.615858368580409e+02,
        -1.556989798598866e+02,
        6.680131188771972e+01,
        -1.328068155288572e+01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e+00,
        -2.549732539343734e+00,
        4.374664141464968e+00,
        2.938163982698783e+00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e+00,
        3.754408661907416e+00,
    ]

    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (
            ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        ) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    elif p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            ((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]
        ) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(
            ((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]
        ) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class GreeksResult:
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


# ---------------------------------------------------------------------------
# Quant Engine
# ---------------------------------------------------------------------------
class QuantEngine:
    """Pure-Python quantitative analytics engine."""

    @staticmethod
    def black_scholes(
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        vol: float,
        option_type: str,
    ) -> tuple[float, dict]:
        """Black-Scholes option pricing with Greeks.

        Args:
            spot: Current price of the underlying asset.
            strike: Option strike price.
            time_to_expiry: Time to expiry in years (must be > 0).
            rate: Risk-free interest rate (annualized, e.g. 0.05 for 5%).
            vol: Volatility (annualized, e.g. 0.20 for 20%).
            option_type: "call" or "put".

        Returns:
            Tuple of (price, greeks_dict).
        """
        if time_to_expiry <= 0:
            # At expiry — intrinsic value only
            if option_type == "call":
                price = max(spot - strike, 0.0)
            else:
                price = max(strike - spot, 0.0)
            return price, {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}

        T = time_to_expiry
        sqrt_T = math.sqrt(T)

        d1 = (math.log(spot / strike) + (rate + 0.5 * vol * vol) * T) / (vol * sqrt_T)
        d2 = d1 - vol * sqrt_T

        discount = math.exp(-rate * T)

        if option_type == "call":
            price = spot * _norm_cdf(d1) - strike * discount * _norm_cdf(d2)
        else:
            price = strike * discount * _norm_cdf(-d2) - spot * _norm_cdf(-d1)

        greeks = QuantEngine.calculate_greeks(spot, strike, T, rate, vol, option_type)
        return price, greeks

    @staticmethod
    def calculate_greeks(
        spot: float,
        strike: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
    ) -> dict:
        """Calculate option Greeks.

        Returns:
            Dict with keys: delta, gamma, theta, vega, rho.
        """
        if T <= 0:
            return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}

        sqrt_T = math.sqrt(T)
        d1 = (math.log(spot / strike) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T

        discount = math.exp(-r * T)
        pdf_d1 = _norm_pdf(d1)

        # Gamma and Vega are the same for calls and puts
        gamma = pdf_d1 / (spot * sigma * sqrt_T)
        vega = spot * pdf_d1 * sqrt_T / 100.0  # per 1% vol change

        if option_type == "call":
            delta = _norm_cdf(d1)
            theta = (
                -(spot * pdf_d1 * sigma) / (2.0 * sqrt_T)
                - r * strike * discount * _norm_cdf(d2)
            ) / 365.0  # per calendar day
            rho = strike * T * discount * _norm_cdf(d2) / 100.0  # per 1% rate change
        else:
            delta = _norm_cdf(d1) - 1.0
            theta = (
                -(spot * pdf_d1 * sigma) / (2.0 * sqrt_T)
                + r * strike * discount * _norm_cdf(-d2)
            ) / 365.0
            rho = -strike * T * discount * _norm_cdf(-d2) / 100.0

        return {
            "delta": round(delta, 6),
            "gamma": round(gamma, 6),
            "theta": round(theta, 6),
            "vega": round(vega, 6),
            "rho": round(rho, 6),
        }

    @staticmethod
    def monte_carlo_var(
        returns: list[float],
        confidence: float = 0.95,
        horizon: int = 1,
        num_sims: int = 10000,
    ) -> tuple[float, float]:
        """Monte Carlo Value at Risk.

        Simulates future portfolio values using historical return distribution.

        Returns:
            Tuple of (VaR, CVaR) as positive loss values.
        """
        if len(returns) < 2:
            return 0.0, 0.0

        mu = statistics.mean(returns)
        sigma = statistics.stdev(returns)

        if sigma == 0:
            return 0.0, 0.0

        # Simulate cumulative returns over the horizon
        simulated_returns: list[float] = []
        rng = random.Random(42)  # deterministic seed for reproducibility

        for _ in range(num_sims):
            cumulative = 0.0
            for _ in range(horizon):
                # Generate standard normal via Box-Muller
                u1 = rng.random()
                u2 = rng.random()
                # Guard against log(0)
                u1 = max(u1, 1e-15)
                z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
                daily_return = mu + sigma * z
                cumulative += daily_return
            simulated_returns.append(cumulative)

        # Sort losses (negative returns)
        simulated_returns.sort()

        # VaR: the loss at the confidence percentile
        var_index = int((1.0 - confidence) * num_sims)
        var_index = max(0, min(var_index, num_sims - 1))
        var_value = -simulated_returns[var_index]

        # CVaR: expected loss beyond VaR (expected shortfall)
        tail = simulated_returns[: var_index + 1]
        cvar_value = -statistics.mean(tail) if tail else var_value

        return round(max(var_value, 0.0), 6), round(max(cvar_value, 0.0), 6)

    @staticmethod
    def historical_var(
        returns: list[float],
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """Historical Value at Risk.

        Uses actual historical returns to estimate VaR at given confidence.

        Returns:
            Tuple of (VaR, CVaR) as positive loss values.
        """
        if len(returns) < 2:
            return 0.0, 0.0

        sorted_returns = sorted(returns)
        n = len(sorted_returns)

        var_index = int((1.0 - confidence) * n)
        var_index = max(0, min(var_index, n - 1))
        var_value = -sorted_returns[var_index]

        tail = sorted_returns[: var_index + 1]
        cvar_value = -statistics.mean(tail) if tail else var_value

        return round(max(var_value, 0.0), 6), round(max(cvar_value, 0.0), 6)

    @staticmethod
    def parametric_var(
        mean: float,
        std: float,
        confidence: float = 0.95,
        horizon: int = 1,
    ) -> tuple[float, float]:
        """Parametric (Gaussian) Value at Risk.

        Returns:
            Tuple of (VaR, CVaR) as positive loss values.
        """
        if std <= 0:
            return 0.0, 0.0

        z = _norm_ppf(confidence)
        sqrt_h = math.sqrt(horizon)

        var_value = -(mean * horizon - z * std * sqrt_h)

        # CVaR for normal distribution: mu*h + sigma*sqrt(h) * phi(z) / (1-alpha)
        cvar_value = -(mean * horizon) + std * sqrt_h * _norm_pdf(z) / (1.0 - confidence)

        return round(max(var_value, 0.0), 6), round(max(cvar_value, 0.0), 6)

    @staticmethod
    def portfolio_metrics(
        returns_matrix: list[list[float]],
        weights: list[float],
    ) -> dict:
        """Compute portfolio risk metrics.

        Args:
            returns_matrix: List of return series per asset.
                            Each inner list is a time series of returns for one asset.
            weights: Portfolio weights (should sum to ~1.0).

        Returns:
            Dict with sharpe_ratio, sortino_ratio, calmar_ratio,
            max_drawdown, annualized_return, annualized_vol.
        """
        if not returns_matrix or not weights:
            return {
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "max_drawdown": 0.0,
                "annualized_return": 0.0,
                "annualized_vol": 0.0,
            }

        n_assets = len(returns_matrix)
        n_periods = min(len(r) for r in returns_matrix) if returns_matrix else 0

        if n_periods < 2 or n_assets != len(weights):
            return {
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "max_drawdown": 0.0,
                "annualized_return": 0.0,
                "annualized_vol": 0.0,
            }

        # Compute portfolio returns
        portfolio_returns: list[float] = []
        for t in range(n_periods):
            r = sum(weights[i] * returns_matrix[i][t] for i in range(n_assets))
            portfolio_returns.append(r)

        mean_ret = statistics.mean(portfolio_returns)
        std_ret = statistics.stdev(portfolio_returns)

        # Annualize (assume daily data, 252 trading days)
        annualized_return = mean_ret * 252
        annualized_vol = std_ret * math.sqrt(252) if std_ret > 0 else 0.0

        # Sharpe ratio (assume risk-free = 0 for simplicity)
        sharpe_ratio = (annualized_return / annualized_vol) if annualized_vol > 0 else 0.0

        # Sortino ratio (downside deviation)
        downside = [r for r in portfolio_returns if r < 0]
        if len(downside) >= 2:
            downside_std = math.sqrt(sum(d * d for d in downside) / len(downside))
            annualized_downside = downside_std * math.sqrt(252)
            sortino_ratio = (annualized_return / annualized_downside) if annualized_downside > 0 else 0.0
        else:
            sortino_ratio = 0.0

        # Max drawdown
        cumulative = 1.0
        peak = 1.0
        max_drawdown = 0.0
        for r in portfolio_returns:
            cumulative *= (1.0 + r)
            if cumulative > peak:
                peak = cumulative
            dd = (peak - cumulative) / peak if peak > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = dd

        # Calmar ratio
        calmar_ratio = (annualized_return / max_drawdown) if max_drawdown > 0 else 0.0

        return {
            "sharpe_ratio": round(sharpe_ratio, 6),
            "sortino_ratio": round(sortino_ratio, 6),
            "calmar_ratio": round(calmar_ratio, 6),
            "max_drawdown": round(max_drawdown, 6),
            "annualized_return": round(annualized_return, 6),
            "annualized_vol": round(annualized_vol, 6),
        }

    @staticmethod
    def covariance_matrix(returns_matrix: list[list[float]]) -> list[list[float]]:
        """Compute the covariance matrix from a returns matrix.

        Args:
            returns_matrix: List of return series per asset.

        Returns:
            2D list representing the covariance matrix.
        """
        n = len(returns_matrix)
        if n == 0:
            return []

        min_len = min(len(r) for r in returns_matrix)
        if min_len < 2:
            return [[0.0] * n for _ in range(n)]

        # Trim all series to the same length
        trimmed = [series[:min_len] for series in returns_matrix]
        means = [statistics.mean(s) for s in trimmed]

        cov = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i, n):
                cov_ij = sum(
                    (trimmed[i][t] - means[i]) * (trimmed[j][t] - means[j])
                    for t in range(min_len)
                ) / (min_len - 1)
                cov[i][j] = round(cov_ij, 10)
                cov[j][i] = cov[i][j]

        return cov

    @staticmethod
    def interpolate_yield_curve(
        tenors: list[float],
        rates: list[float],
        target_tenor: float,
    ) -> float:
        """Linear interpolation on a yield curve.

        Args:
            tenors: Sorted list of tenors in years (e.g., [0.083, 0.25, 0.5, 1.0, ...]).
            rates: Corresponding rates for each tenor.
            target_tenor: The tenor to interpolate.

        Returns:
            Interpolated rate.
        """
        if not tenors or not rates or len(tenors) != len(rates):
            return 0.0

        # Clamp to boundary values
        if target_tenor <= tenors[0]:
            return rates[0]
        if target_tenor >= tenors[-1]:
            return rates[-1]

        # Find bracketing tenors
        for i in range(len(tenors) - 1):
            if tenors[i] <= target_tenor <= tenors[i + 1]:
                # Linear interpolation
                t0, t1 = tenors[i], tenors[i + 1]
                r0, r1 = rates[i], rates[i + 1]
                if t1 == t0:
                    return r0
                weight = (target_tenor - t0) / (t1 - t0)
                return round(r0 + weight * (r1 - r0), 6)

        return rates[-1]
