"""Public Politburo meeting readout metadata collector.

Best-effort scraper that extracts Politburo meeting metadata from the
references section of the English Wikipedia article on the 20th Politburo
of the Chinese Communist Party. Wikipedia citations link to official
readouts (e.g. Xinhua, gov.cn, Communist Party Membership Network) and
provide the meeting date and title in a stable, public, neutral format.

Returns one EconomicData-shaped row per identified meeting / collective
study session, with value=1 and metadata containing the original title,
URL and publisher.
"""

import logging
import re
from datetime import datetime, timezone

import pandas as pd
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from core.base_collector import BaseCollector
from core.exceptions import SchemaChangedError

logger = logging.getLogger(__name__)

DEFAULT_URL = (
    "https://en.wikipedia.org/wiki/20th_Politburo_of_the_Chinese_Communist_Party"
)

# Reference must mention the Politburo / Political Bureau in Chinese or English.
_KEYWORDS = (
    "中共中央政治局",
    "political bureau of the cpc central committee",
    "politburo of the cpc central committee",
)

# Regexes used to pull a publication date out of a Wikipedia citation line.
_DATE_PATTERNS = [
    re.compile(r"\((\d{1,2}\s+[A-Za-z]+\s+\d{4})\)"),          # (25 October 2022)
    re.compile(r"\(([A-Za-z]+\s+\d{1,2},?\s+\d{4})\)"),        # (October 25, 2022)
    re.compile(r"\((\d{4}-\d{2}-\d{2})\)"),                    # (2022-10-25)
    re.compile(r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})"),               # 25 October 2022
    re.compile(r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})"),             # October 25, 2022
]


class PolitburoReadoutsCollector(BaseCollector):
    name = "politburo_readouts"
    source_type = "api"  # routed to the EconomicData table by BaseCollector

    def __init__(self, config: dict):
        super().__init__(config)
        self.url = config.get("url", DEFAULT_URL)
        # Wikipedia blocks non-browser user-agents; use a generic browser string.
        self._http.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    async def collect(self) -> list[dict]:
        try:
            resp = await self._http.get(self.url)
            if resp.status_code != 200:
                logger.warning(
                    f"[{self.name}] {self.url} returned HTTP {resp.status_code}"
                )
                return []
            return [{"html": resp.text, "url": self.url}]
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to fetch {self.url}: {e}")
            return []

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        if not raw_data:
            return pd.DataFrame()

        html = raw_data[0].get("html", "")
        source_url = raw_data[0].get("url", self.url)

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            logger.warning(f"[{self.name}] HTML parse failed: {e}")
            return pd.DataFrame()

        rows = []
        references = soup.find("ol", {"class": "references"})
        if not references:
            logger.warning(f"[{self.name}] No references list found at {source_url}")
            return pd.DataFrame()

        for li in references.find_all("li", recursive=False):
            cite = li.find("cite")
            if not cite:
                continue

            text = cite.get_text(" ", strip=True).lower()
            if not any(kw.lower() in text for kw in _KEYWORDS):
                continue

            link = cite.find("a", {"class": "external text"})
            readout_url = link.get("href", "") if link else ""
            title = (link.get_text(strip=True) if link else "").strip('"')

            # Try to grab the English translation in square brackets when present.
            translation = ""
            bracket_match = re.search(r"\[([^\]]+)\]", cite.get_text(" ", strip=True))
            if bracket_match:
                translation = bracket_match.group(1).strip()

            meeting_date = self._extract_date(cite.get_text(" ", strip=True))
            if meeting_date is None:
                logger.debug(
                    f"[{self.name}] Could not extract date for reference: {title!r}"
                )
                continue

            publisher = self._extract_publisher(cite)

            rows.append(
                {
                    "indicator": self.name,
                    "date": meeting_date,
                    "value": 1,
                    "unit": "meeting",
                    "metadata": {
                        "source_url": source_url,
                        "readout_url": readout_url,
                        "title": title or translation,
                        "title_zh": title if any(
                            "\u4e00" <= ch <= "\u9fff" for ch in title
                        ) else "",
                        "translation": translation,
                        "publisher": publisher,
                    },
                }
            )

        if not rows:
            logger.warning(
                f"[{self.name}] No Politburo meeting references parsed from {source_url}"
            )

        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("date").reset_index(drop=True)
        return df

    def _extract_date(self, text: str) -> datetime | None:
        """Return a timezone-aware datetime parsed from a citation line."""
        for pattern in _DATE_PATTERNS:
            match = pattern.search(text)
            if not match:
                continue
            date_str = match.group(1)
            try:
                dt = date_parser.parse(date_str)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
        return None

    def _extract_publisher(self, cite) -> str:
        """Best-effort publisher extraction from a Wikipedia <cite> node."""
        text = cite.get_text(" ", strip=True)
        # Common Wikipedia cite-web pattern: "...(in Language). Publisher. Retrieved ..."
        match = re.search(r"\(in\s+[^)]+\)\.\s*([^\.]+?)\.", text)
        if match:
            return match.group(1).strip()
        # Fallback: last internal wiki link text before access date.
        for a in cite.find_all("a"):
            href = a.get("href", "")
            if href.startswith("/wiki/") and "accessdate" not in href.lower():
                continue
            if not href.startswith("http"):
                continue
            return a.get_text(strip=True)
        return ""

    def validate(self, df: pd.DataFrame) -> bool:
        if df.empty:
            return True
        required = ["indicator", "date", "value", "unit"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SchemaChangedError(self.name, required, list(df.columns))
        return True
