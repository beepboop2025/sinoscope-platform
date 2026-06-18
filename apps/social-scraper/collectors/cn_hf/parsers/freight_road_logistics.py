"""Parser for the China Road Logistics Price Index.

The index is published weekly by the China Federation of Logistics and Purchasing
(CFLP) and Guangdong Lin'an Logistics Group as HTML press releases on
chinawuliu.com.cn. This collector scrapes the latest weekly report page and
extracts the headline composite index plus vehicle/LTL sub-indices.
"""

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOURCE: dict = {
    "key": "freight_road_logistics",
    "name_zh": "中国公路物流运价指数",
    "name_en": "China Road Logistics Price Index",
    "url": "http://www.chinawuliu.com.cn/xsyj/tjsj/",
    "access_method": "scrape",
    "frequency": "weekly",
    "sector": "transport_logistics",
    "difficulty": "medium",
    "unit": "index",
    "note": (
        "Weekly road-freight price index published by CFLP and Lin'an Logistics. "
        "Scraped from public HTML report pages on chinawuliu.com.cn."
    ),
}

_BASE_URL = "http://www.chinawuliu.com.cn"
_LISTING_URL = f"{_BASE_URL}/xsyj/tjsj/"
_REPORT_TITLE_PATTERN = re.compile(r"中国公路物流运价周指数报告")
_TITLE_DATE_PATTERN = re.compile(r"[（(](\d{4})\.(\d{1,2})\.(\d{1,2})[)）]")
_PUBLISH_DATE_PATTERN = re.compile(r"发布时间[：:]\s*(\d{4}-\d{2}-\d{2})")
_VALUE_PATTERNS = {
    "composite": re.compile(r"中国公路物流运价指数为\s*(\d+(?:\.\d+)?)\s*点"),
    "vehicle": re.compile(r"整车指数为\s*(\d+(?:\.\d+)?)\s*点"),
    "ltl_light": re.compile(r"零担轻货指数为\s*(\d+(?:\.\d+)?)\s*点"),
    "ltl_heavy": re.compile(r"零担重货指数为\s*(\d+(?:\.\d+)?)\s*点"),
}


def _extract_report_url(soup: BeautifulSoup) -> str | None:
    """Find the URL of the latest weekly road-logistics index report."""
    for link in soup.find_all("a", href=True):
        title = link.get("title") or link.get_text(strip=True)
        if _REPORT_TITLE_PATTERN.search(title):
            return urljoin(_BASE_URL, link["href"])
    return None


def _parse_date_from_title(title: str) -> datetime | None:
    """Parse a date like '（2026.6.5)' from the report title."""
    match = _TITLE_DATE_PATTERN.search(title)
    if match:
        year, month, day = match.groups()
        try:
            return datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _parse_publish_date(text: str) -> datetime | None:
    """Parse the publish timestamp printed on the article page."""
    match = _PUBLISH_DATE_PATTERN.search(text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _extract_values(text: str) -> dict[str, float]:
    """Extract the composite and sub-index values from report text."""
    values: dict[str, float] = {}
    for component, pattern in _VALUE_PATTERNS.items():
        match = pattern.search(text)
        if match:
            try:
                values[component] = float(match.group(1))
            except ValueError:
                logger.warning(
                    f"[freight_road_logistics] Could not convert value for {component}"
                )
    return values


async def collect(http, src: dict) -> list[dict]:
    """Return the latest weekly road-logistics index observations.

    Each observation contains at least:
        {"date": <datetime>, "value": <float>, "indicator": "freight_road_logistics"}
    """
    try:
        list_resp = await http.get(_LISTING_URL)
        list_resp.raise_for_status()
        list_soup = BeautifulSoup(list_resp.text, "lxml")

        report_url = _extract_report_url(list_soup)
        if not report_url:
            logger.warning(
                "[freight_road_logistics] No weekly report link found on listing page"
            )
            return []

        report_resp = await http.get(report_url)
        report_resp.raise_for_status()
        report_soup = BeautifulSoup(report_resp.text, "lxml")

        title = report_soup.title.string if report_soup.title else ""
        article = report_soup.find("div", class_="text") or report_soup
        text = article.get_text(" ", strip=True)

        # Determine observation date: prefer explicit date in title, fall back to publish date.
        obs_date = _parse_date_from_title(title) or _parse_publish_date(text)
        if obs_date is None:
            logger.warning(
                "[freight_road_logistics] Could not determine observation date"
            )
            return []

        values = _extract_values(text)
        if "composite" not in values:
            logger.warning(
                "[freight_road_logistics] Composite index value not found in report"
            )
            return []

        observations = []
        component_names = {
            "composite": "composite",
            "vehicle": "vehicle",
            "ltl_light": "ltl_light",
            "ltl_heavy": "ltl_heavy",
        }
        for component, value in values.items():
            observations.append(
                {
                    "date": obs_date,
                    "value": value,
                    "indicator": "freight_road_logistics",
                    "component": component_names.get(component, component),
                }
            )

        logger.info(
            f"[freight_road_logistics] Collected {len(observations)} values for {obs_date.date()}"
        )
        return observations

    except Exception as e:
        logger.warning(f"[freight_road_logistics] Collection failed: {e}")
        return []
