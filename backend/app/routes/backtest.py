"""Backtesting framework API routes."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.backtest import BacktestRun, BacktestTrade, Strategy
from app.schemas.backtest import (
    BacktestRunCreate,
    BacktestRunResponse,
    BacktestTradeResponse,
    StrategyCreate,
    StrategyResponse,
    StrategyUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
@router.post("/strategies", response_model=StrategyResponse, status_code=201)
async def create_strategy(
    body: StrategyCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Create a new trading strategy."""
    strategy = Strategy(
        user_id=auth.user_id,
        name=body.name,
        description=body.description,
        dsl_config=json.dumps(body.dsl_config),
        is_public=body.is_public,
    )
    session.add(strategy)
    await session.flush()
    return strategy


@router.get("/strategies", response_model=list[StrategyResponse])
async def list_strategies(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List the current user's strategies."""
    result = await session.execute(
        select(Strategy)
        .where(Strategy.user_id == auth.user_id)
        .order_by(Strategy.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/strategies/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get a strategy by ID (must belong to user or be public)."""
    result = await session.execute(
        select(Strategy).where(Strategy.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy.user_id != auth.user_id and not strategy.is_public:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.put("/strategies/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: str,
    body: StrategyUpdate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Update a strategy (must belong to user)."""
    result = await session.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == auth.user_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if body.name is not None:
        strategy.name = body.name
    if body.description is not None:
        strategy.description = body.description
    if body.dsl_config is not None:
        strategy.dsl_config = json.dumps(body.dsl_config)
    if body.is_public is not None:
        strategy.is_public = body.is_public

    await session.flush()
    return strategy


@router.delete("/strategies/{strategy_id}", status_code=204)
async def delete_strategy(
    strategy_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Delete a strategy (must belong to user)."""
    result = await session.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == auth.user_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    await session.delete(strategy)


# ---------------------------------------------------------------------------
# Backtest Runs
# ---------------------------------------------------------------------------
@router.post("/backtests", response_model=BacktestRunResponse, status_code=201)
async def launch_backtest(
    body: BacktestRunCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Launch a backtest run. Execution happens asynchronously via Celery."""
    # Verify the strategy exists and belongs to user (or is public)
    result = await session.execute(
        select(Strategy).where(Strategy.id == body.strategy_id)
    )
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    if strategy.user_id != auth.user_id and not strategy.is_public:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if body.end_date <= body.start_date:
        raise HTTPException(status_code=400, detail="end_date must be after start_date")

    backtest_run = BacktestRun(
        strategy_id=body.strategy_id,
        user_id=auth.user_id,
        status="pending",
        start_date=body.start_date,
        end_date=body.end_date,
        initial_capital=body.initial_capital,
    )
    session.add(backtest_run)
    await session.flush()

    # Dispatch to Celery
    try:
        from collector.tasks.backtest import run_backtest_task
        run_backtest_task.delay(backtest_run.id)
        logger.info(f"Backtest {backtest_run.id} dispatched to Celery")
    except Exception as e:
        logger.error(f"Failed to dispatch backtest task: {e}")
        # Still return the run — it can be retried

    return backtest_run


@router.get("/backtests", response_model=list[BacktestRunResponse])
async def list_backtests(
    strategy_id: str | None = Query(None),
    status: str | None = Query(None),
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """List the current user's backtest runs."""
    query = (
        select(BacktestRun)
        .where(BacktestRun.user_id == auth.user_id)
        .order_by(BacktestRun.created_at.desc())
    )
    if strategy_id:
        query = query.where(BacktestRun.strategy_id == strategy_id)
    if status:
        query = query.where(BacktestRun.status == status)

    result = await session.execute(query)
    return list(result.scalars().all())


@router.get("/backtests/{backtest_id}", response_model=BacktestRunResponse)
async def get_backtest(
    backtest_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get a backtest run by ID."""
    result = await session.execute(
        select(BacktestRun).where(
            BacktestRun.id == backtest_id,
            BacktestRun.user_id == auth.user_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return run


@router.get("/backtests/{backtest_id}/trades", response_model=list[BacktestTradeResponse])
async def get_backtest_trades(
    backtest_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    """Get trades for a backtest run."""
    # Verify ownership
    result = await session.execute(
        select(BacktestRun).where(
            BacktestRun.id == backtest_id,
            BacktestRun.user_id == auth.user_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    trades_result = await session.execute(
        select(BacktestTrade)
        .where(BacktestTrade.backtest_id == backtest_id)
        .order_by(BacktestTrade.timestamp.asc())
    )
    return list(trades_result.scalars().all())
