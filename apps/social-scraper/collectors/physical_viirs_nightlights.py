"""VIIRS Nighttime Lights collector for China.

This module implements a `BaseCollector` subclass for monthly VIIRS DNB
(Day/Night Band) nighttime lights over China.  Aggregating the raw radiance
values into a single country-level time-series requires access to global
GeoTIFF/COG composites and a raster processing stack (rasterio/gdal), which is
not part of the project dependency set and is not exposed by a stable,
credentials-free JSON endpoint.

Therefore the current implementation degrades gracefully: it logs a TODO and
returns an empty record set.  When a public summary service or open COG-stat
endpoint becomes available, `collect()` can be wired to fetch it and `parse()`
can transform the response into EconomicData-shaped rows.
"""

import logging

import pandas as pd

from core.base_collector import BaseCollector
from core.exceptions import SchemaChangedError

logger = logging.getLogger(__name__)


class VIIRSNightlightsCollector(BaseCollector):
    """Collector for VIIRS nighttime lights over China.

    Expected output indicator: ``viirs_nightlights_china``
    Unit: ``nW/cm2/sr``
    """

    name = "viirs_nightlights"
    source_type = "api"

    async def collect(self) -> list[dict]:
        """Fetch raw VIIRS records.

        Currently a no-op stub because a stable public endpoint that exposes
        pre-aggregated monthly radiance values for China is not available in
        the allowed dependency set.
        """
        logger.warning(
            "[%s] TODO: no stable public endpoint for aggregated monthly VIIRS "
            "nighttime lights over China (requires raster aggregation or "
            "authenticated NASA/NOAA data). Returning empty.",
            self.name,
        )
        return []

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        """Transform raw VIIRS records into EconomicData-shaped rows."""
        if not raw_data:
            return pd.DataFrame(
                columns=["indicator", "date", "value", "unit", "metadata"]
            )

        rows = []
        for record in raw_data:
            rows.append(
                {
                    "indicator": record.get(
                        "indicator", "viirs_nightlights_china"
                    ),
                    "date": record.get("date"),
                    "value": record.get("value"),
                    "unit": record.get("unit", "nW/cm2/sr"),
                    "metadata": record.get("metadata", {}),
                }
            )
        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate that the parsed DataFrame has the expected columns."""
        required = ["indicator", "date", "value", "unit"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SchemaChangedError(self.name, required, list(df.columns))
        return True
