"""UN Comtrade mirror collector for China merchandise trade.

Fetches two complementary views from the UN Comtrade API:

1. **Reported by China** — `reporterCode=156`, `partnerCode=0` (world),
   flows `M` (imports) and `X` (exports).
2. **Mirror view** — major partner countries reporting trade with China
   (`partnerCode=156`). Flow directions are inverted so they are comparable
   to China-reported flows:
   * partner `M`  → stored as `X` (China export mirror)
   * partner `X`  → stored as `M` (China import mirror)

Each record is written to the `economic_data` table with:
* `source`: `comtrade_mirror`
* `indicator`: `trade_{flow}_{hs}` for the China-reported view and
  `trade_{flow}_{hs}_mirror` for the mirror view. The suffix keeps the two
  views distinct under the unique ``(source, indicator, date)`` index.
* `value`: `primaryValue` in USD
* `metadata`: `{"hs", "flow", "reporter", "partner", "period", "netWeight",
  "view", "original_flow"?}`

The collector is config-driven but supplies sensible defaults so it can be
registered from `sources.yaml` with minimal boilerplate.
"""

import asyncio
import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from core.base_collector import BaseCollector
from core.exceptions import RateLimitError, SchemaChangedError, SourceDownError

logger = logging.getLogger(__name__)

# Two-digit HS chapters most relevant for China cyclical/export sectors.
_DEFAULT_HS_CHAPTERS = [
    "84",  # machinery / electrical machinery nuclei
    "85",  # electrical machinery
    "62",  # apparel (non-knit)
    "61",  # apparel (knit)
    "73",  # articles of iron/steel
    "72",  # iron/steel
    "39",  # plastics
    "90",  # optical / medical instruments
    "29",  # organic chemicals
    "27",  # mineral fuels
]

# Major trading partners used to build the mirror view (UN M49 reporter codes).
_DEFAULT_PARTNER_REPORTERS = [
    842,  # United States
    392,  # Japan
    276,  # Germany
    410,  # Rep. of Korea
    704,  # Viet Nam
    528,  # Netherlands
    826,  # United Kingdom
    356,  # India
    36,   # Australia
    643,  # Russian Federation
]


