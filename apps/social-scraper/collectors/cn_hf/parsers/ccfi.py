"""CN-HF parser: China Containerized Freight Index (CCFI).

The Shanghai Shipping Exchange publishes the latest weekly CCFI composite index
and route sub-indices as a public JSON endpoint.  This parser fetches the
current release and returns the composite index value(s).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict[str, Any] = {
    "key": "ccfi",
    "name_zh": "中国出口集装箱运价指数",
    "name_en": "China Containerized Freight Index (CCFI)",
    "url": "https://en.sse.net.cn/currentIndex?indexName=ccfi",
    "access_method": "open_json",
    "frequency": "weekly",
    "sector": "transport_logistics",
    "difficulty": "easy",
    "unit": "index",
    "note": (
        "Published weekly (Fridays) by the Shanghai Shipping Exchange. "
        "The public /currentIndex endpoint returns the latest CCFI composite index "
        "and per-route sub-indices as JSON without authentication."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Fetch the latest CCFI release and return composite observations.

    Each observation contains at least:
        {"date": <datetime.date>, "value": <float>, "indicator": "ccfi"}
    """
    url = src.get("url", SOURCE["url"])
    try:
        resp = await http.get(url)
        if resp.status_code != 200:
            logger.warning(
                "[%s] HTTP %s from %s",
                SOURCE["key"],
                resp.status_code,
                url,
            )
            return []

        payload = resp.json()
        data = payload.get("data", {}) or {}
        current_date_str = data.get("currentDate")
        last_date_str = data.get("lastDate")
        line_data = data.get("lineDataList", [])

        if not current_date_str or not line_data:
            logger.warning("[%s] Unexpected payload shape: %s", SOURCE["key"], payload)
            return []

        composite = next(
            (
                item
                for item in line_data
                if item.get("dataItemTypeName") == "CCFI_T"
                or (item.get("properties") or {}).get("lineName_EN") == "COMPOSITE INDEX"
            ),
            None,
        )
        if composite is None:
            logger.warning("[%s] Composite index not found in payload", SOURCE["key"])
            return []

        observations = []
        for date_str, value_key in (
            (current_date_str, "currentContent"),
            (last_date_str, "lastContent"),
        ):
            if not date_str:
                continue
            try:
                value = float(composite[value_key])
                obs_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError, KeyError) as e:
                logger.warning("[%s] Could not parse %s/%s: %s", SOURCE["key"], date_str, value_key, e)
                continue

            observations.append(
                {
                    "date": obs_date,
                    "value": value,
                    "indicator": SOURCE["key"],
                    "metadata": {
                        "name_en": "COMPOSITE INDEX",
                        "name_zh": "中国出口集装箱运价综合指数",
                        "release": "current" if value_key == "currentContent" else "previous",
                    },
                }
            )

        return observations

    except httpx.HTTPError as e:
        logger.warning("[%s] Network error: %s", SOURCE["key"], e)
    except Exception as e:
        logger.warning("[%s] Parse error: %s", SOURCE["key"], e)

    return []
