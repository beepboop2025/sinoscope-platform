"""Chinese high-frequency economic indicators collector.

Fetches public Chinese / China-relevant high-frequency indicators as configured
in ``enabled_sources``.  Sources marked ``access="todo"`` are logged and
skipped; open JSON/CSV sources are fetched and parsed.  Failures are caught,
logged, and the collector continues.

The collector can be driven three ways:

1. ``config.enabled_sources`` as a list of full source dicts.
2. ``config.enabled_sources`` as a list of keys, filtering ``config/cn_hf_sources.json``.
3. No config → the full ``config/cn_hf_sources.json`` catalog is used, falling
   back to a small built-in set of open World Bank China proxies.
"""

import io
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from core.base_collector import BaseCollector


# ── Per-source bespoke parsers ───────────────────────────────────────
# Some open sources return idiosyncratic JSON the generic json_path/date/value
# mapping can't reach. Each parser takes the decoded response and returns a flat
# list of {"date": str, "value": number, **extra} observations.

def _parse_sse_freight(data: Any) -> list:
    """Shanghai Shipping Exchange CCFI/SCFI composite index.

    Emits the current AND prior-week points so the index has a period-over-period
    delta to compute momentum from.
    """
    d = (data or {}).get("data", {}) or {}
    cur, last = d.get("currentDate"), d.get("lastDate")
    lines = d.get("lineDataList", []) or []

    def emit(item, label):
        out = [{"date": cur, "value": item.get("currentContent"), "line": label}]
        if last and item.get("lastContent") is not None:
            out.append({"date": last, "value": item.get("lastContent"), "line": label})
        return out

    for item in lines:
        dit = (item.get("dataItemTypeName") or "")
        en = ((item.get("properties") or {}).get("lineName_EN") or "").strip().upper()
        if dit.endswith("_T") or en == "COMPOSITE INDEX":
            return emit(item, "COMPOSITE")
    if lines:  # fallback: first line
        return emit(lines[0], lines[0].get("dataItemTypeName") or "LINE")
    return []


def _parse_chinadata_series(data: Any, value_key: str = "export") -> list:
    """chinadata.live series: data.data is a list of monthly trade rows."""
    rows = ((data or {}).get("data", {}) or {}).get("data", []) or []
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append({
            "date": r.get("date"),
            "value": r.get(value_key),
            **{k: r.get(k) for k in ("total", "export", "import", "balance") if k in r},
        })
    return out


_CUSTOM_PARSERS = {
    "ccfi": _parse_sse_freight,
    "scfi": _parse_sse_freight,
    "macro_customs": _parse_chinadata_series,
}
from core.exceptions import SchemaChangedError

logger = logging.getLogger(__name__)

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "config" / "cn_hf_sources.json"

