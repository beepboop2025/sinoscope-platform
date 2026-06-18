"""Baidu Maps city congestion index (百度地图城市拥堵指数).

The authoritative, real-time congestion curve is served by Baidu Maps
internal/proprietary endpoints (jiaotong.baidu.com) and the Baidu Maps
LBS API, which require a platform API key (ak) and are governed by Baidu
platform terms. Public, unauthenticated bulk JSON/CSV endpoints are not
available, and the public report pages are heavily dynamic/anti-bot.

This module is therefore registered as ``todo`` and degrades gracefully.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict = {
    "key": "mobility_baidu_congestion",
    "name_zh": "百度地图城市拥堵指数",
    "name_en": "Baidu Maps City Congestion Index",
    "url": "https://jiaotong.baidu.com/reports/",
    "access_method": "todo",
    "frequency": "daily",
    "sector": "mobility",
    "difficulty": "hard",
    "note": (
        "Baidu Maps publishes city congestion rankings and reports on "
        "jiaotong.baidu.com, but no open bulk JSON/CSV endpoint exists. "
        "Real-time road traffic requires a Baidu Maps API key (ak) and is "
        "restricted by platform terms; implementation needs a scraper or "
        "authenticated API integration."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return empty list; Baidu congestion data is not available publicly.

    A production implementation could call the Baidu Maps LBS Traffic Status
    API (https://lbsyun.baidu.com/index.php?title=webapi/traffic) with a
    valid ``ak`` and parse the returned congestion index curve, or scrape the
    dynamic report pages on jiaotong.baidu.com.
    """
    logger.warning(
        "[mobility_baidu_congestion] TODO: Baidu Maps congestion data requires "
        "an authenticated API key or a dynamic-page scraper; returning empty."
    )
    return []
