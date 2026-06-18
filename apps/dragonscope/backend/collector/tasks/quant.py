"""Celery tasks for quantitative analytics — yield curve fetching and covariance computation."""

import json
import logging
import time
import uuid
from datetime import date, datetime, timezone

import psycopg2
import psycopg2.extras

from app.config import get_settings
from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, safe_fetch

logger = logging.getLogger(__name__)
settings = get_settings()

# FRED series for Treasury yield curve
TREASURY_SERIES = {
    "1M": "DGS1MO",
    "3M": "DGS3MO",
    "6M": "DGS6MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "10Y": "DGS10",
    "30Y": "DGS30",
}


def _get_sync_dsn() -> str:
    """Convert async DATABASE_URL to sync psycopg2 DSN."""
    url = settings.DATABASE_URL
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _get_conn():
    """Get a synchronous psycopg2 connection."""
    return psycopg2.connect(_get_sync_dsn())


@celery_app.task(name="collector.tasks.quant.fetch_yield_curve", bind=True, max_retries=3)
def fetch_yield_curve(self):
    """Fetch Treasury yield curve data from FRED API and save to DB."""
    fred_key = settings.FRED_API_KEY
    if not fred_key:
        logger.warning("[QUANT] No FRED_API_KEY configured — skipping yield curve fetch")
        return

    today = date.today()
    rows = []

    for tenor, series_id in TREASURY_SERIES.items():
        if not can_request("fred"):
            logger.warning("[QUANT] FRED rate limit reached — stopping")
            break
        consume_token("fred")

        try:
            resp = safe_fetch(
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={series_id}&api_key={fred_key}&file_type=json"
                f"&sort_order=desc&limit=1"
            )
            data = resp.json()
            observations = data.get("observations", [])

            for obs in observations:
                value = obs.get("value", ".")
                if value == ".":
                    continue
                rate = float(value)
                obs_date = obs.get("date", str(today))
                rows.append((
                    str(uuid.uuid4()),
                    obs_date,
                    tenor,
                    rate,
                    "FRED",
                    datetime.now(timezone.utc),
                ))

        except Exception as e:
            logger.error(f"[QUANT] Failed to fetch {tenor} ({series_id}): {e}")

        time.sleep(0.2)  # Be polite to FRED

    if not rows:
        logger.info("[QUANT] No yield curve data fetched")
        return

    # Bulk upsert into yield_curves table
    sql = """
        INSERT INTO yield_curves (id, date, tenor, rate, source, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (date, tenor) DO UPDATE SET
            rate = EXCLUDED.rate,
            source = EXCLUDED.source
    """

    try:
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, sql, rows)
            conn.commit()
            logger.info(f"[QUANT] Yield curve: saved {len(rows)} tenors")
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"[QUANT] Failed to persist yield curve: {e}")
        raise self.retry(exc=e, countdown=60)


@celery_app.task(name="collector.tasks.quant.compute_covariance", bind=True, max_retries=2)
def compute_covariance(self, symbols: list[str] | None = None, window_days: int = 60):
    """Compute covariance matrix from recent price data stored in market_ticks.

    Args:
        symbols: List of symbols to compute covariance for.
                 Defaults to top crypto symbols.
        window_days: Number of days of historical data to use.
    """
    if symbols is None:
        symbols = ["BTC", "ETH", "BNB", "SOL", "ADA"]

    try:
        conn = _get_conn()
        try:
            returns_by_symbol: dict[str, list[float]] = {}

            with conn.cursor() as cur:
                for symbol in symbols:
                    cur.execute(
                        """
                        SELECT price FROM market_ticks
                        WHERE symbol = %s AND price IS NOT NULL
                        ORDER BY time DESC
                        LIMIT %s
                        """,
                        (symbol, window_days + 1),
                    )
                    prices = [row[0] for row in cur.fetchall()]
                    prices.reverse()  # oldest first

                    if len(prices) < 2:
                        logger.warning(f"[QUANT] Not enough price data for {symbol}")
                        continue

                    # Compute daily returns
                    rets = []
                    for i in range(1, len(prices)):
                        if prices[i - 1] > 0:
                            rets.append((prices[i] - prices[i - 1]) / prices[i - 1])
                    returns_by_symbol[symbol] = rets

            # Only proceed if we have at least 2 symbols with data
            valid_symbols = [s for s in symbols if s in returns_by_symbol and len(returns_by_symbol[s]) >= 2]
            if len(valid_symbols) < 2:
                logger.info("[QUANT] Not enough valid symbols for covariance matrix")
                return

            # Align returns to the same length
            min_len = min(len(returns_by_symbol[s]) for s in valid_symbols)
            matrix_data: list[list[float]] = []
            for s in valid_symbols:
                matrix_data.append(returns_by_symbol[s][:min_len])

            # Compute covariance
            from app.services.quant_engine import QuantEngine
            cov = QuantEngine.covariance_matrix(matrix_data)

            # Persist
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO covariance_matrices (id, symbols, window_days, matrix_data, computed_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        ",".join(valid_symbols),
                        window_days,
                        json.dumps(cov),
                        datetime.now(timezone.utc),
                    ),
                )
            conn.commit()
            logger.info(f"[QUANT] Covariance matrix computed for {valid_symbols}")

        finally:
            conn.close()

    except Exception as e:
        logger.error(f"[QUANT] Covariance computation failed: {e}")
        raise self.retry(exc=e, countdown=120)