# Minimal built-in fallback used when the external catalog is absent.
# World Bank endpoints are open, stable, and require no API key.
_DEFAULT_SOURCES: list[dict] = [
    {
        "key": "wb_chn_gdp",
        "name_zh": "世界银行中国GDP",
        "name_en": "World Bank China GDP",
        "url": "https://api.worldbank.org/v2/country/CHN/indicator/NY.GDP.MKTP.CD?format=json&per_page=20",
        "method": "GET",
        "parser": "json",
        "json_path": "1",
        "date_field": "date",
        "value_field": "value",
        "unit": "USD",
        "sector": "macro",
        "access": "open_json",
        "frequency": "annual",
        "difficulty": "easy",
        "note": "Open World Bank API; annual GDP in current USD.",
    },
    {
        "key": "wb_chn_cpi",
        "name_zh": "世界银行中国CPI通胀",
        "name_en": "World Bank China CPI Inflation",
        "url": "https://api.worldbank.org/v2/country/CHN/indicator/FP.CPI.TOTL.ZG?format=json&per_page=20",
        "method": "GET",
        "parser": "json",
        "json_path": "1",
        "date_field": "date",
        "value_field": "value",
        "unit": "%",
        "sector": "macro",
        "access": "open_json",
        "frequency": "annual",
        "difficulty": "easy",
        "note": "Open World Bank API; annual CPI inflation.",
    },
    {
        "key": "wb_chn_exports",
        "name_zh": "世界银行中国货物服务出口",
        "name_en": "World Bank China Exports of Goods and Services",
        "url": "https://api.worldbank.org/v2/country/CHN/indicator/NE.EXP.GNFS.CD?format=json&per_page=20",
        "method": "GET",
        "parser": "json",
        "json_path": "1",
        "date_field": "date",
        "value_field": "value",
        "unit": "USD",
        "sector": "manufacturing",
        "access": "open_json",
        "frequency": "annual",
        "difficulty": "easy",
        "note": "Open World Bank API; annual exports in current USD.",
    },
    # High-frequency Chinese domestic sources — mostly scrape/paid, stubbed as TODO.
    {
        "key": "bdi",
        "name_zh": "波罗的海干散货指数",
        "name_en": "Baltic Dry Index",
        "url": "https://www.balticexchange.com",
        "method": "GET",
        "parser": "json",
        "unit": "points",
        "sector": "transport_logistics",
        "access": "todo",
        "frequency": "daily",
        "difficulty": "medium",
        "note": "Daily bulk freight index. Real-time public feed requires subscription or scrape.",
    },
    {
        "key": "ccfi",
        "name_zh": "中国出口集装箱运价指数",
        "name_en": "China Containerized Freight Index",
        "url": "http://www.sse.net.cn",
        "method": "GET",
        "parser": "json",
        "unit": "points",
        "sector": "transport_logistics",
        "access": "todo",
        "frequency": "weekly",
        "difficulty": "medium",
        "note": "Published by Shanghai Shipping Exchange; no stable open API — scrape required.",
    },
    {
        "key": "scfi",
        "name_zh": "上海出口集装箱运价指数",
        "name_en": "Shanghai Containerized Freight Index",
        "url": "http://www.sse.net.cn",
        "method": "GET",
        "parser": "json",
        "unit": "points",
        "sector": "transport_logistics",
        "access": "todo",
        "frequency": "weekly",
        "difficulty": "medium",
        "note": "Published by Shanghai Shipping Exchange; no stable open API — scrape required.",
    },
    {
        "key": "yiwu_index",
        "name_zh": "义乌中国小商品指数",
        "name_en": "Yiwu China Commodity Index",
        "url": "http://www.ywindex.com",
        "method": "GET",
        "parser": "json",
        "unit": "points",
        "sector": "retail_consumer",
        "access": "todo",
        "frequency": "weekly",
        "difficulty": "medium",
        "note": "Yiwu small-commodity price index; no stable open API — scrape required.",
    },
    {
        "key": "cpca_retail_pv",
        "name_zh": "乘联会乘用车零售销量",
        "name_en": "CPCA Passenger Vehicle Retail Sales",
        "url": "http://www.cpcaauto.com",
        "method": "GET",
        "parser": "json",
        "unit": "units",
        "sector": "retail_consumer",
        "access": "todo",
        "frequency": "weekly",
        "difficulty": "hard",
        "note": "CPCA weekly/monthly PV retail; published as HTML/Excel — scrape required.",
    },
    {
        "key": "cpca_wholesale_pv",
        "name_zh": "乘联会乘用车批发销量",
        "name_en": "CPCA Passenger Vehicle Wholesale Sales",
        "url": "http://www.cpcaauto.com",
        "method": "GET",
        "parser": "json",
        "unit": "units",
        "sector": "retail_consumer",
        "access": "todo",
        "frequency": "weekly",
        "difficulty": "hard",
        "note": "CPCA weekly/monthly PV wholesale; published as HTML/Excel — scrape required.",
    },
]


