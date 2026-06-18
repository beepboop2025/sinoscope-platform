"""100njz / Mysteel construction steel price parser.

百年建筑网建筑钢材行情数据由上海钢联（Mysteel）建筑钢材频道提供。
The public listing pages currently expose only "电议" (contact-for-price)
quotes and do not publish numeric daily price values without a commercial
Mysteel/100njz API agreement. Therefore this parser is registered as a TODO
stub and returns an empty observation list.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

SOURCE: dict = {
    "key": "steel_100njz_construction",
    "name_zh": "百年建筑网建筑钢材价格",
    "name_en": "100njz Construction Steel Price",
    "url": "https://jiancai.mysteel.com/",
    "access_method": "todo",
    "frequency": "daily",
    "sector": "steel",
    "difficulty": "hard",
    "note": (
        "百年建筑网（100njz.com）建筑钢材行情由上海钢联（Mysteel）建筑钢材频道"
        "（jiancai.mysteel.com）提供，日度更新。公开页面仅展示'电议'报价，"
        "具体日度价格数据需登录或商业数据接口。TODO：接入Mysteel/100njz商业API或"
        "确认可公开访问的价格指数页面。"
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Return an empty observation list.

    Numeric construction steel prices from 100njz/Mysteel are not available on
    the public listing page without a commercial agreement. The public page only
    shows '电议' (contact-for-price) listings, so no observable `value` can be
    extracted.
    """
    logger.warning(
        "[%s] TODO: numeric construction steel prices require a commercial "
        "Mysteel/100njz API or authenticated data feed; public page shows only "
        "contact-for-price listings.",
        src.get("key", SOURCE["key"]),
    )
    return []
