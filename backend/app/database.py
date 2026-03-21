import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,  # Recycle connections every 30 min to avoid stale connections
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Connection pool monitoring ────────────────────────────────────────────────

def get_pool_stats() -> dict[str, Any]:
    """Return connection pool statistics for monitoring."""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalid": pool.status(),
    }


def log_pool_stats() -> None:
    """Log current pool stats at INFO level."""
    stats = get_pool_stats()
    logger.info(
        "DB pool: size=%d checked_in=%d checked_out=%d overflow=%d",
        stats["pool_size"],
        stats["checked_in"],
        stats["checked_out"],
        stats["overflow"],
    )


# ── Slow query counter (read by health endpoint) ─────────────────────────────

_slow_query_count: int = 0


def increment_slow_query_count() -> None:
    global _slow_query_count
    _slow_query_count += 1


def get_slow_query_count() -> int:
    return _slow_query_count


# ── Database health probe ─────────────────────────────────────────────────────

async def get_db_health() -> dict[str, Any]:
    """Comprehensive database health check for /api/health/db endpoint."""
    result: dict[str, Any] = {"status": "healthy"}

    # Pool stats
    result["pool"] = get_pool_stats()
    result["slow_query_count"] = get_slow_query_count()

    # Check connectivity + table sizes
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
            result["connected"] = True

            # Table sizes (top 15 largest)
            try:
                rows = await session.execute(text(
                    "SELECT relname AS table_name, "
                    "pg_size_pretty(pg_total_relation_size(relid)) AS total_size, "
                    "pg_total_relation_size(relid) AS size_bytes "
                    "FROM pg_catalog.pg_statio_user_tables "
                    "ORDER BY pg_total_relation_size(relid) DESC "
                    "LIMIT 15"
                ))
                result["table_sizes"] = [
                    {"table": r.table_name, "size": r.total_size, "bytes": r.size_bytes}
                    for r in rows
                ]
            except Exception:
                result["table_sizes"] = "unavailable"

    except Exception as e:
        result["status"] = "unhealthy"
        result["connected"] = False
        result["error"] = str(e)

    return result
