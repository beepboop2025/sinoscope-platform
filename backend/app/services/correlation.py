"""
Cross-market Pearson correlation calculation.

Computes a correlation matrix for a set of symbols using historical
MarketTick data from the database.

Usage:
    from app.services.correlation import CorrelationService

    svc = CorrelationService()
    matrix = await svc.get_correlations(
        symbols=["BTC", "ETH", "SPY"],
        window_days=30,
        db_session=session,
    )
    # matrix["BTC"]["ETH"] -> 0.87
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import MarketTick

logger = logging.getLogger(__name__)


class CorrelationService:
    """Computes Pearson correlation matrices from MarketTick data."""

    async def get_correlations(
        self,
        symbols: list[str],
        db_session: AsyncSession,
        window_days: int = 30,
    ) -> dict[str, dict[str, float | None]]:
        """
        Compute pairwise Pearson correlation for a list of symbols.

        Args:
            symbols: List of ticker symbols (e.g. ["BTC", "ETH", "SPY"]).
            db_session: Active async DB session.
            window_days: Number of days of historical data to use.

        Returns:
            Nested dict: ``result[sym_a][sym_b] = correlation_value``.
            Correlation is None if insufficient data for a pair.
        """
        if len(symbols) < 2:
            return {s: {s: 1.0} for s in symbols}

        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

        # Fetch price time series for all requested symbols
        series = await self._fetch_price_series(symbols, cutoff, db_session)

        # Align series to common timestamps and compute correlations
        return self._compute_matrix(symbols, series)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _fetch_price_series(
        self,
        symbols: list[str],
        cutoff: datetime,
        db_session: AsyncSession,
    ) -> dict[str, list[tuple[datetime, float]]]:
        """
        Fetch (time, price) tuples for each symbol from MarketTick.

        Returns:
            Dict mapping symbol -> sorted list of (time, price).
        """
        result = await db_session.execute(
            select(MarketTick.symbol, MarketTick.time, MarketTick.price)
            .where(
                MarketTick.symbol.in_(symbols),
                MarketTick.time >= cutoff,
                MarketTick.price.isnot(None),
            )
            .order_by(MarketTick.symbol, MarketTick.time)
        )

        series: dict[str, list[tuple[datetime, float]]] = {s: [] for s in symbols}
        for row in result.all():
            sym, ts, price = row[0], row[1], row[2]
            if sym in series:
                series[sym].append((ts, float(price)))

        return series

    @staticmethod
    def _compute_matrix(
        symbols: list[str],
        series: dict[str, list[tuple[datetime, float]]],
    ) -> dict[str, dict[str, float | None]]:
        """
        Build a correlation matrix using numpy for the actual computation.

        Aligns each pair of series by finding the closest timestamps
        (within a 5-minute tolerance), converts to daily returns, then
        computes Pearson correlation.
        """
        try:
            import numpy as np
        except ImportError:
            logger.error("numpy is required for correlation calculation")
            return {
                s1: {s2: None for s2 in symbols}
                for s1 in symbols
            }

        # Convert series to daily close prices keyed by date
        daily: dict[str, dict[str, float]] = {}
        for sym, points in series.items():
            day_map: dict[str, float] = {}
            for ts, price in points:
                day_key = ts.strftime("%Y-%m-%d")
                # Keep the last (most recent) price for each day
                day_map[day_key] = price
            daily[sym] = day_map

        # Build the matrix
        matrix: dict[str, dict[str, float | None]] = {
            s: {s2: None for s2 in symbols} for s in symbols
        }

        for i, sym_a in enumerate(symbols):
            matrix[sym_a][sym_a] = 1.0
            for j in range(i + 1, len(symbols)):
                sym_b = symbols[j]
                corr = _pearson_from_daily(
                    daily.get(sym_a, {}),
                    daily.get(sym_b, {}),
                    np,
                )
                matrix[sym_a][sym_b] = corr
                matrix[sym_b][sym_a] = corr

        return matrix


def _pearson_from_daily(
    daily_a: dict[str, float],
    daily_b: dict[str, float],
    np: Any,
) -> float | None:
    """
    Compute Pearson correlation of daily returns for two series.

    Args:
        daily_a: date_str -> closing price for symbol A.
        daily_b: date_str -> closing price for symbol B.
        np: numpy module reference.

    Returns:
        Correlation coefficient, or None if fewer than 5 overlapping points.
    """
    # Find common dates (sorted)
    common_dates = sorted(set(daily_a.keys()) & set(daily_b.keys()))
    if len(common_dates) < 5:
        return None

    prices_a = np.array([daily_a[d] for d in common_dates], dtype=np.float64)
    prices_b = np.array([daily_b[d] for d in common_dates], dtype=np.float64)

    # Compute log returns (avoids division-by-zero with zero prices)
    with np.errstate(divide="ignore", invalid="ignore"):
        returns_a = np.diff(np.log(prices_a))
        returns_b = np.diff(np.log(prices_b))

    # Filter out NaN/Inf from log of zero or negative prices
    mask = np.isfinite(returns_a) & np.isfinite(returns_b)
    returns_a = returns_a[mask]
    returns_b = returns_b[mask]

    if len(returns_a) < 4:
        return None

    # Pearson correlation
    corr_matrix = np.corrcoef(returns_a, returns_b)
    corr = corr_matrix[0, 1]

    if np.isnan(corr):
        return None

    return round(float(corr), 4)
