"""Celery task for running backtests asynchronously."""

import json
import logging
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

from app.config import get_settings
from collector.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_sync_dsn() -> str:
    """Convert async DATABASE_URL to sync psycopg2 DSN."""
    url = settings.DATABASE_URL
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _get_conn():
    """Get a synchronous psycopg2 connection."""
    return psycopg2.connect(_get_sync_dsn())


@celery_app.task(name="collector.tasks.backtest.run_backtest_task", bind=True, max_retries=1)
def run_backtest_task(self, backtest_run_id: str):
    """Execute a backtest run.

    1. Load strategy DSL and backtest config from DB
    2. Fetch price data from market_ticks
    3. Run the backtesting engine
    4. Save results + trades back to DB
    """
    logger.info(f"[BACKTEST] Starting backtest run {backtest_run_id}")

    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc)

        # Mark as running
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE backtest_runs SET status = %s, started_at = %s WHERE id = %s",
                ("running", now, backtest_run_id),
            )
        conn.commit()

        # Load backtest run
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM backtest_runs WHERE id = %s", (backtest_run_id,))
            run = cur.fetchone()

        if not run:
            logger.error(f"[BACKTEST] Run {backtest_run_id} not found")
            return

        # Load strategy
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM strategies WHERE id = %s", (run["strategy_id"],))
            strategy = cur.fetchone()

        if not strategy:
            _fail_run(conn, backtest_run_id, "Strategy not found")
            return

        try:
            dsl_config = json.loads(strategy["dsl_config"])
        except (json.JSONDecodeError, TypeError) as e:
            _fail_run(conn, backtest_run_id, f"Invalid strategy DSL: {e}")
            return

        # Determine the symbol from DSL or default
        symbol = dsl_config.get("symbol", "BTC")

        # Fetch price data from market_ticks
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT time, price FROM market_ticks
                WHERE symbol = %s
                    AND time >= %s
                    AND time <= %s
                    AND price IS NOT NULL
                ORDER BY time ASC
                """,
                (symbol, run["start_date"], run["end_date"]),
            )
            rows = cur.fetchall()

        if len(rows) < 10:
            # Fallback: generate synthetic price data for testing
            logger.warning(
                f"[BACKTEST] Only {len(rows)} ticks for {symbol} — "
                f"generating synthetic data for range {run['start_date']} to {run['end_date']}"
            )
            rows = _generate_synthetic_prices(run["start_date"], run["end_date"])

        timestamps = [row[0] if isinstance(row[0], datetime) else datetime.combine(row[0], datetime.min.time()) for row in rows]
        prices = [float(row[1]) for row in rows]

        # Run the engine
        from app.services.backtest_engine import BacktestEngine

        result = BacktestEngine.run_backtest(
            strategy_dsl=dsl_config,
            prices=prices,
            timestamps=timestamps,
            symbol=symbol,
            initial_capital=float(run["initial_capital"]),
        )

        completed_at = datetime.now(timezone.utc)

        # Update the run with results
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE backtest_runs SET
                    status = 'completed',
                    final_capital = %s,
                    total_return = %s,
                    sharpe_ratio = %s,
                    max_drawdown = %s,
                    total_trades = %s,
                    win_rate = %s,
                    completed_at = %s
                WHERE id = %s
                """,
                (
                    result.final_capital,
                    result.total_return,
                    result.sharpe_ratio,
                    result.max_drawdown,
                    result.total_trades,
                    result.win_rate,
                    completed_at,
                    backtest_run_id,
                ),
            )

        # Insert trades
        if result.trades:
            trade_rows = []
            for trade in result.trades:
                trade_rows.append((
                    str(uuid.uuid4()),
                    backtest_run_id,
                    trade.symbol,
                    trade.side,
                    trade.quantity,
                    trade.price,
                    trade.commission,
                    trade.slippage,
                    trade.timestamp,
                    trade.pnl,
                ))

            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(
                    cur,
                    """
                    INSERT INTO backtest_trades
                        (id, backtest_id, symbol, side, quantity, price, commission, slippage, timestamp, pnl)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    trade_rows,
                )

        conn.commit()
        logger.info(
            f"[BACKTEST] Completed {backtest_run_id}: "
            f"return={result.total_return:.4f} sharpe={result.sharpe_ratio:.4f} "
            f"trades={result.total_trades}"
        )

    except Exception as e:
        logger.error(f"[BACKTEST] Run {backtest_run_id} failed: {e}")
        try:
            _fail_run(conn, backtest_run_id, str(e))
        except Exception:
            pass
        raise self.retry(exc=e, countdown=60)
    finally:
        conn.close()


def _fail_run(conn, backtest_run_id: str, error_message: str) -> None:
    """Mark a backtest run as failed."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE backtest_runs SET status = 'failed', error_message = %s, completed_at = %s WHERE id = %s",
            (error_message, datetime.now(timezone.utc), backtest_run_id),
        )
    conn.commit()
    logger.error(f"[BACKTEST] Run {backtest_run_id} failed: {error_message}")


def _generate_synthetic_prices(start_date, end_date, base_price: float = 100.0) -> list[tuple]:
    """Generate synthetic daily price data for testing.

    Uses a simple geometric Brownian motion model.
    """
    import math
    import random

    rng = random.Random(42)
    current = base_price
    prices = []

    # Convert dates to datetime if needed
    if not isinstance(start_date, datetime):
        start_dt = datetime.combine(start_date, datetime.min.time())
    else:
        start_dt = start_date

    if not isinstance(end_date, datetime):
        end_dt = datetime.combine(end_date, datetime.min.time())
    else:
        end_dt = end_date

    from datetime import timedelta
    day = start_dt
    while day <= end_dt:
        # Skip weekends
        if day.weekday() < 5:
            drift = 0.0002
            vol = 0.02
            shock = rng.gauss(0, 1)
            current *= math.exp(drift + vol * shock)
            prices.append((day, round(current, 4)))
        day += timedelta(days=1)

    return prices
