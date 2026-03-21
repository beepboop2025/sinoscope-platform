import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import async_session_factory, get_pool_stats, get_slow_query_count
from app.redis import get_redis

logger = logging.getLogger(__name__)
router = APIRouter()

# Track startup time for uptime calculation
_STARTUP_TIME = time.time()
_APP_VERSION = "2.0.0"
_DEPLOY_TIMESTAMP = os.environ.get("DEPLOY_TIMESTAMP", datetime.now(timezone.utc).isoformat())


async def _check_dependency(name: str, check_fn) -> dict[str, Any]:
    """Run a health check function and measure response time."""
    start = time.perf_counter()
    try:
        result = await check_fn()
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        return {"status": "healthy", "response_time_ms": elapsed_ms, **result}
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        return {"status": "unhealthy", "response_time_ms": elapsed_ms, "error": str(e)}


async def _check_postgres() -> dict[str, Any]:
    async with async_session_factory() as session:
        await session.execute(text("SELECT 1"))
    return {"connected": True}


async def _check_redis() -> dict[str, Any]:
    r = get_redis()
    info = await r.info("server")
    await r.ping()
    return {
        "connected": True,
        "redis_version": info.get("redis_version", "unknown"),
    }


async def _check_timescale() -> dict[str, Any]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
        )
        version = result.scalar_one_or_none()
        if version:
            chunk_result = await session.execute(text(
                "SELECT coalesce(sum(num_chunks), 0) FROM timescaledb_information.hypertables "
                "WHERE hypertable_schema = 'public'"
            ))
            chunk_count = chunk_result.scalar_one_or_none() or 0
            return {"version": version, "chunks": chunk_count}
        return {"installed": False}


async def _check_collector() -> dict[str, Any]:
    r = get_redis()
    last_update = await r.get("collector:last_update")
    return {"last_update": last_update or "never"}


# ── Lightweight probe for load balancers ──────────────────────────────────────

@router.get("/health/live")
async def liveness():
    """Minimal liveness check for K8s / load balancer probes. Always returns 200."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    """Readiness probe — verifies critical dependencies are reachable."""
    pg = await _check_dependency("postgres", _check_postgres)
    redis = await _check_dependency("redis", _check_redis)

    all_healthy = pg["status"] == "healthy" and redis["status"] == "healthy"
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_healthy else "not_ready",
            "postgres": pg,
            "redis": redis,
        },
    )


# ── Comprehensive health check ────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """
    Full health check with per-dependency status, response times,
    pool stats, uptime, and version info.

    Returns:
        - status: healthy | degraded | unhealthy
        - Individual dependency status with response_time_ms
        - Database pool stats and slow query count
        - System uptime and version
    """
    checks = {}
    checks["postgres"] = await _check_dependency("postgres", _check_postgres)
    checks["redis"] = await _check_dependency("redis", _check_redis)
    checks["timescaledb"] = await _check_dependency("timescaledb", _check_timescale)
    checks["collector"] = await _check_dependency("collector", _check_collector)

    # Determine overall status
    statuses = [c["status"] for c in checks.values()]
    if all(s == "healthy" for s in statuses):
        overall = "healthy"
    elif checks["postgres"]["status"] == "unhealthy" or checks["redis"]["status"] == "unhealthy":
        overall = "unhealthy"
    else:
        overall = "degraded"

    # Pool + slow query monitoring
    try:
        pool_stats = get_pool_stats()
    except Exception:
        pool_stats = "unavailable"

    uptime_seconds = round(time.time() - _STARTUP_TIME)

    status_code = 200 if overall != "unhealthy" else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": _APP_VERSION,
            "deploy_timestamp": _DEPLOY_TIMESTAMP,
            "uptime_seconds": uptime_seconds,
            "dependencies": checks,
            "database": {
                "pool": pool_stats,
                "slow_query_count": get_slow_query_count(),
            },
        },
    )


# ── DB-specific health endpoint ───────────────────────────────────────────────

@router.get("/health/db")
async def db_health():
    """Detailed database health: pool stats, slow queries, table sizes."""
    from app.database import get_db_health
    return await get_db_health()
