import asyncio
import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

_REPORT_INTERVAL_SECONDS = 60


class PoolMonitor:
    """Periodically samples and logs SQLAlchemy async connection-pool statistics.

    The monitor runs as a background ``asyncio.Task`` and emits structured JSON
    log lines every :data:`_REPORT_INTERVAL_SECONDS`.
    """

    def __init__(self, engine: AsyncEngine, interval: int = _REPORT_INTERVAL_SECONDS) -> None:
        self._engine = engine
        self._interval = interval
        self._task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def report(self) -> dict[str, Any]:
        """Return current pool statistics as a dict.

        The underlying ``pool.status()`` is synchronous, so we access the
        sync pool through the async engine's ``sync_engine``.
        """
        pool = self._engine.sync_engine.pool
        stats: dict[str, Any] = {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "invalid": pool.status(),  # human-readable string
        }
        return stats

    def start(self) -> None:
        """Start the background reporting loop."""
        if self._task is not None and not self._task.done():
            logger.warning("PoolMonitor already running.")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="pool-monitor")
        logger.info("PoolMonitor started (interval=%ds).", self._interval)

    def stop(self) -> None:
        """Cancel the background reporting loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None
            logger.info("PoolMonitor stopped.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _loop(self) -> None:
        """Run the periodic reporting loop until stopped or cancelled."""
        try:
            while self._running:
                try:
                    stats = await self.report()
                    logger.info(
                        "db_pool_stats %s",
                        json.dumps(stats, default=str),
                    )
                except Exception:
                    logger.exception("Error collecting pool stats.")
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            logger.debug("PoolMonitor task cancelled.")


# ---------------------------------------------------------------------------
# Module-level convenience helpers
# ---------------------------------------------------------------------------

_monitor: PoolMonitor | None = None


def start_monitor(engine: AsyncEngine, interval: int = _REPORT_INTERVAL_SECONDS) -> PoolMonitor:
    """Create and start a :class:`PoolMonitor` for *engine*.

    Returns the monitor instance so callers can also invoke
    ``monitor.report()`` on demand.
    """
    global _monitor
    if _monitor is not None:
        _monitor.stop()
    _monitor = PoolMonitor(engine, interval=interval)
    _monitor.start()
    return _monitor


def stop_monitor() -> None:
    """Stop the module-level :class:`PoolMonitor`, if running."""
    global _monitor
    if _monitor is not None:
        _monitor.stop()
        _monitor = None
