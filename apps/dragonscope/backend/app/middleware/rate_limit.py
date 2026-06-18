import logging
import time
from typing import Sequence

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.redis import get_redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate-limit tier configuration
# ---------------------------------------------------------------------------
#
# Tiers:
#   - Public endpoints (no auth): 60 req/min
#   - Authenticated endpoints (general): 300 req/min
#   - Data-heavy endpoints (SQL, ML, quant, backtest): 30 req/min
#   - Write endpoints (POST/PUT/PATCH/DELETE): 50 req/min
# ---------------------------------------------------------------------------

_PUBLIC_LIMIT = 60       # requests per minute — unauthenticated
_AUTH_LIMIT = 300        # requests per minute — authenticated general
_WRITE_LIMIT = 50        # write mutations
_DATAHEAVY_LIMIT = 30    # expensive compute / large result sets

# Data-heavy endpoint prefixes — get the tightest bucket.
_DATAHEAVY_PREFIXES: tuple[str, ...] = (
    "/api/quant",
    "/api/backtest",
    "/api/data/sql",
    "/api/agents",
    "/api/compliance",
    "/api/analytics",
)

# Endpoints exempt from rate limiting.
_BYPASS_PREFIXES: tuple[str, ...] = (
    "/health",
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/metrics",
)

_WINDOW_SECONDS = 60


def _classify_request(path: str, method: str, is_authenticated: bool = False) -> tuple[str, int]:
    """Return (bucket_suffix, limit) for the request."""
    # Data-heavy endpoints (tightest)
    for prefix in _DATAHEAVY_PREFIXES:
        if path.startswith(prefix):
            return "dataheavy", _DATAHEAVY_LIMIT

    # Write mutations
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return "write", _WRITE_LIMIT

    # Authenticated vs public read
    if is_authenticated:
        return "auth", _AUTH_LIMIT

    return "public", _PUBLIC_LIMIT


def _is_bypassed(path: str) -> bool:
    for prefix in _BYPASS_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


class RateLimitMiddleware:
    """ASGI middleware implementing per-user sliding-window rate limiting
    backed by Redis sorted sets.

    Redis key schema::

        rl:{user_id}:{bucket}

    Each member is a unique request id (timestamp-based), scored by its
    epoch-millisecond timestamp.  On each request we:

    1. Remove entries older than the window.
    2. Count remaining entries.
    3. If under the limit, add the new entry.
    4. Set TTL = window so keys auto-expire.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path
        method = request.method

        # Bypass health / docs endpoints
        if _is_bypassed(path):
            await self.app(scope, receive, send)
            return

        # Identify the caller.  The auth middleware stores user info on
        # request.state; if it hasn't run yet we fall back to the client IP.
        user_id: str = getattr(getattr(request, "state", None), "user_id", None) or (
            request.client.host if request.client else "anonymous"
        )

        is_authenticated = getattr(getattr(request, "state", None), "user_id", None) is not None
        bucket, limit = _classify_request(path, method, is_authenticated)
        redis_key = f"rl:{user_id}:{bucket}"

        try:
            redis = get_redis()
            now_ms = time.time() * 1000
            window_start = now_ms - (_WINDOW_SECONDS * 1000)

            pipe = redis.pipeline(transaction=True)
            # 1. Trim entries outside the window
            pipe.zremrangebyscore(redis_key, 0, window_start)
            # 2. Count current entries
            pipe.zcard(redis_key)
            results: Sequence = await pipe.execute()

            current_count: int = results[1]

            remaining = max(0, limit - current_count)
            reset_at = int((now_ms + _WINDOW_SECONDS * 1000) / 1000)

            if current_count >= limit:
                retry_after = _WINDOW_SECONDS
                logger.warning(
                    "Rate limit exceeded: user=%s bucket=%s count=%d limit=%d",
                    user_id,
                    bucket,
                    current_count,
                    limit,
                )
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please try again later."},
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_at),
                    },
                )
                await response(scope, receive, send)
                return

            # 3. Add this request and set TTL
            member = f"{now_ms}"
            pipe2 = redis.pipeline(transaction=True)
            pipe2.zadd(redis_key, {member: now_ms})
            pipe2.expire(redis_key, _WINDOW_SECONDS + 1)
            await pipe2.execute()

            remaining = max(0, limit - current_count - 1)

        except RuntimeError:
            # Redis not initialized — let request through without rate limiting.
            logger.debug("Redis unavailable; skipping rate limit for %s", path)
            remaining = -1
            limit = -1
            reset_at = 0
        except Exception:
            # Any Redis error — fail open so we don't block real traffic.
            logger.exception("Rate limiter error for user=%s path=%s", user_id, path)
            remaining = -1
            limit = -1
            reset_at = 0

        # Wrap send to inject rate-limit headers into the response.
        async def send_with_headers(message: dict) -> None:
            if message["type"] == "http.response.start" and remaining >= 0:
                headers = list(message.get("headers", []))
                headers.append((b"x-ratelimit-limit", str(limit).encode()))
                headers.append((b"x-ratelimit-remaining", str(remaining).encode()))
                headers.append((b"x-ratelimit-reset", str(reset_at).encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)
