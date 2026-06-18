"""SCFI — Shanghai Containerized Freight Index.

Source: Shanghai Shipping Exchange public current-index endpoint.
https://en.sse.net.cn/currentIndex?indexName=scfi

Returns the latest weekly composite index and any route sub-indices that
have a non-null current value.
"""

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict[str, Any] = {
    "key": "scfi",
    "name_zh": "上海出口集装箱运价指数",
    "name_en": "Shanghai Containerized Freight Index (SCFI)",
    "url": "https://en.sse.net.cn/currentIndex?indexName=scfi",
    "access_method": "open_json",
    "frequency": "weekly",
    "sector": "transport_logistics",
    "difficulty": "easy",
    "note": (
        "Published weekly (Fridays) by the Shanghai Shipping Exchange. "
        "The public /currentIndex endpoint returns the latest SCFI composite index "
        "and per-route sub-indices as JSON without authentication."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Fetch the latest SCFI release and return observation rows."""
    url = src.get("url", SOURCE["url"])
    observations: list[dict] = []

    try:
        resp = await http.get(url)
        if resp.status_code != 200:
            logger.warning(
                f"[scfi] Unexpected status {resp.status_code} from {url}"
            )
            return []

        payload = resp.json()
    except Exception as e:  # pragma: no cover - network/parse failure path
        logger.warning(f"[scfi] Failed to fetch or parse JSON: {e}")
        return []

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        logger.warning("[scfi] Response missing 'data' object")
        return []

    current_date_raw = data.get("currentDate")
    last_date_raw = data.get("lastDate")
    line_data = data.get("lineDataList")
    if not isinstance(line_data, list):
        logger.warning("[scfi] Response missing 'lineDataList'")
        return []

    try:
        current_date = datetime.fromisoformat(str(current_date_raw)).date().isoformat()
    except Exception:
        current_date = str(current_date_raw) if current_date_raw is not None else None

    for item in line_data:
        if not isinstance(item, dict):
            continue

        value = item.get("currentContent")
        if value is None:
            continue

        try:
            value = float(value)
        except (TypeError, ValueError):
            logger.warning(f"[scfi] Non-numeric value skipped: {value}")
            continue

        props = item.get("properties") or {}
        observations.append(
            {
                "date": current_date,
                "value": value,
                "indicator": SOURCE["key"],
                "metadata": {
                    "line_name_zh": props.get("lineName_ZH", ""),
                    "line_name_en": props.get("lineName_EN", ""),
                    "data_item_type": item.get("dataItemTypeName", ""),
                    "unit_zh": props.get("unit_ZH", ""),
                    "unit_en": props.get("unit_EN", ""),
                    "weighting_zh": props.get("weighting_ZH", ""),
                    "weighting_en": props.get("weighting_EN", ""),
                    "last_date": last_date_raw,
                    "last_value": item.get("lastContent"),
                    "absolute_change": item.get("absolute"),
                    "percentage_change": item.get("percentage"),
                },
            }
        )

    logger.info(f"[scfi] Collected {len(observations)} observations for {current_date}")
    return observations
