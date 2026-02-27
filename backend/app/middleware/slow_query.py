"""
SQLAlchemy event-based slow query detection.

Attaches to before_cursor_execute / after_cursor_execute events on the
async engine's underlying sync engine to measure query execution time
and log warnings for queries exceeding the threshold.

Usage:
    from app.middleware.slow_query import setup_slow_query_logging
    setup_slow_query_logging(engine)  # pass the async engine
"""

import logging
import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

SLOW_QUERY_THRESHOLD_MS = 500


def setup_slow_query_logging(
    async_engine: AsyncEngine,
    threshold_ms: float = SLOW_QUERY_THRESHOLD_MS,
) -> None:
    """
    Attach slow-query logging listeners to the async engine.

    Args:
        async_engine: The SQLAlchemy async engine.
        threshold_ms: Queries taking longer than this (in ms) are logged as warnings.
    """
    # SQLAlchemy async engines wrap a sync engine; events attach to the sync one.
    sync_engine = async_engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def _after_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        start_times = conn.info.get("query_start_time")
        if not start_times:
            return

        start = start_times.pop()
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        if elapsed_ms >= threshold_ms:
            # Truncate very long queries for readability
            stmt_preview = statement[:500] + "..." if len(statement) > 500 else statement
            logger.warning(
                "Slow query detected: %.1fms — %s",
                elapsed_ms,
                stmt_preview,
                extra={
                    "slow_query_ms": round(elapsed_ms, 1),
                    "statement_length": len(statement),
                },
            )

    logger.info(
        "Slow query logging enabled (threshold=%dms)", threshold_ms
    )
