import logging
import time
from datetime import datetime, timedelta

from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, save_data, safe_fetch

logger = logging.getLogger(__name__)


@celery_app.task(name="collector.tasks.forex.fetch_forex")
def fetch_forex():
    if not can_request("frankfurter"):
        return
    consume_token("frankfurter")
    try:
        resp = safe_fetch("https://api.frankfurter.dev/v1/latest?base=USD")
        data = resp.json()
        save_data("forex", {
            "base": data["base"],
            "date": data["date"],
            "rates": data["rates"],
            "timestamp": int(time.time() * 1000),
        })
        logger.info("[FOREX] Rates updated")
    except Exception as e:
        logger.error(f"[FOREX] Error: {e}")


@celery_app.task(name="collector.tasks.forex.fetch_forex_timeseries")
def fetch_forex_timeseries():
    if not can_request("frankfurter"):
        return
    consume_token("frankfurter")
    try:
        to_date = datetime.utcnow().strftime("%Y-%m-%d")
        from_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
        resp = safe_fetch(
            f"https://api.frankfurter.dev/v1/{from_date}..{to_date}?base=USD&symbols=CNY,EUR,GBP,JPY,INR"
        )
        data = resp.json()
        save_data("forex_timeseries", data, ttl=21600)
        logger.info("[FOREX] Timeseries updated")
    except Exception as e:
        logger.error(f"[FOREX] Timeseries error: {e}")
