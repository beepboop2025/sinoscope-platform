import logging
import time

from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, save_data, safe_fetch
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SERIES = {
    "GDP": "GDP",
    "CPI": "CPIAUCSL",
    "UNEMPLOYMENT": "UNRATE",
    "FED_RATE": "FEDFUNDS",
    "RETAIL_SALES": "RSXFS",
    "HOUSING_STARTS": "HOUST",
    "M2": "M2SL",
    "TRADE_BALANCE": "BOPGSTB",
}


@celery_app.task(name="collector.tasks.economic.fetch_economic")
def fetch_economic():
    fred_key = settings.FRED_API_KEY
    if not fred_key:
        return

    results = {}
    for name, series_id in SERIES.items():
        if not can_request("fred"):
            break
        consume_token("fred")
        try:
            resp = safe_fetch(
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={series_id}&api_key={fred_key}&file_type=json&sort_order=desc&limit=24"
            )
            data = resp.json()
            obs = [
                {"date": o["date"], "value": float(o["value"])}
                for o in data.get("observations", [])
                if o.get("value") != "."
            ]
            results[name] = obs
        except Exception as e:
            logger.error(f"[ECON] {name} error: {e}")
        time.sleep(0.2)

    if results:
        save_data("economic", results, ttl=300)
        logger.info(f"[ECON] Updated {len(results)} indicators")
