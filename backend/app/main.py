import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.database import engine
from app.middleware.request_id import RequestIdMiddleware
from app.redis import close_redis, init_redis
from app.routes import alerts, api_keys, data, health, portfolios, users, watchlists, websocket
from app.services.websocket_manager import ws_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting DragonScope API...")
    await init_redis()
    await ws_manager.start_heartbeat()
    logger.info(f"API running on port {settings.API_PORT}")
    yield
    # Shutdown
    logger.info("Shutting down DragonScope API...")
    await ws_manager.stop_heartbeat()
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="DragonScope API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"])
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Rate limit exceeded"},
    )


# Middleware
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(data.router, prefix="/api", tags=["data"])
app.include_router(portfolios.router, prefix="/api", tags=["portfolios"])
app.include_router(watchlists.router, prefix="/api", tags=["watchlists"])
app.include_router(alerts.router, prefix="/api", tags=["alerts"])
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(api_keys.router, prefix="/api", tags=["api-keys"])
app.include_router(websocket.router, tags=["websocket"])


# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"[API Error] {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error" if not settings.DEBUG else str(exc)},
    )
