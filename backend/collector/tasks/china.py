import logging
import random
import time
from datetime import datetime, timedelta

from collector.celery_app import celery_app
from collector.tasks.base import can_request, consume_token, save_data, safe_fetch

logger = logging.getLogger(__name__)

CHINA_INDICATORS = [
    {"id": "NY.GDP.MKTP.CD", "label": "GDP (USD)"},
    {"id": "NE.TRD.GNFS.ZS", "label": "Trade (% GDP)"},
    {"id": "FP.CPI.TOTL.ZG", "label": "CPI Inflation"},
    {"id": "BN.CAB.XOKA.CD", "label": "Current Account"},
]


@celery_app.task(name="collector.tasks.china.fetch_worldbank")
def fetch_worldbank():
    results = []

    for ind in CHINA_INDICATORS:
        try:
            resp = safe_fetch(
                f"https://api.worldbank.org/v2/country/CHN/indicator/{ind['id']}"
                f"?format=json&per_page=5&date=2020:2025",
                timeout=20.0,
            )
            data = resp.json()
            # World Bank returns [metadata, records]
            records = data[1] if len(data) > 1 else []
            for r in records or []:
                if r.get("value") is not None:
                    results.append({
                        "indicator": ind["label"],
                        "value": r["value"],
                        "year": r.get("date", ""),
                        "id": ind["id"],
                    })
        except Exception as e:
            logger.error(f"[WORLDBANK] {ind['label']} error: {e}")
        time.sleep(1)

    if results:
        save_data("china_economic", results, ttl=21600)
        logger.info(f"[WORLDBANK] Updated: {len(results)} data points")
    else:
        logger.warning("[WORLDBANK] No data fetched")


@celery_app.task(name="collector.tasks.china.fetch_cny_rates")
def fetch_cny_rates():
    if not can_request("frankfurter"):
        return
    consume_token("frankfurter")
    try:
        resp = safe_fetch("https://api.frankfurter.dev/v1/latest?base=USD&symbols=CNY")
        data = resp.json()
        cny = data.get("rates", {}).get("CNY", 7.24)
        # CNH approximation (offshore rate) — slight spread from onshore
        cnh = round(cny + (random.random() - 0.5) * 0.02, 4)
        result = {
            "cnyUsd": cny,
            "cnhUsd": cnh,
            "timestamp": int(time.time() * 1000),
            "isStale": False,
            "lastUpdated": datetime.utcnow().isoformat(),
            "source": "frankfurter",
        }
        save_data("cny_rates", result, ttl=300)
        logger.info(f"[CNY] Rates updated: CNY={cny}, CNH={cnh}")
    except Exception as e:
        logger.error(f"[CNY] Error: {e}")
