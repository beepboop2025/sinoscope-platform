import logging
import time

from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, save_data, safe_fetch
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

INDICATORS = {
    "GASOLINE": "GASREGW",
    "OIL_WTI": "DCOILWTICO",
    "OIL_BRENT": "DCOILBRENTEU",
    "NATGAS": "DHHNGSP",
    "COPPER": "PCOPPUSDM",
}


@celery_app.task(name="collector.tasks.commodities.fetch_commodities")
def fetch_commodities():
    fred_key = settings.FRED_API_KEY
    if not fred_key:
        return

    results = {}
    for name, series_id in INDICATORS.items():
        if not can_request("fred"):
            break
        consume_token("fred")
        try:
            resp = safe_fetch(
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={series_id}&api_key={fred_key}&file_type=json&sort_order=desc&limit=30"
            )
            data = resp.json()
            obs = [
                {"date": o["date"], "value": float(o["value"])}
                for o in data.get("observations", [])
                if o.get("value") != "."
            ]
            if obs:
                results[name] = {
                    "price": obs[0]["value"],
                    "date": obs[0]["date"],
                    "history": obs[:10],
                }
        except Exception as e:
            logger.error(f"[COMMODITIES] {name} error: {e}")
        time.sleep(0.2)

    if results:
        save_data("commodities", results, ttl=600)
        logger.info(f"[COMMODITIES] Updated {len(results)} commodities")
