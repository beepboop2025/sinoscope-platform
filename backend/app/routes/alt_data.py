"""Alternative data routes — insider trades, short interest, trends, patents, etc."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.alt_data import (
    GovernmentContract,
    GoogleTrend,
    InsiderTrade,
    JobPosting,
    PatentFiling,
    ShortInterest,
    WeatherImpact,
)
from app.schemas.alt_data import (
    AltDataSummary,
    GovernmentContractResponse,
    GoogleTrendResponse,
    InsiderTradeResponse,
    JobPostingResponse,
    PatentFilingResponse,
    ShortInterestResponse,
    WeatherImpactResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alt-data", tags=["alt-data"])


# ── Insider Trades ────────────────────────────────────────────────────────────

@router.get("/insider-trades", response_model=list[InsiderTradeResponse])
async def list_insider_trades(
    symbol: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    """List insider trades, optionally filtered by symbol."""
    stmt = select(InsiderTrade).order_by(InsiderTrade.filing_date.desc()).limit(limit)
    if symbol:
        stmt = stmt.where(InsiderTrade.symbol == symbol.upper())
    rows = (await session.execute(stmt)).scalars().all()
    return rows


# ── Short Interest ────────────────────────────────────────────────────────────

@router.get("/short-interest", response_model=list[ShortInterestResponse])
async def list_short_interest(
    symbol: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    """List short interest reports, optionally filtered by symbol."""
    stmt = select(ShortInterest).order_by(ShortInterest.report_date.desc()).limit(limit)
    if symbol:
        stmt = stmt.where(ShortInterest.symbol == symbol.upper())
    rows = (await session.execute(stmt)).scalars().all()
    return rows


# ── Google Trends ─────────────────────────────────────────────────────────────

@router.get("/trends", response_model=list[GoogleTrendResponse])
async def list_trends(
    keyword: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    """List Google Trends data, optionally filtered by keyword."""
    stmt = select(GoogleTrend).order_by(GoogleTrend.date.desc()).limit(limit)
    if keyword:
        stmt = stmt.where(GoogleTrend.keyword == keyword)
    rows = (await session.execute(stmt)).scalars().all()
    return rows


# ── Government Contracts ──────────────────────────────────────────────────────

@router.get("/government-contracts", response_model=list[GovernmentContractResponse])
async def list_government_contracts(
    vendor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    """List government contracts, optionally filtered by vendor."""
    stmt = select(GovernmentContract).order_by(GovernmentContract.award_date.desc()).limit(limit)
    if vendor:
        stmt = stmt.where(GovernmentContract.vendor.ilike(f"%{vendor}%"))
    rows = (await session.execute(stmt)).scalars().all()
    return rows


# ── Patents ───────────────────────────────────────────────────────────────────

@router.get("/patents", response_model=list[PatentFilingResponse])
async def list_patents(
    assignee: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    """List patent filings, optionally filtered by assignee."""
    stmt = select(PatentFiling).order_by(PatentFiling.filing_date.desc()).limit(limit)
    if assignee:
        stmt = stmt.where(PatentFiling.assignee.ilike(f"%{assignee}%"))
    rows = (await session.execute(stmt)).scalars().all()
    return rows


# ── Job Postings ──────────────────────────────────────────────────────────────

@router.get("/jobs", response_model=list[JobPostingResponse])
async def list_jobs(
    company: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    """List job postings, optionally filtered by company."""
    stmt = select(JobPosting).order_by(JobPosting.created_at.desc()).limit(limit)
    if company:
        stmt = stmt.where(JobPosting.company.ilike(f"%{company}%"))
    rows = (await session.execute(stmt)).scalars().all()
    return rows


# ── Weather Impact ────────────────────────────────────────────────────────────

@router.get("/weather", response_model=list[WeatherImpactResponse])
async def list_weather_impacts(
    region: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db),
):
    """List weather impact events, optionally filtered by region."""
    stmt = select(WeatherImpact).order_by(WeatherImpact.start_date.desc()).limit(limit)
    if region:
        stmt = stmt.where(WeatherImpact.region.ilike(f"%{region}%"))
    rows = (await session.execute(stmt)).scalars().all()
    return rows


# ── Aggregated Summary ────────────────────────────────────────────────────────

@router.get("/summary/{symbol}", response_model=AltDataSummary)
async def get_alt_data_summary(
    symbol: str,
    session: AsyncSession = Depends(get_db),
):
    """Get aggregated alternative data summary for a symbol."""
    symbol = symbol.upper()

    # Insider trades count
    trades_result = await session.execute(
        select(InsiderTrade).where(InsiderTrade.symbol == symbol)
    )
    trades = list(trades_result.scalars().all())

    # Latest short interest
    si_result = await session.execute(
        select(ShortInterest)
        .where(ShortInterest.symbol == symbol)
        .order_by(ShortInterest.report_date.desc())
        .limit(1)
    )
    si = si_result.scalar_one_or_none()

    # Google Trends score for the symbol
    trend_result = await session.execute(
        select(GoogleTrend)
        .where(GoogleTrend.keyword == symbol)
        .order_by(GoogleTrend.date.desc())
        .limit(1)
    )
    trend = trend_result.scalar_one_or_none()

    # Government contracts (search vendor by symbol — rough match)
    contracts_result = await session.execute(
        select(GovernmentContract).where(
            GovernmentContract.vendor.ilike(f"%{symbol}%")
        )
    )
    contracts = list(contracts_result.scalars().all())

    return AltDataSummary(
        symbol=symbol,
        insider_trades_count=len(trades),
        short_interest_latest=float(si.short_interest) if si else None,
        trend_score=trend.interest_score if trend else None,
        recent_contracts=len(contracts),
    )
