"""Baidu Migration Index (Qianxi) — TODO stub.

Baidu Qianxi exposes daily inter-city migration indices through undocumented
JSONP endpoints on huiyan.baidu.com (cityrank, provincerank, historycurve,
lastdate).  The endpoints are public and do not require an API key, but they
need correct region codes, JSONP wrapper stripping,Referer/UA headers and are
subject to geo-blocking and cookie rotation.  Until a robust, lawful scraper is
implemented this source is kept as a TODO stub.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict = {
    "key": "mobility_baidu_migration",
    "name_zh": "百度迁徙",
    "name_en": "Baidu Migration Index (Qianxi)",
    "url": "http://huiyan.baidu.com/migration/cityrank.jsonp",
    "access_method": "todo",
    "frequency": "daily",
    "sector": "mobility",
    "difficulty": "hard",
    "note": (
        "Undocumented JSONP endpoints on huiyan.baidu.com (cityrank/provincerank/"
        "historycurve/lastdate) expose daily move-in/move-out rankings and "
        "migration-scale indices by region ID. No API key is required, but requests "
        "need correct region codes, JSONP stripping, and geo-blocking/cookie handling. "
        "Marked TODO until a robust scraper/collector is implemented."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return no observations; Baidu Qianxi parser is TODO."""
    logger.warning(
        "[%s] Baidu Qianxi migration collector is TODO: undocumented JSONP endpoints "
        "require region codes, JSONP stripping and header/cookie handling",
        src.get("key", "mobility_baidu_migration"),
    )
    return []
