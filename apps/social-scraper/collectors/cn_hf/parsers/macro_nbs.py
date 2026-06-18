"""NBS China macroeconomic data parser (TODO stub).

The National Bureau of Statistics of China (NBS / 国家统计局) publishes monthly
macroeconomic releases (CPI, PPI, industrial production, retail sales,
fixed-asset investment, surveyed urban unemployment, etc.) through the
National Data (EasyQuery) portal at data.stats.gov.cn.

The EasyQuery endpoints can be queried programmatically, but they:
  * return JSONP/HTML that must be unwrapped and parsed,
  * require constructing undocumented ``wd`` / ``dfwds`` dimension parameters,
  * use hierarchical indicator codes that change over time,
  * are protected by anti-bot measures and have no documented open API key.

Because there is no stable, public, credential-free endpoint, this parser is
kept as a TODO stub.  A future implementation could either reverse-engineer
the EasyQuery JSONP protocol or scrape the English/Chinese monthly bulletin
pages on stats.gov.cn and extract the headline tables.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict = {
    "key": "macro_nbs",
    "name_zh": "国家统计局宏观数据",
    "name_en": "NBS China Macroeconomic Data",
    "url": "https://data.stats.gov.cn/easyquery.htm?cn=A01",
    "access_method": "todo",
    "frequency": "monthly",
    "sector": "macro",
    "difficulty": "hard",
    "note": (
        "Monthly macroeconomic releases from the National Bureau of Statistics of China. "
        "The EasyQuery portal can be queried via parameterized endpoints, but responses are "
        "JSONP/HTML, require undocumented wd/dfwds parameters, and are protected by anti-bot "
        "measures with no documented open API key. Marked todo until a stable scraper or API "
        "client is implemented."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """TODO: fetch NBS macroeconomic observations.

    Currently returns an empty list because data.stats.gov.cn has no stable
    public, credential-free endpoint.  All errors are handled gracefully.
    """
    logger.warning(
        "[macro_nbs] TODO: NBS EasyQuery parser not yet implemented; "
        "source requires undocumented JSONP parameters and is protected by anti-bot measures."
    )
    return []
