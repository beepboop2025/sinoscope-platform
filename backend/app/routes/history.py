"""Historical time-series data routes backed by TimescaleDB."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.database import async_session_factory
from app.schemas.history import (
    CandleResponse,
    SnapshotResponse,
    StatsResponse,
    SymbolInfo,
    TickResponse,
    TimeSeriesResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_INTERVALS = {"1h", "1d", "1w"}
INTERVAL_VIEW_MAP = {"1h": "market_ticks_1h", "1d": "market_ticks_1d", "1w": "market_ticks_1w"}


def _default_start() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=7)


def _default_end() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/history/ticks/{symbol}", response_model=TimeSeriesResponse)
async def get_ticks(
    symbol: str,
    start: datetime | None = Query(None, description="Start time (ISO 8601)"),
    end: datetime | None = Query(None, description="End time (ISO 8601)"),
    category: str | None = Query(None, description="Filter by category"),
    limit: int = Query(1000, ge=1, le=10000),
):
    """Raw tick data for a given symbol."""
    start = start or _default_start()
    end = end or _default_end()

    conditions = ["symbol = :symbol", "time >= :start", "time <= :end"]
    params: dict = {"symbol": symbol.upper(), "start": start, "end": end, "limit": limit}

    if category:
        conditions.append("category = :category")
        params["category"] = category

    where = " AND ".join(conditions)
    sql = text(f"""
        SELECT time, symbol, category, price, open, high, low, volume, market_cap, change_pct, extra
        FROM market_ticks
        WHERE {where}
        ORDER BY time DESC
        LIMIT :limit
    """)

    async with async_session_factory() as session:
        result = await session.execute(sql, params)
        rows = result.mappings().all()

    ticks = [TickResponse(**dict(r)) for r in rows]
    return TimeSeriesResponse(data=ticks, count=len(ticks), symbol=symbol.upper())


@router.get("/history/candles/{symbol}", response_model=TimeSeriesResponse)
async def get_candles(
    symbol: str,
    interval: str = Query("1h", description="Candle interval: 1h, 1d, 1w"),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(500, ge=1, le=10000),
):
    """OHLCV candles from continuous aggregates."""
    if interval not in VALID_INTERVALS:
        return TimeSeriesResponse(data=[], count=0, symbol=symbol.upper(), interval=interval)

    start = start or _default_start()
    end = end or _default_end()
    view = INTERVAL_VIEW_MAP[interval]

    sql = text(f"""
        SELECT bucket, symbol, category, open, high, low, close, volume, market_cap, tick_count
        FROM {view}
        WHERE symbol = :symbol AND bucket >= :start AND bucket <= :end
        ORDER BY bucket DESC
        LIMIT :limit
    """)

    async with async_session_factory() as session:
        result = await session.execute(sql, {
            "symbol": symbol.upper(), "start": start, "end": end, "limit": limit,
        })
        rows = result.mappings().all()

    candles = [CandleResponse(**dict(r)) for r in rows]
    return TimeSeriesResponse(data=candles, count=len(candles), symbol=symbol.upper(), interval=interval)


@router.get("/history/snapshots/{category}", response_model=list[SnapshotResponse])
async def get_snapshots(
    category: str,
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """Historical JSON snapshots for a category."""
    start = start or _default_start()
    end = end or _default_end()

    sql = text("""
        SELECT time, category, snapshot, record_count
        FROM snapshot_logs
        WHERE category = :category AND time >= :start AND time <= :end
        ORDER BY time DESC
        LIMIT :limit
    """)

    async with async_session_factory() as session:
        result = await session.execute(sql, {
            "category": category, "start": start, "end": end, "limit": limit,
        })
        rows = result.mappings().all()

    return [SnapshotResponse(**dict(r)) for r in rows]


@router.get("/history/symbols", response_model=list[SymbolInfo])
async def list_symbols(
    category: str | None = Query(None, description="Filter by category"),
):
    """List all symbols with latest price and data point count."""
    conditions = []
    params: dict = {}
    if category:
        conditions.append("WHERE category = :category")
        params["category"] = category

    where = conditions[0] if conditions else ""

    sql = text(f"""
        SELECT
            symbol,
            category,
            last(price, time)   AS latest_price,
            max(time)           AS latest_time,
            count(*)            AS data_points
        FROM market_ticks
        {where}
        GROUP BY symbol, category
        ORDER BY symbol
    """)

    async with async_session_factory() as session:
        result = await session.execute(sql, params)
        rows = result.mappings().all()

    return [SymbolInfo(**dict(r)) for r in rows]


@router.get("/history/stats", response_model=StatsResponse)
async def get_stats():
    """TimescaleDB statistics — hypertable sizes, chunk counts, compression."""
    stats = StatsResponse()

    async with async_session_factory() as session:
        # TimescaleDB version
        try:
            result = await session.execute(text(
                "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"
            ))
            row = result.scalar_one_or_none()
            stats.timescaledb_version = row
        except Exception:
            pass

        # Hypertable info
        try:
            result = await session.execute(text("""
                SELECT
                    hypertable_name,
                    num_chunks,
                    pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) AS size_pretty,
                    hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass) AS size_bytes
                FROM timescaledb_information.hypertables
                WHERE hypertable_schema = 'public'
            """))
            rows = result.mappings().all()
            total_chunks = 0
            total_size = 0
            for r in rows:
                d = dict(r)
                total_chunks += d.get("num_chunks", 0) or 0
                total_size += d.get("size_bytes", 0) or 0
                stats.hypertables.append(d)
            stats.total_chunks = total_chunks
            stats.total_size_bytes = total_size
        except Exception:
            pass

        # Compression stats
        try:
            result = await session.execute(text("""
                SELECT
                    sum(before_compression_total_bytes) AS before_bytes,
                    sum(after_compression_total_bytes) AS after_bytes
                FROM hypertable_compression_stats('market_ticks')
            """))
            row = result.mappings().first()
            if row and row["before_bytes"] and row["after_bytes"] and row["before_bytes"] > 0:
                stats.compression_ratio = round(row["before_bytes"] / row["after_bytes"], 2)
        except Exception:
            pass

    return stats
