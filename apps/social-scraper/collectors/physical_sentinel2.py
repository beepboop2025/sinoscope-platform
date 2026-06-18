"""Sentinel-2 physical-anchor collector for China.

Queries the public Copernicus Data Space Ecosystem (CDSE) OData catalogue for
Sentinel-2 scene counts intersecting a China bounding box, aggregated by month.
No authentication is required for catalogue search.

If the catalogue is unavailable or the response schema changes, the collector
gracefully returns an empty result and logs a warning.
"""

import logging
from datetime import datetime, timezone

import httpx
import pandas as pd
from dateutil.relativedelta import relativedelta

from core.base_collector import BaseCollector
from core.exceptions import SchemaChangedError

logger = logging.getLogger(__name__)

# Approximate bounding box for mainland China (lon, lat).
CHINA_BBOX_WKT = (
    "POLYGON ((73.5 18, 135 18, 135 53.5, 73.5 53.5, 73.5 18))"
)

CDSE_CATALOG_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"


class Sentinel2Collector(BaseCollector):
    """Collect monthly Sentinel-2 scene-count proxy for China."""

    name = "sentinel2"
    source_type = "api"

    def __init__(self, config: dict):
        super().__init__(config)
        self.months_back = config.get("months_back", 3)
        self.catalog_url = config.get("catalog_url", CDSE_CATALOG_URL)
        self.indicator = "sentinel2_scene_count_china"
        self.unit = "scenes"

    async def collect(self) -> list[dict]:
        """Fetch monthly Sentinel-2 scene counts for China from CDSE.

        Returns a list of raw records. On any failure, logs a warning and
        returns an empty list so the engine can continue with other sources.
        """
        records: list[dict] = []
        now = datetime.now(timezone.utc)
        current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        for offset in range(self.months_back):
            month_start = current_month - relativedelta(months=offset)
            month_end = month_start + relativedelta(months=1)

            odata_filter = (
                f"Collection/Name eq 'SENTINEL-2' and "
                f"OData.CSC.Intersects(area=geography'SRID=4326;{CHINA_BBOX_WKT}') and "
                f"ContentDate/Start ge {month_start.isoformat()} and "
                f"ContentDate/Start lt {month_end.isoformat()}"
            )
            params = {
                "$filter": odata_filter,
                "$count": "true",
                "$top": "0",
            }

            try:
                resp = await self._http.get(self.catalog_url, params=params)
                resp.raise_for_status()
                payload = resp.json()
                count = payload.get("@odata.count")
                if count is None:
                    logger.warning(
                        "[%s] Missing @odata.count for month %s",
                        self.name,
                        month_start.date().isoformat(),
                    )
                    continue

                records.append(
                    {
                        "date": month_start,
                        "value": int(count),
                        "indicator": self.indicator,
                        "unit": self.unit,
                        "metadata": {
                            "bbox_wkt": CHINA_BBOX_WKT,
                            "collection": "SENTINEL-2",
                            "month": month_start.date().isoformat(),
                            "catalog_url": self.catalog_url,
                            "query_filter": odata_filter,
                        },
                    }
                )
            except httpx.HTTPError as e:
                logger.warning(
                    "[%s] HTTP error fetching scene count for %s: %s",
                    self.name,
                    month_start.date().isoformat(),
                    e,
                )
            except Exception as e:
                logger.warning(
                    "[%s] Unexpected error fetching scene count for %s: %s",
                    self.name,
                    month_start.date().isoformat(),
                    e,
                )

        logger.info(
            "[%s] Collected %d monthly Sentinel-2 scene-count records",
            self.name,
            len(records),
        )
        return records

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        """Transform raw records into EconomicData-shaped rows."""
        if not raw_data:
            return pd.DataFrame(
                columns=["date", "value", "indicator", "unit", "metadata"]
            )

        rows = []
        for record in raw_data:
            rows.append(
                {
                    "date": record.get("date"),
                    "value": record.get("value"),
                    "indicator": record.get("indicator", self.indicator),
                    "unit": record.get("unit", self.unit),
                    "metadata": record.get("metadata", {}),
                }
            )

        df = pd.DataFrame(rows)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], utc=True)
        return df

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate the parsed DataFrame schema.

        Raises SchemaChangedError if required columns are missing.
        """
        required = ["date", "value", "indicator", "unit"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SchemaChangedError(self.name, required, list(df.columns))
        return True
