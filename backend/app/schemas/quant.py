"""Pydantic v2 schemas for quantitative analytics."""

from datetime import date, datetime

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Yield Curve
# ---------------------------------------------------------------------------
class YieldCurveResponse(BaseModel):
    id: str
    date: date
    tenor: str
    rate: float
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


class YieldCurveCreate(BaseModel):
    date: date
    tenor: str = Field(pattern=r"^(1M|3M|6M|1Y|2Y|5Y|10Y|30Y)$")
    rate: float
    source: str = "FRED"


# ---------------------------------------------------------------------------
# Option Chain
# ---------------------------------------------------------------------------
class OptionChainResponse(BaseModel):
    id: str
    symbol: str
    expiry: date
    strike: float
    option_type: str
    bid: float
    ask: float
    volume: int
    open_interest: int
    implied_vol: float
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    fetched_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Option pricing request / response
# ---------------------------------------------------------------------------
class OptionPriceRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    strike: float = Field(gt=0)
    expiry: date
    option_type: str = Field(pattern=r"^(call|put)$")
    spot_price: float = Field(gt=0)
    risk_free_rate: float = Field(ge=0, le=1)
    volatility: float = Field(gt=0, le=5)


class GreeksResponse(BaseModel):
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class OptionPriceResponse(BaseModel):
    price: float
    greeks: GreeksResponse


# ---------------------------------------------------------------------------
# VaR
# ---------------------------------------------------------------------------
class VarResultResponse(BaseModel):
    id: str
    portfolio_id: str | None = None
    method: str
    confidence: float
    horizon_days: int
    var_value: float
    cvar_value: float | None = None
    computed_at: datetime

    model_config = {"from_attributes": True}


class VarRequest(BaseModel):
    portfolio_id: str | None = None
    symbols: list[str] | None = None
    weights: list[float] | None = None
    returns: list[list[float]] | None = None
    method: str = Field(default="historical", pattern=r"^(historical|parametric|monte_carlo)$")
    confidence: float = Field(default=0.95, ge=0.5, le=0.999)
    horizon_days: int = Field(default=1, ge=1, le=365)
    num_simulations: int = Field(default=10000, ge=100, le=1000000)


# ---------------------------------------------------------------------------
# Covariance Matrix
# ---------------------------------------------------------------------------
class CovarianceMatrixResponse(BaseModel):
    id: str
    symbols: str
    window_days: int
    matrix_data: str
    computed_at: datetime

    model_config = {"from_attributes": True}


class CovarianceRequest(BaseModel):
    symbols: list[str] = Field(min_length=2)
    returns: list[list[float]]
    window_days: int = Field(default=252, ge=10, le=1260)


# ---------------------------------------------------------------------------
# Portfolio Metrics
# ---------------------------------------------------------------------------
class PortfolioMetricsRequest(BaseModel):
    symbols: list[str] = Field(min_length=1)
    weights: list[float] = Field(min_length=1)
    returns: list[list[float]]  # list of return series per symbol


class PortfolioMetricsResponse(BaseModel):
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    annualized_return: float
    annualized_vol: float
