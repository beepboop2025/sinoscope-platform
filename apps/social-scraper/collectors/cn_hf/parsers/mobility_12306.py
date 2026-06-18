"""12306 railway passenger traffic parser.

12306 (China Railway's ticketing platform) does not expose a public,
unauthenticated API for passenger volume or ticket/booking data.  The official
site is a commercial booking engine and any bulk data requires authenticated
access or scraping behind anti-bot protections.

This module therefore exposes the source metadata as a TODO stub and returns
an empty observation list.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict[str, Any] = {
    "key": "mobility_12306",
    "name_zh": "12306铁路客运量",
    "name_en": "12306 Railway Passenger Traffic",
    "url": "https://www.12306.cn",
    "access_method": "todo",
    "frequency": "daily",
    "sector": "transport_logistics",
    "difficulty": "hard",
    "note": (
        "12306 has no public API. Booking/search data is only available by "
        "scraping the official site or via Ministry of Transport monthly aggregate "
        "railway passenger reports. Marked todo until a stable public endpoint or "
        "scraper is implemented."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return no observations.

    12306 passenger traffic is not available from a public unauthenticated
    endpoint.  Keep the collector stubbed as TODO so the dispatcher can skip it
    gracefully without breaking the fan-out.
    """
    logger.warning(
        "[mobility_12306] TODO: no public API for 12306 railway passenger "
        "traffic; returning empty observations."
    )
    return []
