"""Hong Kong private residential property price index collector.

Source: Hong Kong Rating and Valuation Department (RVD)
        "Private Domestic - Price Indices by Class (Territory-wide)"
        https://www.rvd.gov.hk/en/publications/property_market_statistics.html

The headline "All Classes" index is published monthly with base 1999=100.
Public XLS download; no authentication required.
"""

import io
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import pandas as pd

from core.base_collector import BaseCollector

logger = logging.getLogger(__name__)

RVD_PROPERTY_PRICE_XLS = (
    "https://www.rvd.gov.hk/doc/en/statistics/his_data_4.xls"
)

# Column layout in the "Monthly" sheet of his_data_4.xls
# (pandas reads merged cells into alternating columns)
MONTHLY_COLUMNS = {
    8: ("hk_property_price_index_class_a", "Class A (<40 m²)"),
    11: ("hk_property_price_index_class_b", "Class B (40-69.9 m²)"),
    14: ("hk_property_price_index_class_c", "Class C (70-99.9 m²)"),
    17: ("hk_property_price_index_class_d", "Class D (100-159.9 m²)"),
    20: ("hk_property_price_index_class_e", "Class E (≥160 m²)"),
    23: ("hk_property_price_index_under_100m2", "A, B & C (<100 m²)"),
    26: ("hk_property_price_index_100m2_plus", "D & E (≥100 m²)"),
    29: ("hk_property_price_index", "All Classes"),
}

UNIT = "index (1999=100)"


class HKPropertyCollector(BaseCollector):
    """Collect Hong Kong RVD private domestic price indices."""

    name = "hk_property"
    source_type = "api"

    async def collect(self) -> list[dict]:
        """Fetch the RVD monthly price-index XLS and return raw observations."""
        try:
            resp = await self._http.get(RVD_PROPERTY_PRICE_XLS)
            if resp.status_code != 200:
                logger.warning(
                    f"[{self.name}] RVD returned HTTP {resp.status_code}"
                )
                return []

            return self._parse_xls(resp.content)
        except httpx.HTTPError as e:
            logger.warning(f"[{self.name}] Network error: {e}")
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to collect data: {e}")
        return []

    def _parse_xls(self, content: bytes) -> list[dict]:
        """Parse the monthly sheet from the downloaded XLS bytes."""
        try:
            xls = pd.ExcelFile(io.BytesIO(content))
        except Exception as e:
            logger.warning(
                f"[{self.name}] Cannot open XLS (missing xlrd/openpyxl?): {e}"
            )
            return []

        # Pick the monthly sheet; fall back to the first sheet if not found.
        sheet_name = next(
            (s for s in xls.sheet_names if "monthly" in s.lower()),
            xls.sheet_names[0] if xls.sheet_names else None,
        )
        if sheet_name is None:
            logger.warning(f"[{self.name}] No sheets found in XLS")
            return []

        df = xls.parse(sheet_name, header=None)

        # Data rows start around row 10 (0-indexed). Keep all rows and filter later.
        data_rows = df.iloc[10:].copy()
        if data_rows.empty:
            logger.warning(f"[{self.name}] No data rows in monthly sheet")
            return []

        # Forward-fill the year from column 1 so each month has a year value.
        data_rows[1] = data_rows[1].ffill()

        records: list[dict[str, Any]] = []
        for _, row in data_rows.iterrows():
            year = row.get(1)
            month = row.get(5)

            if not self._is_valid_year_month(year, month):
                continue

            year = int(year)
            month = int(month)
            dt = datetime(year, month, 1, tzinfo=timezone.utc)

            for col, (indicator, category) in MONTHLY_COLUMNS.items():
                raw_value = row.get(col)
                value = self._to_float(raw_value)
                if value is None:
                    continue

                records.append({
                    "date": dt,
                    "year": year,
                    "month": month,
                    "indicator": indicator,
                    "value": value,
                    "unit": UNIT,
                    "category": category,
                })

        logger.info(
            f"[{self.name}] Parsed {len(records)} observations from RVD XLS"
        )
        return records

    @staticmethod
    def _is_valid_year_month(year: Any, month: Any) -> bool:
        """Check that year and month are usable integers."""
        try:
            y = int(year)
            m = int(month)
        except (TypeError, ValueError):
            return False
        return 1979 <= y <= 2100 and 1 <= m <= 12

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Convert a cell value to float, ignoring notes/dashes/blank cells."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if pd.isna(value):
                return None
            return float(value)
        text = str(value).strip()
        if not text or text in {"-", "(", ")", "*", "", "nan"}:
            return None
        # Some cells contain note markers like "( " — strip them.
        cleaned = text.replace("(", "").replace(")", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        """Transform raw observations into EconomicData-shaped rows."""
        if not raw_data:
            return pd.DataFrame()

        rows = []
        for r in raw_data:
            rows.append({
                "source": self.name,
                "indicator": r.get("indicator", ""),
                "date": r.get("date"),
                "value": r.get("value"),
                "unit": r.get("unit", ""),
                "metadata": {
                    "category": r.get("category", ""),
                    "year": r.get("year"),
                    "month": r.get("month"),
                },
            })

        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate parsed DataFrame has required EconomicData columns."""
        required = ["source", "indicator", "date", "value", "unit"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            from core.exceptions import SchemaChangedError
            raise SchemaChangedError(self.name, required, list(df.columns))
        if df.empty:
            return True
        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            from core.exceptions import SchemaChangedError
            raise SchemaChangedError(
                self.name, ["datetime date column"], list(df.columns)
            )
        if not pd.api.types.is_numeric_dtype(df["value"]):
            from core.exceptions import SchemaChangedError
            raise SchemaChangedError(
                self.name, ["numeric value column"], list(df.columns)
            )
        return True
