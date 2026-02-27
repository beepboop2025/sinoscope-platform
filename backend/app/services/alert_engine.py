"""
Alert evaluation engine.

Evaluates active user alerts against current prices cached in Redis.
Supports conditions: price_above, price_below, pct_change_above, pct_change_below.

Usage:
    from app.services.alert_engine import AlertEngine

    engine = AlertEngine()
    triggered = await engine.evaluate_alerts(db_session)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.redis import get_redis

logger = logging.getLogger(__name__)


class AlertEngine:
    """Evaluates active alerts against live market prices."""

    async def evaluate_alerts(self, db_session: AsyncSession) -> list[dict[str, Any]]:
        """
        Evaluate all active, non-triggered alerts.

        For each alert, looks up the symbol's current price in Redis,
        checks the condition, and if triggered: marks it in the DB and
        adds it to the result list.

        Args:
            db_session: An active async DB session (caller manages commit).

        Returns:
            List of dicts describing each triggered alert, e.g.::

                {
                    "alert_id": "...",
                    "user_id": "...",
                    "symbol": "BTC",
                    "condition": "price_above",
                    "threshold": 70000.0,
                    "current_price": 71234.56,
                    "triggered_at": "2025-06-01T12:00:00+00:00",
                }
        """
        # Fetch active, untriggered alerts
        result = await db_session.execute(
            select(Alert).where(
                Alert.is_active.is_(True),
                Alert.triggered.is_(False),
            )
        )
        alerts = list(result.scalars().all())

        if not alerts:
            return []

        # Build a set of unique symbols we need prices for
        symbols = {a.symbol for a in alerts}
        prices = await self._fetch_prices(symbols)

        triggered_list: list[dict[str, Any]] = []
        triggered_ids: list[str] = []
        now = datetime.now(timezone.utc)

        for alert in alerts:
            price_info = prices.get(alert.symbol)
            if price_info is None:
                continue

            current_price = price_info.get("price")
            change_pct = price_info.get("change_pct")

            if current_price is None:
                continue

            fired = self._check_condition(
                condition=alert.condition,
                threshold=alert.threshold,
                current_price=current_price,
                change_pct=change_pct,
            )

            if fired:
                triggered_ids.append(alert.id)
                triggered_list.append({
                    "alert_id": alert.id,
                    "user_id": alert.user_id,
                    "symbol": alert.symbol,
                    "condition": alert.condition,
                    "threshold": alert.threshold,
                    "current_price": current_price,
                    "triggered_at": now.isoformat(),
                })

        # Bulk-update triggered alerts
        if triggered_ids:
            await db_session.execute(
                update(Alert)
                .where(Alert.id.in_(triggered_ids))
                .values(triggered=True, triggered_at=now)
            )
            logger.info("Triggered %d alerts: %s", len(triggered_ids), triggered_ids)

        return triggered_list

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _fetch_prices(
        self, symbols: set[str]
    ) -> dict[str, dict[str, float | None]]:
        """
        Look up current prices from Redis.

        Tries per-symbol keys first (``price:<SYMBOL>``), then falls back
        to scanning category caches (``market:crypto``, ``market:stocks``, etc.).

        Returns:
            Mapping of symbol -> {"price": float, "change_pct": float | None}.
        """
        result: dict[str, dict[str, float | None]] = {}

        try:
            r = get_redis()
        except Exception as e:
            logger.warning("Cannot access Redis for price lookup: %s", e)
            return result

        # Strategy 1: per-symbol keys
        for symbol in symbols:
            try:
                raw = await r.get(f"price:{symbol}")
                if raw:
                    data = json.loads(raw)
                    result[symbol] = {
                        "price": _safe_float(data.get("price")),
                        "change_pct": _safe_float(data.get("change_pct")),
                    }
            except Exception:
                continue

        # Strategy 2: scan category caches for remaining symbols
        missing = symbols - set(result.keys())
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
                            result[sym] = {
                                "price": _safe_float(rec.get("price")),
                                "change_pct": _safe_float(rec.get("change_pct")),
                            }
                            missing.discard(sym)
                except Exception:
                    continue

        return result

    @staticmethod
    def _check_condition(
        condition: str,
        threshold: float,
        current_price: float,
        change_pct: float | None,
    ) -> bool:
        """Evaluate a single alert condition."""
        if condition == "price_above":
            return current_price > threshold
        if condition == "price_below":
            return current_price < threshold
        if condition == "pct_change_above" and change_pct is not None:
            return change_pct > threshold
        if condition == "pct_change_below" and change_pct is not None:
            return change_pct < threshold
        return False


def _safe_float(val: Any) -> float | None:
    """Convert to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
