"""China monthly import/export trade data from China Data Portal (GACC)."""

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict = {
    "key": "macro_customs",
    "name_zh": "中国进出口贸易总额（海关月度）",
    "name_en": "China Monthly Import and Export Trade (GACC)",
    "url": "https://chinadata.live/api/v2/data/china-trade-monthly",
    "access_method": "open_json",
    "frequency": "monthly",
    "sector": "macro",
    "difficulty": "easy",
    "note": (
        "Free no-key JSON API from China Data Portal, sourced from General "
        "Administration of Customs of China (GACC) official monthly releases. "
        "Returns total trade, exports, imports and trade balance in USD millions."
    ),
}

# Metrics published for each month.  The API also returns ytd_* fields; we keep
# the four headline series to stay aligned with the source description.
_METRICS = ("total", "export", "import", "balance")


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Fetch monthly China trade data and return one observation per metric."""
    url = src.get("url", SOURCE["url"])

    try:
        resp = await http.get(url)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        logger.warning(f"[macro_customs] Failed to fetch trade data: {e}")
        return []

    if not isinstance(payload, dict) or not payload.get("success"):
        logger.warning("[macro_customs] API returned unsuccessful payload")
        return []

    series = payload.get("data", {}).get("data")
    if not isinstance(series, list):
        logger.warning("[macro_customs] No data array in API response")
        return []

    observations = []
    for row in series:
        if not isinstance(row, dict):
            continue

        period = row.get("date")
        if not period:
            continue

        try:
            dt = datetime.strptime(str(period), "%Y-%m").replace(tzinfo=timezone.utc)
        except Exception as e:
            logger.warning(f"[macro_customs] Could not parse date '{period}': {e}")
            continue

        for metric in _METRICS:
            raw_value = row.get(metric)
            if raw_value is None:
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                logger.warning(
                    f"[macro_customs] Non-numeric {metric} for {period}: {raw_value}"
                )
                continue

            observations.append({
                "date": dt,
                "value": value,
                "indicator": f"{SOURCE['key']}_{metric}",
                "period": period,
                "unit": "USD Million",
            })

    logger.info(f"[macro_customs] Collected {len(observations)} observations")
    return observations
