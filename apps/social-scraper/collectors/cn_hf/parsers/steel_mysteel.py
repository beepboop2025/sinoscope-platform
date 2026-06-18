"""CN-HF parser stub: Mysteel China steel prices (steel_mysteel).

Mysteel (我的钢铁网) publishes daily spot steel and raw-materials prices for
China, but the full historical time-series and stable machine-readable feeds
are behind a subscription wall and anti-bot protection.  The public news pages
show the latest prices, yet there is no reliable, unauthenticated JSON or CSV
endpoint.  This parser is therefore marked as "todo" and returns an empty
result while logging the reason.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict[str, Any] = {
    "key": "steel_mysteel",
    "name_zh": "我的钢铁网钢材价格",
    "name_en": "Mysteel China Steel Prices",
    "url": "https://news.mysteel.com/",
    "access_method": "todo",
    "frequency": "daily",
    "sector": "steel",
    "difficulty": "hard",
    "note": (
        "Daily spot steel and raw-materials prices for China published by Mysteel. "
        "No stable open JSON/API endpoint is available; the full time-series is "
        "behind a subscription/anti-bot wall. TODO: implement a scraper or "
        "commercial API integration."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return no observations; this source requires a scraper or authenticated feed."""
    logger.warning(
        "[%s] Mysteel steel price source is a TODO stub: no stable public "
        "JSON/CSV endpoint available (subscription/anti-bot required).",
        SOURCE["key"],
    )
    return []
