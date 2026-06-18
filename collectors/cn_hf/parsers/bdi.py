"""CN-HF parser: Baltic Dry Index (BDI).

The Baltic Exchange's authoritative time-series is subscription-only, but
Investing.com publishes a public daily historical data table.  This parser
scrapes the most recent rows from that table and returns observations for the
BDI composite index.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SOURCE: dict[str, Any] = {
    "key": "bdi",
    "name_zh": "波罗的海干散货指数",
    "name_en": "Baltic Dry Index (BDI)",
    "url": "https://www.investing.com/indices/baltic-dry-historical-data",
    "access_method": "scrape",
    "frequency": "daily",
    "sector": "transport_logistics",
    "difficulty": "medium",
    "unit": "index",
    "note": (
        "Daily composite dry-bulk freight index published by the Baltic Exchange. "
        "The official feed is subscription-only; this parser scrapes the public "
        "Investing.com historical table as a best-effort open proxy. It is "
        "subject to anti-bot/ToS limits and may return partial history."
    ),
}


async def collect(http: httpx.AsyncClient, src: dict) -> list[dict]:
    """Scrape the latest BDI daily observations from Investing.com.

    Each observation contains at least:
        {"date": <datetime.date>, "value": <float>, "indicator": "bdi"}
    """
    url = src.get("url", SOURCE["url"])
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        resp = await http.get(url, headers=headers)
        if resp.status_code != 200:
            logger.warning(
                "[%s] HTTP %s from %s",
                SOURCE["key"],
                resp.status_code,
                url,
            )
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all(
            "tr", class_=lambda cls: cls and "historical-data-v2_price" in cls
        )
        if not rows:
            logger.warning("[%s] No historical data rows found at %s", SOURCE["key"], url)
            return []

        observations: list[dict] = []
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 2:
                continue

            date_text = cells[0]
            price_text = cells[1]
            if not date_text or not price_text:
                continue

            try:
                obs_date = datetime.strptime(date_text, "%b %d, %Y").date()
                value = float(price_text.replace(",", ""))
            except (ValueError, TypeError) as e:
                logger.warning(
                    "[%s] Could not parse date/value from %s: %s",
                    SOURCE["key"],
                    cells,
                    e,
                )
                continue

            metadata = {"source_url": url, "price_type": "close"}
            if len(cells) >= 3:
                metadata["open"] = _to_float(cells[2])
            if len(cells) >= 4:
                metadata["high"] = _to_float(cells[3])
            if len(cells) >= 5:
                metadata["low"] = _to_float(cells[4])
            if len(cells) >= 7:
                metadata["change_pct"] = _to_float(cells[6].replace("%", ""))

            observations.append(
                {
                    "date": obs_date,
                    "value": value,
                    "indicator": SOURCE["key"],
                    "metadata": metadata,
                }
            )

        logger.info(
            "[%s] Collected %s observations from %s",
            SOURCE["key"],
            len(observations),
            url,
        )
        return observations

    except httpx.HTTPError as e:
        logger.warning("[%s] Network error: %s", SOURCE["key"], e)
    except Exception as e:
        logger.warning("[%s] Unexpected error: %s", SOURCE["key"], e)

    return []


def _to_float(text: str | None) -> float | None:
    """Safely convert a cleaned string to float; return None on failure."""
    if text is None:
        return None
    cleaned = text.replace(",", "").replace("%", "").strip()
    if cleaned == "" or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None
