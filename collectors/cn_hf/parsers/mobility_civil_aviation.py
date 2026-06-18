"""CAAC monthly civil aviation KPI parser.

The Civil Aviation Administration of China (CAAC / 中国民航局) publishes monthly
production indicator statistics (passenger trips, cargo/mail, aircraft
movements) as PDF attachments on a Chinese-language index page:

    https://www.caac.gov.cn/XXGK/XXGK/TJSJ/TJSJ_1/

No stable, public, unauthenticated JSON or CSV endpoint is available.
Extracting a clean time-series requires scraping the index, downloading PDF
attachments, and parsing tables, which is beyond the allowed dependency set
for this batch.  This parser is therefore marked as "todo" and returns an
empty observation list while logging the reason.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict[str, Any] = {
    "key": "mobility_civil_aviation",
    "name_zh": "中国民航月度主要生产指标统计",
    "name_en": "CAAC Monthly Civil Aviation KPIs",
    "url": "https://www.caac.gov.cn/XXGK/XXGK/TJSJ/TJSJ_1/",
    "access_method": "todo",
    "frequency": "monthly",
    "sector": "mobility",
    "difficulty": "hard",
    "note": (
        "CAAC publishes monthly production indicator PDFs (passenger trips, "
        "cargo/mail, aircraft movements) on a Chinese-language index page. No "
        "open JSON/CSV or machine-readable API endpoint was found; extraction "
        "requires scraping the index, downloading PDF attachments, and parsing "
        "tables."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return no observations; this source requires a PDF/table scraper."""
    logger.warning(
        "[%s] TODO: CAAC monthly civil aviation KPIs are only available as "
        "PDF attachments on the CAAC statistics index page; no stable public "
        "JSON/CSV endpoint exists. Returning empty observations.",
        SOURCE["key"],
    )
    return []
