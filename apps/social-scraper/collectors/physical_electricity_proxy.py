"""Electricity proxy collector for China.

Fetches annual electricity-generation data for China from the public
Our World in Data / Ember energy dataset.  The series is a stable,
credentials-free proxy for total electricity output in terawatt-hours.

Output EconomicData rows:
    indicator = "electricity_proxy_china"
    value     = annual electricity generation (TWh)
    unit      = "TWh"
"""

import io
import logging
from datetime import datetime, timezone

import pandas as pd

from core.base_collector import BaseCollector
from core.exceptions import SchemaChangedError

logger = logging.getLogger(__name__)

# Public OWID/Ember energy dataset (CSV).
OWID_ENERGY_CSV = "https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv"


class ElectricityProxyCollector(BaseCollector):
    """Collector for a public China electricity-generation proxy."""

    name = "electricity_proxy"
    source_type = "api"

    INDICATOR = "electricity_proxy_china"
    UNIT = "TWh"
    COUNTRY = "China"
    VALUE_COLUMN = "electricity_generation"

    async def collect(self) -> list[dict]:
        """Fetch the OWID energy CSV and return it as a raw record."""
        try:
            resp = await self._http.get(OWID_ENERGY_CSV)
            if resp.status_code != 200:
                logger.warning(
                    f"[{self.name}] OWID returned HTTP {resp.status_code}"
                )
                return []
            return [{"csv_text": resp.text}]
        except Exception as e:
            logger.warning(f"[{self.name}] Collection failed: {e}")
            return []

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        """Transform the OWID CSV into EconomicData-shaped rows for China."""
        if not raw_data:
            return pd.DataFrame(columns=[
                "indicator", "date", "value", "unit", "metadata"
            ])

        csv_text = raw_data[0].get("csv_text", "")
        if not csv_text:
            return pd.DataFrame(columns=[
                "indicator", "date", "value", "unit", "metadata"
            ])

        try:
            df = pd.read_csv(io.StringIO(csv_text))
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to parse CSV: {e}")
            return pd.DataFrame(columns=[
                "indicator", "date", "value", "unit", "metadata"
            ])

        if "country" not in df.columns or self.VALUE_COLUMN not in df.columns:
            logger.warning(
                f"[{self.name}] Required columns missing from OWID dataset"
            )
            return pd.DataFrame(columns=[
                "indicator", "date", "value", "unit", "metadata"
            ])

        china = df[df["country"] == self.COUNTRY].copy()
        china = china.dropna(subset=[self.VALUE_COLUMN, "year"])
        if china.empty:
            logger.warning(
                f"[{self.name}] No {self.COUNTRY} data found in OWID dataset"
            )
            return pd.DataFrame(columns=[
                "indicator", "date", "value", "unit", "metadata"
            ])

        rows = []
        for _, row in china.iterrows():
            try:
                year = int(row["year"])
                value = float(row[self.VALUE_COLUMN])
                date = datetime(year, 12, 31, tzinfo=timezone.utc)
                rows.append({
                    "indicator": self.INDICATOR,
                    "date": date,
                    "value": value,
                    "unit": self.UNIT,
                    "metadata": {
                        "country": self.COUNTRY,
                        "year": year,
                        "source_dataset": "owid-energy-data",
                        "source_url": OWID_ENERGY_CSV,
                    },
                })
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"[{self.name}] Skipping invalid row for year "
                    f"{row.get('year')}: {e}"
                )

        if not rows:
            logger.warning(f"[{self.name}] No parseable rows for {self.COUNTRY}")
            return pd.DataFrame(columns=[
                "indicator", "date", "value", "unit", "metadata"
            ])

        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate that parsed rows contain the required EconomicData columns."""
        if df.empty:
            return True

        required = ["indicator", "date", "value"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SchemaChangedError(self.name, required, list(df.columns))
        return True
