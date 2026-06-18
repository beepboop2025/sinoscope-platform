"""Mobility & Box Office parser.

Maoyan (猫眼) publishes a real-time box-office dashboard at
https://piaofang.maoyan.com/dashboard.  The underlying JSON endpoint
``/dashboard-ajax/movie`` is public but protects numeric values with a
custom icon font, requires dynamic signatures/timestamps, cookie rotation
and Referer headers, and changes its obfuscation periodically.  Public,
unauthenticated, stable daily box-office or mobility-proxy time-series are
therefore not currently available.

This module keeps the source metadata and exposes a no-op collector so the
dispatcher can skip it gracefully.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict[str, Any] = {
    "key": "mobility_box_office",
    "name_zh": "出行与电影票房",
    "name_en": "Mobility & Box Office",
    "url": "https://piaofang.maoyan.com/dashboard",
    "access_method": "todo",
    "frequency": "daily",
    "sector": "mobility",
    "difficulty": "hard",
    "note": (
        "Composite high-frequency proxy for Chinese consumer mobility and "
        "discretionary services. Maoyan dashboard loads real-time box-office via "
        "https://piaofang.maoyan.com/dashboard-ajax/movie (JSON) but requires "
        "dynamic signatures, timestamp, cookie rotation and Referer headers. "
        "Mobility proxies (Baidu Qianxi migration index, Amap city congestion "
        "index) are also scrape-only and periodically change obfuscation. "
        "Marked todo until a stable, lawful access path is implemented."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return no observations; this source is TODO.

    Maoyan's dashboard requires anti-bot/font-decoding handling that is not
    reliably achievable with the allowed public-data-only dependency set.
    """
    logger.warning(
        "[%s] TODO: Maoyan box-office / mobility dashboard is protected by "
        "dynamic signatures and custom icon-font obfuscation; returning empty "
        "observations.",
        src.get("key", SOURCE["key"]),
    )
    return []
