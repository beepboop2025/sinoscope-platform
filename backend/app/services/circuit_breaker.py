"""
Per-API circuit breaker with CLOSED / OPEN / HALF_OPEN states.

Prevents cascading failures by short-circuiting calls to degraded
external services. Thread-safe via asyncio.Lock.

Usage:
    from app.services.circuit_breaker import get_breaker, CircuitOpenError

    breaker = get_breaker("coingecko")
    try:
        result = await breaker.call(fetch_coingecko, symbol)
    except CircuitOpenError:
        # fallback logic
        ...
"""

import asyncio
import enum
import logging
import time
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class CircuitState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted while the circuit is OPEN."""

    def __init__(self, name: str, retry_after: float):
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker '{name}' is OPEN — retry after {retry_after:.1f}s"
        )


class CircuitBreaker:
    """
    Async circuit breaker for a single named service.

    Args:
        name: Identifier for this breaker (e.g. "coingecko", "alphavantage").
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds to wait in OPEN before allowing a probe.
        half_open_max_calls: Max concurrent calls allowed in HALF_OPEN state.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls: int = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Execute *func* through the circuit breaker.

        Raises CircuitOpenError if the circuit is OPEN and the recovery
        timeout has not yet elapsed.
        """
        async with self._lock:
            self._maybe_transition_to_half_open()

            if self._state == CircuitState.OPEN:
                retry_after = self.recovery_timeout - (
                    time.monotonic() - self._last_failure_time
                )
                raise CircuitOpenError(self.name, max(retry_after, 0.0))

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError(self.name, retry_after=0.0)
                self._half_open_calls += 1

        # Execute outside the lock so we don't block other coroutines
        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            await self._record_failure()
            raise exc
        else:
            await self._record_success()
            return result

    # ── Internal state transitions ────────────────────────────────────────────

    def _maybe_transition_to_half_open(self) -> None:
        """Must be called while holding self._lock."""
        if (
            self._state == CircuitState.OPEN
            and time.monotonic() - self._last_failure_time >= self.recovery_timeout
        ):
            logger.info(
                "Circuit breaker '%s': OPEN -> HALF_OPEN (recovery timeout elapsed)",
                self.name,
            )
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                # Probe failed — re-open
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning(
                    "Circuit breaker '%s': HALF_OPEN -> OPEN (probe failed)",
                    self.name,
                )
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s': CLOSED -> OPEN (threshold=%d reached)",
                    self.name,
                    self.failure_threshold,
                )

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # Probe succeeded — close circuit
                logger.info(
                    "Circuit breaker '%s': HALF_OPEN -> CLOSED (probe succeeded)",
                    self.name,
                )
                self._state = CircuitState.CLOSED

            self._failure_count = 0
            self._half_open_calls = 0

    def reset(self) -> None:
        """Manually reset the breaker to CLOSED (useful in tests)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        self._last_failure_time = 0.0


# ── Registry (one breaker per service name) ───────────────────────────────────

_registry: dict[str, CircuitBreaker] = {}
_registry_lock = asyncio.Lock()


def get_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    half_open_max_calls: int = 1,
) -> CircuitBreaker:
    """
    Return the circuit breaker for *name*, creating it on first access.

    Configuration args are only used when the breaker is first created.
    """
    if name not in _registry:
        _registry[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
        )
    return _registry[name]