class CNIndicatorsCollector(BaseCollector):
    """Collector for Chinese high-frequency economic indicators."""

    name = "cn_indicators"
    source_type = "api"

    def __init__(self, config: dict):
        super().__init__(config)
        self.enabled_sources = self._load_sources()

    # ── Configuration loading ───────────────────────────────────────

    def _load_sources(self) -> list[dict]:
        """Resolve enabled_sources from config and/or catalog."""
        raw_sources = self.config.get("enabled_sources", ...)

        if raw_sources is not ...:
            # Explicit config: list of full dicts, list of keys, or empty list.
            if isinstance(raw_sources, list):
                if raw_sources and isinstance(raw_sources[0], dict):
                    return [self._normalize_source(s) for s in raw_sources]
                if raw_sources and isinstance(raw_sources[0], str):
                    catalog = self._load_catalog()
                    key_set = set(raw_sources)
                    return [self._normalize_source(s) for s in catalog if s.get("key") in key_set]
                return []
            return []

        # No explicit config: load whole catalog, then built-in defaults.
        catalog = self._load_catalog()
        if catalog:
            return [self._normalize_source(s) for s in catalog]
        return [self._normalize_source(s) for s in _DEFAULT_SOURCES]

    @staticmethod
    def _load_catalog() -> list[dict]:
        try:
            if _CATALOG_PATH.exists():
                data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data.get("sources", []) or data.get("enabled_sources", []) or []
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.warning(f"[CNIndicators] Failed to load catalog {_CATALOG_PATH}: {e}")
        return []

    @staticmethod
    def _normalize_source(src: dict) -> dict:
        """Make catalog items compatible with collector config fields."""
        normalized = dict(src)
        # cn_hf_sources.json uses access_method; collector internals use access.
        if "access" not in normalized and "access_method" in normalized:
            normalized["access"] = normalized["access_method"]
        # Default parser/method if missing.
        normalized.setdefault("method", "GET")
        normalized.setdefault("parser", "json")
        normalized.setdefault("date_field", "date")
        normalized.setdefault("value_field", "value")
        normalized.setdefault("unit", "")
        normalized.setdefault("sector", "macro")
        normalized.setdefault("frequency", "unknown")
        normalized.setdefault("name_zh", normalized.get("key", ""))
        normalized.setdefault("name_en", normalized.get("key", ""))
        return normalized

    # ── Collection ──────────────────────────────────────────────────

    async def collect(self) -> list[dict]:
        """Fetch configured sources and return normalized raw records."""
        records: list[dict] = []

        for src in self.enabled_sources:
            key = src["key"]
            access = src.get("access", "todo")

            if access == "todo":
                logger.info(
                    f"[CNIndicators] TODO: {key} — "
                    f"{src.get('note', 'scrape/paid source not yet implemented')}"
                )
                continue

            url = src.get("url")
            if not url:
                logger.warning(f"[CNIndicators] {key}: no URL configured")
                continue

            try:
                items = await self._fetch_source(src)
            except Exception as e:
                logger.warning(f"[CNIndicators] {key}: fetch/parse failed: {e}")
                continue

            if not isinstance(items, list):
                logger.warning(
                    f"[CNIndicators] {key}: expected list of observations, got {type(items).__name__}"
                )
                continue

            count = 0
            date_field = src.get("date_field", "date")
            value_field = src.get("value_field", "value")

            for item in items:
                if not isinstance(item, dict):
                    continue

                date = self._normalize_date(item.get(date_field))
                value = self._normalize_value(item.get(value_field))
                if date is None or value is None:
                    continue

                records.append({
                    "key": key,
                    "date": date,
                    "value": value,
                    "unit": src.get("unit", ""),
                    "sector": src.get("sector", "macro"),
                    "frequency": src.get("frequency", "unknown"),
                    "source_name_zh": src.get("name_zh", key),
                    "source_name_en": src.get("name_en", key),
                    "url": url,
                    "access": access,
                    "metadata_extra": {
                        k: v for k, v in item.items()
                        if k not in (date_field, value_field)
                    },
                })
                count += 1

            logger.info(f"[CNIndicators] {key}: collected {count} records")

        logger.info(f"[CNIndicators] Total records collected: {len(records)}")
        return records

    async def _fetch_source(self, src: dict) -> Any:
        """Fetch one source and return the list of observations."""
        url = src["url"]
        method = src.get("method", "GET").upper()

        if method == "POST":
            resp = await self._http.post(url)
        else:
            resp = await self._http.get(url)

        logger.info(f"[CNIndicators] {src['key']}: HTTP {resp.status_code} from {url}")

        if resp.status_code != 200:
            logger.warning(
                f"[CNIndicators] {src['key']}: non-200 status {resp.status_code}"
            )
            return []

        parser = src.get("parser", "json")
        if parser == "csv":
            df = pd.read_csv(io.StringIO(resp.text))
            return df.to_dict("records")

        data = resp.json()
        custom = _CUSTOM_PARSERS.get(src.get("key"))
        if custom:
            return custom(data)
        return self._get_nested(data, src.get("json_path"))

    # ── Parsing helpers ─────────────────────────────────────────────

    @staticmethod
    def _get_nested(data: Any, path: Optional[str]) -> Any:
        """Navigate a dotted path (supports dict keys and list indices)."""
        if not path:
            return data
        current = data
        for part in path.split("."):
            if current is None:
                return None
            if part.isdigit():
                idx = int(part)
                if isinstance(current, list) and 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            elif isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current

    @staticmethod
    def _normalize_date(value: Any) -> Optional[datetime]:
        """Convert a raw date value to a timezone-aware UTC datetime."""
        if value is None:
            return None

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

        # Numeric year (e.g. World Bank annual observations).
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                return datetime(int(value), 1, 1, tzinfo=timezone.utc)
            except (ValueError, OverflowError):
                return None

        s = str(value).strip()
        if not s:
            return None

        # ISO / pandas timestamp.
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            pass

        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y", "%Y/%m/%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        return None

    @staticmethod
    def _normalize_value(value: Any) -> Optional[float]:
        """Convert a raw value to float, returning None for missing/invalid."""
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            v = float(value)
            return v if math.isfinite(v) else None

        s = str(value).strip().replace(",", "")
        if s.lower() in ("", ".", "-", "nd", "na", "n/a", "null", "none"):
            return None

        try:
            v = float(s)
            return v if math.isfinite(v) else None
        except ValueError:
            return None

    # ── Parse / Validate ────────────────────────────────────────────

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        """Transform raw records into the EconomicData schema."""
        rows = []
        for r in raw_data:
            rows.append({
                "indicator": r["key"],
                "date": r["date"],
                "value": r["value"],
                "unit": r["unit"],
                "metadata": {
                    "category": r["sector"],
                    "frequency": r["frequency"],
                    "source_name_zh": r["source_name_zh"],
                    "source_name_en": r["source_name_en"],
                    "url": r["url"],
                    "access": r["access"],
                    "sector": r["sector"],
                    "raw": r.get("metadata_extra", {}),
                },
            })
        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate that parsed rows contain the required columns."""
        required = ["indicator", "date", "value"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SchemaChangedError(self.name, required, list(df.columns))
        return True
