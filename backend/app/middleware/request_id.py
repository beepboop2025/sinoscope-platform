import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import request_id_ctx, user_id_ctx

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Assigns a correlation ID to every request and injects it into:
    - request.state (for downstream handlers)
    - ContextVar (for structured logging across the entire call chain)
    - Response header (for client-side correlation)

    Also tracks request duration and sets the user_id ContextVar
    when auth middleware has populated request.state.user_id.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Set ContextVars so all loggers in this request automatically include them
        req_token = request_id_ctx.set(request_id)
        uid_token = None

        start = time.perf_counter()
        try:
            response = await call_next(request)

            # If auth middleware ran before us and set user_id, propagate it
            uid = getattr(request.state, "user_id", None)
            if uid:
                uid_token = user_id_ctx.set(uid)

            duration_ms = round((time.perf_counter() - start) * 1000, 1)

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{duration_ms}ms"

            # Structured access log
            logger.info(
                "%s %s %d %.1fms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                extra={
                    "http_method": request.method,
                    "http_path": request.url.path,
                    "http_status": response.status_code,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else None,
                },
            )

            return response
        finally:
            # Reset ContextVars to avoid leaking across requests
            request_id_ctx.reset(req_token)
            if uid_token is not None:
                user_id_ctx.reset(uid_token)
