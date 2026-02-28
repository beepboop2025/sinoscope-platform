"""
DragonScope Risk Analytics Engine - Data Models

Pydantic models for risk reports, scenarios, factor models, and correlation management.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
import uuid
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator, root_validator


class RiskMetricType(str, Enum):
    """Enumeration of supported risk metric types."""
    VAR = "var"
    CVAR = "cvar"
    SHARPE = "sharpe"
    SORTINO = "sortino"
    BETA = "beta"
    TRACKING_ERROR = "tracking_error"
    VOLATILITY = "volatility"
    DRAWDOWN = "drawdown"


class VaRMethod(str, Enum):
    """Value at Risk calculation methods."""
    PARAMETRIC = "parametric"
    HISTORICAL = "historical"
    MONTE_CARLO = "monte_carlo"


class AssetClass(str, Enum):
    """Asset class classification."""
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    ALTERNATIVE = "alternative"
    CASH = "cash"
    DERIVATIVE = "derivative"


class ScenarioType(str, Enum):
    """Stress test scenario types."""
    HISTORICAL = "historical"
    HYPOTHETICAL = "hypothetical"
    SENSITIVITY = "sensitivity"
    MONTE_CARLO = "monte_carlo"


class FactorType(str, Enum):
    """Risk factor types."""
    MARKET = "market"
    STYLE = "style"
    INDUSTRY = "industry"
    MACRO = "macro"
    STATISTICAL = "statistical"
    CUSTOM = "custom"


# ============================================================================
# Base Models
# ============================================================================

class Position(BaseModel):
    """Portfolio position model."""
    position_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_id: str = Field(..., description="Unique asset identifier")
    asset_name: Optional[str] = None
    asset_class: AssetClass = AssetClass.EQUITY
    quantity: float = Field(..., gt=0, description="Position quantity")
    price: float = Field(..., gt=0, description="Current price")
    currency: str = Field(default="USD")
    
    # Risk parameters
    volatility: Optional[float] = Field(default=0.2, ge=0, le=5)
    expected_return: Optional[float] = Field(default=0.0)
    beta: Optional[float] = Field(default=None)
    
    # For options
    is_option: bool = False
    option_type: Optional[str] = None  # 'call' or 'put'
    strike: Optional[float] = None
    expiry: Optional[datetime] = None
    implied_vol: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            np.ndarray: lambda v: v.tolist()
        }
    
    @property
    def market_value(self) -> float:
        """Calculate market value of position."""
        return self.quantity * self.price
    
    @property
    def notional(self) -> float:
        """Calculate notional value."""
        return abs(self.market_value)


class Portfolio(BaseModel):
    """Portfolio model containing positions."""
    portfolio_id: str = Field(..., description="Unique portfolio identifier")
    name: str = Field(..., description="Portfolio name")
    base_currency: str = Field(default="USD")
    positions: List[Position] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Benchmark
    benchmark_id: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @property
    def total_value(self) -> float:
        """Calculate total portfolio value."""
        return sum(pos.market_value for pos in self.positions)
    
    @property
    def long_value(self) -> float:
        """Calculate total long exposure."""
        return sum(pos.market_value for pos in self.positions if pos.quantity > 0)
    
    @property
    def short_value(self) -> float:
        """Calculate total short exposure."""
        return sum(pos.market_value for pos in self.positions if pos.quantity < 0)
    
    @property
    def gross_exposure(self) -> float:
        """Calculate gross exposure."""
        return sum(abs(pos.market_value) for pos in self.positions)
    
    @property
    def net_exposure(self) -> float:
        """Calculate net exposure."""
        return self.total_value
    
    def get_weights(self) -> Dict[str, float]:
        """Calculate position weights."""
        total = self.total_value
        if total == 0:
            return {}
        return {
            pos.position_id: pos.market_value / total 
            for pos in self.positions
        }
    
    def get_asset_class_breakdown(self) -> Dict[str, float]:
        """Get exposure breakdown by asset class."""
        breakdown = {}
        for pos in self.positions:
            ac = pos.asset_class.value
            breakdown[ac] = breakdown.get(ac, 0) + pos.market_value
        return breakdown
    
    def to_positions_dict(self) -> Dict[str, Dict]:
        """Convert to positions dictionary for calculations."""
        return {
            pos.position_id: {
                "asset_id": pos.asset_id,
                "asset_class": pos.asset_class.value,
                "quantity": pos.quantity,
                "price": pos.price,
                "volatility": pos.volatility,
                "expected_return": pos.expected_return,
                "is_option": pos.is_option,
                "option_type": pos.option_type,
                "strike": pos.strike,
                "implied_vol": pos.implied_vol,
                "delta": pos.delta
            }
            for pos in self.positions
        }


# ============================================================================
# Risk Report Models
# ============================================================================

class VaRResult(BaseModel):
    """Value at Risk calculation result."""
    var_95: float = Field(..., description="95% VaR")
    var_99: float = Field(..., description="99% VaR")
    cvar_95: float = Field(..., description="95% Conditional VaR (Expected Shortfall)")
    cvar_99: float = Field(..., description="99% Conditional VaR (Expected Shortfall)")
    method: VaRMethod = Field(..., description="Calculation method used")
    confidence_level: float = Field(..., ge=0, le=1)
    time_horizon: int = Field(..., ge=1, description="Days")
    n_simulations: Optional[int] = None
    calculation_time_ms: Optional[float] = None


class GreeksResult(BaseModel):
    """Option Greeks calculation result."""
    delta: float = Field(..., description="Price sensitivity")
    gamma: float = Field(..., description="Delta sensitivity")
    theta: float = Field(..., description="Time decay (per day)")
    vega: float = Field(..., description="Volatility sensitivity")
    rho: float = Field(..., description="Rate sensitivity")
    vanna: Optional[float] = None
    charm: Optional[float] = None


class FactorExposure(BaseModel):
    """Factor exposure for a single factor."""
    factor_id: str
    factor_name: str
    beta: float = Field(..., description="Factor sensitivity")
    t_stat: Optional[float] = None
    p_value: Optional[float] = None
    contribution_to_risk: float = Field(default=0.0)
    contribution_to_return: float = Field(default=0.0)


class FactorExposureResult(BaseModel):
    """Portfolio factor exposure analysis result."""
    factor_model_id: str
    factor_model_name: str
    exposures: List[FactorExposure] = Field(default_factory=list)
    r_squared: float = Field(..., ge=0, le=1)
    systematic_risk: float = Field(..., description="Annualized systematic volatility")
    specific_risk: float = Field(..., description="Annualized specific volatility")
    total_risk: float = Field(..., description="Total portfolio volatility")
    
    @property
    def diversification_ratio(self) -> float:
        """Calculate diversification ratio."""
        if self.total_risk == 0:
            return 0.0
        return 1 - (self.specific_risk / self.total_risk) ** 2


class PositionRisk(BaseModel):
    """Risk metrics for individual position."""
    position_id: str
    asset_id: str
    asset_name: Optional[str] = None
    market_value: float
    weight: float = Field(..., ge=-1, le=1)
    
    # Risk contributions
    marginal_var: float = Field(default=0.0, description="Marginal VaR contribution")
    component_var: float = Field(default=0.0, description="Component VaR")
    marginal_volatility: float = Field(default=0.0)
    
    # Greeks (for options)
    greeks: Optional[GreeksResult] = None
    
    # Factor exposures
    factor_exposures: Dict[str, float] = Field(default_factory=dict)


class RiskMetrics(BaseModel):
    """Core risk metrics collection."""
    # VaR metrics
    var: VaRResult
    
    # Return/Risk ratios
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    information_ratio: Optional[float] = None
    
    # Volatility metrics
    volatility: float = Field(..., description="Annualized volatility")
    downside_volatility: Optional[float] = None
    
    # Beta metrics
    beta: Optional[float] = None
    tracking_error: Optional[float] = None
    
    # Drawdown metrics
    max_drawdown: Optional[float] = None
    current_drawdown: Optional[float] = None
    avg_drawdown: Optional[float] = None
    
    # Tail metrics
    skewness: Optional[float] = None
    kurtosis: Optional[float] = None
    tail_ratio: Optional[float] = None


class RiskReport(BaseModel):
    """
    Comprehensive risk report for a portfolio.
    
    Contains all calculated risk metrics, factor exposures,
    stress test results, and position-level analytics.
    """
    # Identification
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str
    report_date: datetime = Field(default_factory=datetime.utcnow)
    calculation_date: datetime = Field(default_factory=datetime.utcnow)
    
    # Portfolio snapshot
    portfolio_value: float
    base_currency: str = "USD"
    
    # Core metrics
    risk_metrics: RiskMetrics
    
    # Factor analysis
    factor_exposure: Optional[FactorExposureResult] = None
    
    # Position-level details
    position_risks: List[PositionRisk] = Field(default_factory=list)
    
    # Top contributors/detractors
    top_var_contributors: List[PositionRisk] = Field(default_factory=list)
    top_var_detractors: List[PositionRisk] = Field(default_factory=list)
    
    # Stress test results
    stress_test_results: List["StressTestResult"] = Field(default_factory=list)
    
    # Metadata
    calculation_params: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @property
    def var_95_pct(self) -> float:
        """VaR as percentage of portfolio value."""
        if self.portfolio_value == 0:
            return 0.0
        return self.risk_metrics.var.var_95 / self.portfolio_value
    
    @property
    def var_99_pct(self) -> float:
        """99% VaR as percentage of portfolio value."""
        if self.portfolio_value == 0:
            return 0.0
        return self.risk_metrics.var.var_99 / self.portfolio_value
    
    def get_summary(self) -> Dict[str, Any]:
        """Get human-readable summary of risk report."""
        return {
            "report_id": self.report_id,
            "portfolio_id": self.portfolio_id,
            "report_date": self.report_date.isoformat(),
            "portfolio_value": f"${self.portfolio_value:,.2f}",
            "var_95": f"${self.risk_metrics.var.var_95:,.2f} ({self.var_95_pct:.2%})",
            "var_99": f"${self.risk_metrics.var.var_99:,.2f} ({self.var_99_pct:.2%})",
            "volatility": f"{self.risk_metrics.volatility:.2%}",
            "sharpe_ratio": f"{self.risk_metrics.sharpe_ratio:.2f}" if self.risk_metrics.sharpe_ratio else "N/A",
            "beta": f"{self.risk_metrics.beta:.2f}" if self.risk_metrics.beta else "N/A",
            "max_drawdown": f"{self.risk_metrics.max_drawdown:.2%}" if self.risk_metrics.max_drawdown else "N/A",
            "n_positions": len(self.position_risks),
            "n_warnings": len(self.warnings)
        }


# ============================================================================
# Scenario Models
# ============================================================================

class ShockDefinition(BaseModel):
    """Definition of a market shock."""
    asset_class: Optional[AssetClass] = None
    factor_id: Optional[str] = None
    shock_type: str = Field(default="absolute", description="absolute or relative")
    shock_value: float = Field(..., description="Shock magnitude")
    correlation_adjustment: Optional[float] = None


class Scenario(BaseModel):
    """Stress test scenario definition."""
    scenario_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Scenario name")
    description: Optional[str] = None
    scenario_type: ScenarioType = ScenarioType.HYPOTHETICAL
    
    # Shocks
    shocks: Dict[str, float] = Field(
        default_factory=dict,
        description="Asset class -> shock percentage mapping"
    )
    factor_shocks: Dict[str, float] = Field(
        default_factory=dict,
        description="Factor ID -> shock value mapping"
    )
    
    # Correlation stress
    correlation_stress: Optional[Dict[str, Any]] = None
    
    # Historical reference
    historical_period: Optional[Tuple[datetime, datetime]] = None
    
    # Metadata
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)
    is_system: bool = Field(default=False, description="Predefined system scenario")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator('shocks')
    def validate_shocks(cls, v):
        """Validate shock values are reasonable."""
        for asset_class, shock in v.items():
            if abs(shock) > 1.0:
                raise ValueError(f"Shock magnitude for {asset_class} exceeds 100%")
        return v
    
    def apply_to_returns(
        self,
        returns: pd.DataFrame,
        asset_mapping: Dict[str, str]
    ) -> pd.DataFrame:
        """
        Apply scenario shocks to historical returns.
        
        Args:
            returns: Historical returns DataFrame
            asset_mapping: Mapping of asset_id to asset_class
            
        Returns:
            Stressed returns DataFrame
        """
        stressed = returns.copy()
        
        for asset_id, asset_class in asset_mapping.items():
            if asset_id in stressed.columns and asset_class in self.shocks:
                shock = self.shocks[asset_class]
                stressed[asset_id] = returns[asset_id] + shock
        
        return stressed


class ScenarioResult(BaseModel):
    """Result of applying a scenario."""
    scenario_id: str
    scenario_name: str
    
    portfolio_value_before: float
    portfolio_value_after: float
    pnl_absolute: float
    pnl_percentage: float
    
    position_results: List[Dict[str, Any]] = Field(default_factory=list)
    factor_impacts: Dict[str, float] = Field(default_factory=dict)
    
    # Risk metric changes
    var_before: Optional[float] = None
    var_after: Optional[float] = None
    volatility_before: Optional[float] = None
    volatility_after: Optional[float] = None


class StressTestResult(BaseModel):
    """Stress test execution result."""
    test_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str
    scenario_id: str
    execution_time: datetime = Field(default_factory=datetime.utcnow)
    
    scenario_result: ScenarioResult
    
    # Detailed analytics
    liquidation_impact: Optional[float] = None
    liquidity_stress: Optional[Dict[str, float]] = None
    
    # Margin/capital impact
    margin_impact: Optional[float] = None
    capital_impact: Optional[float] = None
    
    # Breach indicators
    limit_breaches: List[Dict[str, Any]] = Field(default_factory=list)
    concentration_risks: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# Factor Models
# ============================================================================

class RiskFactor(BaseModel):
    """Definition of a risk factor."""
    factor_id: str = Field(..., description="Unique factor identifier")
    factor_name: str
    factor_type: FactorType
    
    # Factor properties
    description: Optional[str] = None
    category: Optional[str] = None
    
    # Time series properties
    frequency: str = Field(default="daily")
    currency: str = Field(default="USD")
    
    # Calculation method
    calculation_formula: Optional[str] = None
    underlying_assets: List[str] = Field(default_factory=list)
    
    # Metadata
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class FactorModel(BaseModel):
    """
    Multi-factor risk model definition.
    
    Defines the factors used for risk decomposition and attribution.
    """
    model_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_name: str
    model_type: FactorType
    description: Optional[str] = None
    
    # Factors in the model
    factors: List[RiskFactor] = Field(default_factory=list)
    
    # Model specification
    lookback_period: int = Field(default=252, description="Days of history")
    estimation_method: str = Field(default="ols", description="Regression method")
    
    # Time parameters
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True
    
    @property
    def n_factors(self) -> int:
        """Number of factors in the model."""
        return len(self.factors)
    
    def get_factor_ids(self) -> List[str]:
        """Get list of factor IDs."""
        return [f.factor_id for f in self.factors]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "model_type": self.model_type.value,
            "n_factors": self.n_factors,
            "factors": [
                {
                    "factor_id": f.factor_id,
                    "factor_name": f.factor_name,
                    "factor_type": f.factor_type.value
                }
                for f in self.factors
            ]
        }


# ============================================================================
# Correlation Matrix Management
# ============================================================================

class CorrelationMatrix(BaseModel):
    """
    Correlation matrix with metadata for risk calculations.
    
    Supports various correlation estimation methods and
    provides utilities for matrix manipulation.
    """
    matrix_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    
    # Matrix data
    assets: List[str] = Field(..., description="Asset IDs in order")
    matrix: List[List[float]] = Field(..., description="Correlation matrix")
    
    # Estimation parameters
    estimation_method: str = Field(default="pearson")
    lookback_period: int = Field(default=252)
    decay_factor: Optional[float] = None  # For EWMA
    
    # Timestamps
    as_of_date: datetime = Field(default_factory=datetime.utcnow)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Metadata
    is_valid: bool = True
    condition_number: Optional[float] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @validator('matrix')
    def validate_correlation_matrix(cls, v, values):
        """Validate correlation matrix properties."""
        if not v:
            return v
        
        n = len(v)
        if any(len(row) != n for row in v):
            raise ValueError("Correlation matrix must be square")
        
        # Check diagonal is 1
        for i in range(n):
            if abs(v[i][i] - 1.0) > 1e-6:
                raise ValueError(f"Diagonal element [{i},{i}] must be 1.0")
        
        # Check symmetry
        for i in range(n):
            for j in range(i + 1, n):
                if abs(v[i][j] - v[j][i]) > 1e-6:
                    raise ValueError(f"Matrix must be symmetric: [{i},{j}] != [{j},{i}]")
        
        # Check bounds
        for i in range(n):
            for j in range(n):
                if v[i][j] < -1 or v[i][j] > 1:
                    raise ValueError(f"Correlation must be in [-1, 1]: [{i},{j}] = {v[i][j]}")
        
        return v
    
    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array(self.matrix)
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        return pd.DataFrame(
            self.matrix,
            index=self.assets,
            columns=self.assets
        )
    
    def get_correlation(self, asset1: str, asset2: str) -> float:
        """Get correlation between two assets."""
        if asset1 not in self.assets or asset2 not in self.assets:
            raise ValueError("Asset not found in correlation matrix")
        
        i = self.assets.index(asset1)
        j = self.assets.index(asset2)
        return self.matrix[i][j]
    
    def get_asset_correlations(self, asset: str) -> Dict[str, float]:
        """Get all correlations for a specific asset."""
        if asset not in self.assets:
            raise ValueError(f"Asset {asset} not found in correlation matrix")
        
        idx = self.assets.index(asset)
        return {
            self.assets[i]: self.matrix[idx][i]
            for i in range(len(self.assets))
            if i != idx
        }
    
    def apply_shrinkage(self, shrinkage_factor: float = 0.5) -> "CorrelationMatrix":
        """
        Apply Ledoit-Wolf type shrinkage towards identity.
        
        Args:
            shrinkage_factor: Shrinkage intensity (0-1)
            
        Returns:
            New CorrelationMatrix with shrinkage applied
        """
        corr = self.to_numpy()
        n = len(corr)
        
        # Target is identity matrix
        target = np.eye(n)
        
        # Shrink
        shrunk = (1 - shrinkage_factor) * corr + shrinkage_factor * target
        
        return CorrelationMatrix(
            name=f"{self.name}_shrunk" if self.name else None,
            assets=self.assets.copy(),
            matrix=shrunk.tolist(),
            estimation_method=f"{self.estimation_method}_shrunk",
            lookback_period=self.lookback_period
        )
    
    def make_positive_semidefinite(self) -> "CorrelationMatrix":
        """
        Force matrix to be positive semidefinite.
        
        Uses eigenvalue decomposition and sets negative eigenvalues to zero.
        
        Returns:
            New CorrelationMatrix that is PSD
        """
        corr = self.to_numpy()
        
        # Eigenvalue decomposition
        eigenvalues, eigenvectors = np.linalg.eigh(corr)
        
        # Set negative eigenvalues to small positive
        eigenvalues = np.maximum(eigenvalues, 1e-8)
        
        # Reconstruct
        corr_psd = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
        
        # Normalize to ensure unit diagonal
        d = np.sqrt(np.diag(corr_psd))
        corr_psd = corr_psd / np.outer(d, d)
        
        return CorrelationMatrix(
            name=f"{self.name}_psd" if self.name else None,
            assets=self.assets.copy(),
            matrix=corr_psd.tolist(),
            estimation_method=f"{self.estimation_method}_psd",
            lookback_period=self.lookback_period
        )
    
    @classmethod
    def from_returns(
        cls,
        returns: pd.DataFrame,
        method: str = "pearson",
        lookback: int = 252,
        min_periods: int = 30
    ) -> "CorrelationMatrix":
        """
        Calculate correlation matrix from returns.
        
        Args:
            returns: Returns DataFrame (dates x assets)
            method: Correlation method ('pearson', 'spearman', 'kendall')
            lookback: Number of periods to use
            min_periods: Minimum periods required
            
        Returns:
            CorrelationMatrix
        """
        # Use last N periods
        returns_window = returns.tail(lookback)
        
        # Calculate correlation
        if method == "pearson":
            corr_df = returns_window.corr(min_periods=min_periods)
        elif method == "spearman":
            corr_df = returns_window.corr(method="spearman", min_periods=min_periods)
        elif method == "kendall":
            corr_df = returns_window.corr(method="kendall", min_periods=min_periods)
        else:
            raise ValueError(f"Unknown correlation method: {method}")
        
        # Fill NaN with 0 correlation
        corr_df = corr_df.fillna(0)
        
        # Ensure diagonal is 1
        for col in corr_df.columns:
            corr_df.loc[col, col] = 1.0
        
        return cls(
            assets=corr_df.columns.tolist(),
            matrix=corr_df.values.tolist(),
            estimation_method=method,
            lookback_period=lookback,
            start_date=returns_window.index[0],
            end_date=returns_window.index[-1]
        )
    
    @classmethod
    def ewma_correlation(
        cls,
        returns: pd.DataFrame,
        decay_factor: float = 0.94,
        lookback: int = 252
    ) -> "CorrelationMatrix":
        """
        Calculate EWMA (Exponentially Weighted Moving Average) correlation.
        
        Args:
            returns: Returns DataFrame
            decay_factor: Lambda parameter (closer to 1 = slower decay)
            lookback: Number of periods
            
        Returns:
            CorrelationMatrix with EWMA correlations
        """
        returns_window = returns.tail(lookback)
        
        # Calculate EWMA covariance
        ewma_cov = returns_window.ewm(span=int(2 / (1 - decay_factor) - 1)).cov()
        
        # Get the last covariance matrix
        last_cov = ewma_cov.iloc[-len(returns_window.columns):].values
        
        # Convert to correlation
        d = np.sqrt(np.diag(last_cov))
        corr = last_cov / np.outer(d, d)
        
        return cls(
            assets=returns_window.columns.tolist(),
            matrix=corr.tolist(),
            estimation_method="ewma",
            decay_factor=decay_factor,
            lookback_period=lookback
        )


# ============================================================================
# Cache Models
# ============================================================================

class CacheKey(BaseModel):
    """Cache key for risk calculation results."""
    calculation_type: str
    portfolio_id: str
    params_hash: str
    as_of_date: str
    
    def to_redis_key(self) -> str:
        """Generate Redis cache key."""
        return f"risk:{self.calculation_type}:{self.portfolio_id}:{self.as_of_date}:{self.params_hash}"


class CachedResult(BaseModel):
    """Cached calculation result with metadata."""
    cache_key: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    result: Dict[str, Any]
    calculation_time_ms: float
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.utcnow() > self.expires_at
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# Request/Response Models for API
# ============================================================================

class VaRRequest(BaseModel):
    """Request model for VaR calculation."""
    method: VaRMethod = VaRMethod.MONTE_CARLO
    confidence_level: float = Field(default=0.95, ge=0.8, le=0.999)
    time_horizon: int = Field(default=1, ge=1, le=252)
    n_simulations: int = Field(default=10000, ge=1000, le=100000)
    use_cache: bool = True
    
    # Optional parameters
    historical_lookback: Optional[int] = Field(default=252, ge=30)
    random_seed: Optional[int] = None


class StressTestRequest(BaseModel):
    """Request model for stress test."""
    scenario_id: Optional[str] = None
    scenario: Optional[Scenario] = None
    shocks: Optional[Dict[str, float]] = None
    include_position_details: bool = True
    include_historical_comparison: bool = False
    
    @root_validator(skip_on_failure=True)
    def check_scenario_source(cls, values):
        """Ensure at least one scenario source is provided."""
        scenario_id = values.get('scenario_id')
        scenario = values.get('scenario')
        shocks = values.get('shocks')
        
        if not any([scenario_id, scenario, shocks]):
            raise ValueError("Must provide scenario_id, scenario, or shocks")
        
        return values


class ScenarioCreateRequest(BaseModel):
    """Request to create a new scenario."""
    name: str
    description: Optional[str] = None
    scenario_type: ScenarioType = ScenarioType.HYPOTHETICAL
    shocks: Dict[str, float] = Field(default_factory=dict)
    factor_shocks: Dict[str, float] = Field(default_factory=dict)
    correlation_stress: Optional[Dict[str, Any]] = None
    tags: List[str] = Field(default_factory=list)


class RiskReportRequest(BaseModel):
    """Request for comprehensive risk report."""
    portfolio_id: str
    calculation_date: Optional[datetime] = None
    include_factor_exposure: bool = True
    include_stress_tests: bool = True
    include_position_risk: bool = True
    stress_scenarios: List[str] = Field(default_factory=list)
    
    # VaR parameters
    var_method: VaRMethod = VaRMethod.MONTE_CARLO
    var_confidence: float = 0.95
    var_horizon: int = 1


class FactorModelRequest(BaseModel):
    """Request for factor model analysis."""
    model_id: Optional[str] = None
    factor_ids: List[str] = Field(default_factory=list)
    lookback_period: int = Field(default=252, ge=63)
    estimation_method: str = "ols"


# ============================================================================
# Utility Functions
# ============================================================================

def create_default_scenarios() -> List[Scenario]:
    """Create default set of stress test scenarios."""
    return [
        Scenario(
            scenario_id="2008_financial_crisis",
            name="2008 Financial Crisis",
            description="Global financial crisis scenario",
            scenario_type=ScenarioType.HISTORICAL,
            shocks={
                "equity": -0.40,
                "fixed_income": -0.05,
                "credit": -0.15,
                "commodity": -0.30
            },
            is_system=True
        ),
        Scenario(
            scenario_id="2020_covid_crash",
            name="COVID-19 Market Crash",
            description="March 2020 market crash",
            scenario_type=ScenarioType.HISTORICAL,
            shocks={
                "equity": -0.34,
                "credit": -0.12,
                "commodity": -0.50,
                "volatility": 0.80
            },
            is_system=True
        ),
        Scenario(
            scenario_id="interest_rate_shock_up",
            name="Interest Rate Shock (Up)",
            description="Rapid 300bp rate increase",
            scenario_type=ScenarioType.HYPOTHETICAL,
            shocks={
                "fixed_income": -0.10,
                "equity": -0.15,
                "rate_sensitive": -0.20
            },
            is_system=True
        ),
        Scenario(
            scenario_id="inflation_spike",
            name="Inflation Spike",
            description="Unexpected inflation increase",
            scenario_type=ScenarioType.HYPOTHETICAL,
            shocks={
                "equity": -0.10,
                "fixed_income": -0.08,
                "commodity": 0.20,
                "real_estate": 0.10
            },
            is_system=True
        ),
        Scenario(
            scenario_id="liquidity_crisis",
            name="Liquidity Crisis",
            description="System-wide liquidity freeze",
            scenario_type=ScenarioType.HYPOTHETICAL,
            shocks={
                "equity": -0.25,
                "credit": -0.30,
                "alternative": -0.15,
                "cash": 0.05
            },
            is_system=True
        )
    ]


def create_fama_french_factors() -> FactorModel:
    """Create Fama-French 5-factor model."""
    return FactorModel(
        model_name="Fama-French 5-Factor",
        model_type=FactorType.STYLE,
        description="Fama-French 5-factor model: Market, SMB, HML, RMW, CMA",
        factors=[
            RiskFactor(
                factor_id="MKT",
                factor_name="Market Excess Return",
                factor_type=FactorType.MARKET,
                description="Market return minus risk-free rate"
            ),
            RiskFactor(
                factor_id="SMB",
                factor_name="Small Minus Big",
                factor_type=FactorType.STYLE,
                description="Size factor: Small cap minus large cap"
            ),
            RiskFactor(
                factor_id="HML",
                factor_name="High Minus Low",
                factor_type=FactorType.STYLE,
                description="Value factor: High book-to-market minus low"
            ),
            RiskFactor(
                factor_id="RMW",
                factor_name="Robust Minus Weak",
                factor_type=FactorType.STYLE,
                description="Profitability factor"
            ),
            RiskFactor(
                factor_id="CMA",
                factor_name="Conservative Minus Aggressive",
                factor_type=FactorType.STYLE,
                description="Investment factor"
            )
        ],
        lookback_period=252
    )


def create_macro_factor_model() -> FactorModel:
    """Create macroeconomic factor model."""
    return FactorModel(
        model_name="Macro Factor Model",
        model_type=FactorType.MACRO,
        description="Macroeconomic risk factors",
        factors=[
            RiskFactor(
                factor_id="EQUITY_MKT",
                factor_name="Equity Market",
                factor_type=FactorType.MARKET
            ),
            RiskFactor(
                factor_id="TERM_SPREAD",
                factor_name="Term Spread",
                factor_type=FactorType.MACRO,
                description="10Y - 2Y Treasury spread"
            ),
            RiskFactor(
                factor_id="CREDIT_SPREAD",
                factor_name="Credit Spread",
                factor_type=FactorType.MACRO,
                description="High yield - Treasury spread"
            ),
            RiskFactor(
                factor_id="INFLATION",
                factor_name="Inflation",
                factor_type=FactorType.MACRO
            ),
            RiskFactor(
                factor_id="FX_RATE",
                factor_name="FX Rate",
                factor_type=FactorType.MACRO
            ),
            RiskFactor(
                factor_id="COMMODITY",
                factor_name="Commodity",
                factor_type=FactorType.MACRO
            )
        ],
        lookback_period=252
    )
