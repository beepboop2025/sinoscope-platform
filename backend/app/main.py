import asyncio
import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import engine
from app.logging_config import setup_logging
from app.middleware.case_converter import CamelCaseResponse, CaseConverterMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.slow_query import setup_slow_query_logging
from app.redis import close_redis, get_redis, init_redis
from app.routes import (
    alerts, api_keys, data, health, history, portfolios, quality,
    users, watchlists, websocket,
    # Enterprise routes
    agents, backtest, compliance, notifications, quant, user_analytics,
)
from app.routes import proxy
from app.services.redis_subscriber import start_redis_subscriber
from app.services.websocket_manager import ws_manager
from app.tracing import setup_tracing

# Structured logging
setup_logging(level="INFO", json_format=True)
logger = logging.getLogger(__name__)

settings = get_settings()

# OpenTelemetry (opt-in via OTEL_EXPORTER_OTLP_ENDPOINT)
setup_tracing()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting DragonScope API...")
    await init_redis()
    await ws_manager.start_heartbeat()

    # Setup slow query detection
    setup_slow_query_logging(engine)

    # Start Redis pub/sub → WebSocket bridge
    subscriber_task = asyncio.create_task(start_redis_subscriber())

    # Start periodic DB pool monitoring (every 60s)
    async def _pool_monitor():
        from app.database import log_pool_stats, get_pool_stats
        from app.metrics import DB_POOL_CHECKED_OUT, DB_POOL_OVERFLOW
        while True:
            await asyncio.sleep(60)
            try:
                log_pool_stats()
                stats = get_pool_stats()
                DB_POOL_CHECKED_OUT.set(stats["checked_out"])
                DB_POOL_OVERFLOW.set(stats["overflow"])
            except Exception:
                pass

    pool_monitor_task = asyncio.create_task(_pool_monitor())

    logger.info(f"API running on port {settings.API_PORT}")
    yield
    # Shutdown — gracefully drain WebSocket connections
    logger.info("Shutting down DragonScope API...")
    pool_monitor_task.cancel()
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass
    try:
        await pool_monitor_task
    except asyncio.CancelledError:
        pass
    await ws_manager.stop_heartbeat()
    await ws_manager.close_all()
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="DragonScope API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=CamelCaseResponse,
)

# ── Prometheus metrics (optional but recommended) ────────────────────────────
# Install with: pip install prometheus-fastapi-instrumentator
# When installed, exposes /metrics endpoint for Prometheus scraping.
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/docs", "/redoc", "/openapi.json"],
    ).instrument(app).expose(app, endpoint="/metrics")
    logger.info("Prometheus metrics enabled at /metrics")
except ImportError:
    logger.warning(
        "prometheus-fastapi-instrumentator not installed — /metrics endpoint disabled. "
        "Install it with: pip install prometheus-fastapi-instrumentator"
    )


# ── Middleware (order matters — outermost first) ─────────────────────────────

# GZip compression for responses > 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request ID tracking + correlation
app.add_middleware(RequestIdMiddleware)

# CORS — locked down to explicit methods and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Accept"],
)

# Case conversion — request-only middleware (camelCase→snake_case for incoming JSON)
# Response conversion is handled by CamelCaseResponse (default_response_class)
app.add_middleware(CaseConverterMiddleware)

# Rate limiting (Redis-backed sliding window)
try:
    from app.middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
except ImportError:
    logger.warning("Rate limit middleware not available — skipping")

# ── Routes ───────────────────────────────────────────────────────────────────
# Core
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(data.router, prefix="/api", tags=["data"])
app.include_router(proxy.router, prefix="/api", tags=["proxy"])
app.include_router(history.router, prefix="/api", tags=["history"])
app.include_router(portfolios.router, prefix="/api", tags=["portfolios"])
app.include_router(watchlists.router, prefix="/api", tags=["watchlists"])
app.include_router(alerts.router, prefix="/api", tags=["alerts"])
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(api_keys.router, prefix="/api", tags=["api-keys"])
app.include_router(quality.router, prefix="/api", tags=["data-quality"])
app.include_router(websocket.router, tags=["websocket"])
# Enterprise
app.include_router(notifications.router, prefix="/api", tags=["notifications"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(backtest.router, prefix="/api", tags=["backtest"])
app.include_router(compliance.router, prefix="/api", tags=["compliance"])
app.include_router(quant.router, prefix="/api", tags=["quant"])
app.include_router(user_analytics.router, prefix="/api", tags=["analytics"])


# ── Global error handler ────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Always log the full stack trace server-side for diagnosis
    logger.error(
        f"[API Error] {request.method} {request.url.path}: {exc}\n"
        f"{traceback.format_exc()}"
    )
    # Never leak stack traces to clients, even in DEBUG mode
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
