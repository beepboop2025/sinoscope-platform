"""SAFENetErrorsCollector — SAFE net errors & omissions proxy.

Fetches China's balance-of-payments net errors and omissions from the World Bank
WDI open API (indicator BN.KAC.EOMS.CD). This is a public, neutral proxy for
the SAFE balance-of-payments release series.
"""

import logging
from datetime import datetime, timezone

import pandas as pd

from core.base_collector import BaseCollector
from core.exceptions import SchemaChangedError

logger = logging.getLogger(__name__)


class SAFENetErrorsCollector(BaseCollector):
    name = "safe_net_errors"
    source_type = "api"

    # World Bank WDI: Net errors and omissions (BoP, current US$)
    BASE_URL = "https://api.worldbank.org/v2"
    INDICATOR = "BN.KAC.EOMS.CD"
    COUNTRY = "CHN"

    def __init__(self, config: dict):
        super().__init__(config)
        self.indicator = config.get("indicator", self.INDICATOR)
        self.country = config.get("country", self.COUNTRY)
        self.start_year = config.get("start_year", 2015)
        self.end_year = config.get("end_year", 2026)

    async def collect(self) -> list[dict]:
        records = []
        try:
            url = f"{self.BASE_URL}/country/{self.country}/indicator/{self.indicator}"
            resp = await self._http.get(
                url,
                params={
                    "format": "json",
                    "per_page": 100,
                    "date": f"{self.start_year}:{self.end_year}",
                },
            )
            if resp.status_code != 200:
                logger.warning(
                    f"[{self.name}] World Bank returned HTTP {resp.status_code}"
                )
                return records

            data = resp.json()
            if not isinstance(data, list) or len(data) < 2:
                logger.warning(
                    f"[{self.name}] Unexpected World Bank response shape"
                )
                return records

            for item in data[1] or []:
                value = item.get("value")
                if value is None:
                    continue
                records.append({
                    "indicator": self.indicator,
                    "country": self.country,
                    "date": item.get("date", ""),
                    "value": float(value),
                    "indicator_name": item.get("indicator", {}).get("value", ""),
                    "country_name": item.get("country", {}).get("value", ""),
                })
        except Exception as e:
            logger.warning(f"[{self.name}] Collection failed: {e}")

        logger.info(f"[{self.name}] Collected {len(records)} data points")
        return records

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        rows = []
        for r in raw_data:
            date_str = str(r.get("date", "")).strip()
            try:
                if date_str and date_str.isdigit():
                    date = datetime(int(date_str), 1, 1, tzinfo=timezone.utc)
                elif date_str:
                    date = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                else:
                    date = datetime.now(timezone.utc)
            except Exception:
                date = datetime.now(timezone.utc)

            rows.append({
                "indicator": "safe_net_errors",
                "date": date,
                "value": r.get("value"),
                "unit": "USD",
                "metadata": {
                    "country": r.get("country", self.country),
                    "indicator_name": r.get("indicator_name", ""),
                    "country_name": r.get("country_name", ""),
                    "world_bank_indicator": r.get("indicator", self.indicator),
                },
            })
        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        required = ["indicator", "date", "value"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SchemaChangedError(self.name, required, list(df.columns))
        return True
