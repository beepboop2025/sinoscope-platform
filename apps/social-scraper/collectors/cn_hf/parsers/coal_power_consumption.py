"""CN-HF parser stub: thermal coal consumption (coal_power_consumption).

Daily coal burn / thermal power coal consumption for China is not available
through a stable, public, unauthenticated JSON or CSV endpoint.  CCTD and
provincial-grid operators publish figures as HTML tables and PDF reports that
require scraping or manual extraction.  This parser is therefore marked as
"todo" and returns an empty result while logging the reason.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict[str, Any] = {
    "key": "coal_power_consumption",
    "name_zh": "火电煤炭消费量",
    "name_en": "Thermal coal consumption",
    "url": "https://www.cctd.com.cn/",
    "access_method": "todo",
    "frequency": "daily",
    "sector": "coal",
    "difficulty": "hard",
    "note": (
        "No documented public API for daily coal burn at Chinese power plants; "
        "CCTD and provincial grid data are published as HTML tables/PDFs that "
        "require scraping or manual extraction."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return no observations; this source requires a scraper or authenticated feed."""
    logger.warning(
        "[%s] Coal power consumption source is a TODO stub: no stable public "
        "JSON/CSV endpoint available (CCTD HTML/PDF only).",
        SOURCE["key"],
    )
    return []