class ComtradeMirrorCollector(BaseCollector):
    name = "comtrade_mirror"
    source_type = "api"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = config.get(
            "base_url", "https://comtradeapi.un.org/data/v1/get"
        ).rstrip("/")
        self.api_key = config.get("api_key") or os.getenv("COMTRADE_API_KEY") or None
        self.hs_chapters = [
            str(hs).strip()[:2]
            for hs in config.get("hs_chapters", _DEFAULT_HS_CHAPTERS)
        ]
        self.partner_reporters = [
            int(p) for p in config.get("partner_reporters", _DEFAULT_PARTNER_REPORTERS)
        ]
        self.recent_months = int(config.get("recent_months", 12))
        self.type_code = config.get("type_code", "C")
        self.freq_code = config.get("freq_code", "M")
        self.classification = config.get("classification", "HS")
        self.include_desc = bool(config.get("include_desc", True))
        self.inter_request_delay = float(config.get("inter_request_delay", 1.0))
        self._last_request_at = 0.0

    # ── Public lifecycle ─────────────────────────────────────────────

    async def collect(self) -> list[dict]:
        """Fetch raw Comtrade records for both China-reported and mirror views."""
        headers = {}
        if self.api_key:
            headers["Ocp-Apim-Subscription-Key"] = self.api_key

        periods = self._periods(self.recent_months)
        cmd_code = ",".join(self.hs_chapters)

        logger.info(
            f"[{self.name}] Collecting Comtrade data: periods={periods}, "
            f"hs_chapters={self.hs_chapters}, partners={len(self.partner_reporters)}"
        )

        records: list[dict] = []
        rate_limited = False
        rate_limit_retry = 60

        # 1) Reported by China
        for period in periods:
            if rate_limited:
                break
            for flow in ("M", "X"):
                try:
                    url = self._endpoint(period, reporter=156)
                    params = self._params(flow=flow, partner=0, cmd_code=cmd_code)
                    batch = await self._fetch(url, params, headers)
                    records.extend(batch)
                except RateLimitError as e:
                    rate_limited = True
                    rate_limit_retry = int(e.retry_after or 60)
                    logger.warning(
                        f"[{self.name}] Rate limited on China-reported view; "
                        f"keeping {len(records)} records collected so far"
                    )
                    break

        # 2) Mirror view (partner reporters)
        for partner in self.partner_reporters:
            if rate_limited:
                break
            for period in periods:
                if rate_limited:
                    break
                for flow in ("M", "X"):
                    try:
                        url = self._endpoint(period, reporter=partner)
                        params = self._params(flow=flow, partner=156, cmd_code=cmd_code)
                        batch = await self._fetch(url, params, headers)
                        # Tag mirror records so parse() can invert the flow.
                        for rec in batch:
                            rec["_mirror_reporter"] = partner
                            rec["_original_flow"] = flow
                        records.extend(batch)
                    except RateLimitError as e:
                        rate_limited = True
                        rate_limit_retry = int(e.retry_after or 60)
                        logger.warning(
                            f"[{self.name}] Rate limited on mirror view; "
                            f"keeping {len(records)} records collected so far"
                        )
                        break

        logger.info(
            f"[{self.name}] Collected {len(records)} raw records "
            f"(rate_limited={rate_limited})"
        )

        if not records and rate_limited:
            logger.warning(
                f"[{self.name}] Rate limited and no records collected; "
                f"returning empty to allow graceful degradation"
            )
        if not records:
            logger.warning(
                f"[{self.name}] No records collected from Comtrade; "
                f"degrading gracefully"
            )
        return records

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        """Transform raw Comtrade records into standardized EconomicData rows.

        Sub-commodity rows (e.g. HS6 codes returned for an HS2 chapter query) are
        aggregated to the (indicator, date) level so they do not violate the
        unique ``(source, indicator, date)`` index on ``economic_data``. Mirror
        rows are written under ``trade_{flow}_{hs}_mirror`` so the China-reported
        and mirror views can coexist for the same flow and HS chapter.
        """
        buckets: dict[tuple[str, datetime], dict] = {}
        for rec in raw_data:
            try:
                parsed = self._parse_record(rec)
                if not parsed:
                    continue
                key = (parsed["indicator"], parsed["date"])
                bucket = buckets.get(key)
                if bucket is None:
                    bucket = {
                        "indicator": parsed["indicator"],
                        "date": parsed["date"],
                        "value": 0.0,
                        "unit": parsed["unit"],
                        "metadata": dict(parsed["metadata"]),
                    }
                    bucket["metadata"]["netWeight"] = 0.0
                    buckets[key] = bucket
                bucket["value"] += parsed["value"]
                new_nw = parsed["metadata"].get("netWeight") or 0.0
                bucket["metadata"]["netWeight"] += new_nw
            except Exception as e:
                logger.warning(f"[{self.name}] Skipping malformed record: {e}")

        rows = []
        for bucket in buckets.values():
            if not bucket["metadata"].get("netWeight"):
                bucket["metadata"]["netWeight"] = None
            rows.append(bucket)
        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        if df.empty:
            return True
        required = ["indicator", "date", "value"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SchemaChangedError(self.name, required, list(df.columns))
        return True

    # ── Internal helpers ─────────────────────────────────────────────

    def _endpoint(self, period: str, reporter: int) -> str:
        return (
            f"{self.base_url}/{self.type_code}/{self.freq_code}/"
            f"{self.classification}/{period}/{reporter}"
        )

    def _params(self, *, flow: str, partner: int, cmd_code: str) -> dict[str, Any]:
        params = {
            "flowCode": flow,
            "partnerCode": str(partner),
            "cmdCode": cmd_code,
        }
        if self.include_desc:
            params["includeDesc"] = "True"
        return params

    async def _fetch(
        self, url: str, params: dict, headers: dict
    ) -> list[dict]:
        """Execute one throttled GET and return the dataset list."""
        await self._throttle()
        try:
            resp = await self._http.get(url, params=params, headers=headers)
        except Exception as e:
            logger.warning(f"[{self.name}] Request error for {url}: {e}")
            return []

        if resp.status_code == 429:
            retry_after = 60
            try:
                retry_after = int(resp.headers.get("Retry-After", 60))
            except (ValueError, TypeError):
                pass
            raise RateLimitError(self.name, retry_after=retry_after)

        if resp.status_code != 200:
            logger.warning(
                f"[{self.name}] HTTP {resp.status_code} for {resp.url}"
            )
            return []

        try:
            payload = resp.json()
        except Exception as e:
            logger.warning(f"[{self.name}] Non-JSON response from {resp.url}: {e}")
            return []

        dataset = self._extract_dataset(payload)
        if dataset:
            logger.debug(f"[{self.name}] {len(dataset)} records from {resp.url}")
        return dataset

    async def _throttle(self):
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.inter_request_delay:
            await asyncio.sleep(self.inter_request_delay - elapsed)
        self._last_request_at = time.monotonic()

    def _extract_dataset(self, payload: Any) -> list[dict]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("dataset", "data", "items"):
                val = payload.get(key)
                if isinstance(val, list):
                    return val
        return []

    def _parse_record(self, rec: dict) -> dict | None:
        flow = self._field(rec, "flowCode") or self._field(rec, "flow")
        if not flow:
            return None

        is_mirror = bool(
            rec.get("_mirror_reporter")
            or str(self._field(rec, "partnerCode")) == "156"
        )
        original_flow = flow
        if is_mirror:
            # Invert flow so partner imports from China become China exports.
            flow = "X" if flow == "M" else "M"

        period = self._field(rec, "period")
        if not period or len(str(period)) != 6:
            return None

        hs_raw = self._field(rec, "cmdCode") or self._field(rec, "cmd")
        if not hs_raw:
            return None
        hs_chapter = str(hs_raw).strip()[:2]

        value_raw = self._field(rec, "primaryValue")
        if value_raw is None:
            return None
        try:
            value = float(value_raw)
        except (ValueError, TypeError):
            return None
        if not math.isfinite(value):
            return None

        net_weight_raw = self._field(rec, "netWgt") or self._field(rec, "netWeight")
        net_weight = None
        if net_weight_raw is not None:
            try:
                net_weight = float(net_weight_raw)
                if not math.isfinite(net_weight):
                    net_weight = None
            except (ValueError, TypeError):
                net_weight = None

        reporter = self._field(rec, "reporterCode")
        partner = self._field(rec, "partnerCode")

        # Mirror rows are aggregated across partner reporters, so reporter is
        # normalised to 0 (world aggregate) while partner=156 keeps the mirror
        # identity needed by the conditions processor.
        metadata = {
            "hs": hs_chapter,
            "flow": flow,
            "reporter": 0 if is_mirror else reporter,
            "partner": partner,
            "period": str(period),
            "netWeight": net_weight,
            "view": "mirror" if is_mirror else "reported",
        }
        if is_mirror:
            metadata["original_flow"] = original_flow

        base_indicator = f"trade_{flow}_{hs_chapter}"
        indicator = f"{base_indicator}_mirror" if is_mirror else base_indicator

        return {
            "indicator": indicator,
            "date": self._period_to_date(period),
            "value": value,
            "unit": "USD",
            "metadata": metadata,
        }

    @staticmethod
    def _field(rec: dict, key: str) -> Any:
        if key in rec:
            return rec[key]
        # Some APIs return PascalCase or lower-cased aliases.
        alt = key[0].lower() + key[1:] if key else key
        if alt != key and alt in rec:
            return rec[alt]
        return None

    @staticmethod
    def _period_to_date(period) -> datetime:
        s = str(period)
        year = int(s[:4])
        month = int(s[4:6])
        return datetime(year, month, 1, tzinfo=timezone.utc)

    @staticmethod
    def _periods(n: int) -> list[str]:
        """Return the last `n` months as YYYYMM strings (most recent first)."""
        now = datetime.now(timezone.utc)
        year, month = now.year, now.month
        periods = []
        for _ in range(n):
            periods.append(f"{year}{month:02d}")
            month -= 1
            if month == 0:
                month = 12
                year -= 1
        return periods
