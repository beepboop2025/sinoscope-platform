"""Middleware to convert request JSON keys camelCase→snake_case and response snake_case→camelCase.

Excludes:
- /api/data/* responses (raw external API data the frontend expects as-is)
- /metrics responses (Prometheus text format)
"""

import json
import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse


_CAMEL_RE = re.compile(r"([A-Z])")
_SNAKE_RE = re.compile(r"_([a-z])")

# Paths whose *response* should NOT be converted (raw external data or non-JSON)
_SKIP_RESPONSE_PREFIXES = ("/api/data/", "/metrics")


def to_snake_case(name: str) -> str:
    """Convert camelCase to snake_case."""
    return _CAMEL_RE.sub(lambda m: "_" + m.group(1).lower(), name).lstrip("_")


def to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase."""
    return _SNAKE_RE.sub(lambda m: m.group(1).upper(), name)


def convert_keys(obj: object, converter) -> object:
    """Recursively convert all dict keys using converter function."""
    if isinstance(obj, dict):
        return {converter(k): convert_keys(v, converter) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_keys(item, converter) for item in obj]
    return obj


class CaseConverterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # --- Request: camelCase → snake_case ---
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type and request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
            if body:
                try:
                    data = json.loads(body)
                    converted = convert_keys(data, to_snake_case)
                    # Replace the request body with converted data
                    request._body = json.dumps(converted).encode("utf-8")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass  # Not valid JSON, pass through

        response = await call_next(request)

        # --- Response: snake_case → camelCase ---
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _SKIP_RESPONSE_PREFIXES):
            return response

        resp_content_type = response.headers.get("content-type", "")
        if "application/json" not in resp_content_type:
            return response

        # Read the response body
        body_chunks = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                body_chunks.append(chunk.encode("utf-8"))
            else:
                body_chunks.append(chunk)
        body = b"".join(body_chunks)

        if not body:
            return response

        try:
            data = json.loads(body)
            converted = convert_keys(data, to_camel_case)
            new_body = json.dumps(converted).encode("utf-8")
        except (json.JSONDecodeError, UnicodeDecodeError):
            new_body = body

        # Build new response preserving status and headers
        headers = dict(response.headers)
        headers["content-length"] = str(len(new_body))
        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
