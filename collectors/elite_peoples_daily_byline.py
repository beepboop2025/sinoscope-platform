"""People's Daily byline-frequency collector (elite signal).

Attempts to extract a daily article-count / byline-activity proxy from the
public People's Daily Online print-edition archive.  The site markup changes
periodically and may rate-limit foreign requests, so the collector degrades
gracefully to an empty result set and logs a warning rather than raising.

Output EconomicData rows:
    indicator = "peoples_daily_byline"
    value     = number of articles detected on the page
    unit      = "articles"
"""

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from bs4 import BeautifulSoup

from core.base_collector import BaseCollector
from core.exceptions import SchemaChangedError

logger = logging.getLogger(__name__)


class PeoplesDailyCollector(BaseCollector):
    name = "peoples_daily_byline"
    source_type = "api"

    # Public print-edition archive URLs.  The first working pattern wins.
    ARCHIVE_URL_PATTERNS = [
        "http://paper.people.com.cn/rmrb/html/{date}/nbs.D110000renmrb_01.htm",
        "http://paper.people.com.cn/rmrb/html/{date}/node_1.htm",
    ]

    def __init__(self, config: dict):
        super().__init__(config)
        self.lookback_days = int(config.get("lookback_days", 7))
        self.timeout = int(config.get("timeout", 30))

    async def collect(self) -> list[dict]:
        """Fetch recent People's Daily archive pages.

        Returns a list of raw records, one per archive page, each containing
        the HTML, date and resolved URL.  Network or parse failures are
        swallowed and result in an empty list.
        """
        records: list[dict] = []
        today = datetime.now(timezone.utc)

        for day_offset in range(self.lookback_days):
            issue_date = today - timedelta(days=day_offset)
            date_path = issue_date.strftime("%Y-%m/%d")
            iso_date = issue_date.strftime("%Y-%m-%d")

            fetched = False
            for pattern in self.ARCHIVE_URL_PATTERNS:
                url = pattern.format(date=date_path)
                try:
                    resp = await self._http.get(url, timeout=self.timeout)
                    if resp.status_code == 200:
                        records.append({
                            "date": iso_date,
                            "html": resp.text,
                            "url": str(resp.url),
                        })
                        fetched = True
                        break
                    logger.debug(
                        f"[{self.name}] {url} returned HTTP {resp.status_code}"
                    )
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"[{self.name}] Failed to fetch {url}: {e}")

            if not fetched:
                logger.warning(
                    f"[{self.name}] Could not retrieve archive page for {iso_date}"
                )

        if not records:
            logger.warning(
                f"[{self.name}] No archive pages retrieved; returning empty result"
            )
        else:
            logger.info(f"[{self.name}] Collected {len(records)} archive pages")
        return records

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        """Extract a daily article-count proxy from archive HTML.

        The print-edition archive lists article headlines/teasers.  We count
        links that look like article links, falling back to headline/list-item
        counts when no obvious article links are found.
        """
        rows: list[dict] = []
        for page in raw_data:
            html = page.get("html", "")
            if not html:
                continue

            try:
                soup = BeautifulSoup(html, "html.parser")

                article_links = [
                    a for a in soup.find_all("a", href=True)
                    if any(
                        token in a["href"].lower()
                        for token in ("content", "node", "article", "n.")
                    )
                ]
                count = len(article_links)

                if count == 0:
                    # Fallback: count headline and list-item elements.
                    count = len(soup.find_all(["h1", "h2", "h3", "h4", "li"]))

                if count == 0:
                    logger.warning(
                        f"[{self.name}] No content found for {page.get('date')}"
                    )
                    continue

                parsed_date = datetime.strptime(
                    page["date"], "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc)

                rows.append({
                    "indicator": "peoples_daily_byline",
                    "date": parsed_date,
                    "value": float(count),
                    "unit": "articles",
                    "metadata": {"source_url": page.get("url", "")},
                })
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"[{self.name}] Parse error for {page.get('date')}: {e}"
                )

        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        """Ensure the parsed DataFrame contains required EconomicData columns."""
        required = ["indicator", "date", "value"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise SchemaChangedError(self.name, required, list(df.columns))
        return True
