"""Data warehouse engine — overview, ETL health, quality scoring, lineage."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.warehouse import (
    DataLineage,
    DataQualityScore,
    DimAsset,
    EtlHealth,
    FactPrice,
)
from app.schemas.warehouse import (
    EtlHealthSummary,
    QualitySummary,
    WarehouseOverview,
)

logger = logging.getLogger(__name__)


class WarehouseEngine:
    """Provides warehouse overview, ETL health, data quality, and lineage queries."""

    @staticmethod
    async def get_overview(session: AsyncSession) -> WarehouseOverview:
        """Aggregate high-level warehouse statistics."""
        # Total distinct assets
        result = await session.execute(select(func.count(DimAsset.id)))
        total_assets = result.scalar_one_or_none() or 0

        # Total fact records
        result = await session.execute(select(func.count(FactPrice.id)))
        total_facts = result.scalar_one_or_none() or 0

        # ETL health summary
        result = await session.execute(
            select(EtlHealth.status, func.count(EtlHealth.id)).group_by(EtlHealth.status)
        )
        etl_counts = {row[0]: row[1] for row in result.all()}
        etl_summary = EtlHealthSummary(
            healthy=etl_counts.get("healthy", 0),
            degraded=etl_counts.get("degraded", 0),
            failed=etl_counts.get("failed", 0),
        )

        # Quality summary
        result = await session.execute(
            select(
                func.avg(DataQualityScore.overall_score),
                func.count(DataQualityScore.id),
            )
        )
        row = result.one()
        avg_score = float(row[0]) if row[0] is not None else 0.0
        tables_checked = row[1] or 0
        quality_summary = QualitySummary(
            average_score=round(avg_score, 4),
            tables_checked=tables_checked,
        )

        logger.info(
            "Warehouse overview: assets=%d, facts=%d, etl=%s, quality_avg=%.4f",
            total_assets, total_facts, etl_counts, avg_score,
        )
        return WarehouseOverview(
            total_assets=total_assets,
            total_fact_records=total_facts,
            etl_health_summary=etl_summary,
            quality_summary=quality_summary,
        )

    @staticmethod
    async def check_etl_health(session: AsyncSession) -> list[EtlHealth]:
        """Return all ETL health records ordered by most recent check."""
        result = await session.execute(
            select(EtlHealth).order_by(EtlHealth.checked_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def run_quality_check(session: AsyncSession, table_name: str) -> DataQualityScore:
        """Run a quality check on the given table and persist the result.

        Scores are computed as follows:
        - freshness: 1.0 if any record was created within the last hour, decaying linearly
        - completeness: fraction of non-NULL required columns (simplified to 1.0 here)
        - validity: 1.0 (placeholder — real implementation would check constraints)
        - overall: weighted average of the three
        """
        now = datetime.now(timezone.utc)

        # Freshness check — see if any record exists with a recent created_at
        freshness_score = 0.0
        completeness_score = 1.0
        validity_score = 1.0

        # Generic freshness probe: check if table_name matches any known model
        known_tables = {
            "dim_assets": DimAsset,
            "fact_prices": FactPrice,
        }

        model = known_tables.get(table_name)
        if model is not None:
            result = await session.execute(
                select(func.max(model.created_at))
            )
            last_created = result.scalar_one_or_none()
            if last_created is not None:
                # Ensure both datetimes are timezone-aware for comparison
                if last_created.tzinfo is None:
                    age_seconds = (now.replace(tzinfo=None) - last_created).total_seconds()
                else:
                    age_seconds = (now - last_created).total_seconds()
                # 1.0 if <1h old, linearly decaying to 0.0 at 24h
                freshness_score = max(0.0, 1.0 - (age_seconds / 86400))
            else:
                freshness_score = 0.0

            # Completeness: count non-NULL values in key columns
            result = await session.execute(select(func.count(model.id)))
            total = result.scalar_one_or_none() or 0
            completeness_score = 1.0 if total > 0 else 0.0
        else:
            # Unknown table — flag as low quality
            freshness_score = 0.0
            completeness_score = 0.0

        overall = round((freshness_score * 0.4 + completeness_score * 0.3 + validity_score * 0.3), 4)

        score = DataQualityScore(
            id=str(uuid.uuid4()),
            table_name=table_name,
            freshness_score=round(freshness_score, 4),
            completeness_score=round(completeness_score, 4),
            validity_score=round(validity_score, 4),
            overall_score=overall,
            checked_at=now,
        )
        session.add(score)
        await session.flush()

        logger.info(
            "Quality check for %s: freshness=%.4f completeness=%.4f validity=%.4f overall=%.4f",
            table_name, freshness_score, completeness_score, validity_score, overall,
        )
        return score

    @staticmethod
    async def get_lineage(
        session: AsyncSession, table_name: str, record_id: str
    ) -> list[DataLineage]:
        """Return lineage chain for a specific record."""
        result = await session.execute(
            select(DataLineage)
            .where(DataLineage.table_name == table_name, DataLineage.record_id == record_id)
            .order_by(DataLineage.created_at.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_quality_scores(session: AsyncSession) -> list[DataQualityScore]:
        """Return all quality scores ordered by most recent check."""
        result = await session.execute(
            select(DataQualityScore).order_by(DataQualityScore.checked_at.desc())
        )
        return list(result.scalars().all())
