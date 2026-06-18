"""CN-HF parser: Amap (Gaode) city congestion delay index.

Amap's public traffic-report dashboard exposes a JSON endpoint that returns the
current national average of the road-network trip delay index (路网行程延时指数)
along with related traffic-health indicators.  This parser fetches that public
endpoint and returns the daily observation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_SOURCE_KEY = "mobility_gaode"
_API_URL = "https://report.amap.com/diagnosis/ajax/countryindicators.do"
_PRIMARY_INDICATOR = "路网行程延时指数"

SOURCE: dict[str, Any] = {
    "key": _SOURCE_KEY,
    "name_zh": "高德地图城市拥堵延时指数",
    "name_en": "Amap City Congestion Delay Index",
    "url": _API_URL,
    "access_method": "open_json",
    "frequency": "daily",
    "sector": "mobility",
    "difficulty": "medium",
    "unit": "index",
    "note": (
        "Amap's public traffic-report dashboard exposes an open JSON endpoint "
        "(report.amap.com/diagnosis/ajax/countryindicators.do) returning the "
        "current national average of the road-network trip delay index and related "
        "traffic-health indicators.  No authentication is required."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Fetch Amap's daily national traffic-health indicators.

    Returns at least one observation for the congestion delay index:
        {"date": <datetime.date>, "value": <float>, "indicator": "mobility_gaode"}

    Additional related indicators (e.g. average speed, congestion share) are
    returned as sub-indicator observations when available.
    """
    url = src.get("url", SOURCE["url"])
    try:
        resp = await http.get(url)
        if resp.status_code != 200:
            logger.warning(
                "[%s] HTTP %s from %s",
                _SOURCE_KEY,
                resp.status_code,
                url,
            )
            return []

        payload = resp.json()
        if not isinstance(payload, list):
            logger.warning("[%s] Unexpected payload shape: %s", _SOURCE_KEY, payload)
            return []

        obs_date = datetime.now(timezone.utc).date()
        observations: list[dict] = []

        for record in payload:
            indicator_name = record.get("indicator")
            avg_value = record.get("avg")
            if not indicator_name or avg_value is None:
                continue

            try:
                value = float(avg_value)
            except (ValueError, TypeError):
                logger.warning(
                    "[%s] Could not parse avg value %r for %s",
                    _SOURCE_KEY,
                    avg_value,
                    indicator_name,
                )
                continue

            indicator = (
                _SOURCE_KEY
                if indicator_name == _PRIMARY_INDICATOR
                else f"{_SOURCE_KEY}_{_slug(indicator_name)}"
            )

            observations.append(
                {
                    "date": obs_date,
                    "value": value,
                    "indicator": indicator,
                    "metadata": {
                        "name_zh": indicator_name,
                        "top_city": record.get("topCityName"),
                        "max_value": record.get("maxValue"),
                        "cities_above_avg": record.get("numGTAvg"),
                    },
                }
            )

        return observations

    except httpx.HTTPError as e:
        logger.warning("[%s] Network error: %s", _SOURCE_KEY, e)
    except Exception as e:
        logger.warning("[%s] Parse error: %s", _SOURCE_KEY, e)

    return []


def _slug(name: str) -> str:
    """Create an ASCII-only sub-indicator slug from a Chinese indicator name."""
    name = name.strip().lower()
    replacements = {
        "(": "_",
        ")": "",
        "（": "_",
        "）": "",
        "/": "_",
        " ": "_",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    # Drop units/symbols that don't add signal to the slug.
    name = name.replace("%", "pct").replace("·", "_")
    # Pinyin-ish romanisation is not reliable, so transliterate common terms.
    name = (
        name.replace("路网", "road_network_")
        .replace("高延时", "high_delay_")
        .replace("拥堵", "congestion_")
        .replace("延时", "delay_")
        .replace("指数", "index")
        .replace("运行", "run_")
        .replace("时间", "time_")
        .replace("占比", "share")
        .replace("路段", "link_")
        .replace("里程", "mileage_")
        .replace("比", "ratio")
        .replace("常发", "frequent_")
        .replace("行程", "trip_")
        .replace("道路", "road_")
        .replace("偏差率", "deviation_rate")
        .replace("平均", "avg_")
        .replace("速度", "speed_")
        .replace("高", "high_")
    )
    name = name.strip("_")
    # Remove any remaining non-ascii/non-alphanumeric characters.
    name = "".join(ch if ch.isascii() and (ch.isalnum() or ch == "_") else "_" for ch in name)
    return name.strip("_") or "unknown"
