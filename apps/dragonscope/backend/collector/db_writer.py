"""Synchronous database writer for Celery workers.

Uses psycopg2 (sync) since Celery tasks are synchronous.
All writes are fire-and-forget — failures are logged but never block the collector.
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import psycopg2
import psycopg2.extras
import psycopg2.pool

from app.config import get_settings

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.SimpleConnectionPool | None = None

# Categories that produce individual ticks (symbol-level data)
TICK_CATEGORIES = {"crypto_markets", "stocks", "commodities", "forex"}

# Categories stored as full JSON snapshots only
SNAPSHOT_CATEGORIES = {
    "bonds", "economic", "news", "defi", "sentiment",
    "research", "china", "crypto_global", "crypto_trending",
    "forex_timeseries",
}


def _get_sync_dsn() -> str:
    """Convert async DATABASE_URL to sync psycopg2 DSN."""
    settings = get_settings()
    url = settings.DATABASE_URL
    # postgresql+asyncpg://... -> postgresql://...
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _get_pool() -> psycopg2.pool.SimpleConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1, maxconn=5, dsn=_get_sync_dsn()
        )
    return _pool


@contextmanager
def _get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_crypto_ticks(items: list[dict]) -> list[dict]:
    """Map CoinGecko /coins/markets response to tick rows."""
    ticks = []
    for item in items:
        symbol = item.get("symbol", "").upper()
        if not symbol:
            continue
        ticks.append({
            "symbol": symbol,
            "category": "crypto",
            "price": item.get("current_price"),
            "high": item.get("high_24h"),
            "low": item.get("low_24h"),
            "volume": item.get("total_volume"),
            "market_cap": item.get("market_cap"),
            "change_pct": item.get("price_change_percentage_24h"),
            "extra": {
                "name": item.get("name"),
                "rank": item.get("market_cap_rank"),
            },
        })
    return ticks


def _extract_stock_ticks(items: list[dict]) -> list[dict]:
    """Map Alpha Vantage quote list to tick rows."""
    ticks = []
    for item in items:
        symbol = item.get("symbol", "")
        if not symbol:
            continue
        ticks.append({
            "symbol": symbol,
            "category": "stocks",
            "price": item.get("price"),
            "open": item.get("open"),
            "high": item.get("high"),
            "low": item.get("low"),
            "volume": item.get("volume"),
            "change_pct": item.get("changePct"),
        })
    return ticks


def _extract_forex_ticks(data: dict) -> list[dict]:
    """Map Frankfurter rates response to tick rows."""
    rates = data.get("rates", {})
    base = data.get("base", "USD")
    ticks = []
    for currency, rate in rates.items():
        ticks.append({
            "symbol": f"{base}/{currency}",
            "category": "forex",
            "price": rate,
        })
    return ticks


def _extract_commodity_ticks(data: dict) -> list[dict]:
    """Map FRED commodity dict to tick rows."""
    ticks = []
    for name, info in data.items():
        if not isinstance(info, dict):
            continue
        ticks.append({
            "symbol": name,
            "category": "commodities",
            "price": info.get("price"),
        })
    return ticks


def _extract_ticks(category: str, data: Any) -> list[dict]:
    """Route category to appropriate extractor."""
    if category == "crypto_markets" and isinstance(data, list):
        return _extract_crypto_ticks(data)
    if category == "stocks" and isinstance(data, list):
        return _extract_stock_ticks(data)
    if category == "forex" and isinstance(data, dict):
        return _extract_forex_ticks(data)
    if category == "commodities" and isinstance(data, dict):
        return _extract_commodity_ticks(data)
    return []


def write_ticks(category: str, data: Any) -> None:
    """Extract individual ticks from collector data and bulk-upsert into market_ticks."""
    ticks = _extract_ticks(category, data)
    if not ticks:
        return

    now = _now()
    rows = []
    for t in ticks:
        rows.append((
            now,
            t["symbol"],
            t.get("category", category),
            t.get("price"),
            t.get("open"),
            t.get("high"),
            t.get("low"),
            t.get("volume"),
            t.get("market_cap"),
            t.get("change_pct"),
            psycopg2.extras.Json(t.get("extra")) if t.get("extra") else None,
        ))

    sql = """
        INSERT INTO market_ticks (time, symbol, category, price, open, high, low, volume, market_cap, change_pct, extra)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (time, symbol) DO UPDATE SET
            price = EXCLUDED.price,
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            volume = EXCLUDED.volume,
            market_cap = EXCLUDED.market_cap,
            change_pct = EXCLUDED.change_pct,
            extra = EXCLUDED.extra
    """

    with _get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, rows)

    logger.info(f"[DB_WRITER] Wrote {len(rows)} ticks for {category}")


def write_snapshot(category: str, data: Any) -> None:
    """Store full JSON payload as a snapshot in snapshot_logs."""
    record_count = None
    if isinstance(data, list):
        record_count = len(data)
    elif isinstance(data, dict):
        record_count = len(data.get("data", data))

    sql = """
        INSERT INTO snapshot_logs (time, category, snapshot, record_count)
        VALUES (%s, %s, %s, %s)
    """

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (
                _now(),
                category,
                psycopg2.extras.Json(data),
                record_count,
            ))

    logger.info(f"[DB_WRITER] Wrote snapshot for {category}")


def persist(category: str, data: Any) -> None:
    """Main entry point — called by base.save_data() after Redis write.

    Routes to write_ticks for tick-capable categories, write_snapshot for the rest.
    """
    try:
        if category in TICK_CATEGORIES:
            write_ticks(category, data)
        if category in SNAPSHOT_CATEGORIES or category not in TICK_CATEGORIES:
            write_snapshot(category, data)
    except Exception as e:
        # Never block the collector — log and move on
        logger.error(f"[DB_WRITER] Failed to persist {category}: {e}")
