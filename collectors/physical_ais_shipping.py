"""AIS shipping / port-call traffic collector for China.

High-frequency AIS vessel traffic data for Chinese ports is only available
through authenticated commercial APIs (MarineTraffic, VesselFinder,
UN Global Platform AIS, Spire, etc.) or private satellite/terrestrial
receiver networks. There is no stable public, unauthenticated endpoint that
covers China.

This collector therefore degrades gracefully: it logs a TODO warning and
returns an empty record list. The parser/validate machinery is wired so the
file still satisfies the EconomicData schema and can be extended later if a
public endpoint or an API key is provided.
"""

import logging
from datetime import datetime, timezone

import pandas as pd

from core.base_collector import BaseCollector
from core.exceptions import SchemaChangedError

logger = logging.getLogger(__name__)


class AISShippingCollector(BaseCollector):
    """China AIS shipping proxy.

    Public, unauthenticated high-frequency AIS data for China is not
    available. The collector returns an empty result and logs a TODO note.
    """

    name = "ais_shipping"
    source_type = "api"

    INDICATOR = "ais_portcalls_china"
    UNIT = "calls"

    async def collect(self) -> list[dict]:
        """Fetch raw AIS records.

        Because stable public endpoints do not exist, this is currently a
        no-op that returns an empty list.
        """
        logger.warning(
            "[ais_shipping] Public unauthenticated AIS endpoint for China is "
            "not available (MarineTraffic, VesselFinder, UN Global Platform, "
            "and similar services require authenticated/commercial API keys). "
            "Skipping collection."
        )
        return []

    async def parse(self, raw_data: list[dict]) -> pd.DataFrame:
        """Transform raw AIS records into the EconomicData schema."""
        rows = []
        for r in raw_data:
            try:
                date = r.get("date")
                if isinstance(date, str):
                    date = datetime.fromisoformat(date.replace("Z", "+00:00"))
                if date is None:
                    date = datetime.now(timezone.utc)

                value = float(r["value"])
                rows.append({
                    "indicator": r.get("indicator", self.INDICATOR),
                    "date": date,
                    "value": value,
                    "unit": r.get("unit", self.UNIT),
                    "metadata": r.get("metadata", {}),
                })
            except (KeyError, ValueError, TypeError) as e:
                logger.warning(f"[ais_shipping] Parse error for record {r!r}: {e}")

        return pd.DataFrame(rows)

    def validate(self, df: pd.DataFrame) -> bool:
        """Validate that parsed rows contain the required columns."""
        if df.empty:
            return True

        required = ["indicator", "date", "value"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise SchemaChangedError(self.name, required, list(df.columns))
        return True
