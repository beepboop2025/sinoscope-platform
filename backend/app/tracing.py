"""
OpenTelemetry tracing setup (opt-in).

Tracing is enabled only when OTEL_EXPORTER_OTLP_ENDPOINT is set as an
environment variable. If the opentelemetry packages are not installed,
this module is a silent no-op.

Usage:
    from app.tracing import setup_tracing
    setup_tracing()
"""

import logging
import os

logger = logging.getLogger(__name__)

SERVICE_NAME = "dragonscope-api"


def setup_tracing() -> None:
    """
    Initialize OpenTelemetry tracing if OTEL_EXPORTER_OTLP_ENDPOINT is set
    and the required packages are installed. Otherwise, silently skip.
    """
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT not set — tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "opentelemetry packages not installed — tracing disabled. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp-proto-grpc"
        )
        return

    # ── Provider + exporter ───────────────────────────────────────────────────
    resource = Resource.create({"service.name": SERVICE_NAME})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # ── Auto-instrument libraries ─────────────────────────────────────────────
    _instrument_fastapi()
    _instrument_sqlalchemy()
    _instrument_redis()
    _instrument_httpx()

    logger.info(f"OpenTelemetry tracing enabled — exporting to {endpoint}")


def _instrument_fastapi() -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument()
    except ImportError:
        logger.debug("opentelemetry-instrumentation-fastapi not installed — skipping")


def _instrument_sqlalchemy() -> None:
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        SQLAlchemyInstrumentor().instrument()
    except ImportError:
        logger.debug("opentelemetry-instrumentation-sqlalchemy not installed — skipping")


def _instrument_redis() -> None:
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
    except ImportError:
        logger.debug("opentelemetry-instrumentation-redis not installed — skipping")


def _instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except ImportError:
        logger.debug("opentelemetry-instrumentation-httpx not installed — skipping")
