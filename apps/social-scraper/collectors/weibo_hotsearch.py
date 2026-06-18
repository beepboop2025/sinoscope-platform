"""Weibo (微博) hot-search collector.

Pulls the real-time hot-search ranking (热搜榜) — the top trending topics on
Chinese social media — and keeps only the financially-relevant entries so they
flow into the sentiment pipeline (XLM-RoBERTa handles the Chinese text).

The public endpoint returns JSON without login:
    https://weibo.com/ajax/side/hotSearch

Design notes:
- source_type = "social_media" so _upsert routes rows to the Article table
  (NOT EconomicData), which is what the sentiment processor reads.
- The FULL hot-search list is fetched into immutable raw storage; the financial
  filter is applied in parse() so raw data stays complete for audit/backfill.
- Add/adjust nothing in code to tune cadence — edit sources.yaml.
"""

import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import quote

import pandas as pd

from core.base_collector import BaseCollector
from core.exceptions import SchemaChangedError, SourceDownError

logger = logging.getLogger(__name__)

HOT_SEARCH_URL = "https://weibo.com/ajax/side/hotSearch"
SEARCH_URL_TMPL = "https://s.weibo.com/weibo?q=%23{q}%23"  # #topic# search page


class WeiboHotSearchCollector(BaseCollector):
    name = "weibo_hotsearch"
    source_type = "social_media"  # → Article table → sentiment pipeline

    def __init__(self, config: dict):
        super().__init__(config)
        # Finance keywords + denylist drive _is_financially_relevant. We prefer the
        # shared lexicon (config/zh_finance_lexicon.json) so the collector and the
        # sentiment processor stay in sync; sources.yaml can override/extend.
        from processors.zh_finance import load_lexicon
        lexicon = load_lexicon()
        self.finance_keywords = config.get(
            "finance_keywords", lexicon.get("finance_keywords", [])
        )
        self.denylist = config.get("denylist", lexicon.get("denylist", []))

    async def collect(self) -> list[dict]:
        """Fetch the full real-time hot-search list."""
        # Weibo's ajax endpoint rejects the default scraper UA; send a browser one.
        resp = await self._http.get(
            HOT_SEARCH_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Referer": "https://weibo.com/",
            },
        )
        if resp.status_code != 200:
            raise SourceDownError(self.name, f"HTTP {resp.status_code}")

        payload = resp.json()
        if payload.get("ok") != 1:
            raise SourceDownError(self.name, f"API ok={payload.get('ok')}")

        realtime = payload.get("data", {}).get("realtime", [])
        logger.info(f"[Weibo] Fetched {len(realtime)} hot-search entries")
        return realtime

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        """Keep only finance-relevant topics; shape them into Article rows."""
        rows = []
        for item in raw_data:
            word = (item.get("word") or "").strip()
            if not word:
                continue

            # The "note" is a short blurb; fall back to the topic word itself.
            note = (item.get("note") or word).strip()

            if not self._is_financially_relevant(word, note):
                continue

            url = SEARCH_URL_TMPL.format(q=quote(word))
            rows.append({
                "title": word,
                "full_text": note,
                "url": url,
                "url_hash": hashlib.sha256(url.encode()).hexdigest()[:32],
                "author": "weibo_hotsearch",
                "published_at": self._onboard_time(item),
                "category": "china_social",
                # heat metric kept for ranking/velocity downstream
                "metadata": {
                    "raw_hot": item.get("raw_hot"),
                    "rank": item.get("rank"),
                    "label": item.get("label_name"),
                    "weibo_category": item.get("category"),
                },
            })

        logger.info(f"[Weibo] {len(rows)}/{len(raw_data)} entries kept as finance-relevant")
        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        # Empty is valid: a window with no finance topics is normal, not a failure.
        if df.empty:
            return True
        if "title" not in df.columns or "url" not in df.columns:
            raise SchemaChangedError(self.name, "missing title/url columns")
        return True

    @staticmethod
    def _onboard_time(item: dict) -> datetime:
        """Weibo gives onboard_time as a unix epoch (seconds); default to now."""
        ts = item.get("onboard_time")
        if isinstance(ts, (int, float)) and ts > 0:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        return datetime.now(timezone.utc)

    # ── Domain logic ──────────────────────────────────────────────
    def _is_financially_relevant(self, word: str, note: str) -> bool:
        """Keep a hot-search topic only if it's about markets/economy/finance.

        Substring matching (NOT \\b regex — that doesn't anchor on Chinese).
        Denylist wins: it excludes false positives that embed a finance word,
        e.g. 经济适用男 ("budget boyfriend" slang) contains 经济 ("economy").
        """
        haystack = f"{word} {note}"
        if any(bad in haystack for bad in self.denylist):
            return False
        return any(kw in haystack for kw in self.finance_keywords)
