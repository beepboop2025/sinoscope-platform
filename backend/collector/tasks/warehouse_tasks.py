"""Celery tasks for data warehouse — ETL health, quality checks, retention."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from collector.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_sync_dsn() -> str:
    settings = get_settings()
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


@celery_app.task(name="collector.tasks.warehouse_tasks.check_etl_health")
def check_etl_health() -> dict:
    """Check health of all ETL pipelines and update the etl_health table.

    Inspects Redis keys and database freshness to determine pipeline status.
    """
    settings = get_settings()
    engine = create_engine(_get_sync_dsn())

    try:
        import redis as redis_lib

        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

        with Session(engine) as session:
            from app.models.warehouse import EtlHealth

            now = datetime.now(timezone.utc)

            # Define pipelines and their Redis keys
            pipelines = {
                "crypto_collector": "market:crypto_markets",
                "forex_collector": "market:forex",
                "stocks_collector": "market:stocks",
                "bonds_collector": "market:bonds",
                "commodities_collector": "market:commodities",
                "news_collector": "market:news",
                "defi_collector": "market:defi",
                "sentiment_collector": "market:sentiment",
            }

            results = []
            for pipeline_name, redis_key in pipelines.items():
                raw = r.get(redis_key)
                if raw is None:
                    status = "failed"
                    records_processed = 0
                else:
                    import json

                    try:
                        parsed = json.loads(raw)
                        updated = parsed.get("_updated", "")
                        data = parsed.get("data", [])
                        records_processed = len(data) if isinstance(data, list) else 1

                        if updated:
                            last_update = datetime.fromisoformat(updated)
                            # If updated is naive, treat as UTC
                            if last_update.tzinfo is None:
                                age = (now.replace(tzinfo=None) - last_update).total_seconds()
                            else:
                                age = (now - last_update).total_seconds()
                            status = "healthy" if age < 300 else ("degraded" if age < 900 else "failed")
                        else:
                            status = "degraded"
                    except (json.JSONDecodeError, TypeError, ValueError):
                        status = "degraded"
                        records_processed = 0

                health = EtlHealth(
                    id=str(uuid.uuid4()),
                    pipeline_name=pipeline_name,
                    status=status,
                    last_run=now,
                    records_processed=records_processed,
                    error_count=0 if status == "healthy" else 1,
                    checked_at=now,
                )
                session.add(health)
                results.append({"pipeline": pipeline_name, "status": status})

            session.commit()
            logger.info("[WAREHOUSE] ETL health checked: %d pipelines", len(results))
            return {"status": "completed", "pipelines": results}

    except Exception as exc:
        logger.error("[WAREHOUSE] ETL health check failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        engine.dispose()


@celery_app.task(name="collector.tasks.warehouse_tasks.run_quality_checks")
def run_quality_checks() -> dict:
    """Run quality checks on all known warehouse tables."""
    engine = create_engine(_get_sync_dsn())

    try:
        with Session(engine) as session:
            from app.models.warehouse import DataQualityScore, DimAsset, FactPrice

            now = datetime.now(timezone.utc)
            tables_checked = []

            for table_name, model in [("dim_assets", DimAsset), ("fact_prices", FactPrice)]:
                # Freshness
                result = session.execute(select(func.max(model.created_at)))
                last_created = result.scalar_one_or_none()
                if last_created is not None:
                    if last_created.tzinfo is None:
                        age = (now.replace(tzinfo=None) - last_created).total_seconds()
                    else:
                        age = (now - last_created).total_seconds()
                    freshness = max(0.0, 1.0 - (age / 86400))
                else:
                    freshness = 0.0

                # Completeness
                result = session.execute(select(func.count(model.id)))
                total = result.scalar_one_or_none() or 0
                completeness = 1.0 if total > 0 else 0.0

                validity = 1.0
                overall = round(freshness * 0.4 + completeness * 0.3 + validity * 0.3, 4)

                score = DataQualityScore(
                    id=str(uuid.uuid4()),
                    table_name=table_name,
                    freshness_score=round(freshness, 4),
                    completeness_score=round(completeness, 4),
                    validity_score=round(validity, 4),
                    overall_score=overall,
                    checked_at=now,
                )
                session.add(score)
                tables_checked.append({"table": table_name, "overall_score": overall})

            session.commit()
            logger.info("[WAREHOUSE] Quality checks completed for %d tables", len(tables_checked))
            return {"status": "completed", "tables": tables_checked}

    except Exception as exc:
        logger.error("[WAREHOUSE] Quality checks failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        engine.dispose()


@celery_app.task(name="collector.tasks.warehouse_tasks.enforce_retention")
def enforce_retention(retention_days: int = 90) -> dict:
    """Delete warehouse records older than retention_days.

    Applies to: etl_health, data_quality_scores, data_lineage.
    Fact data and dimension data are kept indefinitely.
    """
    engine = create_engine(_get_sync_dsn())

    try:
        with Session(engine) as session:
            from app.models.warehouse import DataLineage, DataQualityScore, EtlHealth

            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            deleted_counts = {}

            for model, ts_col in [
                (EtlHealth, EtlHealth.checked_at),
                (DataQualityScore, DataQualityScore.checked_at),
                (DataLineage, DataLineage.created_at),
            ]:
                result = session.execute(
                    delete(model).where(ts_col < cutoff)
                )
                deleted_counts[model.__tablename__] = result.rowcount

            session.commit()
            logger.info("[WAREHOUSE] Retention enforced (%d days): %s", retention_days, deleted_counts)
            return {"status": "completed", "deleted": deleted_counts}

    except Exception as exc:
        logger.error("[WAREHOUSE] Retention enforcement failed: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        engine.dispose()
