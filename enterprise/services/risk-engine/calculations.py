"""
DragonScope Risk Analytics Engine - Core Calculations

High-performance portfolio risk calculations using vectorized numpy operations
for sub-second performance on large portfolios.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Callable
from dataclasses import dataclass
from enum import Enum
from scipy import stats, optimize
from scipy.linalg import cholesky, inv
import warnings
from functools import lru_cache
import hashlib
import json

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')


class VaRMethod(Enum):
    """Value at Risk calculation methodologies."""
    PARAMETRIC = "parametric"
    HISTORICAL = "historical"
    MONTE_CARLO = "monte_carlo"


@dataclass
class VaRResult:
    """Container for VaR calculation results."""
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    method: VaRMethod
    confidence_level: float
    time_horizon: int
    n_simulations: Optional[int] = None
    calculation_time_ms: Optional[float] = None
    
    def to_dict(self) -> Dict:
        """Convert result to dictionary."""
        return {
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "cvar_99": self.cvar_99,
            "method": self.method.value,
            "confidence_level": self.confidence_level,
            "time_horizon": self.time_horizon,
            "n_simulations": self.n_simulations,
            "calculation_time_ms": self.calculation_time_ms
        }


@dataclass
class GreeksResult:
    """Container for option Greeks calculation results."""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    vanna: Optional[float] = None
    charm: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "delta": self.delta,
            "gamma": self.gamma,
            "theta": self.theta,
            "vega": self.vega,
            "rho": self.rho,
            "vanna": self.vanna,
            "charm": self.charm
        }


@dataclass
class FactorExposureResult:
    """Container for factor exposure analysis results."""
    factor_betas: Dict[str, float]
    factor_r_squared: float
    specific_risk: float
    systematic_risk: float
    total_risk: float
    factor_contributions: Dict[str, float]
    
    def to_dict(self) -> Dict:
        return {
            "factor_betas": self.factor_betas,
            "factor_r_squared": self.factor_r_squared,
            "specific_risk": self.specific_risk,
            "systematic_risk": self.systematic_risk,
            "total_risk": self.total_risk,
            "factor_contributions": self.factor_contributions
        }


@dataclass
class StressTestResult:
    """Container for stress test results."""
    scenario_name: str
    portfolio_value_before: float
    portfolio_value_after: float
    pnl_impact: float
    pnl_impact_pct: float
    position_impacts: Dict[str, Dict]
    risk_metrics_before: Dict
    risk_metrics_after: Dict
    
    def to_dict(self) -> Dict:
        return {
            "scenario_name": self.scenario_name,
            "portfolio_value_before": self.portfolio_value_before,
            "portfolio_value_after": self.portfolio_value_after,
            "pnl_impact": self.pnl_impact,
            "pnl_impact_pct": self.pnl_impact_pct,
            "position_impacts": self.position_impacts,
            "risk_metrics_before": self.risk_metrics_before,
            "risk_metrics_after": self.risk_metrics_after
        }


class PortfolioAnalytics:
    """
    High-performance portfolio analytics engine.
    
    Optimized for portfolios up to 10,000 positions with sub-second
    calculation times using vectorized numpy operations.
    """
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Initialize portfolio analytics engine.
        
        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculations
        """
        self.risk_free_rate = risk_free_rate
        self.var_calculator = ValueAtRisk()
        self.greeks_calculator = GreeksCalculator()
        self.factor_analyzer = FactorExposure()
        self.stress_engine = StressTest()
    
    def calculate_returns(
        self,
        prices: pd.DataFrame,
        method: str = "log"
    ) -> pd.DataFrame:
        """
        Calculate returns from price series.
        
        Args:
            prices: DataFrame of prices (dates x assets)
            method: 'log' for log returns, 'simple' for simple returns
            
        Returns:
            DataFrame of returns
        """
        if method == "log":
            return np.log(prices / prices.shift(1)).dropna()
        else:
            return prices.pct_change().dropna()
    
    def calculate_sharpe_ratio(
        self,
        returns: Union[pd.Series, np.ndarray],
        periods_per_year: int = 252
    ) -> float:
        """
        Calculate annualized Sharpe ratio.
        
        Args:
            returns: Array of returns
            periods_per_year: Number of periods in a year
            
        Returns:
            Annualized Sharpe ratio
        """
        returns = np.asarray(returns)
        excess_returns = returns - self.risk_free_rate / periods_per_year
        
        if len(returns) < 2:
            return 0.0
            
        return np.mean(excess_returns) / np.std(returns) * np.sqrt(periods_per_year)
    
    def calculate_sortino_ratio(
        self,
        returns: Union[pd.Series, np.ndarray],
        periods_per_year: int = 252,
        target_return: float = 0.0
    ) -> float:
        """
        Calculate Sortino ratio (downside risk adjusted).
        
        Args:
            returns: Array of returns
            periods_per_year: Number of periods in a year
            target_return: Minimum acceptable return
            
        Returns:
            Annualized Sortino ratio
        """
        returns = np.asarray(returns)
        excess_returns = returns - self.risk_free_rate / periods_per_year
        
        # Downside deviation
        downside_returns = np.where(returns < target_return, returns - target_return, 0)
        downside_std = np.sqrt(np.mean(downside_returns ** 2))
        
        if downside_std == 0:
            return np.inf if np.mean(excess_returns) > 0 else 0.0
            
        return np.mean(excess_returns) / downside_std * np.sqrt(periods_per_year)
    
    def calculate_beta(
        self,
        returns: Union[pd.Series, np.ndarray],
        market_returns: Union[pd.Series, np.ndarray]
    ) -> float:
        """
        Calculate portfolio beta relative to market.
        
        Args:
            returns: Portfolio returns
            market_returns: Market benchmark returns
            
        Returns:
            Beta coefficient
        """
        returns = np.asarray(returns)
        market_returns = np.asarray(market_returns)
        
        if len(returns) != len(market_returns):
            min_len = min(len(returns), len(market_returns))
            returns = returns[-min_len:]
            market_returns = market_returns[-min_len:]
        
        covariance = np.cov(returns, market_returns)[0, 1]
        market_variance = np.var(market_returns)
        
        if market_variance == 0:
            return 0.0
            
        return covariance / market_variance
    
    def calculate_tracking_error(
        self,
        returns: Union[pd.Series, np.ndarray],
        benchmark_returns: Union[pd.Series, np.ndarray],
        annualize: bool = True
    ) -> float:
        """
        Calculate tracking error (active risk).
        
        Args:
            returns: Portfolio returns
            benchmark_returns: Benchmark returns
            annualize: Whether to annualize the result
            
        Returns:
            Tracking error
        """
        returns = np.asarray(returns)
        benchmark_returns = np.asarray(benchmark_returns)
        
        if len(returns) != len(benchmark_returns):
            min_len = min(len(returns), len(benchmark_returns))
            returns = returns[-min_len:]
            benchmark_returns = benchmark_returns[-min_len:]
        
        active_returns = returns - benchmark_returns
        tracking_error = np.std(active_returns)
        
        if annualize:
            tracking_error *= np.sqrt(252)
            
        return tracking_error
    
    def calculate_portfolio_volatility(
        self,
        weights: np.ndarray,
        covariance_matrix: np.ndarray,
        annualize: bool = True
    ) -> float:
        """
        Calculate portfolio volatility from weights and covariance.
        
        Args:
            weights: Portfolio weights (sum to 1)
            covariance_matrix: Covariance matrix of returns
            annualize: Whether to annualize
            
        Returns:
            Portfolio volatility
        """
        variance = np.dot(weights.T, np.dot(covariance_matrix, weights))
        volatility = np.sqrt(variance)
        
        if annualize:
            volatility *= np.sqrt(252)
            
        return volatility
    
    def calculate_var(
        self,
        positions: Dict[str, Dict],
        method: VaRMethod = VaRMethod.MONTE_CARLO,
        confidence_level: float = 0.95,
        time_horizon: int = 1,
        n_simulations: int = 10000,
        historical_data: Optional[pd.DataFrame] = None
    ) -> VaRResult:
        """
        Calculate Value at Risk for a portfolio.
        
        Args:
            positions: Dict of position_id -> {quantity, price, volatility, ...}
            method: VaR calculation method
            confidence_level: Confidence level (e.g., 0.95)
            time_horizon: Time horizon in days
            n_simulations: Number of Monte Carlo simulations
            historical_data: Historical returns DataFrame
            
        Returns:
            VaRResult object with VaR and CVaR values
        """
        return self.var_calculator.calculate(
            positions=positions,
            method=method,
            confidence_level=confidence_level,
            time_horizon=time_horizon,
            n_simulations=n_simulations,
            historical_data=historical_data
        )
    
    def calculate_greeks(
        self,
        option_type: str,
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> GreeksResult:
        """
        Calculate option Greeks.
        
        Args:
            option_type: 'call' or 'put'
            spot: Current underlying price
            strike: Option strike price
            time_to_expiry: Time to expiration in years
            risk_free_rate: Risk-free interest rate
            volatility: Implied volatility
            dividend_yield: Continuous dividend yield
            
        Returns:
            GreeksResult with all Greek values
        """
        return self.greeks_calculator.calculate(
            option_type=option_type,
            spot=spot,
            strike=strike,
            time_to_expiry=time_to_expiry,
            risk_free_rate=risk_free_rate,
            volatility=volatility,
            dividend_yield=dividend_yield
        )
    
    def calculate_factor_exposure(
        self,
        returns: pd.DataFrame,
        factor_returns: pd.DataFrame,
        weights: Optional[np.ndarray] = None
    ) -> FactorExposureResult:
        """
        Calculate portfolio factor exposures.
        
        Args:
            returns: Asset returns DataFrame
            factor_returns: Factor returns DataFrame
            weights: Portfolio weights (if None, equal weighted)
            
        Returns:
            FactorExposureResult with betas and risk decomposition
        """
        return self.factor_analyzer.calculate(
            returns=returns,
            factor_returns=factor_returns,
            weights=weights
        )
    
    def run_stress_test(
        self,
        positions: Dict[str, Dict],
        scenario: Dict,
        current_prices: Dict[str, float]
    ) -> StressTestResult:
        """
        Run stress test on portfolio.
        
        Args:
            positions: Portfolio positions
            scenario: Stress scenario definition
            current_prices: Current market prices
            
        Returns:
            StressTestResult with impact analysis
        """
        return self.stress_engine.run(
            positions=positions,
            scenario=scenario,
            current_prices=current_prices,
            analytics=self
        )


class ValueAtRisk:
    """
    Value at Risk calculator supporting multiple methodologies.
    
    Optimized for performance using vectorized numpy operations.
    """
    
    def __init__(self, random_seed: Optional[int] = 42):
        """
        Initialize VaR calculator.
        
        Args:
            random_seed: Seed for reproducible Monte Carlo simulations
        """
        self.random_seed = random_seed
        self._rng = np.random.RandomState(random_seed)
    
    def calculate(
        self,
        positions: Dict[str, Dict],
        method: VaRMethod = VaRMethod.MONTE_CARLO,
        confidence_level: float = 0.95,
        time_horizon: int = 1,
        n_simulations: int = 10000,
        historical_data: Optional[pd.DataFrame] = None
    ) -> VaRResult:
        """
        Calculate VaR using specified method.
        
        Args:
            positions: Dict of positions with quantities, prices, volatilities
            method: VaRMethod enum
            confidence_level: Confidence level (0-1)
            time_horizon: Days
            n_simulations: For Monte Carlo
            historical_data: For historical simulation
            
        Returns:
            VaRResult
        """
        import time
        start_time = time.time()
        
        if method == VaRMethod.PARAMETRIC:
            result = self._parametric_var(
                positions, confidence_level, time_horizon
            )
        elif method == VaRMethod.HISTORICAL:
            result = self._historical_var(
                positions, confidence_level, time_horizon, historical_data
            )
        elif method == VaRMethod.MONTE_CARLO:
            result = self._monte_carlo_var(
                positions, confidence_level, time_horizon, n_simulations
            )
        else:
            raise ValueError(f"Unknown VaR method: {method}")
        
        calculation_time = (time.time() - start_time) * 1000
        result.calculation_time_ms = calculation_time
        
        return result
    
    def _parametric_var(
        self,
        positions: Dict[str, Dict],
        confidence_level: float,
        time_horizon: int
    ) -> VaRResult:
        """
        Calculate parametric (variance-covariance) VaR.
        
        Assumes normal distribution of returns.
        """
        # Extract position values and volatilities
        position_values = []
        volatilities = []
        
        for pos_id, pos in positions.items():
            quantity = pos.get('quantity', 0)
            price = pos.get('price', 0)
            volatility = pos.get('volatility', 0.2)  # Default 20%
            
            position_values.append(quantity * price)
            volatilities.append(volatility)
        
        position_values = np.array(position_values)
        volatilities = np.array(volatilities)
        
        # Portfolio value
        portfolio_value = np.sum(np.abs(position_values))
        
        # Portfolio variance (simplified - assumes zero correlation)
        position_variances = (position_values * volatilities) ** 2
        portfolio_variance = np.sum(position_variances)
        portfolio_volatility = np.sqrt(portfolio_variance)
        
        # Scale by time horizon
        time_scale = np.sqrt(time_horizon / 252)
        
        # Z-scores for confidence levels
        z_95 = stats.norm.ppf(0.95)
        z_99 = stats.norm.ppf(0.99)
        
        # Calculate VaR
        var_95 = portfolio_volatility * z_95 * time_scale
        var_99 = portfolio_volatility * z_99 * time_scale
        
        # CVaR (Expected Shortfall) for normal distribution
        # CVaR = σ * φ(z) / (1 - α)
        cvar_95 = portfolio_volatility * time_scale * stats.norm.pdf(z_95) / (1 - 0.95)
        cvar_99 = portfolio_volatility * time_scale * stats.norm.pdf(z_99) / (1 - 0.99)
        
        return VaRResult(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            method=VaRMethod.PARAMETRIC,
            confidence_level=confidence_level,
            time_horizon=time_horizon
        )
    
    def _historical_var(
        self,
        positions: Dict[str, Dict],
        confidence_level: float,
        time_horizon: int,
        historical_data: Optional[pd.DataFrame]
    ) -> VaRResult:
        """
        Calculate historical simulation VaR.
        
        Uses actual historical returns to simulate P&L distribution.
        """
        if historical_data is None or historical_data.empty:
            # Fallback to parametric if no historical data
            return self._parametric_var(positions, confidence_level, time_horizon)
        
        # Build position weights
        position_values = []
        asset_ids = []
        
        for pos_id, pos in positions.items():
            quantity = pos.get('quantity', 0)
            price = pos.get('price', 0)
            position_values.append(quantity * price)
            asset_ids.append(pos.get('asset_id', pos_id))
        
        position_values = np.array(position_values)
        total_value = np.sum(np.abs(position_values))
        weights = position_values / total_value if total_value > 0 else np.zeros_like(position_values)
        
        # Filter historical data to relevant assets
        available_assets = [a for a in asset_ids if a in historical_data.columns]
        if len(available_assets) == 0:
            return self._parametric_var(positions, confidence_level, time_horizon)
        
        hist_returns = historical_data[available_assets].values
        
        # Calculate portfolio returns for each historical period
        portfolio_returns = np.dot(hist_returns, weights[:len(available_assets)])
        
        # Scale for time horizon
        if time_horizon > 1:
            # Square root rule for scaling
            portfolio_returns = portfolio_returns * np.sqrt(time_horizon)
        
        # Calculate VaR from empirical distribution
        var_95 = np.percentile(portfolio_returns, (1 - 0.95) * 100) * total_value
        var_99 = np.percentile(portfolio_returns, (1 - 0.99) * 100) * total_value
        
        # Calculate CVaR (average of returns beyond VaR)
        cvar_95 = np.mean(portfolio_returns[portfolio_returns <= var_95 / total_value]) * total_value
        cvar_99 = np.mean(portfolio_returns[portfolio_returns <= var_99 / total_value]) * total_value
        
        # Convert to absolute values (VaR is typically positive)
        var_95, var_99 = abs(var_95), abs(var_99)
        cvar_95, cvar_99 = abs(cvar_95), abs(cvar_99)
        
        return VaRResult(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            method=VaRMethod.HISTORICAL,
            confidence_level=confidence_level,
            time_horizon=time_horizon
        )
    
    def _monte_carlo_var(
        self,
        positions: Dict[str, Dict],
        confidence_level: float,
        time_horizon: int,
        n_simulations: int
    ) -> VaRResult:
        """
        Calculate Monte Carlo VaR.
        
        Simulates price paths using Geometric Brownian Motion.
        """
        # Extract position data
        position_values = []
        volatilities = []
        expected_returns = []
        
        for pos_id, pos in positions.items():
            quantity = pos.get('quantity', 0)
            price = pos.get('price', 0)
            volatility = pos.get('volatility', 0.2)
            expected_return = pos.get('expected_return', 0.0)
            
            position_values.append(quantity * price)
            volatilities.append(volatility)
            expected_returns.append(expected_return)
        
        position_values = np.array(position_values)
        volatilities = np.array(volatilities)
        expected_returns = np.array(expected_returns)
        
        total_value = np.sum(np.abs(position_values))
        weights = position_values / total_value if total_value > 0 else np.zeros_like(position_values)
        
        n_assets = len(positions)
        
        # Correlation matrix (simplified - identity if not provided)
        correlation = np.eye(n_assets)
        
        # Cholesky decomposition for correlated random variables
        try:
            chol = cholesky(correlation, lower=True)
        except np.linalg.LinAlgError:
            chol = np.eye(n_assets)
        
        # Generate random standard normal variables
        z = self._rng.standard_normal((n_simulations, n_assets))
        
        # Apply correlation
        correlated_z = np.dot(z, chol.T)
        
        # Time parameters
        dt = time_horizon / 252  # Trading days
        
        # Simulate returns using GBM
        # dS/S = μdt + σdW
        simulated_returns = (
            (expected_returns - 0.5 * volatilities**2) * dt +
            volatilities * np.sqrt(dt) * correlated_z
        )
        
        # Calculate portfolio returns
        portfolio_returns = np.dot(simulated_returns, weights)
        
        # Convert to P&L
        pnl = portfolio_returns * total_value
        
        # Calculate VaR
        var_95 = abs(np.percentile(pnl, (1 - 0.95) * 100))
        var_99 = abs(np.percentile(pnl, (1 - 0.99) * 100))
        
        # Calculate CVaR
        cvar_95 = abs(np.mean(pnl[pnl <= -var_95])) if np.any(pnl <= -var_95) else var_95
        cvar_99 = abs(np.mean(pnl[pnl <= -var_99])) if np.any(pnl <= -var_99) else var_99
        
        return VaRResult(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            method=VaRMethod.MONTE_CARLO,
            confidence_level=confidence_level,
            time_horizon=time_horizon,
            n_simulations=n_simulations
        )


class GreeksCalculator:
    """
    Option Greeks calculator using Black-Scholes model.
    
    Supports first and second-order Greeks for options risk management.
    """
    
    def calculate(
        self,
        option_type: str,
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float = 0.0
    ) -> GreeksResult:
        """
        Calculate all Greeks for an option.
        
        Args:
            option_type: 'call' or 'put'
            spot: Current underlying price
            strike: Strike price
            time_to_expiry: Time to expiration (years)
            risk_free_rate: Risk-free rate
            volatility: Implied volatility
            dividend_yield: Dividend yield
            
        Returns:
            GreeksResult
        """
        # Calculate d1 and d2
        d1 = self._calculate_d1(
            spot, strike, time_to_expiry, risk_free_rate, 
            volatility, dividend_yield
        )
        d2 = d1 - volatility * np.sqrt(time_to_expiry)
        
        # First-order Greeks
        delta = self._calculate_delta(
            option_type, d1, time_to_expiry, dividend_yield
        )
        theta = self._calculate_theta(
            option_type, spot, strike, time_to_expiry,
            risk_free_rate, volatility, dividend_yield, d1, d2
        )
        vega = self._calculate_vega(
            spot, time_to_expiry, d1, dividend_yield
        )
        rho = self._calculate_rho(
            option_type, strike, time_to_expiry, risk_free_rate, d2
        )
        
        # Second-order Greeks
        gamma = self._calculate_gamma(
            spot, time_to_expiry, volatility, d1, dividend_yield
        )
        
        # Advanced Greeks
        vanna = self._calculate_vanna(
            vega, spot, d1, volatility
        )
        charm = self._calculate_charm(
            option_type, spot, strike, time_to_expiry,
            risk_free_rate, volatility, dividend_yield, d1, d2
        )
        
        return GreeksResult(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
            vanna=vanna,
            charm=charm
        )
    
    def _calculate_d1(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float
    ) -> float:
        """Calculate d1 parameter for Black-Scholes."""
        if time_to_expiry <= 0 or volatility <= 0:
            return 0.0
        
        return (
            np.log(spot / strike) +
            (risk_free_rate - dividend_yield + 0.5 * volatility**2) * time_to_expiry
        ) / (volatility * np.sqrt(time_to_expiry))
    
    def _calculate_delta(
        self,
        option_type: str,
        d1: float,
        time_to_expiry: float,
        dividend_yield: float
    ) -> float:
        """Calculate option delta."""
        discount = np.exp(-dividend_yield * time_to_expiry)
        
        if option_type.lower() == 'call':
            return discount * stats.norm.cdf(d1)
        else:
            return discount * (stats.norm.cdf(d1) - 1)
    
    def _calculate_gamma(
        self,
        spot: float,
        time_to_expiry: float,
        volatility: float,
        d1: float,
        dividend_yield: float
    ) -> float:
        """Calculate option gamma."""
        if time_to_expiry <= 0 or spot <= 0:
            return 0.0
        
        discount = np.exp(-dividend_yield * time_to_expiry)
        return (
            discount * stats.norm.pdf(d1) /
            (spot * volatility * np.sqrt(time_to_expiry))
        )
    
    def _calculate_theta(
        self,
        option_type: str,
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float,
        d1: float,
        d2: float
    ) -> float:
        """Calculate option theta (per year)."""
        if time_to_expiry <= 0:
            return 0.0
        
        discount_div = np.exp(-dividend_yield * time_to_expiry)
        discount_rf = np.exp(-risk_free_rate * time_to_expiry)
        sqrt_t = np.sqrt(time_to_expiry)
        
        term1 = (
            -spot * discount_div * stats.norm.pdf(d1) * volatility /
            (2 * sqrt_t)
        )
        
        if option_type.lower() == 'call':
            term2 = risk_free_rate * strike * discount_rf * stats.norm.cdf(d2)
            term3 = -dividend_yield * spot * discount_div * stats.norm.cdf(d1)
        else:
            term2 = -risk_free_rate * strike * discount_rf * stats.norm.cdf(-d2)
            term3 = dividend_yield * spot * discount_div * stats.norm.cdf(-d1)
        
        # Return daily theta
        return (term1 + term2 + term3) / 365
    
    def _calculate_vega(
        self,
        spot: float,
        time_to_expiry: float,
        d1: float,
        dividend_yield: float
    ) -> float:
        """Calculate option vega (per 1% change in volatility)."""
        if time_to_expiry <= 0:
            return 0.0
        
        discount = np.exp(-dividend_yield * time_to_expiry)
        return spot * discount * stats.norm.pdf(d1) * np.sqrt(time_to_expiry) / 100
    
    def _calculate_rho(
        self,
        option_type: str,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        d2: float
    ) -> float:
        """Calculate option rho (per 1% change in rates)."""
        if time_to_expiry <= 0:
            return 0.0
        
        discount = np.exp(-risk_free_rate * time_to_expiry)
        
        if option_type.lower() == 'call':
            return strike * time_to_expiry * discount * stats.norm.cdf(d2) / 100
        else:
            return -strike * time_to_expiry * discount * stats.norm.cdf(-d2) / 100
    
    def _calculate_vanna(
        self,
        vega: float,
        spot: float,
        d1: float,
        volatility: float
    ) -> float:
        """Calculate vanna (d Vega / d Spot)."""
        if spot <= 0 or volatility <= 0:
            return 0.0
        return vega / spot * (1 - d1 / (volatility * np.sqrt(1)))  # Simplified
    
    def _calculate_charm(
        self,
        option_type: str,
        spot: float,
        strike: float,
        time_to_expiry: float,
        risk_free_rate: float,
        volatility: float,
        dividend_yield: float,
        d1: float,
        d2: float
    ) -> float:
        """Calculate charm (d Delta / d Time)."""
        if time_to_expiry <= 0:
            return 0.0
        
        discount = np.exp(-dividend_yield * time_to_expiry)
        sqrt_t = np.sqrt(time_to_expiry)
        
        term1 = -dividend_yield * discount * stats.norm.cdf(d1 if option_type == 'call' else d1 - 1)
        term2 = (
            discount * stats.norm.pdf(d1) *
            (2 * (risk_free_rate - dividend_yield) * time_to_expiry - d2 * volatility * sqrt_t) /
            (2 * time_to_expiry * volatility * sqrt_t)
        )
        
        return (term1 + term2) / 365


class FactorExposure:
    """
    Multi-factor risk model for portfolio factor exposure analysis.
    
    Supports Fama-French factors, custom macro factors, and statistical factors.
    """
    
    def __init__(self):
        """Initialize factor exposure analyzer."""
        self.fitted_models = {}
    
    def calculate(
        self,
        returns: pd.DataFrame,
        factor_returns: pd.DataFrame,
        weights: Optional[np.ndarray] = None
    ) -> FactorExposureResult:
        """
        Calculate portfolio factor exposures.
        
        Args:
            returns: Asset returns (dates x assets)
            factor_returns: Factor returns (dates x factors)
            weights: Portfolio weights
            
        Returns:
            FactorExposureResult
        """
        # Ensure aligned dates
        common_dates = returns.index.intersection(factor_returns.index)
        returns = returns.loc[common_dates]
        factor_returns = factor_returns.loc[common_dates]
        
        n_assets = returns.shape[1]
        
        # Default equal weights if not provided
        if weights is None:
            weights = np.ones(n_assets) / n_assets
        else:
            weights = np.array(weights)
        
        # Calculate factor betas for each asset using OLS
        factor_names = factor_returns.columns.tolist()
        X = factor_returns.values
        X = np.column_stack([np.ones(len(X)), X])  # Add intercept
        
        asset_betas = {}
        asset_r2 = []
        
        for i, asset in enumerate(returns.columns):
            y = returns.iloc[:, i].values
            
            # OLS: β = (X'X)^(-1) X'y
            try:
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                residuals = y - X @ beta
                ss_res = np.sum(residuals**2)
                ss_tot = np.sum((y - np.mean(y))**2)
                r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
                
                asset_betas[asset] = beta[1:]  # Exclude intercept
                asset_r2.append(r2)
            except np.linalg.LinAlgError:
                asset_betas[asset] = np.zeros(len(factor_names))
                asset_r2.append(0)
        
        # Calculate portfolio factor betas
        portfolio_betas = {}
        for i, factor in enumerate(factor_names):
            beta_values = [asset_betas[asset][i] for asset in returns.columns]
            portfolio_betas[factor] = np.dot(weights, beta_values)
        
        # Calculate portfolio R-squared
        portfolio_r2 = np.dot(weights, asset_r2)
        
        # Calculate risk decomposition
        factor_cov = factor_returns.cov().values
        factor_betas_array = np.array(list(portfolio_betas.values()))
        
        # Systematic risk (from factors)
        systematic_variance = factor_betas_array @ factor_cov @ factor_betas_array
        systematic_risk = np.sqrt(systematic_variance * 252)  # Annualized
        
        # Specific risk (idiosyncratic)
        total_asset_variance = returns.var().values
        specific_variance = np.dot(weights**2, total_asset_variance * (1 - np.array(asset_r2)))
        specific_risk = np.sqrt(specific_variance * 252)
        
        # Total risk
        total_risk = np.sqrt(systematic_risk**2 + specific_risk**2)
        
        # Factor contributions
        marginal_contributions = factor_cov @ factor_betas_array
        factor_contributions = {
            factor: portfolio_betas[factor] * marginal_contributions[i] / systematic_variance
            if systematic_variance > 0 else 0
            for i, factor in enumerate(factor_names)
        }
        
        return FactorExposureResult(
            factor_betas=portfolio_betas,
            factor_r_squared=portfolio_r2,
            specific_risk=specific_risk,
            systematic_risk=systematic_risk,
            total_risk=total_risk,
            factor_contributions=factor_contributions
        )
    
    def calculate_factor_correlation(
        self,
        factor_returns: pd.DataFrame
    ) -> pd.DataFrame:
        """Calculate factor correlation matrix."""
        return factor_returns.corr()
    
    def calculate_factor_volatility_attribution(
        self,
        factor_returns: pd.DataFrame,
        factor_betas: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate volatility attribution by factor."""
        factor_cov = factor_returns.cov()
        beta_array = np.array([factor_betas.get(f, 0) for f in factor_returns.columns])
        
        attributions = {}
        total_variance = beta_array @ factor_cov.values @ beta_array
        
        for i, factor in enumerate(factor_returns.columns):
            # Marginal contribution to variance
            mcv = beta_array[i] * (factor_cov.values[i] @ beta_array)
            attributions[factor] = mcv / total_variance if total_variance > 0 else 0
        
        return attributions


class StressTest:
    """
    Stress testing engine for scenario analysis.
    
    Supports historical scenarios, hypothetical scenarios, and
    sensitivity analysis.
    """
    
    # Predefined historical scenarios
    SCENARIOS = {
        "2008_financial_crisis": {
            "description": "Global Financial Crisis (2008)",
            "shocks": {
                "equity": -0.40,
                "credit_spread": 0.05,
                "volatility": 0.60,
                "interest_rate": -0.02
            }
        },
        "2020_covid_crash": {
            "description": "COVID-19 Market Crash (March 2020)",
            "shocks": {
                "equity": -0.34,
                "credit_spread": 0.04,
                "volatility": 0.80,
                "oil": -0.50
            }
        },
        "interest_rate_shock": {
            "description": "Rapid Interest Rate Increase",
            "shocks": {
                "interest_rate": 0.03,
                "equity": -0.15,
                "bond": -0.10
            }
        },
        "inflation_spike": {
            "description": "Unexpected Inflation Spike",
            "shocks": {
                "inflation": 0.03,
                "equity": -0.10,
                "bond": -0.08,
                "commodity": 0.20
            }
        }
    }
    
    def __init__(self):
        """Initialize stress test engine."""
        self.custom_scenarios = {}
    
    def run(
        self,
        positions: Dict[str, Dict],
        scenario: Dict,
        current_prices: Dict[str, float],
        analytics: Optional[PortfolioAnalytics] = None
    ) -> StressTestResult:
        """
        Run stress test on portfolio.
        
        Args:
            positions: Portfolio positions
            scenario: Stress scenario definition
            current_prices: Current market prices
            analytics: PortfolioAnalytics instance for metrics
            
        Returns:
            StressTestResult
        """
        scenario_name = scenario.get('name', 'Custom Scenario')
        shocks = scenario.get('shocks', {})
        
        # Calculate current portfolio value
        position_values_before = {}
        portfolio_value_before = 0.0
        
        for pos_id, pos in positions.items():
            asset_id = pos.get('asset_id', pos_id)
            quantity = pos.get('quantity', 0)
            price = current_prices.get(asset_id, pos.get('price', 0))
            
            value = quantity * price
            position_values_before[pos_id] = value
            portfolio_value_before += value
        
        # Apply shocks to calculate stressed values
        position_values_after = {}
        portfolio_value_after = 0.0
        position_impacts = {}
        
        for pos_id, pos in positions.items():
            asset_id = pos.get('asset_id', pos_id)
            asset_class = pos.get('asset_class', 'equity')
            quantity = pos.get('quantity', 0)
            price = current_prices.get(asset_id, pos.get('price', 0))
            
            # Get shock for asset class
            shock = shocks.get(asset_class, 0.0)
            
            # Apply shock
            stressed_price = price * (1 + shock)
            stressed_value = quantity * stressed_price
            
            position_values_after[pos_id] = stressed_value
            portfolio_value_after += stressed_value
            
            # Calculate impact
            pnl = stressed_value - position_values_before[pos_id]
            pnl_pct = (stressed_price / price - 1) * 100 if price > 0 else 0
            
            position_impacts[pos_id] = {
                "asset_id": asset_id,
                "asset_class": asset_class,
                "quantity": quantity,
                "price_before": price,
                "price_after": stressed_price,
                "value_before": position_values_before[pos_id],
                "value_after": stressed_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "shock_applied": shock
            }
        
        # Calculate overall P&L
        total_pnl = portfolio_value_after - portfolio_value_before
        total_pnl_pct = (total_pnl / abs(portfolio_value_before) * 100) if portfolio_value_before != 0 else 0
        
        # Calculate risk metrics before/after if analytics provided
        risk_metrics_before = {}
        risk_metrics_after = {}
        
        if analytics:
            try:
                # Simple volatility calculation for demonstration
                returns_before = np.array([0.001] * 100)  # Placeholder
                risk_metrics_before = {
                    "portfolio_value": portfolio_value_before,
                    "estimated_volatility": 0.15
                }
                risk_metrics_after = {
                    "portfolio_value": portfolio_value_after,
                    "estimated_volatility": 0.15 + shocks.get('volatility', 0)
                }
            except Exception:
                pass
        
        return StressTestResult(
            scenario_name=scenario_name,
            portfolio_value_before=portfolio_value_before,
            portfolio_value_after=portfolio_value_after,
            pnl_impact=total_pnl,
            pnl_impact_pct=total_pnl_pct,
            position_impacts=position_impacts,
            risk_metrics_before=risk_metrics_before,
            risk_metrics_after=risk_metrics_after
        )
    
    def get_predefined_scenarios(self) -> Dict[str, Dict]:
        """Get list of predefined stress test scenarios."""
        return self.SCENARIOS.copy()
    
    def add_custom_scenario(self, scenario_id: str, scenario: Dict) -> None:
        """Add a custom stress test scenario."""
        self.custom_scenarios[scenario_id] = scenario
    
    def run_sensitivity_analysis(
        self,
        positions: Dict[str, Dict],
        current_prices: Dict[str, float],
        factor: str,
        shock_range: Tuple[float, float, float] = (-0.3, 0.3, 0.05)
    ) -> List[Dict]:
        """
        Run sensitivity analysis across shock levels.
        
        Args:
            positions: Portfolio positions
            current_prices: Current prices
            factor: Factor to shock
            shock_range: (min_shock, max_shock, step)
            
        Returns:
            List of results for each shock level
        """
        results = []
        min_shock, max_shock, step = shock_range
        
        current = min_shock
        while current <= max_shock:
            scenario = {
                "name": f"{factor}_shock_{current:.2%}",
                "shocks": {factor: current}
            }
            
            result = self.run(positions, scenario, current_prices)
            results.append({
                "shock": current,
                "pnl_impact": result.pnl_impact,
                "pnl_impact_pct": result.pnl_impact_pct
            })
            
            current += step
        
        return results


# Utility functions for caching
def generate_cache_key(params: Dict) -> str:
    """Generate cache key from parameters."""
    param_str = json.dumps(params, sort_keys=True, default=str)
    return hashlib.md5(param_str.encode()).hexdigest()


def calculate_portfolio_metrics_summary(
    positions: Dict[str, Dict],
    historical_returns: pd.DataFrame,
    benchmark_returns: Optional[pd.Series] = None
) -> Dict:
    """
    Calculate comprehensive portfolio metrics summary.
    
    Args:
        positions: Portfolio positions
        historical_returns: Historical returns DataFrame
        benchmark_returns: Optional benchmark returns
        
    Returns:
        Dictionary of portfolio metrics
    """
    analytics = PortfolioAnalytics()
    
    # Calculate position values
    position_values = []
    for pos in positions.values():
        position_values.append(pos.get('quantity', 0) * pos.get('price', 0))
    
    portfolio_value = sum(abs(v) for v in position_values)
    
    # Portfolio returns (weighted average)
    weights = np.array([v / portfolio_value for v in position_values])
    portfolio_returns = (historical_returns * weights).sum(axis=1)
    
    # Basic metrics
    total_return = (1 + portfolio_returns).prod() - 1
    annualized_return = (1 + total_return) ** (252 / len(portfolio_returns)) - 1
    volatility = portfolio_returns.std() * np.sqrt(252)
    sharpe = analytics.calculate_sharpe_ratio(portfolio_returns)
    sortino = analytics.calculate_sortino_ratio(portfolio_returns)
    
    metrics = {
        "portfolio_value": portfolio_value,
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "var_95": portfolio_returns.quantile(0.05) * portfolio_value,
        "var_99": portfolio_returns.quantile(0.01) * portfolio_value
    }
    
    # Add benchmark-relative metrics if provided
    if benchmark_returns is not None:
        beta = analytics.calculate_beta(portfolio_returns, benchmark_returns)
        tracking_error = analytics.calculate_tracking_error(
            portfolio_returns, benchmark_returns
        )
        
        # Information ratio
        active_returns = portfolio_returns - benchmark_returns
        information_ratio = active_returns.mean() / active_returns.std() * np.sqrt(252)
        
        metrics.update({
            "beta": beta,
            "tracking_error": tracking_error,
            "information_ratio": information_ratio
        })
    
    return metrics
