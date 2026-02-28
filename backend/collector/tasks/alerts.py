"""Alert evaluation Celery task — runs every 60s to check alerts."""

import json
import logging
from datetime import datetime, timezone

import redis as redis_lib
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from collector.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_dsn() -> str:
    settings = get_settings()
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def _unwrap_envelope(raw: str) -> object:
    """Unwrap the {_updated, _source, data} envelope from save_data."""
    parsed = json.loads(raw)
    if isinstance(parsed, dict) and "data" in parsed:
        return parsed["data"]
    return parsed


def _get_price(r: redis_lib.Redis, symbol: str) -> float | None:
    """Look up current price from Redis cache across categories."""
    # Try crypto_markets first (most common alerts)
    raw = r.get("market:crypto_markets")
    if raw:
        data = _unwrap_envelope(raw)
        if isinstance(data, list):
            for item in data:
                sym = item.get("symbol", "").upper()
                if sym == symbol.upper():
                    return float(item.get("current_price", 0))

    # Try forex
    raw = r.get("market:forex")
    if raw:
        data = _unwrap_envelope(raw)
        if isinstance(data, dict):
            rates_dict = data.get("rates", data)
            if symbol.upper() in rates_dict:
                return float(rates_dict[symbol.upper()])

    # Try stocks
    raw = r.get("market:stocks")
    if raw:
        data = _unwrap_envelope(raw)
        if isinstance(data, list):
            for item in data:
                if item.get("symbol", "").upper() == symbol.upper():
                    return float(item.get("price", 0))

    return None


@celery_app.task(name="collector.tasks.alerts.evaluate_alerts")
def evaluate_alerts_task():
    """Evaluate all active alerts against current market prices."""
    settings = get_settings()
    try:
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        engine = create_engine(_get_sync_dsn())

        with Session(engine) as session:
            from app.models.alert import Alert

            # Get all active, untriggered alerts
            result = session.execute(
                select(Alert).where(Alert.is_active == True, Alert.triggered == False)
            )
            alerts = list(result.scalars().all())

            if not alerts:
                return

            triggered_count = 0
            for alert in alerts:
                price = _get_price(r, alert.symbol)
                if price is None:
                    continue

                triggered = False
                if alert.condition == "price_above" and price > float(alert.threshold):
                    triggered = True
                elif alert.condition == "price_below" and price < float(alert.threshold):
                    triggered = True

                if triggered:
                    alert.triggered = True
                    alert.triggered_at = datetime.now(timezone.utc)
                    triggered_count += 1
                    logger.info(
                        f"[ALERTS] Triggered: {alert.symbol} {alert.condition} "
                        f"{alert.threshold} (price={price})"
                    )

            if triggered_count:
                session.commit()
                logger.info(f"[ALERTS] Triggered {triggered_count} alerts")
            else:
                session.rollback()

        engine.dispose()
    except Exception as e:
        logger.error(f"[ALERTS] Evaluation failed: {e}")
