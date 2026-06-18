"""
Custom Prometheus metrics for DragonScope.

Provides application-level counters, histograms, and gauges beyond what
prometheus-fastapi-instrumentator gives automatically.

Usage:
    from app.metrics import (
        CACHE_HITS, CACHE_MISSES, WS_CONNECTIONS,
        EXTERNAL_API_DURATION, ML_INFERENCE_DURATION,
        record_cache_hit, record_cache_miss,
    )
"""

import logging
import time
from contextlib import contextmanager
from typing import Generator

logger = logging.getLogger(__name__)

# ── Metric placeholders (no-op when prometheus_client is not installed) ───────

try:
    from prometheus_client import Counter, Gauge, Histogram, Info

    # --- Counters ---
    API_REQUESTS_TOTAL = Counter(
        "dragonscope_api_requests_total",
        "Total API requests by endpoint and status",
        ["endpoint", "method", "status"],
    )

    CACHE_HITS = Counter(
        "dragonscope_cache_hits_total",
        "Total cache hits by cache layer",
        ["layer"],  # redis, memory, disk
    )

    CACHE_MISSES = Counter(
        "dragonscope_cache_misses_total",
        "Total cache misses by cache layer",
        ["layer"],
    )

    # --- Gauges ---
    WS_CONNECTIONS = Gauge(
        "dragonscope_ws_connections_active",
        "Number of active WebSocket connections",
    )

    DB_POOL_CHECKED_OUT = Gauge(
        "dragonscope_db_pool_checked_out",
        "Number of DB connections currently checked out from pool",
    )

    DB_POOL_OVERFLOW = Gauge(
        "dragonscope_db_pool_overflow",
        "Number of DB connections in overflow",
    )

    # --- Histograms ---
    API_REQUEST_DURATION = Histogram(
        "dragonscope_api_request_duration_seconds",
        "API request duration in seconds",
        ["endpoint", "method"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )

    EXTERNAL_API_DURATION = Histogram(
        "dragonscope_external_api_duration_seconds",
        "External API call duration by provider",
        ["provider"],
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    )

    ML_INFERENCE_DURATION = Histogram(
        "dragonscope_ml_inference_duration_seconds",
        "ML model inference duration",
        ["model"],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
    )

    # --- Info ---
    APP_INFO = Info(
        "dragonscope_app",
        "Application version and metadata",
    )
    APP_INFO.info({"version": "2.0.0", "service": "dragonscope-api"})

    _PROMETHEUS_AVAILABLE = True

except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.info("prometheus_client not installed — custom metrics disabled")

    # No-op stubs so callers don't need to check availability
    class _NoOp:
        def inc(self, *a, **kw): pass
        def dec(self, *a, **kw): pass
        def set(self, *a, **kw): pass
        def observe(self, *a, **kw): pass
        def labels(self, *a, **kw): return self
        def info(self, *a, **kw): pass

    _noop = _NoOp()
    API_REQUESTS_TOTAL = _noop
    CACHE_HITS = _noop
    CACHE_MISSES = _noop
    WS_CONNECTIONS = _noop
    DB_POOL_CHECKED_OUT = _noop
    DB_POOL_OVERFLOW = _noop
    API_REQUEST_DURATION = _noop
    EXTERNAL_API_DURATION = _noop
    ML_INFERENCE_DURATION = _noop


# ── Convenience helpers ───────────────────────────────────────────────────────

def record_cache_hit(layer: str = "redis") -> None:
    CACHE_HITS.labels(layer=layer).inc()


def record_cache_miss(layer: str = "redis") -> None:
    CACHE_MISSES.labels(layer=layer).inc()


def record_api_request(endpoint: str, method: str, status: int) -> None:
    API_REQUESTS_TOTAL.labels(endpoint=endpoint, method=method, status=str(status)).inc()


@contextmanager
def track_external_api(provider: str) -> Generator[None, None, None]:
    """Context manager to time external API calls."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        EXTERNAL_API_DURATION.labels(provider=provider).observe(elapsed)


@contextmanager
def track_ml_inference(model: str) -> Generator[None, None, None]:
    """Context manager to time ML inference."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        ML_INFERENCE_DURATION.labels(model=model).observe(elapsed)


def is_prometheus_available() -> bool:
    return _PROMETHEUS_AVAILABLE
