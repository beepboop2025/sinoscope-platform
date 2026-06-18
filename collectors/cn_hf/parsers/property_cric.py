"""CRIC (克尔瑞) China real-estate data parser.

CRIC is a commercial/proprietary provider; no stable public open API exists for
its sales-volume, inventory, price, land-auction or developer-ranking series.
This module is therefore a TODO stub per the Batch A public-data-only rule.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict = {
    "key": "property_cric",
    "name_zh": "克尔瑞房地产数据",
    "name_en": "CRIC China Real Estate Data",
    "url": "https://www.cricbigdata.com/",
    "access_method": "todo",
    "frequency": "monthly",
    "sector": "property",
    "difficulty": "hard",
    "note": (
        "Commercial/proprietary real-estate data from CRIC (克尔瑞). "
        "No public open API; indicators are behind a subscription/paywall. "
        "Stubbed until a lawful public endpoint or scraper is available."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return no observations; CRIC data is not available via a public endpoint."""
    logger.warning(
        "[%s] CRIC data is proprietary/paywalled; no public collection implemented. "
        "Set access_method='todo'.",
        src.get("key", "property_cric"),
    )
    return []
