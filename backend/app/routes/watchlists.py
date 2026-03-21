import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import AuthUser, require_auth
from app.models.watchlist import Watchlist, WatchlistItem
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistResponse,
)
from app.services.audit import write_audit_log

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/watchlists", response_model=list[WatchlistResponse])
async def list_watchlists(
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
):
    result = await session.execute(
        select(Watchlist)
        .where(Watchlist.user_id == auth.user_id)
        .options(selectinload(Watchlist.items))
        .order_by(Watchlist.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.post("/watchlists", response_model=WatchlistResponse, status_code=201)
async def create_watchlist(
    body: WatchlistCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    watchlist = Watchlist(user_id=auth.user_id, name=body.name)
    session.add(watchlist)
    await session.flush()
    await session.refresh(watchlist, ["items"])
    await write_audit_log(session, auth.user_id, "create", "watchlist", {"id": watchlist.id})
    return watchlist


@router.post("/watchlists/{watchlist_id}/items", response_model=WatchlistItemResponse, status_code=201)
async def add_watchlist_item(
    watchlist_id: str,
    body: WatchlistItemCreate,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await session.execute(
        select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.user_id == auth.user_id)
    )
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Resource not found")

    item = WatchlistItem(
        watchlist_id=watchlist_id,
        symbol=body.symbol.upper(),
        asset_type=body.asset_type,
    )
    session.add(item)
    await session.flush()
    return item


@router.delete("/watchlists/{watchlist_id}", status_code=204)
async def delete_watchlist(
    watchlist_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.user_id == auth.user_id)
    )
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Resource not found")

    await session.delete(watchlist)
    await write_audit_log(session, auth.user_id, "delete", "watchlist", {"id": watchlist_id})


@router.delete("/watchlists/{watchlist_id}/items/{item_id}", status_code=204)
async def remove_watchlist_item(
    watchlist_id: str,
    item_id: str,
    auth: AuthUser = Depends(require_auth),
    session: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await session.execute(
        select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.user_id == auth.user_id)
    )
    watchlist = result.scalar_one_or_none()
    if not watchlist:
        raise HTTPException(status_code=404, detail="Resource not found")

    result = await session.execute(
        select(WatchlistItem).where(
            WatchlistItem.id == item_id, WatchlistItem.watchlist_id == watchlist_id
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Resource not found")

    await session.delete(item)
