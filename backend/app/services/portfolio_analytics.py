"""
Portfolio analytics: PnL, per-holding metrics with live prices.

Usage:
    from app.services.portfolio_analytics import PortfolioAnalytics

    analytics = PortfolioAnalytics()
    report = await analytics.get_analytics(portfolio_id, db_session)
"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.portfolio import Holding, Portfolio
from app.redis import get_redis

logger = logging.getLogger(__name__)


class PortfolioAnalytics:
    """Compute portfolio-level and per-holding performance metrics."""

    async def get_analytics(
        self,
        portfolio_id: str,
        db_session: AsyncSession,
    ) -> dict[str, Any] | None:
        """
        Calculate PnL and per-holding breakdown for a portfolio.

        Args:
            portfolio_id: The portfolio UUID.
            db_session: Active async DB session.

        Returns:
            Dict with portfolio-level and per-holding metrics, or None if
            the portfolio does not exist. Example::

                {
                    "portfolio_id": "...",
                    "portfolio_name": "Tech Bets",
                    "total_value": 25000.0,
                    "total_cost": 20000.0,
                    "unrealized_pnl": 5000.0,
                    "unrealized_pnl_pct": 25.0,
                    "holdings": [ ... ],
                }
        """
        # Fetch portfolio with holdings eagerly loaded
        result = await db_session.execute(
            select(Portfolio)
            .options(selectinload(Portfolio.holdings))
            .where(Portfolio.id == portfolio_id)
        )
        portfolio = result.scalar_one_or_none()
        if portfolio is None:
            return None

        holdings: list[Holding] = portfolio.holdings
        if not holdings:
            return {
                "portfolio_id": portfolio.id,
                "portfolio_name": portfolio.name,
                "total_value": 0.0,
                "total_cost": 0.0,
                "unrealized_pnl": 0.0,
                "unrealized_pnl_pct": 0.0,
                "holdings": [],
            }

        # Fetch live prices for all symbols in the portfolio
        symbols = {h.symbol for h in holdings}
        prices = await self._fetch_live_prices(symbols)

        total_value = 0.0
        total_cost = 0.0
        holding_details: list[dict[str, Any]] = []

        for h in holdings:
            cost_basis = h.quantity * h.avg_cost
            current_price = prices.get(h.symbol)
            market_value = h.quantity * current_price if current_price is not None else None

            pnl: float | None = None
            pnl_pct: float | None = None

            if market_value is not None:
                pnl = market_value - cost_basis
                pnl_pct = (pnl / cost_basis * 100.0) if cost_basis != 0.0 else 0.0
                total_value += market_value

            total_cost += cost_basis

            holding_details.append({
                "symbol": h.symbol,
                "asset_type": h.asset_type,
                "quantity": h.quantity,
                "avg_cost": h.avg_cost,
                "current_price": current_price,
                "market_value": _round_or_none(market_value),
                "pnl": _round_or_none(pnl),
                "pnl_pct": _round_or_none(pnl_pct),
                "weight": None,  # computed below
            })

        # Compute weights
        if total_value > 0:
            for detail in holding_details:
                mv = detail.get("market_value")
                if mv is not None:
                    detail["weight"] = round(mv / total_value * 100.0, 2)

        unrealized_pnl = total_value - total_cost
        unrealized_pnl_pct = (
            (unrealized_pnl / total_cost * 100.0) if total_cost != 0.0 else 0.0
        )

        return {
            "portfolio_id": portfolio.id,
            "portfolio_name": portfolio.name,
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            "holdings": holding_details,
        }

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _fetch_live_prices(
        self, symbols: set[str]
    ) -> dict[str, float | None]:
        """
        Resolve current prices from Redis for a set of symbols.

        Tries per-symbol keys (``price:<SYMBOL>``), then scans category
        caches as a fallback.
        """
        result: dict[str, float | None] = {s: None for s in symbols}

        try:
            r = get_redis()
        except Exception as e:
            logger.warning("Redis unavailable for live prices: %s", e)
            return result

        # Per-symbol keys
        for symbol in symbols:
            try:
                raw = await r.get(f"price:{symbol}")
                if raw:
                    data = json.loads(raw)
                    price = data.get("price") if isinstance(data, dict) else data
                    result[symbol] = _safe_float(price)
            except Exception:
                continue

        # Category-cache fallback for any still-missing symbols
        missing = {s for s in symbols if result.get(s) is None}
        if missing:
            for category in ("crypto", "stocks", "forex", "commodities", "bonds", "indices"):
                if not missing:
                    break
                try:
                    raw = await r.get(f"market:{category}")
                    if not raw:
                        continue
                    data = json.loads(raw)
                    records = data if isinstance(data, list) else data.get("data", [])
                    if not isinstance(records, list):
                        continue
                    for rec in records:
                        sym = rec.get("symbol")
                        if sym and sym in missing:
                            result[sym] = _safe_float(rec.get("price"))
                            missing.discard(sym)
                except Exception:
                    continue

        return result


def _safe_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _round_or_none(val: float | None, digits: int = 2) -> float | None:
    if val is None:
        return None
    return round(val, digits)
