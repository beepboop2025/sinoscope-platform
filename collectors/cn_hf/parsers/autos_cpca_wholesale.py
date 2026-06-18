"""CN-HF parser: CPCA passenger vehicle wholesale sales (autos_cpca_wholesale).

The China Passenger Car Association (CPCA / 乘联会) publishes monthly passenger
vehicle wholesale sales via website articles, PDF reports and its WeChat public
account.  There is no stable, public, unauthenticated JSON or CSV endpoint, and
extracting a clean monthly time-series requires scraping reports or parsing
dynamic pages.  This parser is therefore marked as "todo" and returns an empty
result while logging the reason.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict[str, Any] = {
    "key": "autos_cpca_wholesale",
    "name_zh": "乘联会乘用车批发销量",
    "name_en": "CPCA China Passenger Vehicle Wholesale Sales",
    "url": "https://www.cpcaauto.com/",
    "access_method": "todo",
    "frequency": "monthly",
    "sector": "autos",
    "difficulty": "hard",
    "note": (
        "Monthly passenger-vehicle wholesale sales for China published by the China "
        "Passenger Car Association (CPCA / 乘联会). The association releases the "
        "figures via website articles, PDF reports and its WeChat public account; "
        "there is no stable open JSON or CSV endpoint. Extracting a clean monthly "
        "time-series requires scraping or parsing the published reports."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return no observations; this source requires a scraper or authenticated feed."""
    logger.warning(
        "[%s] CPCA wholesale sales source is a TODO stub: no stable public "
        "JSON/CSV endpoint available (website articles/PDF/WeChat only).",
        SOURCE["key"],
    )
    return []
