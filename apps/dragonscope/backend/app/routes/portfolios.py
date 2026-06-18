import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.portfolio import Holding, Portfolio
from app.schemas.portfolio import (
    HoldingCreate,
    HoldingResponse,
    PortfolioCreate,
    PortfolioResponse,
    PortfolioUpdate,
)
from app.services.audit import write_audit_log

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/portfolios", response_model=list[PortfolioResponse])
async def list_portfolios(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
):
    result = await session.execute(
        select(Portfolio)
        .where(Portfolio.user_id == auth.user_id)
        .options(selectinload(Portfolio.holdings))
        .order_by(Portfolio.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    portfolios = list(result.scalars().all())
    return portfolios


@router.post("/portfolios", response_model=PortfolioResponse, status_code=201)
async def create_portfolio(
    body: PortfolioCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    portfolio = Portfolio(
        user_id=auth.user_id,
        name=body.name,
        description=body.description,
    )
    session.add(portfolio)
    await session.flush()
    await session.refresh(portfolio, ["holdings"])
    await write_audit_log(session, auth.user_id, "create", "portfolio", {"id": portfolio.id})
    return portfolio


@router.patch("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
async def update_portfolio(
    portfolio_id: str,
    body: PortfolioUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Portfolio)
        .where(Portfolio.id == portfolio_id, Portfolio.user_id == auth.user_id)
        .options(selectinload(Portfolio.holdings))
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Resource not found")

    if body.name is not None:
        portfolio.name = body.name
    if body.description is not None:
        portfolio.description = body.description

    await session.flush()
    await session.refresh(portfolio)
    return portfolio


@router.delete("/portfolios/{portfolio_id}", status_code=204)
async def delete_portfolio(
    portfolio_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == auth.user_id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Resource not found")

    await session.delete(portfolio)
    await write_audit_log(session, auth.user_id, "delete", "portfolio", {"id": portfolio_id})


@router.post("/portfolios/{portfolio_id}/holdings", response_model=HoldingResponse, status_code=201)
async def add_holding(
    portfolio_id: str,
    body: HoldingCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Verify portfolio ownership
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == auth.user_id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Resource not found")

    holding = Holding(
        portfolio_id=portfolio_id,
        symbol=body.symbol.upper(),
        asset_type=body.asset_type,
        quantity=body.quantity,
        avg_cost=body.avg_cost,
        notes=body.notes,
    )
    session.add(holding)
    await session.flush()
    return holding


@router.delete("/portfolios/{portfolio_id}/holdings/{holding_id}", status_code=204)
async def remove_holding(
    portfolio_id: str,
    holding_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Verify portfolio ownership
    result = await session.execute(
        select(Portfolio).where(Portfolio.id == portfolio_id, Portfolio.user_id == auth.user_id)
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Resource not found")

    result = await session.execute(
        select(Holding).where(Holding.id == holding_id, Holding.portfolio_id == portfolio_id)
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(status_code=404, detail="Resource not found")

    await session.delete(holding)
