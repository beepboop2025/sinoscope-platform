"""PBOC credit, money supply and aggregate financing parser.

The People’s Bank of China publishes monthly monetary statistics, sources/uses
of credit funds, and aggregate financing data on its official portal.  As of the
Batch A survey there is no stable open JSON or CSV endpoint; the configured URL
and known alternative paths return 404 / are blocked from this environment.
This module is therefore registered as ``access_method="todo"`` and degrades
gracefully while preserving the source metadata for a future scraper.
"""

import logging

logger = logging.getLogger(__name__)


SOURCE: dict = {
    "key": "macro_pboc_credit",
    "name_zh": "人民银行信贷收支与货币供应",
    "name_en": "PBOC Credit, Money Supply and Aggregate Financing",
    "url": "http://www.pbc.gov.cn/en/3688240/index.html",
    "access_method": "todo",
    "frequency": "monthly",
    "sector": "macro",
    "difficulty": "hard",
    "note": (
        "Monthly money supply, sources/uses of credit funds and aggregate "
        "financing data from the People’s Bank of China. No stable open JSON or "
        "CSV endpoint is currently available; figures are published as HTML/Excel "
        "tables that require scraping and Chinese date parsing. Marked todo until "
        "a reliable public access path is confirmed."
    ),
}


async def collect(http, src: dict) -> list[dict]:
    """No-op collector for the PBOC credit source.

    Returns an empty list until a stable public endpoint or scrape target is
    identified.  All failures are handled internally.
    """
    logger.warning(
        "[macro_pboc_credit] TODO: PBOC credit parser not yet implemented — "
        "no stable public JSON/CSV endpoint available (src=%s)",
        src.get("key", "macro_pboc_credit"),
    )
    return []
