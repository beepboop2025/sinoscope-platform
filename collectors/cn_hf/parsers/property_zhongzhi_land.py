"""CREIS / Zhongzhi (中指云) China land auction and transaction data.

The public portal at cih-index.com only shows limited preview listings; full
parcel details, historical time-series and ranked city aggregates are gated
behind login/subscription or the commercial API at https://api.cih-index.com/.
No stable public JSON/CSV endpoint exists, so this parser is implemented as a
TODO stub that returns an empty observation list.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict = {
    "key": "property_zhongzhi_land",
    "name_zh": "中指云土地招拍挂数据",
    "name_en": "CREIS / Zhongzhi China Land Auction and Transaction Data",
    "url": "https://www.cih-index.com/landlist/land/",
    "access_method": "todo",
    "frequency": "daily",
    "sector": "property",
    "difficulty": "hard",
    "note": (
        "Daily land auction, supply-plan and transaction listings published by "
        "China Index Academy (CREIS / 中指云 / 中指研究院). The public portal shows "
        "search/filter pages and limited preview records, but full parcel details, "
        "historical time-series and ranked city aggregates are gated behind "
        "login/subscription or delivered through the commercial API at "
        "https://api.cih-index.com/. No stable open JSON/CSV endpoint is available, "
        "so this source is a TODO stub."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return an empty list; data is behind a commercial/paywalled API."""
    logger.warning(
        "[property_zhongzhi_land] TODO: CREIS/Zhongzhi land data requires "
        "authenticated commercial API or subscription; public preview pages do "
        "not expose a stable machine-readable time-series. Skipping collection."
    )
    return []
