"""Quantitative analytics API routes."""

import json
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.quant import CovarianceMatrix, VarResult, YieldCurve
from app.schemas.quant import (
    CovarianceMatrixResponse,
    CovarianceRequest,
    OptionPriceRequest,
    OptionPriceResponse,
    PortfolioMetricsRequest,
    PortfolioMetricsResponse,
    VarRequest,
    VarResultResponse,
    YieldCurveResponse,
)
from app.services.quant_engine import QuantEngine

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Yield Curves
# ---------------------------------------------------------------------------
@router.get("/yield-curves", response_model=list[YieldCurveResponse])
async def list_yield_curves(
    curve_date: date | None = Query(None, alias="date", description="Filter by date"),
    session: AsyncSession = Depends(get_db),
    auth: AuthUser = Depends(require_auth),
):
    """List yield curve data, optionally filtered by date."""
    query = select(YieldCurve).order_by(YieldCurve.date.desc(), YieldCurve.tenor)

    if curve_date is not None:
        query = query.where(YieldCurve.date == curve_date)
    else:
        # Default: latest date only
        subq = select(YieldCurve.date).order_by(YieldCurve.date.desc()).limit(1).scalar_subquery()
        query = query.where(YieldCurve.date == subq)

    result = await session.execute(query)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Option Pricing
# ---------------------------------------------------------------------------
@router.post("/options/price", response_model=OptionPriceResponse)
async def price_option(
    body: OptionPriceRequest,
    auth: AuthUser = Depends(require_auth),
):
    """Price an option using Black-Scholes and return Greeks."""
    today = date.today()
    days_to_expiry = (body.expiry - today).days
    if days_to_expiry < 0:
        raise HTTPException(status_code=400, detail="Expiry date must be in the future")

    time_to_expiry = days_to_expiry / 365.0

    price, greeks = QuantEngine.black_scholes(
        spot=body.spot_price,
        strike=body.strike,
        time_to_expiry=time_to_expiry,
        rate=body.risk_free_rate,
        vol=body.volatility,
        option_type=body.option_type,
    )

    return OptionPriceResponse(
        price=round(price, 4),
        greeks={
            "delta": greeks["delta"],
            "gamma": greeks["gamma"],
            "theta": greeks["theta"],
            "vega": greeks["vega"],
            "rho": greeks["rho"],
        },
    )


# ---------------------------------------------------------------------------
# Value at Risk
# ---------------------------------------------------------------------------
@router.post("/var", response_model=VarResultResponse)
async def calculate_var(
    body: VarRequest,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Calculate Value at Risk using the specified method."""
    if not body.returns or not body.returns[0]:
        raise HTTPException(status_code=400, detail="Returns data is required")

    # Flatten returns if it is a matrix (portfolio-weighted)
    if body.weights and len(body.returns) > 1:
        # Weighted portfolio returns
        n_periods = min(len(r) for r in body.returns)
        flat_returns = []
        for t in range(n_periods):
            r = sum(
                body.weights[i] * body.returns[i][t]
                for i in range(min(len(body.weights), len(body.returns)))
            )
            flat_returns.append(r)
    else:
        flat_returns = body.returns[0] if body.returns else []

    if body.method == "historical":
        var_val, cvar_val = QuantEngine.historical_var(flat_returns, body.confidence)
    elif body.method == "parametric":
        import statistics as stats
        if len(flat_returns) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 return observations")
        mu = stats.mean(flat_returns)
        sigma = stats.stdev(flat_returns)
        var_val, cvar_val = QuantEngine.parametric_var(mu, sigma, body.confidence, body.horizon_days)
    elif body.method == "monte_carlo":
        var_val, cvar_val = QuantEngine.monte_carlo_var(
            flat_returns, body.confidence, body.horizon_days, body.num_simulations,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown VaR method: {body.method}")

    # Persist result
    var_result = VarResult(
        portfolio_id=body.portfolio_id,
        method=body.method,
        confidence=body.confidence,
        horizon_days=body.horizon_days,
        var_value=var_val,
        cvar_value=cvar_val,
    )
    session.add(var_result)
    await session.flush()

    return var_result


# ---------------------------------------------------------------------------
# Portfolio Metrics
# ---------------------------------------------------------------------------
@router.post("/portfolio-metrics", response_model=PortfolioMetricsResponse)
async def calculate_portfolio_metrics(
    body: PortfolioMetricsRequest,
    auth: AuthUser = Depends(require_auth),
):
    """Compute portfolio risk metrics (Sharpe, Sortino, Calmar, MDD)."""
    if len(body.symbols) != len(body.weights):
        raise HTTPException(status_code=400, detail="symbols and weights must have the same length")
    if len(body.symbols) != len(body.returns):
        raise HTTPException(status_code=400, detail="symbols and returns must have the same length")

    metrics = QuantEngine.portfolio_metrics(body.returns, body.weights)
    return PortfolioMetricsResponse(**metrics)


# ---------------------------------------------------------------------------
# Covariance Matrix
# ---------------------------------------------------------------------------
@router.post("/covariance", response_model=CovarianceMatrixResponse)
async def calculate_covariance(
    body: CovarianceRequest,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Compute and store a covariance matrix for the given symbols."""
    if len(body.symbols) != len(body.returns):
        raise HTTPException(status_code=400, detail="symbols and returns must have the same length")

    matrix = QuantEngine.covariance_matrix(body.returns)
    matrix_json = json.dumps(matrix)

    cov_record = CovarianceMatrix(
        symbols=",".join(body.symbols),
        window_days=body.window_days,
        matrix_data=matrix_json,
    )
    session.add(cov_record)
    await session.flush()

    return cov_record
